# Agent Handoff - Scaffold Core

This file is the continuity document for independent AI agents.

Read this after `AGENTS.md` and before changing code.

---

## Current state

```text
Project: Scaffold
Core package: scaffold_core/
Current phase: G5a - Skeleton Runtime
Architecture: immutable B-rep-inspired interpretation pipeline
G0 contract: v1.9 (G0.md remains read-only for agents)
```

Scaffold Core currently contains Layers 0-3, the G5a Layer 5 runtime,
pipeline diagnostics and tests. Layer 4, public API and UI packages remain
deferred:

```text
scaffold_core/layer_4_features/
scaffold_core/api/
scaffold_core/ui/
scaffold/
```

Do not create deferred phase directories during G5a. Layer 5 may consume
Layers 0-3 read-only; relation contracts remain frozen unless the task
explicitly authorizes a G3 repair.

Root `scaffold_blender_inspection.json` is a user-only debug artifact and may
be stale. Do not use it as an architecture reference; use code, docs and tests
instead.

---

## Agent workflow summary

Default execution model:

```text
Architect chat (persistent)
  plans slices and writes Task Cards

Codex Orchestrator session (disposable, one Task Card)
  spawns scaffold_explorer, scaffold_worker and scaffold_reviewer subagents

Reviewer subagent gate
  mandatory after every Worker diff
```

Read:

```text
docs/agent_rules/planning_workflow.md
docs/agent_rules/codex_workflow.md
docs/agent_rules/codex_subagents.md
```

Do not manually create separate Worker/Reviewer chats by default.

---

## Essential reading order for a new agent

1. `AGENTS.md`
2. `docs/context_map.yaml`
3. `docs/phases/G5a_skeleton_runtime.md`
4. `G0.md`
5. `docs/architecture/design_decisions.md`
6. `docs/agent_rules/import_boundaries.md`
7. `docs/agent_rules/anti_overengineering.md`
8. `docs/agent_rules/testing_rules.md`
9. `docs/agent_rules/minimal_patch_protocol.md` if fixing existing code
10. `docs/agent_rules/codex_subagents.md` if using Codex subagents

---

## Current G3/G5a status

Implemented:

- PatchAdjacency / DihedralKind
- conservative ChainContinuationRelation (TERMINUS/SPLIT only)
- ChainDirectionalRun
- PatchChainDirectionalEvidence
- AlignmentClass v0
- PatchAxes v0
- PatchChainEndpointSample
- PatchChainEndpointRelation v0
- LoopCorner v0
- ScaffoldNode v0
- ScaffoldEdge v0
- ScaffoldGraph v0
- ScaffoldJunction v0 SELF_SEAM/CROSS_PATCH
- LocalFaceFanGeometryFacts
- ScaffoldNodeIncidentEdgeRelation v1 complete all-pairs edge-end occurrence matrix
- ScaffoldNodeIncidentEdgeRelationKind SURFACE_SLIDING_CONTINUATION_CANDIDATE v0
- ScaffoldContinuityComponent v0
- SideSurfaceContinuityEvidence v1 evidence-only same-side surface flow record
  with direction/flow-family gate
- SurfaceFlowCompatibilityEvidence v0 evidence-only cross-patch flow-family
  compatibility record
- ConnectedDirectionFamily v1 occurrence-aware geodesic continuation
- RunEndpointJunction v0
- Layer 5 v0 skeleton runtime:
  - `islands.py` spanning-tree Level A island assembly;
  - `skeleton.py` selection-wide AXIS_A / AXIS_B solve over island lines,
    which are the pieces of the Layer 3 rail cut by the island (plan
    Slices O, Q); axes and run orientation from the rigid unfolded island
    frame when no island patch is curved (plan Slice N); an island without
    one takes in-line run signs from its ordered island rails (plan
    Slice Q); the rails are checked against the frame (plan Slice O);
  - `pins.py` run_skeleton_solve output model and invariants (axis-parallel,
    SEAM_SELF length, node/frame and rail/line/frame agreement); pins are
    keyed by topology vertex occurrence (DD-37), so both sides of a seam keep
    their own UV;
  - `uv_transfer.py` the only bpy write boundary; a loop takes only the pin
    of its own vertex occurrence in its own patch.
