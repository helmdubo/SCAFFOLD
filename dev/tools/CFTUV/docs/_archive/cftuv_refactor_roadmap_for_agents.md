# CFTUV Refactor Roadmap For Agents
## Critical review, priorities, and safe execution order

---

## Purpose

Этот документ нужен для AI агентов и будущих рефакторингов.

Он не заменяет `cftuv_architecture_v2.0.md`.
Наоборот: архитектурный документ остаётся главным источником истины,
а `docs/cftuv_entity_model_and_control_plan.md` фиксирует текущую entity model и
границы малого cleanup в `analysis.py`.
Этот файл нужно читать после architecture и до этого roadmap,
а этот файл описывает:

- какие structural problems уже видны в коде;
- какие из них реально опасны;
- в каком порядке их исправлять;
- что нельзя ломать по пути.

Важно:
этот roadmap не должен переопределять entity hierarchy.
Для текущего runtime cleanup канонической считается схема:

- primary topology: `Patch`, `Chain`;
- composite topology: `BoundaryLoop`, `BoundaryCorner`;
- local-derived analysis: `FrameRun`;
- global-derived analysis: `Junction`;
- solve layer: `Quilt`, `ScaffoldMap`.

Главная цель: не делать большой "красивый" рефакторинг вслепую.
Нужно идти малыми фазами, сохраняя chain-first strongest-frontier.

---

## Non-Negotiable Invariants

Любой рефакторинг обязан сохранять:

1. Scaffold остаётся `chain-first strongest-frontier`, не patch-first.
2. `HOLE` loop не должен участвовать в scaffold placement pool.
3. Quilt solve connectivity и topology connectivity - не одно и то же.
4. `analysis.py` строит topology IR, `solve.py` не пересчитывает topology.
5. `PatchGraph` остаётся центральным topology IR.
6. Debug visualization обязана продолжать работать на каждой фазе.
7. Временный UV-dependent шаг в `analysis.py` нельзя размазывать по другим частям analysis.

---

## Current Structural Findings

### F1. Solve policy размазана по коду

Сейчас solve rules живут не в одном слое, а во множестве локальных условий:

- `OUTER`-only filtering;
- same-type propagation;
- tree-edge-only cross-patch sewing;
- conformal-only fallback;
- seed restrictions;
- anchor restrictions.

Это уже дважды привело к bug drift:

- `HOLE` patches попадали в planning, но не были достижимы frontier;
- ring/cylinder quilts замыкались в UV cycle, хотя должны были оставаться tree.

Риск:
любое новое правило solve снова придётся дублировать в нескольких местах.

### F2. В `analysis.py` нет формализованного контракта для raw payload

Промежуточный pipeline до построения финальных `BoundaryChain` всё ещё живёт на
`raw_loop` / `raw_chain` dict payload.

Риск:

- поля появляются и исчезают по шагам неявно;
- `dict.get(...)` скрывает ошибки контракта;
- безопасно менять split/merge pipeline трудно.

Это не просто stylistic issue.
Без typed intermediate payload любой следующий refactor topology builder остаётся partly blind.

### F3. В `analysis.py` есть риск рассинхрона между raw chains и final chains

Сейчас pipeline логически выглядит так:

1. построить raw chains;
2. построить `BoundaryChain`;
3. merge border chains;
4. построить corners.

Но corner generation ещё частично опирается на `raw_chains`, а не только на финальную chain topology.

Риск:
после merge corner metadata может уже не соответствовать финальному loop layout.
Это не обязательно ломает каждый меш, но создаёт скрытый источник нестабильности.

### F4. `analysis.py` не полностью чистый: `OUTER/HOLE` classification идёт через UV side effects

Update 2026-03:
The UV boundary is intentionally retained. `OUTER` / `HOLE` classification for
multi-loop patches still relies on the isolated temporary UV unwrap step,
because wrapped / cylindrical topology is not safely reducible to a simple
planar basis projection.
Planar nesting is allowed only as diagnostics-only shadow data.

`_classify_loops_outer_hole()` использует временный UV unwrap через Blender operator.
Это единственный явно допущенный side effect внутри analysis pipeline.

Риск:

- debug path временно мутирует UV layer и selection state;
- semantics "analysis только читает topology" нарушается;
- шаг плохо изолирован и осложняет дальнейший refactor analysis.

Это не значит, что функцию надо срочно выкинуть любой ценой.
Но её side effects должны быть локализованы, документированы и не должны расползаться дальше.

### F5. Scaffold result не сериализуется и не кэшируется в удобном для регрессии виде

Сейчас после правок сложно ответить на вопрос "что именно изменилось в scaffold".
Сравнение идёт в основном через консоль и ручной осмотр.

Риск:

