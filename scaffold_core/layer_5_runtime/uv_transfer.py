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

    active_object = blender_context.object
    mesh = active_object.data
    uv_layer = mesh.uv_layers.active or mesh.uv_layers.new(name="UVMap")
    by_vertex_patch = {
        (vertex.source_vertex_id, vertex.patch_id): vertex for vertex in result.vertices
    }
    by_vertex = {}
    for vertex in result.vertices:
        by_vertex.setdefault(vertex.source_vertex_id, vertex)
    written = 0
    for polygon in mesh.polygons:
        face_patch = result.patch_by_source_face.get(f"f{polygon.index}")
        for loop_index in polygon.loop_indices:
            loop = mesh.loops[loop_index]
            key = f"v{loop.vertex_index}"
            pinned_vertex = by_vertex_patch.get((key, face_patch)) or by_vertex.get(key)
            if pinned_vertex is None:
                uv_layer.data[loop_index].pin_uv = False
                continue
            uv_layer.data[loop_index].uv = pinned_vertex.uv
            uv_layer.data[loop_index].pin_uv = pinned_vertex.pinned
            written += 1
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    unwrap_status = bpy.ops.uv.unwrap(method="CONFORMAL")
    bpy.ops.object.mode_set(mode="OBJECT")
    return {
        "written_loops": written,
        "pinned_vertices": sum(1 for v in result.vertices if v.pinned),
        "unwrap_status": str(unwrap_status),
        "residual_max": result.residual_max,
        "axis_parallel_violations": len(result.axis_parallel_violations),
    }
