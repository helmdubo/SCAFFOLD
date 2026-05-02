from __future__ import annotations

from typing import Any, Callable, Optional

from mathutils import Vector

try:
    from .console_debug import trace_console
    from .frontier_place import (
        _build_temporary_chain_placement,
        _cf_anchor_count,
        _cf_anchor_debug_label,
        _cf_chain_total_length,
        _cf_determine_direction_for_role,
        _cf_place_chain,
        _default_role_direction,
        _normalize_direction,
        _resolve_straighten_axis,
        _snap_direction_to_role,
        _try_inherit_direction,
    )
    from .frontier_state import FrontierRuntimePolicy, _mark_neighbors_dirty
    from .model import (
        BandMode,
        BoundaryChain,
        ChainNeighborKind,
        ChainRef,
        FrameRole,
        PatchEdgeKey,
        PatchGraph,
        PatchNode,
        PatchType,
        PlacementSourceKind,
        ScaffoldChainPlacement,
        ScaffoldPointKey,
        SpanAuthorityKind,
    )
    from .solve_diagnostics import (
        _chain_uv_axis_metrics,
        _measure_shared_closure_uv_offsets,
    )
    from .solve_records import (
        CHAIN_FRONTIER_THRESHOLD,
        AnchorAdjustment,
        AnchorOption,
        AnchorPairSafetyDecision,
        AnchorRefPair,
        ChainAnchor,
        ChainPoolEntry,
        ClosurePreconstraintApplication,
        ClosurePreconstraintMetric,
        ClosurePreconstraintOptionResult,
        CornerScoringHints,
        DirectionOption,
        DualAnchorClosureDecision,
        DualAnchorRectificationPreview,
        FoundCandidateAnchors,
        FrontierCandidateEval,
        FrontierLocalScoreDetails,
        FrontierPlacementCandidate,
        FrontierRank,
        FrontierRankBreakdown,
        FrontierStopDiagnostics,
        FrontierTopologyFacts,
        PatchScoringContext,
        PointRegistry,
        ResolvedCandidateAnchors,
        SeamRelationProfile,
        SeedChainChoice,
        SolveView,
        VertexPlacementMap,
        _point_registry_key,
    )
except ImportError:
    from console_debug import trace_console
    from frontier_place import (
        _build_temporary_chain_placement,
        _cf_anchor_count,
        _cf_anchor_debug_label,
        _cf_chain_total_length,
        _cf_determine_direction_for_role,
        _cf_place_chain,
        _default_role_direction,
        _normalize_direction,
        _resolve_straighten_axis,
        _snap_direction_to_role,
        _try_inherit_direction,
    )
    from frontier_state import FrontierRuntimePolicy, _mark_neighbors_dirty
    from model import (
        BandMode,
        BoundaryChain,
        ChainNeighborKind,
        ChainRef,
        FrameRole,
        PatchEdgeKey,
        PatchGraph,
        PatchNode,
        PatchType,
        PlacementSourceKind,
        ScaffoldChainPlacement,
        ScaffoldPointKey,
        SpanAuthorityKind,
    )
    from solve_diagnostics import (
        _chain_uv_axis_metrics,
        _measure_shared_closure_uv_offsets,
    )
    from solve_records import (
        CHAIN_FRONTIER_THRESHOLD,
        AnchorAdjustment,
        AnchorOption,
        AnchorPairSafetyDecision,
        AnchorRefPair,
        ChainAnchor,
        ChainPoolEntry,
        ClosurePreconstraintApplication,
        ClosurePreconstraintMetric,
        ClosurePreconstraintOptionResult,
        CornerScoringHints,
        DirectionOption,
        DualAnchorClosureDecision,
        DualAnchorRectificationPreview,
        FoundCandidateAnchors,
        FrontierCandidateEval,
        FrontierLocalScoreDetails,
        FrontierPlacementCandidate,
        FrontierRank,
        FrontierRankBreakdown,
        FrontierStopDiagnostics,
        FrontierTopologyFacts,
        PatchScoringContext,
        PointRegistry,
        ResolvedCandidateAnchors,
        SeamRelationProfile,
        SeedChainChoice,
        SolveView,
        VertexPlacementMap,
        _point_registry_key,
    )


def _closure_preconstraint_direction_options(
    chain_ref: ChainRef,
    chain: BoundaryChain,
    node: PatchNode,
    effective_role: FrameRole,
    start_anchor: Optional[ChainAnchor],
    end_anchor: Optional[ChainAnchor],
    graph: PatchGraph,
    point_registry: PointRegistry,
    placed_chains_map: dict[ChainRef, ScaffoldChainPlacement],
) -> list[DirectionOption]:
    options = [DirectionOption(label='default', direction_override=None)]
    if effective_role not in {FrameRole.H_FRAME, FrameRole.V_FRAME}:
        return options

    base_direction = _try_inherit_direction(
        chain,
        node,
        start_anchor,
        end_anchor,
        graph,
        point_registry,
        chain_ref=chain_ref,
        effective_role=effective_role,
        placed_chains_map=placed_chains_map,
    )
    if base_direction is None:
        base_direction = _cf_determine_direction_for_role(chain, node, effective_role)
    axis_direction = _snap_direction_to_role(base_direction, effective_role)
    axis_direction = _normalize_direction(axis_direction, _default_role_direction(effective_role))
    flipped_direction = Vector((-axis_direction.x, -axis_direction.y))
    if (flipped_direction - axis_direction).length > 1e-8:
        options.append(DirectionOption(label='flip', direction_override=flipped_direction))
    return options


def _closure_preconstraint_metric(
    graph: PatchGraph,
    chain_ref: ChainRef,
    chain: BoundaryChain,
    effective_role: FrameRole,
    uv_points: list[Vector],
    start_anchor: Optional[ChainAnchor],
    end_anchor: Optional[ChainAnchor],
    raw_start_anchor: Optional[ChainAnchor],
    raw_end_anchor: Optional[ChainAnchor],
    partner_placement: ScaffoldChainPlacement,
) -> ClosurePreconstraintMetric:
    temporary_placement = _build_temporary_chain_placement(
        chain_ref,
        chain,
        uv_points,
        start_anchor,
        end_anchor,
        effective_role=effective_role,
    )
    shared_offsets = _measure_shared_closure_uv_offsets(graph, temporary_placement, partner_placement)
    predicted_uv_span = _chain_uv_axis_metrics(temporary_placement).span
    partner_uv_span = _chain_uv_axis_metrics(partner_placement).span
    span_mismatch = abs(predicted_uv_span - partner_uv_span)

    same_patch_gap_max = 0.0
    all_gap_max = 0.0
    all_gap_sum = 0.0
    gap_count = 0
    for raw_anchor, predicted_uv in (
        (raw_start_anchor, uv_points[0]),
        (raw_end_anchor, uv_points[-1]),
    ):
        if raw_anchor is None:
            continue
        gap = (predicted_uv - raw_anchor.uv).length
        all_gap_max = max(all_gap_max, gap)
        all_gap_sum += gap
        gap_count += 1
        if raw_anchor.source_kind == PlacementSourceKind.SAME_PATCH:
            same_patch_gap_max = max(same_patch_gap_max, gap)

    all_gap_mean = all_gap_sum / gap_count if gap_count > 0 else 0.0
    return ClosurePreconstraintMetric(
        same_patch_gap_max,
        shared_offsets.axis_phase_offset_max,
        all_gap_max,
        span_mismatch,
        shared_offsets.axis_phase_offset_mean,
        all_gap_mean,
    )