- regression harness остаётся ручным;
- сложно сравнить scaffold до/после рефактора;
- debug iteration cycle медленнее и менее надёжен, чем должен быть.

Важно:
речь не обязательно о тяжёлом persistent cache сразу.
Минимальный baseline уже реализован как markdown snapshot
(`PatchGraph Snapshot` + `Scaffold Snapshot`),
но он всё ещё manual-first и нужен дальнейший cleanup agreed regression set.

### F6. Frontier state хранится как набор параллельных registry

Сейчас frontier builder использует отдельно:

- `point_registry`;
- `vert_to_placements`;
- `placed_chain_refs`;
- `placed_chains_map`;
- `chain_dependency_patches`;
- `build_order`.

Риск:
это state synchronization problem.
Чем больше special cases, тем выше шанс забыть обновить одну из структур.

### F7. Solve IR содержит поля и типы, которые выглядят как контракт, но частично transitional

Проблемы этого класса:

- `ScaffoldPatchPlacement` содержит поля, которые либо не заполняются полностью, либо выглядят как future fields;
- есть stringly-typed runtime semantics (`source_kind`, `status`);
- остаются sentinel-based соглашения (`neighbor_patch_id = -1 / -2`).

Риск:
агент или разработчик начинает верить этому IR больше, чем код реально гарантирует.

### F8. Есть две разные связности, но API это не подчёркивает достаточно жёстко

Существуют:

- topology connectivity (`PatchGraph.connected_components()`);
- solve connectivity (`solve_components`, attachment-derived).

Обе нужны.
Проблема не в наличии двух моделей, а в том, что их слишком легко перепутать.

### F9. Tree-only scaffold solve не компенсирует closure seam drift

После исправления ring-wrap bug quilt остаётся tree, что правильно.
Но non-tree closure seams теперь остаются intentional cuts без отдельного correction pass.

Риск:

- на closure seam может накапливаться как span drift, так и positional phase drift вдоль рабочей оси seam;
- `V_FRAME<->V_FRAME` и `H_FRAME<->H_FRAME` могут дать заметный seam mismatch;
- one-edge `FREE` bridges усиливают drift, потому что path до closure становится мягче.

Важно:
это не refactor bug и не аргумент возвращать UV cycle.
Это отдельная runtime-стабилизационная задача после tree-only solve.

Важно для runtime semantics:
- `FREE` chains остаются `endpoint-hard`;
- `H/V` chains целевым образом должны трактоваться как `axis-hard, span-soft`, а не как обычная dual-anchor interpolation;
- локальная per-chain rectification для `H/V` уже показала structural regression и временно отключена;
- следующий безопасный шаг здесь не новый локальный snap, а patch/quilt-level orthogonal frame solve.

---

## Refactor Strategy

Не делать монолитный rewrite.

Правильный порядок:

1. Зафиксировать regression cases и snapshot baseline.
2. Формализовать raw payload в `analysis.py`.
3. Стабилизировать topology consistency в `analysis.py`.
4. Изолировать analysis side effects там, где это ещё нужно.
5. Вынести solve policy в один явный слой.
6. Упаковать frontier runtime state.
7. Потом чистить типы и IR.

Этот порядок важен.
Если сначала "чистить классы", а solve rules всё ещё размазаны по коду,
вы просто получите красиво оформленный источник новых багов.

---

## Parallel Runtime Track. Frame Alignment And Closure Stability

### Why This Is Separate

Эта проблема не является прямым продолжением текущих architecture-refactor phases.
Она появилась как следующая runtime-граница после правильного перехода к tree-only quilt sewing
и после стабилизации базового chain-first frontier.

Поэтому её лучше вести как отдельный track:

- не смешивать с Phase 1A/1B/1C;
- не блокировать Phase 2;
- но и не терять как "потом как-нибудь".

### Problem Statement

Tree scaffold размещает patches последовательно от root.
Каждый шаг вносит небольшой residual:

- scale rounding;
- snapped frame direction;
- guided `FREE` placement;
- anchor interpolation.

Когда quilt topology содержит цикл, tree solve разрезает его правильно,
но accumulated residual остаётся на non-tree closure seam.

Отдельно от этого есть второй runtime-класс проблемы:

- геометрически коллинеарные `H_FRAME` / `V_FRAME` внутри одного quilt
  могут получать разные UV offsets;
- визуально это выглядит как "гуляющие" горизонтальные или вертикальные ряды,
  хотя в 3D они лежат в одной линии;
- это уже не чистый closure bug, а недостаток согласованности row / column placement.

Это даёт два разных runtime case:

1. `Dual-anchor closure seam`
   Обе стороны closure seam уже имеют два anchor.
   Здесь проблема в самих anchor positions и accumulated span, а не во внутренних точках chain.

