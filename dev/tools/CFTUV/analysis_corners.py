from __future__ import annotations

import math

from mathutils import Vector

try:
    from .constants import (
        CORNER_ANGLE_THRESHOLD_DEG,
        FRAME_ALIGNMENT_THRESHOLD_H,
        FRAME_ALIGNMENT_THRESHOLD_V,
        FRAME_COMPOUND_LENGTH_THRESHOLD,
        SAWTOOTH_CHORD_AXIS_ALIGNMENT_MIN,
        SAWTOOTH_MIN_DIRECTION_REVERSALS,
        SAWTOOTH_PCA_EIGENVALUE_RATIO_MIN,
    )
    from .model import BoundaryCorner, CornerKind, FrameRole, LoopKind
    from .analysis_records import _RawBoundaryChain
    from .console_debug import trace_console
except ImportError:
    from constants import (
        CORNER_ANGLE_THRESHOLD_DEG,
        FRAME_ALIGNMENT_THRESHOLD_H,
        FRAME_ALIGNMENT_THRESHOLD_V,
        FRAME_COMPOUND_LENGTH_THRESHOLD,
        SAWTOOTH_CHORD_AXIS_ALIGNMENT_MIN,
        SAWTOOTH_MIN_DIRECTION_REVERSALS,
        SAWTOOTH_PCA_EIGENVALUE_RATIO_MIN,
    )
    from model import BoundaryCorner, CornerKind, FrameRole, LoopKind
    from analysis_records import _RawBoundaryChain
    from console_debug import trace_console


def _measure_chain_axis_metrics(chain_vert_cos, basis_u, basis_v):
    if len(chain_vert_cos) < 2:
        return None

    basis_n = basis_u.cross(basis_v)
    if basis_n.length_squared < 1e-8:
        return None
    basis_n.normalize()

    h_support = 0.0
    v_support = 0.0
    n_support = 0.0
    h_deviation_sum = 0.0
    v_deviation_sum = 0.0
    h_max_deviation = 0.0
    v_max_deviation = 0.0
    total_length = 0.0

    for point_index in range(len(chain_vert_cos) - 1):
        delta = chain_vert_cos[point_index + 1] - chain_vert_cos[point_index]
        seg_len = delta.length
        if seg_len < 1e-8:
            continue

        du = delta.dot(basis_u)
        dv = delta.dot(basis_v)
        dn = delta.dot(basis_n)
        abs_du = abs(du)
        abs_dv = abs(dv)
        abs_dn = abs(dn)
        nu_support = math.sqrt(abs_du * abs_du + abs_dn * abs_dn)
        nv_support = math.sqrt(abs_dv * abs_dv + abs_dn * abs_dn)

        # H_FRAME читается как направление в плоскости N-U:
        # допускаем изгиб по N, но штрафуем уход вдоль V.
        h_support += nu_support
        # V_FRAME читается как направление в плоскости N-V:
        # допускаем изгиб по N (дуга), но штрафуем уход вдоль U.
        v_support += nv_support
        n_support += abs_dn
        h_deviation = abs_dv / seg_len
        v_deviation = abs_du / seg_len
        h_deviation_sum += h_deviation * seg_len
        v_deviation_sum += v_deviation * seg_len
        h_max_deviation = max(h_max_deviation, h_deviation)
        v_max_deviation = max(v_max_deviation, v_deviation)
        total_length += seg_len

    if total_length < 1e-8:
        return None

    return {
        "h_support": h_support,
        "v_support": v_support,
        "n_support": n_support,
        "h_avg_deviation": h_deviation_sum / total_length,
        "v_avg_deviation": v_deviation_sum / total_length,
        "h_max_deviation": h_max_deviation,
        "v_max_deviation": v_max_deviation,
        "total_length": total_length,
    }


