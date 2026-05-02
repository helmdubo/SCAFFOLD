from __future__ import annotations

try:
    from mathutils import Vector

    from .model import (
        BoundaryChain, FrameRole, FrameAxisKind, ClosureAnchorMode,
        PatchGraph,
        ScaffoldChainPlacement, ScaffoldQuiltPlacement, ScaffoldClosureSeamReport,
        ScaffoldFrameAlignmentReport, ChainRef, PatchEdgeKey,
    )
    from .console_debug import is_verbose_console_enabled, trace_console
    from .solve_records import (
        RowClassKey, ColumnClassKey, FrameClassKey,
        UvAxisMetrics, FrameUvComponents, FrameGroupDisplayCoords,
        SharedClosureUvOffsets, FrameGroupMember,
        FRAME_ROW_GROUP_TOLERANCE, FRAME_COLUMN_GROUP_TOLERANCE,
        frame_row_class_key, frame_column_class_key,
    )
    from .solve_planning import (
        _build_patch_tree_adjacency,
        _find_patch_tree_path,
    )
except ImportError:
    from mathutils import Vector

    from model import (
        BoundaryChain, FrameRole, FrameAxisKind, ClosureAnchorMode,
        PatchGraph,
        ScaffoldChainPlacement, ScaffoldQuiltPlacement, ScaffoldClosureSeamReport,
        ScaffoldFrameAlignmentReport, ChainRef, PatchEdgeKey,
    )
    from console_debug import is_verbose_console_enabled, trace_console
    from solve_records import (
        RowClassKey, ColumnClassKey, FrameClassKey,
        UvAxisMetrics, FrameUvComponents, FrameGroupDisplayCoords,
        SharedClosureUvOffsets, FrameGroupMember,
        FRAME_ROW_GROUP_TOLERANCE, FRAME_COLUMN_GROUP_TOLERANCE,
        frame_row_class_key, frame_column_class_key,
    )
    from solve_planning import (
        _build_patch_tree_adjacency,
        _find_patch_tree_path,
    )


def _runtime_iter_quilt_closure_chain_pairs(
    graph: PatchGraph,
    quilt_patch_ids: set[int],
    allowed_tree_edges: set[PatchEdgeKey],
):
    try:
        from .solve_frontier import _iter_quilt_closure_chain_pairs
    except ImportError:
        try:
            from solve_frontier import _iter_quilt_closure_chain_pairs
        except ImportError:
            try:
                from .solve import _iter_quilt_closure_chain_pairs
            except ImportError:
                from solve import _iter_quilt_closure_chain_pairs
    return _iter_quilt_closure_chain_pairs(graph, quilt_patch_ids, allowed_tree_edges)


def _runtime_chain_total_length(chain: BoundaryChain, final_scale: float) -> float:
    try:
        from .solve_frontier import _cf_chain_total_length
    except ImportError:
        try:
            from solve_frontier import _cf_chain_total_length
        except ImportError:
            try:
                from .solve import _cf_chain_total_length
            except ImportError:
                from solve import _cf_chain_total_length
    return _cf_chain_total_length(chain, final_scale)


def _chain_uv_axis_metrics(chain_placement: ScaffoldChainPlacement) -> UvAxisMetrics:
    if len(chain_placement.points) < 2:
        return UvAxisMetrics(span=0.0, axis_error=0.0)

    start_uv = chain_placement.points[0][1]
    end_uv = chain_placement.points[-1][1]
    delta = end_uv - start_uv

    if chain_placement.frame_role == FrameRole.H_FRAME:
        return UvAxisMetrics(span=abs(delta.x), axis_error=abs(delta.y))
    if chain_placement.frame_role == FrameRole.V_FRAME:
        return UvAxisMetrics(span=abs(delta.y), axis_error=abs(delta.x))
    return UvAxisMetrics(span=delta.length, axis_error=0.0)


def _split_uv_by_frame_role(frame_role: FrameRole, uv: Vector) -> FrameUvComponents:
    if frame_role == FrameRole.H_FRAME:
        return FrameUvComponents(axis=uv.x, cross=uv.y)
    if frame_role == FrameRole.V_FRAME:
        return FrameUvComponents(axis=uv.y, cross=uv.x)
    return FrameUvComponents(axis=uv.length, cross=0.0)


