from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Vector

try:
    from .console_debug import trace_console
    from .constants import FLOOR_THRESHOLD, WALL_THRESHOLD, WORLD_UP
    from .model import LoopKind, PatchType, WorldFacing
    from .analysis_records import (
        DirectionBucketKey,
        _AnalysisUvClassificationState,
        _LoopClassificationResult,
        _PlanarPoint2D,
        _PolygonEdgeLengthCandidate,
        _RawBoundaryLoop,
    )
except ImportError:
    from console_debug import trace_console
    from constants import FLOOR_THRESHOLD, WALL_THRESHOLD, WORLD_UP
    from model import LoopKind, PatchType, WorldFacing
    from analysis_records import (
        DirectionBucketKey,
        _AnalysisUvClassificationState,
        _LoopClassificationResult,
        _PlanarPoint2D,
        _PolygonEdgeLengthCandidate,
        _RawBoundaryLoop,
    )


def _find_island_up(patch_faces, avg_normal):
    """Find a stable local up direction for patch classification."""

    edge_dirs: dict[DirectionBucketKey, dict[str, object]] = {}
    for face in patch_faces:
        for edge in face.edges:
            length = edge.calc_length()
            if length < 1e-4:
                continue
            vec = (edge.verts[1].co - edge.verts[0].co).normalized()
            if vec.dot(WORLD_UP) < 0.0:
                vec = -vec
            key: DirectionBucketKey = (round(vec.x, 2), round(vec.y, 2), round(vec.z, 2))
            if key not in edge_dirs:
                edge_dirs[key] = {"vec": vec, "weight": 0.0}
            edge_dirs[key]["weight"] += length

    best_direct_up = WORLD_UP.copy()
    max_up_score = -1.0
    for data in edge_dirs.values():
        vec = data["vec"]
        alignment = abs(vec.dot(WORLD_UP))
        score = data["weight"] * (alignment ** 2)
        if score > max_up_score:
            max_up_score = score
            best_direct_up = vec

    best_right = None
    max_right_score = -1.0
    for data in edge_dirs.values():
        vec = data["vec"]
        horizontal = 1.0 - abs(vec.dot(WORLD_UP))
        score = data["weight"] * (horizontal ** 2)
        if score > max_right_score:
            max_right_score = score
            best_right = vec

    if max_right_score > max_up_score and best_right is not None:
        derived_up = avg_normal.cross(best_right)
        if derived_up.dot(WORLD_UP) < 0.0:
            derived_up = -derived_up
        if derived_up.length_squared > 1e-6:
            return derived_up.normalized()

    if max_up_score > 0.0:
        return best_direct_up.normalized()
    return WORLD_UP.copy()


def _classify_patch(bm, face_indices):
    """Classify a patch as WALL, FLOOR, or SLOPE."""

    patch_faces = [bm.faces[idx] for idx in face_indices]
    patch_face_set = set(patch_faces)
    avg_normal = Vector((0.0, 0.0, 0.0))
    total_area = 0.0
    perimeter = 0.0

    for face in patch_faces:
        face_area = face.calc_area()
        avg_normal += face.normal * face_area
        total_area += face_area
        for edge in face.edges:
            link_count = sum(1 for linked_face in edge.link_faces if linked_face in patch_face_set)
            if link_count == 1:
                perimeter += edge.calc_length()

    if avg_normal.length > 0.0:
        avg_normal.normalize()
    else:
        avg_normal = Vector((0.0, 0.0, 1.0))

    signed_up_dot = avg_normal.dot(WORLD_UP)
    up_dot = abs(signed_up_dot)
    if up_dot > FLOOR_THRESHOLD:
        patch_type = PatchType.FLOOR
    elif up_dot < WALL_THRESHOLD:
        patch_type = PatchType.WALL
    else:
        patch_type = PatchType.SLOPE

    if signed_up_dot > WALL_THRESHOLD:
        world_facing = WorldFacing.UP
    elif signed_up_dot < -WALL_THRESHOLD:
        world_facing = WorldFacing.DOWN
    else:
        world_facing = WorldFacing.SIDE

    return patch_type, world_facing, avg_normal, total_area, perimeter


