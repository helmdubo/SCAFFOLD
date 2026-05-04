# G3 - Derived Relations

G3 derives relation snapshots from immutable topology and raw geometry facts.

## Scope

Allowed:

- Layers 0-2 as inputs
- Layer 3 - Derived Relations
- Pipeline relation-building integration
- Diagnostics and G3 synthetic tests

Forbidden in G3:

- Layer 4 Feature Grammar
- Layer 5 Runtime/Solve
- FeatureRule / FeatureCandidate / FeatureInstance / FeatureConstraint
- UV transfer
- Blender UI package

## G3 package tree

These core implementation directories are allowed in G3:

```text
scaffold_core/core/
scaffold_core/layer_0_source/
scaffold_core/layer_1_topology/
scaffold_core/layer_2_geometry/
scaffold_core/layer_3_relations/
scaffold_core/pipeline/
scaffold_core/tests/
```

Forbidden future directories:

```text
scaffold_core/layer_4_features/
scaffold_core/layer_5_runtime/
scaffold_core/api/
scaffold_core/ui/
```

## Layer 3 Relations

Implemented:

- G3a - PatchAdjacency / DihedralKind / RelationSnapshot
- G3b1 - PatchChain incidence queries
- G3b2 - conservative ChainContinuationRelation
- G3c0 - ChainDirectionalRun
- G3c1 - PatchChainDirectionalEvidence
- G3c2 - AlignmentClass v0
- G3c3 - PatchAxes v0
- G3c4 - PatchChainEndpointSample
- G3c5 - PatchChainEndpointRelation v0
- G3c6 - LoopCorner v0
- G3c7 - ScaffoldNode v0
- G3c8 - ScaffoldEdge v0 / ScaffoldGraph v0
- G3c9 - ScaffoldJunction v0 SELF_SEAM/CROSS_PATCH
- G3c10 - ScaffoldNodeIncidentEdgeRelation v1 all-pairs edge-end occurrence matrix
- G3c11 - ScaffoldContinuityComponent v0 derived evidence view
- LocalFaceFanGeometryFacts as Layer 2 geometry evidence consumed by Layer 3
- SURFACE_SLIDING_CONTINUATION_CANDIDATE as a conservative
  ScaffoldNodeIncidentEdgeRelationKind.
- SideSurfaceContinuityEvidence v0 as an evidence-only same-side surface flow
  record.

Validation status:

- ScaffoldGraph and ScaffoldJunction compact report expectations are captured
  for representative single patch, cylinder and shared-loop fixtures.
- ScaffoldContinuityComponent v0 tests cover propagation, non-propagation,
  ambiguity preservation, singleton components and inspection serialization.

Deferred:

- ScaffoldJunction kinds beyond SELF_SEAM/CROSS_PATCH
- SideSurfaceContinuityEvidence v1 direction/flow-family gate implementation
- ScaffoldTrace / ScaffoldCircuit / ScaffoldRail
- WorldOrientation
- Layer 4 Feature Grammar
- Layer 5 Runtime / Solve

## Terminology

Current terminology for the final boundary graph model:

| Term | Meaning |
|---|---|
| `PatchChain` | Final patch-local oriented occurrence of a Chain in a BoundaryLoop. |
| `PatchChainDirectionalEvidence` | Derived directional measurement for a PatchChain. |
| `PatchChainEndpointSample` | Endpoint ray/evidence sample for a PatchChain directional measurement. |
| `PatchChainEndpointRelation` | Pairwise local relation between endpoint samples at one Vertex. |
| `LocalFaceFanGeometryFacts` | Local owner-normal geometry evidence. |
| `LoopCorner` | Patch-local transition between adjacent PatchChains in one BoundaryLoop. |
| `ScaffoldNode` | Implemented G3c7 graph-level evidence node assembled from LoopCorners and endpoint evidence. It is not Layer 1 identity. |
| `ScaffoldEdge` | Implemented G3c8 graph-level view of one final PatchChain. |
| `ScaffoldGraph` | Implemented G3c8 connectivity graph assembled from ScaffoldNodes and ScaffoldEdges. |
| `ScaffoldJunction` | Implemented SELF_SEAM/CROSS_PATCH graph-level classification overlay on existing ScaffoldNode, not a separate graph node identity. |
| `ScaffoldContinuityComponent` | Implemented G3c11 derived evidence view grouping existing ScaffoldEdges into continuity families. |
| `SURFACE_SLIDING_CONTINUATION_CANDIDATE` | Implemented conservative ScaffoldNodeIncidentEdgeRelationKind for curved/side-surface continuation evidence. |
| `SideSurfaceContinuityEvidence` | Implemented v0 evidence-only same-side surface flow record over two existing ScaffoldEdge endpoint occurrences at one existing ScaffoldNode. Approved v1 direction/flow-family gate is documented but not yet implemented. |
| `ScaffoldTrace` | Future connected sequence of ScaffoldEdges through ScaffoldNodes. |
| `ScaffoldCircuit` | Future closed ScaffoldTrace. |
| `ScaffoldRail` | Future direction-stable ScaffoldTrace usable as a conditional axis. |

Endpoint samples, endpoint relations, LocalFaceFanGeometryFacts and ScaffoldNodes
are evidence or derived relation records; they are not Layer 1 topology.

ScaffoldJunction classification:

- ordinary ScaffoldNodes remain unclassified unless a ScaffoldJunction
  classifier emits a record;
- `SELF_SEAM` is an implemented ScaffoldJunctionKind for a ScaffoldNode where two
  incident final PatchChains share the same ChainId and same PatchId,
  representing the supported SEAM_SELF case;
- `CROSS_PATCH` is an implemented ScaffoldJunctionKind for an existing
  ScaffoldNode whose incident final ScaffoldEdges reference more than one
  distinct PatchId;
- deferred kind vocabulary after implemented SELF_SEAM/CROSS_PATCH may include
  `BRANCH`, `TERMINUS`, `BORDER_TERMINUS`, `AMBIGUOUS` and `DEGRADED`;
- classification must not change ScaffoldNode grouping, change
  PatchChain identity, walk traces, detect circuits, select rails, choose
  continuations or introduce UV, runtime or feature semantics.

## G3b1 PatchChain incidence

G3b1 implements PatchChain incidence queries as derived views over Vertex.
It does not introduce a ScaffoldJunction entity.
It does not implement disk-cycle ordering.
It does not implement ChainContinuationRelation.

## G3b2 — Conservative ChainContinuationRelation

Scope:
- Define continuation relations at topology vertices.
- Use G3b1 PatchChain incidence queries as input.
- Implement conservative TERMINUS / SPLIT first.
- SMOOTH / TURN are allowed only for trivial synthetic fixtures in Task E.
- Do not solve OQ-11.
- Do not create AlignmentClass.
- Do not create PatchAxes.
- Do not create WorldOrientation.
- Do not mutate or re-id Layer 1 Chains.

Concept:

```text
At this Vertex, does this PatchChain continue into another PatchChain?
```

Conservative kinds for Task E:

```text
TERMINUS:
  A PatchChain reaches a Vertex and has no safe continuation candidate.

SPLIT:
  A PatchChain reaches a Vertex and multiple continuation candidates exist,
  but G3b2 cannot choose one safely.

SMOOTH:
  Deferred by default.
  Task E may support only on trivial synthetic fixtures where geometry is unambiguous.

TURN:
  Deferred by default.
  Task E may support only on trivial synthetic fixtures where geometry is unambiguous.
```

G3b2 conservative implementation must prefer TERMINUS/SPLIT over false
SMOOTH/TURN.

Proposed future model contract for Task E:

```python
@dataclass(frozen=True)
class ChainContinuationRelation:
    vertex_id: VertexId
    source_patch_chain_id: PatchChainId
    target_patch_chain_id: PatchChainId | None
    kind: ContinuationKind
    confidence: float
    evidence: tuple[Evidence, ...] = ()
```

