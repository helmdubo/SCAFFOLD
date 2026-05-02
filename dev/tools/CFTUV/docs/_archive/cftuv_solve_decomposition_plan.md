# CFTUV solve.py Decomposition Plan
## P1: Mechanical split with zero behavior change

---

## Strategy

- Split into sibling modules `solve_*.py` (not a package) to preserve `from .solve import ...`
- `solve.py` becomes a thin facade: re-exports public API only
- No behavior change. No refactoring. No renaming. Just move.
- Each function/class goes to exactly one target module
- Internal cross-module imports use relative imports within `cftuv/`

---

## Target Modules

| Module | Responsibility | Estimated lines |
|--------|---------------|-----------------|
| `solve_records.py` | All dataclasses, enums, type aliases used across modules | ~800 |
| `solve_planning.py` | SolverGraph, SolvePlan, scoring, components, candidates, closure cuts | ~1200 |
| `solve_frontier.py` | FrontierRuntimePolicy, anchor/placement/seed/rescue, chain builder | ~1800 |
| `solve_transfer.py` | UV transfer, pin policy, conformal, scaffold→UV resolution | ~800 |
| `solve_diagnostics.py` | Closure seam reports, row/column alignment, gap diagnostics | ~600 |
| `solve_reporting.py` | format_*_report, print helpers | ~500 |
| `solve.py` | Facade: re-exports public functions | ~50 |

---

## Module 1: `solve_records.py`

All dataclasses, enums, and type aliases that are used by more than one target module.
Single-module-only records stay in their consuming module.

### Type Aliases (from model.py — already there, just re-imported)

These stay in `model.py` where they already live:
- `ChainRef`, `PatchEdgeKey`, `LoopChainRef`, `SourcePoint`, `AnchorAdjustment`

### Local Type Aliases (move here)

```
RowClassKey
ColumnClassKey
FrameClassKey
PointRegistryKey
VertexPlacementRef
PointRegistry
VertexPlacementMap
TransferTargetId
ScaffoldKeyId
TargetSampleMap
PinnedTargetIdSet
ScaffoldKeySet
AnchorRefPair
```

### Local Constants (move here)

```
EDGE_PROPAGATE_MIN
EDGE_WEAK_MIN
SCAFFOLD_CLOSURE_EPSILON
FRAME_ROW_GROUP_TOLERANCE
FRAME_COLUMN_GROUP_TOLERANCE
CHAIN_FRONTIER_THRESHOLD
```

### Shared Enums

```
QuiltStopReason
PatchTransferStatus
PatchPlacementStatus  # already in model.py, keep there
```

### Planning Records

```
PatchCertainty
SolveComponentsResult
AttachmentCandidate
SolverGraph
SolveView
QuiltStep
QuiltPlan
SolvePlan
AttachmentCandidatePreference
ChainPairSelection
AttachmentNeighborRef
ChainEndpointContext
EndpointMatch
EndpointBridgeMetrics
EndpointSupportStats
ClosureCutHeuristic
QuiltClosureCutAnalysis
```

### Frontier Records

```
ChainAnchor
ChainPoolEntry
FrontierCandidateEval
FrontierStopDiagnostics
FrontierPlacementCandidate
FrontierBootstrapResult
FrontierBootstrapAttempt
FinalizedQuiltScaffold
SeedChainChoice
SeedPlacementResult
ClosureFollowPlacementCandidate
FreeIngressPlacementCandidate
TreeIngressPlacementCandidate
ClosureFollowCandidateRank
FreeIngressCandidateRank
TreeIngressCandidateRank
DirectionOption
AnchorOption
ClosurePreconstraintOptionResult
ClosurePreconstraintMetric
ClosurePreconstraintApplication
DualAnchorRectificationPreview
ResolvedCandidateAnchors
FoundCandidateAnchors
AnchorPairSafetyDecision
DualAnchorClosureDecision
ClosureFollowUvBuildResult
```

> **NOTE:** `FrontierRuntimePolicy` is NOT a record. It is a mutable runtime
> owner class whose methods call frontier-layer functions (`_cf_find_anchors`,
> `_cf_resolve_candidate_anchors`, `_cf_apply_closure_preconstraint`,
> `_cf_score_candidate`, `_cf_register_points`). It lives in
> `solve_frontier.py`, not here.

### Diagnostics Records

```
UvAxisMetrics
FrameUvComponents
FrameGroupDisplayCoords
SharedClosureUvOffsets
ClosureChainPairMatch
ClosureChainPairCandidate
FrameGroupMember
PatchChainGapDiagnostics
```

### Transfer Records