def _calc_surface_basis(normal, ref_up=WORLD_UP):
    up_proj = ref_up - normal * ref_up.dot(normal)
    if up_proj.length_squared < 1e-5:
        tangent = Vector((1.0, 0.0, 0.0))
        tangent = (tangent - normal * tangent.dot(normal)).normalized()
        return tangent, normal.cross(tangent).normalized()
    bitangent = up_proj.normalized()
    return bitangent.cross(normal).normalized(), bitangent


def _build_patch_basis(bm, face_indices, patch_type, normal):
    """Build a local orthogonal basis for the patch."""

    patch_faces = [bm.faces[idx] for idx in face_indices]
    island_up = _find_island_up(patch_faces, normal)

    if patch_type in {PatchType.WALL, PatchType.SLOPE}:
        up_proj = WORLD_UP - normal * WORLD_UP.dot(normal)
        if up_proj.length_squared > 1e-8:
            basis_v = up_proj.normalized()
            basis_u = basis_v.cross(normal).normalized()
        else:
            basis_u, basis_v = _calc_surface_basis(normal, island_up)
    else:
        sorted_faces = sorted(
            patch_faces,
            key=lambda face: face.calc_area() * (max(0.0, face.normal.dot(normal)) ** 4),
            reverse=True,
        )
        seed_face = sorted_faces[0] if sorted_faces else patch_faces[0]
        basis_u, basis_v = _calc_surface_basis(seed_face.normal, island_up)

    return basis_u, basis_v


def _signed_area_2d(poly):
    area = 0.0
    count = len(poly)
    for idx in range(count):
        x1, y1 = poly[idx].x, poly[idx].y
        x2, y2 = poly[(idx + 1) % count].x, poly[(idx + 1) % count].y
        area += x1 * y2 - x2 * y1
    return 0.5 * area


def _point_in_polygon_2d(point, poly):
    x, y = point.x, point.y
    inside = False
    count = len(poly)
    for idx in range(count):
        x1, y1 = poly[idx].x, poly[idx].y
        x2, y2 = poly[(idx + 1) % count].x, poly[(idx + 1) % count].y
        if (y1 > y) != (y2 > y):
            x_intersection = (x2 - x1) * (y - y1) / (y2 - y1 + 1e-30) + x1
            if x < x_intersection:
                inside = not inside
    return inside


def _polygon_perimeter_2d(poly):
    perimeter = 0.0
    count = len(poly)
    for idx in range(count):
        x1, y1 = poly[idx].x, poly[idx].y
        x2, y2 = poly[(idx + 1) % count].x, poly[(idx + 1) % count].y
        dx = x2 - x1
        dy = y2 - y1
        perimeter += math.sqrt(dx * dx + dy * dy)
    return perimeter


def _select_polygon_interior_point(poly):
    if len(poly) < 3:
        return poly[0] if poly else _PlanarPoint2D(0.0, 0.0)

    signed_area = _signed_area_2d(poly)
    edges_by_len: list[_PolygonEdgeLengthCandidate] = []
    for idx in range(len(poly)):
        next_idx = (idx + 1) % len(poly)
        dx = poly[next_idx].x - poly[idx].x
        dy = poly[next_idx].y - poly[idx].y
        edges_by_len.append(_PolygonEdgeLengthCandidate(dx * dx + dy * dy, idx))
    edges_by_len.sort(reverse=True)

    for edge_candidate in edges_by_len:
        next_idx = (edge_candidate.index + 1) % len(poly)
        mid_x = (poly[edge_candidate.index].x + poly[next_idx].x) * 0.5
        mid_y = (poly[edge_candidate.index].y + poly[next_idx].y) * 0.5
        dx = poly[next_idx].x - poly[edge_candidate.index].x
        dy = poly[next_idx].y - poly[edge_candidate.index].y
        edge_len = math.sqrt(edge_candidate.len_squared)
        if edge_len < 1e-12:
            continue

        if signed_area >= 0.0:
            normal_x, normal_y = -dy / edge_len, dx / edge_len
        else:
            normal_x, normal_y = dy / edge_len, -dx / edge_len

        epsilon = edge_len * 0.01
        point = _PlanarPoint2D(mid_x + normal_x * epsilon, mid_y + normal_y * epsilon)
        if _point_in_polygon_2d(point, poly):
            return point

    return _PlanarPoint2D(
        sum(point.x for point in poly) / len(poly),
        sum(point.y for point in poly) / len(poly),
    )


def _project_raw_loop_to_patch_plane(raw_loop, basis_u, basis_v):
    return [
        _PlanarPoint2D(point.dot(basis_u), point.dot(basis_v))
        for point in raw_loop.vert_cos
    ]


