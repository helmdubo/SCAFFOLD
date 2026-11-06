# ScaffoldTrace / ScaffoldRail Contract Draft

Status: APPLIED. The user approved the DD-46/DD-47 text below after plan
Slice O, and it is in `G0.md` v1.6 (2026-11-06). G0 is the contract; this
document keeps the background: motivation, loop and branch policy,
fixtures and the answers to the open questions.

Purpose: define the Layer 3 substrate that lets G5a consume ordered,
direction-stable rails instead of reconstructing rail order and orientation
inside the runtime solver.

## Motivation

G5a v0 validated the pinned-skeleton pipeline on simple developable fixtures,
and the multiseam cylinder exposed a layer inversion: Layer 5 tried to infer
rail order and orientation signs from looped `ConnectedDirectionFamily`
membership. That is not a runtime responsibility. A direction-stable ordered
rail is a Layer 3 graph fact over existing topology and relation evidence.

The `artist_cyl_multiseam` collapse itself turned out to be a Layer 3 family
leak (plan Slice L1). The layer rule stands: missing rail order is never an
invitation to add another BFS, greedy traversal, or sign-propagation heuristic
to `scaffold_core/layer_5_runtime/`.

## Proposed G0 Amendment Text

### DD-46 - ScaffoldTrace is ordered graph evidence, not topology identity

`ScaffoldTrace` is a Layer 3 derived evidence view over existing graph atoms:

- `ScaffoldNode`;
- `RunEndpointJunction`;
- `PatchChainDirectionalEvidence`;
- the crossing records of one `ConnectedDirectionFamily`.

It orders the family's directional members through trace nodes by stations.
The two uses of one hinge Chain, joined by a SHARED_CHAIN crossing, cover the
same source edges and form one station: they are listed together and occupy
a single step between two trace nodes, never two consecutive steps. Every
other crossing links two stations at its trace node: a `ScaffoldNode`, or a
`RunEndpointJunction` inside a coalesced Chain. The trace names its stations
(`ordered_station_member_ids`), so no consumer regroups the uses of a hinge
itself.

It must not mutate or replace Layer 1 `Vertex`, `Chain`, `PatchChain`,
`BoundaryLoop`, Layer 3 `ScaffoldNode` or `ScaffoldEdge` identity, or the
family membership.

Each trace member records:

- directional evidence id;
- patch id and patch-chain id;
- start/end trace node ids;
- the vertex occurrences of its endpoint samples (by sample role, which
  follows the PatchChain traversal, not the trace direction);
- crossing provenance to the previous and next member;
- confidence.

The trace records branch and loop ambiguity and its diagnostics.

`ScaffoldTrace` is evidence only. It is not UV, pins, feature grammar,
packing, texel policy, H/V, WORLD_UP, wall/floor labeling, runtime solve
behavior, or a user-visible edit operation.

### DD-47 - ScaffoldRail is a direction-stable ScaffoldTrace

`ScaffoldRail` is a `ScaffoldTrace` whose station order carries a transported
orientation sign per member, suitable for consumption as a conditional axis by
Layer 5.

Each rail carries:

- ordered directional-evidence member ids;
- ordered stations (`ordered_station_member_ids`); in a consumable rail
  station i is the step between trace nodes i and i + 1, and a branched or
  looped rail lists its stations by station id;
- ordered trace node ids;
- first and last trace node ids;
- closed-loop flag (the stations form one cycle);
- per-member orientation sign: +1 along the rail, -1 against it, 0 unknown;
- crossing records used to transport the frame;
- branch records: a station with more than two links, or a trace node touched
  by more than two stations;
- loop ambiguity records where no linear start/end order is intrinsic;
- confidence and degradation diagnostics.

A member's sign comes from the trace nodes of the links before and after its
station; a rail of one station orients its uses against its first member. The
sign is never taken from world direction comparison or a runtime greedy walk.
Dihedral and in-patch geodesic crossings modulate how the frame transports;
they do not turn rail construction into a UV solve.

A rail is consumable by Layer 5 only when it has more than one member, no
branch record, no closed loop, no diagnostics, and a nonzero sign on every
member.

Cut view. A consumer that owns a structural cut (the members it keeps and the
hinge Chains its cut keeps joined, for example one island's runs and stitched
seams) may ask Layer 3 to cut a family's rail. A crossing survives when both
members are kept and it stays inside one patch or passes a kept Chain. Each
connected piece is ordered through its stations like a whole rail and names
its stations. A loop
opens exactly where the cut opens it; a branch, or a loop the cut leaves
closed, stays unordered with a diagnostic. The cut view is computed on demand
from Layer 3 evidence and the consumer's cut. It is not stored in
`RelationSnapshot`, and it never chooses an opening or a branch itself.

`ScaffoldRail` remains Layer 3 evidence. It must not choose UV coordinates,
pins, island packing, texel scale, feature constraints, or Blender operations.

## Loop Policy

Closed or looped direction families are not automatically linear rails.

A loop may become an ordered open rail only when a structural cut the rail
builder does not own already provides an ordered opening, for example the
seams an island leaves cut or a selected split seam that turns the loop into
a trace with distinct first and last nodes. The cut is an input from
topology or island assembly, not a decision invented by the rail builder.
Implemented as the cut view (`cut_scaffold_rail`); the global rail of a loop
stays a closed, non-consumable loop rail.

For a closed loop with no such opening:

- preserve it as a loop rail or ambiguous trace;
- record loop ambiguity explicitly;
- expose consistency checks over the loop;
- do not pick an arbitrary lexical start as a runtime sign source;
- do not force it into Layer 5 as a linear coordinate row/column.

Loop closure equations are validation/consistency checks, not the source of
orientation signs for the whole family.

## Branch Policy

At valence greater than two, the contract preserves ambiguity unless a future
explicit rule resolves it.

The rail builder emits branch records keyed by the branching station
(`station:<member>`) or trace node (`trace_node:<node>`) with the stations
involved. A trace node touched by more than two stations is a branch even
when the stations form a path: a path that comes back to a node it passed
is not a line. A cut segment that still branches carries `branch:<record>`
diagnostics and zero signs.

It must not silently choose one outgoing trace at a branch. A future Layer 4
feature rule or an approved Layer 3 continuation contract may resolve such a
branch; this contract does not define that policy.

## Relationship To Existing Evidence

`ConnectedDirectionFamily` answers membership: which directional evidence
records belong to one transported family.

`ScaffoldTrace` answers ordering: how directional evidence records connect
through graph nodes.

`ScaffoldRail` answers direction stability: whether an ordered trace has a
transport-consistent frame that Layer 5 may consume as an axis input.

`RunEndpointJunction` remains the graph atom that exposes directional-run
endpoints inside coalesced chains. Rail construction consumes it; it does not
replace it.

## Layer 5 Consumer Rule

G5a may consume `ScaffoldRail` order and per-member transported orientation
when present and unambiguous enough for the current solve. Inside an island it
consumes rails through the cut view, with the island's runs and stitched hinge
Chains as the cut.

Since plan Slice O, G5a checks the island rails and reports failures as
validation outputs (`SolveResult.rail_frame_conflicts`):

- every island line with more than one run is exactly one cut segment;
- in an island with a rigid unfolded frame, an ordered segment runs one way
  along its axis: the rail sign times the frame sign is the same for every
  axis run of the line.

The solve does not use rail order yet; the unwrap along rails is a later
stage.

When `ScaffoldRail` is absent, degraded, branch-ambiguous, or loop-ambiguous,
G5a must:

- emit diagnostics naming the missing or ambiguous rail;
- leave affected vertices unpinned or mark the component UNCONSTRAINED;
- keep the behavior pinned by a known-limitation test;
- not reconstruct the missing rail via local BFS, greedy traversal, lexical
  ordering, world-direction comparison, or ad-hoc sign propagation.

## Positive And Negative Contract Fixtures

Positive fixtures, all covered by tests:

- two-seam cylinder tube: both rim rings stay closed loop rails in Layer 3;
  the island cut opens each at the seam the island leaves cut into one ordered
  rail (`test_cut_rail_opens_a_loop_only_where_the_cut_is`,
  `test_island_cut_opens_the_ring_rails_of_a_two_seam_tube`);
- l-corridor tunnel: length rails transport across the folds and stay open
  and consumable;
- beveled wall corner and T-vertex wall: the two uses of a hinge are one
  station, and stations line up through their nodes;
- extruded_cross: side-band top rim and bottom rim are distinct rails;
- artist multiseam cylinder capture: both rims are closed loop rails across
  the six strips, and the band island opens each into one ordered rail
  (`test_artist_multiseam_band_rims_open_into_ordered_island_rails`).

Negative fixtures:

- tube_with_cap: cap perimeter must not merge with side-band rails;
- detached_parallel_walls: the two shells share no topology, and no family
  (so no rail) spans both (checked at Slice O, not pinned by a rail test);
- branch fixtures with valence > 2: a station with three links
  (`test_cut_rail_keeps_a_branch_unordered`), a path that returns to its own
  node, and the T-vertex wall with its right hinge cut, where the floor and
  wall uses of that hinge both continue the left station at w1
  (`test_cut_rail_names_the_branch_where_a_cut_hinge_parts_its_uses`); each
  stays unordered with a branch diagnostic;
- closed loop with no structural opening: remains a loop rail, not a forced
  linear rail;
- reflex corner (plan Slice O1): a node crossing never folds back over a
  patch that wraps around a corner node, so no rail doubles back in the frame.

## Answers To The Open Questions (Slice O)

1. Separate record or typed view? Separate Layer 3 records: `ScaffoldTrace`
   and `ScaffoldRail`, one per family, in `RelationSnapshot`. A cut segment
   (`ScaffoldRailSegment`) is a value of the on-demand cut view, not a stored
   record.
2. Who opens loops? Island assembly owns the cut, and the rail builder exposes
   both views: the uncut global rail (loops stay loops) and the cut view that
   orders the pieces of a caller's cut.
3. Minimum fields before G5a may consume a rail: the consumable rule above
   (`is_consumable_by_g5a`) for a global rail, and `is_ordered` for a cut
   segment (no branch, no uncut loop, no diagnostics, every sign nonzero).
   Confidence is informational: diagnostics cap it at 0.5, branches and loops
   at 0.75.
4. Branch resolution: none in Layer 3 yet. Branches stay explicit; resolving
   them needs a Layer 4 feature rule or an approved Layer 3 continuation
   contract. On the 13 seamed buildings objects 10 of 4821 global rails
   branch, and 4 of 2094 island rails with more than one run stay unordered,
   each at a node touched by more than two stations of one family.
