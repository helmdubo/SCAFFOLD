# CFTUV Architecture
## Current implementation state and design decisions

---

## Purpose

This is the detailed architecture document. Read `AGENTS.md` first.
Open this when your task requires understanding pipeline internals,
IR design, entity model, or current architectural debt.

---

## Module Responsibilities

| Module | Reads | Writes | Role |
|--------|-------|--------|------|
| `model.py` | — | — | Enums, topology IR, solve IR, UVSettings |
| `constants.py` | — | — | Thresholds, sentinels, scoring weights |
| `analysis.py` | BMesh | PatchGraph | Patch split, basis, loops, chains, corners, seams |
| `solve_records.py` | — | — | Pure data types: PinPolicy, FrontierRank, PatchPinMap, frontier records |
| `solve_planning.py` | PatchGraph | SolveView, SolvePlan | Quilt planning, attachment candidates |
| `solve_frontier.py` | PatchGraph, SolvePlan | ScaffoldMap | Chain-first frontier builder |
| `solve_pin_policy.py` | PatchGraph, ScaffoldPatchPlacement | PatchPinMap | Pin decisions — single source of truth |
| `solve_instrumentation.py` | solve_records | QuiltFrontierTelemetry | Frontier telemetry collector and formatting |
| `solve_transfer.py` | ScaffoldMap, BMesh | UV layer | Scaffold → UV, conformal fallback |
| `solve_diagnostics.py` | ScaffoldMap, BMesh UV | reports | Closure/alignment diagnostics |
| `solve_reporting.py` | ScaffoldMap, PatchPinMap | text | Snapshots, human-readable reports |
| `structural_tokens.py` | BoundaryLoop, PatchNode | ChainToken, LoopSignature | Generic structural fingerprint layer |
| `shape_types.py` | model enums | PatchShapeClass, LoopShapeInterpretation | Shape-policy type contracts |
| `shape_classify.py` | LoopSignature, shape types | PatchShapeClass, LoopShapeInterpretation | BAND/MIX classifier and FREE→STRAIGHTEN interpretation |
| `band_spine.py` | PatchGraph | BandSpineData | BAND section-based spine, per-chain local UV targets |
| `solve.py` | all above | — | Facade — orchestrates solve pipeline |
| `debug.py` | PatchGraph | Grease Pencil | Visualization + GPENCIL/GREASEPENCIL v3 compatibility helpers |
| `operators.py` | all | — | Blender UI, orchestration, preflight |

Legacy monolith `Hotspot_UV_v2_5_xx.py` is dead. Do not use.

---

## IR Layers

### 1. Topology IR: PatchGraph

Lives in `model.py`. Central inter-module contract.

Stores topology-only mesh representation:
- `PatchNode` — patch geometry, basis, classification
- `BoundaryLoop` — closed boundary contour (OUTER or HOLE)
- `BoundaryChain` — continuous boundary segment with one neighbor
- `BoundaryCorner` — junction between two chains
- `SeamEdge` — shared seam relation between patches

Key properties:
- Stores indices, not BMFace/BMEdge references
- Describes patch topology, not solve decisions
- Contains both OUTER and HOLE loops
- Stores seam adjacency at patch level

### 2. Persistent Solve IR: ScaffoldMap

Also lives in `model.py`. Working runtime IR:
- `ScaffoldPointKey` — unique source point reference
- `ScaffoldChainPlacement` — placed chain with UV coordinates
- `ScaffoldPatchPlacement` — per-patch envelope with status/diagnostics
- `ScaffoldQuiltPlacement` — per-quilt collection with build order
- `ScaffoldMap` — root container of all quilts

### 3. Transient Planning IR

Lives in `solve.py` (target: `solve_planning.py`):
- `PatchCertainty` — per-patch solvability + root score
- `AttachmentCandidate` — scored seam relation between two patches
- `SolverGraph` — all candidates + components
- `QuiltPlan` / `SolvePlan` — ordered solve plan

---

## Entity Model

### Primary Topology Entities