def _cf_apply_closure_preconstraint(
    chain_ref: ChainRef,
    chain: BoundaryChain,
    node: PatchNode,
    effective_role: FrameRole,
    raw_start_anchor: Optional[ChainAnchor],
    raw_end_anchor: Optional[ChainAnchor],
    start_anchor: Optional[ChainAnchor],
    end_anchor: Optional[ChainAnchor],
    known: int,
    graph: PatchGraph,
    point_registry: PointRegistry,
    placed_chains_map: dict[ChainRef, ScaffoldChainPlacement],
    closure_pair_map: dict[ChainRef, ChainRef],
    final_scale: float,
    runtime_policy: FrontierRuntimePolicy,
) -> ClosurePreconstraintApplication:
    if known != 1 or effective_role not in {FrameRole.H_FRAME, FrameRole.V_FRAME}:
        return ClosurePreconstraintApplication(start_anchor=start_anchor, end_anchor=end_anchor)

    partner_ref = closure_pair_map.get(chain_ref)
    if partner_ref is None:
        return ClosurePreconstraintApplication(start_anchor=start_anchor, end_anchor=end_anchor)
    partner_placement = placed_chains_map.get(partner_ref)
    if partner_placement is None or len(partner_placement.points) < 2:
        return ClosurePreconstraintApplication(start_anchor=start_anchor, end_anchor=end_anchor)

    anchor_options: list[AnchorOption] = []
    seen_anchor_keys: set[AnchorRefPair] = set()
    for anchor_label, option_start, option_end in (
        ('resolved', start_anchor, end_anchor),
        ('start_only', raw_start_anchor, None),
        ('end_only', None, raw_end_anchor),
    ):
        if _cf_anchor_count(option_start, option_end) != 1:
            continue
        anchor_key: AnchorRefPair = (
            option_start.source_ref if option_start is not None else None,
            option_end.source_ref if option_end is not None else None,
        )
        if anchor_key in seen_anchor_keys:
            continue
        seen_anchor_keys.add(anchor_key)
        anchor_options.append(AnchorOption(
            label=anchor_label,
            start_anchor=option_start,
            end_anchor=option_end,
        ))

    if not anchor_options:
        return ClosurePreconstraintApplication(start_anchor=start_anchor, end_anchor=end_anchor)

    option_results: list[ClosurePreconstraintOptionResult] = []
    for anchor_option in anchor_options:
        direction_options = _closure_preconstraint_direction_options(
            chain_ref,
            chain,
            node,
            effective_role,
            anchor_option.start_anchor,
            anchor_option.end_anchor,
            graph,
            point_registry,
            placed_chains_map,
        )
        for direction_option in direction_options:
            uv_points = _cf_place_chain(
                chain,
                node,
                anchor_option.start_anchor,
                anchor_option.end_anchor,
                final_scale,
                direction_option.direction_override,
                placed_chains_map=placed_chains_map,
                graph=graph,
                effective_role=effective_role,
                chain_ref=chain_ref,
                runtime_policy=runtime_policy,
            )
            if not uv_points or len(uv_points) != len(chain.vert_cos):
                continue
            metric = _closure_preconstraint_metric(
                graph,
                chain_ref,
                chain,
                effective_role,
                uv_points,
                anchor_option.start_anchor,
                anchor_option.end_anchor,
                raw_start_anchor,
                raw_end_anchor,
                partner_placement,
            )
            option_results.append(ClosurePreconstraintOptionResult(
                metric=metric,
                anchor_label=anchor_option.label,
                direction_label=direction_option.label,
                start_anchor=anchor_option.start_anchor,
                end_anchor=anchor_option.end_anchor,
                direction_override=direction_option.direction_override,
            ))

    if not option_results:
        return ClosurePreconstraintApplication(start_anchor=start_anchor, end_anchor=end_anchor)

    current_anchor_key: AnchorRefPair = (
        start_anchor.source_ref if start_anchor is not None else None,
        end_anchor.source_ref if end_anchor is not None else None,
    )
    current_metric = None
    best_result: Optional[ClosurePreconstraintOptionResult] = None
    for result in sorted(option_results, key=lambda item: item.metric):
        option_anchor_key: AnchorRefPair = (
            result.start_anchor.source_ref if result.start_anchor is not None else None,
            result.end_anchor.source_ref if result.end_anchor is not None else None,
        )
        if option_anchor_key == current_anchor_key and result.direction_label == 'default' and current_metric is None:
            current_metric = result.metric
        if best_result is None:
            best_result = result

    if best_result is None or current_metric is None:
        return ClosurePreconstraintApplication(start_anchor=start_anchor, end_anchor=end_anchor)

    if best_result.metric >= current_metric:
        return ClosurePreconstraintApplication(start_anchor=start_anchor, end_anchor=end_anchor)

    reason = (
        f"closure_preconstraint:{best_result.anchor_label}/{best_result.direction_label}"
        f":phase={best_result.metric.axis_phase_offset_max:.4f}"
        f":gap={best_result.metric.same_patch_gap_max:.4f}"
    )
    return ClosurePreconstraintApplication(
        start_anchor=best_result.start_anchor,
        end_anchor=best_result.end_anchor,
        direction_override=best_result.direction_override,
        reason=reason,
    )