- Debug add-on `Write UV (G5a)` button in
  `dev/tools/scaffold_graph_debug/`.
- ScaffoldTrace / ScaffoldRail v1 Layer 3 evidence views
  (`layer_3_relations/scaffold_rails.py`): ordered through hinge stations;
  closed loops stay non-consumable globally, and the pure cut view
  `cut_scaffold_rail` opens them only where a caller's structural cut
  (an island) opens them.
- PatchChainShapeRelation v0 (`layer_3_relations/patch_chain_shape.py`,
  G0 DD-48): per PatchChain use, each piece between surface corners is a
  surface line, a surface curve or unresolved, from Layer 2 chain plane
  and per-side facts. One reader: directional runs take the chord
  shortcut of a zigzag Chain per use (Stage B, G0 DD-30).
- RunCornerRelation v0 (`layer_3_relations/run_corners.py`, G0 DD-49): the
  corner between two run ends on one patch surface, STRAIGHT, RIGHT or
  OTHER; the Layer 5 frame-free axis bipartition reads the RIGHT corners.
- Pipeline tooling: Chain -> PatchChain incidence index
  (`layer_3_relations/patch_chain_incidence.py`), per-pass stage timings in
  `PipelineContext.pass_timings` (reported by inspection), and a networkx
  node-link ScaffoldGraph export (`scaffold_graph_node_link` in full
  inspection; `dev/tools/scaffold_graph_viewer/export_networkx_graph.py`).

Plan Slice L: the artist_cyl_multiseam collapse was a Layer 3 family leak
through curved shared chains, fixed by the straight-hinge SHARED_CHAIN rule
(L1). Slice L2 removed the same-patch bridge and blocks any family merge that
revisits a patch. Slice M1 keeps UV writes inside the solved faces. Tier 3
Blender smoke runner: `dev/tools/blender_smoke/` (Blender 4.5.9 headless). A corner-node gap stays a strict xfail until a future patch-normal
filter; do not introduce cap/wall semantics for it.

Plan Slice N (consistent patch -> line -> island structure): Layer 3
in-patch geodesic continuation no longer depends on edge vertex order (DD-45),
and node crossings name the hinge through their node (DD-43 provenance).
Layer 5 splits families into island lines at cut seams and derives axes and
orientation in the rigid unfolded island frame; 60 of 62 islands have one, so
the frame-free bipartition (3522 conflicts before) no longer runs there. On
the 13 seamed buildings objects: pins 964 -> 6924, Layer 5 diagnostics 3561
-> 36, OBLIQUE runs 7458 -> 97. Tier 3 now records structure metrics
(`rigid_islands`, `island_lines`, `oblique_runs`, `lines_not_straight`,
`patches_outside_frame`, `node_frame_mismatches`).

Plan Task Card M2 (bug fix after Slice N): pins were keyed by (source vertex,
patch), so the two seam-side occurrences of a SEAM_SELF band collapsed into
one pin, and uv_transfer borrowed another patch's pin for loops without one.
Pins now carry their vertex occurrence and the write looks each loop up by its
face corner's occurrence; the solve is unchanged. Tier 3: Cube pins 40 -> 42,
and 706 borrowed loops on four walls objects are no longer written. A run end
on a seam-cut mid-chain vertex stays unpinned with a diagnostic.

Plan Slice O (ScaffoldRail over island lines): a node crossing no longer
folds back over a patch that wraps around a corner node (O1, G3 repair; 75
fold-backs on buildings -> 0). Rails are ordered through hinge stations:
the two uses of one hinge Chain are one station, not two members in a row
(O2; consumable rails 233 -> 4301 of 4821). The Layer 3 cut view orders a
rail cut by a caller's cut, so a loop opens only where the island cuts it
(O3). Layer 5 checks every island line against its island rail and the
frame (O4): 2094 island rails with more than one run, 2090 ordered, 0
conflicts. Tier 3 records `island_rails`, `unordered_island_rails` and
`rail_frame_conflicts` (O5). The solve does not use rail order yet; pins,
Layer 5 diagnostics and OBLIQUE runs are unchanged.