def _classify_chain_frame_role(chain_vert_cos, basis_u, basis_v, strict_guards=True):
    metrics = _measure_chain_axis_metrics(chain_vert_cos, basis_u, basis_v)
    if metrics is None:
        return FrameRole.FREE

    # Для wrapped H-chains допускаем немного больший drift по V,
    # если chain значимо уходит в N относительно среднего basis patch.
    normal_leakage_ratio = metrics["n_support"] / max(metrics["total_length"], 1e-8)
    threshold_h = max(FRAME_ALIGNMENT_THRESHOLD_H, FRAME_ALIGNMENT_THRESHOLD_V * normal_leakage_ratio)
    threshold_v = FRAME_ALIGNMENT_THRESHOLD_V
    if strict_guards:
        h_max_deviation_limit = max(threshold_h * 2.0, threshold_h + 0.03)
        v_max_deviation_limit = max(threshold_v * 2.0, threshold_v + 0.03)
    else:
        h_max_deviation_limit = max(threshold_h * 4.0, threshold_h + 0.08)
        v_max_deviation_limit = max(threshold_v * 4.0, threshold_v + 0.08)

    h_compound = metrics["h_avg_deviation"] * math.sqrt(metrics["total_length"])
    v_compound = metrics["v_avg_deviation"] * math.sqrt(metrics["total_length"])

    h_ok = (
        metrics["h_support"] > 1e-6
        and metrics["h_avg_deviation"] < threshold_h
        and metrics["h_max_deviation"] < h_max_deviation_limit
        and h_compound < FRAME_COMPOUND_LENGTH_THRESHOLD
    )
    v_ok = (
        metrics["v_support"] > 1e-6
        and metrics["v_avg_deviation"] < threshold_v
        and metrics["v_max_deviation"] < v_max_deviation_limit
        and v_compound < FRAME_COMPOUND_LENGTH_THRESHOLD
    )

    if h_ok and v_ok:
        if abs(metrics["h_avg_deviation"] - metrics["v_avg_deviation"]) > 1e-6:
            return FrameRole.H_FRAME if metrics["h_avg_deviation"] < metrics["v_avg_deviation"] else FrameRole.V_FRAME
        return FrameRole.H_FRAME if metrics["h_support"] >= metrics["v_support"] else FrameRole.V_FRAME
    if h_ok:
        return FrameRole.H_FRAME
    if v_ok:
        return FrameRole.V_FRAME
    return FrameRole.FREE


