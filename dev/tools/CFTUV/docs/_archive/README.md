# Docs Overview

Only current project documents should live in `docs/`.

## Read Order

1. `docs/cftuv_architecture_v2.0.md`
   Main project baseline. Describes the current addon structure, IR, solve
   pipeline, architectural invariants, and active system boundaries.

2. `docs/cftuv_entity_model_and_control_plan.md`
   Current control document. Fixes the entity model, layering
   (`intrinsic/contextual/derived`), and the allowed scope of `FrameRun` /
   `Junction` work.

3. `docs/cftuv_refactor_roadmap_for_agents.md`
   Practical companion document. Describes structural findings, safe execution
   order, runtime track priorities, and research branches.

4. `docs/cftuv_runtime_notes.md`
   Read only when the task is inside the active runtime stabilization track or
   in diagnostics / research work around the `aligned frame lattice`.

5. `docs/cftuv_regression_checklist.md`
   Phase 0 manual checklist for agreed regression meshes and snapshot review.

## What Each Doc Answers

- `cftuv_architecture_v2.0.md`
  What exists right now? What are the real module boundaries, IRs, and runtime
  invariants?

- `cftuv_entity_model_and_control_plan.md`
  What is the current entity hierarchy? What is primary vs composite vs
  analysis-derived? What small refactor is allowed now?

- `cftuv_refactor_roadmap_for_agents.md`
  In what order is it safe to refactor? Which structural debts are broader than
  the current cleanup?

- `cftuv_runtime_notes.md`
  What are the current runtime heuristics, production-case lessons, and active
  stabilization boundaries?

- `cftuv_regression_checklist.md`
  Which manual regression cases and snapshots should be checked after changes?

## Notes

- Start with architecture, then control plan, then roadmap.
- Runtime notes are not the design baseline. They store sprint-level runtime
  facts, production-case lessons, and active heuristics.
- Current code-side reflection of the control plan:
  `cftuv/model.py` marks topology fields by `intrinsic / contextual / derived`,
  while `cftuv/analysis.py` keeps canonical analysis-derived topology in a
  dedicated derived bundle, validates its internal indices / aggregates, and
  keeps report-only diagnostics separate from it. Raw topology trace, patch
  assembly, preflight, and `PatchGraph` construction now live in
  `cftuv/analysis_topology.py`. Raw boundary trace and raw-boundary validation
  now live in `cftuv/analysis_boundary.py`, while final boundary loop / chain /
  corner serialization now lives in `cftuv/analysis_boundary_loops.py`. Private
  record/dataclass payloads live in `cftuv/analysis_records.py`, corner/role/split geometry in
  `cftuv/analysis_corners.py`, patch classification and UV loop-kind boundary in
  `cftuv/analysis_classification.py`, report/view builders and serialization in
  `cftuv/analysis_reporting.py`, frame-run continuity derivation in
  `cftuv/analysis_frame_runs.py`, junction construction in
  `cftuv/analysis_junctions.py`, canonical derived-topology assembly in
  `cftuv/analysis_derived.py`, and derived/report validation in
  `cftuv/analysis_validation.py`. `analysis.py` is now primarily the public
  facade over topology, derived, reporting, and validation layers. Console/snapshot
  formatting still goes through a typed
  report-view layer with its own presentation-contract validation and a final
  serializer layer instead of ad-hoc string assembly inside report entrypoints.
- `README.md` is the repo entry point.
- `docs/README.md` is the docs map.
- `AGENTS.md` continues to treat `docs/cftuv_architecture_v2.0.md` as the main
  baseline document, with the control plan as the next mandatory companion.
