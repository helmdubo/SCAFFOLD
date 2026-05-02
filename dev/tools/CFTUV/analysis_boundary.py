from __future__ import annotations

try:
    from .console_debug import trace_console
    from .model import (
        LoopKind,
    )
    from .analysis_records import (
        _RawBoundaryLoop,
        _BoundarySideKey,
        _LoopClassificationResult,
    )
    from .analysis_boundary_loops import (
        _build_boundary_loops,
        _validate_patch_loop_classification,
    )
    from .analysis_classification import (
        _snapshot_planar_loop_classification,
    )
except ImportError:
    from console_debug import trace_console
    from model import (
        LoopKind,
    )
    from analysis_records import (
        _RawBoundaryLoop,
        _BoundarySideKey,
        _LoopClassificationResult,
    )
    from analysis_boundary_loops import (
        _build_boundary_loops,
        _validate_patch_loop_classification,
    )
    from analysis_classification import (
        _snapshot_planar_loop_classification,
    )


def _report_boundary_loop_invariant_violation(patch_id, loop_index, rule_code, detail):
    trace_console(f"[CFTUV][TopologyInvariant] Patch {patch_id} Loop {loop_index} {rule_code} {detail}")


def _report_patch_topology_invariant_violation(patch_id, rule_code, detail):
    trace_console(f"[CFTUV][TopologyInvariant] Patch {patch_id} {rule_code} {detail}")


def _report_loop_classification_diagnostic(patch_id, detail):
    trace_console(f"[CFTUV][LoopClassDiag] Patch {patch_id} {detail}")


def _is_boundary_side(loop, patch_face_indices):
    edge = loop.edge
    in_patch_count = sum(1 for linked_face in edge.link_faces if linked_face.index in patch_face_indices)
    if len(edge.link_faces) == 1:
        return True
    if in_patch_count == 1:
        return True
    if in_patch_count >= 2 and edge.seam:
        return True
    return False


def _boundary_side_key(loop):
    return _BoundarySideKey(
        face_index=loop.face.index,
        edge_index=loop.edge.index,
        vert_index=loop.vert.index,
    )


def _find_next_boundary_side(loop, patch_face_indices):
    candidate = loop.link_loop_next
    safety = 0
    while safety < 200000:
        safety += 1
        if _is_boundary_side(candidate, patch_face_indices):
            return candidate

        radial = candidate.link_loop_radial_next
        if radial == candidate:
            return None

        next_radial = None
        probe = radial
        while True:
            if probe.face.index in patch_face_indices:
                next_radial = probe
                break
            probe = probe.link_loop_radial_next
            if probe == candidate:
                break

        if next_radial is None:
            return None

        candidate = next_radial.link_loop_next

    return None


def _trace_boundary_loops(patch_faces):
    patch_face_indices = {face.index for face in patch_faces}
    raw_loops = []
    used_sides = set()

    for face in patch_faces:
        for loop in face.loops:
            if not _is_boundary_side(loop, patch_face_indices):
                continue

            start_key = _boundary_side_key(loop)
            if start_key in used_sides:
                continue

            current = loop
            vert_indices = []
            vert_cos = []
            edge_indices = []
            side_face_indices = []
            closed = False
            safety = 0

            while safety < 200000:
                safety += 1
                current_key = _boundary_side_key(current)
                if current_key in used_sides:
                    break

                used_sides.add(current_key)
                vert_indices.append(current.vert.index)
                vert_cos.append(current.vert.co.copy())
                edge_indices.append(current.edge.index)
                side_face_indices.append(current.face.index)

                next_side = _find_next_boundary_side(current, patch_face_indices)
                if next_side is None:
                    break
                if _boundary_side_key(next_side) == start_key:
                    closed = True
                    break

                current = next_side

            if edge_indices:
                raw_loops.append(
                    _RawBoundaryLoop(
                        vert_indices=vert_indices,
                        vert_cos=vert_cos,
                        edge_indices=edge_indices,
                        side_face_indices=side_face_indices,
                        kind=LoopKind.OUTER,
                        depth=0,
                        closed=closed,
                    )
                )

    return raw_loops


def _collect_patch_boundary_edge_indices(patch_face_indices, bm):
    patch_face_index_set = set(patch_face_indices)
    boundary_edge_indices = set()
    for face_index in patch_face_index_set:
        face = bm.faces[face_index]
        for loop in face.loops:
            if _is_boundary_side(loop, patch_face_index_set):
                boundary_edge_indices.add(loop.edge.index)
    return boundary_edge_indices