def _measure_sawtooth_signals(chain_vert_cos, basis_u, basis_v):
    """Один проход по polyline, возвращает сигналы для sawtooth-теста.

    Все сигналы считаются в 2D-проекции на плоскость (U, V) patch-базиса:
    нас не интересует уход в нормаль (как у strict-классификатора),
    интересует «насколько эта ломаная идёт по одной оси U или V».

    Возвращает dict или None для вырожденных случаев.
    """
    if len(chain_vert_cos) < 3:
        return None

    if basis_u.length_squared < 1e-12 or basis_v.length_squared < 1e-12:
        return None
    basis_u_n = basis_u.normalized()
    basis_v_n = basis_v.normalized()

    chord = chain_vert_cos[-1] - chain_vert_cos[0]
    chord_len = chord.length
    if chord_len < 1e-8:
        return None

    polyline_len = 0.0
    for point_index in range(len(chain_vert_cos) - 1):
        polyline_len += (chain_vert_cos[point_index + 1] - chain_vert_cos[point_index]).length
    if polyline_len < 1e-8:
        return None

    chord_polyline_ratio = chord_len / polyline_len

    chord_u_align = abs(chord.dot(basis_u_n)) / chord_len
    chord_v_align = abs(chord.dot(basis_v_n)) / chord_len
    if chord_u_align >= chord_v_align:
        preferred_axis = "H"
        chord_axis_alignment = chord_u_align
    else:
        preferred_axis = "V"
        chord_axis_alignment = chord_v_align

    # 2D-точки в (U, V), относительно первой вершины.
    first_point = chain_vert_cos[0]
    points_2d = []
    for point in chain_vert_cos:
        rel = point - first_point
        points_2d.append((rel.dot(basis_u_n), rel.dot(basis_v_n)))

    n_pts = len(points_2d)
    cx = sum(p[0] for p in points_2d) / n_pts
    cy = sum(p[1] for p in points_2d) / n_pts

    cxx = cyy = cxy = 0.0
    for x, y in points_2d:
        dx = x - cx
        dy = y - cy
        cxx += dx * dx
        cyy += dy * dy
        cxy += dx * dy
    cxx /= n_pts
    cyy /= n_pts
    cxy /= n_pts

    # Собственные числа симметричной 2×2:
    # λ = (cxx + cyy)/2 ± √(((cxx − cyy)/2)² + cxy²)
    half_trace = (cxx + cyy) * 0.5
    half_diff = (cxx - cyy) * 0.5
    disc = math.sqrt(half_diff * half_diff + cxy * cxy)
    lambda1 = half_trace + disc
    lambda2 = half_trace - disc
    if lambda1 < 1e-20:
        return None
    lambda2_safe = max(lambda2, lambda1 * 1e-9)
    pca_eigenvalue_ratio = lambda1 / lambda2_safe

    # Главный собственный вектор. cxy ≠ 0 → стандартная формула;
    # cxy = 0 → матрица уже диагональна.
    if abs(cxy) > 1e-20:
        ev1_x = lambda1 - cyy
        ev1_y = cxy
    elif cxx >= cyy:
        ev1_x, ev1_y = 1.0, 0.0
    else:
        ev1_x, ev1_y = 0.0, 1.0
    ev1_len = math.sqrt(ev1_x * ev1_x + ev1_y * ev1_y)
    if ev1_len < 1e-12:
        return None
    ev1_x /= ev1_len
    ev1_y /= ev1_len

    # В нашем 2D-фрейме оси U → (1,0), V → (0,1).
    if preferred_axis == "H":
        primary_axis_alignment = abs(ev1_x)
    else:
        primary_axis_alignment = abs(ev1_y)

    # Direction reversals: знак производной перпендикулярной-к-хорде
    # компоненты. Каждая смена знака — это локальный пик/впадина.
    # Прямая = 0, дуга = 1, S-кривая = 2, пила N зубцов ≈ 2N-1.
    # Ловит и cross-chord, и same-side варианты (паттерн «стена с
    # канавками все с одной стороны» даёт диагональный тренд, но
    # per-segment производная всё равно разворачивается на каждом зубе).
    chord_2d_x = points_2d[-1][0] - points_2d[0][0]
    chord_2d_y = points_2d[-1][1] - points_2d[0][1]
    chord_2d_len = math.sqrt(chord_2d_x * chord_2d_x + chord_2d_y * chord_2d_y)
    if chord_2d_len < 1e-8:
        return None
    perp_x = -chord_2d_y / chord_2d_len
    perp_y = chord_2d_x / chord_2d_len

    origin_x, origin_y = points_2d[0]
    sides = [(x - origin_x) * perp_x + (y - origin_y) * perp_y for x, y in points_2d]

    direction_reversals = 0
    prev_diff_sign = 0
    for index in range(len(sides) - 1):
        diff = sides[index + 1] - sides[index]
        if diff > 1e-9:
            cur_sign = 1
        elif diff < -1e-9:
            cur_sign = -1
        else:
            cur_sign = 0
        if cur_sign != 0 and prev_diff_sign != 0 and cur_sign != prev_diff_sign:
            direction_reversals += 1
        if cur_sign != 0:
            prev_diff_sign = cur_sign

    return {
        "chord_len": chord_len,
        "polyline_len": polyline_len,
        "chord_polyline_ratio": chord_polyline_ratio,
        "chord_axis_alignment": chord_axis_alignment,
        "pca_eigenvalue_ratio": pca_eigenvalue_ratio,
        "primary_axis_alignment": primary_axis_alignment,
        "direction_reversals": direction_reversals,
        "preferred_axis": preferred_axis,
    }