2. `One-anchor closure-sensitive seam`
   Хотя бы одна сторона closure-sensitive path ещё строится от одного anchor.
   Здесь главная цель - prevention: не дать frontier прийти к closure через слабый `FREE` path,
   если есть frame continuation.

3. `Untouched tree-child ingress`
   Patch топологически входит в quilt и связан разрешённым tree edge,
   но ingress chain до него не набирает обычный frontier score.
   В результате patch ошибочно падает в `unsupported` / fallback conformal,
   хотя topology и role graph у него корректны.

### Ordered Plan

Детальные runtime heuristics, thresholds и production-case notes вынесены в
`docs/cftuv_runtime_notes.md`.
Эта секция должна описывать порядок работ и decision points, а не заменять собой operational log.

#### Step 0. Diagnostics First

Сначала расширить диагностику до двух типов отчётов:

1. `closure seam diagnostics`
2. `row / column diagnostics`

Для closure seams текущая база уже есть:

- quilt id;
- patch pair;
- owner/target chain refs;
- seam role (`H/H`, `V/V`);
- anchor mode (`dual-anchor`, `one-anchor`, `mixed`);
- canonical 3D span;
- owner / target UV span;
- axis error;
- phase offset вдоль рабочей оси seam;
- cross-axis offset;
- общий shared-vertex UV delta;
- path length in tree;
- free bridge count on path.

Для row / column diagnostics добавить:

- grouping `H_FRAME` chains по общей 3D row class;
- grouping `V_FRAME` chains по общей 3D column class;
- UV scatter внутри каждой группы (`max`, `mean`);
- sample count и суммарную длину chains в группе;
- признак, является ли группа closure-sensitive.

Без этого любой snap или pre-constraint будет слепым.

Текущий статус:

- `row / column diagnostics` уже реализованы в `solve.py` как `FrameDiag`;
- отчёт сохраняется в `ScaffoldQuiltPlacement.frame_alignment_reports`;
- текущая practical версия намеренно ограничена `WALL.SIDE` и не притворяется общим orthogonal solve;
- точечный `closure pre-constraint` уже реализован после diagnostics;
- следующий шаг track — повторный замер production meshes и decision point по `row / column snap post-pass`.

#### Step 1. Closure Pre-Constraint First

Первый runtime fix после diagnostics должен быть точечным и low-risk:

- добавить closure pre-constraint только для closure-sensitive seams;
- не менять поведение non-cyclic quilts;
- не трогать chains, которые не участвуют в closure path;
- использовать canonical 3D span / axis как guide до момента placement.

Это точечнее и безопаснее, чем quilt-wide post-pass.

Текущий статус реализации:

- pre-constraint встроен в frontier placement path;
- он активируется только для `closure-sensitive` matched non-tree same-role pairs;
- текущая версия не трогает scoring и не делает quilt-wide snap;
- все текущие operational детали этого шага вынесены в `docs/cftuv_runtime_notes.md`;
- practical задача следующего шага — повторный замер на real meshes.

#### Step 1A. Controlled Reachability Rescue

После production mesh `walls.011` стало ясно, что есть отдельный runtime case:
patch может быть корректно sewn в `QuiltPlan`, но не получать ни одного placed chain,
если ingress в него существует только как weak / tiny tree-entry candidate.

Правильный порядок rescue здесь:

1. `tree_ingress`
   Если patch ещё untouched, но висит на разрешённом tree edge и имеет ровно один
   `cross_patch` anchor, разрешить один контролируемый ingress placement.
   Приоритет: обычный `H/V` > corner-split `H/V` > one-edge `FREE`.

2. `free_ingress`
   Если patch уже начат, но следующий жёсткий chain закрыт one-edge `FREE` corridor,
   разрешить один bootstrap bridge до внутреннего `H/V`.

3. `closure_follow`
   Только после этого добирать same-role non-tree closure partner, если его pair уже placed.

Это не новый solve mode. Это stall-recovery path внутри того же chain-first frontier.

#### Parallel branch. Landmark diagnostics

Эта ветка не должна блокировать runtime fixes, потому что её первые шаги zero-risk:
она ничего не меняет в placement path, а только измеряет будущую coarse frame structure.

Что можно делать уже параллельно:

1. identify lattice nodes
   - `cross node`: есть и `H`, и `V`, минимум из двух patches;
   - `axis node`: есть одна ось, но перенос идёт через несколько patches;
   - `weak node`: один patch only и/или `FREE`-dominated topology.

2. build axis constraints
   - отдельно для `H` и `V`;
   - без pairwise-all-path averaging как основной модели;
   - базовая единица constraint = axis edge между lattice nodes.

