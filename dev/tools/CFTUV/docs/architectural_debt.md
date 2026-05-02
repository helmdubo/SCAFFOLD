# Architectural Debt

This ledger tracks deliberate architectural debt marked inline with
`ARCHITECTURAL_DEBT: <ID>` comments. Read the matching section before extending
or copying a marked pattern.

## F2_CORNERFAN

Summary:
Circular disk-cycle order around a junction is still reconstructed on demand
from corner records instead of being stored as a first-class `CornerFan`.

Affected files and functions:
- `cftuv/analysis_junctions.py:_derive_junction_disk_cycle`

Why deferred:
- P7 needed junction disk-cycle access for skeleton solve, but a full CornerFan
  refactor would reopen heavily-debugged corner/junction analysis with limited
  additional payoff in this phase.

Trigger conditions:
- Corner or bevel analysis is reopened for unrelated work.
- A third runtime consumer of circular junction order appears.
- Junction/disk-cycle logic starts being copied into new modules.

Estimated payoff:
- Removes repeated angle-sort logic.
- Gives one canonical source for disk-cycle order and incidence metadata.
- Simplifies singular-junction handling in skeleton graph construction.

Origin:
- `docs/P7_skeleton_solve.md`

## F3_LOOP_PREVNEXT

Summary:
Frontier and related runtime helpers still reconstruct loop-local previous/next
chain relations ad hoc instead of consuming explicit `ChainUse` adjacency.

Affected files and functions:
- `cftuv/frontier_eval.py:_cf_find_anchors`
- `cftuv/frontier_score.py:_cf_preview_would_be_connected`
- `cftuv/frontier_score.py:_cf_build_corner_scoring_hints`
- `cftuv/frontier_state.py:FrontierRuntimePolicy._same_patch_continuation_hint`

Why deferred:
- P7 skeleton solve does not require explicit `ChainUse.prev/next`, and
  frontier parity was higher priority than loop-adjacency cleanup.

Trigger conditions:
- A frontier simplification or corner-turn cleanup pass is opened.
- New runtime code starts copying the same prev/next derivation pattern.
- Same-patch continuation logic needs another behavior change.

Estimated payoff:
- Fewer loop-walking helpers and corner-specific conditionals.
- Faster, simpler same-patch adjacency queries.
- Cleaner separation between loop topology facts and frontier heuristics.

Origin:
- `docs/P7_skeleton_solve.md`