```
ScaffoldUvTarget
PatchTransferTargetsState
PatchApplyStats
UvBounds
PatchRoleCounts
```

### Helper Function (stays with records since used everywhere)

```
_point_registry_key
_clamp01
_patch_pair_key
```

---

## Module 2: `solve_planning.py`

Everything that builds SolverGraph, SolvePlan, and closure cut analysis.
Entry points: `build_solver_graph()`, `plan_solve_phase1()`.

### Functions

```
# SolveView
_build_solve_view

# Scoring helpers
_count_patch_roles              # uses PatchRoleCounts from records
_frame_presence_strength
_semantic_stability_bonus
_build_patch_certainty

# Chain endpoint analysis
_chain_endpoint_strength
_get_chain_corner
_get_chain_endpoint_context
_corner_similarity_strength
_find_endpoint_matches
_endpoint_bridge_strength
_frame_continuation_strength
_semantic_pair_strength
_loop_pair_strength
_best_chain_pair

# Attachment candidate
_build_attachment_candidate
_iter_neighbor_chains           # compatibility shim, uses _build_solve_view

# Component analysis
_build_solve_components

# PUBLIC: SolverGraph builder
build_solver_graph

# Root selection
choose_best_root
_choose_root_loop

# Quilt tree helpers
_build_quilt_tree_edges
_build_patch_tree_adjacency
_find_patch_tree_path
_is_allowed_quilt_edge
_rebuild_quilt_steps_with_forbidden_edges

# Closure cut analysis
_attachment_candidate_preference_key
_select_preferred_edge_candidate
_count_chain_endpoint_support
_closure_cut_support_label
_build_closure_cut_heuristic
_build_quilt_edge_candidate_map
_analyze_quilt_closure_cuts
_apply_quilt_closure_cut_recommendations
_restore_original_quilt_plan

# PUBLIC: Plan builder
plan_solve_phase1
```

### Imports from records

```
from .solve_records import (
    PatchCertainty, SolveComponentsResult, AttachmentCandidate,
    SolverGraph, SolveView, QuiltStep, QuiltStopReason, QuiltPlan, SolvePlan,
    AttachmentCandidatePreference, ChainPairSelection, AttachmentNeighborRef,
    ChainEndpointContext, EndpointMatch, EndpointBridgeMetrics, EndpointSupportStats,
    ClosureCutHeuristic, QuiltClosureCutAnalysis, PatchRoleCounts,
    EDGE_PROPAGATE_MIN, EDGE_WEAK_MIN,
    _clamp01, _patch_pair_key,
)
```

---

## Module 3: `solve_frontier.py`

Chain-first strongest-frontier builder and all supporting machinery.
Entry points: `build_quilt_scaffold_chain_frontier()`, `build_root_scaffold_map()`.

### Runtime Owner Class

```
FrontierRuntimePolicy          # Mutable runtime owner. Methods call frontier functions directly.
                               # NOT a record — lives here because it IS the frontier.
```

### Functions — Geometry / Direction

```
_cf_chain_total_length
_snap_direction_to_role
_rotate_direction
_chain_edge_lengths
_default_role_direction
_normalize_direction
_segment_source_step_directions
_interpolate_between_anchors_by_lengths
_sample_cubic_bezier_point
_sample_cubic_bezier_polyline
_resample_polyline_by_edge_lengths
```

### Functions — Chain Placement Builders

```
_build_guided_free_chain_from_one_end
_build_guided_free_chain_between_anchors
_build_frame_chain_from_one_end
_build_frame_chain_between_anchors
_cf_rebuild_chain_points_for_endpoints
```

### Functions — Anchor Logic

```
_cf_find_anchors
_cf_frame_cross_axis_value
_cf_with_frame_cross_axis
_cf_preview_anchor_source_adjustment
_cf_same_patch_anchor_is_protected
_cf_preview_frame_dual_anchor_rectification
_cf_frame_anchor_pair_is_axis_safe
_cf_can_use_dual_anchor_closure
_cf_resolve_candidate_anchors
_cf_apply_anchor_adjustments
```

### Functions — Closure Preconstraint

```
_closure_preconstraint_direction_options
_closure_preconstraint_metric
_cf_apply_closure_preconstraint
_build_temporary_chain_placement
```

### Functions — Scoring / Direction Inheritance

```
_cf_score_candidate
_cf_determine_direction
_try_inherit_direction
_cf_place_chain
```

### Functions — Seed / Bootstrap

```
_cf_choose_seed_chain
_cf_build_seed_placement
_cf_bootstrap_frontier_runtime
_cf_build_frontier_chain_pool
_cf_chain_source_points
_cf_anchor_count
_cf_anchor_debug_label
```

