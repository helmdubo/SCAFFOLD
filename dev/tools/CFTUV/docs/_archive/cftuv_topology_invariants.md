# CFTUV — Topology Invariants
## Formal rules for Patch / Loop / Chain / Corner / Junction

---

## Purpose

Этот документ фиксирует **математически честные** отношения между topology entities.
Каждое правило — invariant: его нарушение = баг.
Правила разделены на **гарантированные** (выполняются сейчас) и **целевые** (должны выполняться после cleanup).

---

## Layer 0. Mesh → Patches

### Definition

**Patch** — связный набор faces после flood fill, ограниченный seam edges и mesh boundary.

### Invariants

| # | Rule | Status |
|---|---|---|
| P1 | Каждый face принадлежит **ровно одному** patch | ✅ Guaranteed |
| P2 | Patches **не перекрываются**: `∀ i≠j: faces(Pᵢ) ∩ faces(Pⱼ) = ∅` | ✅ Guaranteed |
| P3 | Объединение всех patches покрывает весь mesh: `∪ faces(Pᵢ) = all_faces` | ✅ Guaranteed |
| P4 | Patch — связный подграф face adjacency (без пересечения seam edges) | ✅ Guaranteed |
| P5 | `PatchType` (`WALL`/`FLOOR`/`SLOPE`) определяется **только** углом нормали к `WORLD_UP` | ✅ Guaranteed |

---

## Layer 1. Patch → Boundary Loops

### Definition

**BoundaryLoop** — замкнутый контур boundary edges одного patch.
Boundary edge = edge, у которого одна сторона принадлежит patch, а другая — нет (другой patch, или край mesh).

### Invariants

| # | Rule | Status |
|---|---|---|
| L1 | Каждый patch имеет **ровно 1** `OUTER` loop | ✅ Guaranteed |
| L2 | Каждый patch имеет **0+** `HOLE` loops | ✅ Guaranteed |
| L3 | `OUTER` loop описывает **внешний контур** patch | ✅ Guaranteed |
| L4 | `HOLE` loop описывает **внутреннее отверстие** | ✅ Guaranteed |
| L5 | Loops одного patch **не пересекаются**: общие vertices допускаются только в mesh boundary вершинах | ✅ Guaranteed |
| L6 | Все boundary edges patch принадлежат **ровно одному** loop | ✅ Guaranteed |
| L7 | Loop всегда замкнут: `vert_indices[0]` топологически связан с `vert_indices[-1]` через последний edge | ✅ Guaranteed |

### Classification Rule

> [!UPDATE]
> The UV unwrap boundary remains intentionally preserved for multi-loop
> `OUTER` / `HOLE` classification. For wrapped or cylindrical patches,
> pure projection into patch-local basis is not a mathematically safe replacement.
> Planar nesting in patch-local basis may still be used as diagnostics-only
> shadow classification, but not as the authoritative production rule.

`OUTER` vs `HOLE` определяется через nesting depth:
- depth = количество других loops того же patch, внутрь которых попадает interior point данного loop
- `depth == 0` или `depth % 2 == 0` → `OUTER`
- `depth % 2 == 1` → `HOLE`

> [!NOTE]
> Для single-loop patches классификация тривиальна: единственный loop = `OUTER`.
> Для multi-loop patches используется UV-dependent classification (единственный допустимый UV side effect в analysis).

---

## Layer 2. Loop → Chains

### Definition

**BoundaryChain** — непрерывный участок boundary loop.

### Chain Detection — Two Layers

#### Layer 2A. Primary Split: By Neighbor (mandatory)

Каждый boundary edge имеет **одного соседа** на стороне, противоположной patch:
- face другого patch → `neighbor = other_patch_id`
- face того же patch (seam внутри) → `neighbor = SEAM_SELF` (-2)
- нет face → `neighbor = MESH_BORDER` (-1)

**Rule:** непрерывная последовательность boundary edges с **одинаковым** neighbor = один chain.
Точка, где neighbor **меняется** = split point → начало нового chain.

