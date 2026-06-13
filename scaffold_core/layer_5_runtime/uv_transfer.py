"""
Layer: 5 - Runtime

Rules:
- The ONLY bpy write boundary in scaffold_core (G5a phase rule).
- Writes pinned skeleton UVs, then invokes Blender's pinned conformal
  unwrap for the fabric. Mesh editing stays Blender's.
- bpy is imported lazily inside functions so headless suites never load it.
"""

from __future__ import annotations

from typing import Any

from scaffold_core.layer_5_runtime.pins import SolveResult


def write_pinned_uvs(blender_context: Any, result: SolveResult) -> dict[str, Any]:
    """Write skeleton UVs + pins to the active mesh and run pinned unwrap."""

    import bpy  # the G5 write boundary; never imported headlessly
    import bmesh

    active_object = blender_context.object
    # Mesh.polygons/loops/uv_layers.data are EMPTY in Edit Mode (the data
    # lives in the bmesh). The artist selects faces in Edit Mode, so force
    # Object Mode before touching mesh data, and restore the mode after.
    previous_mode = active_object.mode
    if previous_mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    mesh = active_object.data
    uv_layer = mesh.uv_layers.active or mesh.uv_layers.new(name="UVMap")
    by_vertex_patch = {
        (vertex.source_vertex_id, vertex.patch_id): vertex for vertex in result.vertices
    }
    by_vertex = {}
    for vertex in result.vertices:
        by_vertex.setdefault(vertex.source_vertex_id, vertex)
    written = 0
    pinned_by_face_loop: dict[tuple[int, int], bool] = {}
    for polygon in mesh.polygons:
        face_patch = result.patch_by_source_face.get(f"f{polygon.index}")
        for loop_offset, loop_index in enumerate(polygon.loop_indices):
            loop = mesh.loops[loop_index]
            key = f"v{loop.vertex_index}"
            pinned_vertex = by_vertex_patch.get((key, face_patch)) or by_vertex.get(key)
            if pinned_vertex is None:
                pinned_by_face_loop[(polygon.index, loop_offset)] = False
                continue
            uv_layer.data[loop_index].uv = pinned_vertex.uv
            pinned_by_face_loop[(polygon.index, loop_offset)] = pinned_vertex.pinned
            written += 1
    # Blender 4.3 can crash when Object Mode writes pin_uv before rebuilding
    # edit bmesh, so pin in Edit Mode after the UV coordinates are committed.
    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(mesh)
    bm.faces.ensure_lookup_table()
    bm.faces.index_update()
    edit_uv_layer = bm.loops.layers.uv.active
    for face in bm.faces:
        for loop_offset, loop in enumerate(face.loops):
            loop[edit_uv_layer].pin_uv = bool(pinned_by_face_loop.get((face.index, loop_offset), False))
    bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
    bpy.ops.mesh.select_all(action="SELECT")
    try:
        unwrap_status = bpy.ops.uv.unwrap(method="CONFORMAL")
    except (RuntimeError, TypeError):
        # Older Blender enum naming; ANGLE_BASED also honours pins.
        unwrap_status = bpy.ops.uv.unwrap(method="ANGLE_BASED")
    bpy.ops.object.mode_set(mode="OBJECT")
    if previous_mode != "OBJECT":
        bpy.ops.object.mode_set(mode=previous_mode)
    return {
        "written_loops": written,
        "pinned_vertices": sum(1 for v in result.vertices if v.pinned),
        "unwrap_status": str(unwrap_status),
        "residual_max": result.residual_max,
        "axis_parallel_violations": len(result.axis_parallel_violations),
    }