def _validate_raw_patch_boundary_topology(patch_id, patch_data, bm):
    raw_loops = patch_data.raw_loops
    if not raw_loops:
        return

    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    expected_boundary_edges = _collect_patch_boundary_edge_indices(patch_data.face_indices, bm)
    edge_to_loops: dict[int, set[int]] = {}
    vert_to_loops: dict[int, set[int]] = {}
    patch_face_index_set = set(patch_data.face_indices)

    for loop_index, raw_loop in enumerate(raw_loops):
        edge_count = len(raw_loop.edge_indices)
        vert_count = len(raw_loop.vert_indices)
        side_count = len(raw_loop.side_face_indices)

        if edge_count != vert_count:
            _report_boundary_loop_invariant_violation(
                patch_id,
                loop_index,
                "L6",
                f"raw_edge_vert_count_mismatch edges={edge_count} verts={vert_count}",
            )
        if edge_count != side_count:
            _report_boundary_loop_invariant_violation(
                patch_id,
                loop_index,
                "L6",
                f"raw_edge_side_count_mismatch edges={edge_count} side_faces={side_count}",
            )
        if len(set(raw_loop.edge_indices)) != edge_count:
            _report_boundary_loop_invariant_violation(
                patch_id,
                loop_index,
                "L6",
                "raw_loop_repeats_boundary_edge",
            )

        for side_face_index in raw_loop.side_face_indices:
            if side_face_index not in patch_face_index_set:
                _report_boundary_loop_invariant_violation(
                    patch_id,
                    loop_index,
                    "L6",
                    f"raw_side_face_out_of_patch face={side_face_index}",
                )

        for edge_index in raw_loop.edge_indices:
            edge_to_loops.setdefault(edge_index, set()).add(loop_index)

        for vert_index in set(raw_loop.vert_indices):
            vert_to_loops.setdefault(vert_index, set()).add(loop_index)

    actual_boundary_edges = set(edge_to_loops.keys())
    missing_edges = sorted(expected_boundary_edges - actual_boundary_edges)
    extra_edges = sorted(actual_boundary_edges - expected_boundary_edges)
    if missing_edges or extra_edges:
        _report_patch_topology_invariant_violation(
            patch_id,
            "L6",
            f"raw_boundary_edge_coverage_mismatch missing={missing_edges} extra={extra_edges}",
        )

    for edge_index, loop_indices in edge_to_loops.items():
        if len(loop_indices) != 1:
            _report_patch_topology_invariant_violation(
                patch_id,
                "L6",
                f"boundary_edge_multi_loop edge={edge_index} loops={sorted(loop_indices)}",
            )

    for vert_index, loop_indices in vert_to_loops.items():
        if len(loop_indices) < 2:
            continue
        vert = bm.verts[vert_index]
        touches_mesh_border = any(len(edge.link_faces) == 1 for edge in vert.link_edges)
        if not touches_mesh_border:
            _report_patch_topology_invariant_violation(
                patch_id,
                "L5",
                f"shared_non_border_vertex vert={vert_index} loops={sorted(loop_indices)}",
            )


def _validate_raw_patch_loop_classification(patch_id, patch_data):
    raw_loops = patch_data.raw_loops
    if not raw_loops:
        _report_patch_topology_invariant_violation(
            patch_id,
            "L1",
            "patch_has_no_raw_loops",
        )
        return

    outer_loop_count = sum(1 for raw_loop in raw_loops if raw_loop.kind == LoopKind.OUTER)
    if outer_loop_count != 1:
        _report_patch_topology_invariant_violation(
            patch_id,
            "L1",
            f"raw_outer_loop_count_mismatch expected=1 actual={outer_loop_count}",
        )

    for loop_index, raw_loop in enumerate(raw_loops):
        if not raw_loop.closed:
            _report_boundary_loop_invariant_violation(
                patch_id,
                loop_index,
                "L7",
                "raw_loop_not_closed",
            )

        expected_kind = LoopKind.OUTER if raw_loop.depth % 2 == 0 else LoopKind.HOLE
        if raw_loop.kind != expected_kind:
            _report_boundary_loop_invariant_violation(
                patch_id,
                loop_index,
                "L3",
                f"raw_depth_parity_kind_mismatch depth={raw_loop.depth} "
                f"expected={expected_kind.value} actual={raw_loop.kind.value}",
            )

    if len(raw_loops) <= 1:
        return

    planar_results = _snapshot_planar_loop_classification(
        raw_loops,
        patch_data.basis_u,
        patch_data.basis_v,
    )
    uv_results = tuple(
        _LoopClassificationResult(kind=raw_loop.kind, depth=raw_loop.depth)
        for raw_loop in raw_loops
    )
    if planar_results != uv_results:
        uv_kinds = [result.kind.value for result in uv_results]
        uv_depths = [result.depth for result in uv_results]
        planar_kinds = [result.kind.value for result in planar_results]
        planar_depths = [result.depth for result in planar_results]
        _report_loop_classification_diagnostic(
            patch_id,
            f"uv_vs_planar_mismatch uv_kinds={uv_kinds} uv_depths={uv_depths} "
            f"planar_kinds={planar_kinds} planar_depths={planar_depths}",
        )


def _validate_raw_patch_boundary_data(patch_id, patch_data, bm):
    _validate_raw_patch_boundary_topology(patch_id, patch_data, bm)
    _validate_raw_patch_loop_classification(patch_id, patch_data)
