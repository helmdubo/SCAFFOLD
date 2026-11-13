"""
Layer: 5 - Runtime

Rules:
- The ONLY bpy write boundary in scaffold_core (G5a phase rule).
- write_pinned_uvs writes pinned skeleton UVs via bmesh in the mesh's
  current mode and calls no bpy operator; the artist runs U > Unwrap for the
  conformal fill, and Blender respects the pins it writes.
- write_quilt_uvs (plan Slice AH) lays the quilts: it writes the same pins,
  sets the seam flags of the solved faces' edges to exactly the UV cut set
  of the solve (so each quilt is one chart), runs Blender's conformal unwrap
  on the solved faces and restores every seam flag and the selection in a
  finally block. The user's seams are never changed. From Object Mode it
  enters Edit Mode for the unwrap and returns (the unwrap operator needs
  Edit Mode); from Edit Mode it calls no mode_set.
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
        (vertex.vertex_id, vertex.patch_id): vertex for vertex in result.vertices
    }

    def _pinned_for(face_index: int, vertex_index: int, face_patch: str | None):
        # Only the loop's own occurrence: never another seam side's or patch's pin.
        corner = (f"f{face_index}", f"v{vertex_index}")
        return by_vertex_patch.get((result.vertex_by_face_corner.get(corner), face_patch))

    written = 0
    if mesh_object.mode == "EDIT":
        bm = bmesh.from_edit_mesh(mesh)
        uv_layer = bm.loops.layers.uv.verify()
        for face in bm.faces:
            face_patch = result.patch_by_source_face.get(f"f{face.index}")
            if face_patch is None:
                continue  # outside the solved selection: never touch its loops
            for loop in face.loops:
                pinned = _pinned_for(face.index, loop.vert.index, face_patch)
                if pinned is None:
                    loop[uv_layer].pin_uv = False
                    continue
                loop[uv_layer].uv = pinned.uv
                loop[uv_layer].pin_uv = bool(pinned.pinned)
                written += 1
        bmesh.update_edit_mesh(mesh)
    else:
        bm = bmesh.new()
        try:
            bm.from_mesh(mesh)
            bm.faces.ensure_lookup_table()
            uv_layer = bm.loops.layers.uv.verify()
            for face in bm.faces:
                face_patch = result.patch_by_source_face.get(f"f{face.index}")
                if face_patch is None:
                    continue  # outside the solved selection: never touch its loops
                for loop in face.loops:
                    pinned = _pinned_for(face.index, loop.vert.index, face_patch)
                    if pinned is None:
                        loop[uv_layer].pin_uv = False
                        continue
                    loop[uv_layer].uv = pinned.uv
                    loop[uv_layer].pin_uv = bool(pinned.pinned)
                    written += 1
            bm.to_mesh(mesh)
            mesh.update()
        finally:
            bm.free()

    return {
        "written_loops": written,
        "pinned_vertices": sum(1 for v in result.vertices if v.pinned),
        "residual_max": result.residual_max,
        "axis_parallel_violations": len(result.axis_parallel_violations),
        "next_step": "press U > Unwrap to fill the fabric (pins are respected)",
    }


def write_quilt_uvs(blender_context: Any, result: SolveResult) -> dict[str, Any]:
    """Write the pins, then lay each quilt as one chart by Blender's conformal unwrap.

    For the unwrap only, a solved face's edge is a seam exactly when it is a
    UV cut of the solve (SolveResult.uv_cut_source_edge_ids); the seams the
    tree stitched are not cuts. Every seam flag, and the vertex, edge and face
    selection, are restored afterwards, even when the unwrap fails.
    """

    import bpy
    import bmesh

    summary = write_pinned_uvs(blender_context, result)
    mesh_object = _resolve_mesh_object(blender_context)
    mesh = mesh_object.data
    view_layer = bpy.context.view_layer
    previous_active = view_layer.objects.active
    started_in_edit = mesh_object.mode == "EDIT"
    if not started_in_edit:
        view_layer.objects.active = mesh_object
        bpy.ops.object.mode_set(mode="EDIT")
    cut = result.uv_cut_source_edge_ids
    solved = {int(face_id[1:]) for face_id in result.patch_by_source_face}
    bm = bmesh.from_edit_mesh(mesh)
    bm.edges.index_update()
    bm.faces.index_update()
    seams = [edge.seam for edge in bm.edges]
    selection = (
        [vertex.select for vertex in bm.verts],
        [edge.select for edge in bm.edges],
        [face.select for face in bm.faces],
    )
    cut_edges = 0
    try:
        for edge in bm.edges:
            if any(face.index in solved for face in edge.link_faces):
                edge.seam = f"e{edge.index}" in cut
                cut_edges += int(edge.seam)
        for face in bm.faces:
            face.select_set(face.index in solved)
        bmesh.update_edit_mesh(mesh)
        bpy.ops.uv.unwrap(method="CONFORMAL", fill_holes=False, margin=0.0)
    finally:
        bm = bmesh.from_edit_mesh(mesh)
        for edge, seam in zip(bm.edges, seams):
            edge.seam = seam
        for items, flags in zip((bm.verts, bm.edges, bm.faces), selection):
            for item, flag in zip(items, flags):
                item.select = flag
        bmesh.update_edit_mesh(mesh)
        restored = sum(1 for edge, seam in zip(bm.edges, seams) if edge.seam != seam)
        if not started_in_edit:
            bpy.ops.object.mode_set(mode="OBJECT")
            view_layer.objects.active = previous_active
    summary.update({
        "quilts": len(result.assembly.islands),
        "uv_cut_edges": cut_edges,
        "seam_flags_changed": restored,
        "next_step": "quilts laid by the conformal unwrap; seams unchanged",
    })
    return summary


def _resolve_mesh_object(blender_context: Any) -> Any:
    candidate = getattr(blender_context, "object", None)
    if candidate is not None and getattr(candidate, "type", None) == "MESH":
        return candidate
    for obj in getattr(blender_context, "selected_objects", ()):  # pragma: no cover
        if getattr(obj, "type", None) == "MESH":
            return obj
    return None
