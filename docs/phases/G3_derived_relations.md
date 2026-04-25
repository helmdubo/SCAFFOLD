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

## G3b1 Junction incidence

G3b1 implements Junction incidence queries as derived views over Vertex.
It does not introduce a Junction entity.
It does not implement disk-cycle ordering.
It does not implement ChainContinuationRelation.

## G3b2 — Conservative ChainContinuationRelation

Scope:
- Define continuation relations at topology vertices.
- Use G3b1 junction incidence queries as input.
- Implement conservative TERMINUS / SPLIT first.
- SMOOTH / TURN are allowed only for trivial synthetic fixtures in Task E.
- Do not solve OQ-11.
- Do not create AlignmentClass.
- Do not create PatchAxes.
- Do not create WorldOrientation.
- Do not mutate or re-id Layer 1 Chains.

Concept:

```text
At this Vertex, does this ChainUse continue into another ChainUse?
```

Conservative kinds for Task E:

```text
TERMINUS:
  A ChainUse reaches a Vertex and has no safe continuation candidate.

SPLIT:
  A ChainUse reaches a Vertex and multiple continuation candidates exist,
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
    junction_vertex_id: VertexId
    source_chain_use_id: ChainUseId
    target_chain_use_id: ChainUseId | None
    kind: ContinuationKind
    confidence: float
    evidence: tuple[Evidence, ...] = ()
```

Notes:
- `target_chain_use_id = None` for TERMINUS.
- SPLIT may be represented as multiple relations from the same source use
  to multiple candidate target uses, each with kind = SPLIT.
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

## G3c1 - Chain directional run uses

G3c1 implements `ChainDirectionalRunUse` as a patch-local directional
occurrence derived from `ChainDirectionalRun` plus Layer 1 `ChainUse`.

Scope:
- Preserve per-ChainUse membership needed by future AlignmentClass.
- Reverse direction and source endpoints for negatively oriented ChainUses.
- Preserve Layer 1 Chain, ChainUse, BoundaryLoop and Patch identity.
- Do not implement AlignmentClass or PatchAxes.

## G3c2 - AlignmentClass v0

G3c2 implements `AlignmentClass` v0 as sign-insensitive direction-family
groups over `ChainDirectionalRunUse` records.

Scope:
- Consume `ChainDirectionalRunUse`, not Layer 1 Chain directly.
- Group by direction similarity only.
- Preserve per-ChainUse membership through `member_run_use_ids`.
- Do not implement PatchAxes, CoordinateHint, WORLD_UP bias, H/V labels,
  or WorldOrientation.

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
