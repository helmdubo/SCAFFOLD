from __future__ import annotations

from mathutils import Vector

try:
    from .constants import (
        NB_MESH_BORDER,
        NB_SEAM_SELF,
    )
    from .model import (
        BoundaryChain,
        BoundaryCorner,
        BoundaryLoop,
        ChainNeighborKind,
        CornerKind,
        FrameRole,
        LoopKind,
        _build_chain_use,
    )
    from .analysis_records import (
        _RawBoundaryChain,
        _BoundaryLoopBuildState,
        _BoundaryLoopDerivedTopology,
        _ResolvedLoopCornerIdentity,
    )
    from .analysis_frame_runs import (
        _measure_chain_frame_confidence,
    )
    from .analysis_corners import (
        _measure_chain_axis_metrics,
        _classify_chain_frame_role,
        _find_corner_reference_point,
        _measure_corner_turn_angle,
        _build_geometric_loop_corners,
        _sawtooth_promoted_role,
        _try_geometric_outer_loop_split,
    )
    from .console_debug import trace_console
except ImportError:
    from constants import (
        NB_MESH_BORDER,
        NB_SEAM_SELF,
    )
    from model import (
        BoundaryChain,
        BoundaryCorner,
        BoundaryLoop,
        ChainNeighborKind,
        CornerKind,
        FrameRole,
        LoopKind,
        _build_chain_use,
    )
    from analysis_records import (
        _RawBoundaryChain,
        _BoundaryLoopBuildState,
        _BoundaryLoopDerivedTopology,
        _ResolvedLoopCornerIdentity,
    )
    from analysis_frame_runs import (
        _measure_chain_frame_confidence,
    )
    from analysis_corners import (
        _measure_chain_axis_metrics,
        _classify_chain_frame_role,
        _find_corner_reference_point,
        _measure_corner_turn_angle,
        _build_geometric_loop_corners,
        _sawtooth_promoted_role,
        _try_geometric_outer_loop_split,
    )
    from console_debug import trace_console


def _report_boundary_loop_invariant_violation(patch_id, loop_index, rule_code, detail):
    trace_console(f"[CFTUV][TopologyInvariant] Patch {patch_id} Loop {loop_index} {rule_code} {detail}")


def _report_patch_topology_invariant_violation(patch_id, rule_code, detail):
    trace_console(f"[CFTUV][TopologyInvariant] Patch {patch_id} {rule_code} {detail}")


def _neighbor_for_side(edge_index, side_face_index, patch_face_indices, face_to_patch, patch_id, bm):
    edge = bm.edges[edge_index]
    if len(edge.link_faces) == 1:
        return NB_MESH_BORDER

    in_patch_faces = [linked_face for linked_face in edge.link_faces if linked_face.index in patch_face_indices]
    if len(in_patch_faces) >= 2 and edge.seam:
        return NB_SEAM_SELF

    other_faces = [linked_face for linked_face in edge.link_faces if linked_face.index not in patch_face_indices]
    if not other_faces:
        return NB_MESH_BORDER

    neighbor_patch_id = face_to_patch.get(other_faces[0].index, NB_MESH_BORDER)
    if neighbor_patch_id == patch_id:
        return NB_SEAM_SELF

    return neighbor_patch_id


def _split_loop_into_chains_by_neighbor(raw_loop, loop_neighbors):
    loop_vert_indices = raw_loop.vert_indices
    loop_vert_cos = raw_loop.vert_cos
    loop_edge_indices = raw_loop.edge_indices
    loop_side_face_indices = raw_loop.side_face_indices
    vertex_count = len(loop_vert_cos)
    edge_count = len(loop_edge_indices)
    if edge_count == 0:
        return []

    neighbors = list(loop_neighbors[:edge_count])
    if len(neighbors) < edge_count:
        neighbors.extend([NB_MESH_BORDER] * (edge_count - len(neighbors)))

    split_indices = []
    for idx in range(vertex_count):
        if neighbors[(idx - 1) % edge_count] != neighbors[idx % edge_count]:
            split_indices.append(idx)

    if not split_indices:
        return [
            _RawBoundaryChain(
                vert_indices=list(loop_vert_indices),
                vert_cos=list(loop_vert_cos),
                edge_indices=list(loop_edge_indices),
                side_face_indices=list(loop_side_face_indices),
                neighbor=neighbors[0],
                is_closed=True,
                start_loop_index=0,
                end_loop_index=0,
            )
        ]

    chains = []
    split_count = len(split_indices)
    for split_idx in range(split_count):
        v_start = split_indices[split_idx]
        v_end = split_indices[(split_idx + 1) % split_count]

        chain_vert_indices = []
        chain_vert_cos = []
        chain_edge_indices = []
        chain_side_face_indices = []
        idx = v_start
        safety = 0
        while safety < vertex_count + 2:
            safety += 1
            chain_vert_indices.append(loop_vert_indices[idx % vertex_count])
            chain_vert_cos.append(loop_vert_cos[idx % vertex_count])
            chain_edge_indices.append(loop_edge_indices[idx % edge_count])
            chain_side_face_indices.append(loop_side_face_indices[idx % vertex_count])
            idx += 1
            if idx % vertex_count == v_end % vertex_count:
                chain_vert_indices.append(loop_vert_indices[v_end % vertex_count])
                chain_vert_cos.append(loop_vert_cos[v_end % vertex_count])
                chain_side_face_indices.append(loop_side_face_indices[v_end % vertex_count])
                break

        chains.append(
            _RawBoundaryChain(
                vert_indices=chain_vert_indices,
                vert_cos=chain_vert_cos,
                edge_indices=chain_edge_indices,
                side_face_indices=chain_side_face_indices,
                neighbor=neighbors[v_start % edge_count],
                is_closed=False,
                start_loop_index=v_start % vertex_count,
                end_loop_index=v_end % vertex_count,
            )
        )

    return chains