def _build_chain_vert_uv_map(
    graph: PatchGraph,
    chain_placement: ScaffoldChainPlacement,
) -> dict[int, Vector]:
    node = graph.nodes.get(chain_placement.patch_id)
    if node is None:
        return {}
    if chain_placement.loop_index < 0 or chain_placement.loop_index >= len(node.boundary_loops):
        return {}

    boundary_loop = node.boundary_loops[chain_placement.loop_index]
    if chain_placement.chain_index < 0 or chain_placement.chain_index >= len(boundary_loop.chains):
        return {}

    chain = boundary_loop.chains[chain_placement.chain_index]
    chain_use = graph.get_chain_use(
        chain_placement.patch_id,
        chain_placement.loop_index,
        chain_placement.chain_index,
    )
    vert_uv_map = {}
    for point_key, uv in chain_placement.points:
        if (
            point_key.patch_id != chain_placement.patch_id
            or point_key.loop_index != chain_placement.loop_index
            or point_key.chain_index != chain_placement.chain_index
        ):
            continue
        if chain_use is None:
            continue
        resolved_source_point = boundary_loop.resolve_chain_use_source_point(chain_use, point_key.source_point_index)
        if resolved_source_point is None:
            continue
        _loop_point_index, vert_index = resolved_source_point
        vert_uv_map[vert_index] = uv

    if not vert_uv_map and len(chain.vert_indices) == len(chain_placement.points):
        for source_point_index, (_, uv) in enumerate(chain_placement.points):
            if chain_use is None:
                continue
            resolved_source_point = boundary_loop.resolve_chain_use_source_point(chain_use, source_point_index)
            if resolved_source_point is None:
                continue
            _loop_point_index, vert_index = resolved_source_point
            vert_uv_map[vert_index] = uv

    return vert_uv_map


def _measure_shared_closure_uv_offsets(
    graph: PatchGraph,
    owner_placement: ScaffoldChainPlacement,
    target_placement: ScaffoldChainPlacement,
) -> SharedClosureUvOffsets:
    owner_uv_by_vert = _build_chain_vert_uv_map(graph, owner_placement)
    target_uv_by_vert = _build_chain_vert_uv_map(graph, target_placement)
    shared_vert_indices = sorted(set(owner_uv_by_vert.keys()) & set(target_uv_by_vert.keys()))
    if not shared_vert_indices:
        return SharedClosureUvOffsets()

    uv_deltas = []
    axis_offsets = []
    cross_axis_offsets = []
    for vert_index in shared_vert_indices:
        owner_uv = owner_uv_by_vert[vert_index]
        target_uv = target_uv_by_vert[vert_index]
        owner_components = _split_uv_by_frame_role(owner_placement.frame_role, owner_uv)
        target_components = _split_uv_by_frame_role(target_placement.frame_role, target_uv)
        uv_deltas.append((owner_uv - target_uv).length)
        axis_offsets.append(abs(owner_components.axis - target_components.axis))
        cross_axis_offsets.append(abs(owner_components.cross - target_components.cross))

    sample_count = len(shared_vert_indices)
    return SharedClosureUvOffsets(
        sampled_shared_vert_count=sample_count,
        shared_uv_delta_max=max(uv_deltas),
        shared_uv_delta_mean=sum(uv_deltas) / sample_count,
        axis_phase_offset_max=max(axis_offsets),
        axis_phase_offset_mean=sum(axis_offsets) / sample_count,
        cross_axis_offset_max=max(cross_axis_offsets),
        cross_axis_offset_mean=sum(cross_axis_offsets) / sample_count,
    )


def _classify_closure_anchor_mode(
    owner_anchor_count: int,
    target_anchor_count: int,
) -> ClosureAnchorMode:
    if owner_anchor_count >= 2 and target_anchor_count >= 2:
        return ClosureAnchorMode.DUAL_ANCHOR
    if owner_anchor_count <= 1 and target_anchor_count <= 1:
        return ClosureAnchorMode.ONE_ANCHOR
    return ClosureAnchorMode.MIXED


def _count_free_bridges_on_patch_path(
    quilt_scaffold: ScaffoldQuiltPlacement,
    patch_path: list[int],
) -> int:
    free_bridge_count = 0
    for patch_id in patch_path:
        patch_placement = quilt_scaffold.patches.get(patch_id)
        if patch_placement is None or patch_placement.notes:
            continue
        for chain_placement in patch_placement.chain_placements:
            if chain_placement.frame_role == FrameRole.FREE and len(chain_placement.points) <= 2:
                free_bridge_count += 1
    return free_bridge_count