**Patch** and **Chain** — the two fundamental units.

Patch properties by layer:
- Intrinsic: `face_indices`, `normal`, `area`, `perimeter`, `basis`
- Contextual: `patch_type`, `world_facing`
- Derived: quilt membership, solve diagnostics

Chain properties by layer:
- Intrinsic: `vert_indices`, `vert_cos`, `edge_indices`, `is_closed`
- Contextual: `neighbor_kind`, `neighbor_patch_id`, `frame_role` (H/V/FREE native)
- Structural: generic loop fingerprints + shape-policy interpretation (`LoopShapeInterpretation`)
- Derived: scaffold placement, anchor provenance

### Composite Topology Entities

**BoundaryLoop** — ordered container over chains. Needed for boundary traversal
order, OUTER/HOLE classification, corner ordering.

**BoundaryCorner** — intra-patch junction record. Fixes vertex identity,
chain stitch point, turn angle. Not a solve unit.

### Analysis-Derived Views

**FrameRun** — local-derived continuity view over neighboring chains of one
loop. Diagnostic only. Does not change topology. Does not participate in
placement. Answers: "Do these adjacent chains behave as one logical side?"

**Junction** — global-derived view at mesh vertex, aggregating corners from
different patches. Diagnostic/research entity. Not in solve runtime yet.

**Structural Tokens** (`structural_tokens.py`) — thin structural views over
existing BoundaryChain/Corner data. Not a new canonical model.
- `ChainToken`: raw frame role, opposite_ref, border/neighbor context, length.
- `LoopSignature`: ordered generic loop fingerprint.

**Shape Policy** (`shape_types.py`, `shape_classify.py`, `analysis_shape_support.py`)
- `PatchShapeClass`: admission gate — MIX (default) or BAND.
- `LoopShapeInterpretation`: shape-policy interpretation over one generic signature.
- `analysis_shape_support.py` is the orchestration seam:
  fingerprint collection → loop interpretation → per-shape runtime support artifact.
- BAND = 4-chain loop where one non-adjacent pair is both-FREE (→ SIDE)
  and the other pair has similar lengths (→ CAP).
- BAND admission is shape-first, not neighbor-first:
  isolated/border 4-chain loops may still classify as BAND if the outer loop
  survives as four chains.
- `straighten_chain_refs`: set of ChainRef built from BAND SIDE interpretation,
  passed to frontier (gated by straighten toggle).
- `BandSpineData`: analysis-owned pre-parametrization for BAND patches.
  Stores oriented SIDE/CAP refs, section-based spine polyline, widths, and
  per-chain local UV targets used by frontier placement/pin logic.
- Runtime straighten authorities may be enabled directly by `band_spine_data`;
  do not require legacy `band_mode` summary if shape support already produced a valid BAND artifact.

### Chain Role Layers

Chain role is intentionally layered. Multiple role values may exist for the
same chain at different pipeline stages, but they must follow one strict
contract.

1. **Raw chain role**
- Source: `BoundaryChain.frame_role` in PatchGraph.
- Owner: early analysis / local chain classification.
- Meaning: local patch-basis fact only.
- Uses: structural fingerprints, `LoopSignature`, shape identity input.
- Must remain immutable after PatchGraph assembly.

2. **Effective structural role**
- Source: `analysis_derived.py` (`neighbor_inherited_roles`, run/junction interpretation).
- Owner: derived analysis layer.
- Meaning: raw role plus inherited seam / junction / paired-free-seam context.
- Uses: structural runtime summaries, Analyze/debug presentation, solve-facing
  analysis output.
- This is the canonical downstream non-local chain role.

3. **Runtime placement role**
- Source: `frontier_state.py`.
- Owner: frontier runtime policy.
- Meaning: effective structural role plus shape-owned runtime promotions such
  as BAND `STRAIGHTEN` and BAND CAP authority.
- Uses: viability, ranking, anchor logic, scaffold build, placement authority.

Role-layer rules:
- Shape identity (`PatchShapeClass`) must use raw structural fingerprints, not
  runtime placement role. Otherwise shape admission becomes cyclic.