def _cf_preview_frame_dual_anchor_rectification(
    chain_ref: ChainRef,
    chain: BoundaryChain,
    start_anchor: Optional[ChainAnchor],
    end_anchor: Optional[ChainAnchor],
    graph: PatchGraph,
    placed_chains_map: dict[ChainRef, ScaffoldChainPlacement],
    runtime_policy: FrontierRuntimePolicy,
    effective_role: Optional[FrameRole] = None,
) -> DualAnchorRectificationPreview:
    role = effective_role if effective_role is not None else chain.frame_role
    if role not in {FrameRole.H_FRAME, FrameRole.V_FRAME}:
        return DualAnchorRectificationPreview(start_anchor=start_anchor, end_anchor=end_anchor)
    if start_anchor is None or end_anchor is None:
        return DualAnchorRectificationPreview(start_anchor=start_anchor, end_anchor=end_anchor)
    if start_anchor.source_kind != PlacementSourceKind.SAME_PATCH or end_anchor.source_kind != PlacementSourceKind.SAME_PATCH:
        return DualAnchorRectificationPreview(start_anchor=start_anchor, end_anchor=end_anchor)

    def _anchor_source_score(anchor: ChainAnchor) -> int:
        source_chain = graph.get_chain(*anchor.source_ref)
        if source_chain is None:
            return 0
        placed_source = placed_chains_map.get(anchor.source_ref)
        source_role = placed_source.frame_role if placed_source is not None else source_chain.frame_role
        score = 0
        if anchor.source_kind == PlacementSourceKind.CROSS_PATCH:
            score += 4
        elif anchor.source_kind == PlacementSourceKind.SAME_PATCH:
            score += 2
        if source_role in {FrameRole.H_FRAME, FrameRole.V_FRAME}:
            score += 2
        if len(source_chain.vert_cos) <= 2:
            score += 1
        return score

    start_score = _anchor_source_score(start_anchor)
    end_score = _anchor_source_score(end_anchor)
    keep_start = start_score >= end_score
    fixed_anchor = start_anchor if keep_start else end_anchor
    adjustable_anchor = end_anchor if keep_start else start_anchor

    fixed_cross = fixed_anchor.uv.y if role == FrameRole.H_FRAME else fixed_anchor.uv.x
    fixed_axis = fixed_anchor.uv.x if role == FrameRole.H_FRAME else fixed_anchor.uv.y
    adjustable_axis = adjustable_anchor.uv.x if role == FrameRole.H_FRAME else adjustable_anchor.uv.y
    axis_sign = 1.0 if adjustable_axis >= fixed_axis else -1.0
    if abs(adjustable_axis - fixed_axis) <= 1e-8:
        axis_sign = 1.0
    target_span = runtime_policy.resolve_target_span(
        chain_ref,
        chain,
        start_anchor,
        end_anchor,
        effective_role=role,
    )
    span_tolerance = max(0.05, target_span * 0.15) if target_span > 1e-8 else 0.05

    if role == FrameRole.H_FRAME:
        rectified_uv = Vector((adjustable_anchor.uv.x, fixed_cross))
    else:
        rectified_uv = Vector((fixed_cross, adjustable_anchor.uv.y))

    rectified_axis = rectified_uv.x if role == FrameRole.H_FRAME else rectified_uv.y
    current_span = abs(rectified_axis - fixed_axis)
    if target_span > 1e-8 and abs(current_span - target_span) > span_tolerance:
        resolved_axis = fixed_axis + axis_sign * target_span
        if role == FrameRole.H_FRAME:
            rectified_uv = Vector((resolved_axis, fixed_cross))
        else:
            rectified_uv = Vector((fixed_cross, resolved_axis))

    if (rectified_uv - adjustable_anchor.uv).length <= 1e-8:
        return DualAnchorRectificationPreview(start_anchor=start_anchor, end_anchor=end_anchor)

    rectified_anchor = ChainAnchor(
        uv=rectified_uv.copy(),
        source_ref=adjustable_anchor.source_ref,
        source_point_index=adjustable_anchor.source_point_index,
        source_kind=adjustable_anchor.source_kind,
    )
    anchor_adjustment = (
        adjustable_anchor.source_ref,
        adjustable_anchor.source_point_index,
        rectified_uv.copy(),
    )

    reason = 'frame_dual_anchor_rectify:keep_start' if keep_start else 'frame_dual_anchor_rectify:keep_end'
    if keep_start:
        return DualAnchorRectificationPreview(
            start_anchor=start_anchor,
            end_anchor=rectified_anchor,
            reason=reason,
            anchor_adjustments=(anchor_adjustment,),
        )
    return DualAnchorRectificationPreview(
        start_anchor=rectified_anchor,
        end_anchor=end_anchor,
        reason=reason,
        anchor_adjustments=(anchor_adjustment,),
    )


def _cf_seed_cross_patch_hv_bonus(
    chain: BoundaryChain,
    graph: PatchGraph,
    neighbor_patch_id: int,
) -> float:
    """Бонус если парный chain на соседнем патче — H/V (shared seam edges).

    Находит chain на neighbor_patch_id, у которого есть общие edge_indices
    с нашим chain. Если этот парный chain тоже H/V — возвращает бонус.
    """
    neighbor_node = graph.nodes.get(neighbor_patch_id)
    if neighbor_node is None:
        return 0.0
    own_edges = set(chain.edge_indices)
    if not own_edges:
        return 0.0
    for loop in neighbor_node.boundary_loops:
        for nb_chain in loop.chains:
            if not set(nb_chain.edge_indices) & own_edges:
                continue
            if nb_chain.frame_role in (FrameRole.H_FRAME, FrameRole.V_FRAME):
                return 0.6
    return 0.0


def _cf_choose_seed_chain(
    solve_view: SolveView,
    graph: PatchGraph,
    root_node: PatchNode,
    quilt_patch_ids: set[int],
    allowed_tree_edges: set[PatchEdgeKey],
    *,
    is_allowed_quilt_edge: Callable[[set[PatchEdgeKey], int, int], bool],
    count_hv_adjacent_endpoints: Callable[[PatchGraph, ChainRef], int],
) -> Optional[SeedChainChoice]:
    best_ref: Optional[SeedChainChoice] = None
    best_rank: Optional[tuple[int, int, float, float]] = None

    for loop_idx, loop in solve_view.iter_visible_loops(root_node.patch_id):
        for chain_idx, chain in enumerate(loop.chains):
            chain_ref = (root_node.patch_id, loop_idx, chain_idx)
            is_hv = chain.frame_role in (FrameRole.H_FRAME, FrameRole.V_FRAME)
            hv_adjacency = count_hv_adjacent_endpoints(graph, chain_ref)

            score = 0.0
            chain_len = 0.0

            if is_hv:
                score += 1.0
                # H/V без соседних H/V — допускаем как seed, но с пониженным score
                if hv_adjacency <= 0:
                    score -= 0.5
            else:
                score += 0.1

            if len(chain.vert_cos) > 1:
                chain_len = sum(
                    (chain.vert_cos[i + 1] - chain.vert_cos[i]).length
                    for i in range(len(chain.vert_cos) - 1)
                )
                score += min(chain_len * 0.1, 0.5)

            # Бонус за cross-patch соседа (seam boundary ценнее MESH_BORDER как seed).
            # Работает вне зависимости от quilt membership.
            if is_hv and chain.neighbor_kind == ChainNeighborKind.PATCH:
                score += 0.3
                # Дополнительно: если парный chain на соседнем патче тоже H/V
                xp_hv_bonus = _cf_seed_cross_patch_hv_bonus(
                    chain, graph, chain.neighbor_patch_id,
                )
                score += xp_hv_bonus

            if (
                chain.neighbor_kind == ChainNeighborKind.PATCH
                and chain.neighbor_patch_id in quilt_patch_ids
                and is_allowed_quilt_edge(allowed_tree_edges, root_node.patch_id, chain.neighbor_patch_id)
            ):
                neighbor_key = graph.get_patch_semantic_key(chain.neighbor_patch_id)
                patch_type = root_node.patch_type.value if hasattr(root_node.patch_type, 'value') else str(root_node.patch_type)
                if patch_type == 'WALL':
                    if neighbor_key == 'FLOOR.DOWN':
                        score += 0.5
                    elif neighbor_key == 'FLOOR.UP':
                        score += 0.2
                    elif neighbor_key.endswith('.SIDE'):
                        score += 0.15
                else:
                    if neighbor_key.endswith('.SIDE'):
                        score += 0.2

            rank = (
                1 if is_hv else 0,
                hv_adjacency if is_hv else -1,
                score,
                chain_len,
            )
            if best_rank is None or rank > best_rank:
                best_rank = rank
                best_ref = SeedChainChoice(
                    loop_index=loop_idx,
                    chain_index=chain_idx,
                    chain=chain,
                    score=score,
                )

    return best_ref