def _build_boundary_loop_base(raw_loop):
    loop_kind = raw_loop.kind
    if not isinstance(loop_kind, LoopKind):
        loop_kind = LoopKind(loop_kind)

    return BoundaryLoop(
        vert_indices=list(raw_loop.vert_indices),
        vert_cos=[co.copy() for co in raw_loop.vert_cos],
        edge_indices=list(raw_loop.edge_indices),
        side_face_indices=list(raw_loop.side_face_indices),
        kind=loop_kind,
        depth=int(raw_loop.depth),
    )


def _collect_raw_loop_neighbors(raw_loop, patch_face_indices, face_to_patch, patch_id, bm):
    return [
        _neighbor_for_side(edge_index, side_face_index, patch_face_indices, face_to_patch, patch_id, bm)
        for edge_index, side_face_index in zip(raw_loop.edge_indices, raw_loop.side_face_indices)
    ]


def _begin_boundary_loop_build(raw_loop, patch_face_indices, face_to_patch, patch_id, bm):
    state = _BoundaryLoopBuildState(
        raw_loop=raw_loop,
        boundary_loop=_build_boundary_loop_base(raw_loop),
    )
    state.loop_neighbors = _collect_raw_loop_neighbors(
        raw_loop,
        patch_face_indices,
        face_to_patch,
        patch_id,
        bm,
    )
    state.raw_chains = _split_loop_into_chains_by_neighbor(raw_loop, state.loop_neighbors)
    return state


def _merge_bevel_wrap_chains(chains, bm):
    return list(chains)


def _atomize_raw_chain_to_edges(raw_chain):
    """Разбивает один raw chain на per-edge chains."""

    vertex_count = len(raw_chain.vert_indices)
    edge_count = len(raw_chain.edge_indices)
    if vertex_count < 2 or edge_count < 1:
        return [raw_chain]

    edge_limit = min(edge_count, vertex_count if raw_chain.is_closed else vertex_count - 1)
    if edge_limit < 1:
        return [raw_chain]

    atomized_chains = []
    parent_start_loop_index = int(raw_chain.start_loop_index)
    side_face_count = len(raw_chain.side_face_indices)

    for edge_pos in range(edge_limit):
        start_vert_pos = edge_pos
        end_vert_pos = (edge_pos + 1) % vertex_count if raw_chain.is_closed else edge_pos + 1
        if start_vert_pos >= vertex_count or end_vert_pos >= vertex_count:
            continue

        side_start = (
            int(raw_chain.side_face_indices[start_vert_pos])
            if start_vert_pos < side_face_count
            else -1
        )
        side_end = (
            int(raw_chain.side_face_indices[end_vert_pos])
            if end_vert_pos < side_face_count
            else side_start
        )

        if raw_chain.is_closed:
            start_loop_index = (parent_start_loop_index + edge_pos) % vertex_count
            end_loop_index = (parent_start_loop_index + edge_pos + 1) % vertex_count
        else:
            start_loop_index = parent_start_loop_index + edge_pos
            end_loop_index = parent_start_loop_index + edge_pos + 1

        atomized_chains.append(
            _RawBoundaryChain(
                vert_indices=[
                    int(raw_chain.vert_indices[start_vert_pos]),
                    int(raw_chain.vert_indices[end_vert_pos]),
                ],
                vert_cos=[
                    raw_chain.vert_cos[start_vert_pos].copy(),
                    raw_chain.vert_cos[end_vert_pos].copy(),
                ],
                edge_indices=[int(raw_chain.edge_indices[edge_pos])],
                side_face_indices=[side_start, side_end],
                neighbor=int(raw_chain.neighbor),
                is_closed=False,
                start_loop_index=int(start_loop_index),
                end_loop_index=int(end_loop_index),
                is_corner_split=False,
            )
        )

    return atomized_chains if atomized_chains else [raw_chain]


def _atomize_mesh_border_chains(_raw_loop, raw_chains):
    """Атомизирует MESH_BORDER chains до single-edge уровня."""

    result = []
    for raw_chain in raw_chains:
        if int(raw_chain.neighbor) == NB_MESH_BORDER and not raw_chain.is_corner_split:
            result.extend(_atomize_raw_chain_to_edges(raw_chain))
        else:
            result.append(raw_chain)
    return result


def _refine_boundary_loop_raw_chains(state, basis_u, basis_v, bm):
    state.raw_chains = _merge_bevel_wrap_chains(state.raw_chains, bm)
    state.raw_chains = _try_geometric_outer_loop_split(
        state.raw_loop,
        state.raw_chains,
        basis_u,
        basis_v,
        bm=bm,
    )
    state.raw_chains = _atomize_mesh_border_chains(state.raw_loop, state.raw_chains)