### Functions — Frontier Loop / Candidate Selection

```
_cf_select_best_frontier_candidate
_cf_try_place_frontier_candidate
_cf_register_points
```

### Functions — Rescue Paths

```
_cf_try_place_closure_follow_candidate
_cf_build_closure_follow_uvs
_cf_try_place_free_ingress_bridge
_cf_try_place_tree_ingress_candidate
```

### Functions — Envelope / Finalization

```
_compute_scaffold_connected_chains
_compute_patch_chain_gap_reports
_cf_build_envelopes
_finalize_quilt_scaffold_frontier
```

### Functions — Closure Pair Matching (used by frontier)

```
_match_non_tree_closure_chain_pairs
_iter_quilt_closure_chain_pairs
_build_quilt_closure_pair_map
```

### PUBLIC Entry Points

```
build_quilt_scaffold_chain_frontier
build_root_scaffold_map
```

### Imports from other solve modules

```
from .solve_records import (...)       # all frontier records
from .solve_planning import (          # tree/quilt helpers needed by frontier
    _build_solve_view,
    _build_quilt_tree_edges,
    _build_patch_tree_adjacency,
    _find_patch_tree_path,
    _is_allowed_quilt_edge,
)
from .solve_diagnostics import (       # called at finalization
    _collect_quilt_closure_seam_reports,
    _collect_quilt_frame_alignment_reports,
    _print_quilt_closure_seam_reports,
    _print_quilt_frame_alignment_reports,
)
```

---

## Module 4: `solve_transfer.py`

UV transfer, pin policy, conformal unwrap, scaffold validation.
Entry points: `execute_phase1_preview()`, `validate_scaffold_uv_transfer()`.

### Functions — UV Helpers

```
_all_patch_ids
_collect_patch_face_indices
_select_patch_faces
_select_patch_uv_loops
_count_selected_patch_uv_loops
_compute_patch_uv_bbox
_translate_patch_uvs
_scale_patch_uvs
_restore_patch_uv_bounds
_clear_patch_pins
_pin_corner_vertices
_compute_quilt_bbox
_ordered_quilt_patch_ids
```

### Functions — Scaffold Resolution

```
_scaffold_key_id
_resolve_scaffold_uv_targets
_count_patch_scaffold_points
_patch_scaffold_is_supported
_format_scaffold_uv_points
```

### Functions — Pin Policy

```
_should_pin_scaffold_point
_free_endpoint_has_local_frame_anchor
```

### Functions — Transfer / Apply

```
_build_patch_transfer_targets
_apply_patch_scaffold_to_uv
```

### Functions — Validation

```
validate_scaffold_uv_transfer
```

### Functions — Phase1 Preview Orchestration

```
_collect_phase1_unsupported_patch_ids
_print_phase1_preview_patch_report
_print_phase1_preview_quilt_report
_execute_phase1_preview_impl
execute_phase1_preview
execute_phase1_transfer_only
```

---

## Module 5: `solve_diagnostics.py`

Closure seam reports, row/column alignment, shared UV offset measurement.
All diagnostic/reporting infrastructure that analyzes scaffold results.

### Functions — UV Axis Metrics

```
_chain_uv_axis_metrics
_split_uv_by_frame_role
_build_chain_vert_uv_map
_measure_shared_closure_uv_offsets
_classify_closure_anchor_mode
```

### Functions — Closure Seam Reports

```
_count_free_bridges_on_patch_path
_collect_quilt_closure_seam_reports
_print_quilt_closure_seam_reports
_collect_quilt_closure_sensitive_patch_ids
```

### Functions — Frame Alignment Reports

```
_frame_cross_axis_uv_value
_wall_side_row_class_key
_wall_side_column_class_key
_frame_group_display_coords
_collect_quilt_frame_alignment_reports
_print_quilt_frame_alignment_reports
```

---

## Module 6: `solve_reporting.py`

All `format_*_report` functions and their helpers.

### Functions

```
format_root_scaffold_report
format_regression_snapshot_report
format_solve_plan_report
_format_closure_cut_heuristic
_format_patch_signature
_format_candidate_line
```

### Imports

```
from .solve_records import (...)
from .solve_planning import (
    _build_quilt_tree_edges,
    _analyze_quilt_closure_cuts,
)
from .solve_transfer import (
    _build_patch_transfer_targets,
    _collect_phase1_unsupported_patch_ids,
    _ordered_quilt_patch_ids,
    _patch_scaffold_is_supported,
    _format_scaffold_uv_points,
)
from .solve_diagnostics import (
    _chain_uv_axis_metrics,
)
```

