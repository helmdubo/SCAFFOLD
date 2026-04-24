# Blender Boundaries

Scaffold Core separates Blender IO from core interpretation logic.

## Mesh read boundary

The only core mesh-read entrypoint is:

```text
scaffold_core/layer_0_source/blender_io.py
```

It converts Blender/BMesh state into `SourceMeshSnapshot`.

Other core layers must not read BMesh directly.

## UV write boundary

UV write-back is introduced in G5 and belongs only to:

```text
scaffold_core/layer_5_runtime/uv_transfer.py
```

No other runtime module should write UVs to BMesh.

## Blender add-on exception

A separate Blender add-on package may import `bpy` for:

- `bl_info`;
- register/unregister;
- operators;
- panels;
- debug overlays.

The add-on package must call into Scaffold Core through public pipeline/API boundaries.

It must not duplicate core logic.

## Recommended add-on metadata

```python
bl_info = {
    "name": "Scaffold",
    "author": "...",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "category": "UV",
    "description": "Structural UV for architectural meshes",
    "location": "UV Editor > Sidebar > Scaffold",
}
```

`category = "UV"` is intentional because the primary workflow lives in UV space.