def _build_boundary_chain_objects(raw_chains, basis_u, basis_v):
    chains = []
    for raw_chain in raw_chains:
        chain_vert_cos = [co.copy() for co in raw_chain.vert_cos]
        neighbor_id = int(raw_chain.neighbor)
        use_strict_guards = (neighbor_id != NB_MESH_BORDER)
        raw_role = _classify_chain_frame_role(
            chain_vert_cos,
            basis_u,
            basis_v,
            strict_guards=use_strict_guards,
        )
        # Fallback: FREE chain с пилообразной детализацией вдоль одной
        # оси patch → промоушен в H_FRAME / V_FRAME. Strict отсекает
        # зубья по h_avg_deviation; composite-тест смотрит на форму
        # ломаной в целом (хорда + PCA + zero-crossings).
        if raw_role == FrameRole.FREE:
            promoted = _sawtooth_promoted_role(chain_vert_cos, basis_u, basis_v)
            if promoted is not None:
                trace_console(
                    f"[CFTUV][Sawtooth] promoted neighbor={neighbor_id} "
                    f"verts={len(chain_vert_cos)} role={promoted.value}"
                )
                raw_role = promoted
        chains.append(
            BoundaryChain(
                vert_indices=list(raw_chain.vert_indices),
                vert_cos=chain_vert_cos,
                edge_indices=list(raw_chain.edge_indices),
                side_face_indices=list(raw_chain.side_face_indices),
                neighbor_patch_id=neighbor_id,
                is_closed=bool(raw_chain.is_closed),
                frame_role=raw_role,
                start_loop_index=int(raw_chain.start_loop_index),
                end_loop_index=int(raw_chain.end_loop_index),
                is_corner_split=bool(raw_chain.is_corner_split),
            )
        )
    return chains


def _build_boundary_loop_chain_uses(boundary_loop, patch_id, loop_index):
    chain_uses = []
    for chain_index, chain in enumerate(boundary_loop.chains):
        chain_uses.append(
            _build_chain_use(
                chain,
                patch_id,
                loop_index,
                chain_index,
                position_in_loop=chain_index,
            )
        )
    return chain_uses


def _downgrade_same_role_point_contact_chains(chains, basis_u, basis_v, patch_id, loop_index):
    chain_count = len(chains)
    if chain_count < 2:
        return

    pair_indices = [(chain_index, chain_index + 1) for chain_index in range(chain_count - 1)]
    if chain_count > 2:
        pair_indices.append((chain_count - 1, 0))

    for first_index, second_index in pair_indices:
        first_chain = chains[first_index]
        second_chain = chains[second_index]
        if first_chain.frame_role != second_chain.frame_role:
            continue
        if first_chain.frame_role not in (FrameRole.H_FRAME, FrameRole.V_FRAME):
            continue
        if (
            first_chain.neighbor_kind == ChainNeighborKind.MESH_BORDER
            and second_chain.neighbor_kind == ChainNeighborKind.MESH_BORDER
        ):
            continue

        shared_vert_indices = (set(first_chain.vert_indices) & set(second_chain.vert_indices)) - {-1}
        if len(shared_vert_indices) != 1:
            continue

        first_strength = _measure_chain_frame_confidence(first_chain, basis_u, basis_v, _measure_chain_axis_metrics)
        second_strength = _measure_chain_frame_confidence(second_chain, basis_u, basis_v, _measure_chain_axis_metrics)
        weaker_index = second_index if first_strength >= second_strength else first_index
        stronger_index = first_index if weaker_index == second_index else second_index
        weaker_chain = chains[weaker_index]
        if weaker_chain.frame_role == FrameRole.FREE:
            continue

        shared_vert_index = next(iter(shared_vert_indices))
        trace_console(
            f"[CFTUV][RoleConflict] Patch {patch_id} Loop {loop_index} "
            f"{first_chain.frame_role.value} point_contact vert={shared_vert_index} "
            f"keep=C{stronger_index} drop=C{weaker_index}->FREE"
        )
        weaker_chain.frame_role = FrameRole.FREE


def _demote_isolated_hv_border_chains(chains, patch_id, loop_index):
    """Демотирует изолированные H/V MESH_BORDER chains → FREE.

    Изолированный = MESH_BORDER chain, у которого:
    1) оба соседа (prev/next в loop) — FREE
    2) ни один из соседей не является PATCH chain

    Если сосед — PATCH chain, значит start/end point chain находится
    на границе с другим патчем (junction), и через эту точку может
    быть сильный H/V chain на соседнем патче → chain "закреплён".
    """
    chain_count = len(chains)
    if chain_count < 3:
        return

    for i in range(chain_count):
        chain = chains[i]
        if chain.frame_role not in (FrameRole.H_FRAME, FrameRole.V_FRAME):
            continue
        if chain.neighbor_kind != ChainNeighborKind.MESH_BORDER:
            continue

        prev_chain = chains[(i - 1) % chain_count]
        next_chain = chains[(i + 1) % chain_count]

        if prev_chain.frame_role != FrameRole.FREE:
            continue
        if next_chain.frame_role != FrameRole.FREE:
            continue

        # Если хоть один сосед — PATCH chain, то start/end vertex
        # лежит на границе с другим патчем → chain закреплён.
        if prev_chain.neighbor_kind == ChainNeighborKind.PATCH:
            continue
        if next_chain.neighbor_kind == ChainNeighborKind.PATCH:
            continue

        trace_console(
            f"[CFTUV][IsolatedHV] Patch {patch_id} Loop {loop_index} "
            f"C{i} {chain.frame_role.value} MESH_BORDER isolated -> FREE"
        )
        chain.frame_role = FrameRole.FREE


