# CFTUV Runtime Notes

Этот файл хранит текущие operational notes для active runtime track.
Он нужен, чтобы не засорять `cftuv_architecture_v2.0.md` и roadmap sprint-level
эвристиками, thresholds и production-case lessons.

Использование:

1. Сначала читать `docs/cftuv_architecture_v2.0.md`.
2. Затем `docs/cftuv_entity_model_and_control_plan.md`.
3. Затем `docs/cftuv_refactor_roadmap_for_agents.md`.
4. И только если задача касается runtime stabilization / lattice research,
   открывать этот файл.

Если заметка из этого файла противоречит архитектурному инварианту,
приоритет такой:

1. architecture doc
2. control plan
3. roadmap
4. runtime notes

---

## Control-model alignment

Этот файл не переопределяет entity model.
Для active runtime track считать обязательными такие границы:

- scaffold по-прежнему строится только из `chains`;
- `FrameRun` — local-derived analysis view, diagnostic-only;
- `Junction` — global-derived analysis / research view, пока не solve runtime;
- `Run` и `Junction` нельзя тихо превращать в новые placement units;
- runtime stabilization не должна маскироваться под redesign solve layer.

---

## Current runtime focus

Активная practical задача остаётся узкой:

- стабилизировать chain-first frontier на production meshes;
- не терять tree-connected patches из-за weak ingress;
- уменьшать closure / row-column drift без ухода в patch-first solve;
- не превращать lattice research в новый global solve layer.

---

## Active operational rules

### H/V classification

- classifier должен оставаться асимметричным:
  - `H_FRAME` = plane-based относительно локальной плоскости `N-U`;
  - `V_FRAME` = axis-based относительно локальной оси `basis_v`;
- текущие thresholds разделены:
  - `H_FRAME` uses `0.02`
  - `V_FRAME` uses `0.04`
- возвращаться к симметричному `extent_u / extent_v` test нельзя.

### Same-role continuation guards

- adjacent same-role point-contact (`shared_vert_count == 1`) не считается жёстким continuation;
- weaker chain в таком case должен деградировать в `FREE`;
- stronger/weaker heuristic должна смотреть на dominant span и chain length, а не на tiny sliver axiality;
- adjacent `MESH_BORDER + MESH_BORDER` same-role pieces не должны ломаться этим guard и должны сначала merge-иться в один border carrier-chain.

### FREE handling

- one-edge `FREE` bridges должны быть ниже любых `H/V` в frontier scoring;
- one-anchor `FREE` bridge должен ждать second anchor, если нет stall-recovery case;
- локальная per-chain rectification для `H/V` уже проверялась и отключена как structural regression.

### Closure / reachability rescue order

Когда обычный strongest-frontier stalled, допустим только такой recovery order:

1. `tree_ingress`
2. `free_ingress`
3. `closure_follow`

Это reachability rescue, а не новый solve mode.

### Closure-sensitive runtime rules

- closure-aware tree-edge swap допустим только с safe fallback на original quilt plan;
- точечный `closure pre-constraint` разрешён только для closure-sensitive `one-anchor` `H/V` placement;
- runtime не должен трактоваться как reclassifier chain roles на лету.

### Debug source-of-truth

- `Loops_Chains` и `Frontier_Path` должны всегда строиться из одного текущего `PatchGraph`;
- stale Analyze graph + новый frontier replay = invalid debug state;
- если timeline расходится с `LoopTypes`, сначала проверять stale debug layers и `build_order`, а не предполагать runtime reclassification.

### Analysis-cleanup boundary

- если runtime bug на самом деле рождается в `analysis.py`, нужно чинить split/merge/classification там;
- runtime notes не дают права лечить плохой split новыми широкими rescue-pass'ами;
- если для диагностики добавляются `FrameRun` / `Junction`, они должны оставаться report-only,
  пока не будет отдельного архитектурного решения об integration.

---

## Known production cases

### `walls.011`

- patch может быть topologically tree-connected сильными `WALL + V` seams;
- при этом ingress chain может не набирать обычный frontier score;
- следствие: patch ошибочно падает в `unsupported`;
- правильный ответ: `tree_ingress` rescue, а не patch-first fallback.

---

## Lattice research notes

### Canonical term

Использовать термин:

- `pre-frontier landmark alignment pass`
- результат: `aligned frame lattice`

Не использовать как основной термин `aligned parallel corpus`.

### Zero-risk branch

Diagnostics-only часть lattice track можно вести параллельно runtime fixes:

1. identify lattice nodes
2. build axis constraints
3. measure residuals

Пока эти шаги не меняют placement path, они считаются zero-risk.

### Node tiers

- `cross node`: есть и `H`, и `V`, минимум из двух patches
- `axis node`: перенос по одной оси через несколько patches
- `weak node`: один patch only и/или `FREE`-dominated topology

### Canonical metric

Нельзя использовать:

- raw polyline length
- endpoint-to-endpoint projection

Нужно использовать:

- per-segment role-aligned accumulated span
- с локальным basis каждого patch / chain
- как constraint per axis edge

Практический смысл:

- bevel noise не должен раздувать span
- L-shaped path не должен срезаться прямой между endpoints
- multi-patch path должен суммироваться в basis соответствующих patches

### Solve model

- coarse lattice solve = две независимые 1D axis задачи
- решение через constraint system / least-squares
- cycle residual использовать как diagnostics
- pairwise-all-path averaging не использовать как основную модель

### Integration rule

Если lattice потом попадёт в placement path:

- не создавать fake scaffold placements
- не писать coarse lattice прямо в runtime как будто это уже placed chains
- использовать compact transient lattice storage
- вводить отдельный provenance: `source_kind='lattice_anchor'`

Первая допустимая integration:

1. diagnostics + guide для ingress choice
2. closure-sensitive / dual-endpoint `H/V` placement
3. только потом более широкие placement assists

### Success criterion

- любые `H_FRAME` chains внутри одной solved row-class должны иметь одинаковую UV row-coordinate в пределах epsilon
- любые `V_FRAME` chains внутри одной solved column-class должны иметь одинаковую UV column-coordinate в пределах epsilon
- `FREE`-dominated зоны остаются вне этой гарантии by design