def _classify_raw_loops_by_nesting_depth(raw_loops, basis_u, basis_v):
    """Classify raw loops as OUTER or HOLE via planar nesting in patch-local basis."""

    if not raw_loops:
        return

    if len(raw_loops) == 1:
        raw_loops[0].kind = LoopKind.OUTER
        raw_loops[0].depth = 0
        return

    polys_2d = [
        _project_raw_loop_to_patch_plane(raw_loop, basis_u, basis_v)
        for raw_loop in raw_loops
    ]
    interior_points = [_select_polygon_interior_point(poly) for poly in polys_2d]

    for loop_index, raw_loop in enumerate(raw_loops):
        depth = 0
        for poly_index, poly in enumerate(polys_2d):
            if loop_index == poly_index:
                continue
            if _point_in_polygon_2d(interior_points[loop_index], poly):
                depth += 1

        raw_loop.depth = depth
        raw_loop.kind = LoopKind.OUTER if depth % 2 == 0 else LoopKind.HOLE


def _prepare_outer_hole_classification_inputs(raw_patch_data):
    """Normalize trivial loop kinds and collect only multi-loop patches for classification."""

    classification_inputs = []

    for patch_id, patch_data in raw_patch_data.items():
        if len(patch_data.raw_loops) <= 1:
            for raw_loop in patch_data.raw_loops:
                raw_loop.kind = LoopKind.OUTER
                raw_loop.depth = 0
            continue
        classification_inputs.append((patch_id, patch_data))

    return classification_inputs


def _repair_disconnected_uv_loop_classification(raw_loops, polys_2d, patch_id):
    """Fallback: если UV unwrap развалил nesting, оставляем самый доминантный loop внешним."""

    outer_loop_indices = [
        loop_index
        for loop_index, raw_loop in enumerate(raw_loops)
        if raw_loop.kind == LoopKind.OUTER
    ]
    if len(outer_loop_indices) <= 1:
        return

    if any(raw_loop.kind == LoopKind.HOLE for raw_loop in raw_loops):
        return

    dominant_loop_index = max(
        range(len(raw_loops)),
        key=lambda loop_index: (
            abs(_signed_area_2d(polys_2d[loop_index])),
            _polygon_perimeter_2d(polys_2d[loop_index]),
            len(polys_2d[loop_index]),
            -loop_index,
        ),
    )

    for loop_index, raw_loop in enumerate(raw_loops):
        if loop_index == dominant_loop_index:
            raw_loop.depth = 0
            raw_loop.kind = LoopKind.OUTER
            continue
        raw_loop.depth = max(1, raw_loop.depth)
        raw_loop.kind = LoopKind.HOLE

    trace_console(
        f"[CFTUV][LoopClassDiag] Patch {patch_id} "
        f"uv_outer_repair dominant_loop={dominant_loop_index} outer_before={len(outer_loop_indices)}"
    )


def _repair_missing_outer_uv_loop_classification(raw_loops, basis_u, basis_v, patch_id):
    """Fallback: UV pass produced zero OUTER loops, promote the longest loop to OUTER."""

    _ = basis_u, basis_v

    outer_loop_count = sum(1 for raw_loop in raw_loops if raw_loop.kind == LoopKind.OUTER)
    if outer_loop_count > 0:
        return

    def raw_loop_perimeter(raw_loop):
        if len(raw_loop.vert_cos) < 2:
            return 0.0
        perimeter = 0.0
        for index, point in enumerate(raw_loop.vert_cos):
            next_point = raw_loop.vert_cos[(index + 1) % len(raw_loop.vert_cos)]
            perimeter += (next_point - point).length
        return perimeter

    dominant_loop_index = max(
        range(len(raw_loops)),
        key=lambda loop_index: (
            raw_loop_perimeter(raw_loops[loop_index]),
            len(raw_loops[loop_index].vert_cos),
            -loop_index,
        ),
    )

    for loop_index, raw_loop in enumerate(raw_loops):
        if loop_index == dominant_loop_index:
            raw_loop.depth = 0
            raw_loop.kind = LoopKind.OUTER
            continue
        if raw_loop.depth <= 0:
            raw_loop.depth = 1
        elif raw_loop.depth % 2 == 0:
            raw_loop.depth += 1
        raw_loop.kind = LoopKind.HOLE

    trace_console(
        f"[CFTUV][LoopClassDiag] Patch {patch_id} "
        f"uv_zero_outer_repair dominant_loop={dominant_loop_index} "
        f"length={raw_loop_perimeter(raw_loops[dominant_loop_index]):.4f}"
    )