Plan Slice P (rigid seams first): the island tree takes straight hinges
and coplanar joins between planar, unwarped patches before the other
accepted seams, so a planar patch no longer hangs off a warped n-gon when a
path of rigid seams connects it to the frame root. The tree and the rigid
frame share one predicate (`islands.is_rigid_seam`). On buildings, patches
outside the frame go 10 -> 5 (only warped n-gons remain), OBLIQUE runs
97 -> 65, pins 6926 -> 6957 and Layer 5 diagnostics 36 -> 31; four seams
swap between stitched and cut.

Plan Slice Q (Layer 5 on rails): island lines are the pieces of the Layer
3 rail cut, and an island without a rigid frame takes its in-line run
signs from its ordered island rails; a run on an unordered rail stays
unsigned with a diagnostic. Layer 5's own family split and head-to-tail
sign walk are gone, and so is the DD-47 provisional exception. Results
are identical on all 101 islands of the buildings and in-repo captures.

Not implemented:

- ScaffoldJunction kinds beyond SELF_SEAM/CROSS_PATCH
- ScaffoldCircuit
- ScaffoldRail branch resolution
- WorldOrientation
- Layer 4 Feature Grammar
- public API
- product UI/add-on wrapper beyond the dev debug add-on

---

## Current terminology

```text
PatchChain:
  final patch-local oriented occurrence of a Chain in a BoundaryLoop.

PatchChainDirectionalEvidence:
  derived directional measurement for a PatchChain.
  It is not competing PatchChain identity.

PatchChainEndpointSample:
  endpoint ray/evidence sample for a PatchChain directional measurement.
  It is not a graph node.

PatchChainEndpointRelation:
  pairwise local relation between endpoint samples at one Vertex.
  It is not a graph node.

LocalFaceFanGeometryFacts:
  local owner-normal geometry evidence.
  It is not a graph node.

LoopCorner:
  patch-local transition between adjacent PatchChains in one BoundaryLoop.

ScaffoldNode:
  implemented G3c7 graph-level evidence node assembled from LoopCorners and
  endpoint evidence. It is not Layer 1 identity and must not mutate Vertex,
  Chain or PatchChain records.

ScaffoldJunction:
  implemented SELF_SEAM/CROSS_PATCH graph-level classification overlay on
  existing ScaffoldNode, not a separate graph node identity. SELF_SEAM
  classifies a ScaffoldNode where two incident final PatchChains share the same
  ChainId and same PatchId. CROSS_PATCH classifies an existing ScaffoldNode
  whose incident final ScaffoldEdges reference more than one distinct PatchId.
  All other ScaffoldJunction kinds remain future/deferred.

ScaffoldEdge:
  implemented G3c8 graph-level view of one final PatchChain.

ScaffoldGraph:
  implemented G3c8 connectivity graph assembled from ScaffoldNodes and
  ScaffoldEdges.

ScaffoldTrace:
  implemented v1 (G0 DD-46) ordered evidence view over ConnectedDirectionFamily
  members through ScaffoldNode / RunEndpointJunction atoms, by stations: the
  two uses of one hinge Chain are one step between two trace nodes.

ScaffoldCircuit:
  future closed ScaffoldTrace.

ScaffoldRail:
  implemented v1 (G0 DD-47) direction-stability view over a ScaffoldTrace;
  branches and closed loops stay ambiguous and non-consumable by G5a; the
  on-demand cut view orders the pieces of a consumer's cut (an island).

ScaffoldContinuityComponent:
  implemented Layer 3 derived evidence view grouping existing ScaffoldEdges into
  continuity families from ScaffoldNodeIncidentEdgeRelation records.

SideSurfaceContinuityEvidence:
  implemented Layer 3 derived evidence record over two
  existing ScaffoldEdge endpoint occurrences at one existing ScaffoldNode. It
  proves candidate same-side surface flow within one patch boundary loop and
  compatible direction/flow-family evidence. It is evidence only.

SurfaceFlowCompatibilityEvidence:
  implemented Layer 3 derived evidence record over two
  existing ScaffoldEdge endpoint occurrences or edge-pair occurrences across
  compatible patches. It proves cross-patch surface-flow family compatibility
  only. It is separate from SideSurfaceContinuityEvidence and is evidence only.
```