- Frontier / scaffold map must use effective structural role or runtime
  placement role, never raw role alone.
- Reporting/debug should expose effective structural role as the primary role
  and preserve raw role as secondary context when they differ.
- Do not overwrite raw `frame_role` in PatchGraph to "bake in" inherited or
  runtime promotions.

### Solve Entities

**Quilt** and **ScaffoldMap** — solve layer. Scaffold is built only from chains.
FrameRun and Junction do not participate.

---

## Two Different Connectivities

This is critically important.

**Topology connectivity** — `PatchGraph.edges`, `PatchGraph.connected_components()`.
Answers: "Which patches are seam-connected at all?"

**Solve connectivity** — valid `AttachmentCandidate`, `SolverGraph.solve_components`,
tree edges from `QuiltPlan`.
Answers: "Which seam relations are allowed for solve propagation?"

These do NOT coincide:
- Patch may be topology-connected only through HOLE but solve-ineligible
- Patch may be in one topology component but non-tree seam remains UV cut
- Ring/cylinder topology does NOT mean quilt may close as UV cycle

---

## Pipeline

```
operators.py
  → validate_solver_input_mesh()
  → build_patch_graph()                    # analysis.py
  → build_solver_graph()                   # solve.py: scoring, components
  → plan_solve_phase1()                    # solve.py: quilt plans, closure cuts
  → build_straighten_structural_support()  # analysis.py: structural fingerprints + shape policy
  → build_root_scaffold_map()             # solve.py: chain frontier builder (STRAIGHTEN-aware)
  → transfer scaffold to UV               # solve.py: pin + write UV loops
  → bpy.ops.uv.unwrap(CONFORMAL)          # Blender: relax with pinned scaffold
```

### Analysis Pipeline (analysis.py)

1. Flood fill faces into patches by seam
2. Classify patch as WALL / FLOOR / SLOPE
3. Build local basis (basis_u, basis_v)
4. Build explicit patch assembly state
5. Trace raw boundary loops
6. Classify loops as OUTER / HOLE via temporary UV unwrap
7. Validate raw patch boundary topology
8. Split loop into raw chains by neighbor change
9. Geometric outer fallback split for isolated OUTER loops (≥4 corners)
10. Preserve geometric corner-split BORDER chains through final loop topology;
    do not atomize/merge them back into one border chain before shape support.
11. Build BoundaryChain objects
12. Downgrade weaker same-role point-contact chains to FREE
13. Merge adjacent same-role MESH_BORDER chains
14. Build corners and endpoint topology
15. Build seam edges between patches
16. Validate patch-neighbor chains against seam graph

Important: `_classify_loops_outer_hole()` is the only analysis step that
temporarily mutates UV state. This is intentional for wrapped/cylindrical
geometry and must remain isolated.

### Frontier Builder Rules

1. Pool contains only OUTER chains. HOLE loops excluded.
2. Seed chain chosen within root patch, quilt-context only.
3. Anchor provenance: `same_patch` (via corner) or `cross_patch` (via shared
   seam vertex on tree edge).
4. Dual-anchor closure via two cross_patch anchors forbidden (prevents patch wrap).
5. Same-patch H/V dual-anchor closure may override pair-safety rejection for
   both `span_mismatch` and `axis_mismatch`; this is a closure-only fallback and
   does not relax the cross-patch wrap guard above.
6. Orthogonal corner turn-sign inheritance may drive any target `MESH_BORDER`
   H/V chain from an already placed same-patch neighbor, regardless of whether
   the source chain is `PATCH`, `SEAM_SELF`, or `MESH_BORDER`.
   This prevents wrapped wall-border chains from falling back to misleading
   chord-based direction and mirroring a notch/arm across the patch.
7. Non-tree seams are intentional UV cuts, not re-sewn.
8. When frontier stalls, only narrow recovery in this order:
   - `tree_ingress`: one ingress chain into untouched tree-child patch
   - `closure_follow`: same-role non-tree closure partner if its pair already placed
