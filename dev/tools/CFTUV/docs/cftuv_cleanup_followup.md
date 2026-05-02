# CFTUV Cleanup Follow-Up

## Track A - Auto Pipeline Follow-Up

### Shape Support
- Add real `CYLINDER` support behind `analysis_shape_support.py` handler dispatch.
- Add real `CABLE` support behind the same dispatch boundary.
- Keep `structural_tokens.py` as the low-level token/signature source; do not turn it into solve logic.
- Extend BAND-adjacent shape support without widening `PatchShapeClass` semantics prematurely.
- Keep shape admission independent of patch-neighbor presence:
  `CABLE` / `CYLINDER` must be classifiable from loop structure and geometry even for isolated/border-only patches.
- Reuse the current BAND pattern:
  shape interpretation may produce runtime support directly even when legacy structural-summary flags are missing.

### Straighten Support
- Revisit `analysis_derived.py` structural summary extraction once new shape handlers land.
- Keep new shape support feeding frontier through the same pattern:
  - analysis facts
  - runtime authority resolution
  - no patch-first detour
- Treat current BAND parametrization as the baseline strip-family experiment:
  - shared section field from spine-normal intersections
  - analysis-owned `BandSpineData`
  - runtime consumption through frontier/pin policy, not through a separate operator
- For `CABLE` / `CYLINDER`, prefer a shared strip/tube parameterization family over shape-specific solver forks.
- The next real design step is not another BAND heuristic pass; it is extracting the reusable section/station core that both `CABLE` and `CYLINDER` can consume.

### Transfer / Diagnostics
- Continue slimming `solve_transfer.py` into smaller orchestration helpers without moving pin logic out of `solve_pin_policy.py`.
- Preserve current validation and reporting density while reducing preview orchestration bulk.

## Track B - Manual / Reverse Workflow Follow-Up

### Alternate Entry
- Implement the placeholder seam introduced in `cftuv/frontier_bootstrap.py`:
  - `seed_runtime_from_existing_scaffold_context(...)`
- Keep this as an alternate entry into the same frontier runtime, not as a parallel solver architecture.

### Reverse / Manual Operations
- Define a future `UV -> ScaffoldMap` reconstruction path that produces result data compatible with transfer/reporting.
- Add local/manual chain operations only on top of the existing scaffold/result boundary.
- Keep manual tools scaffold-aware and patch/chain-based; do not invent corner/junction runtime units.

### Operator Boundary
- Keep `operators.py` limited to Blender classes, panel, and registration; continue pushing orchestration into `operators_pipeline.py` and `operators_session.py`.
- Keep future manual/reverse UI entry points thin and route any session choreography through `operators_session.py` rather than rebuilding helper sprawl in `operators.py`.