def _cf_find_anchors(
    chain_ref: ChainRef,
    chain: BoundaryChain,
    graph: PatchGraph,
    point_registry: PointRegistry,
    vert_to_placements: VertexPlacementMap,
    placed_refs: set[ChainRef],
    allowed_tree_edges: set[PatchEdgeKey],
    *,
    is_allowed_quilt_edge: Callable[[set[PatchEdgeKey], int, int], bool],
) -> FoundCandidateAnchors:
    patch_id, loop_index, chain_index = chain_ref
    node = graph.nodes.get(patch_id)
    if node is None or loop_index >= len(node.boundary_loops):
        return FoundCandidateAnchors(start_anchor=None, end_anchor=None)

    boundary_loop = node.boundary_loops[loop_index]
    start_vert = chain.start_vert_index
    end_vert = chain.end_vert_index
    seam_neighbor_patch_id = chain.neighbor_patch_id if chain.neighbor_kind == ChainNeighborKind.PATCH else None
    start_anchor = None
    end_anchor = None

    # ARCHITECTURAL_DEBT: F3_LOOP_PREVNEXT
    # Same-patch prev/next lookup still walks loop corners ad hoc here instead
    # of consuming explicit prev/next links on ChainUse. See the ledger doc.
    for corner in boundary_loop.corners:
        prev_ci = corner.prev_chain_index
        next_ci = corner.next_chain_index

        if next_ci == chain_index and start_anchor is None:
            prev_ref = (patch_id, loop_index, prev_ci)
            if prev_ref in placed_refs:
                prev_chain = boundary_loop.chains[prev_ci]
                prev_last = len(prev_chain.vert_indices) - 1
                if prev_last >= 0:
                    key = _point_registry_key(prev_ref, prev_last)
                    if key in point_registry:
                        start_anchor = ChainAnchor(
                            uv=point_registry[key].copy(),
                            source_ref=prev_ref,
                            source_point_index=prev_last,
                            source_kind=PlacementSourceKind.SAME_PATCH,
                        )

        if prev_ci == chain_index and end_anchor is None:
            next_ref = (patch_id, loop_index, next_ci)
            if next_ref in placed_refs:
                key = _point_registry_key(next_ref, 0)
                if key in point_registry:
                    end_anchor = ChainAnchor(
                        uv=point_registry[key].copy(),
                        source_ref=next_ref,
                        source_point_index=0,
                        source_kind=PlacementSourceKind.SAME_PATCH,
                    )

    if start_anchor is None and start_vert >= 0 and start_vert in vert_to_placements:
        for other_ref, pt_idx in vert_to_placements[start_vert]:
            if other_ref[0] == patch_id:
                continue

            is_junction_allowed = False
            if seam_neighbor_patch_id is not None and other_ref[0] != seam_neighbor_patch_id:
                other_node = graph.nodes.get(other_ref[0])
                if other_node is not None:
                    t1, t2 = node.patch_type, other_node.patch_type
                    if (
                        (t1 == PatchType.WALL and t2 in (PatchType.FLOOR, PatchType.SLOPE))
                        or (t2 == PatchType.WALL and t1 in (PatchType.FLOOR, PatchType.SLOPE))
                    ):
                        is_junction_allowed = True

            if seam_neighbor_patch_id is not None and other_ref[0] != seam_neighbor_patch_id and not is_junction_allowed:
                continue
            if not is_allowed_quilt_edge(allowed_tree_edges, patch_id, other_ref[0]):
                continue
            key = _point_registry_key(other_ref, pt_idx)
            if key in point_registry:
                start_anchor = ChainAnchor(
                    uv=point_registry[key].copy(),
                    source_ref=other_ref,
                    source_point_index=pt_idx,
                    source_kind=PlacementSourceKind.CROSS_PATCH,
                )
                break

    if end_anchor is None and end_vert >= 0 and end_vert in vert_to_placements:
        for other_ref, pt_idx in vert_to_placements[end_vert]:
            if other_ref[0] == patch_id:
                continue

            is_junction_allowed = False
            if seam_neighbor_patch_id is not None and other_ref[0] != seam_neighbor_patch_id:
                other_node = graph.nodes.get(other_ref[0])
                if other_node is not None:
                    t1, t2 = node.patch_type, other_node.patch_type
                    if (
                        (t1 == PatchType.WALL and t2 in (PatchType.FLOOR, PatchType.SLOPE))
                        or (t2 == PatchType.WALL and t1 in (PatchType.FLOOR, PatchType.SLOPE))
                    ):
                        is_junction_allowed = True

            if seam_neighbor_patch_id is not None and other_ref[0] != seam_neighbor_patch_id and not is_junction_allowed:
                continue
            if not is_allowed_quilt_edge(allowed_tree_edges, patch_id, other_ref[0]):
                continue
            key = _point_registry_key(other_ref, pt_idx)
            if key in point_registry:
                end_anchor = ChainAnchor(
                    uv=point_registry[key].copy(),
                    source_ref=other_ref,
                    source_point_index=pt_idx,
                    source_kind=PlacementSourceKind.CROSS_PATCH,
                )
                break

    return FoundCandidateAnchors(start_anchor=start_anchor, end_anchor=end_anchor)


def _cf_frame_anchor_pair_is_axis_safe(
    chain: BoundaryChain,
    start_anchor: ChainAnchor,
    end_anchor: ChainAnchor,
    final_scale: float,
    effective_role: Optional[FrameRole] = None,
    target_span: Optional[float] = None,
) -> AnchorPairSafetyDecision:
    role = effective_role if effective_role is not None else chain.frame_role
    if role not in {FrameRole.H_FRAME, FrameRole.V_FRAME}:
        return AnchorPairSafetyDecision(is_safe=True)

    total_length = target_span if target_span is not None else _cf_chain_total_length(chain, final_scale)
    if total_length <= 1e-8:
        return AnchorPairSafetyDecision(is_safe=True)

    delta = end_anchor.uv - start_anchor.uv
    axis_error = abs(delta.y) if role == FrameRole.H_FRAME else abs(delta.x)
    axis_span = abs(delta.x) if role == FrameRole.H_FRAME else abs(delta.y)

    axis_tolerance = max(0.02, total_length * 0.05)
    span_tolerance = max(0.05, total_length * 0.15)

    if axis_error > axis_tolerance:
        return AnchorPairSafetyDecision(is_safe=False, reason='axis_mismatch')
    if abs(axis_span - total_length) > span_tolerance:
        return AnchorPairSafetyDecision(is_safe=False, reason='span_mismatch')
    return AnchorPairSafetyDecision(is_safe=True)