def _merge_same_role_border_chains(chains):
    if len(chains) < 2:
        return chains

    merged = [chains[0]]
    for i in range(1, len(chains)):
        prev = merged[-1]
        curr = chains[i]

        can_merge = (
            prev.neighbor_kind == ChainNeighborKind.MESH_BORDER
            and curr.neighbor_kind == ChainNeighborKind.MESH_BORDER
            and prev.frame_role == curr.frame_role
            and not prev.is_corner_split
            and not curr.is_corner_split
            and not prev.is_closed
            and not curr.is_closed
        )

        if can_merge:
            merged[-1] = BoundaryChain(
                vert_indices=prev.vert_indices + curr.vert_indices[1:],
                vert_cos=prev.vert_cos + curr.vert_cos[1:],
                edge_indices=prev.edge_indices + curr.edge_indices,
                side_face_indices=prev.side_face_indices + curr.side_face_indices[1:],
                neighbor_patch_id=prev.neighbor_patch_id,
                is_closed=False,
                frame_role=prev.frame_role,
                start_loop_index=prev.start_loop_index,
                end_loop_index=curr.end_loop_index,
                is_corner_split=prev.is_corner_split and curr.is_corner_split,
            )
        else:
            merged.append(curr)

    if len(merged) >= 2:
        last = merged[-1]
        first = merged[0]
        can_wrap = (
            last.neighbor_kind == ChainNeighborKind.MESH_BORDER
            and first.neighbor_kind == ChainNeighborKind.MESH_BORDER
            and last.frame_role == first.frame_role
            and not last.is_corner_split
            and not first.is_corner_split
            and not last.is_closed
            and not first.is_closed
        )
        if can_wrap:
            merged[0] = BoundaryChain(
                vert_indices=last.vert_indices + first.vert_indices[1:],
                vert_cos=last.vert_cos + first.vert_cos[1:],
                edge_indices=last.edge_indices + first.edge_indices,
                side_face_indices=last.side_face_indices + first.side_face_indices[1:],
                neighbor_patch_id=last.neighbor_patch_id,
                is_closed=False,
                frame_role=last.frame_role,
                start_loop_index=last.start_loop_index,
                end_loop_index=first.end_loop_index,
                is_corner_split=last.is_corner_split and first.is_corner_split,
            )
            merged.pop()

    return merged


def _resolve_loop_corner_from_final_chains(boundary_loop, prev_chain, next_chain):
    next_start_vert_index = next_chain.start_vert_index
    prev_end_vert_index = prev_chain.end_vert_index
    shared_vert_index = next_start_vert_index if next_start_vert_index >= 0 else prev_end_vert_index
    resolved_exactly = True

    if (
        next_start_vert_index >= 0
        and prev_end_vert_index >= 0
        and next_start_vert_index != prev_end_vert_index
    ):
        resolved_exactly = False
        shared_vert_index = next_start_vert_index

    vertex_count = len(boundary_loop.vert_indices)
    if vertex_count > 0 and shared_vert_index >= 0:
        loop_vert_index = next_chain.start_loop_index % vertex_count
        prev_loop_vert_index = prev_chain.end_loop_index % vertex_count
        if prev_loop_vert_index != loop_vert_index:
            resolved_exactly = False

        if (
            0 <= loop_vert_index < len(boundary_loop.vert_indices)
            and boundary_loop.vert_indices[loop_vert_index] == shared_vert_index
            and 0 <= loop_vert_index < len(boundary_loop.vert_cos)
        ):
            return _ResolvedLoopCornerIdentity(
                loop_vert_index=loop_vert_index,
                vert_index=shared_vert_index,
                vert_co=boundary_loop.vert_cos[loop_vert_index].copy(),
                resolved_exactly=resolved_exactly,
            )

        resolved_exactly = False

    if next_chain.vert_cos:
        return _ResolvedLoopCornerIdentity(
            loop_vert_index=int(next_chain.start_loop_index),
            vert_index=int(next_chain.start_vert_index),
            vert_co=next_chain.vert_cos[0].copy(),
            resolved_exactly=False,
        )
    if prev_chain.vert_cos:
        return _ResolvedLoopCornerIdentity(
            loop_vert_index=int(prev_chain.end_loop_index),
            vert_index=int(prev_chain.end_vert_index),
            vert_co=prev_chain.vert_cos[-1].copy(),
            resolved_exactly=False,
        )
    return _ResolvedLoopCornerIdentity(
        loop_vert_index=-1,
        vert_index=-1,
        vert_co=Vector((0.0, 0.0, 0.0)),
        resolved_exactly=False,
    )