def _sawtooth_promoted_role(chain_vert_cos, basis_u, basis_v):
    """Fallback H/V промоушен для FREE chains, которые выглядят как пила
    вдоль одной оси patch (например, стена с декоративными канавками).

    Композитный тест: четыре независимых сигнала должны сойтись. Если
    любой не прошёл — возвращаем None (остаётся FREE).

    Возвращает FrameRole.H_FRAME / FrameRole.V_FRAME при промоушене.
    """
    signals = _measure_sawtooth_signals(chain_vert_cos, basis_u, basis_v)
    if signals is None:
        return None

    # Gate 1: хорда должна указывать вдоль одной оси patch.
    if signals["chord_axis_alignment"] < SAWTOOTH_CHORD_AXIS_ALIGNMENT_MIN:
        return None

    # Gate 2: PCA — главная ось проекции должна совпадать с той же осью
    # (ломаная — настоящая линия с шумом, а не диагональный пучок).
    if signals["primary_axis_alignment"] < SAWTOOTH_CHORD_AXIS_ALIGNMENT_MIN:
        return None
    if signals["pca_eigenvalue_ratio"] < SAWTOOTH_PCA_EIGENVALUE_RATIO_MIN:
        return None

    # Gate 3: зубы должны быть. Дуга = 1 reversal, S-кривая = 2, прямая = 0.
    # Порог ≥ 3 принимает 2+ зубца и отсекает всё перечисленное.
    if signals["direction_reversals"] < SAWTOOTH_MIN_DIRECTION_REVERSALS:
        return None

    if signals["preferred_axis"] == "H":
        return FrameRole.H_FRAME
    return FrameRole.V_FRAME


def _find_corner_reference_point(points, corner_co, reverse=False):
    """Find a non-degenerate neighbor point around a chain junction."""

    if reverse:
        candidates = list(reversed(points[:-1]))
    else:
        candidates = list(points[1:])

    for point in candidates:
        if (point - corner_co).length_squared > 1e-12:
            return point
    return None


def _measure_corner_turn_angle(corner_co, prev_point, next_point, basis_u, basis_v):
    """Measure the turn angle at a chain junction in patch-local 2D space."""

    if prev_point is None or next_point is None:
        return 0.0

    prev_vec_3d = corner_co - prev_point
    next_vec_3d = next_point - corner_co
    prev_vec = Vector((prev_vec_3d.dot(basis_u), prev_vec_3d.dot(basis_v)))
    next_vec = Vector((next_vec_3d.dot(basis_u), next_vec_3d.dot(basis_v)))
    if prev_vec.length_squared < 1e-12 or next_vec.length_squared < 1e-12:
        return 0.0

    return math.degrees(prev_vec.angle(next_vec, 0.0))


def _build_geometric_loop_corners(boundary_loop, basis_u, basis_v):
    """Build geometric corners directly from loop turns inside one chain."""

    vertex_count = len(boundary_loop.vert_cos)
    if vertex_count < 3:
        return []

    corners = []
    for loop_vert_index in range(vertex_count):
        corner_co = boundary_loop.vert_cos[loop_vert_index].copy()
        prev_point = boundary_loop.vert_cos[(loop_vert_index - 1) % vertex_count]
        next_point = boundary_loop.vert_cos[(loop_vert_index + 1) % vertex_count]
        turn_angle_deg = _measure_corner_turn_angle(corner_co, prev_point, next_point, basis_u, basis_v)
        if turn_angle_deg < CORNER_ANGLE_THRESHOLD_DEG:
            continue
        corners.append(
            BoundaryCorner(
                loop_vert_index=loop_vert_index,
                vert_index=boundary_loop.vert_indices[loop_vert_index] if loop_vert_index < len(boundary_loop.vert_indices) else -1,
                vert_co=corner_co,
                prev_chain_index=0,
                next_chain_index=0,
                corner_kind=CornerKind.GEOMETRIC,
                turn_angle_deg=turn_angle_deg,
                prev_role=FrameRole.FREE,
                next_role=FrameRole.FREE,
            )
        )

    return corners