def _cf_can_use_dual_anchor_closure(
    chain_ref: ChainRef,
    chain: BoundaryChain,
    start_anchor: ChainAnchor,
    end_anchor: ChainAnchor,
    placed_in_patch: int,
    final_scale: float,
    runtime_policy: FrontierRuntimePolicy,
    effective_role: Optional[FrameRole] = None,
) -> DualAnchorClosureDecision:
    role = effective_role if effective_role is not None else chain.frame_role
    spine = runtime_policy.band_spine(chain_ref[0]) if runtime_policy is not None else None
    if spine is not None and chain_ref in spine.chain_uv_targets:
        return DualAnchorClosureDecision(can_close=True)

    target_span = runtime_policy.resolve_target_span(
        chain_ref,
        chain,
        start_anchor,
        end_anchor,
        effective_role=role,
    )
    axis_safety = _cf_frame_anchor_pair_is_axis_safe(
        chain,
        start_anchor,
        end_anchor,
        final_scale,
        effective_role=role,
        target_span=target_span,
    )
    if not axis_safety.is_safe:
        if (
            axis_safety.reason in ('span_mismatch', 'axis_mismatch')
            and role in {FrameRole.H_FRAME, FrameRole.V_FRAME}
            and start_anchor.source_kind == PlacementSourceKind.SAME_PATCH
            and end_anchor.source_kind == PlacementSourceKind.SAME_PATCH
        ):
            axis_safety = AnchorPairSafetyDecision(is_safe=True)
        else:
            return DualAnchorClosureDecision(can_close=False, reason=axis_safety.reason)

    if (
        start_anchor.source_kind == PlacementSourceKind.CROSS_PATCH
        and end_anchor.source_kind == PlacementSourceKind.CROSS_PATCH
    ):
        if role == FrameRole.FREE and len(chain.vert_cos) <= 2:
            return DualAnchorClosureDecision(can_close=True)
        return DualAnchorClosureDecision(can_close=False, reason='prevent_patch_wrap')

    return DualAnchorClosureDecision(can_close=True)


def _cf_resolve_candidate_anchors(
    chain_ref: ChainRef,
    chain: BoundaryChain,
    start_anchor: Optional[ChainAnchor],
    end_anchor: Optional[ChainAnchor],
    placed_in_patch: int,
    final_scale: float,
    graph: PatchGraph,
    placed_chains_map: dict[ChainRef, ScaffoldChainPlacement],
    runtime_policy: FrontierRuntimePolicy,
    effective_role: Optional[FrameRole] = None,
) -> ResolvedCandidateAnchors:
    role = effective_role if effective_role is not None else chain.frame_role
    base_role = runtime_policy.effective_placement_role(chain_ref, chain)
    known = _cf_anchor_count(start_anchor, end_anchor)
    spine = runtime_policy.band_spine(chain_ref[0]) if runtime_policy is not None else None
    if spine is not None and chain_ref in spine.chain_uv_targets:
        return ResolvedCandidateAnchors(
            start_anchor=start_anchor,
            end_anchor=end_anchor,
            known=known,
        )

    if runtime_policy.should_gate_inherited_same_patch(chain_ref, chain):
        same_patch_anchor_count = sum(
            1
            for anchor in (start_anchor, end_anchor)
            if anchor is not None and anchor.source_kind == PlacementSourceKind.SAME_PATCH
        )
        cross_patch_anchor_count = sum(
            1
            for anchor in (start_anchor, end_anchor)
            if anchor is not None and anchor.source_kind == PlacementSourceKind.CROSS_PATCH
        )
        if same_patch_anchor_count > 0 and cross_patch_anchor_count == 0:
            if role == base_role and runtime_policy._patch_band_mode(chain_ref[0]) == BandMode.NOT_BAND:
                return ResolvedCandidateAnchors(
                    start_anchor=None,
                    end_anchor=None,
                    known=0,
                    reason='gate_unresolved_inherited_same_patch',
                )
    if known < 2:
        return ResolvedCandidateAnchors(start_anchor=start_anchor, end_anchor=end_anchor, known=known)

    rectified = _cf_preview_frame_dual_anchor_rectification(
        chain_ref,
        chain,
        start_anchor,
        end_anchor,
        graph,
        placed_chains_map,
        runtime_policy,
        effective_role=role,
    )
    start_anchor = rectified.start_anchor
    end_anchor = rectified.end_anchor
    rect_reason = rectified.reason
    anchor_adjustments = rectified.anchor_adjustments

    closure_decision = _cf_can_use_dual_anchor_closure(
        chain_ref,
        chain,
        start_anchor,
        end_anchor,
        placed_in_patch,
        final_scale,
        runtime_policy,
        effective_role=role,
    )
    if closure_decision.can_close:
        return ResolvedCandidateAnchors(
            start_anchor=start_anchor,
            end_anchor=end_anchor,
            known=2,
            reason=rect_reason,
            anchor_adjustments=anchor_adjustments,
        )
    reason = closure_decision.reason

    if (
        start_anchor is not None and end_anchor is not None
        and start_anchor.source_kind == PlacementSourceKind.SAME_PATCH
        and end_anchor.source_kind == PlacementSourceKind.SAME_PATCH
        and role in {FrameRole.H_FRAME, FrameRole.V_FRAME}
        and chain.neighbor_kind == ChainNeighborKind.MESH_BORDER
    ):
        reason_note = f'{rect_reason}|{reason}' if rect_reason else reason
        return ResolvedCandidateAnchors(
            start_anchor=None,
            end_anchor=None,
            known=0,
            reason=f'{reason_note}:reject_same_patch_axis_mismatch',
        )

    if start_anchor is not None and start_anchor.source_kind == PlacementSourceKind.SAME_PATCH and (
        end_anchor is None or end_anchor.source_kind != PlacementSourceKind.SAME_PATCH
    ):
        reason_note = f'{rect_reason}|{reason}' if rect_reason else reason
        return ResolvedCandidateAnchors(
            start_anchor=start_anchor,
            end_anchor=None,
            known=1,
            reason=f'{reason_note}:drop_end',
        )
    if end_anchor is not None and end_anchor.source_kind == PlacementSourceKind.SAME_PATCH and (
        start_anchor is None or start_anchor.source_kind != PlacementSourceKind.SAME_PATCH
    ):
        reason_note = f'{rect_reason}|{reason}' if rect_reason else reason
        return ResolvedCandidateAnchors(
            start_anchor=None,
            end_anchor=end_anchor,
            known=1,
            reason=f'{reason_note}:drop_start',
        )

    if (
        start_anchor is not None and end_anchor is not None
        and start_anchor.source_kind == PlacementSourceKind.SAME_PATCH
        and end_anchor.source_kind == PlacementSourceKind.SAME_PATCH
        and role in {FrameRole.H_FRAME, FrameRole.V_FRAME}
    ):
        reason_note = f'{rect_reason}|{reason}' if rect_reason else reason
        return ResolvedCandidateAnchors(
            start_anchor=start_anchor,
            end_anchor=None,
            known=1,
            reason=f'{reason_note}:axis_soft_from_start',
        )

    return ResolvedCandidateAnchors(start_anchor=None, end_anchor=None, known=0, reason=reason)