def _derive_loop_corners_from_final_chains(boundary_loop, basis_u, basis_v, patch_id, loop_index):
    chain_count = len(boundary_loop.chains)
    if chain_count < 2:
        return _build_geometric_loop_corners(boundary_loop, basis_u, basis_v)

    corners = []
    for next_chain_index in range(chain_count):
        prev_chain_index = (next_chain_index - 1) % chain_count
        prev_chain = boundary_loop.chains[prev_chain_index]
        next_chain = boundary_loop.chains[next_chain_index]
        corner_identity = _resolve_loop_corner_from_final_chains(
            boundary_loop,
            prev_chain,
            next_chain,
        )
        if not corner_identity.resolved_exactly:
            _report_boundary_loop_invariant_violation(
                patch_id,
                loop_index,
                "R7",
                f"corner_resolution_fallback prev_chain={prev_chain_index} next_chain={next_chain_index} "
                f"prev_end=({prev_chain.end_loop_index},{prev_chain.end_vert_index}) "
                f"next_start=({next_chain.start_loop_index},{next_chain.start_vert_index})",
            )

        loop_vert_index = corner_identity.loop_vert_index
        vert_index = corner_identity.vert_index
        corner_co = corner_identity.vert_co

        prev_point = _find_corner_reference_point(prev_chain.vert_cos, corner_co, reverse=True)
        next_point = _find_corner_reference_point(next_chain.vert_cos, corner_co, reverse=False)
        turn_angle_deg = _measure_corner_turn_angle(corner_co, prev_point, next_point, basis_u, basis_v)

        corners.append(
            BoundaryCorner(
                loop_vert_index=int(loop_vert_index),
                vert_index=int(vert_index),
                vert_co=corner_co,
                prev_chain_index=prev_chain_index,
                next_chain_index=next_chain_index,
                corner_kind=CornerKind.JUNCTION,
                turn_angle_deg=turn_angle_deg,
                prev_role=prev_chain.frame_role,
                next_role=next_chain.frame_role,
            )
        )

    return corners


def _assign_loop_chain_endpoint_topology(boundary_loop):
    for chain in boundary_loop.chains:
        chain.start_corner_index = -1
        chain.end_corner_index = -1

    chain_count = len(boundary_loop.chains)
    if chain_count < 2 or len(boundary_loop.corners) != chain_count:
        return

    for corner_index, corner in enumerate(boundary_loop.corners):
        if 0 <= corner.next_chain_index < chain_count:
            boundary_loop.chains[corner.next_chain_index].start_corner_index = corner_index
        if 0 <= corner.prev_chain_index < chain_count:
            boundary_loop.chains[corner.prev_chain_index].end_corner_index = corner_index


def _loop_vertex_span(loop_vert_indices, start_loop_index, end_loop_index):
    vertex_count = len(loop_vert_indices)
    if vertex_count == 0:
        return []

    start_loop_index %= vertex_count
    end_loop_index %= vertex_count
    if start_loop_index == end_loop_index:
        return list(loop_vert_indices)

    span = [loop_vert_indices[start_loop_index]]
    loop_index = start_loop_index
    safety = 0
    while safety < vertex_count:
        safety += 1
        loop_index = (loop_index + 1) % vertex_count
        span.append(loop_vert_indices[loop_index])
        if loop_index == end_loop_index:
            break
    return span


def _loop_edge_span(loop_edge_indices, start_loop_index, end_loop_index):
    edge_count = len(loop_edge_indices)
    if edge_count == 0:
        return []

    start_loop_index %= edge_count
    end_loop_index %= edge_count
    if start_loop_index == end_loop_index:
        return list(loop_edge_indices)

    span = []
    loop_index = start_loop_index
    safety = 0
    while safety < edge_count:
        safety += 1
        span.append(loop_edge_indices[loop_index])
        loop_index = (loop_index + 1) % edge_count
        if loop_index == end_loop_index:
            break
    return span


