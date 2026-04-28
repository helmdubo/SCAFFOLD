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
- LocalFaceFanGeometryFacts

Not implemented:

- ScaffoldNode
- ScaffoldJunction
- ScaffoldEdge
- ScaffoldGraph
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
  future graph-level node assembled from LoopCorners and endpoint evidence.

ScaffoldJunction:
  future ScaffoldNode classification for branch/seam/cross-patch structures.

ScaffoldEdge:
  future graph-level view of a final PatchChain.

ScaffoldTrace:
  future connected sequence of ScaffoldEdges through ScaffoldNodes.

ScaffoldCircuit:
  future closed ScaffoldTrace.

ScaffoldRail:
  future direction-stable ScaffoldTrace usable as a conditional axis.
```

Future terms reserve naming and constraints only. They must not be implemented
during documentation cleanup or unrelated G3 work.

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

PatchChains:
  1. seam side A
  2. cap / border ring A
  3. seam side B
  4. cap / border ring B

LocalFaceFanGeometryFacts:
  many per mesh
  not ScaffoldJunctions
  not expected to be 2

Future ScaffoldJunction:
  likely two seam endpoint groups

Future ScaffoldCircuit:
  likely two cap / border circuits
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
```

PatchChainEndpointRelation classifies local endpoint pairs as:

```text
CONTINUATION_CANDIDATE
CORNER_CONNECTOR
OBLIQUE_CONNECTOR
AMBIGUOUS
DEGENERATE
```

LoopCorner is patch-local. ScaffoldNode is graph-level. ScaffoldJunction is a
ScaffoldNode kind, not every corner.

Do not use U/V labels, H/V labels, WORLD_UP, WorldOrientation or runtime solve
in Layer 3 AlignmentClass, PatchAxes, endpoint relations or LoopCorner.
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

Still unresolved:

- curved-chain policy;
- sawtooth tuning;
- user split marks;
- closed-loop wrap merge policy;
- advanced corner detection;
- local face-fan refinement policy;
- exact relationship between endpoint relations and ScaffoldGraph construction.

---

## Recommended next task

Review full inspection JSON for PatchChainEndpointRelations and LoopCorners.

Goal:
Validate that final PatchChains, LoopCorners and endpoint relations look stable
on cylinder, cube and L-shape fixtures before starting ScaffoldNode.

After that:
ScaffoldNode v0.

---

## Agent safety rules

- Do not create future phase directories.
- Do not create the deferred `scaffold/` add-on wrapper during G3.
- Do not add `utils.py`, `helpers.py`, `manager.py`, `service.py`, `factory.py`, `registry.py`.
- Do not put Feature, runtime solve, pin or UV facts in Layer 3.
- Do not feed WorldOrientation labels into base Alignment.
- Do not use WORLD_UP in AlignmentClass, PatchAxes or endpoint relations.
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