def evaluate_candidate(
    runtime_policy: FrontierRuntimePolicy,
    chain_ref: ChainRef,
    chain: BoundaryChain,
    node: PatchNode,
    apply_closure_preconstraint: bool = False,
    compute_score: bool = False,
    *,
    is_allowed_quilt_edge: Callable[[set[PatchEdgeKey], int, int], bool],
    build_patch_scoring_context: Callable[[ChainRef, FrontierRuntimePolicy], PatchScoringContext],
    chain_seam_relation: Callable[[ChainRef, BoundaryChain, FrontierRuntimePolicy], Optional[SeamRelationProfile]],
    build_corner_scoring_hints: Callable[[ChainRef, BoundaryChain, PatchGraph, FrontierRuntimePolicy, Optional[FrameRole]], CornerScoringHints],
    score_candidate: Callable[..., tuple[float, FrontierTopologyFacts, FrontierLocalScoreDetails]],
    build_frontier_rank: Callable[..., tuple[FrontierRank, FrontierRankBreakdown]],
) -> FrontierCandidateEval:
    found_anchors = _cf_find_anchors(
        chain_ref,
        chain,
        runtime_policy.graph,
        runtime_policy.point_registry,
        runtime_policy.vert_to_placements,
        runtime_policy.placed_chain_refs,
        runtime_policy.allowed_tree_edges,
        is_allowed_quilt_edge=is_allowed_quilt_edge,
    )
    raw_start_anchor = found_anchors.start_anchor
    raw_end_anchor = found_anchors.end_anchor

    placed_in_patch = runtime_policy.placed_in_patch(chain_ref[0])
    base_eff_role = runtime_policy.effective_placement_role(chain_ref, chain)
    candidate_role = runtime_policy.candidate_placement_role(
        chain_ref,
        chain,
        raw_start_anchor,
        raw_end_anchor,
        effective_role=base_eff_role,
    )
    eff_role = runtime_policy.continuation_placement_role(
        chain_ref,
        chain,
        raw_start_anchor,
        raw_end_anchor,
        effective_role=candidate_role,
    )
    # For axis-dependent anchor resolution, resolve STRAIGHTEN → H/V.
    # The original eff_role (possibly STRAIGHTEN) is kept for scoring/tier.
    anchor_role = _resolve_straighten_axis(chain, node) if eff_role == FrameRole.STRAIGHTEN else eff_role
    patch_context = build_patch_scoring_context(chain_ref, runtime_policy)
    seam_relation = chain_seam_relation(chain_ref, chain, runtime_policy)
    resolved_anchors = _cf_resolve_candidate_anchors(
        chain_ref,
        chain,
        raw_start_anchor,
        raw_end_anchor,
        placed_in_patch,
        runtime_policy.final_scale,
        runtime_policy.graph,
        runtime_policy.placed_chains_map,
        runtime_policy,
        effective_role=anchor_role,
    )
    start_anchor = resolved_anchors.start_anchor
    end_anchor = resolved_anchors.end_anchor
    known = resolved_anchors.known
    anchor_reason = resolved_anchors.reason
    anchor_adjustments = resolved_anchors.anchor_adjustments

    closure_dir_override = None
    if apply_closure_preconstraint and runtime_policy.closure_pair_map is not None:
        closure_application = _cf_apply_closure_preconstraint(
            chain_ref,
            chain,
            node,
            anchor_role,
            raw_start_anchor,
            raw_end_anchor,
            start_anchor,
            end_anchor,
            known,
            runtime_policy.graph,
            runtime_policy.point_registry,
            runtime_policy.placed_chains_map,
            runtime_policy.closure_pair_map,
            runtime_policy.final_scale,
            runtime_policy,
        )
        start_anchor = closure_application.start_anchor
        end_anchor = closure_application.end_anchor
        closure_dir_override = closure_application.direction_override
        closure_reason = closure_application.reason
        if closure_reason:
            anchor_reason = f"{anchor_reason}|{closure_reason}" if anchor_reason else closure_reason

    score = -1.0
    topology_facts = FrontierTopologyFacts()
    score_details = FrontierLocalScoreDetails()
    rank = None
    rank_breakdown = None
    corner_hints = None
    if compute_score and known > 0:
        corner_hints = build_corner_scoring_hints(chain_ref, chain, runtime_policy.graph, runtime_policy, eff_role)
        score, topology_facts, score_details = score_candidate(
            chain_ref,
            chain,
            node,
            known,
            runtime_policy.graph,
            patch_context,
            runtime_policy.quilt_patch_ids,
            runtime_policy.allowed_tree_edges,
            runtime_policy,
            corner_hints=corner_hints,
            seam_relation=seam_relation,
            closure_pair_refs=runtime_policy.closure_pair_refs or None,
            start_anchor=start_anchor,
            end_anchor=end_anchor,
            effective_role=eff_role,
        )
        rank, rank_breakdown = build_frontier_rank(
            chain_ref,
            chain,
            node,
            known,
            runtime_policy.graph,
            topology_facts,
            patch_context,
            runtime_policy.quilt_patch_ids,
            runtime_policy.allowed_tree_edges,
            runtime_policy,
            score,
            seam_relation=seam_relation,
            seam_bonus=score_details.seam_bonus,
            shape_bonus=score_details.shape_bonus,
            closure_pair_refs=runtime_policy.closure_pair_refs or None,
            start_anchor=start_anchor,
            end_anchor=end_anchor,
            effective_role=eff_role,
        )

    return FrontierCandidateEval(
        raw_start_anchor=raw_start_anchor,
        raw_end_anchor=raw_end_anchor,
        start_anchor=start_anchor,
        end_anchor=end_anchor,
        known=known,
        placed_in_patch=placed_in_patch,
        effective_role=eff_role,
        anchor_reason=anchor_reason,
        anchor_adjustments=anchor_adjustments,
        closure_dir_override=closure_dir_override,
        score=score,
        length_factor=score_details.length_factor,
        downstream_count=score_details.downstream_count,
        downstream_bonus=score_details.downstream_bonus,
        isolation_preview=topology_facts.would_be_connected,
        isolation_penalty=score_details.isolation_penalty,
        structural_free_bonus=score_details.structural_free_bonus,
        hv_adjacency=topology_facts.hv_adjacency,
        rank=rank,
        rank_breakdown=rank_breakdown,
        patch_context=patch_context,
        corner_hints=corner_hints,
        seam_relation=seam_relation,
        seam_bonus=score_details.seam_bonus,
        corner_bonus=score_details.corner_bonus,
        shape_bonus=score_details.shape_bonus,
    )