---

## Layer 1 topology status

Layer 1 builds immutable topology from selected source faces.

Patch segmentation is seam-only by default. Patch flood fill is blocked by:

```text
mesh/selection border
non-manifold selected edge
explicit Scaffold boundary mark
Blender UV Seam
```

Blender Sharp is read as source data but is not a default Patch boundary.

BoundaryLoops contain final PatchChains. Raw boundary sides, atomic source
edges, draft boundary runs and raw boundary cycles are builder internals.
Downstream systems must use final PatchChains.

Layer 1 boundary run kinds:

```text
BORDER_RUN
PATCH_ADJACENCY_RUN
SEAM_SELF_RUN
NON_MANIFOLD_RUN
```

SEAM_SELF loops may materialize duplicate topology Vertex occurrences so one
source vertex can appear on different sides of a materialized BoundaryLoop.
VertexId equality is topology-occurrence equality; SourceVertexId equality is
provenance equality.

Cylinder sanity case:

```text
Cylinder tube without caps + one seam cut:
  Patch count: 1
  BoundaryLoop count: 1 OUTER
  Chain count: 3
  PatchChain count: 4
  LoopCorner count: 4
  ScaffoldNode count: 2
  ScaffoldEdge count: 4
  SELF_SEAM ScaffoldJunction count: 2

PatchChains:
  1. seam side A
  2. cap / border ring A
  3. seam side B
  4. cap / border ring B

LocalFaceFanGeometryFacts:
  many per mesh
  not ScaffoldJunctions
  not expected to be 2

ScaffoldNode:
  graph-level evidence nodes assembled from loop corners and endpoint evidence;
  this is not one node per mesh vertex.

ScaffoldEdge:
  one graph edge per final PatchChain.

ScaffoldJunction:
  ordinary ScaffoldNodes remain unclassified unless a ScaffoldJunction
  classifier emits a record. SELF_SEAM classifies the 2 seam endpoint
  ScaffoldNodes in this fixture after ScaffoldGraph construction.

Grease Pencil compact report expectation:
  scaffold_node_count: 2
  scaffold_edge_count: 4
  scaffold_junction_count: 2
  edge_stroke_count: 4
  node_marker_count: 2
  junction_marker_count: 2
```

---

## Layer 3 implemented chain

```text
Layer 1 Chain / PatchChain
-> Layer 2 ChainSegmentGeometryFacts
-> Layer 3 ChainDirectionalRun
-> Layer 3 PatchChainDirectionalEvidence
-> Layer 3 AlignmentClass
-> Layer 3 PatchAxes
```

Current graph-prep layer:

```text
PatchChainEndpointSample
-> PatchChainEndpointRelation
-> LoopCorner
-> ScaffoldNode
-> ScaffoldEdge / ScaffoldGraph
-> ScaffoldJunction classification for SELF_SEAM/CROSS_PATCH
```

PatchChainEndpointRelation classifies local endpoint pairs as:

```text
CONTINUATION_CANDIDATE
CORNER_CONNECTOR
OBLIQUE_CONNECTOR
AMBIGUOUS
DEGENERATE
```

LoopCorner is patch-local. ScaffoldNode is graph-level evidence. ScaffoldJunction
is a ScaffoldNode classification overlay, not every corner or node and not a
separate graph node identity. Ordinary ScaffoldNodes remain unclassified unless
a ScaffoldJunction classifier emits a record.
ScaffoldEdge is a graph-level view of one final PatchChain, and ScaffoldGraph is
connectivity-only over existing ScaffoldNodes and ScaffoldEdges.

ScaffoldNodeIncidentEdgeRelation v1 is implemented as a complete unordered
all-pairs relation over incident ScaffoldEdge
endpoint occurrences at one existing ScaffoldNode: n incident edge-end
occurrences emit C(n,2) relations. Missing endpoint sample/relation evidence
must not make a pair disappear; it becomes MISSING_ENDPOINT_EVIDENCE or
DEGRADED evidence. Implemented normal-aware kinds include
STRAIGHT_CONTINUATION_CANDIDATE, SURFACE_CONTINUATION_CANDIDATE,
CROSS_SURFACE_CONNECTOR, ORTHOGONAL_CORNER, OBLIQUE_CONNECTOR,
SAME_RAY_AMBIGUOUS, MISSING_ENDPOINT_EVIDENCE and DEGRADED.

