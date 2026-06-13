# ScaffoldTrace / ScaffoldRail Contract Draft

Status: draft for Architect and user approval. This document is not an
implemented contract and does not amend `G0.md` by itself.

Purpose: define the Layer 3 substrate that lets G5a consume ordered,
direction-stable rails instead of reconstructing rail order and orientation
inside the runtime solver.

## Motivation

G5a v0 validates the pinned-skeleton pipeline on simple developable fixtures,
but the multiseam cylinder exposes a layer inversion: Layer 5 tries to infer
rail order and orientation signs from looped `ConnectedDirectionFamily`
membership. That is not a runtime responsibility. A direction-stable ordered
rail is a Layer 3 graph fact over existing topology and relation evidence.

The current `artist_cyl_multiseam` xfail is therefore a missing
`ScaffoldTrace` / `ScaffoldRail` contract, not an invitation to add another
BFS, greedy traversal, or sign-propagation heuristic to
`scaffold_core/layer_5_runtime/`.

## Proposed G0 Amendment Text

### DD-46 - ScaffoldTrace is ordered graph evidence, not topology identity

`ScaffoldTrace` is a Layer 3 derived evidence view over existing graph atoms:

- `ScaffoldNode`;
- `RunEndpointJunction`;
- `PatchChainDirectionalEvidence`;
- existing crossing/provenance records such as shared-chain and node crossings.

It is an ordered connected sequence of directional evidence members through
existing graph nodes. It must not mutate or replace Layer 1 `Vertex`, `Chain`,
`PatchChain`, `BoundaryLoop`, Layer 3 `ScaffoldNode`, or `ScaffoldEdge`
identity.

Each trace member records:

- directional evidence id;
- patch id and patch-chain id;
- start/end trace node ids;
- topology/source start/end vertex provenance where available;
- crossing provenance to the previous and next member;
- confidence and diagnostics.

`ScaffoldTrace` is evidence only. It is not UV, pins, feature grammar,
packing, texel policy, H/V, WORLD_UP, wall/floor labeling, runtime solve
behavior, or a user-visible edit operation.

### DD-47 - ScaffoldRail is a direction-stable ScaffoldTrace

`ScaffoldRail` is a `ScaffoldTrace` whose ordered member sequence has a stable
transported direction frame suitable for consumption as a conditional axis by
Layer 5.

Each rail carries:

- ordered directional-evidence member ids;
- ordered trace node ids;
- first and last trace node ids for open rails;
- closed-loop flag for loop rails;
- per-member orientation sign in the transported rail frame;
- crossing records used to transport the frame;
- branch records where valence is greater than two;
- loop ambiguity records where no linear start/end order is intrinsic;
- confidence and degradation diagnostics.

The per-member orientation sign is supplied by rail-frame transport, not by
world direction comparison and not by a runtime greedy walk. Dihedral and
in-patch geodesic crossings modulate how the frame transports; they do not
turn rail construction into a UV solve.

`ScaffoldRail` remains Layer 3 evidence. It must not choose UV coordinates,
pins, island packing, texel scale, feature constraints, or Blender operations.

## Loop Policy

Closed or looped direction families are not automatically linear rails.

A loop may become a consumable open `ScaffoldRail` only when a lower-layer
structural cut already provides an ordered opening, for example an island cut
or selected split seam that turns the loop into a trace with distinct first and
last nodes. The cut is an input from topology/island assembly, not a decision
invented by the rail builder.

For a closed loop with no such opening:

- preserve it as a loop rail or ambiguous trace;
- record loop ambiguity explicitly;
- expose consistency checks over the loop;
- do not pick an arbitrary lexical start as a runtime sign source;
- do not force it into Layer 5 as a linear coordinate row/column.

Loop closure equations are validation/consistency checks, not the source of
orientation signs for the whole family.

## Branch Policy

At valence greater than two, the contract must preserve ambiguity unless a
future explicit rule resolves it.

The rail builder may emit:

- branch records naming the junction id;
- incident directional evidence ids;
- candidate continuation pairs;
- evidence/confidence for each candidate.

It must not silently choose one outgoing trace at a branch. A future Layer 4
feature rule or an approved Layer 3 continuation contract may resolve such a
branch, but this draft does not define that policy.

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
when present and unambiguous enough for the current solve.

When `ScaffoldRail` is absent, degraded, branch-ambiguous, or loop-ambiguous,
G5a must:

- emit diagnostics naming the missing or ambiguous rail;
- leave affected vertices unpinned or mark the component UNCONSTRAINED;
- keep the behavior pinned by a known-limitation test;
- not reconstruct the missing rail via local BFS, greedy traversal, lexical
  ordering, world-direction comparison, or ad-hoc sign propagation.

## Positive And Negative Contract Fixtures

Required positive fixtures before implementation:

- two-seam cylinder tube: top and bottom rails remain consumable open rails
  and G5a keeps the validated rectangle;
- l-corridor tunnel: length rail transports across folds, width rails remain
  stable;
- extruded_cross: side-band top rim and bottom rim are distinct rails;
- artist multiseam cylinder capture or in-repo synthetic equivalent:
  multiseam open band exposes ordered rails after the island cut.

Required negative fixtures:

- tube_with_cap: cap perimeter must not merge with side-band rails;
- detached_parallel_walls: disconnected shells never share rails;
- branch fixture with valence > 2: emits branch ambiguity, no silent trace
  choice;
- closed loop with no structural opening: remains loop/ambiguous, not a
  forced linear rail.

## Open Questions For Approval

1. Should `ScaffoldRail` be a separate Layer 3 record type, or a typed view
   attached to `ConnectedDirectionFamily` inspection output?
2. Does island assembly provide the structural cut context to open loop rails,
   or should the rail builder expose both closed-loop and cut-open views?
3. What minimum confidence/degradation fields are required before G5a may
   consume a rail?
4. Which branch-resolution rules belong in Layer 3, and which must wait for
   Layer 4 feature grammar?
