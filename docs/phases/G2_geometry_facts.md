# G2 - Geometry Facts

G2 attaches raw measured geometry to the immutable G1 topology snapshot.

## Scope

Allowed:

- Layer 0 - Source Mesh Snapshot
- Layer 1 - Immutable Topology Snapshot
- Layer 2 - Geometry Facts
- Pipeline Pass 0 integration
- Diagnostics and G2 synthetic tests

Forbidden in G2:

- Layer 3 Relations
- Layer 4 Feature Grammar
- Layer 5 Runtime/Solve
- AlignmentClass
- PatchAxes
- WorldOrientation
- DihedralKind
- FeatureRule / FeatureCandidate / FeatureInstance / FeatureConstraint
- UV transfer
- Blender UI package

## G2 package tree

These core implementation directories are allowed in G2:

```text
scaffold_core/core/
scaffold_core/layer_0_source/
scaffold_core/layer_1_topology/
scaffold_core/layer_2_geometry/
scaffold_core/pipeline/
scaffold_core/tests/
```

Forbidden future directories:

```text
scaffold_core/layer_3_relations/
scaffold_core/layer_4_features/
scaffold_core/layer_5_runtime/
scaffold_core/api/
scaffold_core/ui/
```

## Layer 2 Facts

G2 may introduce:

- `PatchGeometryFacts`
- `ChainGeometryFacts`
- `VertexGeometryFacts`
- `LocalFaceFanGeometryFacts`
- `PatchChainGeometryFacts`
- `GeometryFactSnapshot`

G2a facts:

```text
Patch:
  area
  area-weighted normal
  area-weighted centroid
  area_vector_length (plan Slice AH): the length of the sum of the
    patch's triangle area vectors, the unnormalised normal; a raw
    measurement (equal to the area on a planar patch, about 0 when the
    vectors cancel)
  degenerate-area diagnostic
  GEOMETRY_FACE_NEAR_ZERO_AREA (DEGRADED, plan Slice AH): a face whose
    area is at most 1e-6 of its perimeter squared (no width at its own
    scale; a square has 1/16)

Chain:
  length
  chord direction
  zero-length diagnostic

Vertex:
  position

LocalFaceFan:
  patch-local source face component around a topology Vertex
  area
  area-weighted normal
```

G2b facts:

```text
straightness
detour ratio
shape_hint
sawtooth-straight geometry classifier
```

Sawtooth classification remains a geometry fact. It must not promote anything
to runtime roles or H/V labels.

G2b acceptance:

1. Chain straightness is measured.
2. Chain detour ratio is measured.
3. Chain shape hints remain raw geometry facts.
4. Sawtooth-straight classification does not derive roles, alignment,
   world orientation, feature facts, pin facts or UV facts.

G2c facts (G0 DD-48, plan Slice W Stage A):

```text
Chain:
  plane normal (none for a collinear chain)
  largest vertex distance from that plane
  largest vertex distance from the chord

PatchChain (one side of a Chain):
  side face of every chain segment in the use's own patch, and its normal
  tilt range between the chain plane and those normals
```

These stay raw measurements. Whether a piece is a line or a curve on a
surface is a Layer 3 relation (PatchChainShapeRelation).

## Must Not Contain

Layer 2 must not contain or derive:

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

Layer 2 answers:

```text
What shape does this topology have in 3D?
```

Layer 2 does not answer:

```text
What role does this topology play?
```

## Pipeline Rule

`pipeline/` may import Layer 2 and orchestrate Pass 0.

Layer 2 must not import:

```text
pipeline.passes
pipeline.validator
layer_3_relations
layer_4_features
layer_5_runtime
api
ui
```

Layer 1 must not import Layer 2.

## G2a Acceptance

G2a is acceptable when:

1. `test_forbidden_imports.py` passes.
2. `test_module_docstrings.py` passes.
3. Layer 2 facts are frozen dataclasses.
4. Single-quad geometry facts are tested.
5. Multi-face patch aggregate area, normal and centroid are tested.
6. Degenerate patch/chain diagnostics are tested.
7. Pass 0 returns topology and geometry facts.
8. Layer 2 contains no semantic roles, alignment facts, world orientation,
   feature facts, pin facts or UV facts.
