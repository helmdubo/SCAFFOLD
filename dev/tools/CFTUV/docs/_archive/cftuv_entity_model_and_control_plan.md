# CFTUV Entity Model And Control Plan
## Current control document for entity layering and small analysis refactor

---

## Purpose

Этот документ фиксирует рабочую control-модель проекта между:

- `docs/cftuv_architecture_v2.0.md` — главным baseline-документом;
- `docs/cftuv_refactor_roadmap_for_agents.md` — широким roadmap и safe execution order.

Он не заменяет ни architecture, ни roadmap.
Его задача уже и практичнее:

- зафиксировать текущую entity model;
- развести topology / analysis views / solve;
- определить границы для `FrameRun` и `Junction`;
- зафиксировать небольшой безопасный refactor plan для текущего cleanup.

---

## Control Principles

1. `Chain` остаётся единственной solve-unit.
2. Scaffold продолжает строиться только из `chains`.
3. `FrameRun` не участвует в placement.
4. `Junction` пока не участвует в runtime solve.
5. Если `analysis` плохо режет boundary, нужно чинить split/merge policy,
   а не наращивать rescue-проходы `FREE -> H/V`.
6. `chain-first strongest-frontier` не трогать.

---

## Entity Layers

### 1. Primary Topology Entities

Это минимальные topology-единицы, вокруг которых строится весь IR.

- `Patch`
- `Chain`

#### `Patch`

Минимальная topology unit после flood fill по seam.

Примеры intrinsic-свойств:

- `face_indices`
- `normal`
- `area`
- `perimeter`
- `basis`

Примеры contextual-свойств:

- `patch_type`
- `world_facing`
- `is_cyclic`

Примеры derived-свойств:

- quilt membership
- solve diagnostics
- row / column diagnostics

#### `Chain`

Минимальная boundary unit для solve placement.

Примеры intrinsic-свойств:

- `vert_indices`
- `vert_cos`
- `edge_indices`
- `length`
- `is_closed`

Примеры contextual-свойств:

- `neighbor_kind`
- `neighbor_patch_id`
- `frame_role`
- принадлежность к loop

Примеры derived-свойств:

- scaffold placement
- anchor provenance
- runtime diagnostics

---

### 2. Composite Topology Entities

Это не atom-level сущности, а составные topology-контейнеры.

- `BoundaryLoop`
- `BoundaryCorner`

#### `BoundaryLoop`

`BoundaryLoop` — составной контейнер над ordered chains одного patch.
Это не primary entity.

Он нужен для:

- порядка обхода boundary;
- хранения loop geometry;
- `OUTER/HOLE` classification;
- corner ordering и debug.

Важно:
loop geometry сейчас не нужно выкидывать из runtime модели.
Она реально нужна для fallback/debug path.

#### `BoundaryCorner`

`BoundaryCorner` — intra-patch junction record внутри одного loop.

Corner не является самостоятельной solve-unit.
Он фиксирует:

- vertex identity;
- стык `prev_chain -> next_chain`;
- угол поворота;
- локальный boundary context одного patch.

---

### 3. Local-Derived Analysis View

- `FrameRun`

`FrameRun` — не новая topology-сущность и не новый solve-unit.
Это analysis-only derived view над уже построенными chains одного loop.

Вопрос, на который отвечает `FrameRun`:

"Эти несколько соседних chains ведут себя как одна логическая сторона или нет?"

Pipeline:

`Patch -> BoundaryLoop -> Chains -> Corners -> FrameRuns`

То есть `FrameRun` строится не из raw loop geometry напрямую,
а из уже финального loop/chains/corners представления.

#### Что `FrameRun` описывает

- последовательность соседних chain indices внутри одного loop;
- dominant frame behavior (`H_FRAME`, `V_FRAME` или отсутствие доминирующей роли);
- длину support-участков;
- длину и размер `FREE` gap-ов;
- общий chord / projected span;
- start/end corners.

#### Что `FrameRun` не делает

- не меняет topology;
- не переписывает `frame_role`;
- не заменяет `Chain` в scaffold solve;
- не лечит плохой split автоматически.

Он сначала нужен только как diagnostic layer.

#### Пример `FrameRun`

```text
Chain 0: H_FRAME  len=2.00
Chain 1: FREE     len=0.02
Chain 2: H_FRAME  len=1.45
Chain 3: FREE     len=0.03
Chain 4: H_FRAME  len=2.30
```

Если короткие `FREE` сегменты:

- действительно micro-gap,
- не меняют общий direction,
- окружены устойчивой H-support длиной,

то это один логический `H_RUN`.

Но solve всё равно должен видеть исходные `chains`.
`Run` нужен только для вывода:
"analysis раздробил одну сторону на мусорные sub-chains".

#### Initial `FrameRun` metrics

На первом этапе не вводить `confidence score`.
Сначала хранить только сырые метрики:

- `total_length`
- `support_length`
- `gap_free_length`
- `max_free_gap_length`
- `projected_u_span`
- `projected_v_span`

Если потом понадобится confidence, он должен выводиться из этих метрик,
а не появляться как новая самостоятельная semantic axis.

---

### 4. Global-Derived Analysis View

- `Junction`

`Junction` — глобальный derived view на уровне mesh vertex,
который собирает локальные corner-события из разных patches.