def _validate_boundary_loop_topology(boundary_loop, patch_id, loop_index):
    loop_vertex_count = len(boundary_loop.vert_indices)
    loop_edge_count = len(boundary_loop.edge_indices)
    chain_count = len(boundary_loop.chains)
    corner_count = len(boundary_loop.corners)

    total_chain_edges = 0
    for chain_index, chain in enumerate(boundary_loop.chains):
        expected_vert_indices = _loop_vertex_span(
            boundary_loop.vert_indices,
            chain.start_loop_index,
            chain.end_loop_index,
        )
        if chain.vert_indices != expected_vert_indices:
            _report_boundary_loop_invariant_violation(
                patch_id,
                loop_index,
                "X8",
                f"chain={chain_index} vert_span_mismatch expected={expected_vert_indices} actual={chain.vert_indices}",
            )

        expected_edge_indices = _loop_edge_span(
            boundary_loop.edge_indices,
            chain.start_loop_index,
            chain.end_loop_index,
        )
        if chain.edge_indices != expected_edge_indices:
            _report_boundary_loop_invariant_violation(
                patch_id,
                loop_index,
                "X7",
                f"chain={chain_index} edge_span_mismatch expected={expected_edge_indices} actual={chain.edge_indices}",
            )

        total_chain_edges += len(chain.edge_indices)

    if total_chain_edges != loop_edge_count:
        _report_boundary_loop_invariant_violation(
            patch_id,
            loop_index,
            "X7",
            f"edge_coverage_mismatch loop_edges={loop_edge_count} chain_edges={total_chain_edges}",
        )

    if chain_count >= 2 and corner_count != chain_count:
        _report_boundary_loop_invariant_violation(
            patch_id,
            loop_index,
            "X2",
            f"corner_count_mismatch chains={chain_count} corners={corner_count}",
        )

    if chain_count >= 2:
        for next_chain_index in range(chain_count):
            prev_chain_index = (next_chain_index - 1) % chain_count
            prev_chain = boundary_loop.chains[prev_chain_index]
            next_chain = boundary_loop.chains[next_chain_index]
            if prev_chain.end_vert_index != next_chain.start_vert_index:
                _report_boundary_loop_invariant_violation(
                    patch_id,
                    loop_index,
                    "X1",
                    f"chain_endpoint_mismatch prev_chain={prev_chain_index} next_chain={next_chain_index} "
                    f"prev_end={prev_chain.end_vert_index} next_start={next_chain.start_vert_index}",
                )

        for corner_index, corner in enumerate(boundary_loop.corners):
            if corner.corner_kind != CornerKind.JUNCTION:
                _report_boundary_loop_invariant_violation(
                    patch_id,
                    loop_index,
                    "R1",
                    f"corner={corner_index} expected=JUNCTION actual={corner.corner_kind.value}",
                )

            if not (0 <= corner.prev_chain_index < chain_count and 0 <= corner.next_chain_index < chain_count):
                _report_boundary_loop_invariant_violation(
                    patch_id,
                    loop_index,
                    "R7",
                    f"corner={corner_index} invalid_chain_refs prev={corner.prev_chain_index} next={corner.next_chain_index}",
                )
                continue

            prev_chain = boundary_loop.chains[corner.prev_chain_index]
            next_chain = boundary_loop.chains[corner.next_chain_index]
            if corner.vert_index != prev_chain.end_vert_index:
                _report_boundary_loop_invariant_violation(
                    patch_id,
                    loop_index,
                    "X3",
                    f"corner={corner_index} vert={corner.vert_index} prev_end={prev_chain.end_vert_index}",
                )
            if corner.vert_index != next_chain.start_vert_index:
                _report_boundary_loop_invariant_violation(
                    patch_id,
                    loop_index,
                    "X4",
                    f"corner={corner_index} vert={corner.vert_index} next_start={next_chain.start_vert_index}",
                )

            if not corner.wedge_normal_valid:
                _report_boundary_loop_invariant_violation(
                    patch_id,
                    loop_index,
                    "R8",
                    f"corner={corner_index} invalid wedge normal",
                )
            elif corner.wedge_normal.length_squared < 1e-12:
                _report_boundary_loop_invariant_violation(
                    patch_id,
                    loop_index,
                    "R8",
                    f"corner={corner_index} zero length wedge normal",
                )
            elif not corner.wedge_face_indices:
                _report_boundary_loop_invariant_violation(
                    patch_id,
                    loop_index,
                    "R8",
                    f"corner={corner_index} valid wedge missing face ids",
                )

        for chain_index, chain in enumerate(boundary_loop.chains):
            expected_start_corner = chain_index
            expected_end_corner = (chain_index + 1) % chain_count
            if chain.start_corner_index != expected_start_corner:
                _report_boundary_loop_invariant_violation(
                    patch_id,
                    loop_index,
                    "R7",
                    f"chain={chain_index} start_corner_mismatch expected={expected_start_corner} actual={chain.start_corner_index}",
                )
            if chain.end_corner_index != expected_end_corner:
                _report_boundary_loop_invariant_violation(
                    patch_id,
                    loop_index,
                    "R7",
                    f"chain={chain_index} end_corner_mismatch expected={expected_end_corner} actual={chain.end_corner_index}",
                )

    elif chain_count == 1:
        for corner_index, corner in enumerate(boundary_loop.corners):
            if corner.corner_kind != CornerKind.GEOMETRIC:
                _report_boundary_loop_invariant_violation(
                    patch_id,
                    loop_index,
                    "R2",
                    f"corner={corner_index} expected=GEOMETRIC actual={corner.corner_kind.value}",
                )
            if corner.prev_chain_index != 0 or corner.next_chain_index != 0:
                _report_boundary_loop_invariant_violation(
                    patch_id,
                    loop_index,
                    "R2",
                    f"corner={corner_index} single_chain_refs prev={corner.prev_chain_index} next={corner.next_chain_index}",
                )
    elif loop_vertex_count > 0 or loop_edge_count > 0:
        _report_boundary_loop_invariant_violation(
            patch_id,
            loop_index,
            "C1",
            "loop_has_geometry_but_no_chains",
        )

    if boundary_loop.chain_uses and len(boundary_loop.chain_uses) != chain_count:
        _report_boundary_loop_invariant_violation(
            patch_id,
            loop_index,
            "CU1",
            f"chain_use_count_mismatch expected={chain_count} actual={len(boundary_loop.chain_uses)}",
        )


def _validate_patch_loop_classification(node):
    if not node.boundary_loops:
        return

    outer_loop_count = sum(1 for boundary_loop in node.boundary_loops if boundary_loop.kind == LoopKind.OUTER)
    if outer_loop_count != 1:
        _report_patch_topology_invariant_violation(
            node.patch_id,
            "L1",
            f"outer_loop_count_mismatch expected=1 actual={outer_loop_count}",
        )

    for loop_index, boundary_loop in enumerate(node.boundary_loops):
        expected_kind = LoopKind.OUTER if boundary_loop.depth % 2 == 0 else LoopKind.HOLE
        if boundary_loop.kind != expected_kind:
            _report_boundary_loop_invariant_violation(
                node.patch_id,
                loop_index,
                "L3",
                f"depth_parity_kind_mismatch depth={boundary_loop.depth} expected={expected_kind.value} "
                f"actual={boundary_loop.kind.value}",
            )


