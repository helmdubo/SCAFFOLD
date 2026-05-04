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
| `ScaffoldJunction` | Implemented SELF_SEAM/CROSS_PATCH graph-level classification overlay on existing ScaffoldNode, not a separate graph node identity. |
| `AlignmentClass` | Implemented Layer 3 direction-family grouping over PatchChainDirectionalEvidence. |
| `PatchAxes` | Implemented Layer 3 primary/secondary AlignmentClass selection per Patch. |

Implementation status:
Code has already adopted canonical terms for PatchChain, PatchChainEndpointSample,
PatchChainEndpointRelation, LocalFaceFanGeometryFacts, LoopCorner and ScaffoldNode.
No code rename is required as part of this documentation cleanup.

### Future / reserved nomenclature, not implemented yet

| Term | Meaning |
|---|---|
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
BoundaryLoop. A LoopCorner may feed ScaffoldNode evidence. ScaffoldJunction is
a graph-level classification overlay on existing ScaffoldNode, not a separate
graph node identity. Ordinary ScaffoldNodes remain unclassified unless a
ScaffoldJunction classifier emits a record.

Implemented ScaffoldJunctionKind vocabulary includes SELF_SEAM and CROSS_PATCH.
SELF_SEAM is for a ScaffoldNode where two incident final PatchChains share the
same ChainId and same PatchId, representing the supported SEAM_SELF case.
CROSS_PATCH is for an existing ScaffoldNode whose incident final ScaffoldEdges
reference more than one distinct PatchId. Future kind vocabulary beyond
SELF_SEAM/CROSS_PATCH includes BRANCH, TERMINUS, BORDER_TERMINUS, AMBIGUOUS
and DEGRADED.

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
ScaffoldJunction classification must not change ScaffoldNode grouping, change
PatchChain identity, walk traces, detect circuits, select rails, choose
continuations or introduce UV, runtime or feature semantics.

## DD-39 - ScaffoldNodeIncidentEdgeRelation v1 is all-pairs evidence

Implemented ScaffoldNodeIncidentEdgeRelation v1 is a complete unordered all-pairs
Layer 3 relation over incident ScaffoldEdge endpoint occurrences at one
existing ScaffoldNode. For n incident edge-end occurrences at one ScaffoldNode,
v1 emits C(n,2) relations.

Emission is graph-structural. Missing PatchChainEndpointSample or
PatchChainEndpointRelation evidence must not cause an edge-end pair to
disappear. When endpoint evidence is missing, the pair remains present and is
classified with missing or degraded evidence quality.

Classification is evidence-backed. It may use tangent direction evidence,
owner normal evidence, direction_dot, normal_dot, endpoint sample ids,
PatchChainEndpointRelation id when available, confidence and evidence quality.
It is evidence only. It must not select trace paths, circuits, rails,
continuations, UV behavior or runtime behavior.

Implemented v1 relation kinds:
- STRAIGHT_CONTINUATION_CANDIDATE: opposite tangent/chord evidence;
  compatible owner-normal proof may be absent or weak.
- SURFACE_CONTINUATION_CANDIDATE: continuation candidate with compatible owner
  normals for opposite-tangent or straight-ish surface continuation.
- CROSS_SURFACE_CONNECTOR: tangent may align or connect, but owner normals
  diverge strongly.
- ORTHOGONAL_CORNER: tangent evidence is orthogonal.
- OBLIQUE_CONNECTOR: tangent evidence is neither collinear nor orthogonal.
- SAME_RAY_AMBIGUOUS: endpoint tangents point in the same ray direction away
  from the node.
- MISSING_ENDPOINT_EVIDENCE: the edge-end pair exists but endpoint
  sample/relation evidence is absent.
- DEGRADED: tangent, normal, confidence or evidence is zero, unknown or
  collapsed.

- SURFACE_SLIDING_CONTINUATION_CANDIDATE: node-local relation between two
  existing ScaffoldEdge endpoint occurrences whose local tangent/chord
  classification may otherwise look orthogonal or same-ray, but explicit
  same-side-surface evidence plus compatible local owner normals support
  continuation along the same curved or side surface. It is not a trace path
  choice, not a selected next edge, not a rail/circuit decision and not a UV
  direction.