def _collect_quilt_closure_seam_reports(
    graph: PatchGraph,
    quilt_plan,
    quilt_scaffold: ScaffoldQuiltPlacement,
    placed_chains_map: dict[ChainRef, ScaffoldChainPlacement],
    final_scale: float,
    allowed_tree_edges: set[PatchEdgeKey],
) -> tuple[ScaffoldClosureSeamReport, ...]:
    quilt_patch_ids = set(quilt_plan.solved_patch_ids)
    quilt_patch_ids.add(quilt_plan.root_patch_id)
    patch_tree_adjacency = _build_patch_tree_adjacency(quilt_plan)

    reports = []
    for owner_patch_id, target_patch_id, matched_pairs in _runtime_iter_quilt_closure_chain_pairs(
        graph,
        quilt_patch_ids,
        allowed_tree_edges,
    ):
        patch_path = _find_patch_tree_path(patch_tree_adjacency, owner_patch_id, target_patch_id)
        tree_patch_distance = max(0, len(patch_path) - 1) if patch_path else 0
        free_bridge_count = _count_free_bridges_on_patch_path(quilt_scaffold, patch_path) if patch_path else 0

        for match in matched_pairs:
            owner_placement = placed_chains_map.get(match.owner_ref)
            target_placement = placed_chains_map.get(match.target_ref)
            if owner_placement is None or target_placement is None:
                continue
            if len(owner_placement.points) < 2 or len(target_placement.points) < 2:
                continue

            owner_axis_metrics = _chain_uv_axis_metrics(owner_placement)
            target_axis_metrics = _chain_uv_axis_metrics(target_placement)
            shared_offsets = _measure_shared_closure_uv_offsets(graph, owner_placement, target_placement)
            canonical_3d_span = (
                _runtime_chain_total_length(match.owner_chain, final_scale)
                + _runtime_chain_total_length(match.target_chain, final_scale)
            ) * 0.5

            reports.append(ScaffoldClosureSeamReport(
                owner_patch_id=match.owner_ref[0],
                owner_loop_index=match.owner_ref[1],
                owner_chain_index=match.owner_ref[2],
                target_patch_id=match.target_ref[0],
                target_loop_index=match.target_ref[1],
                target_chain_index=match.target_ref[2],
                frame_role=match.owner_chain.frame_role,
                owner_anchor_count=owner_placement.anchor_count,
                target_anchor_count=target_placement.anchor_count,
                anchor_mode=_classify_closure_anchor_mode(owner_placement.anchor_count, target_placement.anchor_count),
                canonical_3d_span=canonical_3d_span,
                owner_uv_span=owner_axis_metrics.span,
                target_uv_span=target_axis_metrics.span,
                owner_axis_error=owner_axis_metrics.axis_error,
                target_axis_error=target_axis_metrics.axis_error,
                span_mismatch=abs(owner_axis_metrics.span - target_axis_metrics.span),
                sampled_shared_vert_count=shared_offsets.sampled_shared_vert_count,
                shared_uv_delta_max=shared_offsets.shared_uv_delta_max,
                shared_uv_delta_mean=shared_offsets.shared_uv_delta_mean,
                axis_phase_offset_max=shared_offsets.axis_phase_offset_max,
                axis_phase_offset_mean=shared_offsets.axis_phase_offset_mean,
                cross_axis_offset_max=shared_offsets.cross_axis_offset_max,
                cross_axis_offset_mean=shared_offsets.cross_axis_offset_mean,
                tree_patch_distance=tree_patch_distance,
                free_bridge_count=free_bridge_count,
                shared_vert_count=match.shared_vert_count,
            ))

    reports.sort(
        key=lambda report: (
            -report.axis_phase_offset_max,
            -report.cross_axis_offset_max,
            -report.shared_uv_delta_max,
            -report.span_mismatch,
            report.owner_patch_id,
            report.target_patch_id,
            report.owner_chain_index,
            report.target_chain_index,
        )
    )
    return tuple(reports)


