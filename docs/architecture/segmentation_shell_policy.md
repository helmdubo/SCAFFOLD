# G1 Patch Segmentation and Shell Detection Policy

This file resolves G0 open questions OQ-01 and OQ-02 for G1.

`G0.md` remains the canonical architecture contract. This file is the focused policy reference for implementation work in `scaffold_core/layer_1_topology/`.

---

## OQ-01 resolved — Patch segmentation

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

That future option should convert sharp information into seam/boundary input before segmentation. It must not make Sharp a hidden default segmentation source.

Not default in G1:

```text
- Blender Sharp;
- material boundary;
- normal angle threshold;
- existing UV island boundary.
```

Rationale: G1 should prefer explicit UV/Scaffold boundary intent over broad automatic splitting. Expansion is easy later; undoing over-segmentation assumptions is harder.

---

## OQ-02 resolved — Shell detection

Shell detection uses edge-connected components of selected faces.

Shell connectivity ignores Patch segmentation boundaries:

```text
seams / explicit Scaffold boundary marks:
  may split Patches
  do not split Shells
```

Vertex-only contact does not connect Shells.

Non-manifold edge connectivity keeps faces in the same Shell candidate, but emits a degraded non-manifold diagnostic.

Rationale: Shell is a connected surface component. Patch boundaries describe region segmentation inside a Shell; they are not Shell breaks.

---

## Implementation implications

Final G1 topology building should follow this order:

```text
1. Build selected-face edge adjacency.
2. Detect Shells as selected-face edge-connected components.
3. Detect Patch components by flood fill blocked by the G1 boundary predicate.
4. Build boundary loops per Patch.
5. Build Chain / ChainUse cardinality from Patch boundary uses:
   - collect atomic boundary sides;
   - order them into BoundaryLoops;
   - materialize seam-cut vertex occurrences when a source vertex appears on
     two sides of one Patch loop;
   - coalesce consecutive sides with the same boundary run kind and Patch
     context into Chains;
   - create one ChainUse per Chain occurrence in a Patch loop.
6. Emit diagnostics for border, SEAM_SELF and non-manifold cardinality cases.
```

Current G1/G3 Chain coalescing is topology/context-based only.
Geometry-based Chain splitting or refinement is deferred.

Layer 1 boundary run kinds:

```text
BORDER_RUN
PATCH_ADJACENCY_RUN
SEAM_SELF_RUN
NON_MANIFOLD_RUN
```

## Coalescing scope

Topology coalescing and any future geometry-based Chain refinement must:

- operate inside one ordered atomic boundary cycle;
- never cross OUTER / INNER BoundaryLoop boundaries;
- never merge across separate cycles;
- preserve Layer 1 Chain identity once it is decided in Pass 0
  (see DD-30).

Refinement, if introduced, lives in Layer 3 and produces derived entities
that AlignmentClass consumes. It does not rewrite Layer 1 Chains.
