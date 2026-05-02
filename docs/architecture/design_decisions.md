# Design Decisions - Scaffold Core

This file mirrors the authoritative DD register in `G0.md`.

Agents may read this file for quick lookup. If it disagrees with `G0.md`, `G0.md` wins.

## Glossary

### Current / implemented or conceptually active

| Term | Meaning |
|---|---|
| `Chain` | Shared/logical boundary run referenced by one or more PatchChains. |
| `PatchChain` | Final patch-local oriented occurrence of a Chain in a BoundaryLoop. |
| `BoundaryLoop` | Final ordered sequence of PatchChains. |
| `LocalFaceFanGeometryFacts` | Local owner-normal geometry evidence; not graph topology. |
| `ChainDirectionalRun` | Direction-ready measured run derived from Chain geometry. |
| `PatchChainDirectionalEvidence` | Derived directional measurement for a PatchChain; not competing PatchChain identity. |
| `PatchChainEndpointSample` | Endpoint ray/evidence sample for a PatchChain directional measurement; not a graph node. |
| `PatchChainEndpointRelation` | Pairwise local relation between endpoint samples at one Vertex; not a graph node. |
| `LoopCorner` | Patch-local transition between adjacent PatchChains in one BoundaryLoop. |
| `ScaffoldNode` | Implemented G3c7 graph-level evidence node assembled from LoopCorners and endpoint evidence. It is not Layer 1 identity. |
| `ScaffoldEdge` | Implemented G3c8 graph-level view of one final PatchChain. |
| `ScaffoldGraph` | Implemented G3c8 connectivity graph assembled from ScaffoldNodes and ScaffoldEdges. |
| `AlignmentClass` | Implemented Layer 3 direction-family grouping over PatchChainDirectionalEvidence. |
| `PatchAxes` | Implemented Layer 3 primary/secondary AlignmentClass selection per Patch. |

Implementation status:
Code has already adopted canonical terms for PatchChain, PatchChainEndpointSample,
PatchChainEndpointRelation, LocalFaceFanGeometryFacts, LoopCorner and ScaffoldNode.
No code rename is required as part of this documentation cleanup.

### Future / reserved nomenclature, not implemented yet

| Term | Meaning |
|---|---|
| `ScaffoldJunction` | Future graph-level classification overlay on existing ScaffoldNode, not a separate graph node identity. |
| `ScaffoldTrace` | Future connected sequence of ScaffoldEdges through ScaffoldNodes. |
| `ScaffoldCircuit` | Future closed ScaffoldTrace. |
| `ScaffoldRail` | Future direction-stable ScaffoldTrace usable as a conditional axis. |
| `WorldOrientation` | Future/deferred parallel semantic overlay. |

Future terms reserve naming and constraints only. They must not be implemented
outside explicit phase work.

## Core decisions

