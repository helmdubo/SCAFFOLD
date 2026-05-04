# Agent Handoff - Scaffold Core

This file is the continuity document for independent AI agents.

Read this after `AGENTS.md` and before changing code.

---

## Current state

```text
Project: Scaffold
Core package: scaffold_core/
Current phase: G3 - Derived Relations
Architecture: immutable B-rep-inspired interpretation pipeline
G0 contract: v1.2
```

Scaffold Core currently contains Layers 0-3 plus pipeline diagnostics and tests.
Future layers and wrappers are intentionally not created yet:

```text
scaffold_core/layer_4_features/
scaffold_core/layer_5_runtime/
scaffold_core/api/
scaffold_core/ui/
scaffold/
```

Do not create them during G3.

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
3. `docs/phases/G3_derived_relations.md`
4. `docs/architecture/G0_full.md`
5. `docs/architecture/design_decisions.md`
6. `docs/agent_rules/import_boundaries.md`
7. `docs/agent_rules/anti_overengineering.md`
8. `docs/agent_rules/testing_rules.md`
9. `docs/agent_rules/minimal_patch_protocol.md` if fixing existing code
10. `docs/agent_rules/codex_subagents.md` if using Codex subagents

Read `G0.md` when the task touches architecture or phase boundaries.

---

## Current G3 status

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

Planned/approved:

- ScaffoldContinuityComponent v0 derived evidence view over existing
  ScaffoldEdges and ScaffoldNodeIncidentEdgeRelation records

Not implemented:

- ScaffoldContinuityComponent v0 implementation
- ScaffoldJunction kinds beyond SELF_SEAM/CROSS_PATCH
- ScaffoldTrace
- ScaffoldCircuit
- ScaffoldRail
- WorldOrientation
- Layer 4 Feature Grammar
- Layer 5 Runtime/Solve
- UV transfer
- UI/add-on wrapper

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
  future connected sequence of ScaffoldEdges through ScaffoldNodes.

ScaffoldCircuit:
  future closed ScaffoldTrace.

ScaffoldRail:
  future direction-stable ScaffoldTrace usable as a conditional axis.

ScaffoldContinuityComponent:
  planned Layer 3 derived evidence view grouping existing ScaffoldEdges into
  continuity families from ScaffoldNodeIncidentEdgeRelation records.
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

This relation is evidence only. It must not choose traces, circuits, rails,
continuations, UV behavior or runtime behavior, and must not change
ScaffoldNode grouping or ScaffoldEdge, PatchChain, Chain, Vertex or
BoundaryLoop identity.

ScaffoldContinuityComponent v0 is the next planned implementation slice. It
should group ScaffoldEdges into continuity families using existing
ScaffoldNodeIncidentEdgeRelation records. Default propagation is limited to
SURFACE_CONTINUATION_CANDIDATE. STRAIGHT_CONTINUATION_CANDIDATE is weak
non-default evidence. ORTHOGONAL_CORNER, OBLIQUE_CONNECTOR,
CROSS_SURFACE_CONNECTOR, SAME_RAY_AMBIGUOUS, MISSING_ENDPOINT_EVIDENCE and
DEGRADED do not propagate; SAME_RAY_AMBIGUOUS must preserve ambiguity. Every
ScaffoldEdge belongs to exactly one component, including singletons, and
ambiguous component evidence must not choose one continuation target.

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
- trace/circuit/rail construction over ScaffoldGraph.

---

## Next architecture decision

Implement ScaffoldContinuityComponent v0 next as a Layer 3 evidence view over
existing ScaffoldEdges and ScaffoldNodeIncidentEdgeRelation records. Keep it
separate from ScaffoldTrace, ScaffoldCircuit and ScaffoldRail construction, and
do not choose continuation targets, UV directions or solve behavior.

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

Run:

```bash
python -m pytest scaffold_core/tests
```

Architectural tests to keep green:

```text
scaffold_core/tests/test_forbidden_imports.py
scaffold_core/tests/test_module_docstrings.py
```
