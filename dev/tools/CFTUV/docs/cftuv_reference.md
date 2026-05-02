# CFTUV Reference
## Invariants, heuristics, and regression checklist

Do NOT read this document end-to-end. Look up specific sections when needed.

---

## Section 1. Topology Invariants

### Mesh → Patches

| # | Rule | Status |
|---|------|--------|
| P1 | Each face belongs to exactly one patch | ✅ |
| P2 | Patches do not overlap | ✅ |
| P3 | Union of all patches covers entire mesh | ✅ |
| P4 | Patch is a connected face subgraph (no seam crossings) | ✅ |
| P5 | PatchType determined only by normal angle to WORLD_UP | ✅ |

### Patch → Boundary Loops

| # | Rule | Status |
|---|------|--------|
| L1 | Each patch has exactly 1 OUTER loop | ✅ |
| L2 | Each patch has 0+ HOLE loops | ✅ |
| L3 | OUTER loop describes external contour | ✅ |
| L4 | HOLE loop describes internal opening | ✅ |
| L5 | Loops of one patch do not intersect (shared verts only at mesh boundary) | ✅ |
| L6 | All boundary edges belong to exactly one loop | ✅ |
| L7 | Loop is always closed | ✅ |

OUTER vs HOLE classification uses nesting depth via temporary UV unwrap
for multi-loop patches. Single-loop = trivially OUTER.

### Loop → Chains

Chain detection has two layers:

**Layer A: Primary split by neighbor (mandatory).** Continuous edges with same
neighbor = one chain. Neighbor change = split point.

**Layer B: Secondary split by geometric corner (conditional).**
- Case A: Isolated closed OUTER loop with one neighbor → geometric split at ≥4
  corners by turn angle ≥30°.
- Case B: Open MESH_BORDER chain through geometric angle → split into sub-chains
  for proper FrameRole classification.

**Post-split refinement:**
1. Bevel merge (adjacent chains split by bevel wrap)
2. Same-role point-contact downgrade (weaker → FREE)
3. Same-role border merge (adjacent MESH_BORDER with same role)

| # | Rule | Status |
|---|------|--------|
| C1 | Chains completely cover loop (all boundary edges) | ✅ |
| C2 | Chains do not overlap (shared only endpoint vertices) | ✅ |
| C3 | Chain order consistent with geometric traversal | ✅ |
| C4 | Each chain has ≥2 vertices (minimum = one edge) | ✅ |
| C5 | `chain[i].end_vert == chain[(i+1)%N].start_vert` | ⚠️ Target |
| C6 | ChainNeighborKind unambiguously determined by primary split | ✅ |
| C7 | FrameRole determined after all split/merge | ✅ |
| C8 | Geometric split not applied to HOLE loops | ✅ |
| C9 | Geometric split Case A requires ≥4 corners | ✅ |

### Chains → Corners

Two paths:

**Path A: Junction corners (≥2 chains).** `corner[i]` between `chain[i-1]` and
`chain[i]`. vert_index = shared endpoint vertex.

**Path B: Geometric corners (1 chain fallback).** Turn points inside single
chain. `prev_chain_index = 0, next_chain_index = 0`. Marker, not junction.

| # | Rule | Status |
|---|------|--------|
| R1 | Loop with ≥2 chains: corner_count == chain_count | ✅ |
| R2 | Loop with 1 chain: corners = geometric turn points (0+) | ✅ |
| R3 | corner.vert_co = 3D vertex position | ✅ |
| R4 | corner.vert_index = mesh vertex index | ✅ |
| R5 | turn_angle_deg in patch-local 2D basis | ✅ |
| R6 | prev_role / next_role from neighboring chains | ✅ |
| R7 | corner.vert_index == chain[prev].end == chain[next].start | ⚠️ Target |
| R8 | `wedge_normal` is analysis-owned local corner orientation input; primary build path uses explicit owner-patch face sector between `prev_chain -> next_chain` | ✅ |

### FrameRole Classification

