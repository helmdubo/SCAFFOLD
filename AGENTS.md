# AGENTS.md — Scaffold Core

Mandatory operating rules for AI agents working in this repository.

Scaffold Core is an immutable B-rep-inspired interpretation pipeline for topology-aware structural UV alignment.

This file is a router, not the full architecture.

Full architectural contract:

```text
G0.md
```

Machine routing index:

```text
docs/context_map.yaml
```

---

## Current phase

```text
G5a - Skeleton Runtime (docs/phases/G5a_skeleton_runtime.md)
G4a - Layer 4 v0, the strip feature (docs/phases/G4a_strip_feature.md),
opened by the user in autonomous mode (plan decision 14), plus the bevel
kinds BEVEL_STRIP / BEVEL_JUNCTION approved by the user (G0 DD-54).
The user-filter stage scaffold_core/user_filters/ (pass 3, G0 DD-55, plan
Slice AH), opened by the user's direction that quilts are joined by
structure and split only by user filters.
G3 relation contracts remain frozen per G0; relation changes still
follow G3 rules below.
```

Allowed during G5a:

```text
scaffold_core/core/
scaffold_core/layer_0_source/
scaffold_core/layer_1_topology/
scaffold_core/layer_2_geometry/
scaffold_core/layer_3_relations/
scaffold_core/layer_4_features/
scaffold_core/layer_5_runtime/
scaffold_core/user_filters/
scaffold_core/pipeline/
scaffold_core/tests/
```

Forbidden during G5a:

```text
scaffold_core/api/
scaffold_core/ui/
```

Layer 4 holds the strip feature (G0 DD-50) and the bevel kinds BEVEL_STRIP /
BEVEL_JUNCTION (G0 DD-54; a strip confirmed by the mark emits a
STRAIGHT_LADDER constraint unless both its rails are straight on its
surface); a further feature kind needs
the user's approval. Layer 5 may consume Layers 0-4 read-only and reads Layer 4
only through FeatureConstraint. The user-filter stage (G0 DD-55) runs between
Layer 4 and Layer 5; Layer 5 reads it only through SeamDirective. bpy is allowed ONLY in
scaffold_core/layer_5_runtime/uv_transfer.py (the G5 write boundary).

Do not create future-phase directories.

---

## Read-only architecture

`G0.md` is read-only for agents.

Agents may read it. Agents may not modify it.

If a task conflicts with G0, stop and report:

- the conflicting G0 section;
- why the task cannot be completed under current G0;
- what amendment would be required.

---

## Routing table

Before coding, read only the routed docs needed for the task.

| Task | Read |
|---|---|
| Any architecture question | `G0.md` |
| Active slice / Task Card roadmap | `docs/plans/uv_tracer_revision_plan.md` |
| Planning / Architect workflow | `docs/agent_rules/planning_workflow.md` |
| Codex workflow | `docs/agent_rules/codex_workflow.md` |
| Codex subagent workflow | `docs/agent_rules/codex_subagents.md` |
| Prompt templates | `docs/agent_rules/codex_prompt_library.md` |
| CFTUV migration / bridge | `docs/migration/cftuv_lessons.md` + `docs/migration/cftuv_bridge.md` |
| CFTUV parity fixtures | `docs/migration/cftuv_parity_fixtures.md` |
| G1 topology work | `docs/phases/G1_topology_snapshot.md` + `docs/layers/layer_1_topology.md` + `docs/architecture/segmentation_shell_policy.md` |
| G2 geometry facts | `docs/phases/G2_geometry_facts.md` + `G0.md` |
| G3 derived relations | `docs/phases/G3_derived_relations.md` + `G0.md` |
| Chain shape / line or curve per patch side | `docs/architecture/chain_shape_contract_draft.md` + `G0.md` DD-48 |
| G5a skeleton runtime / UV write | `docs/phases/G5a_skeleton_runtime.md` + `docs/agent_rules/blender_boundaries.md` |
| Layer 4 strip feature / FeatureConstraint | `docs/phases/G4a_strip_feature.md` + `G0.md` DD-50 |
| User filters / world vertical option / quilts / UV cut set | `docs/phases/G5a_skeleton_runtime.md` + `G0.md` DD-55 |
| CFTUV reference scene / parity scoreboard | `dev/tools/cftuv_parity/README.md` |
| Patch segmentation / shell detection | `docs/architecture/segmentation_shell_policy.md` |
| Source mesh snapshot | `docs/layers/layer_0_source.md` |
| Import rule / new file | `docs/agent_rules/import_boundaries.md` |
| Bug fix / regression | `docs/agent_rules/minimal_patch_protocol.md` |
| New test | `docs/agent_rules/testing_rules.md` |
| Blender IO | `docs/agent_rules/blender_boundaries.md` |
| File split / new abstraction | `docs/agent_rules/anti_overengineering.md` |
| Design decision lookup | `docs/architecture/design_decisions.md` |