SURFACE_SLIDING_CONTINUATION_CANDIDATE requires local owner-normal evidence,
compatible local owner normals and explicit same-side-surface evidence.
Current SideSurfaceContinuityEvidence v1 is consumed as this explicit
same-side-surface evidence source and includes the direction/flow-family
compatibility gate before this evidence may promote a pair to
SURFACE_SLIDING_CONTINUATION_CANDIDATE. Same patch, same loop,
END -> START adjacency and compatible local normals are not sufficient by
themselves under v1. Missing, degraded or direction-family-incompatible evidence
must not produce this kind under v1. SharedChainPatchChainRelation alone must
not produce this kind. Cross-patch cap, corner and shared-boundary cases must
remain non-propagating unless same-side-surface and direction/flow-family
evidence is explicit and safe under v1.

ScaffoldNodeIncidentEdgeRelation v1 must not change ScaffoldNode grouping,
ScaffoldEdge identity, PatchChain identity, Chain identity, Vertex identity or
BoundaryLoop identity. It must not use H/V, U/V, WORLD_UP, WorldOrientation,
Feature, API, UI, runtime solve or UV transfer.

Examples:
- Tube without caps split by multiple seam chains: top border PatchChains may
  become SURFACE_SLIDING_CONTINUATION_CANDIDATE through seam nodes when
  explicit same-side-surface evidence, compatible local owner normals and
  compatible direction/flow-family evidence prove curved side-surface
  continuation. The expected continuity result is two side families rather than
  four singleton side boundary edges.
- Tube with cap patch: side-to-cap PatchChains may be shared/cross-patch
  neighbors, but they are not side-surface continuation when owner normals
  diverge.
- Folded 90 seam, cube-like corner and cap-cross-surface cases remain
  non-propagating unless explicit same-side-surface evidence is safe.
- Local D:\cylinder.blend is an exploratory smoke fixture, not the canonical
  synthetic fixture for this contract.

## DD-40 - ScaffoldContinuityComponent v0 component coloring is not relation-kind coloring

Implemented ScaffoldContinuityComponent v0 is a Layer 3 derived evidence view over
existing ScaffoldEdges and existing ScaffoldNodeIncidentEdgeRelation records. It
groups ScaffoldEdges into continuity families using continuation-compatible
incident relations.

Continuity components are family memberships, while incident relation kinds are
local pair classifications. Debug coloring must therefore represent
continuity_component_id, not relation kind. Relation kind remains a separate
visual channel such as marker, glyph, label, dash or warning outline. Component
colors must be deterministic pseudo-random and stable by component id, never
true random.

Default propagation policy:
- SURFACE_CONTINUATION_CANDIDATE propagates continuity.
- SURFACE_SLIDING_CONTINUATION_CANDIDATE propagates continuity by default.
- SideSurfaceContinuityEvidence must not propagate continuity directly; current
  v1 may affect continuity only through a
  SURFACE_SLIDING_CONTINUATION_CANDIDATE relation.
- SurfaceFlowCompatibilityEvidence must not propagate continuity directly;
  once implemented it may affect continuity only through a
  SURFACE_SLIDING_CONTINUATION_CANDIDATE relation.
- STRAIGHT_CONTINUATION_CANDIDATE is weak evidence and does not propagate by
  default in v0.
- ORTHOGONAL_CORNER, OBLIQUE_CONNECTOR, CROSS_SURFACE_CONNECTOR,
  SAME_RAY_AMBIGUOUS, MISSING_ENDPOINT_EVIDENCE and DEGRADED do not propagate.
- SAME_RAY_AMBIGUOUS must mark ambiguity.

Every ScaffoldEdge belongs to exactly one continuity component, including
singleton components. If multiple continuation-compatible candidates meet at
the same ScaffoldNode, the component may be marked ambiguous; v0 must preserve
that ambiguity and must not choose one continuation target. It is not a trace,
path choice, rail, circuit, UV direction, runtime behavior or replacement for
ScaffoldEdge or PatchChain identity, and it must not introduce H/V, U/V,
WORLD_UP, WorldOrientation, Feature, API, UI, runtime solve or UV transfer.