def _derive_boundary_loop_topology(state, basis_u, basis_v, patch_id, loop_index):
    boundary_loop = state.boundary_loop
    chains = _build_boundary_chain_objects(state.raw_chains, basis_u, basis_v)
    _downgrade_same_role_point_contact_chains(chains, basis_u, basis_v, patch_id, loop_index)
    chains = _merge_same_role_border_chains(chains)
    _demote_isolated_hv_border_chains(chains, patch_id, loop_index)
    chains = _merge_same_role_border_chains(chains)
    boundary_loop.chains = chains

    corners = _derive_loop_corners_from_final_chains(
        boundary_loop,
        basis_u,
        basis_v,
        patch_id,
        loop_index,
    )
    return _BoundaryLoopDerivedTopology(
        chains=chains,
        corners=corners,
        uses_geometric_corner_fallback=(len(chains) < 2),
    )


def _edge_is_owner_boundary(edge, patch_face_index_set):
    in_patch_count = sum(1 for linked_face in edge.link_faces if linked_face.index in patch_face_index_set)
    if len(edge.link_faces) == 1:
        return True
    if in_patch_count == 1:
        return True
    if in_patch_count >= 2 and edge.seam:
        return True
    return False


def _find_face_loop_at_vertex(face, vert_index, incoming_edge_index=None, outgoing_edge_index=None):
    for loop in face.loops:
        if loop.vert.index != vert_index:
            continue
        if incoming_edge_index is not None and loop.link_loop_prev.edge.index != incoming_edge_index:
            continue
        if outgoing_edge_index is not None and loop.edge.index != outgoing_edge_index:
            continue
        return loop
    return None


def _resolve_corner_owner_half_loops(boundary_loop, corner, patch_face_index_set, bm):
    edge_count = len(boundary_loop.edge_indices)
    if edge_count == 0 or len(boundary_loop.side_face_indices) != edge_count:
        return None, None, -1

    corner_loop_index = corner.loop_vert_index
    if corner_loop_index < 0:
        return None, None, -1
    corner_loop_index %= edge_count

    if corner_loop_index >= len(boundary_loop.vert_indices):
        return None, None, -1

    corner_vert_index = int(boundary_loop.vert_indices[corner_loop_index])
    if corner_vert_index < 0:
        corner_vert_index = int(corner.vert_index)
    if corner_vert_index < 0:
        return None, None, -1

    prev_side_index = (corner_loop_index - 1) % edge_count
    next_side_index = corner_loop_index

    prev_face_index = int(boundary_loop.side_face_indices[prev_side_index])
    next_face_index = int(boundary_loop.side_face_indices[next_side_index])
    prev_edge_index = int(boundary_loop.edge_indices[prev_side_index])
    next_edge_index = int(boundary_loop.edge_indices[next_side_index])

    if (
        prev_face_index not in patch_face_index_set
        or next_face_index not in patch_face_index_set
        or prev_face_index < 0
        or next_face_index < 0
        or prev_face_index >= len(bm.faces)
        or next_face_index >= len(bm.faces)
    ):
        return None, None, corner_vert_index

    prev_face = bm.faces[prev_face_index]
    next_face = bm.faces[next_face_index]
    prev_loop = _find_face_loop_at_vertex(
        prev_face,
        corner_vert_index,
        incoming_edge_index=prev_edge_index,
    )
    next_loop = _find_face_loop_at_vertex(
        next_face,
        corner_vert_index,
        outgoing_edge_index=next_edge_index,
    )
    return prev_loop, next_loop, corner_vert_index


def _collect_corner_wedge_sector_loops(start_loop, end_loop, patch_face_index_set):
    if start_loop is None or end_loop is None:
        return ()
    if start_loop.vert.index != end_loop.vert.index:
        return ()

    corner_vert = start_loop.vert
    owner_vertex_loops = [
        loop
        for loop in corner_vert.link_loops
        if loop.vert.index == corner_vert.index and loop.face.index in patch_face_index_set
    ]
    incoming_edge_to_loops = {}
    for loop in owner_vertex_loops:
        incoming_edge_to_loops.setdefault(loop.link_loop_prev.edge.index, []).append(loop)

    target_key = (end_loop.face.index, end_loop.edge.index)
    sector_loops = []
    visited = set()
    current_loop = start_loop
    max_steps = len(owner_vertex_loops) + 1

    for _ in range(max_steps):
        current_key = (current_loop.face.index, current_loop.edge.index)
        if current_key in visited:
            return ()
        visited.add(current_key)
        sector_loops.append(current_loop)

        if current_key == target_key:
            return tuple(sector_loops)

        outgoing_edge = current_loop.edge
        if _edge_is_owner_boundary(outgoing_edge, patch_face_index_set):
            return ()

        next_candidates = [
            loop
            for loop in incoming_edge_to_loops.get(outgoing_edge.index, ())
            if loop.face.index != current_loop.face.index
        ]
        if len(next_candidates) != 1:
            return ()
        current_loop = next_candidates[0]

    return ()