---

## G1 segmentation rule

Patch segmentation is seam-only by default.

Patch flood fill is blocked by:

```text
mesh/selection border
non-manifold selected edge
explicit Scaffold boundary mark
Blender UV Seam
```

Blender Sharp is not a default Patch boundary source.

A future optional command may support `make seams by sharps`, but Sharp must not become a hidden default segmentation source.

---

## G2 geometry rule

Layer 2 stores raw measured geometry facts only.

Allowed G2 facts:

```text
area
normal
centroid
length
chord direction
vertex position
degenerate geometry diagnostics
chain plane, deviation from it and from the chord
per-side side faces and tilt of a chain plane against its own patch
patch area vector length (length of the sum of its triangle area vectors)
```

Forbidden in Layer 2:

```text
H_FRAME
V_FRAME
WALL
FLOOR
SLOPE
AlignmentClass
PatchAxes
WorldOrientation
DihedralKind
Feature
Pin
UV
```

Sawtooth/straightness work exists only as raw G2 geometry facts.

---

## G3 relations rule

Layer 3 stores derived relations over topology and geometry.
PatchQuadLadderRelation also reads the Layer 0 source face cycles (G0 DD-53).

## G3 relations status

Implemented in G3:

```text
PatchAdjacency
DihedralKind
RelationSnapshot
PatchChain incidence queries
conservative ChainContinuationRelation (TERMINUS/SPLIT)
ChainDirectionalRun
PatchChainDirectionalEvidence
AlignmentClass v0
PatchAxes v0
PatchChainEndpointSample
PatchChainEndpointRelation v0
LoopCorner v0
ScaffoldNode v0
ScaffoldEdge v0
ScaffoldGraph v0
ScaffoldJunction v0 SELF_SEAM/CROSS_PATCH classification overlay
LocalFaceFanGeometryFacts
ScaffoldNodeIncidentEdgeRelation v1 all-pairs edge-end occurrence matrix
ScaffoldContinuityComponent v0 derived evidence view over ScaffoldEdges
ScaffoldNodeIncidentEdgeRelationKind SURFACE_SLIDING_CONTINUATION_CANDIDATE v0
SideSurfaceContinuityEvidence v1 evidence-only same-side surface flow record with direction/flow-family gate
SurfaceFlowCompatibilityEvidence v0 evidence-only cross-patch flow-family compatibility record
ConnectedDirectionFamily v1 (G0 DD-43/DD-45) occurrence-aware geodesic families
RunEndpointJunction v0 (G0 DD-44)
ScaffoldTrace / ScaffoldRail v1 evidence views: station order and island cut view (G0 DD-46/DD-47; plan Slices J, O)
PatchChainShapeRelation v0 (G0 DD-48; plan Slice W Stages A, B) per-side chain shape: surface line, surface curve or unresolved; one reader, the per-use chord shortcut of directional runs (G0 DD-30)
RunCornerRelation v0 (G0 DD-49; plan Slice X) evidence: STRAIGHT / RIGHT / OTHER corner between two run ends on one patch surface; read by the Layer 5 frame-free axis bipartition and line orientation
RunBridgedCornerRelation v0 (G0 DD-52; plan Slice AD) evidence: a right corner turned over exactly one bridge run between two OTHER corners; read by the Layer 5 frame-free bipartition, line orientation and bridge equations
PatchQuadLadderRelation v0 (G0 DD-53; plan Slice AE-1) evidence: the zero, one or two quad-ladder readings of an all-quad patch (columns, rails, ends, profile lines), pure topology; read by the Layer 4 bevel rule
Direction conventions and the corner turn law (G0 DD-51; plan Slice AA): a use walks its loop as its faces wind, an evidence follows its use, a reflex face corner is measured as reflex
Layer 4 v0 (G0 DD-50; plan Slice Y): strip feature candidates, instances and the STRAIGHT_STRIP constraint behind the user option straighten_strips (off by default)
Layer 4 bevel kinds (G0 DD-54; plan Slices AE-2, AF): BEVEL_STRIP / BEVEL_JUNCTION records by the Layer 0 Blender Face Strength mark, or without it by a structural rule (candidates); a strip by mark emits a STRAIGHT_LADDER constraint behind straighten_bevel_strips (on by default), unless both its rails are straight on its surface (plan Slice AI: it unfolds straight as it is, an INFO diagnostic says so), and Layer 5 lays it from the constraint (frame LADDER) when it is an island by itself; the STRIP rule accepts only long sides that are not straight on the surface
User-filter stage (G0 DD-55; plan Slice AH): scaffold_core/user_filters/, pass 3 between Layer 4 and Layer 5; with the user option world_up (a direction in the mesh's own space; None by default, and then the stage emits nothing) each patch is HORIZONTAL or VERTICAL, and a seam gets a SeamDirective: SPLIT between the two classes, JOIN between a bevel by mark and a patch of its class. Layer 5 islands are quilts; island assembly reads only the SeamDirectives, and the solve states the UV cut set; uv_transfer.write_quilt_uvs lays each quilt as one chart by Blender's conformal unwrap and restores the user's seams. The vertical is not WorldOrientation and feeds nothing into Layers 1-4
Ladder strips in quilts (G0 DD-54; plan Slice AI): scaffold_core/layer_5_runtime/quilt_ladders.py; a STRAIGHT_LADDER strip in a quilt without a rigid frame is read when exactly one of its rails is stitched and the quilt already lays that rail on an axis: the free rail gives no length equations and each of its vertices takes the along-rail coordinate of its profile-line partner on the stitched rail. The ladder gives the quilt no axis. Every strip in a quilt gets an outcome; the unexpected ones are diagnostics (among them a strip whose quilt pins none of its vertices, and a strip outside its quilt's rigid frame). Layer 5 reads only the FeatureConstraint, the island's stitched Chains and the Layer 1 use-to-Chain mapping
```