## DD-41 - SideSurfaceContinuityEvidence v1 direction-family gate contract

Implemented SideSurfaceContinuityEvidence v1 is a Layer 3 derived evidence
record over two existing ScaffoldEdge endpoint occurrences at one existing
ScaffoldNode. It proves both candidate same-side surface flow within one patch
boundary loop and compatible direction/flow families.

It is evidence only. It is not a trace path choice, not a selected next edge,
not a rail, not a circuit, not a UV direction, not a feature and not runtime
solve behavior.

Required v1 evidence:
- same ScaffoldNodeId;
- same PatchId;
- same LoopId;
- different ChainId;
- both ScaffoldEdge endpoint occurrence roles are explicit and
  serialized/traceable;
- same materialized/source vertex at the node;
- endpoint roles form ordered local adjacency END -> START;
- both endpoint samples exist;
- both owner normals use LOCAL_FACE_FAN_NORMAL;
- normal_dot is greater than or equal to the ScaffoldNodeIncidentEdgeRelation
  compatible-normal threshold source, currently COMPATIBLE_NORMAL_MIN_DOT in
  scaffold_core/layer_3_relations/scaffold_graph_relations.py;
- when both PatchChains have AlignmentClass or direction-family evidence, the
  direction/flow families are compatible;
- if direction-family evidence is missing, ORTHOGONAL_CORNER promotion must be
  conservative and must not emit SideSurfaceContinuityEvidence;
- SAME_RAY_AMBIGUOUS remains conservative unless direction-family compatibility
  is explicit;
- neither endpoint evidence is missing or degraded.

Explicit non-evidence:
- same-chain pairs;
- cross-patch pairs;
- different-loop pairs;
- shared-chain-only pairs;
- cap, corner or cross-surface pairs without explicit same-side evidence;
- ORTHOGONAL_CORNER pairs crossing different AlignmentClass families;
- same-patch same-loop END -> START compatible-normal pairs without compatible
  direction/flow-family evidence;
- missing or degraded endpoint or normal evidence.

Implemented v1 consumption rule:
- SURFACE_SLIDING_CONTINUATION_CANDIDATE may consume
  SideSurfaceContinuityEvidence v1 as its same-side-surface evidence source.
- ScaffoldContinuityComponent v0 may continue propagating only through
  SURFACE_SLIDING_CONTINUATION_CANDIDATE.
- ScaffoldContinuityComponent v0 must not propagate directly through
  SideSurfaceContinuityEvidence.

Fixture expectation:
- Local D:\cylinder.blend / Cube.001 remains exploratory, not canonical
  acceptance. Wrong merges P1C1->P1C2, P1C2->P1C3, P2C3->P2C0 and P2C2->P2C3
  are examples of ORTHOGONAL_CORNER pairs crossing alignment:0 <-> alignment:1
  and must be blocked by v1 rather than promoted to
  SURFACE_SLIDING_CONTINUATION_CANDIDATE.
- Missing lower-side cross-patch or same-chain lower-ring flow is deferred and
  unresolved. It requires a separate evidence contract if needed later.

## DD-42 - SurfaceFlowCompatibilityEvidence v0 is planned cross-patch flow evidence

Approved/planned SurfaceFlowCompatibilityEvidence v0 is a Layer 3 derived
evidence record over two existing ScaffoldEdge endpoint occurrences or
edge-pair occurrences across compatible patches. It means the two PatchChains
are compatible members of the same surface-flow family across patch boundaries.

It is evidence only. It is not a trace path choice, not a selected next edge,
not a rail, not a circuit, not a UV direction, not a feature and not runtime
solve behavior. It does not replace ScaffoldEdge, PatchChain, Chain, Vertex or
Patch identity and must not introduce H/V, U/V, WORLD_UP, WorldOrientation,
Feature, API, UI, runtime solve or UV transfer.

SurfaceFlowCompatibilityEvidence is separate from SideSurfaceContinuityEvidence.
SideSurfaceContinuityEvidence handles same-patch, same-loop local side flow.
SurfaceFlowCompatibilityEvidence handles cross-patch flow-family compatibility.