def _corner_sector_loop_weight(loop):
    corner_co = loop.vert.co
    prev_vec = loop.link_loop_prev.vert.co - corner_co
    next_vec = loop.link_loop_next.vert.co - corner_co
    if prev_vec.length_squared < 1e-12 or next_vec.length_squared < 1e-12:
        return 0.0

    corner_angle = prev_vec.angle(next_vec, 0.0)
    face_area = loop.face.calc_area()
    if corner_angle <= 1e-12 or face_area <= 1e-12:
        return 0.0
    return face_area * corner_angle


def _compute_weighted_sector_normal(sector_loops):
    eps = 1e-12
    normal = Vector((0.0, 0.0, 0.0))

    for loop in sector_loops:
        weight = _corner_sector_loop_weight(loop)
        if weight <= eps:
            continue
        normal += loop.face.normal * weight

    if normal.length_squared > eps:
        return normal.normalized(), True

    for loop in sector_loops:
        normal += loop.face.normal
    if normal.length_squared > eps:
        return normal.normalized(), True

    return Vector((0.0, 0.0, 0.0)), False


def _compute_corner_wedge_data(boundary_loop, corner, patch_face_index_set, bm):
    if corner.corner_kind != CornerKind.JUNCTION:
        return (), Vector((0.0, 0.0, 0.0)), False

    chain_count = len(boundary_loop.chains)
    if not (0 <= corner.prev_chain_index < chain_count and 0 <= corner.next_chain_index < chain_count):
        return (), Vector((0.0, 0.0, 0.0)), False

    start_loop, end_loop, corner_vert_index = _resolve_corner_owner_half_loops(
        boundary_loop,
        corner,
        patch_face_index_set,
        bm,
    )
    sector_loops = _collect_corner_wedge_sector_loops(start_loop, end_loop, patch_face_index_set)
    if sector_loops:
        face_ids = tuple(dict.fromkeys(loop.face.index for loop in sector_loops))
        normal, valid = _compute_weighted_sector_normal(sector_loops)
        if valid:
            return face_ids, normal, True

    face_ids = []
    if start_loop is not None and start_loop.face.index in patch_face_index_set:
        face_ids.append(start_loop.face.index)
    if end_loop is not None and end_loop.face.index in patch_face_index_set and end_loop.face.index not in face_ids:
        face_ids.append(end_loop.face.index)

    eps = 1e-12
    normal = Vector((0.0, 0.0, 0.0))
    for fid in face_ids:
        normal += bm.faces[fid].normal
    if normal.length_squared > eps:
        return tuple(face_ids), normal.normalized(), True

    if corner_vert_index < 0 or corner_vert_index >= len(bm.verts):
        return tuple(face_ids), Vector((0.0, 0.0, 0.0)), False

    owner_faces = [
        f for f in bm.verts[corner_vert_index].link_faces
        if f.index in patch_face_index_set
    ]
    owner_face_ids = tuple(sorted({f.index for f in owner_faces}))
    normal = Vector((0.0, 0.0, 0.0))
    for f in owner_faces:
        normal += f.normal

    if normal.length_squared > eps:
        return owner_face_ids, normal.normalized(), True

    return owner_face_ids, Vector((0.0, 0.0, 0.0)), False


def _annotate_boundary_loop_corner_wedges(boundary_loop, patch_face_indices, bm):
    patch_face_index_set = set(patch_face_indices)
    for corner in boundary_loop.corners:
        if corner.corner_kind != CornerKind.JUNCTION:
            continue
        face_ids, normal, valid = _compute_corner_wedge_data(boundary_loop, corner, patch_face_index_set, bm)
        corner.wedge_face_indices = face_ids
        corner.wedge_normal = normal
        corner.wedge_normal_valid = valid


def _finalize_boundary_loop_build(state, basis_u, basis_v, patch_id, loop_index, patch_face_indices, bm):
    boundary_loop = state.boundary_loop
    derived_topology = _derive_boundary_loop_topology(state, basis_u, basis_v, patch_id, loop_index)
    boundary_loop.chains = derived_topology.chains
    boundary_loop.corners = derived_topology.corners
    boundary_loop.chain_uses = _build_boundary_loop_chain_uses(boundary_loop, patch_id, loop_index)
    _assign_loop_chain_endpoint_topology(boundary_loop)
    _annotate_boundary_loop_corner_wedges(boundary_loop, patch_face_indices, bm)
    _validate_boundary_loop_topology(boundary_loop, patch_id, loop_index)
    return boundary_loop


def _build_boundary_loops(raw_loops, patch_face_indices, face_to_patch, patch_id, basis_u, basis_v, bm):
    boundary_loops = []
    patch_face_indices = set(patch_face_indices)

    for loop_index, raw_loop in enumerate(raw_loops):
        state = _begin_boundary_loop_build(
            raw_loop,
            patch_face_indices,
            face_to_patch,
            patch_id,
            bm,
        )
        _refine_boundary_loop_raw_chains(state, basis_u, basis_v, bm)
        boundary_loops.append(
            _finalize_boundary_loop_build(state, basis_u, basis_v, patch_id, loop_index, patch_face_indices, bm)
        )

    return boundary_loops
