# Layer 1 — Immutable Topology Snapshot

Layer 1 is the stable topological substrate.

## Purpose

Layer 1 represents how a source mesh is decomposed into surface regions, boundaries, loops and oriented boundary uses.

Layer 1 is intentionally ignorant of:

- H/V roles;
- WALL/FLOOR/SLOPE;
- UV coordinates;
- pin decisions;
- feature classifications;
- runtime solve roles.

## Owns

- `SurfaceModel`
- `Shell`
- `Patch`
- `BoundaryLoop`
- `Chain`
- `PatchChain` / legacy code name `ChainUse`
- `Vertex`
- topology invariants
- topology queries

## G1 Patch segmentation policy

Patch segmentation uses selected-face flood fill.

A source edge blocks Patch flood fill and becomes a Patch boundary if:

```text
- it is a mesh/selection border;
- it is non-manifold in selected scope;
- it has an explicit Scaffold boundary mark;
- it has a Blender UV Seam.
```

Blender Sharp is **not** a default Patch boundary source in G1.

A future optional command/flag may support:

```text
make seams by sharps
```

That option should convert sharp information into seam/boundary input before segmentation. It must not make Sharp a hidden default segmentation source.

Not default in G1:

```text
- Blender Sharp;
- material boundary;
- normal angle threshold;
- existing UV island boundary.
```

## G1 Shell detection policy

Shell detection uses edge-connected components of selected faces.

Shell connectivity ignores Patch segmentation boundaries:

```text
seams / explicit Scaffold boundary marks:
  may split Patches
  do not split Shells
```

Vertex-only contact does not connect Shells.

Non-manifold edge connectivity keeps faces in the same Shell candidate, but emits a degraded non-manifold diagnostic.

## PatchChain rule

`PatchChain` is mandatory. Current code may still use the legacy class name
`ChainUse`; conceptually this is the final PatchChain.

A `Chain` is the shared boundary entity.
A `PatchChain` is the oriented use of a `Chain` inside a BoundaryLoop/Patch.

All orientation-sensitive logic must use `PatchChain` / `ChainUse`, not raw
`Chain`.

`PatchChain` may carry materialized start/end topology vertices for seam-cut
loop occurrences. These vertices are still Layer 1 topology/provenance and do
not store normals or geometry semantics.

## Chain coalescing

Layer 1 distinguishes atomic boundary segments from topology Chains:

```text
Atomic boundary segment:
  one source edge on a Patch boundary.

Chain:
  shared topological boundary run built from one or more atomic boundary
  segments.

PatchChain:
  final oriented patch-local use of a Chain inside a BoundaryLoop.
```

Current G1/G3 implementation rule:

```text
Merge consecutive boundary segments when they have the same boundary run kind,
the same Patch context and are continuous in final materialized loop order.
```

Intended boundary construction pipeline:

```text
1. Flood fill selected faces until boundary edges.
2. Build Patch boundaries and raw boundary cycles.
3. For every boundary edge, classify neighbour context:
   - self patch neighbour / seam-self;
   - other patch neighbour;
   - no patch neighbour / open boundary;
   - non-manifold.
4. Build draft boundary runs internally.
5. Redefine/coalesce/split draft runs according to policy.
6. Materialize final BoundaryLoop with final PatchChains.
7. Downstream systems use final PatchChains.
```

Raw boundary sides, atomic source edges and draft runs are builder internals.
Do not create a public `PatchChainSpan`, `EffectivePatchChain` or
`ScaffoldPatchChain` layer.

Boundary run kinds:

```text
BORDER_RUN:
  source mesh / selected-region border

PATCH_ADJACENCY_RUN:
  boundary between different Patches

SEAM_SELF_RUN:
  seam cut materialized as two ChainUses in the same Patch

NON_MANIFOLD_RUN:
  represented and diagnosed, not silently fixed
```

Example:

```text
Long seam of 4 source edges between two Patches:
  expected:
    1 Chain
    Chain.source_edge_ids = (e10, e9, e6, e7)
    2 ChainUses
```

Cylinder tube without caps and with one seam cut:

```text
Patch count: 1
BoundaryLoop count: 1 OUTER
Chain count: 3
PatchChain count: 4

PatchChains:
  1. seam side A
  2. cap/border ring A
  3. seam side B
  4. cap/border ring B
```

Final PatchChain may be the same as the draft run, or may be split/coalesced.
For example, a cap ring can remain one PatchChain if policy says it is one
structural boundary side, a long L-shaped open boundary can become several
PatchChains, and a seam side can be one PatchChain used twice through
SEAM_SELF.

## Current limitations

- Coalescing is topology/context-based only.
- Geometry-based Chain split/refinement by tangent, angle, normal or user split
  is deferred.

## Chain refinement note

Current G3a Chain identity is topological. A coalesced Chain represents a
shared boundary region between Patches. It is correct for `PatchAdjacency`.

It is **not** guaranteed direction-stable for AlignmentClass.

A coalesced Chain may be:

- closed (start_vertex_id == end_vertex_id);
- turning (multiple direction segments through corners);
- direction-ambiguous (no stable chord direction).

Before AlignmentClass / PatchAxes, such Chains require Layer 2
geometry-based refinement.

Refinement does not change Layer 1 Chain identity. It produces derived
Layer 3 entities or alignment groupings consumed by AlignmentClass.

See DD-29, DD-30, OQ-11.

## Cardinality cases

| Case | Chain has PatchChains / ChainUses | Meaning |
|---|---:|---|
| Mesh border | 1 | Boundary of model or selection. |
| Normal shared boundary | 2, different patches | Standard adjacency. |
| SEAM_SELF | 2, same patch | Supported self-use case. |
| Non-manifold | >2 | Represent and diagnose explicitly. |

## Layer 1 must not contain

- `H_FRAME`
- `V_FRAME`
- `FREE`
- `WALL`
- `FLOOR`
- `SLOPE`
- `BAND`
- `PANEL`
- `PINNED`
- `GUIDE`
- UV coordinates
- skeleton solve coordinates
- feature confidence

If any of these appear in Layer 1 models, higher-level interpretation leaked into topology.