Notes:
- `target_patch_chain_id = None` for TERMINUS.
- SPLIT is represented as one relation from the source use with no selected
  target. Candidate count is retained in evidence.
- No ContinuationId is required in the first implementation.
- RelationSnapshot may store continuations as a tuple.

Acceptance for Task E:
1. Continuation relations derive from Layer 1 + Layer 2 + G3b1 incidence only.
2. TERMINUS is produced when no safe target exists.
3. SPLIT is produced when multiple candidates exist.
4. SMOOTH / TURN are absent or fixture-only.
5. No Layer 1 Chain identity changes.
6. No H/V, WALL/FLOOR/SLOPE, Feature, Runtime, UV, or Solve terms.
7. Tests cover simple terminus, ambiguous split, non-manifold ambiguity, and skipped full-continuation policy.

## G3c0 - Chain directional refinement view

G3c0 implements `ChainDirectionalRun` as a Layer 3 derived view from Layer 2
segment geometry.

Scope:
- Derive direction-ready runs from `ChainGeometryFacts.segments`.
- Preserve Layer 1 Chain identity.
- Emit one run for one-segment, `STRAIGHT`, or `SAWTOOTH_STRAIGHT` Chains.
- Split `UNKNOWN`, closed, or direction-unstable polygonal Chains by adjacent
  segment direction compatibility.
- Do not merge across closed-loop wrap in v1.

This is a partial OQ-11 decision for straight/turning polygonal Chains only.
Curved policy, sawtooth tuning, user split marks, closed-loop wrap merge,
advanced corner detection and relation to disk-cycle ordering remain unresolved.

G3c0 does not implement AlignmentClass or PatchAxes.

## G3c1 - Chain directional PatchChain evidence

G3c1 implements `PatchChainDirectionalEvidence` as a patch-local directional
occurrence derived from `ChainDirectionalRun` plus Layer 1 `PatchChain`.

Scope:
- Preserve per-PatchChain membership needed by future AlignmentClass.
- Reverse direction and source endpoints for negatively oriented PatchChains.
- Preserve Layer 1 Chain, PatchChain, BoundaryLoop and Patch identity.
- Do not implement AlignmentClass or PatchAxes.
- `PatchChainDirectionalEvidence` is derived directional evidence for a PatchChain.
  It is not a competing PatchChain identity.

## G3c2 - AlignmentClass v0

G3c2 implements `AlignmentClass` v0 as sign-insensitive direction-family
groups over `PatchChainDirectionalEvidence` records.

Scope:
- Consume `PatchChainDirectionalEvidence`, not Layer 1 Chain directly.
- Group by direction similarity only.
- Preserve per-PatchChain membership through `member_directional_evidence_ids`.
- Do not implement PatchAxes, CoordinateHint, WORLD_UP bias, H/V labels,
  or WorldOrientation.

## G3c3 - PatchAxes v0

G3c3 implements `PatchAxes` v0 as primary/secondary AlignmentClass selection
per Patch.

Scope:
- Derive PatchAxes from AlignmentClasses and patch-local run-use length scores.
- Use primary/secondary naming only.
- Do not introduce U/V labels, WORLD_UP fallback, H/V labels,
  WorldOrientation, UV placement or runtime solve.

## G3c4 - PatchChain Endpoint Samples

G3c4 introduces endpoint samples for PatchChain directional evidence at
topology vertices.

Purpose:
- represent a patch-local directional run as a ray leaving or entering a
  PatchChain endpoint;
- provide tangent-away-from-endpoint vectors;
- attach owner surface normal evidence;
- prepare pairwise endpoint relations.

This does not introduce U/V labels, H/V labels, WORLD_UP, WorldOrientation,
solve, UV or ScaffoldGraph.

Model concept:

```text
PatchChainDirectionalEvidence
  -> endpoint sample at START vertex
  -> endpoint sample at END vertex
```

Each sample stores:

- vertex_id;
- directional_evidence_id;
- patch_id;
- patch_chain_id;
- endpoint_role: START / END;
- tangent_away_from_vertex;
- owner_normal;
- owner_normal_source;
- confidence / evidence.

Owner normals prefer Layer 2 `LocalFaceFanGeometryFacts.normal` with
`owner_normal_source = LOCAL_FACE_FAN_NORMAL`. If no non-zero fan normal is
available, endpoint samples may fall back to `PatchGeometryFacts.normal` with
`owner_normal_source = PATCH_AGGREGATE_NORMAL`.

Layer 1 `PatchChain` must not store normals.

Implementation status:
- `PatchChainEndpointSample` is implemented as a Layer 3 derived relation.
- Code has adopted canonical `PatchChainEndpointSample` terminology.
- Samples are emitted for START and END directional evidence endpoints.
- `tangent_away_from_vertex` points away from the sampled topology Vertex.
- Owner normals prefer LocalFaceFan normals and fall back to Patch aggregate
  normals when needed.

## G3c5 - PatchChain Endpoint Relations

G3c5 derives pairwise relations between PatchChain endpoint samples at the
same Vertex.

Purpose:
- identify continuation candidates;
- identify orthogonal/corner connectors;
- identify oblique/ambiguous/degenerate relations;
- provide structural input for ScaffoldGraph.

Relation vocabulary v0:

```text
Direction relation:
  OPPOSITE_COLLINEAR
  SAME_RAY_COLLINEAR
  ORTHOGONAL
  OBLIQUE
  DEGENERATE

Scaffold relation kind:
  CONTINUATION_CANDIDATE
  CORNER_CONNECTOR
  OBLIQUE_CONNECTOR
  AMBIGUOUS
  DEGENERATE
```

Rules:
- no U/V labels;
- no H/V labels;
- no WORLD_UP;
- no WorldOrientation;
- no solve/runtime/UV;
- no Layer 1 mutation;
- relations are derived from Layer 1 topology, Layer 2 geometry and Layer 3
  directional evidence data.

Implementation status:
- `PatchChainEndpointRelation` is implemented as a Layer 3 derived relation.
- Code has adopted canonical `PatchChainEndpointRelation` terminology.
- Relations are unordered sample pairs at the same Vertex.
- v0 classifies direction relation as OPPOSITE_COLLINEAR,
  SAME_RAY_COLLINEAR, ORTHOGONAL, OBLIQUE or DEGENERATE.
- v0 maps those measurements to continuation candidate, corner connector,
  oblique connector, ambiguous or degenerate relation kinds.
- ScaffoldTrace remains deferred.

## G3c6 - LoopCorner

G3c6 introduces `LoopCorner` as the patch-local transition between adjacent
PatchChains inside one BoundaryLoop at one materialized Vertex occurrence.

LoopCorner is patch-local. It is not a ScaffoldNode and not a ScaffoldJunction
by itself.

Implementation status:
- LoopCorner is implemented as a Layer 3 derived relation.
- One LoopCorner is built per BoundaryLoop position from final PatchChains.
- For the cylinder tube fixture this produces exactly four LoopCorners.
- ScaffoldGraph consumes LoopCorner and ScaffoldNode evidence in G3c8.

## G3c7 - ScaffoldNode v0

G3c7 introduces `ScaffoldNode` as a graph-level evidence node assembled from
`LoopCorner`, `PatchChainEndpointSample` and `PatchChainEndpointRelation` data.

ScaffoldNode v0 is a Layer 3 derived relation record. It is not Layer 1 topology
and not a replacement for Vertex, Chain, PatchChain or BoundaryLoop identity.

Grouping policy v0:

- group materialized topology `Vertex` occurrences by `SourceVertexId` when
  source provenance exists;
- fall back to topology `VertexId` grouping when no source provenance exists;
- retain contributing LoopCorner ids, endpoint sample ids, endpoint relation ids,
  incident PatchChain ids, Patch ids, confidence and evidence;
