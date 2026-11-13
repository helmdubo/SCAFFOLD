# Agent Handoff - Scaffold Core

This file is the continuity document for independent AI agents.

Read this after `AGENTS.md` and before changing code.

---

## Current state

```text
Project: Scaffold
Core package: scaffold_core/
Current phase: G5a - Skeleton Runtime, plus G4a (Layer 4 v0, strip feature,
  and the bevel kinds BEVEL_STRIP / BEVEL_JUNCTION) and the user-filter
  stage scaffold_core/user_filters/ (pass 3, plan Slice AH)
Architecture: immutable B-rep-inspired interpretation pipeline
G0 contract: v1.16 (G0.md remains read-only for agents)
Branch: claude/scaffold-g5a-research-8a1f57; main has everything up to
  PR #40 (Slices AF and AG-1, G0 v1.15). Slice AH (commits 4e0c667,
  0b4006f, eb3d99c with the first review fixes, the second review's fixes
  and its docs, G0 v1.16) is on the branch and not merged yet.
Tests: 963 passed, 4 skipped, 1 xfailed (python -m pytest from the root).
```

Scaffold Core currently contains Layers 0-4, the user-filter stage, the G5a
Layer 5 runtime, pipeline diagnostics and tests. Public API and UI packages
remain deferred:

```text
scaffold_core/api/
scaffold_core/ui/
scaffold/
```

Do not create deferred phase directories during G5a. Layer 5 may consume
Layers 0-4 read-only (Layer 4 only through FeatureConstraint) and the
user-filter stage only through SeamDirective; relation contracts remain
frozen unless the task explicitly authorizes a G3 repair.

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
    of its own vertex occurrence in its own patch. `write_pinned_uvs`
    writes pins only; `write_quilt_uvs` (plan Slice AH) also lays each
    quilt as one chart by Blender's conformal unwrap and restores the
    user's seams.
- User-filter stage (`scaffold_core/user_filters/`, pass 3, G0 DD-55, plan
  Slice AH): with the user option `world_up` (a direction in the mesh's
  own space; None by default, then nothing is emitted) each patch is
  HORIZONTAL or VERTICAL and seams get SeamDirectives: SPLIT between the
  two classes, JOIN between a bevel by mark and a patch of its class.
  Layer 5 islands are quilts and read only the SeamDirectives; the solve
  states the UV cut set. The vertical is not WorldOrientation.
- Debug add-on `dev/tools/scaffold_graph_debug/` (plan Slice AC): Analyze
  runs Passes 0-3 (pass 3 since Slice AH) and the Layer 5 solve and draws fixed Grease Pencil
  layers from pipeline records only (patches, loops, chains per use by
  island axis, islands by frame kind, island lines, nodes, pins, stitch
  decisions, side shapes, corners, Layer 4 patch types); `Write UV (G5a)`
  and `Write UV and unwrap quilts` buttons, and the user-filter options
  (on, +Z, 45 degrees by default in the panel). It computes display offsets and nothing else: do not add
  derived structure to it, add a record to the core instead.
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
- RunBridgedCornerRelation v0 (`layer_3_relations/run_corners.py`, G0
  DD-52, plan Slice AD): a right corner turned over one bridge run (two
  consecutive OTHER corners whose turns add up to a right angle, e.g. a
  chamfered corner). A frame-free island reads it like a RIGHT corner
  and lays the bridge by one vector equation per axis.
- PatchQuadLadderRelation v0 (`layer_3_relations/quad_ladders.py`, G0
  DD-53, plan Slice AE-1): the ladder readings of an all-quad patch
  (columns, rails, ends, profile lines), pure topology. Layer 0 reads the
  raw Blender Face Strength mark per face.