def _classify_raw_loops_via_temporary_uv(raw_loops, bm, patch_face_indices, uv_layer, patch_id):
    """Classify raw loops as OUTER or HOLE inside the temporary analysis UV boundary."""

    if not raw_loops:
        return

    if len(raw_loops) == 1:
        raw_loops[0].kind = LoopKind.OUTER
        raw_loops[0].depth = 0
        return

    patch_face_indices = set(patch_face_indices)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    def get_side_uv(face_index, edge_index, vert_index):
        face = bm.faces[face_index]
        for loop in face.loops:
            if loop.edge.index == edge_index and loop.vert.index == vert_index:
                uv = loop[uv_layer].uv
                return _PlanarPoint2D(uv.x, uv.y)

        vert = bm.verts[vert_index]
        uvs = [loop[uv_layer].uv for loop in vert.link_loops if loop.face.index in patch_face_indices]
        if not uvs:
            return _PlanarPoint2D(0.0, 0.0)
        return _PlanarPoint2D(
            sum(uv.x for uv in uvs) / len(uvs),
            sum(uv.y for uv in uvs) / len(uvs),
        )

    polys_2d = []
    for raw_loop in raw_loops:
        poly = []
        for face_index, edge_index, vert_index in zip(
            raw_loop.side_face_indices,
            raw_loop.edge_indices,
            raw_loop.vert_indices,
        ):
            poly.append(get_side_uv(face_index, edge_index, vert_index))
        polys_2d.append(poly)

    interior_points = [_select_polygon_interior_point(poly) for poly in polys_2d]

    for loop_index, raw_loop in enumerate(raw_loops):
        depth = 0
        for poly_index, poly in enumerate(polys_2d):
            if loop_index == poly_index:
                continue
            if _point_in_polygon_2d(interior_points[loop_index], poly):
                depth += 1

        raw_loop.depth = depth
        raw_loop.kind = LoopKind.OUTER if depth == 0 or depth % 2 == 0 else LoopKind.HOLE

    _repair_disconnected_uv_loop_classification(raw_loops, polys_2d, patch_id)


def _collect_patch_self_seam_edge_indices(bm, patch_face_indices):
    """Для UV-классификации временно игнорируем seam'ы, замыкающиеся внутри того же patch."""

    patch_face_index_set = set(patch_face_indices)
    seam_edge_indices = []
    for face_index in patch_face_index_set:
        face = bm.faces[face_index]
        for edge in face.edges:
            if not edge.seam:
                continue
            in_patch_count = sum(
                1 for linked_face in edge.link_faces if linked_face.index in patch_face_index_set
            )
            if in_patch_count >= 2:
                seam_edge_indices.append(edge.index)
    return tuple(sorted(set(seam_edge_indices)))


def _set_face_selection(bm, face_indices):
    """Apply face selection explicitly for the temporary analysis UV boundary."""

    bm.faces.ensure_lookup_table()
    face_index_set = set(face_indices)
    for face in bm.faces:
        face.select = face.index in face_index_set


def _allocate_analysis_temp_uv_layer(bm, obj, base_name="_cftuv_temp_outer_hole"):
    """Create a fresh temporary UV layer so rollback never touches persistent user layers."""

    uv_name = base_name
    suffix = 1
    while bm.loops.layers.uv.get(uv_name) is not None or uv_name in obj.data.uv_layers:
        uv_name = f"{base_name}_{suffix}"
        suffix += 1

    return uv_name, bm.loops.layers.uv.new(uv_name)


def _begin_analysis_uv_classification(bm, obj):
    """Enter the explicit UV-dependent OUTER/HOLE analysis boundary."""

    state = _AnalysisUvClassificationState(
        original_active_uv_name=obj.data.uv_layers.active.name if obj.data.uv_layers.active else None,
        original_selection=[face.index for face in bm.faces if face.select],
    )
    state.temp_uv_name, uv_layer = _allocate_analysis_temp_uv_layer(bm, obj)

    try:
        bmesh.update_edit_mesh(obj.data)
        if state.temp_uv_name in obj.data.uv_layers:
            obj.data.uv_layers[state.temp_uv_name].active = True

        _set_face_selection(bm, [])
    except Exception:
        _finish_analysis_uv_classification(bm, obj, uv_layer, state)
        raise

    return uv_layer, state