- **DD-01 - Topology is immutable snapshot.** Scaffold Core does not mutate topology in place.
- **DD-02 - PatchChain is mandatory.** All oriented boundary use is represented through `PatchChain`.
- **DD-03 - Topology and geometry are separate.** Layer 1 stores incidence/orientation; Layer 2 stores measured geometry.
- **DD-04 - H/V is not a primary stored role.** H/V-like labels are derived runtime/debug labels.
- **DD-05 - WALL/FLOOR/SLOPE is not a primary patch type.** World-facing semantics are deferred semantic overlays, not Layer 1 facts.
- **DD-06 - Relations are derived caches with provenance.** Relations store confidence, evidence, source and snapshot context.
- **DD-07 - Alignment membership is per PatchChain.** A Chain may have multiple PatchChains with different AlignmentClass memberships.
- **DD-08 - Patch axes are derived from AlignmentClasses.** PatchAxes is Layer 3 classification, not solve output.
- **DD-09 - Continuation is a Layer 3 relation.** Old ContinuationEdge becomes ChainContinuationRelation.
- **DD-10 - Dihedral is a PatchAdjacency relation.** Signed dihedral references patch pair, shared Chain and both PatchChains.
- **DD-11 - WorldOrientation is a deferred derived relation namespace.** SurfaceRole, WorldEdgeKind and WorldCornerKind are future derived semantics.
- **DD-12 - Base WorldOrientation does not depend on Runtime/Solve.** Solve output must not redefine world semantics.
- **DD-13 - Alignment and PatchAxes do not use WorldOrientation.** AlignmentClass and PatchAxes consume patch-local directional evidence only. They must not use WORLD_UP vector bias, SurfaceRole labels or WorldOrientation labels.
- **DD-14 - Runtime solve consumes lower layers only.** Runtime solve must not discover or mutate topology, geometry or base relations.
- **DD-15 - Feature recognition returns candidates, not decisions.** Rules produce FeatureCandidates; resolver produces FeatureInstances.
- **DD-16 - Full rebuild is preferred in v1.** Correctness and debuggability beat incremental complexity.
- **DD-17 - User overrides are inputs, not topology mutations.** Overrides affect rebuild interpretation.
- **DD-18 - Skeleton solve supports optional FeatureConstraints.** FeatureConstraints are the Layer 4 to Layer 5 bridge.
- **DD-19 - Two-pass maximum in v1.** No iterative feature/solve convergence loop.
- **DD-20 - Suppressed candidates are retained.** Suppressed/rejected/weak candidates are inspectable diagnostics.
- **DD-21 - Detail generation is external.** Detail/decal/wear systems consume Scaffold APIs.
- **DD-22 - SEAM_SELF is first-class.** Two PatchChains of one Chain in one Patch is supported.
- **DD-23 - Architecture allows N AlignmentClasses per patch; v1 resolves at most two.** Non-orthogonal/curved/N-family cases are future work.
- **DD-24 - Direction clustering is conservative in v1.** Straight-like PatchChains only, chord direction only, fixed tolerance.
- **DD-25 - Layer 3 is frozen after Pass 1.** Pass 2 may consume Layer 3 but must not write to it.
- **DD-26 - FeatureConstraint is first-class.** FeatureConstraint is the only channel from accepted features into solve.
- **DD-27 - G1 Patch segmentation is seam-only by default.** Patch flood fill is blocked by border, non-manifold selected edge, explicit Scaffold boundary mark, and Blender UV Seam. Blender Sharp is not a default boundary source.
- **DD-28 - G1 Shell detection ignores Patch boundaries.** Shells are selected-face edge-connected components. Seams and explicit Patch boundaries may split Patches but do not split Shells. Vertex-only contact does not connect Shells.

## DD-29 - Chain coalescing is staged

Layer 1 materializes final PatchChains from raw boundary elements.

Raw boundary sides, atomic source edges, draft boundary runs and raw boundary
cycles are builder internals. They are not public model entities.

Boundary coalescing uses topology/materialization context only:
- boundary run kind;
- Patch context;
- seam/cut side;
- neighbour context;
- loop materialization.

Border runs may coalesce into ordered Chains when materialization policy
identifies them as one final PatchChain.

Reason:
Cylinder tube without caps + one seam cut showed that edge-atomic border Chains
prevent correct materialized BoundaryLoop construction. Border ring runs must
be allowed to coalesce into final PatchChains.

Geometry may later describe or classify a final PatchChain, but it must not
create a competing public PatchChain identity.

## DD-30 - Chain refinement does not change Layer 1 Chain identity

Layer 1 Chain identity is topology-only. Geometry-driven refinement lives in
Layer 3 and produces derived sub-chain entities or alignment groupings. It must
not split, rewrite, or re-id Layer 1 Chains.

## DD-31 - PatchChain endpoint relations are local and axis-free

PatchChain endpoint relations are Layer 3 derived relations between patch-local
`PatchChainDirectionalEvidence` endpoint samples at the same Vertex. They
classify local structural relations such as continuation candidate, corner
connector, oblique connector, ambiguous and degenerate. They must not use U/V
labels, H/V labels, WORLD_UP, WorldOrientation labels or runtime solve output.

## DD-32 - Surface normals for PatchChain are derived facts, not Layer 1 topology

Layer 1 `PatchChain` must not store face normals or averaged normals. Owner
normals used by endpoint relations are derived from Layer 2 geometry or Layer 3
evidence. LocalFaceFanGeometryFacts may provide local endpoint normals; Patch
aggregate normals are a fallback.

## DD-33 - ScaffoldGraph is derived from endpoint relations and LoopCorners

ScaffoldGraph is a Layer 3 derived structure built from
`PatchChainEndpointRelation`, `LoopCorner` and implemented `ScaffoldNode` evidence,
not from raw Chain or world axes. ScaffoldTrace remains deferred. ScaffoldEdge
is a graph-level view of final PatchChain, not a competing PatchChain identity.

## DD-34 - Final PatchChain is the single source of truth

BoundaryLoop contains final PatchChains. Raw boundary sides, atomic source edges
and draft runs are builder internals. ScaffoldGraph must use final PatchChains
as graph edges, not a parallel effective PatchChain layer.