- do not classify ScaffoldJunctions inside the ScaffoldNode builder;
- ScaffoldNode v0 itself does not classify ScaffoldJunctions or build graph
  edges/traces.

Rules:

- no Layer 1 mutation;
- no PatchChain split/re-id;
- no U/V labels;
- no H/V labels;
- no WORLD_UP;
- no WorldOrientation;
- no Feature, Runtime, Solve or UV semantics.

Implementation status:

- `ScaffoldNode` is implemented in the Layer 3 relation model.
- `build_scaffold_nodes()` builds nodes from LoopCorners and endpoint evidence.
- `RelationSnapshot.scaffold_nodes` stores the derived node records.
- Inspection reports `scaffold_node_count` and full `scaffold_nodes` in full detail.

## G3c8 - ScaffoldEdge / ScaffoldGraph v0

G3c8 builds `ScaffoldGraph` from final PatchChains and implemented
`ScaffoldNode` evidence.

`ScaffoldEdge` is the graph-level view of one final PatchChain. It does not
split, merge, refine or re-id PatchChains. `ScaffoldGraph` is connectivity-only
over existing ScaffoldNodes and ScaffoldEdges.

Implementation status:

- `ScaffoldEdge` is implemented in the Layer 3 relation model.
- `ScaffoldGraph` is implemented in the Layer 3 relation model.
- `build_scaffold_graph()` emits one ScaffoldEdge per final PatchChain.
- `RelationSnapshot.scaffold_edges` and `RelationSnapshot.scaffold_graph` store
  the derived records.
- Pipeline inspection exposes a JSON-serializable `scaffold_graph_overlay`
  payload with node anchors, edge polylines, SELF_SEAM junction markers and
  graph ids for debug tooling.
- Grease Pencil dev rendering consumes that overlay payload and reports compact
  validation counts; it does not recompute ScaffoldGraph semantics.

Compact report expectations:

| Fixture | `scaffold_node_count` | `scaffold_edge_count` | `scaffold_junction_count` | `edge_stroke_count` | `node_marker_count` | `junction_marker_count` |
|---|---:|---:|---:|---:|---:|---:|
| single patch / rectangle | 1 | 1 | 0 | 1 | 1 | 0 |
| cylinder tube without caps + one seam cut | 2 | 4 | 2 | 4 | 2 | 2 |
| closed shared-loop / cube-like synthetic fixture | 2 | 2 | 2 | 2 | 2 | 2 |

Report interpretation:

- `ScaffoldNode` is graph-level evidence grouped from LoopCorners and endpoint
  evidence; it is not every mesh vertex.
- `ScaffoldEdge` is one graph edge per final `PatchChain`; the overlay edge
  source remains `FINAL_PATCH_CHAIN`.
- `SELF_SEAM` `ScaffoldJunction` markers render on top of existing ScaffoldNode
  positions and do not create additional graph nodes.

Rules:

- no Layer 1 mutation;
- no PatchChain split/re-id;
- no raw BMesh or boundary-builder internal source;
- no ScaffoldTrace, ScaffoldCircuit or ScaffoldRail construction;
- no U/V labels, H/V labels, WORLD_UP, WorldOrientation, Feature, Runtime,
  Solve or UV semantics.

Grease Pencil rendering is a dev-tool consumer. It must consume the inspection
overlay payload instead of duplicating core graph logic or importing Blender
into Scaffold Core.

## G3c9 - ScaffoldJunction v0 SELF_SEAM/CROSS_PATCH

G3c9 classifies `SELF_SEAM` and `CROSS_PATCH` ScaffoldJunction overlays on existing
`ScaffoldNode` records after ScaffoldGraph construction.

`ScaffoldJunction` is not a separate graph node identity. It is a Layer 3
derived classification record keyed to `ScaffoldNode.id`. Ordinary
ScaffoldNodes remain unclassified by emitting no ScaffoldJunction record.

Implementation status:

- `ScaffoldJunctionKind` is implemented with `SELF_SEAM` and `CROSS_PATCH`.
- `ScaffoldJunction` records retain policy, scaffold node id, matched ChainId
  and PatchId when applicable, contributing ChainIds, PatchIds, LoopIds,
  ScaffoldEdge ids, PatchChain ids, confidence and evidence.
- `build_scaffold_junctions()` consumes existing ScaffoldNodes and
  ScaffoldEdges. It emits SELF_SEAM when one ScaffoldNode has at least two
  incident final PatchChains with the same ChainId and same PatchId.
- `build_scaffold_junctions()` emits CROSS_PATCH when one existing
  ScaffoldNode's incident final ScaffoldEdges reference more than one distinct
  PatchId.
- `RelationSnapshot.scaffold_junctions` stores emitted junction overlays.
- Pipeline inspection reports `scaffold_junction_count` and full
  `scaffold_junctions` details in full detail.

Fixture expectations:

| Fixture | `scaffold_junction_count` |
|---|---:|
| single patch / rectangle | 0 |
| cylinder tube without caps + one seam cut | 2 |
| closed shared-loop / cube-like synthetic fixture | 2 |

Rules:

- no ScaffoldNode grouping changes;
- no ScaffoldEdge or ScaffoldGraph identity changes;
- no Layer 1 Vertex, Chain, PatchChain, BoundaryLoop or Patch identity changes;
- no ScaffoldJunction kinds beyond SELF_SEAM/CROSS_PATCH;
- no ScaffoldTrace, ScaffoldCircuit or ScaffoldRail construction;
- no U/V labels, H/V labels, WORLD_UP, WorldOrientation, Feature, Runtime,
  Solve or UV semantics.

## Implemented - ScaffoldNodeIncidentEdgeRelation v1

ScaffoldNodeIncidentEdgeRelation v1 is implemented as a complete unordered all-pairs
relation over incident ScaffoldEdge endpoint occurrences at one existing
ScaffoldNode. For n incident edge-end occurrences at one ScaffoldNode, v1 emits
C(n,2) relations.

Current code emits the complete all-pairs matrix, including pairs with missing
endpoint evidence.

Emission is graph-structural. Missing PatchChainEndpointSample or
PatchChainEndpointRelation evidence must not cause a pair to disappear. When
endpoint evidence is unavailable, the pair remains present as
MISSING_ENDPOINT_EVIDENCE or DEGRADED.

Classification is evidence-backed and may use:

- tangent direction evidence;
- owner normal evidence;
- direction_dot;
- normal_dot;
- endpoint sample ids;
- PatchChainEndpointRelation id when available;
- confidence and evidence quality.

Implemented v1 kinds:

| Kind | Meaning |
|---|---|
| `STRAIGHT_CONTINUATION_CANDIDATE` | Opposite tangent/chord evidence; compatible owner-normal proof may be absent or weak. |
| `SURFACE_CONTINUATION_CANDIDATE` | Opposite-tangent or straight-ish surface continuation candidate with compatible owner normals. |
| `CROSS_SURFACE_CONNECTOR` | Tangent may align or connect, but owner normals diverge strongly. |
| `ORTHOGONAL_CORNER` | Tangent evidence is orthogonal. |
| `OBLIQUE_CONNECTOR` | Tangent evidence is neither collinear nor orthogonal. |
| `SAME_RAY_AMBIGUOUS` | Endpoint tangents point in the same ray direction away from the node. |
| `MISSING_ENDPOINT_EVIDENCE` | The edge-end pair exists but endpoint sample/relation evidence is absent. |
| `DEGRADED` | Tangent, normal, confidence or evidence is zero, unknown or collapsed. |

| Kind | Meaning |
|---|---|
| `SURFACE_SLIDING_CONTINUATION_CANDIDATE` | Node-local relation between two existing ScaffoldEdge endpoint occurrences whose local tangent/chord classification may otherwise look orthogonal or same-ray, but explicit same-side-surface evidence plus compatible local owner normals support continuation along the same curved or side surface. |