3. measure residuals
   - cycle residual;
   - row / column inconsistency;
   - disagreement между альтернативными путями как diagnostics, а не как повод сразу переписывать placement.

Это уже полезно для production meshes и не ломает runtime.

#### Step 2. Re-Measure

После closure pre-constraint снова прогнать diagnostics:

- closure residual;
- row / column scatter;
- особенно кейсы с `FREE bridge` на closure path.
- отдельно production meshes с `untouched tree-child patch`, чтобы проверить,
  что tree-connected `WALL.SIDE` patches больше не уходят в fallback conformal только из-за ingress threshold.

Если closure residual ушёл, а row scatter остался, это уже отдельный alignment case,
а не closure bug.

#### Step 3. Conservative Row / Column Snap Post-Pass

Только если diagnostics всё ещё показывают значимый scatter, добавить
очень ограниченный snap post-pass:

- только для подтверждённых row / column classes;
- только для `H_FRAME` / `V_FRAME`;
- только вне `FREE`;
- только при scatter выше порога;
- weighted average по длине chain и/или strength;
- не как новый solve layer, а как консервативный post-pass после frontier.

Первая practical цель здесь — `WALL.SIDE` cases.

#### Step 4. Only Then Revisit Wider Prevention

Если после этого всё ещё остаются production cases, уже потом возвращаться к:

- closure-aware scoring;
- dual-anchor closure correction pass;
- optional seam equalization.

Но не раньше, чем появятся данные после diagnostics и closure pre-constraint.

### Non-Goals

Не делать:

- возврат к patch wrap или UV cycle;
- большой orthogonal frame graph solve на этом этапе;
- persistent override layer / dirty-scope system ради этой задачи;
- quilt-wide snap "на всякий случай" без diagnostics;
- off-axis correction для `H_FRAME` / `V_FRAME`;
- маскировку drift простым усреднением UV targets на transfer stage.

Дополнительно:

- не добавлять новые persistent opt-out поля в IR до появления реального manual case;
- в этой фазе достаточно уважать текущие role/type guards и не трогать `FREE`.

### Success Criteria

- non-tree closure seams диагностируются явно;
- row / column groups диагностируются явно;
- tree-connected `WALL.SIDE` patches больше не падают в `unsupported` только потому,
  что ingress chain остался ниже обычного frontier threshold;
- ring/closed-house cases сохраняют intentional cut seam без заметного V/V или H/H drift;
- collinear `H_FRAME` / `V_FRAME` группы перестают гулять по cross-axis без необходимости;
- paths с `FREE bridge` больше не являются "тихим усилителем" closure mismatch;
- runtime fix не ломает tree-only solve и не возвращает cycle sewing.

Для lattice branch критерий жёстче и уже не диагностический:

- любые `H_FRAME` chains внутри одной solved row-class должны иметь одинаковую UV row-coordinate в пределах epsilon;
- любые `V_FRAME` chains внутри одной solved column-class должны иметь одинаковую UV column-coordinate в пределах epsilon;
- если component lattice disconnected или `FREE`-dominated, эта гарантия на него не распространяется by design.

### Immediate Code Entry Points

Ближайшая practical implementation order:

1. `solve.py -> build_root_scaffold_map()`
   Здесь уже есть центральная точка после frontier build и до final transfer.

2. `solve.py -> _collect_quilt_closure_seam_reports()`
   Использовать как существующий шаблон для нового row / column diagnostic report.

3. `solve.py -> _cf_resolve_candidate_anchors()` / placement path
   Здесь уже встроен точечный closure pre-constraint; следующий агент должен сначала смотреть логи после него, а не перепридумывать placement path.

4. `solve.py -> build_quilt_scaffold_chain_frontier()` stop-path
   Здесь теперь живёт узкий rescue order:
   `tree_ingress` -> `free_ingress` -> `closure_follow`.
   Следующий агент не должен превращать этот блок в patch-loop traversal.

5. `solve.py -> placed_chains_map` post-pass перед `_cf_build_envelopes()`
   Это правильное место для консервативного row / column snap,
   если diagnostics подтвердят, что он действительно нужен.

---

## Parallel research branch. Pre-frontier landmark alignment pass

Это не "следующая большая фаза после всего", а отдельная ветка с разным уровнем риска:

- Steps 1-3 diagnostics можно вести параллельно runtime fixes уже сейчас;
- coarse lattice solve допустим после появления стабильных diagnostics;
- integration в placement path разрешена только после того, как blocking production meshes перестанут терять patches по reachability.

Предпочтительный термин для результата:
`aligned frame lattice`.

Почему не `aligned parallel corpus`:

- `parallel corpus` звучит как термин из NLP;
- нам нужен не набор последовательностей, а временная геометрическая решётка;
- `frame lattice` лучше отражает row / column landmarks и их связи.