Planned v0 rule A - ring flow without shared-chain relation:
- current ScaffoldNodeIncidentEdgeRelation kind is SAME_RAY_AMBIGUOUS;
- endpoint samples are present;
- same AlignmentClass/direction-family;
- same PatchAxes role where available;
- both participating patches are compatible side/dual-axis patches, not
  cap-like single-axis patches;
- no SharedChainPatchChainRelation exists for the pair;
- the pair is not in the same patch;
- evidence is not missing or degraded.

Planned rule A Cube.001 examples:
- positive: P1C1/P2C0 and P1C3/P2C2;
- negative: P0C1/P1C1 and P0C0/P2C0.

Planned v0 rule B - side-side seam flow through shared chain:
- SharedChainPatchChainRelation exists for the pair;
- both patches are compatible side/dual-axis patches with matching PatchAxes
  structure;
- same AlignmentClass/direction-family;
- same PatchAxes role where available;
- no cap-like single-axis patch participates;
- evidence is not missing or degraded unless a future edge-level fallback is
  explicitly approved.

Planned rule B Cube.001 examples:
- positive: P1C2/P2C3;
- negative: P0C0/P2C0 and P0C1/P1C1.

Explicit v0 non-goals:
- do not solve P1C0/P2C1 while endpoint evidence is missing;
- do not add an edge-level fallback for missing endpoint samples;
- do not allow direct ScaffoldContinuityComponent propagation through
  SurfaceFlowCompatibilityEvidence;
- do not reintroduce same-loop alignment:0 <-> alignment:1 false merges;
- do not implement ScaffoldTrace, ScaffoldCircuit or ScaffoldRail.

Planned v0 consumption rule:
- SURFACE_SLIDING_CONTINUATION_CANDIDATE may consume
  SurfaceFlowCompatibilityEvidence as an additional same-flow evidence source
  once SurfaceFlowCompatibilityEvidence is implemented.
- ScaffoldContinuityComponent v0 may continue propagating only through
  SURFACE_*_CONTINUATION_CANDIDATE relation kinds.
- ScaffoldContinuityComponent v0 must not propagate directly through
  SurfaceFlowCompatibilityEvidence.

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

- **OQ-11 - Geometry-based Chain / PatchChain refinement policy.** Status: partially resolved. Final PatchChain is the public source of truth; raw boundary elements are builder internals; Layer 3 may derive directional evidence from final PatchChains; polygonal straight/turning Chains can be described by ChainDirectionalRun / PatchChain directional evidence; directional evidence must not become a competing PatchChain identity; ScaffoldNode may group materialized Vertex occurrences as graph-level evidence but not Layer 1 identity; implemented ScaffoldNodeIncidentEdgeRelation v1 is all-pairs graph evidence over existing ScaffoldNode incident edge-end occurrences and must not choose traces, circuits, rails or continuations; implemented ScaffoldContinuityComponent v0 may group existing ScaffoldEdges into continuity-family evidence without choosing trace, circuit, rail or continuation targets; implemented SURFACE_SLIDING_CONTINUATION_CANDIDATE is conservative curved/side-surface continuation evidence and must not choose traces, circuits, rails or continuation targets; implemented SideSurfaceContinuityEvidence v1 is evidence-only same-patch same-loop side-surface flow input for sliding, requires compatible direction/flow-family evidence, and must not propagate continuity directly; approved/planned SurfaceFlowCompatibilityEvidence v0 is evidence-only cross-patch flow-family compatibility, is not implemented, may later be consumed by SURFACE_SLIDING_CONTINUATION_CANDIDATE, and must not propagate continuity directly; missing endpoint fallback for lower-side cross-patch or same-chain lower-ring flow remains unresolved and requires a separate evidence contract if needed later. Curved-chain policy, sawtooth tuning, user split marks, closed-loop wrap merge policy, advanced corner detection, local face-fan refinement policy and trace/circuit/rail construction over ScaffoldGraph remain unresolved. See `G0.md` Section 6.
