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

G3 may introduce:

- `PatchAdjacency`
- `DihedralKind`
- `ChainContinuationRelation`
- PatchChain endpoint relations
- `AlignmentClass`
- `PatchAxes`
- WorldOrientation relations
- relation diagnostics

Initial G3a scope:

```text
PatchAdjacency
DihedralKind
RelationSnapshot
```

Deferred G3 slices:

```text
G3b:
  endpoint relations
  ChainContinuationRelation

G3c:
  AlignmentClass
  PatchAxes

G3d:
  WorldOrientation
```

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
| `ScaffoldJunction` | Future graph-level ScaffoldNode classification for branch/seam/cross-patch structures. |

Endpoint samples, endpoint relations and LocalFaceFanGeometryFacts are evidence
or measurements; they are not graph nodes.

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

## G3c4 - PatchChainEndpointSample

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
- Current code uses
  `PatchChainEndpointSample`; those are current names.
- Samples are emitted for START and END run-use endpoints.
- `tangent_away_from_vertex` points away from the sampled topology Vertex.
- Owner normals prefer LocalFaceFan normals and fall back to Patch aggregate
  normals when needed.

## G3c5 - PatchChainEndpointRelation

G3c5 derives pairwise relations between PatchChain endpoint samples at the
same Vertex.

Purpose:
- identify continuation candidates;
- identify orthogonal/corner connectors;
- identify oblique/ambiguous/degenerate relations;
- provide structural input for future ScaffoldGraph.

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
  run-use data.

Implementation status:
- `PatchChainEndpointRelation` is implemented as a Layer 3 derived relation.
- Current code uses `PatchChainEndpointRelation`;
  those are current names.
- Relations are unordered sample pairs at the same Vertex.
- v0 classifies direction relation as OPPOSITE_COLLINEAR,
  SAME_RAY_COLLINEAR, ORTHOGONAL, OBLIQUE or DEGENERATE.
- v0 maps those measurements to continuation candidate, corner connector,
  oblique connector, ambiguous or degenerate relation kinds.
- ScaffoldGraph / ScaffoldTrace remain deferred.

## G3c6 - LoopCorner

G3c6 introduces `LoopCorner` as the patch-local transition between adjacent
PatchChains inside one BoundaryLoop at one materialized Vertex occurrence.

LoopCorner is patch-local. It is not a ScaffoldNode and not a ScaffoldJunction
by itself.

For a cylinder tube with one OUTER BoundaryLoop and four PatchChains, expected
LoopCorner count is four.

## Future - ScaffoldGraph / ScaffoldTrace

A future slice may build `ScaffoldGraph` from `PatchChainEndpointRelation` and
LoopCorner data.

`ScaffoldTrace` is a connected component over continuation-like relations.
It may later be classified as:

```text
OPEN_TRACE
CLOSED_TRACE
BRANCHING_TRACE
AMBIGUOUS_TRACE
```

Cylinder-like cases may produce closed traces/circuits around cap boundaries.
These traces can later inform conditional axes or UV orientation.

Do not implement ScaffoldGraph before PatchChainEndpointRelation and
LoopCorner data are available.

## Rules

Layer 3 is derived from:

```text
Layer 1 topology
Layer 2 geometry
Layer 0 overrides, where explicitly supported
WORLD_UP vector, where explicitly allowed
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