def _print_quilt_closure_seam_reports(
    quilt_index: int,
    closure_seam_reports: tuple[ScaffoldClosureSeamReport, ...],
) -> None:
    if not closure_seam_reports or not is_verbose_console_enabled():
        return

    max_mismatch = max((report.span_mismatch for report in closure_seam_reports), default=0.0)
    max_axis_phase = max((report.axis_phase_offset_max for report in closure_seam_reports), default=0.0)
    trace_console(
        f"[CFTUV][ClosureDiag] Quilt {quilt_index}: "
        f"seams={len(closure_seam_reports)} "
        f"max_span_mismatch={max_mismatch:.6f} "
        f"max_axis_phase={max_axis_phase:.6f}"
    )
    for report in closure_seam_reports:
        trace_console(
            f"[CFTUV][ClosureDiag] Quilt {quilt_index} "
            f"P{report.owner_patch_id}L{report.owner_loop_index}C{report.owner_chain_index}"
            f"<->P{report.target_patch_id}L{report.target_loop_index}C{report.target_chain_index} "
            f"{report.frame_role.value} anchor:{report.anchor_mode.value} "
            f"span:{report.owner_uv_span:.6f}/{report.target_uv_span:.6f} "
            f"phase:{report.axis_phase_offset_max:.6f}/{report.axis_phase_offset_mean:.6f} "
            f"cross:{report.cross_axis_offset_max:.6f}/{report.cross_axis_offset_mean:.6f} "
            f"delta:{report.shared_uv_delta_max:.6f}/{report.shared_uv_delta_mean:.6f} "
            f"shared:{report.sampled_shared_vert_count}/{report.shared_vert_count} "
            f"path:{report.tree_patch_distance} free:{report.free_bridge_count}"
        )


def _frame_cross_axis_uv_value(chain_placement: ScaffoldChainPlacement) -> float:
    if not chain_placement.points:
        return 0.0
    if chain_placement.frame_role == FrameRole.H_FRAME:
        return sum(uv.y for _, uv in chain_placement.points) / float(len(chain_placement.points))
    if chain_placement.frame_role == FrameRole.V_FRAME:
        return sum(uv.x for _, uv in chain_placement.points) / float(len(chain_placement.points))
    return 0.0


def _wall_side_row_class_key(chain: BoundaryChain) -> RowClassKey:
    return frame_row_class_key(chain)


def _wall_side_column_class_key(chain: BoundaryChain) -> ColumnClassKey:
    return frame_column_class_key(chain)


def _frame_group_display_coords(
    axis_kind: FrameAxisKind,
    class_key: FrameClassKey,
) -> FrameGroupDisplayCoords:
    if axis_kind == FrameAxisKind.ROW:
        return FrameGroupDisplayCoords(
            coord_a=class_key[0] * FRAME_ROW_GROUP_TOLERANCE,
            coord_b=0.0,
        )
    if axis_kind == FrameAxisKind.COLUMN:
        return FrameGroupDisplayCoords(
            coord_a=class_key[0] * FRAME_COLUMN_GROUP_TOLERANCE,
            coord_b=class_key[1] * FRAME_COLUMN_GROUP_TOLERANCE,
        )
    return FrameGroupDisplayCoords(coord_a=0.0, coord_b=0.0)


def _collect_quilt_closure_sensitive_patch_ids(
    quilt_plan,
    closure_seam_reports: tuple[ScaffoldClosureSeamReport, ...],
) -> set[int]:
    if not closure_seam_reports:
        return set()

    patch_tree_adjacency = _build_patch_tree_adjacency(quilt_plan)
    closure_sensitive_patch_ids: set[int] = set()
    for report in closure_seam_reports:
        path = _find_patch_tree_path(
            patch_tree_adjacency,
            report.owner_patch_id,
            report.target_patch_id,
        )
        if path:
            closure_sensitive_patch_ids.update(path)
        else:
            closure_sensitive_patch_ids.add(report.owner_patch_id)
            closure_sensitive_patch_ids.add(report.target_patch_id)
    return closure_sensitive_patch_ids