SURFACE_SLIDING_CONTINUATION_CANDIDATE is implemented as a conservative
node-local relation between two existing ScaffoldEdge
endpoint occurrences where tangent/chord classification may otherwise look
orthogonal or same-ray, but explicit same-side-surface evidence plus compatible
local owner normals support continuation along the same curved or side surface.
It requires local owner-normal evidence, compatible local owner normals and
explicit same-side-surface evidence. Current SideSurfaceContinuityEvidence v1
is consumed as this explicit same-side-surface evidence source and includes the
direction/flow-family compatibility gate before this evidence may promote a pair
to SURFACE_SLIDING_CONTINUATION_CANDIDATE. Same patch, same
loop, END -> START adjacency and compatible local normals are not sufficient by
themselves under v1. Missing/degraded or direction-family-incompatible evidence
and SharedChainPatchChainRelation alone must not produce this kind under v1.
Cross-patch cap, corner and shared-boundary cases remain non-propagating unless
same-side-surface and direction/flow-family evidence is explicit and safe under
v1.

This relation is evidence only. It must not choose traces, circuits, rails,
continuations, UV behavior or runtime behavior, and must not change
ScaffoldNode grouping or ScaffoldEdge, PatchChain, Chain, Vertex or
BoundaryLoop identity.

SideSurfaceContinuityEvidence v1 is implemented as a Layer 3 derived evidence
record over two existing ScaffoldEdge endpoint
occurrences at one existing ScaffoldNode. Required evidence is same
ScaffoldNodeId, same PatchId, same LoopId, different ChainId, explicit and
serialized/traceable endpoint occurrence roles, same materialized/source vertex
at the node, ordered local adjacency END -> START, both endpoint samples,
LOCAL_FACE_FAN_NORMAL for both owner normals, normal_dot greater than or equal
to the ScaffoldNodeIncidentEdgeRelation compatible-normal threshold source
COMPATIBLE_NORMAL_MIN_DOT, and no missing or degraded endpoint evidence.

Implemented v1 evidence additionally requires direction/flow-family compatibility
when PatchChains have AlignmentClass or direction-family evidence. If
direction-family evidence is missing, ORTHOGONAL_CORNER promotion must be
conservative and must not emit SideSurfaceContinuityEvidence.
SAME_RAY_AMBIGUOUS remains conservative unless direction-family compatibility is
explicit.
Same-chain, cross-patch, different-loop, shared-chain-only, cap/corner or
cross-surface pairs without explicit same-side evidence, ORTHOGONAL_CORNER pairs
crossing different AlignmentClass families, same-patch same-loop END -> START
compatible-normal pairs without compatible direction/flow-family evidence, and
missing/degraded endpoint or normal evidence are non-evidence.

ScaffoldContinuityComponent v0 groups ScaffoldEdges into continuity families
using existing ScaffoldNodeIncidentEdgeRelation records. Default propagation
includes SURFACE_CONTINUATION_CANDIDATE and
SURFACE_SLIDING_CONTINUATION_CANDIDATE. STRAIGHT_CONTINUATION_CANDIDATE is weak
non-default evidence. ORTHOGONAL_CORNER, OBLIQUE_CONNECTOR,
CROSS_SURFACE_CONNECTOR, SAME_RAY_AMBIGUOUS, MISSING_ENDPOINT_EVIDENCE and
DEGRADED do not propagate; SAME_RAY_AMBIGUOUS must preserve ambiguity. Every
ScaffoldEdge belongs to exactly one component, including singletons, and
ambiguous component evidence must not choose one continuation target.
ScaffoldContinuityComponent v0 must not propagate directly through
SideSurfaceContinuityEvidence; it may continue only through
SURFACE_SLIDING_CONTINUATION_CANDIDATE.