`SURFACE_SLIDING_CONTINUATION_CANDIDATE` is not a trace path choice, not a
selected next edge, not a rail/circuit decision and not a UV direction. It
requires local owner-normal evidence, compatible local owner normals and
explicit same-side-surface evidence. Current SideSurfaceContinuityEvidence v0
may be consumed as this explicit same-side-surface evidence source. The approved
v1 contract adds a direction/flow-family compatibility gate before this evidence
may promote a pair to `SURFACE_SLIDING_CONTINUATION_CANDIDATE`. Same patch,
same loop, END -> START adjacency and compatible local normals are not
sufficient by themselves under v1. Missing, degraded or
direction-family-incompatible evidence must not produce this kind under v1.
SharedChainPatchChainRelation alone must not produce this kind. Cross-patch
cap, corner and shared-boundary cases must remain non-propagating unless
same-side-surface and direction/flow-family evidence is explicit and safe under
v1.

Tube examples:

- Tube without caps split by multiple seam chains: top border PatchChains may
  become `SURFACE_SLIDING_CONTINUATION_CANDIDATE` through seam nodes when
  explicit same-side-surface evidence, compatible local owner normals and
  compatible direction/flow-family evidence prove curved side-surface
  continuation. The expected continuity result is two side families rather than
  four singleton side boundary edges.
- Tube with cap patch: side-to-cap PatchChains may be shared/cross-patch
  neighbors, but they are not side-surface continuation when owner normals
  diverge.
- Folded 90 seam, cube-like corner and cap-cross-surface cases remain
  non-propagating unless explicit same-side-surface evidence is safe.
- Local `D:\cylinder.blend` is an exploratory smoke fixture, not the canonical
  synthetic fixture for this contract.

Rules:

- evidence only; no trace path, circuit, rail, continuation, UV or runtime
  behavior selection;
- no ScaffoldNode grouping changes;
- no ScaffoldEdge, PatchChain, Chain, Vertex or BoundaryLoop identity changes;
- no H/V, U/V, WORLD_UP, WorldOrientation, Feature, API, UI, runtime solve or
  UV transfer.

## Implemented - SideSurfaceContinuityEvidence v0; approved v1 contract

SideSurfaceContinuityEvidence v0 is implemented as a
Layer 3 derived evidence record over two existing ScaffoldEdge endpoint
occurrences at one existing ScaffoldNode.

Meaning:

- the two edge-end occurrences are candidate same-side surface flow within one
  patch boundary loop;
- the approved v1 contract, not yet implemented, additionally requires
  compatible direction/flow families;
- evidence only;
- not a trace path choice;
- not a selected next edge;
- not a rail, circuit, UV direction, feature or runtime solve.

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

Consumption:

- SURFACE_SLIDING_CONTINUATION_CANDIDATE may consume
  SideSurfaceContinuityEvidence v1 as its same-side-surface evidence source.
- ScaffoldContinuityComponent v0 may continue propagating through
  SURFACE_SLIDING_CONTINUATION_CANDIDATE only.
- ScaffoldContinuityComponent v0 must not propagate directly through
  SideSurfaceContinuityEvidence.

Fixture expectation:

- Local `D:\cylinder.blend` / Cube.001 remains exploratory, not canonical
  acceptance. Wrong merges P1C1->P1C2, P1C2->P1C3, P2C3->P2C0 and P2C2->P2C3
  are examples of ORTHOGONAL_CORNER pairs crossing alignment:0 <-> alignment:1
  and must be blocked by v1 rather than promoted to
  SURFACE_SLIDING_CONTINUATION_CANDIDATE.
- Missing lower-side cross-patch or same-chain lower-ring flow is deferred and
  unresolved. It requires a separate evidence contract if needed later.

## G3c11 - ScaffoldContinuityComponent v0

ScaffoldContinuityComponent v0 is implemented as a Layer 3 derived evidence
view over existing ScaffoldEdges and existing ScaffoldNodeIncidentEdgeRelation
records.