SHARED_CHAIN family transport crosses only straight single-run hinges
(plan Slice L1). A family visits each patch at most once as one continuous
in-patch segment; merges that would revisit a patch are blocked, so opposite
sides of a patch never share a family (plan Slice L2). In-patch geodesic
continuation depends on the junction angle alone, and node crossings record
the hinge Chain through their node (plan Slice N, G0 v1.5). A node crossing
never folds back: after transport about the hinge its two runs leave the
node in opposite directions (plan Slice O1, G0 v1.6). Layer 5 takes its
island lines from the Layer 3 cut view of each family's rail by the island
(plan Slices O, Q); an island without a rigid frame takes its in-line run
signs from those rails. Known
deferred gap: a run transported through a 90-degree
corner ScaffoldNode may join an end patch's perimeter family; it is pinned by
a strict xfail and waits for a future patch-normal filter. Do not add
cap/wall patch semantics to fix it.

PatchChainShapeRelation v0 has one reader: directional runs take the chord
shortcut of a zigzag Chain per PatchChain use, only where the whole Chain is
one surface line on that side (plan Slice W Stage B, G0 DD-30). Nothing else
in Layer 3 or Layer 5 reads it. A curve record and a multi-segment line as
one run are later stages of `docs/architecture/chain_shape_contract_draft.md`.

Approved tracer spike home (consumer tooling, outside scaffold_core):

```text
dev/tools/tracer_spike/
```

The tracer spike consumes pipeline outputs like the debug addon. It must not
be imported by scaffold_core and must not move solve logic into the core.

Deferred in G3:

```text
ScaffoldJunction kinds beyond SELF_SEAM/CROSS_PATCH
ScaffoldCircuit
ScaffoldRail branch resolution
WorldOrientation
```

Forbidden during G3:

```text
Layer 4 Feature Grammar
Layer 5 Runtime/Solve
UV transfer
API
UI
Blender add-on wrapper
```

Layer 3 must not import or depend on Layer 4 features, Layer 5 runtime/solve,
UV transfer, API, UI or Blender modules.

ScaffoldNode v0 is graph-level evidence assembled from LoopCorners and endpoint
evidence. It is not Layer 1 identity and must not mutate Vertex, Chain or
PatchChain records.

ScaffoldJunction is a graph-level classification overlay on existing
ScaffoldNode, not a separate graph node identity. Ordinary ScaffoldNodes remain
unclassified unless a ScaffoldJunction classifier emits a record. SELF_SEAM v0
is implemented for the supported SEAM_SELF case where two incident final
PatchChains share the same ChainId and same PatchId. CROSS_PATCH v0 is
implemented where an existing ScaffoldNode's incident final ScaffoldEdges
reference more than one distinct PatchId. All other ScaffoldJunction kinds
remain future/deferred.

ScaffoldContinuityComponent v0 is implemented as a Layer 3 derived evidence
view over existing ScaffoldEdges and existing ScaffoldNodeIncidentEdgeRelation
records. It groups ScaffoldEdges into continuity families without replacing
ScaffoldEdge or PatchChain identity and without choosing traces, paths, rails,
circuits, UV direction or solve behavior. It must not introduce H/V, U/V,
WORLD_UP, WorldOrientation, Feature, API, UI or runtime semantics.

SURFACE_SLIDING_CONTINUATION_CANDIDATE is an implemented
ScaffoldNodeIncidentEdgeRelationKind. It is a
node-local relation between existing ScaffoldEdge endpoint occurrences for
curved/side-surface continuation with explicit same-side-surface evidence and
compatible local owner normals. It must not choose trace paths, next edges,
rails, circuits, UV direction or solve behavior.