def _measure_corner_turn_angle_3d(corner_co, prev_point, next_point):
    if prev_point is None or next_point is None:
        return 0.0

    prev_vec = corner_co - prev_point
    next_vec = next_point - corner_co
    if prev_vec.length_squared < 1e-12 or next_vec.length_squared < 1e-12:
        return 0.0

    return math.degrees(prev_vec.angle(next_vec, 0.0))


def _loop_arc_length(loop_vert_cos, start_loop_index, end_loop_index):
    vertex_count = len(loop_vert_cos)
    if vertex_count < 2:
        return 0.0

    length = 0.0
    loop_index = start_loop_index % vertex_count
    safety = 0
    while safety < vertex_count + 1:
        safety += 1
        next_loop_index = (loop_index + 1) % vertex_count
        length += (loop_vert_cos[next_loop_index] - loop_vert_cos[loop_index]).length
        loop_index = next_loop_index
        if loop_index == end_loop_index % vertex_count:
            break

    return length


def _is_tangent_plane_turn(corner_co, prev_point, next_point, vert_normal):
    edge_in = corner_co - prev_point
    edge_out = next_point - corner_co
    if edge_in.length_squared < 1e-12 or edge_out.length_squared < 1e-12:
        return True
    edge_in_n = edge_in.normalized()
    edge_out_n = edge_out.normalized()
    turn_axis = edge_in_n.cross(edge_out_n)
    if turn_axis.length_squared < 1e-12:
        return edge_in_n.dot(edge_out_n) >= -0.5
    alignment = abs(turn_axis.normalized().dot(vert_normal.normalized()))
    return alignment > 0.3


def _collect_closed_loop_corner_candidates(loop_vert_cos, basis_u, basis_v, loop_vert_indices=None, bm=None):
    vertex_count = len(loop_vert_cos)
    if vertex_count < 4:
        return [], []

    use_vert_normals = (loop_vert_indices is not None and bm is not None)
    if use_vert_normals:
        bm.verts.ensure_lookup_table()

    raw_candidates = []
    filtered_candidates = []
    for point_index in range(vertex_count):
        prev_point = loop_vert_cos[(point_index - 1) % vertex_count]
        corner_co = loop_vert_cos[point_index]
        next_point = loop_vert_cos[(point_index + 1) % vertex_count]
        turn_angle_deg = _measure_corner_turn_angle(corner_co, prev_point, next_point, basis_u, basis_v)
        trace_console(
            f"[CFTUV][GeoSplit] idx={point_index} turn={turn_angle_deg:.1f} "
            f"threshold={CORNER_ANGLE_THRESHOLD_DEG} use_normals={use_vert_normals}"
        )
        if turn_angle_deg < CORNER_ANGLE_THRESHOLD_DEG:
            continue

        candidate = (point_index, turn_angle_deg)
        raw_candidates.append(candidate)
        is_hairpin_turn = turn_angle_deg >= 150.0
        if is_hairpin_turn:
            turn_angle_3d = _measure_corner_turn_angle_3d(corner_co, prev_point, next_point)
            if turn_angle_3d < 120.0:
                trace_console(
                    f"[CFTUV][GeoSplit] skip idx={point_index} reason=projected_hairpin "
                    f"turn2d={turn_angle_deg:.1f} turn3d={turn_angle_3d:.1f}"
                )
                continue

        if use_vert_normals:
            vert_index = loop_vert_indices[point_index]
            if vert_index < len(bm.verts):
                vert_normal = bm.verts[vert_index].normal
                if vert_normal.length_squared > 1e-12 and not _is_tangent_plane_turn(
                    corner_co,
                    prev_point,
                    next_point,
                    vert_normal,
                ):
                    reason = "hairpin_not_tangent" if is_hairpin_turn else "bevel_not_tangent"
                    trace_console(
                        f"[CFTUV][GeoSplit] skip idx={point_index} reason={reason} "
                        f"turn2d={turn_angle_deg:.1f}"
                    )
                    continue

        filtered_candidates.append(candidate)

    return raw_candidates, filtered_candidates


