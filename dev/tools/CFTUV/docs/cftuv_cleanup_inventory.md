# CFTUV Cleanup Inventory

## Snapshot
- Goal preserved: `PatchGraph -> SolvePlan -> ScaffoldMap` boundary remains intact.
- Core solve principle preserved: chain-first strongest-frontier.
- Cleanup state reflects the current post-cleanup module graph, including new siblings for shape support, frontier bootstrap, operator orchestration, and records grouping.

## Module Inventory

### Analysis

| module | status | used_by | imports | public_role | notes |
| --- | --- | --- | --- | --- | --- |
| `cftuv/analysis.py` | core | `operators.py`, `operators_pipeline.py`, `operators_session.py`, `solve_planning.py`, `solve_transfer.py` | `model.py`, `analysis_reporting.py`, `analysis_corners.py`, `analysis_derived.py`, `analysis_topology.py`, `analysis_validation.py` | Public analysis facade | Stable entry for reports, preflight, PatchGraph build, derived topology access. |
| `cftuv/analysis_topology.py` | core | `analysis.py` | `model.py`, `analysis_records.py`, `analysis_boundary.py`, `analysis_classification.py`, `console_debug.py` | BMesh -> PatchGraph assembly | Owns patch flood-fill, seam interpretation, and graph invariants. |
| `cftuv/analysis_boundary.py` | core | `analysis_topology.py` | `model.py`, `analysis_records.py`, `analysis_boundary_loops.py`, `analysis_classification.py`, `console_debug.py` | Raw patch boundary tracing + validation | Still the seam between raw boundary data and classified loops. |
| `cftuv/analysis_boundary_loops.py` | core | `analysis_boundary.py` | `constants.py`, `model.py`, `analysis_records.py`, `analysis_frame_runs.py`, `analysis_corners.py`, `console_debug.py` | Loop -> chain/corner topology builder | Heavy but active; print noise removed. |
| `cftuv/analysis_corners.py` | core | `analysis.py`, `analysis_boundary_loops.py` | `constants.py`, `model.py`, `analysis_records.py`, `console_debug.py` | Corner metrics and geometric split helpers | Remains analysis-owned wedge/corner truth source. |
| `cftuv/analysis_classification.py` | core | `analysis_boundary.py`, `analysis_topology.py` | `constants.py`, `model.py`, `analysis_records.py`, `console_debug.py` | Patch type/basis + OUTER/HOLE classification | Temporary UV side effect is now explicitly isolated to the UV classification boundary helpers. |
| `cftuv/analysis_frame_runs.py` | core | `analysis_boundary_loops.py`, `analysis_derived.py` | `model.py`, `analysis_records.py`, `console_debug.py` | Analysis-only run continuity view | Diagnostic/support layer, not solve runtime. |
| `cftuv/analysis_junctions.py` | core | `analysis_derived.py`, `analysis_validation.py` | `model.py`, `analysis_records.py` | Junction aggregation view | Remains derived-only and non-runtime. |
| `cftuv/analysis_records.py` | core | Most analysis modules, `band_spine.py`, `frontier_state.py`, `solve_frontier.py` | `model.py`, `shape_types.py`, `structural_tokens.py` | Analysis dataclasses and derived topology bundle | Stable typed substrate for analysis and structural support, including persisted loop-shape interpretations. |
| `cftuv/analysis_reporting.py` | core | `analysis.py`, `analysis_validation.py` | `analysis_records.py`, `model.py` | PatchGraph report serialization | Observability layer, intentionally untouched in behavior. |
| `cftuv/analysis_validation.py` | core | `analysis.py` | `analysis_records.py`, `analysis_junctions.py`, `analysis_reporting.py`, `model.py` | Derived-topology validation | Keeps invariants explicit and separate from build logic. |
| `cftuv/analysis_derived.py` | refactor | `analysis.py` | `constants.py`, `model.py`, `analysis_records.py`, `analysis_frame_runs.py`, `analysis_junctions.py`, `analysis_shape_support.py`, `band_spine.py`, `console_debug.py` | Derived topology assembly | Still large, but shape orchestration moved out; now owns raw structural summary extraction + final derived bundle assembly. |
| `cftuv/analysis_shape_support.py` | core | `analysis_derived.py` | `analysis_records.py`, `band_spine.py`, `model.py`, `shape_classify.py`, `shape_types.py`, `structural_tokens.py` | Shape fingerprint/classify/support orchestration | Explicit extension point: generic fingerprints in, loop interpretations + per-patch support artifacts out, runtime support assembled per shape. |
| `cftuv/shape_types.py` | core | `analysis_records.py`, `analysis_shape_support.py`, `frontier_state.py`, `shape_classify.py` | `model.py` | Shape enums and interpretation contracts | Keeps `PatchShapeClass` out of the token layer. |
| `cftuv/shape_classify.py` | core | `analysis_shape_support.py` | `model.py`, `shape_types.py`, `structural_tokens.py` | Shape policy classifier | Owns BAND/MIX rules and FREE -> STRAIGHTEN interpretation. |

