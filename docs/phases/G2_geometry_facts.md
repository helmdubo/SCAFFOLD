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
- `GeometryFactSnapshot`

Initial G2a facts:

```text
Patch:
  area
  area-weighted normal
  area-weighted centroid
  degenerate-area diagnostic

Chain:
  length
  chord direction
  zero-length diagnostic

Vertex:
  position
```

Later G2b facts:

```text
straightness
detour ratio
shape_hint
sawtooth-straight geometry classifier
```

Sawtooth classification remains a geometry fact. It must not promote anything
to runtime roles or H/V labels.

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