def _collect_quilt_frame_alignment_reports(
    graph: PatchGraph,
    quilt_plan,
    quilt_scaffold: ScaffoldQuiltPlacement,
    final_scale: float,
    closure_seam_reports: tuple[ScaffoldClosureSeamReport, ...],
) -> tuple[ScaffoldFrameAlignmentReport, ...]:
    closure_sensitive_patch_ids = _collect_quilt_closure_sensitive_patch_ids(quilt_plan, closure_seam_reports)
    grouped_members: dict[
        tuple[FrameAxisKind, str, FrameClassKey],
        list[FrameGroupMember],
    ] = {}

    for patch_id, patch_placement in quilt_scaffold.patches.items():
        if patch_placement is None or patch_placement.notes:
            continue
        node = graph.nodes.get(patch_id)
        if node is None or node.semantic_key != 'WALL.SIDE':
            continue
        if patch_placement.loop_index < 0 or patch_placement.loop_index >= len(node.boundary_loops):
            continue
        boundary_loop = node.boundary_loops[patch_placement.loop_index]

        for chain_placement in patch_placement.chain_placements:
            if chain_placement.frame_role not in {FrameRole.H_FRAME, FrameRole.V_FRAME}:
                continue
            if chain_placement.chain_index < 0 or chain_placement.chain_index >= len(boundary_loop.chains):
                continue
            chain = boundary_loop.chains[chain_placement.chain_index]
            if len(chain.vert_cos) < 2:
                continue

            axis_kind = (
                FrameAxisKind.ROW
                if chain_placement.frame_role == FrameRole.H_FRAME
                else FrameAxisKind.COLUMN
            )
            if axis_kind == FrameAxisKind.ROW:
                class_key = _wall_side_row_class_key(chain)
            else:
                class_key = _wall_side_column_class_key(chain)
            ref = (patch_id, patch_placement.loop_index, chain_placement.chain_index)
            cross_uv = _frame_cross_axis_uv_value(chain_placement)
            weight = max(_runtime_chain_total_length(chain, final_scale), 1e-8)
            grouped_members.setdefault((axis_kind, node.semantic_key, class_key), []).append(
                FrameGroupMember(
                    ref=ref,
                    cross_uv=cross_uv,
                    weight=weight,
                    patch_id=patch_id,
                )
            )

    reports = []
    for (axis_kind, semantic_key, class_key), members in grouped_members.items():
        if len(members) < 2:
            continue

        total_weight = sum(member.weight for member in members)
        if total_weight <= 1e-8:
            continue
        target_cross_uv = sum(member.cross_uv * member.weight for member in members) / total_weight
        scatter_values = [abs(member.cross_uv - target_cross_uv) for member in members]
        display_coords = _frame_group_display_coords(axis_kind, class_key)

        reports.append(ScaffoldFrameAlignmentReport(
            axis_kind=axis_kind,
            semantic_key=semantic_key,
            frame_role=FrameRole.H_FRAME if axis_kind == FrameAxisKind.ROW else FrameRole.V_FRAME,
            class_coord_a=display_coords.coord_a,
            class_coord_b=display_coords.coord_b,
            chain_count=len(members),
            total_weight=total_weight,
            target_cross_uv=target_cross_uv,
            scatter_max=max(scatter_values),
            scatter_mean=sum(scatter_values) / float(len(scatter_values)),
            closure_sensitive=any(member.patch_id in closure_sensitive_patch_ids for member in members),
            member_refs=tuple(sorted(member.ref for member in members)),
        ))

    reports.sort(
        key=lambda report: (
            -report.scatter_max,
            -report.scatter_mean,
            report.axis_kind.value,
            report.class_coord_a,
            report.class_coord_b,
        )
    )
    return tuple(reports)


def _print_quilt_frame_alignment_reports(
    quilt_index: int,
    frame_alignment_reports: tuple[ScaffoldFrameAlignmentReport, ...],
) -> None:
    if not frame_alignment_reports or not is_verbose_console_enabled():
        return

    max_row_scatter = max(
        (report.scatter_max for report in frame_alignment_reports if report.axis_kind == FrameAxisKind.ROW),
        default=0.0,
    )
    max_column_scatter = max(
        (report.scatter_max for report in frame_alignment_reports if report.axis_kind == FrameAxisKind.COLUMN),
        default=0.0,
    )
    trace_console(
        f"[CFTUV][FrameDiag] Quilt {quilt_index}: "
        f"groups={len(frame_alignment_reports)} "
        f"max_row_scatter={max_row_scatter:.6f} "
        f"max_column_scatter={max_column_scatter:.6f}"
    )
    for report in frame_alignment_reports:
        coord_label = (
            f"z:{report.class_coord_a:.6f}"
            if report.axis_kind == FrameAxisKind.ROW
            else f"xy:({report.class_coord_a:.6f},{report.class_coord_b:.6f})"
        )
        refs_label = ','.join(
            f"P{patch_id}L{loop_index}C{chain_index}"
            for patch_id, loop_index, chain_index in report.member_refs
        )
        closure_tag = " closure:1" if report.closure_sensitive else " closure:0"
        trace_console(
            f"[CFTUV][FrameDiag] Quilt {quilt_index} "
            f"{report.axis_kind.value} {report.frame_role.value} {coord_label} "
            f"chains:{report.chain_count} target:{report.target_cross_uv:.6f} "
            f"scatter:{report.scatter_max:.6f}/{report.scatter_mean:.6f} "
            f"weight:{report.total_weight:.6f}{closure_tag} refs:[{refs_label}]"
        )