SideSurfaceContinuityEvidence v1 is implemented as a Layer 3 derived evidence
record over two existing ScaffoldEdge endpoint
occurrences at one existing ScaffoldNode proving candidate same-side surface
flow within one patch boundary loop. It includes a direction/flow-family
compatibility gate. Same
patch, same loop, END -> START adjacency and compatible local normals are not
sufficient by themselves. ORTHOGONAL_CORNER pairs crossing different
AlignmentClass families must not emit SideSurfaceContinuityEvidence and must
not become SURFACE_SLIDING_CONTINUATION_CANDIDATE. If direction-family evidence
is missing, ORTHOGONAL_CORNER promotion stays conservative; SAME_RAY_AMBIGUOUS
stays conservative unless direction-family compatibility is explicit.
SURFACE_SLIDING_CONTINUATION_CANDIDATE consumes current v1 evidence as its
same-side-surface evidence source.
ScaffoldContinuityComponent v0 must not propagate directly through
SideSurfaceContinuityEvidence; it may continue propagating only through
SURFACE_SLIDING_CONTINUATION_CANDIDATE.

SurfaceFlowCompatibilityEvidence v0 is implemented. It is
a Layer 3 derived evidence record over two existing ScaffoldEdge endpoint
occurrences or edge-pair occurrences across compatible patches. It proves
cross-patch surface-flow family compatibility only. It is separate from
SideSurfaceContinuityEvidence, which handles same-patch/same-loop local side
flow. It is not a trace path choice, selected next edge, rail, circuit, UV
direction, feature, API, UI, runtime solve or WorldOrientation. Missing
endpoint fallback, including lower-side P1C0/P2C1-style flow, remains deferred
unless a future evidence contract explicitly approves it.
SURFACE_SLIDING_CONTINUATION_CANDIDATE may consume
SurfaceFlowCompatibilityEvidence as an additional same-flow evidence source.
ScaffoldContinuityComponent v0 must not propagate directly through
SurfaceFlowCompatibilityEvidence; it may continue propagating only through
SURFACE_*_CONTINUATION_CANDIDATE relation kinds.

Missing lower-side cross-patch or same-chain lower-ring flow remains deferred
and requires a separate evidence contract if needed later.

---

## Import rules

Allowed layer direction:

```text
Layer 0 → Layer 1 → Layer 2 → Layer 3 → Layer 4 → Layer 5
```

Lower layers must not import higher layers.

The user-filter stage `scaffold_core/user_filters/` sits between Layer 4 and
Layer 5. It imports `core`, `ids`, Layer 2 measures and the Layer 4 model,
never Layer 5. Layer 5 and `pipeline/` may import it; Layers 0-4 must not.

`pipeline/` may import layers.

Layers must not import:

```text
pipeline.passes
pipeline.validator
```

Limited exception: layer builders may type-import `pipeline.context.PipelineContext` if needed.

---

## Blender boundaries

Mesh read boundary:

```text
scaffold_core/layer_0_source/blender_io.py
```

UV write boundary, introduced only in G5:

```text
scaffold_core/layer_5_runtime/uv_transfer.py
```

Blender add-on UI code may import `bpy`, but it must not duplicate core logic.

---

## Anti-overengineering

Do not create:

```text
utils.py
helpers.py
common.py
manager.py
factory.py
service.py
registry.py
```

Do not add new top-level directories without architectural review.

Prefer frozen dataclasses and simple functions over service classes.

Split a file only when the rule in `docs/agent_rules/anti_overengineering.md` allows it.

---

## Minimal Patch Protocol

For bug fixes, regressions and small corrections:

- identify exact file/function/line range before editing;
- apply the smallest patch;
- do not refactor;
- do not rename;
- do not reformat unrelated code;
- separate `PATCH` from `NOTES`.

Full protocol:

```text
docs/agent_rules/minimal_patch_protocol.md
```

---

## Add-on metadata

Recommended Blender add-on metadata:

```python
bl_info = {
    "name": "Scaffold",
    "author": "...",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "category": "UV",
    "description": "Structural UV for architectural meshes",
    "location": "UV Editor > Sidebar > Scaffold",
}
```

`category = "UV"` is intentional.

---

## Final checklist

```text
[ ] I read the routed docs.
[ ] I stayed within current phase scope.
[ ] I did not create future-phase directories.
[ ] I did not introduce forbidden imports.
[ ] I did not add utils/helpers/managers/services.
[ ] I did not mutate lower-layer data from a higher layer.
[ ] I added or updated tests.
[ ] I did not reintroduce H/V or WALL/FLOOR/SLOPE as primary topology or geometry facts.
[ ] If this was a bug fix, I followed Minimal Patch Protocol.
```

When in doubt, choose the simpler structure.