## DD-35 - LoopCorner is patch-local; ScaffoldJunction is graph-level

LoopCorner is the local transition between adjacent PatchChains inside one
BoundaryLoop. A LoopCorner may feed ScaffoldNode evidence. ScaffoldJunction
remains a future graph-level classification overlay on existing ScaffoldNode,
not a separate graph node identity. Ordinary ScaffoldNodes remain unclassified
until a future ScaffoldJunction classifier exists.

Planning-only ScaffoldJunctionKind vocabulary includes SELF_SEAM, CROSS_PATCH,
BRANCH, TERMINUS, AMBIGUOUS and DEGRADED. SELF_SEAM is for a ScaffoldNode where
two incident final PatchChains share the same ChainId and same PatchId,
representing the supported SEAM_SELF case.

## DD-36 - LocalFaceFan is geometry evidence, not graph topology

LocalFaceFanGeometryFacts provides local normals for endpoint evidence. It is
not a ScaffoldNode and not a graph entity.

## DD-37 - Seam cuts may materialize duplicate topology Vertex occurrences

A seam cut may materialize multiple topology Vertex occurrences for one source
vertex.

One source vertex can appear on different sides of a materialized BoundaryLoop
or seam cut. These occurrences may receive distinct topology VertexIds while
retaining provenance to the same source vertex.

Reason:
Materialized UV-cut topology needs separate loop-side occurrences for the same
source vertex. This is required for correct BoundaryLoop traversal, PatchChain
construction, LoopCorner construction and ScaffoldNode grouping.

Implications:
- VertexId equality is topology-occurrence equality, not source-vertex equality.
- SourceVertexId equality is provenance equality.
- Public queries that need source-space grouping must explicitly group by SourceVertexId or structural provenance.
- ScaffoldNode construction may aggregate multiple materialized Vertex occurrences into one graph node.

## DD-38 - ScaffoldNode v0 is graph-level evidence, not Layer 1 identity

ScaffoldNode v0 is a Layer 3 derived relation record assembled from LoopCorner,
PatchChainEndpointSample and PatchChainEndpointRelation evidence.

Grouping policy v0:
- group materialized topology Vertex occurrences by SourceVertexId when provenance exists;
- fall back to topology VertexId grouping when no SourceVertexId provenance exists;
- retain evidence ids, incident PatchChain ids, Patch ids, confidence and provenance.

ScaffoldNode does not mutate, merge, split or replace Layer 1 Vertex, Chain,
PatchChain or BoundaryLoop identity. It does not classify ScaffoldJunctions.
ScaffoldEdge and ScaffoldGraph consume ScaffoldNode evidence in the implemented
G3c8 builder; ScaffoldTrace, ScaffoldCircuit and ScaffoldRail remain deferred.
Future ScaffoldJunction classification must not change ScaffoldNode grouping,
change PatchChain identity, walk traces, detect circuits, select rails, choose
continuations or introduce UV, runtime or feature semantics.

## PatchChain directional evidence

Final PatchChain remains the public source of truth.

Layer 3 may derive directional evidence from final PatchChains to support
alignment, endpoint samples and ScaffoldGraph construction.

Concepts:

```text
ChainDirectionalRun:
  Direction-ready measured run derived from Chain / PatchChain geometry.

PatchChainDirectionalEvidence:
  Patch-local directional evidence derived from final PatchChain.
  It may include source edges, segment indices, direction, length, confidence
  and provenance.
```

These are evidence/views over final PatchChain. They are not competing
PatchChain identities. ScaffoldEdges consume these facts only as evidence and
must not replace final PatchChains as graph source of truth.

## Future policy notes

A future optional command/flag may support:

```text
make seams by sharps
```

That future option should convert sharp information into seam/boundary input before segmentation. It must not make Sharp a hidden default segmentation source.

## Open questions

- **OQ-11 - Geometry-based Chain / PatchChain refinement policy.** Status: partially resolved. Final PatchChain is the public source of truth; raw boundary elements are builder internals; Layer 3 may derive directional evidence from final PatchChains; polygonal straight/turning Chains can be described by ChainDirectionalRun / PatchChain directional evidence; directional evidence must not become a competing PatchChain identity; ScaffoldNode may group materialized Vertex occurrences as graph-level evidence but not Layer 1 identity. Curved-chain policy, sawtooth tuning, user split marks, closed-loop wrap merge policy, advanced corner detection, local face-fan refinement policy and trace/circuit/rail construction over ScaffoldGraph remain unresolved. See `G0.md` Section 6.