---

## Module 7: `solve.py` (Facade)

```python
"""CFTUV Solve — public API facade.

All heavy logic lives in solve_* sibling modules.
This file re-exports the public interface used by operators.py.
"""

from .solve_planning import (
    build_solver_graph,
    plan_solve_phase1,
)
from .solve_frontier import (
    build_root_scaffold_map,
)
from .solve_transfer import (
    execute_phase1_preview,
    execute_phase1_transfer_only,
    validate_scaffold_uv_transfer,
)
from .solve_reporting import (
    format_root_scaffold_report,
    format_regression_snapshot_report,
    format_solve_plan_report,
)
```

That's it. `operators.py` doesn't change at all.

---

## Cross-Module Dependency Graph

```
solve_records.py          ← no internal deps, imports only model.py + constants.py
    ↑
solve_planning.py         ← imports solve_records
    ↑
solve_diagnostics.py      ← imports solve_records, solve_planning (tree helpers)
    ↑
solve_frontier.py         ← imports solve_records, solve_planning, solve_diagnostics
    ↑
solve_transfer.py         ← imports solve_records, solve_frontier (build_root_scaffold_map)
    ↑
solve_reporting.py        ← imports solve_records, solve_planning, solve_transfer, solve_diagnostics
    ↑
solve.py                  ← facade, imports public functions from all modules
```

No circular dependencies. DAG flows downward.

---

## Execution Checklist

### Phase A: Create empty modules, move records

- [ ] Create `solve_records.py` with all type aliases, constants, dataclasses, enums
- [ ] Verify: `from .solve_records import *` works from solve.py
- [ ] Delete moved code from solve.py, replace with imports from solve_records

### Phase B: Extract planning

- [ ] Create `solve_planning.py` with all planning functions
- [ ] Wire imports from solve_records
- [ ] Delete moved code from solve.py, replace with imports
- [ ] Test: `build_solver_graph()` and `plan_solve_phase1()` produce identical output

### Phase C: Extract diagnostics

- [ ] Create `solve_diagnostics.py`
- [ ] Wire imports from solve_records + solve_planning
- [ ] Delete moved code from solve.py

### Phase D: Extract frontier

- [ ] Create `solve_frontier.py` — this is the largest move
- [ ] Move `FrontierRuntimePolicy` here (owner class, not a record)
- [ ] Wire imports from solve_records + solve_planning + solve_diagnostics
- [ ] Delete moved code from solve.py
- [ ] Test: `build_root_scaffold_map()` produces identical scaffold

### Phase E: Extract transfer

- [ ] Create `solve_transfer.py`
- [ ] Wire imports
- [ ] Delete moved code
- [ ] Test: `execute_phase1_preview()` produces identical UV result

### Phase F: Extract reporting

- [ ] Create `solve_reporting.py`
- [ ] Wire imports
- [ ] Delete moved code
- [ ] Test: all format_*_report produce identical text output

### Phase G: Finalize facade

- [ ] solve.py becomes pure re-export facade (~50 lines)
- [ ] Verify operators.py imports still work unchanged
- [ ] Run full regression on production meshes

---

## Risk Assessment

**Risk: circular imports** — Eliminated by DAG structure above. Records has no internal deps. Each subsequent module depends only on earlier modules.

**Risk: FrontierRuntimePolicy** — RESOLVED. This is a mutable runtime owner class, not a record. It lives in `solve_frontier.py` alongside the functions its methods call (`_cf_find_anchors`, `_cf_resolve_candidate_anchors`, `_cf_apply_closure_preconstraint`, `_cf_score_candidate`, `_cf_register_points`). If `solve_diagnostics.py` needs to reference `FrontierRuntimePolicy` as a type hint, it imports it from `solve_frontier`. This does NOT create a circular dependency because diagnostics only uses the class as a parameter type, not at module load time. No delegation wrappers needed.

**Risk: _build_solve_view used by both planning and frontier** — Lives in solve_planning.py. Frontier imports it from there. No duplication.

**Risk: tree helper functions** — `_build_quilt_tree_edges`, `_find_patch_tree_path`, etc. are used by planning, diagnostics, AND frontier. They live in solve_planning.py and are imported by the others.

---

## What This Plan Does NOT Do

- Does not rename any function or class
- Does not change any behavior or algorithm
- Does not restructure records (that's P2 follow-up)
- Does not change operators.py imports
- Does not touch analysis.py, model.py, debug.py, or constants.py
- Does not introduce new abstractions or protocols