### Canonical metric

Не использовать:

- raw polyline length;
- endpoint-to-endpoint projection.

Использовать только:

- per-segment role-aligned accumulated span;
- с локальным basis каждого patch / chain;
- как constraint per axis edge, а не как pairwise-all-path average.

Практический смысл:

- bevel noise не должен раздувать span;
- L-shaped path не должен "срезаться" прямой между endpoints;
- multi-patch path должен суммироваться в basis соответствующих patches.

### Solve model

Минимальная безопасная первая итерация:

1. собирать только strong / axis `H/V` lattice nodes;
2. строить transient axis-edge constraints;
3. считать residuals на циклах как diagnostics;
4. решать coarse grid как две 1D least-squares задачи;
5. не писать ничего persistent в `PatchGraph` / `ScaffoldMap`.

### Integration rule

Если lattice позже попадёт в frontier path, правильная семантика такая:

- не создавать fake scaffold placements;
- не подменять обычные placed chain points;
- использовать compact transient lattice coordinate storage;
- вводить новый provenance: `source_kind='lattice_anchor'`.

Первая допустимая practical integration:

- diagnostics + guide для ingress choice;
- затем closure-sensitive / dual-endpoint `H/V` placement;
- и только потом более широкие placement assists, если production meshes подтвердят пользу.

Не делать на первом шаге:

- quilt-wide orthogonal re-solve;
- patch-first placement;
- editable persistent constraint layer;
- прямую запись coarse lattice в runtime как будто это уже placed scaffold;
- массовый snap всех chains без diagnostics.

## Phase 0. Regression Harness And Snapshot Baseline

### Goal

Создать минимальный набор проверок и сравнений, чтобы безопасно делать следующие фазы.

### Tasks

1. Собрать эталонные production-like meshes:
   - simple wall;
   - wall with hole-attached patches;
   - floor caps;
   - closed ring house;
   - mixed wall/floor;
   - bevel-heavy wall.

2. Для каждого кейса фиксировать:
   - patch count;
   - quilt count;
   - unsupported patch ids;
   - invalid closure count;
   - closure seam residuals для non-tree same-role seams;
   - final conformal fallback count;
   - заметные frontier logs.

3. Сделать один markdown checklist "expected behavior per mesh".

4. Определить стабильный snapshot/report format, который можно сравнивать до/после:
   уже есть минимальная реализация (`PatchGraph Snapshot` + `Scaffold Snapshot`),
   но формат всё ещё можно стабилизировать дальше.
   - quilt ids;
   - patch membership;
   - unsupported patches;
   - build order;
   - closure status;
   - pinned/unpinned summary.

5. Реализовать минимальный способ сохранить этот snapshot baseline для agreed regression meshes:
   минимальный markdown snapshot уже есть, дальше вопрос в coverage и discipline использования.
   - в файл;
   - или в стабильный markdown/text report;
   - но не оставлять это только на уровне "формат придуман, реализации нет".

- closure-follow, free-ingress и tree-ingress rescue candidates в `solve.py`
  теперь тоже живут как explicit dataclass records, а не как local `best_candidate` tuples.
- `ScaffoldPatchPlacement.gap_reports` теперь живёт как typed persistent record
  (`ChainGapReport`), а transfer/apply path больше не опирается на raw key tuples
  без именованных contracts.
- канонические aliases `PatchEdgeKey`, `LoopChainRef`, `SourcePoint` теперь вынесены
  в `model.py` и протянуты через `solve.py`; seed-chain choice и seed-placement payload
  тоже больше не возвращаются как анонимные tuples.
- planning / closure-cut path в `solve.py` тоже частично очищен от tuple-soup:
  attachment-neighbor refs, endpoint context, direction/anchor options, best chain-pair
  selection и endpoint-support stats теперь оформлены как explicit records.
- shared closure offsets / preconstraint metric, attachment preference key и
  dual-anchor resolution path теперь тоже живут на typed records; rescue candidate
  ranks больше не передаются как анонимные tuple keys.
- remaining anchor/preconstraint helper returns тоже дочищены: found-anchor payload,
  axis-safety / dual-anchor closure decision и closure-preconstraint application
  теперь возвращаются как explicit records, а не как raw tuples.
- report-layer formatter’ы (`analysis.py` / `solve.py`) теперь тоже возвращают единый
  typed payload (`FormattedReport`) вместо ad-hoc `(lines, summary)` pairs; `operators.py`
  читает `.lines/.summary`, а не распаковывает сырые tuples.
- helper payloads вокруг closure-follow / frontier bootstrap / quilt finalize / patch-gap
  diagnostics тоже переведены на explicit records, так что эти runtime paths больше не
  живут на ad-hoc return pairs.