| # | Rule | Status |
|---|------|--------|
| F1 | FrameRole determined after all split/merge/downgrade | ✅ |
| F2 | Native role (H/V/FREE) depends only on chain.vert_cos and patch basis | ✅ |
| F3 | Same geometry + same basis = same role (deterministic) | ✅ |
| F4 | FREE = default for chains passing neither H nor V threshold | ✅ |
| F5 | STRAIGHTEN assigned to FREE SIDE chains of BAND patches by structural tokens | ✅ |
| F6 | STRAIGHTEN resolves to H/V at placement time via geometry (dominant axis) | ✅ |
| F7 | H/V chains can never be SIDE in a BAND — SIDE must be FREE→STRAIGHTEN | ✅ |

### Shape Classification (PatchShapeClass)

| # | Rule | Status |
|---|------|--------|
| S1 | BAND requires exactly 4 boundary chains | ✅ |
| S2 | BAND requires exactly 2 SIDE + 2 CAP chains | ✅ |
| S3 | SIDE = the non-adjacent pair where BOTH chains are FREE | ✅ |
| S4 | If both pairs are FREE-FREE, higher internal-similarity pair = CAP | ✅ |
| S5 | CAP length similarity must be >= threshold (bands don't diverge) | ✅ |
| S6 | BAND SIDE interpretation promotes FREE chains to STRAIGHTEN in shape policy, not in ChainToken | ✅ |
| S7 | Classification is strict: under-classify (MIX) rather than false-positive BAND | ✅ |
| S8 | BAND runtime role assignment must preserve structural SIDE/CAP membership even when inherited H/V exists on one chain | ✅ |
| S9 | `BandSpineData` stores local UV targets for all 4 BAND outer chains: 2 SIDE + 2 CAP | ✅ |
| S10 | BAND spine chains pin as one connected scaffold group; CAPs must not fall back to FREE bridge pinning | ✅ |

### Cross-Layer Consistency

| # | Rule | Status |
|---|------|--------|
| X1 | Closed loop: endpoint stitching between adjacent chains | ⚠️ Target |
| X2 | Multi-chain loop: corner_count == chain_count | ✅ |
| X3 | corner[i].vert == chain[i-1].end | ⚠️ Target |
| X4 | corner[i].vert == chain[i].start | ⚠️ Target |
| X5 | Mutual patch neighbors → SeamEdge exists | ✅ |
| X6 | Seam shared verts = chain endpoint shared verts | ⚠️ Target |
| X7 | Sum of chain edges = loop edges | ⚠️ Target |
| X8 | Union of chain verts = loop verts | ⚠️ Target |

### Junction Invariants (future)

| # | Rule | Status |
|---|------|--------|
| J1 | One vertex = one junction (unique) | 🔮 Future |
| J2 | junction.valence == len(corners) | 🔮 Future |
| J3 | Junction aggregates corners, creates no new topology | 🔮 Future |
| J4 | Every corner with vert_index V exists in junction V | 🔮 Future |
| J5 | role_signature is deterministic | 🔮 Future |

### Known Risks

**Risk 1: Two corner detection paths with semantic gap.** Case A (closed loop,
≥4 corners, perimeter spacing) and Case B (open chain, ≥2 corners, local
support) can disagree on the same physical vertex.

**Risk 2: Endpoint identity not formally validated.** Fallback search by
vert_indices when direct match fails. Invariants C5, R7, X1, X3, X4 not
formally guaranteed.

**Risk 3: Geometric fallback corners semantically different.** Path B corners
(single-chain) have `prev_chain = next_chain = 0` and `role = FREE`. Not real
chain junctions. `corner_kind` field (`JUNCTION` vs `GEOMETRIC`) distinguishes
them.

---

## Section 2. Runtime Heuristics

### H/V Classification

Classifier is asymmetric:
- `H_FRAME`: plane-based relative to local N-U plane, threshold `0.02`
- `V_FRAME`: axis-based relative to local basis_v, threshold `0.04`
- Both thresholds live in `constants.py` as `FRAME_ALIGNMENT_THRESHOLD_H/V`
- Do NOT return to symmetric extent_u / extent_v test

### Same-Role Continuation Guards

- Adjacent same-role point-contact (shared_vert_count == 1): weaker chain → FREE
- Adjacent MESH_BORDER + MESH_BORDER same-role: merge first, don't break
- Stronger/weaker decided by dominant span and chain length, not tiny axiality

### FREE Handling

- One-edge FREE bridges scored below any H/V in frontier
- One-anchor FREE bridge waits for second anchor
- Local per-chain rectification for H/V already tested and disabled (regression)

### Rescue Path Order (when frontier stalls)

1. `tree_ingress` — one chain into untouched tree-child patch
2. `closure_follow` — same-role non-tree closure partner if pair already placed

This is reachability rescue, NOT a new solve mode.

### Frontier Rank (Phase 1)

- Main frontier winner is selected by structured rank, not by raw scalar-only comparison
- Current rank order is:
  `viable > role > ingress > patch_fit > anchor > closure_risk > local_score > tie_length`
- `local_score` remains as subordinate refinement and `FRONTIER_MINIMUM_SCORE` threshold gate
- Rescue paths remain separate from main rank during this phase
- Row / Column drift diagnostics stay outside the main frontier rank; the dedicated next-step plan is `docs/cftuv_alignment_drift_roadmap.md`
- Secondary closure seam with only cross-patch anchor must be rank-demoted during early patch ingress,
  otherwise it can outrun same-patch H/V carriers and collapse tube/ring cuts

### PatchScoringContext (Phase 2)

- Main frontier derives explicit patch runtime context before score/rank evaluation
- Current context includes placed role counts, `placed_ratio`, `hv_coverage_ratio`,
  `same_patch_backbone_strength`, `closure_pressure`, untouched-state, and secondary seam presence
- Incremental frontier cache must now dirty same-patch refs on every placement, not only on first ingress
- Telemetry detail should expose both rank and patch-context snapshot for the winning candidate

### CornerScoringHints (Phase 3)

- Corner facts are collected per chain candidate and remain local features only
- Current hints include start/end turn strength, orthogonal turn count, same-role continuation strength,
  and geometric-vs-junction markers
- These hints affect only subordinate local refinement and telemetry; they do not create a corner candidate type
- Chain remains the only runtime placement unit in main frontier selection

### PatchShapeProfile (Phase 4)

- Main frontier now derives a coarse `PatchShapeProfile` per patch and stores it inside `PatchScoringContext`
- Current profile is numeric-only: `elongation`, `rectilinearity`, `hole_ratio`,
  `frame_dominance`, `seam_multiplicity_hint`
- Shape affects only weak prior logic:
  early H/V ingress/backbone preference, closure sensitivity, and subordinate `local_score` refinement
- Structured-rank layer order stays the same:
  `viable > role > ingress > patch_fit > anchor > closure_risk > local_score > tie_length`
- Shape must not become a hard solve mode selector and must not override chain-first strongest-frontier

### SeamRelationProfile (Phase 5)

- Planning now derives explicit `SeamRelationProfile` per undirected patch edge and persists it into each quilt
- Current profile includes:
  `primary_pair`, `secondary_pairs`, `secondary_pair_count`, `pair_strength_gap`,
  `is_closure_like`, `support_asymmetry`, `ingress_preference`
- Frontier uses seam relation only as weak explicit context:
  primary ingress support, secondary seam demotion during early patch ingress,
  and telemetry/debug explanation
- Closure rescue / follow logic remains separate; seam relation does not replace rescue control flow in this phase

### Layered Frontier Score (Phase 6)

- Frontier scalar scoring is now split into explicit helper layers instead of one monolithic body
- Current runtime layering is:
  raw topology facts → patch/anchor context → closure guard →
  local seam hints / shape hints / corner hints → structured rank breakdown
- `_cf_score_candidate()` is now a thin orchestrator over those helpers
- Telemetry fields remain the same, but their source is now inspectable layer by layer

### Rescue-Gap Telemetry (Phase 7)

- Rescue control flow is still separate: `tree_ingress` and `closure_follow` are not absorbed into main frontier in this phase
- Successful rescue placements now store a `FrontierRescueGap` snapshot with:
  `candidate_class`, `main_known`, `main_score`, `threshold_gap`, `main_viable`,
  plus rescue-local support numbers (`hv_adjacency`, `downstream_support`, `shared_vert_count`)
- Quilt telemetry summary now reports rescue-gap aggregates:
  measured rescue count, `below_threshold`, `main_viable`, `no_anchor`, mean/max threshold gap,
  and top undervalued rescue classes
- Post-hoc placement detail now prints rescue-gap info per rescue step so it is visible
  whether the missing part was anchor reachability, threshold deficit, or frontier control flow

### Closure / Pre-Constraint Rules

- Closure-aware tree-edge swap has safe fallback to original quilt plan
- Closure pre-constraint only for closure-sensitive one-anchor H/V placement
- Same-patch H/V dual-anchor closure may override pair-safety rejection for both
  `span_mismatch` and `axis_mismatch`; this is a closure-only fallback for
  interpolation inside one already-placed patch, not permission for patch wrap
- `cross_patch + cross_patch` dual-anchor closure remains forbidden for H/V chains
  (except the existing short FREE bridge carve-out)
- Runtime must not reclassify chain roles on the fly

### Direction Inheritance Rules

- Same-role inheritance remains the first direction override path
- Orthogonal corner turn-sign inheritance is allowed for any target
  `MESH_BORDER` H/V chain and for legacy `corner_split` chains
- The source chain may be `PATCH`, `SEAM_SELF`, or `MESH_BORDER`; turn geometry
  comes from 3D tangent + normal and does not depend on source `neighbor_kind`
- `BoundaryCorner.wedge_normal` is analysis-owned runtime input and should come
  from the local owner-patch wedge sector; solve-time turn sign must not be
  reconstructed from patch basis, patch-average normal, or fan triangulation
- Current construction path for `wedge_normal` is:
  explicit owner-side half-edge resolve at the corner → sector walk over
  owner-patch faces around the corner vertex → area * corner-angle weighted
  normal. Endpoint-owner-face / owner one-ring are fallback paths only.
- This rule exists because wrapped border chains can have a misleading endpoint
  chord, causing `_cf_determine_direction()` to mirror a wall arm or notch leg
- If a closing H/V chain shows a large cross-axis delta, inspect upstream
  border-direction inheritance first; the closure chain itself may be correct and
  only interpolating divergent anchors

### Phase 1 Pin Cleanup

- `Solve Phase 1 Preview` clears final UV pins by default.
- Add-on Preferences may disable that cleanup to inspect pinned scaffold state.
- `Transfer Only` keeps pins.

### Scoring Weights (constants.py)

Root patch certainty (sum = 1.0 + semantic bonus):
- `ROOT_WEIGHT_AREA` = 0.30
- `ROOT_WEIGHT_FRAME` = 0.30
- `ROOT_WEIGHT_FREE_RATIO` = 0.20
- `ROOT_WEIGHT_HOLES` = 0.10
- `ROOT_WEIGHT_BASE` = 0.10

Attachment candidate (sum = 1.0 minus penalties):
- `ATTACH_WEIGHT_SEAM` = 0.25
- `ATTACH_WEIGHT_PAIR` = 0.40
- `ATTACH_WEIGHT_TARGET` = 0.20
- `ATTACH_WEIGHT_OWNER` = 0.15

Chain pair strength:
- `PAIR_WEIGHT_FRAME_CONT` = 0.40
- `PAIR_WEIGHT_ENDPOINT` = 0.25
- `PAIR_WEIGHT_CORNER` = 0.10
- `PAIR_WEIGHT_SEMANTIC` = 0.10
- `PAIR_WEIGHT_EP_STRENGTH` = 0.10
- `PAIR_WEIGHT_LOOP` = 0.05

Frontier thresholds:
- `FRONTIER_PROPAGATE_THRESHOLD` = 0.45
- `FRONTIER_WEAK_THRESHOLD` = 0.25
- `FRONTIER_MINIMUM_SCORE` = 0.30

### Continuous Scoring Factors (P5)

- `SCORE_FREE_LENGTH_SCALE` = 0.1
- `SCORE_FREE_LENGTH_CAP` = 0.15
- `SCORE_DOWNSTREAM_SCALE` = 0.05
- `SCORE_DOWNSTREAM_CAP` = 0.20
- `SCORE_ISOLATED_HV_PENALTY` = 0.40
- `SCORE_FREE_STRIP_CONNECTOR` = 0.10
- `SCORE_FREE_FRAME_NEIGHBOR` = 0.05

### Debug Source-of-Truth

- `Loops_Chains` and `Frontier_Path` must always build from same current PatchGraph
- Stale Analyze + new Frontier Replay = invalid debug state
- If timeline diverges from LoopTypes, check stale debug layers first
- Analyze `Patches_WALL/FLOOR/SLOPE` data must be generated regardless of current
  patch visibility toggles; UI toggles control only GP layer visibility. Empty
  patch layers caused by hidden scene props are a bug.
- GP compatibility is helper-owned in `debug.py`; operators/panels must not
  hardcode `GPENCIL` vs `GREASEPENCIL` object checks.
- Do not hardcode Blender-version-specific GP fields outside helpers:
  `layer.info/name`, `layer.clear()`, `stroke.line_width/use_cyclic`,
  `point.co/strength` vs `point.position/opacity/radius`.

### Snapshot / Telemetry Output Contract

- `Save Regression Snapshot` is anomaly-first by default
- Stable addresses in snapshot are expected: `ADDR Q#/P#`, `ADDR Q#/P#/L#/C#`, `ADDR Q#/S#`
- Healthy patches should collapse to one compact line; suspicious H/V chains may expand into compact directional lines
- Terminal exhausted stop should not appear as `stall_unresolved` anomaly
- In telemetry summary, terminal-only stop is expected as `stalls: terminal:N`
- `quilt_index` may be non-contiguous (`Q0`, `Q1`, `Q4`) and must be treated as stable id, not display ordinal

---

## Section 3. Regression Checklist

### Baseline Mesh Set

- [ ] Simple wall
- [ ] Wall with hole-attached patches
- [ ] Floor caps
- [ ] Closed ring house
- [ ] Mixed wall/floor
- [ ] Bevel-heavy wall
- [ ] Isolated curved wall strip
- [ ] Curved wall strip with neighbors
- [ ] Capless cylinder
- [ ] Cylinder with caps and opening

### Per-Mesh Verification

For each mesh, use `Save Regression Snapshot` and check:

- [ ] Patch count unchanged without expected reason
- [ ] Chain count unchanged without expected reason
- [ ] Corner count unchanged without expected reason
- [ ] Quilt count unchanged without expected reason
- [ ] PatchGraph Snapshot readable and compact
- [ ] Regression Snapshot is anomaly-first and compact by default
- [ ] Unsupported patch ids expected
- [ ] Invalid closure count expected
- [ ] Terminal-only stall does not appear in `Anomalies:`
- [ ] Terminal-only telemetry summary uses `stalls: terminal:N`
- [ ] Closure seam residuals not degraded
- [ ] Wrapped border arms / P-notch contours do not mirror because of missing
  border turn-sign inheritance
- [ ] Dual-anchor H/V closure does not end with large cross-axis delta from
  divergent same-patch anchor paths
- [ ] Row / column scatter not degraded
- [ ] Conformal fallback patch count expected
- [ ] H_FRAME / V_FRAME / FREE distribution looks expected
- [ ] Run / Junction summary in snapshot looks expected
- [ ] Build order shows no suspicious drift
- [ ] Pinned / unpinned summary expected
- [ ] Debug visualization matches snapshot

### Notes Template

```
Mesh:
Snapshot file:
Expected patch/quilt counts:
Expected chain/corner counts:
Expected unsupported patches:
Expected closure behavior:
Expected row/column behavior:
Expected conformal fallback:
Observed deviations:
Decision: OK / Investigate
```

---

## Section 4. Lattice Research Notes

This section is reference-only for future research. Not active in runtime.
Canonical implementation boundary for this topic now lives in `docs/cftuv_alignment_drift_roadmap.md`.

### Terminology

Use: `pre-frontier landmark alignment pass`, result: `aligned frame lattice`.
Do not use `aligned parallel corpus` as primary term.

### Canonical Metric

Do NOT use raw polyline length or endpoint-to-endpoint projection.
Use per-segment role-aligned accumulated span with local basis per patch/chain.

### Node Tiers

- `cross node`: has both H and V, from ≥2 patches
- `axis node`: one axis transferred through multiple patches
- `weak node`: single patch and/or FREE-dominated

### Integration Rule (if lattice enters placement path)

- Do not create fake scaffold placements
- Use separate provenance: `source_kind='lattice_anchor'`
- Do not write coarse lattice directly into runtime as placed chains

### Success Criterion

- H_FRAME chains within one solved row-class: same UV row-coordinate ±ε
- V_FRAME chains within one solved column-class: same UV column-coordinate ±ε
- FREE-dominated zones: outside this guarantee by design