It groups ScaffoldEdges into continuity families using continuation-compatible
incident relations. It is not a trace, path choice, rail, circuit, UV
direction, runtime behavior or replacement for ScaffoldEdge or PatchChain
identity.

Default propagation policy:

| Incident relation kind | v0 propagation |
|---|---|
| `SURFACE_CONTINUATION_CANDIDATE` | Propagates continuity. |
| `SURFACE_SLIDING_CONTINUATION_CANDIDATE` | Propagates continuity by default. |
| `SideSurfaceContinuityEvidence` | Does not propagate directly; may affect components only through `SURFACE_SLIDING_CONTINUATION_CANDIDATE`. |
| `STRAIGHT_CONTINUATION_CANDIDATE` | Weak evidence; non-default for propagation in v0. |
| `ORTHOGONAL_CORNER` | Does not propagate. |
| `OBLIQUE_CONNECTOR` | Does not propagate. |
| `CROSS_SURFACE_CONNECTOR` | Does not propagate. |
| `SAME_RAY_AMBIGUOUS` | Does not propagate and must mark ambiguity. |
| `MISSING_ENDPOINT_EVIDENCE` | Does not propagate. |
| `DEGRADED` | Does not propagate. |

Every ScaffoldEdge belongs to exactly one continuity component, including
singleton components. If multiple continuation-compatible candidates meet at
the same ScaffoldNode, the component may be marked ambiguous. v0 must preserve
ambiguity and must not choose one continuation target.

Debugging contract:

- color represents `continuity_component_id`, not relation kind;
- relation kind remains a separate visual channel such as marker, glyph, label,
  dash or warning outline;
- component colors are deterministic pseudo-random and stable by component id,
  never true random.

Rules:

- no ScaffoldNode grouping changes;
- no ScaffoldEdge, ScaffoldGraph, ScaffoldJunction, PatchChain, Chain or Vertex
  identity changes;
- no ScaffoldTrace, ScaffoldCircuit or ScaffoldRail construction;
- no path choice, continuation target choice, runtime behavior or solve
  behavior.
- no H/V, U/V, WORLD_UP, WorldOrientation, Feature, API, UI, runtime solve or
  UV transfer.

## Future - ScaffoldTrace

`ScaffoldTrace` is a connected sequence of ScaffoldEdges through ScaffoldNodes.
It may later be classified as:

```text
OPEN_TRACE
CLOSED_TRACE
BRANCHING_TRACE
AMBIGUOUS_TRACE
```

`ScaffoldCircuit` is a closed ScaffoldTrace. `ScaffoldRail` is a future
direction-stable ScaffoldTrace usable as a conditional axis.

Cylinder-like cases may produce ScaffoldCircuits around cap boundaries. These
traces can later inform conditional axes or UV orientation.

ScaffoldTrace must not create a competing PatchChain identity layer.

## Rules

Layer 3 is derived from:

```text
Layer 1 topology
Layer 2 geometry
Layer 0 overrides, where explicitly supported
```

Layer 3 must not depend on:

```text
Layer 4 features
Layer 5 runtime/solve
UV transfer
Blender UI
```

`DihedralKind` is an attribute of `PatchAdjacency`, not of `Chain`.

A query by Chain must return a list of adjacency records, not a single
dihedral value.

Signed dihedral computation must use both PatchChain orientations.

WorldOrientation labels must not feed base Alignment.

## G3a Acceptance

G3a is acceptable when:

1. `test_forbidden_imports.py` passes.
2. `test_module_docstrings.py` passes.
3. Patch adjacency is derived from shared two-patch Chains.
4. Border, SEAM_SELF and non-manifold Chains do not produce normal adjacency.
5. `DihedralKind` is stored on `PatchAdjacency`.
6. Pipeline output can carry a relation snapshot.
7. Layer 3 does not import Layer 4, Layer 5, API, UI or Blender modules.
8. Layer 3 stores no H/V, WALL/FLOOR/SLOPE, Feature, runtime, UV, or solve roles.
9. G3a relation builder does not use `WORLD_UP`.
