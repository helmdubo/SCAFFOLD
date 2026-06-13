"""
Layer: 5 - Runtime

Rules:
- The ONLY bpy write boundary in scaffold_core (G5a phase rule).
- Writes pinned skeleton UVs via bmesh in the mesh's current mode; it does
  NOT call any bpy operator (mode_set/unwrap), so it cannot trigger an
  operator-context segfault. The artist runs U > Unwrap for the conformal
  fill; Blender respects the pins this writes.
- bpy/bmesh are imported lazily inside the function so headless suites
  never load them.
"""

from __future__ import annotations

from typing import Any

from scaffold_core.layer_5_runtime.pins import SolveResult


def write_pinned_uvs(blender_context: Any, result: SolveResult) -> dict[str, Any]:
    """Write skeleton UVs + pin flags onto the active mesh (no operators)."""

    import bpy  # noqa: F401 - the G5 write boundary; never imported headlessly
    import bmesh

    mesh_object = _resolve_mesh_object(blender_context)
    if mesh_object is None:
        raise ValueError("Active object is not a mesh; select the mesh and retry.")
    mesh = mesh_object.data

    by_vertex_patch = {
        (vertex.source_vertex_id, vertex.patch_id): vertex for vertex in result.vertices
    }
    by_vertex: dict[str, Any] = {}
    for vertex in result.vertices:
        by_vertex.setdefault(vertex.source_vertex_id, vertex)

    def _pinned_for(vertex_index: int, face_patch: str | None):
        key = f"v{vertex_index}"
        return by_vertex_patch.get((key, face_patch)) or by_vertex.get(key)

    written = 0
    if mesh_object.mode == "EDIT":
        bm = bmesh.from_edit_mesh(mesh)
        uv_layer = bm.loops.layers.uv.verify()
        for face in bm.faces:
            face_patch = result.patch_by_source_face.get(f"f{face.index}")
            for loop in face.loops:
                pinned = _pinned_for(loop.vert.index, face_patch)
                if pinned is None:
                    loop[uv_layer].pin_uv = False
                    continue
                loop[uv_layer].uv = pinned.uv
                loop[uv_layer].pin_uv = bool(pinned.pinned)
                written += 1
        bmesh.update_edit_mesh(mesh)
    else:
        uv_layer = mesh.uv_layers.active or mesh.uv_layers.new(name="UVMap")
        for polygon in mesh.polygons:
            face_patch = result.patch_by_source_face.get(f"f{polygon.index}")
            for loop_index in polygon.loop_indices:
                pinned = _pinned_for(mesh.loops[loop_index].vertex_index, face_patch)
                if pinned is None:
                    uv_layer.data[loop_index].pin_uv = False
                    continue
                uv_layer.data[loop_index].uv = pinned.uv
                uv_layer.data[loop_index].pin_uv = bool(pinned.pinned)
                written += 1

    return {
        "written_loops": written,
        "pinned_vertices": sum(1 for v in result.vertices if v.pinned),
        "residual_max": result.residual_max,
        "axis_parallel_violations": len(result.axis_parallel_violations),
        "next_step": "press U > Unwrap to fill the fabric (pins are respected)",
    }


def _resolve_mesh_object(blender_context: Any) -> Any:
    candidate = getattr(blender_context, "object", None)
    if candidate is not None and getattr(candidate, "type", None) == "MESH":
        return candidate
    for obj in getattr(blender_context, "selected_objects", ()):  # pragma: no cover
        if getattr(obj, "type", None) == "MESH":
            return obj
    return None
