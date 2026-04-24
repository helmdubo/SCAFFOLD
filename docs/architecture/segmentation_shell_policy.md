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
5. Build Chain / ChainUse cardinality from Patch boundary uses.
6. Emit diagnostics for border, SEAM_SELF and non-manifold cardinality cases.
```

The current fixture-oriented baseline builder may remain simple while tests and policy-specific implementation are added incrementally.