SurfaceFlowCompatibilityEvidence v0 is implemented. It is
a Layer 3 derived evidence record over two existing ScaffoldEdge endpoint
occurrences or edge-pair occurrences across compatible patches. It means the two
PatchChains are compatible members of the same surface-flow family across patch
boundaries. It is separate from SideSurfaceContinuityEvidence, which handles
same-patch/same-loop local side flow.

Implemented rule A covers ring flow without SharedChainPatchChainRelation when the
current ScaffoldNodeIncidentEdgeRelation kind is SAME_RAY_AMBIGUOUS, endpoint
samples are present, AlignmentClass/direction-family and PatchAxes role are
compatible where available, both patches are compatible side/dual-axis patches,
the pair is not same-patch, and evidence is not missing/degraded. Positive
Cube.001 examples are P1C1/P2C0 and P1C3/P2C2; negative examples are
P0C1/P1C1 and P0C0/P2C0.

Implemented rule B covers side-side seam flow through a SharedChainPatchChainRelation
when both patches are compatible side/dual-axis patches with matching PatchAxes
structure, same AlignmentClass/direction-family, same PatchAxes role where
available, no cap-like single-axis patch participation, and no missing/degraded
evidence unless a future edge-level fallback is explicitly approved. Positive
Cube.001 example is P1C2/P2C3; negative examples are P0C0/P2C0 and P0C1/P1C1.

SurfaceFlowCompatibilityEvidence must not choose traces, circuits, rails,
selected next edges, continuation targets, UV direction, features or runtime
solve behavior. It must not reintroduce same-loop alignment:0 <-> alignment:1
false merges. P1C0/P2C1 and other missing-endpoint lower-side flow remain
deferred in v0; do not add edge-level fallback in this slice.
SURFACE_SLIDING_CONTINUATION_CANDIDATE may consume
SurfaceFlowCompatibilityEvidence as an additional same-flow evidence source.
ScaffoldContinuityComponent v0 must not propagate directly through
SurfaceFlowCompatibilityEvidence and continues to propagate only through
SURFACE_*_CONTINUATION_CANDIDATE relation kinds.

Debug component coloring should represent continuity_component_id, not relation
kind. Relation kind remains a separate visual channel, and component colors
must be deterministic pseudo-random and stable by component id, never true
random.

ScaffoldNode v0 grouping policy:

```text
SourceVertexId grouping when provenance exists;
VertexId fallback when no SourceVertexId exists.
```

This grouping is a Layer 3 derived view. It must not rewrite or merge Layer 1
Vertex, Chain or PatchChain identity.

Do not use U/V labels, H/V labels, WORLD_UP, WorldOrientation or runtime solve
in Layer 3 AlignmentClass, PatchAxes, endpoint relations, LoopCorner or
ScaffoldNode.
Do not store normals on Layer 1 PatchChain.

---

## OQ-11 status

OQ-11 is partially resolved.

Resolved:

- Final PatchChain is the public source of truth.
- Raw boundary elements are builder internals.
- Layer 3 may derive directional evidence from final PatchChains.
- Polygonal straight/turning Chains can be described by ChainDirectionalRun /
  PatchChain directional evidence.
- Directional evidence must not become a competing PatchChain identity.
- ScaffoldNode v0 may aggregate materialized Vertex occurrences as graph-level
  evidence, but not as Layer 1 identity.

Still unresolved:

- curved-chain policy;
- sawtooth tuning;
- user split marks;
- closed-loop wrap merge policy;
- advanced corner detection;
- local face-fan refinement policy;
- ScaffoldCircuit and ScaffoldRail branch resolution.
- lower-side cross-patch or same-chain lower-ring flow endpoint fallback.

---

## Next architecture decision

Checkpoint 2026-11 (plan Slices L1, L2, M1, N, Task Card M2 and Slice O).
ConnectedDirectionFamily transports SHARED_CHAIN only across straight
single-run hinges, and a family visits each patch at most once (G0 v1.5
DD-43). UV writes stay inside the solved faces, and each loop takes only the
pin of its own vertex occurrence. Layer 5 works on island lines in the
unfolded island frame and checks them against the island rails that the
Layer 3 cut view orders (Slice O). The
Tier 3 Blender runner (`dev/tools/blender_smoke/`) and its
`buildings_seamed.json` baseline cover 13 seamed artist objects and record
structure metrics.