Это **единственный обязательный** механизм chain detection.

#### Layer 2B. Secondary Split: By Geometric Corner (conditional)

Возникает в двух случаях:

**Case A: Isolated closed OUTER loop** — `_collect_geometric_split_indices()`
Когда весь замкнутый `OUTER` loop имеет **одного соседа** (или `MESH_BORDER`), primary split даёт **один closed chain** → один `FREE` chain на весь контур patch. Это бесполезно для solve.

Geometric split ищет **≥ 4 corner** по turn angle ≥ `CORNER_ANGLE_THRESHOLD_DEG` (30°) и разбивает closed loop на open chains. Фильтры: bevel-заворот (vertex normal), cluster spacing, min 4% perimeter.

**Case B: Open MESH_BORDER chains** — `_find_open_chain_corners_filtered()`
Когда `MESH_BORDER` chain проходит через **геометрический угол** (например, угол стены), весь chain целиком классифицируется как `FREE`, хотя его части по отдельности являются `H_FRAME` или `V_FRAME`.

Geometric split ищет corners **внутри** существующего chain и разрезает его на sub-chains, каждый из которых может получить свою `FrameRole`.

#### Layer 2C. Post-Split Refinement

After both layers, chains проходят через:
1. **Bevel merge** — соседние chains, разделённые bevel-заворотом, мержатся обратно
2. **Same-role point-contact downgrade** — слабые adjacent same-role chains понижаются до `FREE`
3. **Same-role border merge** — соседние `MESH_BORDER` chains с одинаковой `FrameRole` мержатся

### Chain Invariants

| # | Rule | Status |
|---|---|---|
| C1 | Chains **полностью покрывают** loop: при обходе chains по порядку проходим все boundary edges loop | ✅ Guaranteed |
| C2 | Chains **не перекрываются**: общие только endpoint вершины | ✅ Guaranteed |
| C3 | Порядок chains в loop **согласован** с geometrical обходом | ✅ Guaranteed |
| C4 | Каждый chain имеет **≥ 2 вершины** (минимум = одно edge) | ✅ Guaranteed |
| C5 | `chain[i].end_vert == chain[(i+1) % N].start_vert` для замкнутого loop | ⚠️ Target |
| C6 | `ChainNeighborKind` = `PATCH` / `MESH_BORDER` / `SEAM_SELF` — однозначно определён по primary split | ✅ Guaranteed |
| C7 | `FrameRole` (`H_FRAME`/`V_FRAME`/`FREE`) определяется **после** всех split/merge | ✅ Guaranteed |
| C8 | Geometric split (Layer 2B) **не применяется** к `HOLE` loops | ✅ Guaranteed |
| C9 | Geometric split Case A требует **≥ 4 corners** для split (иначе loop остаётся single chain) | ✅ Guaranteed |

> [!IMPORTANT]
> **C5 — Target Invariant.** Сейчас endpoint stitching не проверяется формально.
> Chain endpoint identity гарантируется конструкцией (split by index), но нет explicit validation.
> Это критично для Junction layer.

---

## Layer 3. Chains → Corners

### Definition

**BoundaryCorner** — вершина на стыке двух соседних chains внутри одного loop.

### Corner Classification

Corners возникают **двумя путями**:

**Path A: Junction corners (≥ 2 chains)**
Когда loop содержит ≥ 2 chains, corner exists between each adjacent pair.
`corner[i]` стоит между `chain[i-1]` и `chain[i]`.
- `prev_chain_index = (i-1) % N`
- `next_chain_index = i`
- `vert_index` = shared endpoint vertex
- `turn_angle_deg` = поворот в patch-local 2D пространстве

**Path B: Geometric corners (single chain fallback)**
Когда loop содержит **1 chain**, corners определяются чисто геометрически по turn angle.
Это fallback — corner не разделяет два chain'а, а только помечает точку поворота.
- `prev_chain_index = 0`, `next_chain_index = 0` (оба указывают на единственный chain)
- `prev_role = FREE`, `next_role = FREE`