- internal math/summary helpers в `solve.py` тоже частично типизированы:
  component builder, UV axis split/metrics, frame-group display coords, role counts
  и bbox payloads теперь идут через именованные records / aliases, а не через
  неявные tuple contracts.

### Exit Criteria

- После любой refactor phase можно быстро понять, что сломалось.
- Есть хотя бы один serializable snapshot baseline, а не только ручной просмотр консоли.
- Для базового набора regression meshes snapshot реально сохранён и пригоден для сравнения.
- Проверка выполняется руками, без сложной тестовой инфраструктуры.

### Important

Не пытаться сначала построить полноценный unit-test framework для Blender.
Сейчас gold logs, scaffold snapshots и manual verification полезнее.

---

## Phase 1A. Typed Raw Analysis Payload

### Goal

Формализовать промежуточный payload в `analysis.py`, прежде чем чинить topology drift.

### Tasks

1. Внутри `analysis.py` ввести private dataclasses для raw payload:
   - raw loop;
   - raw chain.

2. Не переносить это в `model.py`, если нет отдельного решения.

3. Минимизировать string-key contracts внутри analysis pipeline.

4. Явно зафиксировать, какие поля обязательны после каждого шага:
   - split by neighbor;
   - bevel merge;
   - geometric split;
   - border corner split.

### Exit Criteria

- Код `analysis.py` проще читать.
- Меньше неявных полей и `dict`-протоколов.
- Следующая фаза может чинить corner/split/merge logic не вслепую.
- Есть явный patch assembly state вместо ручной сборки `PatchNode` и raw payload вразнобой.

---

## Phase 1B. Topology Consistency In Analysis

### Goal

Убрать скрытый drift между финальными chains и corner topology.

### Tasks

1. Проследить весь pipeline `_build_boundary_loops()`.
2. Определить, где raw metadata ещё используется после chain merge.
3. Перестроить corner generation так, чтобы оно зависело от финального chain representation.
4. Проверить:
   - `start_corner_index`;
   - `end_corner_index`;
   - wrap-around merge;
   - corner turn angles;
   - corner vertex identity.
5. Явно проверить и задокументировать текущую асимметрию между:
   - `_collect_geometric_split_indices()`;
   - `_find_open_chain_corners()`.
   Нужно отделить intentional differences от случайного semantic drift.

### Recommended Rule

После того как loop перешёл в финальный `BoundaryLoop.chains`,
вся endpoint/corner topology должна вычисляться только из этого финального представления.

### Exit Criteria

- chain count, corner count, endpoint links и debug overlay согласованы;
- bevel-heavy meshes не дают странных corner jumps;
- no new regressions в Phase 0 harness.
- legacy corner helpers сведены к thin compatibility wrappers над unified detectors.
- post-split cleanup больше не нарушает primary neighbor contract.

---

## Phase 1C. Analysis Purity And UV-Dependent Classification Boundary

### Goal

Сделать UV-dependent шаг в analysis явным, изолированным и безопасным для debug/runtime paths.

Важно:
эта фаза про isolation boundary, а не про замену самого алгоритма `OUTER/HOLE` classification.

### Tasks

1. Выделить `_classify_loops_outer_hole()` в один явный boundary step с минимальным числом call sites.
   Остальной analysis pipeline должен получать уже готовый loop-kind result и не зависеть от UV mutation mechanics.
2. Явно задокументировать, что это единственный допустимый side-effect inside analysis.
3. Проверить и упростить rollback contract:
   - temporary UV layer;
   - active UV layer;
   - selection state.
4. Убедиться, что scope этой фазы не расползается в redesign loop classification algorithm.

### Optional Follow-Up Research

После завершения isolation phase можно отдельно исследовать,
нужна ли полная замена UV-unwrap classification на другой метод.
Это не должно блокировать закрытие Phase 1C.

### Exit Criteria

- Side effects analysis локализованы и явно описаны.
- Debug path не получает неожиданных persistent изменений состояния меша при обычном выполнении.
- Есть один понятный boundary, через который проходит UV-dependent classification.
- Дальнейшие refactor phases не распространяют UV side effects на новые части analysis.
- Raw patch boundary topology валидируется сразу после этого boundary.

---

## Phase 2. Central Solve Policy Layer

### Goal

Убрать архитектурно опасное дублирование solve rules.

### Problem

Сейчас правила solve разбросаны по planning, frontier scoring, anchor search,
seed selection, report formatting и conformal fallback.

### Architectural Decision Required Before Implementation

До начала этой фазы нужно явно решить, как делится solve policy:

1. `Stateless` часть:
   правила, которые зависят только от `PatchGraph`, `SolvePlan`, quilt membership и config.

