# G1 — Topology Snapshot Prototype

G1 implements only the foundation of Scaffold Core.

## Scope

Allowed:

- Layer 0 — Source Mesh Snapshot
- Layer 1 — Immutable Topology Snapshot
- Pipeline Pass 0
- Diagnostics and evidence models
- G1 tests and synthetic fixtures

Forbidden in G1:

- Layer 2 Geometry Facts
- Layer 3 Relations
- Layer 4 Feature Grammar
- Layer 5 Runtime/Solve
- AlignmentClass
- WorldOrientation
- FeatureRule / FeatureCandidate / FeatureInstance / FeatureConstraint
- UV transfer
- Blender UI package

## G1 package tree

Only these core implementation directories are allowed in G1:

```text
scaffold_core/core/
scaffold_core/layer_0_source/
scaffold_core/layer_1_topology/
scaffold_core/pipeline/
scaffold_core/tests/
```

## Primary deliverable

A topology snapshot that can represent:

- SurfaceModel
- Shell
- Patch
- BoundaryLoop
- Chain
- ChainUse
- Vertex / Junction

with diagnostics for:

- loop closure;
- ChainUse orientation;
- border chains;
- normal shared chains;
- SEAM_SELF;
- non-manifold chains;
- missing/degraded topology.

## Acceptance

G1 is acceptable when:

1. `test_forbidden_imports.py` passes.
2. `test_module_docstrings.py` passes.
3. Layer 1 invariants are tested.
4. SEAM_SELF has a synthetic fixture and test.
5. Non-manifold cardinality is represented and diagnosed.
6. Pass 0 can build a topology snapshot from a SourceMeshSnapshot fixture.