def _filter_closed_corner_candidates_by_loop_spacing(loop_vert_cos, candidates, min_span_length, min_vertex_gap):
    if not candidates:
        return []

    vertex_count = len(loop_vert_cos)
    filtered = []
    for candidate in candidates:
        if not filtered:
            filtered.append(candidate)
            continue

        prev_candidate = filtered[-1]
        span_length = _loop_arc_length(loop_vert_cos, prev_candidate[0], candidate[0])
        span_vertex_count = (candidate[0] - prev_candidate[0]) % vertex_count
        if span_vertex_count < min_vertex_gap or span_length < min_span_length:
            if candidate[1] > prev_candidate[1]:
                filtered[-1] = candidate
            continue

        filtered.append(candidate)

    while len(filtered) >= 2:
        first_candidate = filtered[0]
        last_candidate = filtered[-1]
        wrap_span_length = _loop_arc_length(loop_vert_cos, last_candidate[0], first_candidate[0])
        wrap_span_vertex_count = (first_candidate[0] - last_candidate[0]) % vertex_count
        if wrap_span_vertex_count >= min_vertex_gap and wrap_span_length >= min_span_length:
            break

        if first_candidate[1] >= last_candidate[1]:
            filtered.pop()
        else:
            filtered.pop(0)

    return filtered


def _detect_closed_loop_corner_indices(loop_vert_cos, basis_u, basis_v, loop_vert_indices=None, bm=None):
    raw_candidates, candidate_corners = _collect_closed_loop_corner_candidates(
        loop_vert_cos,
        basis_u,
        basis_v,
        loop_vert_indices=loop_vert_indices,
        bm=bm,
    )
    if len(candidate_corners) < 4 and len(raw_candidates) >= 4:
        non_hairpin_candidates = [candidate for candidate in raw_candidates if candidate[1] < 150.0]
        if len(non_hairpin_candidates) >= 4:
            trace_console(f"[CFTUV][GeoSplit] fallback raw_non_hairpin candidates={len(non_hairpin_candidates)}")
            candidate_corners = non_hairpin_candidates

    if len(candidate_corners) < 4:
        return []

    perimeter = _loop_arc_length(loop_vert_cos, 0, 0)
    strict_min_span_length = max(perimeter * 0.04, 1e-4)
    filtered_corners = _filter_closed_corner_candidates_by_loop_spacing(
        loop_vert_cos,
        candidate_corners,
        strict_min_span_length,
        1,
    )
    if len(filtered_corners) < 4:
        relaxed_min_span_length = max(perimeter * 0.015, 1e-4)
        if relaxed_min_span_length < strict_min_span_length:
            relaxed_corners = _filter_closed_corner_candidates_by_loop_spacing(
                loop_vert_cos,
                candidate_corners,
                relaxed_min_span_length,
                1,
            )
            if len(relaxed_corners) >= 4:
                filtered_corners = relaxed_corners

    if len(filtered_corners) < 4:
        return []

    return [candidate[0] for candidate in filtered_corners]