2. `Stateful` часть:
   правила, которые зависят от текущего frontier progress:
   placed chains, available anchors, closure guards, build order.

Текущий код смешивает эти категории.

Рекомендуемое направление:

- сделать явный stateless solve-time view для topology/visibility/filtering;
- не притворяться, что anchor/seed/closure rules тоже stateless;
- stateful runtime rules оставить в явном frontier/runtime policy layer.

Иными словами:
не пытаться запихнуть весь solve behavior в один "как бы stateless" объект.

### Required Result

Появляется solve-time policy/view слой, например:

- `SolveView`;
- или `SolvePolicy`;
- или связка `SolveView` + `FrontierRuntimePolicy`.

Название не критично.
Критично, чтобы правила solve-допуска больше не были набором независимых `if` по коду.

### This Layer Must Answer

#### Stateless questions

1. Какие loops solve-visible?
2. Какие chains solve-visible?
3. Какие patch types совместимы для solve?
4. Разрешён ли cross-patch relation для пары patches?
5. Является ли seam tree-edge quilt или cut-edge?

#### Stateful questions

1. Есть ли у chain допустимые anchors в текущем frontier state?
2. Может ли chain быть seed в текущем quilt state?
3. Разрешено ли placement/closure с текущим набором placed chains?

### Tasks

1. Собрать текущие правила из `solve.py` и разделить их на stateless и stateful.
2. Перенести stateless фильтрацию в один явный слой.
3. Явно описать, какие runtime checks остаются stateful.
4. Переподключить:
   - attachment candidate generation;
   - seed selection;
   - anchor search;
   - chain scoring;
   - frontier pool assembly.

### Exit Criteria

- solve rules больше не размазаны по случайным локальным `if`;
- добавление нового solve rule не требует правок в 5+ местах;
- distinction between stateless visibility and stateful runtime gating явно выражен в коде;
- `HOLE` case и ring case продолжают работать.

---

## Phase 3. Frontier Runtime State

### Goal

Упростить и стабилизировать runtime state frontier builder.

### Problem

Сейчас frontier loop управляет несколькими взаимозависимыми registry вручную.

### Required Result

Сделать один explicit runtime container, например `FrontierState`.

### Suggested Responsibilities

- register placed chain;
- resolve anchor candidates;
- maintain point/vertex lookup;
- count placed chains per patch;
- expose dependency patches;
- expose placed refs and build order.

### Tasks

1. Создать dataclass внутри `solve.py`.
2. Перенести туда текущие registry.
3. Убрать ручную синхронизацию в главной frontier loop.
4. Сократить повторяющиеся вычисления внутри hot path.

### Exit Criteria

- `build_quilt_scaffold_chain_frontier()` заметно проще читать;
- special cases меняются в одном месте;
- runtime behavior совпадает с предыдущим;
- Phase 2 policy split при этом не размывается обратно.

---

### Current Status

Практически закрыто.

В `solve.py` runtime state frontier builder уже упакован в `FrontierRuntimePolicy`:

- placed/rejected/build_order/dependency/point registries имеют одного owner'а;
- `placed_in_patch` и `closure_pair_refs` кэшируются в runtime container;
- stop diagnostics, strongest-candidate selection, placement path, seed bootstrap и quilt finalization вынесены в explicit helper/dataclass layer;
- `build_quilt_scaffold_chain_frontier()` теперь остаётся orchestration function, а не местом с ручной синхронизацией registry.

Дальше Phase 3 не нужно открывать заново без конкретной runtime-regression.
Приоритет после этого: runtime bugfix track или Phase 4 IR cleanup.

## Phase 4. IR Cleanup

### Goal

Сделать runtime contracts честными.

### Problem

IR сейчас содержит смесь:

- реально используемых полей;
- transitional fields;
- sleeping fields;
- loosely typed fields.

### Tasks

1. Проверить каждое поле `ScaffoldPatchPlacement`.
2. Разделить их на группы:
   - active runtime fields;
   - planned-but-not-active fields;
   - dead fields.

3. Для active fields:
   - обеспечить полное заполнение.

4. Для planned/dead:
   - удалить из runtime IR;
   - или явно пометить как future-only.

5. По возможности заменить строковые статусы и source kinds на enum-like модели.

6. Явно задокументировать место sentinel semantics и при возможности сузить их зону.

### Current Progress

- Первый safe slice уже сделан: `root_chain_index` больше не является спящим
  полем по умолчанию.