### Corner Invariants

| # | Rule | Status |
|---|---|---|
| R1 | В loop с **≥ 2 chains**: `corner_count == chain_count` | ✅ Guaranteed |
| R2 | В loop с **1 chain**: corners = geometric turn points (может быть 0+) | ✅ Guaranteed |
| R3 | `corner.vert_co` = 3D позиция вершины | ✅ Guaranteed |
| R4 | `corner.vert_index` = mesh vertex index этой вершины | ✅ Guaranteed |
| R5 | `turn_angle_deg` вычисляется через `_measure_corner_turn_angle()` в patch-local 2D basis | ✅ Guaranteed |
| R6 | `prev_role` и `next_role` берутся из `FrameRole` соседних chains | ✅ Guaranteed |
| R7 | В Path A: `corner.vert_index == chain[prev].vert_indices[-1] == chain[next].vert_indices[0]` | ⚠️ Target |

> [!WARNING]
> **R7 — Target Invariant.** Сейчас endpoint identity определяется конструкцией, но не проверяется.
> `_resolve_loop_corner_from_final_chains()` использует best-match fallback, когда direct match не найден.

---

## Layer 4. Corners → Junctions (future)

### Definition

**Junction** — глобальная точка, где сходятся corners из **разных patches/loops** в одной mesh vertex.

> [!NOTE]
> Junction пока не реализован как persistent entity. Определение фиксируется здесь для будущей реализации.

### Junction Properties

| Property | Source |
|---|---|
| `vert_index` | mesh vertex index (primary key) |
| `valence` | количество corners, сходящихся в этой вершине |
| `patch_ids` | множество patches, чьи corners здесь встречаются |
| `chain_endpoints` | множество (patch_id, loop_index, chain_index, "start"/"end") |
| `role_signature` | sorted tuple of `FrameRole` пар `(prev_role, next_role)` из каждого corner |

### Junction Invariants

| # | Rule | Status |
|---|---|---|
| J1 | `junction.vert_index` уникален: **один vertex = одна junction** | 🔮 Future |
| J2 | `junction.valence == len(junction.corners)` | 🔮 Future |
| J3 | Junction **не создаёт** new topology — только **агрегирует** corners | 🔮 Future |
| J4 | Если corner с `vert_index V` существует в patch P, junction `V` содержит этот corner | 🔮 Future |
| J5 | `role_signature` junction = **deterministic** (не зависит от порядка обхода patches) | 🔮 Future |

### Junction Prerequisite

> [!CAUTION]
> Junction детерминирован **только если corners детерминированы** (C5, R7).
> Пока endpoint identity не проверяется формально, Junction будет наследовать нестабильность corners.

---

## Layer 5. Chains → FrameRole Classification

### Definition

`FrameRole` — роль chain в локальном базисе patch: `H_FRAME`, `V_FRAME`, `FREE`.

### Classification Rules

Определяется по **геометрическому alignment** chain polyline к patch basis:

1. Measure per-segment deviation от H-plane и V-axis
2. `H_FRAME`: chain stays close to local N-U plane (`avg_deviation < threshold_h`)
3. `V_FRAME`: chain stays close to local V axis (`avg_deviation < threshold_v`)
4. Both pass → choose by lower deviation
5. Neither → `FREE`

### FrameRole Invariants

| # | Rule | Status |
|---|---|---|
| F1 | FrameRole определяется **после** всех split/merge/downgrade | ✅ Guaranteed |
| F2 | FrameRole зависит только от `chain.vert_cos` и `patch.basis_u`/`basis_v` | ✅ Guaranteed |
| F3 | Один и тот же chain geometry в одном и том же basis **всегда** даёт одну и ту же role | ✅ Guaranteed |
| F4 | `FREE` = default: chain, не прошедший ни H, ни V threshold | ✅ Guaranteed |
| F5 | Geometric corner split (Layer 2B Case B) **не меняет** classification, а **создаёт условия** для правильной classification, разрезая L-shaped chain на прямые segments | ✅ Design Intent |