def _split_closed_loop_by_corner_indices(raw_loop, split_indices, neighbor_patch_id):
    loop_vert_indices = list(raw_loop.vert_indices)
    loop_vert_cos = list(raw_loop.vert_cos)
    loop_edge_indices = list(raw_loop.edge_indices)
    loop_side_face_indices = list(raw_loop.side_face_indices)
    vertex_count = len(loop_vert_cos)
    edge_count = len(loop_edge_indices)
    if vertex_count < 2 or edge_count == 0:
        return []

    ordered_split_indices = sorted({loop_vert_index % vertex_count for loop_vert_index in split_indices})
    if len(ordered_split_indices) < 2:
        return []

    raw_chains = []
    split_count = len(ordered_split_indices)
    for split_index in range(split_count):
        start_loop_index = ordered_split_indices[split_index]
        end_loop_index = ordered_split_indices[(split_index + 1) % split_count]

        chain_vert_indices = []
        chain_vert_cos = []
        chain_edge_indices = []
        chain_side_face_indices = []

        loop_index = start_loop_index
        safety = 0
        while safety < vertex_count + 2:
            safety += 1
            chain_vert_indices.append(loop_vert_indices[loop_index % vertex_count])
            chain_vert_cos.append(loop_vert_cos[loop_index % vertex_count])
            chain_edge_indices.append(loop_edge_indices[loop_index % edge_count])
            chain_side_face_indices.append(loop_side_face_indices[loop_index % vertex_count])
            loop_index += 1
            if loop_index % vertex_count == end_loop_index % vertex_count:
                chain_vert_indices.append(loop_vert_indices[end_loop_index % vertex_count])
                chain_vert_cos.append(loop_vert_cos[end_loop_index % vertex_count])
                chain_side_face_indices.append(loop_side_face_indices[end_loop_index % vertex_count])
                break

        if len(chain_vert_indices) < 2:
            continue

        raw_chains.append(
            _RawBoundaryChain(
                vert_indices=chain_vert_indices,
                vert_cos=chain_vert_cos,
                edge_indices=chain_edge_indices,
                side_face_indices=chain_side_face_indices,
                neighbor=neighbor_patch_id,
                is_closed=False,
                start_loop_index=start_loop_index,
                end_loop_index=end_loop_index,
                is_corner_split=True,
            )
        )

    return raw_chains


def _try_geometric_outer_loop_split(raw_loop, raw_chains, basis_u, basis_v, bm=None):
    """Fallback split for one closed OUTER chain that collapsed around one neighbor."""

    loop_kind = raw_loop.kind
    if not isinstance(loop_kind, LoopKind):
        loop_kind = LoopKind(loop_kind)

    if loop_kind != LoopKind.OUTER or len(raw_chains) != 1:
        return raw_chains

    raw_chain = raw_chains[0]
    if not raw_chain.is_closed:
        return raw_chains

    split_indices = _detect_closed_loop_corner_indices(
        raw_loop.vert_cos,
        basis_u,
        basis_v,
        loop_vert_indices=raw_loop.vert_indices,
        bm=bm,
    )
    trace_console(f"[CFTUV][GeoSplit] split_indices={len(split_indices)} indices={split_indices}")
    if len(split_indices) < 4:
        trace_console("[CFTUV][GeoSplit] BAIL: <4 split indices")
        return raw_chains

    derived_raw_chains = _split_closed_loop_by_corner_indices(
        raw_loop,
        split_indices,
        int(raw_chain.neighbor),
    )
    trace_console(f"[CFTUV][GeoSplit] derived_chains={len(derived_raw_chains)}")
    if len(derived_raw_chains) < 4:
        trace_console("[CFTUV][GeoSplit] BAIL: <4 derived chains")
        return raw_chains

    derived_roles = []
    for derived_raw_chain in derived_raw_chains:
        strict_role = _classify_chain_frame_role(
            derived_raw_chain.vert_cos,
            basis_u,
            basis_v,
            strict_guards=False,
        )
        if strict_role == FrameRole.FREE:
            promoted = _sawtooth_promoted_role(derived_raw_chain.vert_cos, basis_u, basis_v)
            if promoted is not None:
                strict_role = promoted
        derived_roles.append(strict_role)
    trace_console(f"[CFTUV][GeoSplit] derived_roles={[role.value for role in derived_roles]}")
    non_free_count = sum(1 for role in derived_roles if role != FrameRole.FREE)
    if non_free_count < 1:
        trace_console("[CFTUV][GeoSplit] KEEP: all derived chains are FREE, preserving geometric split")
    trace_console(f"[CFTUV][GeoSplit] SUCCESS: split into {len(derived_raw_chains)} chains, non_free={non_free_count}")

    return derived_raw_chains