9. Main frontier comparison is lexicographic structured rank:
   `viable > role > ingress > patch_fit > anchor > closure_risk > local_score > tie_length`.
   The old scalar score remains threshold gate and subordinate refinement.
10. Main frontier scoring derives explicit `PatchScoringContext` first
   (`placed_ratio`, `hv_coverage_ratio`, backbone/closure pressure, same-patch seam state,
   `PatchShapeProfile` snapshot),
   then feeds that context into rank + scalar refinement. Rescue flow is intentionally unchanged.
11. Corner-derived facts are collected as `CornerScoringHints` and affect only local
   refinement / telemetry. Corner does not become a frontier candidate type or solve step unit.
12. Patch shape acts only as a weak prior for ingress/backbone/closure sensitivity inside
    patch context + subordinate local refinement. It does not add a new solve mode or override
    the structured-rank ordering.
13. Planning now preserves explicit `SeamRelationProfile` per patch edge
    (primary pair, secondary seam pairs, closure-likeness, asymmetry, ingress preference).
    Frontier consumes this as weak seam context instead of reconstructing all seam semantics
    ad hoc from scalar attachment fields.
14. Frontier scalar scoring is now layered:
    raw topology facts → patch/anchor context → closure guard → local seam/shape/corner hints
    → structured rank/debug explanation. `_cf_score_candidate()` is a thin orchestrator over
    these helper layers, not a monolithic policy blob.
15. Rescue flow remains separate, but successful rescue placements now carry
    counterfactual main-frontier telemetry (`FrontierRescueGap`).
16. STRAIGHTEN chains (BAND SIDE) are handled natively by the frontier — no
    separate pre-pass or post-pass operator. Scoring uses STRAIGHTEN identity
    (tier 2); placement resolves to H/V via geometry. Authority resolution
    treats STRAIGHTEN as strong role (alongside H/V) via `_STRONG_ROLES` set.
17. `straighten_chain_refs` is toggle-gated: only passed to `FrontierRuntimePolicy`
    when straighten is enabled. When off, SIDE chains remain FREE.
18. If `BandSpineData` exists for a patch, runtime straighten is allowed even
    when old structural summary flags (`band_mode`, `band_requires_intervention`)
    are absent. Shape-owned runtime artifacts are authoritative for BAND support.

### UV Transfer and Pin Policy

1. Conformal all-FREE patch => pin nothing.
2. Connected H/V => pin all.
3. Isolated H/V => pin nothing.
4. FREE => only endpoints that touch connected local H/V.
5. Unsupported patches get individual fallback Conformal.
6. `Solve Phase 1 Preview` clears final pins by default; Add-on Preferences may keep them for debug inspection.
7. `execute_phase1_transfer_only()` keeps pins by design.

### Debug Compatibility

- `debug.py` owns Blender-version GP compatibility.
- Operators and panels must not hardcode GP object types or legacy-only layer/stroke fields.
- Supported runtime target: Blender 4.1 legacy GPENCIL and Blender 4.5.x GREASEPENCIL v3.

### Reporting / Telemetry Contract

Reporting is now policy-driven and must not be treated as raw runtime trace dump.

- Stable addresses are mandatory in reports: `ADDR Q#/P#`, `ADDR Q#/P#/L#/C#`, `ADDR Q#/S#`
- Default reports are anomaly-first and compact; healthy routine entities are compressed
- `summary` / `diagnostic` / `forensic` are presentation modes only, never solve modes
- Live telemetry trace is separate from post-hoc report detail
- Suspicious H/V chains must retain directional diagnostics: role, start/end UV, delta, axis error, inherited flag, anchor kinds, status code
- Large cross-axis delta on an H/V closure chain is usually an upstream anchor-lineage problem
  (often missing border turn-sign inheritance on a wrapped contour), not necessarily a bad
  closing-chain interpolation
- Stall lifecycle is explicit: `open` / `close`; terminal exhausted stop is not the same as actionable unresolved stall
- Successful rescue placements must preserve rescue-gap telemetry so we can see whether the missing piece was
  `no_anchor`, `below_threshold`, or already `main_viable` but blocked by control flow
