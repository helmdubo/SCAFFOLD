# CFTUV — Critical Architectural Analysis
## Perspective: Principal Technical Art Engineer

---

## Executive Summary

CFTUV — проект с **сильным архитектурным ядром** (chain-first strongest-frontier, PatchGraph IR, typed model layer) и **серьёзной проблемой масштаба реализации**: [solve.py](file:///d:/_mimirhead/website/CFTUV/cftuv/solve.py) разросся до 6479 строк и содержит ~60 dataclasses, что делает его практически не-maintainable одним разработчиком.

Для расширения на trim mesh decals проект **нуждается в structural decomposition** solve слоя — текущая монолитная организация не выдержит второго workflow поверх.

---

## Что работает хорошо

### 1. Chain-First Strongest-Frontier — правильный принцип

Выбор chain как primary solve unit вместо patch или loop — архитектурно верный для trim/tile workflow. Это позволяет:
- точечно контролировать alignment по осям;
- органически расти через seam boundaries;
- не привязываться к фиксированной patch topology.

### 2. Два IR слоя — чёткое разделение

| IR | Где живёт | Что хранит |
|---|---|---|
| [PatchGraph](file:///d:/_mimirhead/website/CFTUV/cftuv/model.py#272-406) | [model.py](file:///d:/_mimirhead/website/CFTUV/cftuv/model.py) | topology facts — indices, не ссылки |
| [ScaffoldMap](file:///d:/_mimirhead/website/CFTUV/cftuv/model.py#549-554) | [model.py](file:///d:/_mimirhead/website/CFTUV/cftuv/model.py) | persistent solve result |

Это правильная архитектура: topology и solve decision не смешаны.

### 3. [model.py](file:///d:/_mimirhead/website/CFTUV/cftuv/model.py) — чистый, typed, без bpy

554 строки, dataclasses, enums, frozen records. **Это лучший модуль проекта.** Правила [model.py](file:///d:/_mimirhead/website/CFTUV/cftuv/model.py) НЕ импортирует `bpy/bmesh` выполняются неукоснительно.

### 4. Debug visualization — полноценный инструмент

[debug.py](file:///d:/_mimirhead/website/CFTUV/cftuv/debug.py) (620 строк) — compact и самодостаточный. Grease Pencil визуализация chains по ролям, animated frontier replay, patch fill — это production-quality debug tooling.

### 5. Документация — исключительно сильная

5 документов с общим объёмом ~100KB. Glossary, invariants, guardrails, entity model. Это **лучше задокументированный проект, чем 90% production codebases**.

---

## Критические структурные проблемы

### P1. [solve.py](file:///d:/_mimirhead/website/CFTUV/cftuv/solve.py) — 6479 строк, ~60 dataclasses: монолит v2

> [!CAUTION]
> Это **самая серьёзная проблема проекта**. [solve.py](file:///d:/_mimirhead/website/CFTUV/cftuv/solve.py) больше, чем весь остальной проект вместе взятый.

```
model.py       554 строк   (чистый)
constants.py    63 строки   (чистый)
analysis.py   3372 строки   (умеренно большой)
solve.py      6479 строк   ← ЭТО
debug.py       620 строк   (чистый)
operators.py  1000 строк   (чистый)
```

[solve.py](file:///d:/_mimirhead/website/CFTUV/cftuv/solve.py) содержит **всё**:
- 60+ dataclasses (планирование, frontier, placement, closure, diagnostics, reporting)
- Planning layer (scoring, components, tree building)
- Frontier builder (anchor search, placement, rescue paths)
- UV transfer layer
- Conformal strategy
- Closure analysis
- Row/column diagnostics
- Reporting/formatting

Правило из AGENTS.md «НЕ разбивать solve.py на подмодули (пока < 800 строк)» давно нарушено на порядок.

**Рекомендация:** decompose [solve.py](file:///d:/_mimirhead/website/CFTUV/cftuv/solve.py) на 4-5 файлов внутри `cftuv/solve/` пакета.

### P2. [analysis.py](file:///d:/_mimirhead/website/CFTUV/cftuv/analysis.py) — 3372 строки с raw dict payloads

Хотя typed private dataclasses уже введены ([_RawBoundaryLoop](file:///d:/_mimirhead/website/CFTUV/cftuv/analysis.py#66-77), [_RawBoundaryChain](file:///d:/_mimirhead/website/CFTUV/cftuv/analysis.py#79-92), [_RawPatchBoundaryData](file:///d:/_mimirhead/website/CFTUV/cftuv/analysis.py#94-100)), всё ещё остаётся много inline dict logic в промежуточных шагах.

Corner detection идёт по двум путям (closed `OUTER` vs open `MESH_BORDER`) с не полностью одинаковой семантикой — acknowledged debt, но до сих пор не решённый.

### P3. Explosion of frozen dataclasses в solve.py

~60 `@dataclass(frozen=True)` в [solve.py](file:///d:/_mimirhead/website/CFTUV/cftuv/solve.py) — большинство используются только в одном-двух местах, как typed wrapper вокруг того, что раньше был tuple. Это **overcorrection** из tuple-soup: вместо поиска правильных абстракций каждый return contract стал отдельным классом.

Примеры одноцелевых records, которые можно упростить:
- [ClosurePreconstraintOptionResult](file:///d:/_mimirhead/website/CFTUV/cftuv/solve.py#270-278)
- [DualAnchorRectificationPreview](file:///d:/_mimirhead/website/CFTUV/cftuv/solve.py#313-319)
- [AnchorPairSafetyDecision](file:///d:/_mimirhead/website/CFTUV/cftuv/solve.py#336-340)
- [DualAnchorClosureDecision](file:///d:/_mimirhead/website/CFTUV/cftuv/solve.py#342-346)
- [ClosurePreconstraintApplication](file:///d:/_mimirhead/website/CFTUV/cftuv/solve.py#348-354)

**Проблема не в записях самих по себе**, а в том, что 60 public types в одном файле — это API surface, который невозможно удержать в голове.

### P4. Нет абстрактного Solve Pipeline

Текущий pipeline жёстко залинкован:
```
operators.py → build_solver_graph() → plan_solve_phase1() → build_root_scaffold_map() → execute_phase1_preview()
```

Нет общей абстракции "solve pipeline", которая позволила бы:
- подменить planning strategy;
- подключить другой placement strategy (необходимо для decals);
- инжектировать post-processing passes.

---

## Проблемы, которые помешают развитию в сторону Trim Mesh Decals

### D1. Нет абстракции "UV Strategy" по типу patch

Сейчас [PatchType](file:///d:/_mimirhead/website/CFTUV/cftuv/model.py#9-15) (`WALL`, `FLOOR`, `SLOPE`) — dispatch key для поведения, но dispatch происходит через inline `if/elif` в solve, а не через strategy pattern. Для decals нужно как минимум:
- `DECAL_PLANAR` — flat projected decal;
- `DECAL_TRIM` — trim sheet mapped decal;
- `DECAL_WRAP` — wrap-around decal.

Каждый из этих типов потребует своей placement strategy, но текущая архитектура не имеет точки расширения.

### D2. ScaffoldMap не хранит reverse mapping

Нет обратной связи `UV координата → 3D позиция`. Для trim mesh decal generation нужно:
- знать bounding box UV patch'а в UV space;
- вычислить 3D geometry, которую нужно сгенерировать;
- правильно ориентировать decal mesh.

### D3. Нет "tile" / "trim" абстракции

Для trim decals нужна сущность, описывающая прямоугольный участок trim sheet:
- позиция в trim atlas;
- размер (в UV);
- допустимые оси растяжения;
- правила стыковки с соседними tiles.

Этого нет ни в model, ни в planning.

### D4. Нет mesh generation layer'а

CFTUV сейчас только **пишет UV координаты** в существующую геометрию. Для trim mesh decals нужно **создавать новую геометрию** (flat quads, projected strips). Это принципиально другой output pipeline.

---

## Рекомендации по архитектурным изменениям

### R1. Decompose [solve.py](file:///d:/_mimirhead/website/CFTUV/cftuv/solve.py) → `cftuv/solve/` package

```
cftuv/solve/
├── __init__.py          # public API re-exports
├── planning.py          # SolverGraph, SolvePlan, scoring (~800 lines)
├── frontier.py          # FrontierRuntimePolicy, chain placement (~1500 lines)
├── transfer.py          # UV transfer + conformal (~800 lines)
├── diagnostics.py       # closure/row/column reports (~600 lines)
├── reporting.py         # format_*_report functions (~500 lines)
└── _records.py          # internal dataclasses (~400 lines)
```

**Это безопасно делать сейчас**: все функции в [solve.py](file:///d:/_mimirhead/website/CFTUV/cftuv/solve.py) уже prefixed и stateless/почти stateless. Imports из [operators.py](file:///d:/_mimirhead/website/CFTUV/cftuv/operators.py) не изменятся.

### R2. Ввести Strategy Pattern для Placement

```python
class PlacementStrategy(Protocol):
    def place_chain(self, chain, node, start_anchor, end_anchor, scale, direction) -> list[Vector]:
        ...
    def supports_patch_type(self, patch_type: PatchType) -> bool:
        ...
```

Текущий [_cf_place_chain](file:///d:/_mimirhead/website/CFTUV/cftuv/solve.py#4677-4715) станет `WallPlacementStrategy`. Для decals — `DecalPlacementStrategy`.

### R3. Ввести TrimSheet layer в model.py

```python
@dataclass
class TrimTile:
    uv_origin: Vector     # bottom-left в trim atlas
    uv_size: Vector       # width, height в UV
    stretch_axis: str     # 'U', 'V', 'BOTH', 'NONE'
    edge_rules: dict      # stitch rules per edge

@dataclass
class TrimSheet:
    tiles: list[TrimTile]
    atlas_size: tuple[int, int]
```

### R4. Ввести MeshGenerator protocol для decals

```python
class MeshGenerator(Protocol):
    def generate(self, patch: PatchNode, scaffold: ScaffoldPatchPlacement, trim_tile: TrimTile) -> BMeshFragment:
        ...
```

Этот слой производит геометрию, а не UV координаты. Он должен жить отдельно от [solve](file:///d:/_mimirhead/website/CFTUV/cftuv/solve.py#554-578).

### R5. Centralize Solve Policy (уже в roadmap)

Согласен с Phase 2 из [cftuv_refactor_roadmap_for_agents.md](file:///d:/_mimirhead/website/CFTUV/docs/cftuv_refactor_roadmap_for_agents.md). [SolveView](file:///d:/_mimirhead/website/CFTUV/cftuv/solve.py#156-209) уже частично реализован — его нужно дотянуть до полноценного single-source-of-truth для solve rules.

---

## Порядок действий — что делать прямо сейчас

| Приоритет | Действие | Риск | Буст |
|---|---|---|---|
| **1** | Decompose [solve.py](file:///d:/_mimirhead/website/CFTUV/cftuv/solve.py) → package | Низкий (механический рефакторинг) | Высокий (основа для всего дальнейшего) |
| **2** | Стабилизировать regression snapshot baseline | Нулевой | Средний (безопасность будущих изменений) |
| **3** | Phase 1A: typed raw payload в analysis | Низкий | Средний |
| **4** | Ввести PlacementStrategy protocol | Средний | Высокий (extension point для decals) |
| **5** | Ввести TrimSheet/TrimTile model | Нулевой (новый код) | Высокий (фундамент для decals) |

> [!IMPORTANT]
> **Пункт 1 (decompose solve.py) критически блокирует всё остальное.** 6479 строк — это не просто неудобство, это архитектурный ceiling. Пока [solve.py](file:///d:/_mimirhead/website/CFTUV/cftuv/solve.py) монолитный, любое расширение будет увеличивать его и ухудшать ситуацию.

---

## Что НЕ нужно менять

- **Chain-first strongest-frontier** — правильный принцип, не трогать
- **PatchGraph как central IR** — keep as is
- **ScaffoldMap как persistent solve result** — keep as is
- **model.py** — модуль в отличном состоянии
- **debug.py** — compact и работает
- **Grease Pencil debug** — production quality

---

## Вопросы для обсуждения

1. **Decompose solve.py** — готов ли ты к этому сейчас? Это чисто механический рефакторинг, но его нужно делать аккуратно.

2. **Trim mesh decals** — какой конкретный workflow ты видишь? Варианты:
   - A) Decal mesh генерируется *из* scaffold UV layout (UV → mesh)
   - B) Decal placement — отдельный pipeline, который использует PatchGraph, но не ScaffoldMap
   - C) Hybrid: scaffold определяет layout, a decal генератор создаёт mesh + UV

3. **PatchType расширение** — планируешь ли ты новые типы patches для decals, или decal — это отдельный workflow поверх существующих WALL/FLOOR/SLOPE?

4. **Analysis corner detection** — два пути (closed OUTER vs open MESH_BORDER) — это intentional design или technical debt, который мешает?

---
