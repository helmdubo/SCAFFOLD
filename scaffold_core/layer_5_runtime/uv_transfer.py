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
  takes only the target object into Edit Mode (the unwrap operator needs
  Edit Mode and unwraps every object in it), writes the pins there and
  returns, restoring the object selection and the active object also when
  the unwrap fails; from Edit Mode it calls no mode_set, and it refuses
  before changing anything when another object is in Edit Mode with the
  target. No other object's UVs change.
- After the unwrap, write_quilt_uvs restores the layout's scale of every
  chart (a connected set of solved faces under the cut set) that has fewer
  than two distinct pinned UV positions: Blender gives such a chart a scale
  of its own. The chart is scaled uniformly so that its UV area is its 3D
  area (bmesh, the mesh's own coordinates) times LAYOUT_UV_PER_MESH_UNIT
  squared, about its one pin (pinned loops are never written), otherwise
  about the centroid of its UVs. Charts with two or more distinct pins are
  never touched. No rotation, packing or translation: an unpinned chart
  stays where Blender put it, scaled about its centre, and may overlap
  another chart. A chart with zero UV or zero 3D area is left as it is and
  counted.
- bpy/bmesh are imported lazily inside the function so headless suites
  never load them.
"""

from __future__ import annotations

from typing import Any

from scaffold_core.layer_5_runtime.pins import SolveResult

# The pinned layout's scale. Layer 5 lays the Layer 2 lengths as they are,
# measured in the mesh's own coordinates (Layer 0 reads vertex.co), so one UV
# unit is one mesh unit; nothing in the solve scales them.
LAYOUT_UV_PER_MESH_UNIT = 1.0
# Two pinned UV positions closer than this count as one.
PIN_POSITION_TOLERANCE = 1e-6


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
    selection, are restored afterwards, even when the unwrap fails. Between
    the unwrap and the restore, a chart with fewer than two distinct pins is
    given the layout's scale (see the module rules); the result counts the
    charts by pins and reports the rescaled charts' linear scale range.
    """

    import bpy
    import bmesh

    mesh_object = _resolve_mesh_object(blender_context)
    if mesh_object is None:
        raise ValueError("Active object is not a mesh; select the mesh and retry.")
    mesh = mesh_object.data
    view_layer = bpy.context.view_layer
    started_in_edit = mesh_object.mode == "EDIT"
    if started_in_edit:
        others = sorted(o.name for o in view_layer.objects if o != mesh_object and o.mode == "EDIT")
        if others:
            raise RuntimeError(
                "other objects are in Edit Mode with the target and the unwrap would change their UVs too; "
                f"leave Edit Mode on them and retry: {', '.join(others[:5])}"
            )
    previous_active = view_layer.objects.active
    previous_selected = [o for o in view_layer.objects if o.select_get()]
    if not started_in_edit:
        # Only the target enters Edit Mode, so the unwrap sees no other object.
        for other in previous_selected:
            other.select_set(False)
        mesh_object.select_set(True)
        view_layer.objects.active = mesh_object
    try:
        if not started_in_edit:
            bpy.ops.object.mode_set(mode="EDIT")
        # Pins are written in Edit Mode, the mode of the unwrap.
        summary = write_pinned_uvs(blender_context, result)
        summary.update(_unwrap_quilts(bpy, bmesh, mesh, result))
    finally:
        if not started_in_edit:
            if mesh_object.mode == "EDIT":
                bpy.ops.object.mode_set(mode="OBJECT")
            mesh_object.select_set(mesh_object in previous_selected)
            for other in previous_selected:
                other.select_set(True)
            view_layer.objects.active = previous_active
    return summary


def _unwrap_quilts(bpy: Any, bmesh: Any, mesh: Any, result: SolveResult) -> dict[str, Any]:
    """Seams to the cut set, conformal unwrap, loose charts rescaled, seams and selection restored (Edit Mode)."""

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
        bm = bmesh.from_edit_mesh(mesh)
        rescale = _rescale_loose_charts(bm, solved, cut)
        bmesh.update_edit_mesh(mesh)
    finally:
        bm = bmesh.from_edit_mesh(mesh)
        for edge, seam in zip(bm.edges, seams):
            edge.seam = seam
        for items, flags in zip((bm.verts, bm.edges, bm.faces), selection):
            for item, flag in zip(items, flags):
                item.select = flag
        bmesh.update_edit_mesh(mesh)
        restored = sum(1 for edge, seam in zip(bm.edges, seams) if edge.seam != seam)
    return {
        "quilts": len(result.assembly.islands),
        "uv_cut_edges": cut_edges,
        "seam_flags_changed": restored,
        **rescale,
        "next_step": "quilts laid by the conformal unwrap; seams unchanged",
    }


def chart_rescale_factor(
    uv_area: float, area_3d: float, layout_scale: float = LAYOUT_UV_PER_MESH_UNIT
) -> float | None:
    """Linear factor that gives a chart of uv_area the UV area area_3d * layout_scale**2.

    None for a degenerate chart (no UV area or no 3D area): it is left alone.
    """

    if not (uv_area > 0.0 and area_3d > 0.0 and layout_scale > 0.0):
        return None
    return (area_3d / uv_area) ** 0.5 * layout_scale


def polygon_uv_area(points: list[tuple[float, float]]) -> float:
    """Unsigned shoelace area of one face's UV polygon."""

    count = len(points)
    return abs(sum(
        points[k][0] * points[(k + 1) % count][1] - points[(k + 1) % count][0] * points[k][1]
        for k in range(count)
    )) / 2.0


def _rescale_loose_charts(bm: Any, solved: set[int], cut: frozenset[str]) -> dict[str, Any]:
    """Give every chart with fewer than two distinct pinned UV positions the layout's scale."""

    bm.edges.index_update()
    bm.faces.index_update()
    uv_layer = bm.loops.layers.uv.verify()
    by_pins ={"0": 0, "1": 0, "2+": 0}
    rescaled = 0
    degenerate = 0
    before: list[float] = []
    after: list[float] = []
    seen: set[int] = set()
    for start in bm.faces:
        if start.index not in solved or start.index in seen:
            continue
        chart, stack = [], [start]
        seen.add(start.index)
        while stack:  # one chart: solved faces joined by an edge that is not a UV cut
            face = stack.pop()
            chart.append(face)
            for edge in face.edges:
                if f"e{edge.index}" in cut:
                    continue
                for other in edge.link_faces:
                    if other.index in solved and other.index not in seen:
                        seen.add(other.index)
                        stack.append(other)
        loops = [loop for face in chart for loop in face.loops]
        pins = [tuple(loop[uv_layer].uv) for loop in loops if loop[uv_layer].pin_uv]
        if any(
            max(abs(pin[0] - pins[0][0]), abs(pin[1] - pins[0][1])) > PIN_POSITION_TOLERANCE for pin in pins
        ):
            by_pins["2+"] += 1
            continue  # the pins hold this chart's scale
        by_pins["1" if pins else "0"] += 1
        area_3d = sum(face.calc_area() for face in chart)
        uv_area = sum(polygon_uv_area([tuple(loop[uv_layer].uv) for loop in face.loops]) for face in chart)
        factor = chart_rescale_factor(uv_area, area_3d)
        if factor is None:
            degenerate += 1
            continue
        if pins:
            pivot = pins[0]
        else:
            pivot = (
                sum(loop[uv_layer].uv[0] for loop in loops) / len(loops),
                sum(loop[uv_layer].uv[1] for loop in loops) / len(loops),
            )
        for loop in loops:
            if loop[uv_layer].pin_uv:
                continue  # a pin is never written
            u, v = loop[uv_layer].uv
            loop[uv_layer].uv = (pivot[0] + (u - pivot[0]) * factor, pivot[1] + (v - pivot[1]) * factor)
        rescaled += 1
        before.append((uv_area / area_3d) ** 0.5 / LAYOUT_UV_PER_MESH_UNIT)
        new_area = sum(polygon_uv_area([tuple(loop[uv_layer].uv) for loop in face.loops]) for face in chart)
        after.append((new_area / area_3d) ** 0.5 / LAYOUT_UV_PER_MESH_UNIT)
    return {
        "charts_by_pins": by_pins,
        "charts_rescaled": rescaled,
        "charts_degenerate": degenerate,
        "rescaled_scale_before": (min(before), max(before)) if before else None,
        "rescaled_scale_after": (min(after), max(after)) if after else None,
    }


def _resolve_mesh_object(blender_context: Any) -> Any:
    candidate = getattr(blender_context, "object", None)
    if candidate is not None and getattr(candidate, "type", None) == "MESH":
        return candidate
    for obj in getattr(blender_context, "selected_objects", ()):  # pragma: no cover
        if getattr(obj, "type", None) == "MESH":
            return obj
    return None