def build_stop_diagnostics(
    runtime_policy: FrontierRuntimePolicy,
    all_chain_pool: list[ChainPoolEntry],
    *,
    evaluate_candidate_fn: Callable[[FrontierRuntimePolicy, ChainRef, BoundaryChain, PatchNode], FrontierCandidateEval],
) -> FrontierStopDiagnostics:
    remaining_count = 0
    no_anchor_count = 0
    low_score_count = 0
    patches_with_no_anchor = set()
    untouched_patch_ids = set()

    for entry in all_chain_pool:
        chain_ref = entry.chain_ref
        if not runtime_policy.is_chain_available(chain_ref):
            continue
        remaining_count += 1
        untouched_patch_ids.add(chain_ref[0])
        candidate_eval = evaluate_candidate_fn(runtime_policy, chain_ref, entry.chain, entry.node)
        if candidate_eval.known == 0:
            no_anchor_count += 1
            patches_with_no_anchor.add(chain_ref[0])
        else:
            low_score_count += 1

    placed_patch_ids = set(runtime_policy.placed_patch_ids())
    return FrontierStopDiagnostics(
        remaining_count=remaining_count,
        no_anchor_count=no_anchor_count,
        low_score_count=low_score_count,
        rejected_count=len(runtime_policy.rejected_chain_refs),
        placed_patch_ids=tuple(sorted(placed_patch_ids)),
        untouched_patch_ids=tuple(sorted(untouched_patch_ids - placed_patch_ids)),
        no_anchor_patch_ids=tuple(sorted(patches_with_no_anchor)),
    )


def _cf_make_frontier_placement_candidate(
    entry: ChainPoolEntry,
    candidate_eval: FrontierCandidateEval,
) -> FrontierPlacementCandidate:
    return FrontierPlacementCandidate(
        chain_ref=entry.chain_ref,
        chain=entry.chain,
        node=entry.node,
        start_anchor=candidate_eval.start_anchor,
        end_anchor=candidate_eval.end_anchor,
        effective_role=candidate_eval.effective_role,
        anchor_reason=candidate_eval.anchor_reason,
        anchor_adjustments=candidate_eval.anchor_adjustments,
        closure_dir_override=candidate_eval.closure_dir_override,
        score=candidate_eval.score,
        length_factor=candidate_eval.length_factor,
        downstream_count=candidate_eval.downstream_count,
        downstream_bonus=candidate_eval.downstream_bonus,
        isolation_preview=candidate_eval.isolation_preview,
        isolation_penalty=candidate_eval.isolation_penalty,
        structural_free_bonus=candidate_eval.structural_free_bonus,
        hv_adjacency=candidate_eval.hv_adjacency,
        rank=candidate_eval.rank,
        rank_breakdown=candidate_eval.rank_breakdown,
        patch_context=candidate_eval.patch_context,
        corner_hints=candidate_eval.corner_hints,
        seam_relation=candidate_eval.seam_relation,
        seam_bonus=candidate_eval.seam_bonus,
        corner_bonus=candidate_eval.corner_bonus,
        shape_bonus=candidate_eval.shape_bonus,
    )


def select_best_frontier_candidate(
    runtime_policy: FrontierRuntimePolicy,
    all_chain_pool: list[ChainPoolEntry],
    *,
    evaluate_candidate_fn: Callable[..., FrontierCandidateEval],
) -> Optional[FrontierPlacementCandidate]:
    best_candidate: Optional[FrontierPlacementCandidate] = None
    best_rank: Optional[FrontierRank] = None
    best_viable_candidate: Optional[FrontierPlacementCandidate] = None
    best_viable_rank: Optional[FrontierRank] = None

    for entry in all_chain_pool:
        chain_ref = entry.chain_ref
        if not runtime_policy.is_chain_available(chain_ref):
            continue

        if chain_ref not in runtime_policy._dirty_refs:
            cached = runtime_policy._cached_evals.get(chain_ref)
            if cached is not None:
                runtime_policy._cache_hits += 1
                if cached.known == 0:
                    continue
                placement_candidate = _cf_make_frontier_placement_candidate(entry, cached)
                candidate_rank = cached.rank
                if candidate_rank is not None and (best_rank is None or candidate_rank > best_rank):
                    best_rank = candidate_rank
                    best_candidate = placement_candidate
                if (
                    candidate_rank is not None
                    and cached.score >= CHAIN_FRONTIER_THRESHOLD
                    and (best_viable_rank is None or candidate_rank > best_viable_rank)
                ):
                    best_viable_rank = candidate_rank
                    best_viable_candidate = placement_candidate
                continue

        candidate_eval = evaluate_candidate_fn(
            runtime_policy,
            chain_ref,
            entry.chain,
            entry.node,
            apply_closure_preconstraint=True,
            compute_score=True,
        )
        runtime_policy._cached_evals[chain_ref] = candidate_eval
        runtime_policy._dirty_refs.discard(chain_ref)

        if candidate_eval.known == 0:
            continue

        placement_candidate = _cf_make_frontier_placement_candidate(entry, candidate_eval)
        candidate_rank = candidate_eval.rank
        if candidate_rank is not None and (best_rank is None or candidate_rank > best_rank):
            best_rank = candidate_rank
            best_candidate = placement_candidate
        if (
            candidate_rank is not None
            and candidate_eval.score >= CHAIN_FRONTIER_THRESHOLD
            and (best_viable_rank is None or candidate_rank > best_viable_rank)
        ):
            best_viable_rank = candidate_rank
            best_viable_candidate = placement_candidate

    return best_viable_candidate or best_candidate