The user's goal for this stage is a consistent structure on the levels patch
-> line -> island; the concrete unwrap along rails comes later, and the final
unwrap is only a test tool.

Open decisions, all owned by the user (plan "Decisions the user must
approve", items 3 and 11; item 6 is applied as G0 v1.6):

- Next level (plan decision 11), measured after Slice P on the 13 seamed
  objects: 3 warped n-gons after Slice R, all one hexagon folded around a
  box corner (source mesh warp); curved runs inside Layer 3
  lines (OQ-11; 12 OBLIQUE runs); island assembly without self-overlap
  (walls.007), DONE as plan Slice U (overlap gate: islands 62 -> 355, no
  overlap between patches of an island); branch resolution for the 4
  unordered island rails.
  Cross-island axis agreement: before Slice U no family spanned two
  islands; after it 2470 of 4821 families do, so it is now an open item.
  Plan Slice Q (Layer 5 on rails) is DONE.
- DD-46/DD-47 ScaffoldTrace/ScaffoldRail: approved by the user and applied
  as G0 v1.6 (2026-11-06), together with the Slice O1 fold-back rule in
  DD-43.
- Plan Slice S (user-approved): the rigid frame snaps runs to an axis only
  within about 5 degrees, and the solve absorbs 1 mm per metre of drift;
  pins 6966 -> 10104, contradictions 20 -> 5, artist_cross_band end
  patches solve. Plan Slice T: a run that leaves its axis by more than
  drift is a jog and alone goes OBLIQUE; contradictions 5 -> 0, pins
  10176. Per-component gauge stays an unwrap-level item. The
  uv_transfer cross-patch fallback and the seam-side pin collapse are fixed
  (Task Card M2).
- Corner-node gap (strict xfail): deferred to a future patch-normal filter;
  do not add cap/wall semantics.

### Session handoff (2026-11-10)

Slices R, S, T and U are merged into main (PRs #24-#27); nothing is pending
in review. Tier 3 on the 13 seamed buildings objects after Slice U: islands
355 (354 framed), pins 10112, OBLIQUE 194, Layer 5 diagnostics 28 (25 jogs,
3 folded hexagons), contradictions 0, lines not straight 0, overlap between
patches of an island 0 (walls/f302 overlaps only itself), invariants 0,
4 unordered island rails. Tests: 338 passed, 4 skipped, 1 xfailed.

Measurement probes for the next item live in
`dev/tools/blender_smoke/probes/` (see the README there). After Slice U,
`cross_island.py` reports 2470 of 4821 families in more than one island and
1199 of them with both AXIS_A and AXIS_B; axis labels are local to each
island frame, so the first step of cross-island agreement is to define what
agreement means across frames before counting defects.

Candidate next slices, the choice is the user's: cross-island axis agreement
(recommended), branch resolution for the 4 unordered island rails, curved
runs inside lines (OQ-11).

### Session handoff (2026-11-13)

The user stopped the run of autonomous Layer 5 slices: he could no longer
follow them, because their results were visible only as Tier 3 numbers. His
direction now: layers below UV first; every slice must end with something
he can look at in Blender.

Done (plan Slice W): Stage A, merged as PR #29: chain shape facts in Layer
2, `PatchChainShapeRelation` v0 in Layer 3 (G0 DD-48) and the debug overlay
layer `ScaffoldGraph_ChainShape`. Stage B: a zigzag Chain is one chord run
only for a use where it is one surface line (G0 v1.8 DD-30); on buildings
jogs 25 -> 15. Contract and stages:
`docs/architecture/chain_shape_contract_draft.md`.

Autonomous mode since 2026-11-13 (plan decision 14): the goal is a result
structurally similar to the CFTUV reference scene (Arc, building_walls,
collumn, Main_wall); the agent merges its own slices after tests, Tier 3
and the reviewer gate, and may amend G0, Layer 5 and open Layer 4 when a
similar result needs it. The user comes back only to check, so every
slice must leave something he can look at.

Slice X (G0 v1.9 DD-49): in an island without a rigid frame the axes come
from Layer 3 `RunCornerRelation` RIGHT corners on a patch's own surface, no
longer from 3D perpendicularity at nodes. It repaired the arch regression of
Stage B (arch pins 39 -> 67, conflicts 11 -> 0).

Parity scoreboard: `dev/tools/cftuv_parity/` (reference UVs, captures,
`parity.py`, README). Line recall after Slice X: Arc 67%, building_walls
97%, collumn 0%, Main_wall 54%. The plan section "Reference scene and the
parity scoreboard" says what each gap is. Next subject: a strip feature
(Layer 4, opening allowed by decision 14) for the arch front face and the
column body; Main_wall (slit seams inside a patch) is left for last.

Parked: Slice V (seam turns, island orientation) on the local branch
`claude/slice-v-seam-turns`, commit 99db1a4, on the user's machine and not
pushed. It lacks docs and the reviewer gate. Measured: seams with the hinge
on one axis in both islands 597 -> 776 of 2246.

Findings to keep:

- The arch `Decor_Roof_Left_lod00.003` (`E:\temp\buildings3_3.blend`,
  capture `artist_arch_bevel.json`): CFTUV structures all 5 patches,
  Scaffold solved 1. The front face is a flat ring: its arcs are curves on
  that surface and lines on the rims. Without Straighten Strips CFTUV pins
  one V chain there and Blender's unwrap does the rest (user statement).
- The CFTUV add-on installed in the user's Blender 4.3 is not the copy in
  `dev/tools/CFTUV`: it has no `solve_skeleton.py` (P7 global solve). The
  algorithm cards in `docs/migration/` describe the repo copy.
- Branch rails: the 4 unordered island rails are forks (a line along a
  stitched hinge that parts into two continuations); two of the three
  distinct cases are an unwelded corner. Any ordering rule needs a DD-46 or
  DD-47 amendment and changes no solve today. Left as is.
- OBLIQUE on buildings (104 distinct of 194): about 29 real slants, 27 from
  the AXIS_A seed choice in four islands, 7 stepped chains (Stage B), 40
  small drift. No gradual arcs on those meshes; arches appear in decor
  meshes such as the one above.

Grease Pencil rendering consumes the pipeline inspection overlay payload instead
of duplicating core graph logic. Do not import Blender into Scaffold Core.

---

## Agent safety rules

- Do not create future phase directories.
- Do not create the deferred `scaffold/` add-on wrapper during G3.
- Do not add `utils.py`, `helpers.py`, `manager.py`, `service.py`, `factory.py`, `registry.py`.
- Do not put Feature, runtime solve, pin or UV facts in Layer 3.
- Do not feed WorldOrientation labels into base Alignment.
- Do not use WORLD_UP in AlignmentClass, PatchAxes, endpoint relations,
  LoopCorner or ScaffoldNode.
- Do not import higher layers from lower layers.
- Do not import `pipeline.passes` or `pipeline.validator` from layer code.
- Do not touch `G0.md` unless the task is explicitly an architecture amendment.
- For bug fixes, use Minimal Patch Protocol.

---

## How to verify

Run from the repository root (fresh cloud containers need
`python -m pip install pytest` first). This collects `scaffold_core/tests` and
the pure overlay tests in `dev/tools/scaffold_graph_debug`, which consume
Layer 3 rails and need no Blender; running only `scaffold_core/tests` misses
them:

```bash
python -m pytest
```

Tier 3, only when a slice touches Blender boundaries or real-mesh behavior
(Blender 4.5 headless, see `dev/tools/blender_smoke/README.md`; the user's
local copy of the artist file is `E:\buildings.blend`, and the runner also
finds Blender under `C:/Program Files/Blender Foundation/`):

```bash
python dev/tools/blender_smoke/run_smoke.py <buildings.blend> --seamed --write-uv \
  --baseline dev/tools/blender_smoke/baselines/buildings_seamed.json
```

Architectural tests to keep green:

```text
scaffold_core/tests/test_forbidden_imports.py
scaffold_core/tests/test_module_docstrings.py
```