- Для реально placed patch он теперь заполняется в envelope builder.
- Для `EMPTY/UNSUPPORTED` runtime paths он использует явный sentinel `-1`.
- `ScaffoldPatchPlacement.status` уже переведён из строки в enum-like runtime model.
- `source_kind` в scaffold / anchor runtime path тоже переведён в enum-like model.
- `max_chain_gap` и `gap_reports` уже переведены в честные derived diagnostics.
- patch-level `pinned` и `origin_offset` уже удалены как unused runtime fields.
- `start_anchor_kind / end_anchor_kind` уже удалены как write-only runtime fields.
- transfer/apply preview contract в `solve.py` уже переведён с raw dict на typed
  internal states (`PatchTransferTargetsState`, `PatchApplyStats`).
- `ScaffoldClosureSeamReport.anchor_mode` и `ScaffoldFrameAlignmentReport.axis_kind`
  уже переведены из raw strings в enum-like report fields.
- канонический `ChainRef` теперь выделен как именованный type alias и используется
  в persistent/report/runtime type contracts вместо анонимного `tuple[int, int, int]`.
- `QuiltPlan.stop_reason` уже переведён в enum-like planning/report contract
  с сохранением прежнего текстового snapshot output.
- внутренние registry contracts вокруг `point_registry` и `vert_to_placements`
  уже переведены на именованные aliases (`PointRegistryKey`, `PointRegistry`,
  `VertexPlacementRef`, `VertexPlacementMap`) без изменения storage semantics.
- frontier chain pool, closure matched pairs и frame-group members в `solve.py`
  уже упакованы в typed records вместо анонимных tuple-коллекций.

### Exit Criteria

- IR содержит только то, что runtime реально гарантирует;
- reports не читают фиктивные или неинициализированные данные;
- новый агент не ошибается в ожиданиях от solve IR.

---

## What Not To Do

### 1. Не делать большой split `solve.py` только ради длины файла

Если policy и state останутся неявными, дробление файла ничего не даст.

### 2. Не делать крупную миграцию ownership между `model.py` и `solve.py` в рамках локального багфикса

Сейчас persistent topology/solve IR уже живёт в `model.py`,
а planning/runtime helpers остаются в `solve.py`.
Не надо смешивать локальный bugfix с новой массовой перекладкой структур между модулями.

### 3. Не строить новый graph layer без необходимости

Если `SolveView` покрывает solve policy, отдельный runtime graph может быть лишним.

### 4. Не пытаться насильно объявить stateful frontier rules "stateless policy"

Это просто снова спрячeт архитектурный долг под новую абстракцию.

### 5. Не трогать scoring weights одновременно с structural refactor

Сначала стабилизировать architecture.
Потом уже настраивать scoring.

### 6. Не ломать debug path

Если debug visualization перестала объяснять scaffold state,
рефакторинг считается неудачным.

---

## Recommended Execution Style For Agents

Для любой фазы:

1. Сначала прочитать `docs/cftuv_architecture_v2.0.md`.
2. Затем прочитать `docs/cftuv_entity_model_and_control_plan.md`.
3. Затем прочитать этот roadmap.
4. Выбрать только одну фазу.
5. Не смешивать structural cleanup и scoring tuning в одном change set.
6. Перед правками определить:
   - какие meshes проверяются;
   - какие логи считаются ожидаемыми;
   - какие invariants нельзя нарушать.

После правок агент обязан сообщить:

- какую фазу он выполнял;
- какие функции трогал;
- какие regression cases проверил;
- какие риски остались.

---

## Immediate Recommendation

Если начинать следующую архитектурную работу прямо сейчас, порядок такой:

1. Phase 0
2. Phase 1A
3. Phase 1B
4. Phase 1C
5. Phase 2

Только после этого:

6. Phase 3
7. Phase 4

Причина:

- Phase 0 даёт baseline и сравнимый scaffold snapshot;
- Phase 1A убирает blind editing в analysis pipeline;
- Phase 1B закрывает topology inconsistency;
- Phase 1C локализует side effects analysis;
- Phase 2 убирает главный источник solve drift;
- Phase 3 становится намного проще после Phase 2;
- Phase 4 уже не исправляет корневые баги, а улучшает maintainability.

---

## Short Summary

Главная архитектурная проблема CFTUV сейчас не в том, что "мало абстракций".

Главная проблема в другом:

- solve policy не материализована в один слой;
- analysis pipeline до сих пор partly untyped;
- topology representation местами может расходиться после merge;
- analysis содержит локальный UV side-effect step;
- scaffold трудно сравнивать между ревизиями;
- frontier runtime state раздроблен;
- runtime IR частично честный, частично transitional.

Поэтому правильный путь не "сделать больше классов",
а последовательно:

1. зафиксировать regression harness и snapshot baseline;
2. формализовать raw analysis payload;
3. стабилизировать topology consistency;
4. локализовать analysis side effects;
5. централизовать solve policy;
6. потом чистить state и типы.

---
