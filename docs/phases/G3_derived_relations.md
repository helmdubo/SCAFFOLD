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
- Junction relations
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
  junction relations
  ChainContinuationRelation

G3c:
  AlignmentClass
  PatchAxes

G3d:
  WorldOrientation
```

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

Signed dihedral computation must use both ChainUse orientations.

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
