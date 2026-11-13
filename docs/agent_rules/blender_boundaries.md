# Blender Boundaries

Scaffold Core separates Blender IO from core interpretation logic.

## Mesh read boundary

The only core mesh-read entrypoint is:

```text
scaffold_core/layer_0_source/blender_io.py
```

It converts Blender/BMesh state into `SourceMeshSnapshot`. In Edit Mode the
Face Strength attribute data reads as empty through the mesh, so the mark is
read from the edit BMesh face layer of the same name (plan Slice AH).

Other core layers must not read BMesh directly.

## UV write boundary

UV write-back is introduced in G5 and belongs only to:

```text
scaffold_core/layer_5_runtime/uv_transfer.py
```

No other runtime module should write UVs to BMesh.

Current G5a behavior, two entry points:

```text
write_pinned_uvs: writes pinned skeleton UV coordinates and pin flags only,
  in the mesh's current mode, through bmesh. It calls no bpy operator (no
  mode_set, no unwrap). The artist runs Blender's U > Unwrap afterwards.

write_quilt_uvs (plan Slice AH): lays every quilt as one chart.
  - It acts on the target object only. Before changing anything it
    refuses when the target object is not visible, when any solved face is
    hidden, or when any other object is in Edit Mode, whichever mode the
    target is in (the unwrap skips what is hidden and would change the UVs
    of every object in Edit Mode; measured: one hidden face changed 444 of
    968 loops of the visible faces).
  - From Object Mode it saves the mesh's vertex, edge and face selection
    flags (entering Edit Mode flushes them), deselects the other objects,
    makes the target the only selected and active object, and enters Edit
    Mode (mode_set).
  - It writes the pins there, through write_pinned_uvs, in Edit Mode.
  - For the call only, it sets the seam flag of every edge of a solved face
    to "this edge is a UV cut" (SolveResult.uv_cut_source_edge_ids), selects
    the solved faces and runs bpy.ops.uv.unwrap(method="CONFORMAL",
    fill_holes=False, margin=0.0).
  - It rescales every chart with fewer than two distinct pins so that its
    UV area is its 3D area times LAYOUT_UV_PER_MESH_UNIT squared (about its
    one pin, or about the centre of its UVs); charts with two or more pins
    are not touched.
  - In finally blocks it restores the seam flags, the exact vertex, edge
    and face selection flags (in Edit Mode it clears every flag and then
    sets the saved ones, vertices, edges, faces, because bmesh's select
    setter flushes; from Object Mode it writes the flags saved before Edit
    Mode back after leaving it), the mode, the object selection and the
    active object, also when the unwrap fails. The user's seams are never
    changed.
```

Caution kept from the earlier split: Blender 4.3 crashed when pin flags were
written in one mode and an unwrap or mode operator was then invoked from the
same runtime boundary. write_pinned_uvs stays operator-free for that reason.
write_quilt_uvs avoids the recorded pattern by changing mode first and then
writing the pins and running the unwrap in one mode, Edit Mode.

What was and was not tested for write_quilt_uvs: headless on Blender 4.5 and
4.3.2 (13 objects, no crash, 0 seam flags changed; the smoke tool's
`--unwrap-quilts` run fails when a seam flag changes, a loop of an unsolved
face or of another selected object changes, a vertex, edge or face
selection flag of the target mesh changes, or the object selection or the
active object is not restored). Selection flags measured: 0 changed in
vertex, edge and face select modes, with partial selections and with a
forced unwrap failure. Not tested in the interactive UI; undo was not
verified; the bmesh select history (the active element) was not
measured.

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