---

## Cross-Layer Consistency Rules

### Endpoint Stitching

| # | Rule | Status |
|---|---|---|
| X1 | В closed loop: `chain[i].vert_indices[-1] == chain[(i+1)%N].vert_indices[0]` | ⚠️ Target |
| X2 | В closed loop: `len(corners) == len(chains)` для multi-chain loops | ✅ Guaranteed |
| X3 | `corner[i].vert_index == chain[i-1].vert_indices[-1]` | ⚠️ Target |
| X4 | `corner[i].vert_index == chain[i].vert_indices[0]` | ⚠️ Target |

### Neighbor Consistency

| # | Rule | Status |
|---|---|---|
| X5 | Если `chain_A.neighbor == patch_B` и `chain_B.neighbor == patch_A`, то `SeamEdge(A,B)` exists | ✅ Guaranteed |
| X6 | Seam edge shared vertices = chain endpoint shared vertices | ⚠️ Target |

### Loop ↔ Chain Coverage

| # | Rule | Status |
|---|---|---|
| X7 | Сумма `len(chain.edge_indices)` по всем chains loop = `len(loop.edge_indices)` | ⚠️ Target |
| X8 | Объединение `chain.vert_indices` (с учётом shared endpoints) = `loop.vert_indices` | ⚠️ Target |

---

## Known Violations and Risks

### Risk 1: Two Corner Detection Paths — Semantic Gap

**Paths:**
- Case A: `_collect_geometric_split_indices()` — closed OUTER loop, requires ≥ 4 corners, strict spacing
- Case B: `_find_open_chain_corners_filtered()` — open MESH_BORDER chain, requires ≥ 2 corners, local support validation

**Gap:** Same physical turn angle at same mesh vertex can be detected in Case A but not in Case B (or vice versa), because:
- Case A uses loop-wide perimeter-relative spacing filter
- Case B uses local polyline-relative support filter
- Case A requires ≥ 4, Case B requires ≥ 2
- Case B has additional side-support validation that Case A doesn't have

**Impact:** Junction на этой вершине будет нестабильной — corner presence зависит от context (neighbor type), а не от geometry alone.

### Risk 2: Endpoint Identity Not Validated

`_resolve_loop_corner_from_final_chains()` uses a fallback search по `vert_indices` when direct endpoint match fails. Это допустимый runtime fallback, но он скрывает случаи, когда chain endpoints **не стыкуются** с loop vertex order.

**Impact:** Invariants C5, R7, X1, X3, X4 не гарантируются формально.

### Risk 3: Geometric Fallback Corners Semantically Different

Path B corners (single-chain loops) имеют:
- `prev_chain_index = 0`, `next_chain_index = 0`
- `prev_role = FREE`, `next_role = FREE`

Это не "настоящие" chain junctions, а geometric markers. Код, обрабатывающий corners, должен различать эти два случая, но API `BoundaryCorner` **не различает** их.

---

## Validation Plan

Для перевода **⚠️ Target** invariants в **✅ Guaranteed** рекомендуется:

1. **Добавить assertion pass** после `_finalize_boundary_loop_build()`:
   - проверить endpoint stitching (C5, X1, X3, X4)
   - проверить coverage (X7, X8)
   - проверить corner count (X2)
   - log violations, не crash

2. **Добавить поле `corner_kind`** в `BoundaryCorner`:
   - `JUNCTION` — стык двух разных chains
   - `GEOMETRIC` — turn point inside single chain
   - Это устранит Risk 3

3. **Унифицировать turn angle computation** для обоих corner detection paths:
   - оба пути уже используют `_measure_corner_turn_angle()` ✅
   - но фильтры (spacing, support, bevel) отличаются → документировать **почему** и пометить intentional vs accidental differences

---