- Regression snapshot uses telemetry summary, not step-by-step replay
- `quilt_index` is a stable quilt id from planning and may contain gaps after orphan-quilt merge; report formatter must preserve it verbatim

---

## Current Architectural Debt

### 1. solve.py is a 6500-line monolith

Contains planning, frontier, transfer, diagnostics, reporting, and ~60 dataclasses.
**P1 (decompose) is the blocking priority.** See `cftuv_solve_decomposition_plan.md`.

### 2. No trim sheet abstraction

CFTUV does constrained UV layout but doesn't know about trim atlas positions.
H_FRAME chain gets UV direction but not target atlas row.
**P4 addresses this with minimal data layer in model.py.**

### 3. Two rescue paths are a symptom

`tree_ingress`, `closure_follow` exist because main frontier
scoring doesn't cover all valid production cases.
**P3 collects instrumentation data; P5 revises scoring based on evidence.**

### 4. Pin policy — RESOLVED (P6)

`PatchPinMap` is now the single source of truth for pin decisions.
`solve_pin_policy.py` owns `build_patch_pin_map()` and `preview_chain_pin_decision()`.
`solve_transfer.py` reads the map; frontier can preview decisions before commit.
Circular dependency reduced: scoring can now query pin impact via `preview_chain_pin_decision`.

### 5. Temporary UV side-effect in analysis

`_classify_loops_outer_hole()` uses temporary UV unwrap for OUTER/HOLE
classification of multi-loop patches. Intentionally retained for
wrapped/cylindrical geometry. Must remain localized.

### 6. No closure/row-column correction pass

Tree-only quilt solve is correct but can accumulate:
- Span drift on non-tree closure seams
- Cross-axis scatter in geometrically collinear H/V chains

These are two related but distinct problems, both needing diagnostics-first
approach. Not solved by returning to UV cycle sewing.
Canonical next-step boundary now lives in `docs/cftuv_alignment_drift_roadmap.md`.

---

## Priorities (Agreed)

| # | Task | Status | Blocks |
|---|------|--------|--------|
| P1 | Decompose solve.py → sibling modules | ✓ Done | Everything |
| P2 | AGENTS.md self-contained rewrite | ✓ Done | Agent onboarding |
| P3 | Rescue/scoring instrumentation | ✓ Done | P5 |
| P4 | Minimal trim abstraction in model.py | Pending | Future solve direction |
| P5 | Scoring revision based on data | ✓ Done | — |
| P6 | Pin policy extraction | ✓ Done | — |
| P7 | Structural Token System (Phase 1) | ✓ Done | P8 |

P7 delivered: `structural_tokens.py` as generic fingerprint layer,
`shape_classify.py` for BAND/MIX policy + STRAIGHTEN interpretation,
frontier integration, and `band_spine.py` for BAND SIDE/CAP section-based placement.
Current BAND support also covers isolated closed border loops that survive geometric split.
Next shape work (`CABLE`, `CYLINDER`) should reuse:
- shape-first admission in `analysis_shape_support.py`
- analysis-owned runtime artifact generation
- section-based strip/tube parametrization
and must not depend on patch-neighbor presence to enter straighten runtime.
Future phases: junction enrichment (Phase 2), decal producer (Phase 3).
Alignment / drift follow-up is tracked separately in `docs/cftuv_alignment_drift_roadmap.md`.

---

## Entry Points For New Agents

1. Read `AGENTS.md` (mandatory)
2. Read this file (if task needs pipeline/IR understanding)
3. Look at code:
   - `analysis.py → build_patch_graph()`
   - `solve.py → build_solver_graph()`
   - `solve.py → plan_solve_phase1()`
   - `solve.py → build_root_scaffold_map()`
   - `solve.py → execute_phase1_preview()`
   - `operators.py → _prepare_patch_graph()`
4. If decomposition done, look at `solve_frontier.py` instead of `solve.py`