- Layer 4 bevel kinds (`layer_4_features/build.py`, G0 DD-54, plan Slice
  AE-2): BEVEL_STRIP / BEVEL_JUNCTION records by the mark, or by a strict
  structural rule; records only. Test data with ground truth:
  `scaffold_core/tests/data/bevel_cases` (generator
  `dev/tools/blender_smoke/build_bevel_cases.py`).
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
- WorldOrientation (the world vertical of the user-filter stage is a user
  option, not WorldOrientation)
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

Slice Y (G0 v1.10 DD-50, `docs/phases/G4a_strip_feature.md`): Layer 4 v0
with one feature, STRIP. With the user option `straighten_strips` a
four-sided patch that is an island by itself is laid as a rectangle
through a STRAIGHT_STRIP FeatureConstraint; Layer 5 only applies the
constraint. Off by default; with it off nothing changes.

Parity scoreboard: `dev/tools/cftuv_parity/` (reference UVs, captures,
`parity.py`, README). Line recall after Slice Y: Arc 96%, building_walls
97%, collumn 51%, Main_wall 54%. `write_scaffold_layer.py` writes
Scaffold's result into a second UV layer of a copy of the reference scene
(the user's copy: `E:\temp\buildings3_3_scaffold.blend`).

Slice Z (Layer 5): pins are consistent and complete. Every equation group
of the axis solve has its own gauge; in a framed island all groups are
anchored to the frame, without a frame only the largest group is pinned;
an axis run pins its inner vertices at arc-length stations. Before it, 29%
of pinned nodes had arbitrary coordinates (hole loops), a defect older
than this session that no metric showed. LOOK at results: render the two
UV layers with `dev/tools/cftuv_parity/dump_layers.py` and
`render_layers.py` after `write_scaffold_layer.py`.

Slice AA (Layers 1, 2 and 5; G0 DD-51): direction conventions and the corner
turn law. Three lower-layer defects are fixed: the Layer 2 vertex run of a
one-edge Chain ran against the Chain for half of them, so evidence START/END
were not the loop direction; a reflex corner of an n-gon was measured as 90
degrees; a use of a closed Chain met by a seam got orientation +1 by default.
With them fixed, a law holds exactly on every solved island with a rigid
frame: walking the loop, a convex RIGHT corner turns left and a reflex one
right. Layer 5 now orients the lines of a frame-free island by that law
(`_orient_lines_by_corners`); the old rule compared raw 3D directions and
left unlinked lines with an arbitrary sign, which twisted Main_wall (14 of 40
pins) and mirrored three islands. The law is G5a invariant 9 and two Tier 3
metrics (`corners_against_law`, `mirrored_islands`). When a layout looks
twisted or mirrored, check this law first.

Open after Slice AA:

- Main_wall: the chamfered door notches are solved by Slice AD (bridged
  right corners): every OUTER run but the six chamfers has an axis, all
  66 reference pins are covered. 632 run ends on seam-cut mid-chain
  vertices (the slits of the window reveals) stay unpinned.
- `solve_axis` still normalizes equations between the same two cross
  components by a raw 3D dot; it flips nothing on the 25 captures now.
  `_segments_follow_chain` (Layer 2) and `_patch_chain_reverses_source_path`
  (Layer 3) compensated for the reversed runs and are trivial for open
  chains now.
- Island composition: Scaffold stitches walls across horizontal ledge
  patches, the CFTUV reference keeps them apart; a wall then comes out
  upside down against the rest. This is the user's grouping filter
  (decision 14), not built.
- Island orientation (what is up) is not built either; Slice V is parked.
- The column body is laid by arc length (2.88 m wide), the reference by
  the chord (about 0.83 m): the user's call.
- A strip stitched along a bent side is not straightened (Slice AB frees
  only a strip whose stitch candidates are all straight hinges).

Seen in the Slice AC debugger (state of the core, not fixed):

- Main_wall: all 1047 runs of the window holes are OBLIQUE (650 m). The
  holes are the glass outlines at the bottom of window reveals that lie
  in the facade's own patch; 56 of 78 are wrapped by non-developable
  reveal corners (holonomy up to 73 degrees), and no Layer 3 record ties
  a hole to the outer loop. The CFTUV reference pins none of them (all
  66 pins are on the outer loops); they come out straight from Blender's
  unwrap in both. User decision (2026-11-13): leave them out of the
  skeleton, as in the reference. Main_wall is the only frame-free
  island with holes on 52 captures; in rigid frames holes get axes and
  pins. Each unreached line now carries a diagnostic.
- A bent side of a strip is one island line per run (Arc's strip island
  has 29 lines, the column's strips 49 and 38): the skeleton has no
  entity for a curved side as a whole; the constraint's four sides are
  the only large structure of a strip.
- Patch types are what Layer 4 grades today: strip, rectangle,
  four-sided without a bent pair, and everything else. Trapezoid,
  L-shape and other kinds do not exist; a second feature kind needs the
  user's approval.

DIRECTION SET BY THE USER (2026-11-13), read before any work on islands:

- The large structures built from Chains exist so that what is stitched
  to what in UV is known at once, without growing a frontier step by
  step. By default everything connected is one quilt. Rules that split
  ("these are walls, that is a floor or a ceiling") belong to an over
  filter of user options, which puts patches into separate quilts.
- Today Layer 5 does the opposite: it stitches only seams that unfold
  without distortion (angle defect within 1e-3), so a bevel never joins
  its wall, and Slice AF even refuses every seam of a laid bevel strip.
  The user objected to the result (20 small islands on
  rounded_wall_noise_top). The "own island" rule of Slice AF is
  provisional. (Status after Slice AH: the over filter exists as pass 3;
  a ladder strip is an island by itself only when no seam of it is
  joined; see "After Slice AH" below.)
- Measured for this (scratch study, CFTUV frontier): CFTUV's quilts rest
  on the world vertical (same patch type only, H/V roles, FREE-FREE never
  attaches), it has no overlap check, and it looks joined in Blender only
  where both sides of a seam carry coincident pins, as in Scaffold. On
  rounded_wall_noise_top CFTUV itself gives 15 quilts; the user's
  reference UV (3 islands) is not CFTUV output. On that mesh the gate
  refuses 10 seams, on each the defect is spread over every vertex of the
  seam (bevel seams, 25 to 298 degrees in total).
- A band by shape (not by four uses, not by quads) was stated and checked:
  a one-loop patch whose loop, split at RIGHT corners and bridged right
  corners, has four sides, the two longer opposite sides both turning on
  the surface. It accepts the flat curved bottom f111, the bottom bevel
  strips and the column body, rejects the developable walls and every
  ordinary wall patch of four meshes. Laid by arc-length fraction at the
  mean of its two long sides it matches the reference f111 within 0.5%.
  Not built.

After Slice AF (bevel strip layout):

- A strip is laid with one width; where its width varies it is not
  isometric. Interior vertices of multi-segment strips are not pinned.
- A patch with fewer than two pins comes out of Blender's unwrap at an
  arbitrary scale: a patch with no pin is packed into the unit square, a
  patch with one pin keeps the area the layer had before. After Slice AF
  only the noisy top of rounded_wall_noise_top is left without pins; on
  collumn with strips off 74% of the area has none. Measured candidates:
  a two-pin anchor on the longest run (exact on developable patches,
  0.38 of the area on the noisy top), Blender's Average Islands Scale
  (moves pinned islands, up to 1.9 m), rescaling each unpinned chart to
  its 3D area after the unwrap (exact, but a step after Blender; the
  scene-writing script already does it for charts with no pin). Not
  decided.
- The STRIP rule counts a cornered or unresolved long side as not
  straight (the column body, three folded one-face strips on the
  buildings). Unchanged from before; the user was told and may change it.
- A STRIP patch whose only bent seam goes to a ladder patch does not leave
  its island although that seam is never stitched (no capture shows it).

After Slice AH (quilts, G0 v1.16 DD-55; plan entry Slice AH has the
numbers):

- The user's mesh with +Z: 3 quilts with the patch sets of the reference
  layout, 137 pins, 0 overlaps and 0 flipped faces after Blender's fill;
  the wall ring opens at f94|f211 (the reference at f94|f110, the same
  strip's other rail; no structural fact prefers one).
- Open defect, the proposed next slice: a ladder strip inside a quilt is
  not laid by its ladder. The STRAIGHT_LADDER constraint applies only
  when the strip is an island by itself. In a quilt its runs go through
  the frame-free line layout: the user's bottom quilt strip f36 is
  sheared (rails laid at their own lengths 6.86 and 6.97, cross edges of
  0.074 pinned 3% to 62% too long); the arch cases' strips have no pins
  and take their width from Blender's fill; d_cyl_s2 pins 64 -> 16.
  Adding the ladder's equations to the quilt solve was measured and
  rejected (one width and one length contradict the exact wall lengths;
  the wall quilt lost all pins). Proposal: the rail shared with a
  neighbour takes the neighbour's stations, the free rail copies them
  through the profile lines, the width comes from the ladder, no length
  equations of the strip's own.
- The "island by itself" sentences about ladder strips (G0 header, DD-50,
  DD-54, G4a) now say that they hold only without a JOIN.
- A frame-free quilt lays only the right-corner component that holds its
  longest line; other components stay without axes. The top quilt of the
  user's mesh has one line and no pins (a pin needs both axes).
- Equal-length rings of JOIN seams still open by id (g_short: ten seams of
  equal 3D length); harmless on symmetric meshes (cube, ring).
- Older than Slice AH, found by its study: with the filter off the island
  sets depend on vertex numbering on some meshes (b_rect_s2, b_ring_s1,
  f_rect_inarc, h_rect_s2_tri, m_rect_s2_trimain, several walls objects):
  the edge-count tie-break in the first two tree groups and the
  order-dependent overlap gate. 3D length everywhere would change the
  output without the filter and the Tier 3 baseline: a separate slice.
- Policies not decided by the user: a junction tie is HORIZONTAL; no
  usable normal is VERTICAL; arch soffits are HORIZONTAL and split from
  their walls; JOIN seams enter the tree after the other seams (the order
  "between rigid and other" was measured: no clear winner).
- Charts are not placed or packed; quilts overlap each other in UV.
- write_quilt_uvs: tested headless on Blender 4.5 and 4.3.2 (13 objects,
  no crash, 0 seam flags and 0 selection flags changed, also with partial
  selections and a forced unwrap failure); it refuses a hidden target,
  hidden solved faces and any other object in Edit Mode. Not tested in the
  interactive UI; undo not verified; the bmesh select history (the active
  element) not measured.
- The writer fixes of the second review (exact selection restore, the
  three refusals) have no test that the suite or Tier 3 can fail on. The
  smoke's selection check runs with every face selected, where nothing is
  flushed, so it passes with the restore removed. They were verified by
  the reviewer's Blender scripts (scratch `review_ah2`). To make the
  smoke effective, deselect part of the faces of one object before the
  quilt write and add a hidden-target and a hidden-face case.
- Nothing decides the orientation of a quilt in UV: on the user's mesh the
  wall quilt lies upside down against the reference (straight edge up,
  noisy edge down). A natural home is the user-filter stage, which owns
  the vertical.
- Older than Slice AH: Layer 2's absolute `EPSILON = 1e-9`
  (`layer_2_geometry/measures.py`) makes some lower-layer facts depend on
  mesh scale (at scale 0.001 the sliver face of g_short gets zero area and
  a zero normal), which changes the order of seams outside the JOIN group
  and the pins at that scale. The filter and the JOIN order themselves are
  scale-free (38 captures at 0.001 and 1000).
- Study of the user's "straighten shell" prototype (pure numpy UV relaxer
  outside the repo: rigid shape matching per polygon towards the flat 3D
  shape, plus straight-line constraints on tagged chains), fed with
  Scaffold's pins and lines: as a fill it beats Blender's conformal unwrap
  on a chart without pins (edge length error 6.5% -> 2.9%, area error
  11.3% -> 3.8%) and slightly on pinned charts. Its line constraints add
  nothing today (every vertex of every skeleton line is already pinned: 0
  unpinned on the user's pinned quilts and on the 297 quilts of `walls`).
  Straightening the other sides has no axis from structure (0 of 31
  pieces) and without one breaks the layout (edge error 40%, 13 flipped
  faces on the top quilt). Starting without Blender's unwrap works on two
  of three quilts. Conclusion: a candidate to replace Blender's fill;
  automatic straightening needs a Layer 4 kind ("band") that declares the
  axis. `scaffold_core` has no numpy; adopting it is a separate decision.

After Slice AG-1 (speed): the Layer 5 solve is now the largest cost (about
7 s on building_walls: overlap checks in island assembly, `_key` scans,
the dense solver, `_node_map`) and grows faster than linear. The study in
the scratch folder lists each spot with a one-line fix. The dead Layer 3
records (five sets, proven by execution on 38 captures) are not removed
yet; removing them needs G0 amendments (DD-07, 08, 09, 13, 23, 24, 31,
33, 39-42, 46, 47).

After Slices AE-1 and AE-2 (bevels):

- Wanted next by the user: filters that select bevel strips as
  horizontal, vertical, under a ceiling, outer or inner corner (decals).
  The world vertical is a user option of the filter, never an input of
  Layers 1-3. Since Slice AH the filter stage exists with one filter
  (vertical apart from horizontal, a bevel with its surfaces); the
  filters "under a ceiling", "outer corner" and "inner corner" are not
  built.
- The corner kind of a strip compares whole-patch normals (PatchAdjacency)
  and is MIXED or UNDEFINED beside a curved neighbour; a filter needs a
  local dihedral along the rail.
- "Band" as a patch kind for arcs, cables, caves and curved roads is a
  separate future kind, related to STRIP; the ladder relation serves it.
- The debugger draws the reading Layer 4 chose for a bevel strip and the
  first reading for any other ladder patch.

External audit (2026-11-13), the user's instruction: take what has real
architectural value, defer the rest. Decided:

- Do: remove Layer 3 records that nothing reads and the superlinear spot
  in pass 1 (measured on building_walls, 1429 faces: pass 1 takes 2.7 s;
  15433 ScaffoldNodeIncidentEdgeRelations take about a third of it and no
  code in Layers 4-5 reads them). The user agreed to remove unread G3
  records.
- Do: an order of failure in the axis solve: on contradictory equations
  drop the bridge equations first, not the whole island (a bridged corner
  93 degrees off a right angle takes an island from 7 pins to 0 today).
- Deferred: the `confidence` fields (1.0 everywhere, unused); a direction
  field inside one patch as Layer 3 evidence for frame-free islands; an
  own relaxation with slide-along-line constraints in place of point pins
  plus Blender's unwrap.
- Not taken: a cross-field / MIQ pipeline (it yields UV, not the structure
  records the user needs; the meshes average two faces per patch).

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
  LoopCorner or ScaffoldNode. The world vertical lives only in
  `scaffold_core/user_filters/` (a guard test checks it) and reaches
  Layer 5 only as SeamDirectives.
- Do not import higher layers from lower layers.
- Do not import `pipeline.passes` or `pipeline.validator` from layer code.
- Do not touch `G0.md` unless the task is explicitly an architecture amendment.
- For bug fixes, use Minimal Patch Protocol.

---

## How to verify

Run from the repository root (fresh cloud containers need
`python -m pip install pytest` first). This collects `scaffold_core/tests` and
the pure overlay tests in `dev/tools/scaffold_graph_debug`, which consume
the pipeline through the Layer 5 solve and need no Blender; running only
`scaffold_core/tests` misses them:

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