def _finish_analysis_uv_classification(bm, obj, uv_layer, state):
    """Restore mesh selection and active UV after temporary OUTER/HOLE classification."""

    if uv_layer is not None:
        bm.loops.layers.uv.remove(uv_layer)

    _set_face_selection(bm, state.original_selection)
    bmesh.update_edit_mesh(obj.data)

    if state.original_active_uv_name and state.original_active_uv_name in obj.data.uv_layers:
        obj.data.uv_layers[state.original_active_uv_name].active = True


def _unwrap_patch_faces_for_loop_classification(bm, obj, patch_face_indices, disabled_seam_edge_indices=()):
    """Run temporary unwrap for one patch inside the analysis UV boundary."""

    disabled_edges = [bm.edges[edge_index] for edge_index in disabled_seam_edge_indices]
    original_seam_flags = [edge.seam for edge in disabled_edges]

    try:
        for edge in disabled_edges:
            edge.seam = False

        _set_face_selection(bm, patch_face_indices)
        bmesh.update_edit_mesh(obj.data)
        bpy.ops.uv.unwrap(method="CONFORMAL", fill_holes=False, margin=0.0)
        _set_face_selection(bm, [])
    finally:
        for edge, seam_flag in zip(disabled_edges, original_seam_flags):
            edge.seam = seam_flag
        bmesh.update_edit_mesh(obj.data)


def _classify_multi_loop_patches_via_uv(bm, classification_inputs, obj):
    """Execute the only sanctioned analysis-side-effect pass for OUTER/HOLE classification."""

    uv_layer = None
    state = None

    try:
        uv_layer, state = _begin_analysis_uv_classification(bm, obj)
        for patch_id, patch_data in classification_inputs:
            disabled_seam_edge_indices = _collect_patch_self_seam_edge_indices(
                bm,
                patch_data.face_indices,
            )
            _unwrap_patch_faces_for_loop_classification(
                bm,
                obj,
                patch_data.face_indices,
                disabled_seam_edge_indices=disabled_seam_edge_indices,
            )
            _classify_raw_loops_via_temporary_uv(
                patch_data.raw_loops,
                bm,
                patch_data.face_indices,
                uv_layer,
                patch_id,
            )
            _repair_missing_outer_uv_loop_classification(
                patch_data.raw_loops,
                patch_data.basis_u,
                patch_data.basis_v,
                patch_id,
            )
    finally:
        if uv_layer is not None and state is not None:
            _finish_analysis_uv_classification(bm, obj, uv_layer, state)


def _classify_multi_loop_patches_by_nesting(classification_inputs):
    """Diagnostics-only planar OUTER/HOLE classification helper."""

    for _, patch_data in classification_inputs:
        _classify_raw_loops_by_nesting_depth(
            patch_data.raw_loops,
            patch_data.basis_u,
            patch_data.basis_v,
        )


def _snapshot_planar_loop_classification(raw_loops, basis_u, basis_v):
    """Run planar loop classification on shadow copies for diagnostics only."""

    shadow_loops = [
        _RawBoundaryLoop(
            vert_indices=list(raw_loop.vert_indices),
            vert_cos=list(raw_loop.vert_cos),
            edge_indices=list(raw_loop.edge_indices),
            side_face_indices=list(raw_loop.side_face_indices),
            kind=raw_loop.kind,
            depth=raw_loop.depth,
            closed=raw_loop.closed,
        )
        for raw_loop in raw_loops
    ]
    _classify_raw_loops_by_nesting_depth(shadow_loops, basis_u, basis_v)
    return tuple(
        _LoopClassificationResult(kind=shadow_loop.kind, depth=shadow_loop.depth)
        for shadow_loop in shadow_loops
    )


def _classify_loops_outer_hole(bm, raw_patch_data, obj=None):
    """Classify loops as OUTER or HOLE through the explicit UV-dependent analysis boundary."""

    if not raw_patch_data:
        return

    classification_inputs = _prepare_outer_hole_classification_inputs(raw_patch_data)
    if not classification_inputs:
        return

    if obj is None or obj.type != "MESH":
        return

    _classify_multi_loop_patches_via_uv(bm, classification_inputs, obj)
