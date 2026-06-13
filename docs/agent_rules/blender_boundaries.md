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

Current G5a behavior:

```text
uv_transfer.py writes pinned skeleton UV coordinates and pin flags only.
It does not call bpy.ops.mode_set or bpy.ops.uv.unwrap.
The artist runs Blender's U > Unwrap after the pins are written.
```

This operator-free split is intentional: Blender 4.3 can crash when pin flags
are written in one mode and an unwrap/mode operator is invoked from the same
runtime boundary.

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

## Headless validation

Blender validation scripts may exist as validation tools, but they must not
duplicate Scaffold Core logic.

Allowed output:

```text
compact JSON/text report
UV screenshot
overlay screenshot
failure summary
```

Avoid:

```text
dumping full mesh data into agent context
implementing analysis logic in Blender scripts
writing UV outside the G5 uv_transfer boundary
```

Use Blender smoke validation for key milestones, not for every core unit test.
Pure Python tests and compact inspection reports should remain the default agent
feedback loop.