def try_place_frontier_candidate(
    runtime_policy: FrontierRuntimePolicy,
    candidate: FrontierPlacementCandidate,
    iteration: int,
    *,
    apply_anchor_adjustments_fn: Callable[
        [tuple[AnchorAdjustment, ...], PatchGraph, dict[ChainRef, ScaffoldChainPlacement], PointRegistry, float],
        bool,
    ],
    frontier_rank_debug_label: Callable[[Optional[FrontierRank]], str],
    collector: Optional[Any] = None,
) -> bool:
    graph = runtime_policy.graph
    chain_ref = candidate.chain_ref
    chain = candidate.chain
    placed_before = runtime_policy.placed_in_patch(chain_ref[0])
    eff_role = candidate.effective_role
    # Resolve STRAIGHTEN to H/V for axis-dependent placement logic.
    # Scoring already used the STRAIGHTEN identity for tier ranking.
    if eff_role == FrameRole.STRAIGHTEN:
        eff_role = _resolve_straighten_axis(chain, candidate.node)

    if candidate.anchor_adjustments:
        applied = apply_anchor_adjustments_fn(
            candidate.anchor_adjustments,
            graph,
            runtime_policy.placed_chains_map,
            runtime_policy.point_registry,
            runtime_policy.final_scale,
        )
        if not applied:
            runtime_policy.reject_chain(chain_ref)
            trace_console(
                f"[CFTUV][Frontier] Reject {iteration}: "
                f"P{chain_ref[0]} L{chain_ref[1]}C{chain_ref[2]} "
                f"{eff_role.value} reason:anchor_rectify_failed"
            )
            return False
        for adjusted_ref, _, _ in candidate.anchor_adjustments:
            adjusted_chain = graph.get_chain(*adjusted_ref)
            if adjusted_chain is not None:
                _mark_neighbors_dirty(runtime_policy, adjusted_ref, adjusted_chain)

    dir_override = candidate.closure_dir_override
    closure_dir_was_set = dir_override is not None
    if dir_override is None:
        dir_override = _try_inherit_direction(
            chain,
            candidate.node,
            candidate.start_anchor,
            candidate.end_anchor,
            graph,
            runtime_policy.point_registry,
            chain_ref=chain_ref,
            effective_role=eff_role,
            placed_chains_map=runtime_policy.placed_chains_map,
        )
    direction_inherited = dir_override is not None and not closure_dir_was_set

    uv_points = _cf_place_chain(
        chain,
        candidate.node,
        candidate.start_anchor,
        candidate.end_anchor,
        runtime_policy.final_scale,
        dir_override,
        placed_chains_map=runtime_policy.placed_chains_map,
        graph=runtime_policy.graph,
        effective_role=eff_role,
        chain_ref=chain_ref,
        runtime_policy=runtime_policy,
    )
    if not uv_points or len(uv_points) != len(chain.vert_cos):
        runtime_policy.reject_chain(chain_ref)
        trace_console(
            f"[CFTUV][Frontier] Reject {iteration}: "
            f"P{chain_ref[0]} L{chain_ref[1]}C{chain_ref[2]} "
            f"{eff_role.value} reason:placement_failed"
        )
        return False

    anchor_count = _cf_anchor_count(candidate.start_anchor, candidate.end_anchor)
    if candidate.start_anchor is not None:
        primary_anchor_kind = candidate.start_anchor.source_kind
    elif candidate.end_anchor is not None:
        primary_anchor_kind = candidate.end_anchor.source_kind
    else:
        primary_anchor_kind = PlacementSourceKind.CHAIN
    axis_authority_kind = runtime_policy.resolve_axis_authority_kind(
        chain_ref,
        chain,
        candidate.start_anchor,
        candidate.end_anchor,
        effective_role=eff_role,
    )
    span_authority_kind = runtime_policy.resolve_span_authority_kind(
        chain_ref,
        chain,
        candidate.start_anchor,
        candidate.end_anchor,
        effective_role=eff_role,
    )
    station_authority_kind = runtime_policy.resolve_station_authority_kind(
        chain_ref,
        chain,
        candidate.start_anchor,
        candidate.end_anchor,
        effective_role=eff_role,
    )
    parameter_authority_kind = runtime_policy.resolve_parameter_authority_kind(
        chain_ref,
        chain,
        candidate.start_anchor,
        candidate.end_anchor,
        effective_role=eff_role,
    )
    chain_placement = ScaffoldChainPlacement(
        patch_id=chain_ref[0],
        loop_index=chain_ref[1],
        chain_index=chain_ref[2],
        frame_role=eff_role,
        axis_authority_kind=axis_authority_kind,
        span_authority_kind=span_authority_kind,
        station_authority_kind=station_authority_kind,
        parameter_authority_kind=parameter_authority_kind,
        source_kind=PlacementSourceKind.CHAIN,
        anchor_count=anchor_count,
        primary_anchor_kind=primary_anchor_kind,
        points=tuple(
            (ScaffoldPointKey(chain_ref[0], chain_ref[1], chain_ref[2], i), uv.copy())
            for i, uv in enumerate(uv_points)
        ),
    )

    runtime_policy.register_chain(
        chain_ref,
        chain,
        chain_placement,
        uv_points,
        runtime_policy.dependency_patches_from_anchors(
            chain_ref[0],
            candidate.start_anchor,
            candidate.end_anchor,
        ),
        placed_role=eff_role,
    )

    anchor_label = _cf_anchor_debug_label(candidate.start_anchor, candidate.end_anchor)
    reason_suffix = f" note:{candidate.anchor_reason}" if candidate.anchor_reason else ''
    bridge_tag = ' [BRIDGE]' if eff_role == FrameRole.FREE and len(chain.vert_cos) <= 2 else ''
    hv_suffix = f" hv_adj:{candidate.hv_adjacency}" if eff_role in {FrameRole.H_FRAME, FrameRole.V_FRAME} else ''
    rank_suffix = f" rank:{frontier_rank_debug_label(candidate.rank)}" if candidate.rank is not None else ''
    seam_suffix = f" seam:{candidate.seam_bonus:+.2f}" if abs(candidate.seam_bonus) > 1e-6 else ''
    corner_suffix = f" corner:+{candidate.corner_bonus:.2f}" if candidate.corner_bonus > 0.0 else ''
    shape_suffix = f" shape:{candidate.shape_bonus:+.2f}" if abs(candidate.shape_bonus) > 1e-6 else ''
    ctx_suffix = ''
    if candidate.patch_context is not None:
        ctx_suffix = (
            f" ctx:p{candidate.patch_context.placed_chain_count}"
            f" pr:{candidate.patch_context.placed_ratio:.2f}"
            f" bb:{candidate.patch_context.same_patch_backbone_strength:.2f}"
            f" cp:{candidate.patch_context.closure_pressure:.2f}"
        )
    trace_console(
        f"[CFTUV][Frontier] Step {iteration}: "
        f"P{chain_ref[0]} L{chain_ref[1]}C{chain_ref[2]} "
        f"{eff_role.value} score:{candidate.score:.2f}{rank_suffix}{ctx_suffix}{seam_suffix}{corner_suffix}{shape_suffix} "
        f"ep:{anchor_count} a:{anchor_label}{reason_suffix}{bridge_tag}{hv_suffix}"
    )
    if collector is not None:
        collector.record_placement(
            iteration=iteration,
            chain_ref=chain_ref,
            chain=chain,
            effective_role=eff_role,
            placement_path="main",
            score=candidate.score,
            start_anchor=candidate.start_anchor,
            end_anchor=candidate.end_anchor,
            placed_in_patch_before=placed_before,
            is_closure_pair=(chain_ref in runtime_policy.closure_pair_refs),
            uv_points=uv_points,
            closure_preconstraint_applied=(candidate.closure_dir_override is not None),
            anchor_adjustment_applied=bool(candidate.anchor_adjustments),
            direction_inherited=direction_inherited,
            length_factor=candidate.length_factor,
            downstream_count=candidate.downstream_count,
            downstream_bonus=candidate.downstream_bonus,
            isolation_preview=candidate.isolation_preview,
            isolation_penalty=candidate.isolation_penalty,
            structural_free_bonus=candidate.structural_free_bonus,
            hv_adjacency=candidate.hv_adjacency,
            rank=candidate.rank,
            rank_breakdown=candidate.rank_breakdown,
            patch_context=candidate.patch_context,
            corner_hints=candidate.corner_hints,
            seam_relation=candidate.seam_relation,
            seam_bonus=candidate.seam_bonus,
            corner_bonus=candidate.corner_bonus,
            shape_bonus=candidate.shape_bonus,
        )
    return True