### Solve / Frontier / Records

| module | status | used_by | imports | public_role | notes |
| --- | --- | --- | --- | --- | --- |
| `cftuv/solve.py` | core | `operators.py`, `operators_pipeline.py`, `operators_session.py`, `solve_diagnostics.py` | `solve_planning.py`, `solve_frontier.py`, `solve_transfer.py`, `solve_reporting.py` | Public solve facade | Stable user-facing API preserved. |
| `cftuv/solve_planning.py` | core | `solve.py`, `solve_diagnostics.py`, `solve_frontier.py`, `solve_reporting.py`, `frontier_bootstrap.py`, `frontier_closure.py` | `analysis.py`, `constants.py`, `model.py`, `solve_records.py`, `console_debug.py` | PatchGraph -> SolverGraph / SolvePlan | Closure-cut diagnostics still live here; print noise routed through `trace_console()`. |
| `cftuv/solve_frontier.py` | refactor | `solve.py`, `solve_diagnostics.py`, `solve_transfer.py` | `analysis_records.py`, `frontier_bootstrap.py`, `frontier_closure.py`, `frontier_eval.py`, `frontier_finalize.py`, `frontier_place.py`, `frontier_rescue.py`, `frontier_score.py`, `frontier_state.py`, `model.py`, `solve_instrumentation.py`, `solve_planning.py`, `solve_records.py`, `console_debug.py` | Quilt frontier driver | Slimmer after bootstrap extraction, but still the main frontier orchestration hotspot. |
| `cftuv/frontier_bootstrap.py` | core | `solve_frontier.py` | `console_debug.py`, `frontier_eval.py`, `frontier_place.py`, `frontier_score.py`, `frontier_state.py`, `model.py`, `solve_planning.py`, `solve_records.py`, `analysis_records.py` | Launch-context build + chain seed bootstrap seam | New alternate-entry seam; includes placeholder for future existing-scaffold seeding. |
| `cftuv/frontier_state.py` | refactor | `frontier_eval.py`, `frontier_score.py`, `solve_frontier.py`, `frontier_bootstrap.py` | `analysis_records.py`, `shape_types.py`, `model.py`, `solve_records.py` | Frontier runtime policy/state wrapper | Now split into immutable launch context + mutable runtime state with compatibility wrapper API. |
| `cftuv/frontier_eval.py` | core | `solve_frontier.py`, `frontier_bootstrap.py` | `console_debug.py`, `frontier_place.py`, `frontier_state.py`, `model.py`, `solve_diagnostics.py`, `solve_records.py` | Candidate evaluation / placement loop | Core frontier hot path. |
| `cftuv/frontier_place.py` | core | `solve_frontier.py`, `frontier_eval.py`, `frontier_rescue.py`, `frontier_bootstrap.py` | `analysis_records.py`, `model.py`, `solve_records.py` | Placement math / UV point generation | Remains placement-only and runtime-owned. |
| `cftuv/frontier_score.py` | core | `solve_frontier.py`, `frontier_bootstrap.py` | `constants.py`, `frontier_state.py`, `model.py`, `solve_records.py` | Frontier rank / local score builders | Still scoring core; no cleanup drift into alignment/manual roadmap. |
| `cftuv/frontier_closure.py` | core | `solve_frontier.py` | `console_debug.py`, `model.py`, `solve_records.py` | Closure pair / ingress mapping | Active runtime support. |
| `cftuv/frontier_rescue.py` | core | `solve_frontier.py` | `console_debug.py`, `frontier_place.py`, `solve_diagnostics.py`, `solve_instrumentation.py`, `model.py`, `solve_records.py` | Rescue path implementations | Left behaviorally intact. |
| `cftuv/frontier_finalize.py` | core | `solve_frontier.py` | `console_debug.py`, `model.py`, `solve_diagnostics.py`, `solve_pin_policy.py`, `solve_records.py` | Final quilt scaffold packaging | Result-boundary critical. |
| `cftuv/solve_transfer.py` | refactor | `solve.py`, `solve_report_metrics.py`, `solve_reporting.py` | `model.py`, `solve_records.py`, `solve_frontier.py`, `solve_pin_policy.py`, `console_debug.py`, `analysis.py` | Scaffold -> UV application / conformal fallback | Still broad, but raw print noise removed from business logic path. |
| `cftuv/solve_pin_policy.py` | core | `frontier_finalize.py`, `solve_transfer.py` | `model.py`, `solve_records.py` | Pin decisions single source of truth | Explicitly preserved. |
| `cftuv/solve_diagnostics.py` | core | `frontier_eval.py`, `frontier_finalize.py`, `frontier_rescue.py` | `model.py`, `solve_records.py`, `console_debug.py`, `solve.py` | Closure/alignment diagnostics | Diagnostics boundary intentionally preserved. |
| `cftuv/solve_instrumentation.py` | core | `frontier_rescue.py`, `solve_frontier.py`, `solve_reporting.py` | `model.py`, `solve_records.py`, `solve_report_utils.py`, `console_debug.py` | Frontier telemetry collector | Observability preserved. |
| `cftuv/solve_reporting.py` | core | `solve.py` | `model.py`, `solve_records.py`, `solve_report_anomalies.py`, `solve_report_metrics.py`, `solve_report_utils.py`, `solve_instrumentation.py` | Human-readable scaffold/plan reports | Reporting layer left intact. |
| `cftuv/solve_report_anomalies.py` | core | `solve_reporting.py` | `model.py`, `solve_records.py`, `solve_report_metrics.py`, `solve_report_utils.py` | Report anomaly sections | Supporting reporting sibling. |
| `cftuv/solve_report_metrics.py` | core | `solve_reporting.py`, `solve_report_anomalies.py` | `model.py`, `solve_records.py` | Report metrics aggregation | Supporting reporting sibling. |
| `cftuv/solve_report_utils.py` | core | `solve_instrumentation.py`, `solve_report_anomalies.py`, `solve_reporting.py` | `dataclasses`, `enum` | Shared reporting formatting helpers | Lightweight utility sibling. |
| `cftuv/solve_records.py` | core | Most solve/frontier modules, `model.py` | `solve_records_common.py`, `solve_records_domain.py`, `solve_records_frontier.py`, `solve_records_transfer.py`, `solve_records_telemetry.py` | Compatibility facade for solve records | New facade keeps existing imports stable while real type ownership moved to themed siblings. |
| `cftuv/solve_records_common.py` | core | `solve_records.py`, record siblings | `constants.py`, `model.py` | Shared solve constants / helpers | Holds thresholds and `_patch_pair_key` / `_clamp01`. |
| `cftuv/solve_records_domain.py` | core | `solve_records.py`, `solve_records_frontier.py` | `model.py`, `solve_records_common.py` | Planning/domain records | Solver graph, solve plan, seam relation, candidate records. |
| `cftuv/solve_records_frontier.py` | core | `solve_records.py`, `solve_records_telemetry.py` | `model.py`, `solve_records_common.py`, `solve_records_domain.py` | Frontier/runtime records | Anchor, candidate, rank, rescue, bootstrap, point-registry records. |
| `cftuv/solve_records_transfer.py` | core | `solve_records.py` | `model.py`, `solve_records_common.py` | Transfer/pin records | UV target, patch apply, pin policy/map records. |
| `cftuv/solve_records_telemetry.py` | core | `solve_records.py` | `model.py`, `solve_records_frontier.py` | Telemetry/report records | Frontier placement/stall/quilt telemetry records. |