Это не immediate refactor target для solve.
Сначала это diagnostic / research entity.

#### Что хранит `Junction`

- `vert_index`
- `vert_co`
- ссылки на corners
- ссылки на patches
- ссылки на chains
- `valence`
- `is_open / is_closed`
- `has_mesh_border`
- counts по `H / V / FREE`

`Junction` — контейнер для более общей структурной информации:

- жёсткость узла;
- ambiguity узла;
- тип стыка patches;
- potential continuity patterns.

#### Связь `FrameRun` и `Junction`

Ключевая связка такая:

`Run endpoint -> Corner -> Junction`

То есть:

- `FrameRun` описывает local continuity внутри одного patch;
- `Corner` связывает это continuity с конкретной вершиной loop;
- `Junction` собирает эти вершины в global vertex-level topology view.

`FrameRun` и `Junction` не заменяют друг друга.
Это две разные derived-оси:

- local continuity;
- global inter-patch structure.

---

### 5. Solve Entities

- `Quilt`
- `ScaffoldMap`

Они остаются solve-level слоем.

Важно:

- `Run` сюда не поднимается;
- `Junction` сюда пока тоже не поднимается;
- solve продолжает жить в chain-first terms.

---

## Property Layers

Для runtime и docs действуют три уровня свойств:

### Intrinsic

Что сущность есть сама по себе, без соседей и solve-контекста.

Примеры:

- геометрия patch;
- геометрия chain;
- длина chain.

### Contextual

Что выводится из ближайшего topology-контекста.

Примеры:

- `patch_type`
- `world_facing`
- `neighbor_kind`
- `frame_role`
- `OUTER/HOLE`

### Derived

Что выводится из более широкого анализа или solve-контекста.

Примеры:

- `FrameRun`
- `Junction`
- quilt membership
- runtime diagnostics
- placed / unresolved status

Эта разметка нужна, чтобы не смешивать:

- topology facts;
- local semantics;
- solve result.

---

## Current Refactor Boundary

Этот документ фиксирует безопасную границу текущего cleanup.

### Что разрешено

- явно разметить поля по `intrinsic / contextual / derived`;
- добавить debug-only `FrameRun` builder;
- использовать `FrameRun` для диагностики bad split / fragmentation;
- после стабилизации добавить debug-only `Junction` builder;
- чинить open `MESH_BORDER` split rules;
- чистить semantic rescue, если он скрывает плохой split.

### Что не нужно делать сейчас

- превращать `Run` в solve-unit;
- строить `Junction-centric solve`;
- уводить runtime в новый lattice-driven placement layer;
- подменять analysis cleanup новым patch-first or loop-sequential logic;
- возвращать локальную per-chain rectification для `H/V`.

---

## Small Refactor Plan

### Step 1. Mark field layers

В `model.py` явно пометить поля как:

- intrinsic
- contextual
- derived

Это documentation-first cleanup.
Он не должен менять поведение runtime.

### Step 2. Remove failed semantic rescue

Неудачные rescue-пассы, которые уже дали regressions на `FLOOR`,
нужно убрать, а не расширять.

Смысл:
не лечить плохой split post-factum.

### Step 3. Add debug-only `_FrameRun`

В `analysis.py` добавить private analysis helper:

- `_FrameRun`
- `_build_frame_runs(...)`

Он строится из финальных chains/corners одного loop и только репортит continuity.

### Step 4. Diagnose open `MESH_BORDER` fragmentation

Через `FrameRun` нужно увидеть:

- где split действительно создаёт meaningful sides;
- где он дробит одну сторону на `H + FREE + H` мусор;
- где проблема в split, а где в classification.

### Step 5. Fix split/merge policy

После диагностики править именно:

- split criteria;
- merge criteria;
- hard-corner rules;
- support thresholds.

Но не добавлять новый широкий semantic rescue.

### Step 6. Add debug-only `_Junction`

Когда local continuity станет читаемой,
можно добавить private diagnostic layer:

- `_JunctionCornerRef`
- `_Junction`
- junction map builder

Сначала только для reports.

### Step 7. Re-evaluate integration

Только после этого решать:

- нужен ли `Junction` в persistent model;
- нужен ли он в future lattice diagnostics;
- нужен ли он в solve/runtime path вообще.

---

## Exit Conditions For This Cleanup

Cleanup считается успешным, если:

1. Новый агент видит одну и ту же entity model в docs и в guardrails.
2. `Chain` остаётся solve-unit без двусмысленности.
3. `FrameRun` даёт полезную диагностику, не меняя runtime semantics.
4. Open `MESH_BORDER` split можно обсуждать через явные runs, а не через guesswork.
5. `Junction` появляется как controlled research entity, а не как скрытый redesign solve.

---

## Short Summary

- `Patch` и `Chain` — базовые topology entities.
- `BoundaryLoop` и `BoundaryCorner` — составные topology entities.
- `FrameRun` — local-derived analysis view.
- `Junction` — global-derived analysis view.
- `Quilt` и `ScaffoldMap` — solve layer.
- Scaffold строится только из `chains`.
- `Run` нужен для анализа качества split/classification, а не для placement.
- `Junction` нужен как diagnostic/research layer, а не как immediate solve rewrite.

---
