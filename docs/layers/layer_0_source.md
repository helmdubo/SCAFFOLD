# Layer 0 — Source Mesh Snapshot

Layer 0 is the provenance/input layer.

## Purpose

Layer 0 converts Blender/BMesh state into immutable source data that the rest of Scaffold Core can consume without touching Blender directly.

## Owns

- `SourceMeshSnapshot`
- `MeshVertexRef`
- `MeshEdgeRef`
- `MeshFaceRef`
- `SourceMark`
- `UserOverride`
- checksums / fingerprints
- source selection scope
- Blender mesh-read boundary

## Does not own

- topology entities
- geometry facts
- relations
- features
- runtime solve

## Blender boundary

The only core mesh-read entrypoint is:

```text
scaffold_core/layer_0_source/blender_io.py
```

Other core layers must not read BMesh directly.

## G1 scope

In G1, Layer 0 should be minimal and testable without Blender where possible.

Use simple source snapshot fixtures for unit tests.