### UI / Debug / Foundation

| module | status | used_by | imports | public_role | notes |
| --- | --- | --- | --- | --- | --- |
| `cftuv/operators.py` | refactor | `__init__.py` | `analysis.py`, `debug.py`, `operators_pipeline.py`, `operators_session.py`, `solve.py`, `constants.py` | Blender classes, panel, registration | Active UI boundary is thinner and the extracted helper block is now physically gone. |
| `cftuv/operators_pipeline.py` | core | `operators.py`, `operators_session.py` | `analysis.py`, `model.py`, `solve.py`, `bmesh`, `bpy` | Operator pipeline/preflight helpers | New thin orchestration sibling for patch-graph + solve setup and report helpers. |
| `cftuv/operators_session.py` | core | `operators.py` | `analysis.py`, `constants.py`, `debug.py`, `model.py`, `operators_pipeline.py`, `solve.py`, `bpy` | Session/replay/debug lifecycle helpers | New boundary for replay/debug state choreography. |
| `cftuv/debug.py` | core | `operators.py`, `operators_session.py` | `constants.py`, `model.py`, `mathutils`, `bpy` | Grease Pencil visualization and compatibility | GP ownership preserved here only. |
| `cftuv/console_debug.py` | core | analysis/solve/frontier modules | `bpy` | Verbose console gate + trace helper | Only direct runtime print sink left in business layers. |
| `cftuv/model.py` | core | Entire codebase | `mathutils`, `typing`, `solve_records.py` (TYPE_CHECKING) | Domain enums + IRs | Unsafe-to-touch boundary between analysis and solve. |
| `cftuv/constants.py` | core | analysis/debug/solve modules | none | Thresholds and sentinels | Shared configuration source. |
| `cftuv/structural_tokens.py` | core | `analysis_records.py`, `analysis_shape_support.py`, `shape_classify.py` | `model.py` | Generic loop/chain structural fingerprint layer | No BAND policy, no FREE -> STRAIGHTEN interpretation, no runtime-facing semantics. |
| `cftuv/band_spine.py` | core | `analysis_shape_support.py`, `analysis_derived.py` | `analysis_records.py`, `model.py` | BAND midpoint-spine parametrization | Active runtime support for BAND only; dead classifier helper removed. |
| `cftuv/__init__.py` | core | Blender addon entry | `operators.py` | Addon registration entry | Stable package boundary. |

### Legacy / Reference

| module | status | used_by | imports | public_role | notes |
| --- | --- | --- | --- | --- | --- |
| `Hotspot_UV_v2_5_19.py` | reference_only | none | legacy monolith | Repo-root legacy snapshot | Kept out of active architecture. |

## Four Lists

### Core
- `model.py`
- `analysis.py`, `analysis_topology.py`, `analysis_boundary.py`, `analysis_boundary_loops.py`, `analysis_corners.py`, `analysis_classification.py`, `analysis_frame_runs.py`, `analysis_junctions.py`, `analysis_records.py`, `analysis_reporting.py`, `analysis_validation.py`, `analysis_shape_support.py`
- `solve.py`, `solve_planning.py`, `solve_frontier.py`, `frontier_bootstrap.py`, `frontier_eval.py`, `frontier_place.py`, `frontier_score.py`, `frontier_rescue.py`, `frontier_closure.py`, `frontier_finalize.py`, `solve_transfer.py`, `solve_pin_policy.py`, `solve_diagnostics.py`, `solve_instrumentation.py`, `solve_reporting.py`, `solve_report_anomalies.py`, `solve_report_metrics.py`, `solve_report_utils.py`
- `solve_records.py`, `solve_records_common.py`, `solve_records_domain.py`, `solve_records_frontier.py`, `solve_records_transfer.py`, `solve_records_telemetry.py`
- `operators_pipeline.py`, `operators_session.py`, `debug.py`, `console_debug.py`, `constants.py`, `structural_tokens.py`, `shape_types.py`, `shape_classify.py`, `band_spine.py`, `__init__.py`

### Refactor Zone
- `analysis_derived.py`: still the biggest analysis hotspot even after shape orchestration extraction.
- `solve_frontier.py`: slimmer but still central runtime orchestrator.
- `frontier_state.py`: compatibility wrapper exists, but cleanup can continue once wrapper stabilizes.
- `solve_transfer.py`: still broad; future cleanup can reduce preview/validation orchestration bulk.
- `operators.py`: boundary is now thin; future cleanup should keep new UI features out of policy/session sprawl.

### Legacy / Reference Only
- `Hotspot_UV_v2_5_19.py`
- `docs/_archive/*`

### Trash Candidates
- The disabled legacy operator classes and panel entries for `unwrap_faces`, `manual_dock`, `select_similar`, and `stack_similar`: now removed from active addon code.
- `cftuv/band_operator.py`: deleted from the repo during cleanup.
- Any future reintroduction of `band_operator.py` or a separate BAND operator path: treat as regression.

## Delete / Archive Candidates
- Keep archived, do not import: `Hotspot_UV_v2_5_19.py`

## Unsafe-To-Touch Core Zones
- `cftuv/model.py`: `PatchGraph` / `ScaffoldMap` contracts.
- `cftuv/solve_pin_policy.py`: pin decision ownership boundary.
- `cftuv/debug.py`: GPENCIL / GREASEPENCIL compatibility boundary.
- `cftuv/solve_instrumentation.py`, `cftuv/solve_diagnostics.py`, `cftuv/solve_reporting.py`: observability/reporting boundaries that must not be weakened.
- `cftuv/solve_frontier.py`, `frontier_eval.py`, `frontier_place.py`, `frontier_score.py`: chain-first frontier core; refactor only without architectural drift.
