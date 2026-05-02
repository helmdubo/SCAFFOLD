from __future__ import annotations

from typing import Any, Callable, Optional

try:
    from .console_debug import trace_console
    from .frontier_place import (
        _cf_anchor_count,
        _cf_anchor_debug_label,
        _cf_chain_total_length,
        _cf_place_chain,
        _cf_rebuild_chain_points_for_endpoints,
        _try_inherit_direction,
    )
    from .model import (
        BoundaryChain,
        ChainNeighborKind,
        ChainRef,
        FrameRole,
        PatchGraph,
        PlacementSourceKind,
        ScaffoldChainPlacement,
        ScaffoldPointKey,
        SpanAuthorityKind,
    )
    from .solve_diagnostics import _build_chain_vert_uv_map
    from .solve_instrumentation import FrontierTelemetryCollector
    from .solve_records import (
        CHAIN_FRONTIER_THRESHOLD,
        ChainAnchor,
        ChainPoolEntry,
        ClosureFollowCandidateRank,
        ClosureFollowPlacementCandidate,
        ClosureFollowUvBuildResult,
        FrontierCandidateEval,
        FrontierRescueGap,
        PointRegistry,
        TreeIngressCandidateRank,
        TreeIngressPlacementCandidate,
        _point_registry_key,
    )
except ImportError:
    from console_debug import trace_console
    from frontier_place import (
        _cf_anchor_count,
        _cf_anchor_debug_label,
        _cf_chain_total_length,
        _cf_place_chain,
        _cf_rebuild_chain_points_for_endpoints,
        _try_inherit_direction,
    )
    from model import (
        BoundaryChain,
        ChainNeighborKind,
        ChainRef,
        FrameRole,
        PatchGraph,
        PlacementSourceKind,
        ScaffoldChainPlacement,
        ScaffoldPointKey,
        SpanAuthorityKind,
    )
    from solve_diagnostics import _build_chain_vert_uv_map
    from solve_instrumentation import FrontierTelemetryCollector
    from solve_records import (
        CHAIN_FRONTIER_THRESHOLD,
        ChainAnchor,
        ChainPoolEntry,
        ClosureFollowCandidateRank,
        ClosureFollowPlacementCandidate,
        ClosureFollowUvBuildResult,
        FrontierCandidateEval,
        FrontierRescueGap,
        PointRegistry,
        TreeIngressCandidateRank,
        TreeIngressPlacementCandidate,
        _point_registry_key,
    )


def _cf_build_closure_follow_uvs(
    graph: PatchGraph,
    chain_ref: Optional[ChainRef],
    chain: BoundaryChain,
    partner_placement: ScaffoldChainPlacement,
    final_scale: float,
    effective_role: Optional[FrameRole] = None,
    runtime_policy=None,
) -> ClosureFollowUvBuildResult:
    """Строит UV для closure-пары напрямую от уже placed partner chain."""
    partner_uv_by_vert = _build_chain_vert_uv_map(graph, partner_placement)
    if not partner_uv_by_vert:
        return ClosureFollowUvBuildResult(uv_points=None)

    shared_vert_count = len(set(chain.vert_indices) & set(partner_uv_by_vert.keys()))
    if shared_vert_count <= 0:
        return ClosureFollowUvBuildResult(uv_points=None)

    if len(chain.vert_indices) == len(chain.vert_cos):
        shared_uv_points = []
        all_shared = True
        for vert_index in chain.vert_indices:
            uv = partner_uv_by_vert.get(vert_index)
            if uv is None:
                all_shared = False
                break
            shared_uv_points.append(uv.copy())
        if all_shared and len(shared_uv_points) == len(chain.vert_cos):
            return ClosureFollowUvBuildResult(
                uv_points=shared_uv_points,
                follow_mode='shared_verts',
                shared_vert_count=shared_vert_count,
            )

    start_uv = partner_uv_by_vert.get(chain.start_vert_index)
    end_uv = partner_uv_by_vert.get(chain.end_vert_index)
    if start_uv is None or end_uv is None:
        return ClosureFollowUvBuildResult(uv_points=None, shared_vert_count=shared_vert_count)

    station_map = None
    if runtime_policy is not None and chain_ref is not None:
        station_authority_kind = runtime_policy.resolve_station_authority_kind(
            chain_ref,
            chain,
            effective_role=effective_role,
        )
        station_map = runtime_policy.resolve_shared_station_map(
            chain_ref,
            chain,
            effective_role=effective_role,
            station_authority_kind=station_authority_kind,
        )
    rebuilt_uvs = _cf_rebuild_chain_points_for_endpoints(
        chain,
        start_uv,
        end_uv,
        final_scale,
        effective_role=effective_role,
        station_map=station_map,
    )
    if rebuilt_uvs is None or len(rebuilt_uvs) != len(chain.vert_cos):
        return ClosureFollowUvBuildResult(uv_points=None, shared_vert_count=shared_vert_count)
    return ClosureFollowUvBuildResult(
        uv_points=rebuilt_uvs,
        follow_mode='partner_endpoints',
        shared_vert_count=shared_vert_count,
    )


def _cf_rescue_gap_candidate_class(
    rescue_path: str,
    chain: BoundaryChain,
    main_eval: FrontierCandidateEval,
    *,
    effective_role: Optional[FrameRole] = None,
    shared_vert_count: int = 0,
) -> str:
    anchor_class = {
        0: 'no_anchor',
        1: 'single_anchor',
        2: 'dual_anchor',
    }.get(main_eval.known, f'known{main_eval.known}')
    if rescue_path == 'tree_ingress':
        role = effective_role if effective_role is not None else chain.frame_role
        role_class = 'hv' if role in {FrameRole.H_FRAME, FrameRole.V_FRAME} else 'free'
        patch_phase = (
            'untouched'
            if main_eval.patch_context is not None and main_eval.patch_context.is_untouched
            else 'patch_progress'
        )
        return f"tree_ingress_{anchor_class}_{role_class}_{patch_phase}"
    if rescue_path == 'closure_follow':
        shared_class = 'shared2' if shared_vert_count >= 2 else 'shared1'
        return f"closure_follow_{anchor_class}_{shared_class}"
    return f"{rescue_path}_{anchor_class}"


def _cf_build_frontier_rescue_gap(
    rescue_path: str,
    chain_ref: ChainRef,
    chain: BoundaryChain,
    main_eval: FrontierCandidateEval,
    *,
    effective_role: Optional[FrameRole] = None,
    hv_adjacency: int = 0,
    downstream_support: int = 0,
    shared_vert_count: int = 0,
) -> FrontierRescueGap:
    main_viable = bool(
        main_eval.known > 0
        and main_eval.score >= CHAIN_FRONTIER_THRESHOLD
    )
    if main_eval.known <= 0:
        threshold_gap = CHAIN_FRONTIER_THRESHOLD
        state_label = 'no_main_anchor'
    elif main_viable:
        threshold_gap = 0.0
        state_label = 'main_viable'
    else:
        threshold_gap = max(0.0, CHAIN_FRONTIER_THRESHOLD - main_eval.score)
        state_label = 'below_threshold'

    candidate_class = _cf_rescue_gap_candidate_class(
        rescue_path,
        chain,
        main_eval,
        effective_role=effective_role,
        shared_vert_count=shared_vert_count,
    )
    summary_parts = [candidate_class, state_label]
    if main_eval.rank_breakdown is not None and main_eval.rank_breakdown.summary:
        summary_parts.append(main_eval.rank_breakdown.summary)
    elif main_eval.anchor_reason:
        summary_parts.append(main_eval.anchor_reason)
    if hv_adjacency > 0:
        summary_parts.append(f"hv:{hv_adjacency}")
    if downstream_support > 0:
        summary_parts.append(f"ds:{downstream_support}")
    if shared_vert_count > 0:
        summary_parts.append(f"sh:{shared_vert_count}")

    return FrontierRescueGap(
        candidate_class=candidate_class,
        main_known=main_eval.known,
        main_score=main_eval.score,
        threshold_gap=threshold_gap,
        main_viable=main_viable,
        hv_adjacency=hv_adjacency,
        downstream_support=downstream_support,
        shared_vert_count=shared_vert_count,
        main_rank=main_eval.rank,
        main_rank_breakdown=main_eval.rank_breakdown,
        summary='|'.join(summary_parts),
    )


def _cf_try_place_closure_follow_candidate(
    runtime_policy: Any,
    all_chain_pool: list[ChainPoolEntry],
    closure_pair_map: dict[ChainRef, ChainRef],
    iteration: int,
    *,
    evaluate_candidate: Callable[..., FrontierCandidateEval],
    collector: Optional[FrontierTelemetryCollector] = None,
) -> bool:
    """Когда frontier встал, пробует дозавести same-role closure partner от уже placed пары."""
    graph = runtime_policy.graph
    best_candidate: Optional[ClosureFollowPlacementCandidate] = None

    for entry in all_chain_pool:
        chain_ref = entry.chain_ref
        chain = entry.chain
        if chain_ref in runtime_policy.placed_chain_refs or chain_ref in runtime_policy.rejected_chain_refs:
            continue
        node = graph.nodes.get(chain_ref[0])
        candidate_eval = (
            evaluate_candidate(
                runtime_policy,
                chain_ref,
                chain,
                node,
                apply_closure_preconstraint=True,
                compute_score=False,
            )
            if node is not None else
            FrontierCandidateEval(
                raw_start_anchor=None,
                raw_end_anchor=None,
                start_anchor=None,
                end_anchor=None,
                known=0,
                placed_in_patch=runtime_policy.placed_in_patch(chain_ref[0]),
            )
        )
        eff_role = candidate_eval.effective_role
        if eff_role not in {FrameRole.H_FRAME, FrameRole.V_FRAME}:
            continue

        partner_ref = closure_pair_map.get(chain_ref)
        if partner_ref is None:
            continue
        partner_placement = runtime_policy.placed_chains_map.get(partner_ref)
        if partner_placement is None or len(partner_placement.points) < 2:
            continue
        if partner_placement.frame_role != eff_role:
            continue

        follow_result = _cf_build_closure_follow_uvs(
            graph,
            chain_ref,
            chain,
            partner_placement,
            runtime_policy.final_scale,
            effective_role=eff_role,
            runtime_policy=runtime_policy,
        )
        uv_points = follow_result.uv_points
        follow_mode = follow_result.follow_mode
        shared_vert_count = follow_result.shared_vert_count
        if not uv_points or len(uv_points) != len(chain.vert_cos):
            continue

        candidate_rank = ClosureFollowCandidateRank(
            anchor_count=partner_placement.anchor_count,
            shared_vert_count=shared_vert_count,
            length_bias=-_cf_chain_total_length(chain, runtime_policy.final_scale),
        )
        if best_candidate is None or candidate_rank > best_candidate.rank:
            best_candidate = ClosureFollowPlacementCandidate(
                rank=candidate_rank,
                chain_ref=chain_ref,
                chain=chain,
                partner_ref=partner_ref,
                effective_role=eff_role,
                uv_points=uv_points,
                follow_mode=follow_mode,
                shared_vert_count=shared_vert_count,
            )

    if best_candidate is None:
        return False

    chain_ref = best_candidate.chain_ref
    chain = best_candidate.chain
    partner_ref = best_candidate.partner_ref
    candidate_eff_role = best_candidate.effective_role
    uv_points = best_candidate.uv_points
    follow_mode = best_candidate.follow_mode
    shared_vert_count = best_candidate.shared_vert_count
    node = graph.nodes.get(chain_ref[0])
    main_eval = (
        evaluate_candidate(
            runtime_policy,
            chain_ref,
            chain,
            node,
            apply_closure_preconstraint=True,
            compute_score=True,
        )
        if node is not None else
        FrontierCandidateEval(
            raw_start_anchor=None,
            raw_end_anchor=None,
            start_anchor=None,
            end_anchor=None,
            known=0,
            placed_in_patch=runtime_policy.placed_in_patch(chain_ref[0]),
        )
    )
    rescue_gap = _cf_build_frontier_rescue_gap(
        "closure_follow",
        chain_ref,
        chain,
        main_eval,
        effective_role=main_eval.effective_role,
        shared_vert_count=shared_vert_count,
    )
    eff_role = main_eval.effective_role
    if eff_role != candidate_eff_role or eff_role not in {FrameRole.H_FRAME, FrameRole.V_FRAME}:
        return False
    axis_authority_kind = runtime_policy.resolve_axis_authority_kind(
        chain_ref,
        chain,
        main_eval.start_anchor,
        main_eval.end_anchor,
        effective_role=eff_role,
    )
    span_authority_kind = runtime_policy.resolve_span_authority_kind(
        chain_ref,
        chain,
        main_eval.start_anchor,
        main_eval.end_anchor,
        effective_role=eff_role,
    )
    station_authority_kind = runtime_policy.resolve_station_authority_kind(
        chain_ref,
        chain,
        main_eval.start_anchor,
        main_eval.end_anchor,
        effective_role=eff_role,
    )
    parameter_authority_kind = runtime_policy.resolve_parameter_authority_kind(
        chain_ref,
        chain,
        main_eval.start_anchor,
        main_eval.end_anchor,
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
        anchor_count=2,
        primary_anchor_kind=PlacementSourceKind.SAME_PATCH,
        points=tuple(
            (ScaffoldPointKey(chain_ref[0], chain_ref[1], chain_ref[2], point_index), uv.copy())
            for point_index, uv in enumerate(uv_points)
        ),
    )

    runtime_policy.register_chain(
        chain_ref,
        chain,
        chain_placement,
        uv_points,
        tuple(
            sorted(
                patch_id
                for patch_id in (partner_ref[0],)
                if patch_id != chain_ref[0]
            )
        ),
        placed_role=eff_role,
    )

    trace_console(
        f"[CFTUV][Frontier] Step {iteration}: "
        f"P{chain_ref[0]} L{chain_ref[1]}C{chain_ref[2]} "
        f"{eff_role.value} score:closure_follow ep:2 "
        f"a:CP{partner_ref[0]}/CP{partner_ref[0]} "
        f"note:{follow_mode}:shared={shared_vert_count}"
    )
    if collector is not None:
        collector.record_placement(
            iteration=iteration,
            chain_ref=chain_ref,
            chain=chain,
            effective_role=eff_role,
            placement_path="closure_follow",
            score=-1.0,
            start_anchor=None,
            end_anchor=None,
            placed_in_patch_before=runtime_policy.placed_in_patch(chain_ref[0]) - 1,
            is_closure_pair=(chain_ref in runtime_policy.closure_pair_refs),
            uv_points=uv_points,
            length_factor=main_eval.length_factor,
            downstream_count=main_eval.downstream_count,
            downstream_bonus=main_eval.downstream_bonus,
            isolation_preview=main_eval.isolation_preview,
            isolation_penalty=main_eval.isolation_penalty,
            structural_free_bonus=main_eval.structural_free_bonus,
            hv_adjacency=main_eval.hv_adjacency,
            rank=main_eval.rank,
            rank_breakdown=main_eval.rank_breakdown,
            patch_context=main_eval.patch_context,
            corner_hints=main_eval.corner_hints,
            seam_relation=main_eval.seam_relation,
            seam_bonus=main_eval.seam_bonus,
            corner_bonus=main_eval.corner_bonus,
            shape_bonus=main_eval.shape_bonus,
            rescue_gap=rescue_gap,
        )
    return True


def _cf_build_partner_chain_anchor(
    vert_index: int,
    partner_ref: ChainRef,
    partner_chain: Optional[BoundaryChain],
    point_registry: PointRegistry,
) -> Optional[ChainAnchor]:
    if partner_chain is None or vert_index < 0:
        return None
    for point_index, partner_vert_index in enumerate(partner_chain.vert_indices):
        if partner_vert_index != vert_index:
            continue
        key = _point_registry_key(partner_ref, point_index)
        if key not in point_registry:
            continue
        return ChainAnchor(
            uv=point_registry[key].copy(),
            source_ref=partner_ref,
            source_point_index=point_index,
            source_kind=PlacementSourceKind.CROSS_PATCH,
        )
    return None


def _cf_try_place_tree_ingress_candidate(
    runtime_policy: Any,
    all_chain_pool: list[ChainPoolEntry],
    iteration: int,
    *,
    evaluate_candidate: Callable[..., FrontierCandidateEval],
    is_allowed_quilt_edge: Callable[[set[tuple[int, int]], int, int], bool],
    frame_anchor_pair_is_axis_safe: Callable[..., Any],
    apply_anchor_adjustments: Callable[..., bool],
    collector: Optional[FrontierTelemetryCollector] = None,
) -> bool:
    """Контролируемый bootstrap в untouched tree-child patch, если обычный frontier уже встал."""
    best_candidate: Optional[TreeIngressPlacementCandidate] = None

    graph = runtime_policy.graph
    for entry in all_chain_pool:
        chain_ref = entry.chain_ref
        chain = entry.chain
        node = entry.node
        if chain_ref in runtime_policy.placed_chain_refs or chain_ref in runtime_policy.rejected_chain_refs:
            continue

        candidate_eval = evaluate_candidate(runtime_policy, chain_ref, chain, node)
        eff_role = candidate_eval.effective_role
        if candidate_eval.placed_in_patch > 0:
            continue
        if chain.neighbor_kind != ChainNeighborKind.PATCH:
            continue
        if chain.neighbor_patch_id not in runtime_policy.quilt_patch_ids:
            continue
        if not is_allowed_quilt_edge(runtime_policy.allowed_tree_edges, chain_ref[0], chain.neighbor_patch_id):
            continue

        using_primary_pair = False
        ingress_anchor_adjustments = tuple(candidate_eval.anchor_adjustments)
        ingress_start_anchor = None
        ingress_end_anchor = None
        partner_ref = runtime_policy.tree_ingress_partner_by_chain.get(chain_ref)
        if partner_ref in runtime_policy.placed_chain_refs:
            partner_chain = graph.get_chain(*partner_ref)
            pair_start_anchor = _cf_build_partner_chain_anchor(
                chain.start_vert_index,
                partner_ref,
                partner_chain,
                runtime_policy.point_registry,
            )
            pair_end_anchor = _cf_build_partner_chain_anchor(
                chain.end_vert_index,
                partner_ref,
                partner_chain,
                runtime_policy.point_registry,
            )
            pair_anchor_count = _cf_anchor_count(pair_start_anchor, pair_end_anchor)
            if pair_anchor_count == 1 or (
                pair_anchor_count == 2
                and frame_anchor_pair_is_axis_safe(
                    chain,
                    pair_start_anchor,
                    pair_end_anchor,
                    runtime_policy.final_scale,
                    effective_role=eff_role,
                ).is_safe
            ):
                using_primary_pair = True
                ingress_start_anchor = pair_start_anchor
                ingress_end_anchor = pair_end_anchor
                ingress_anchor_adjustments = ()

        if not using_primary_pair:
            ingress_start_anchor = candidate_eval.start_anchor
            ingress_end_anchor = candidate_eval.end_anchor
            if candidate_eval.known == 1:
                resolved_anchor = (
                    ingress_start_anchor
                    if ingress_start_anchor is not None else
                    ingress_end_anchor
                )
                if resolved_anchor is None or resolved_anchor.source_kind != PlacementSourceKind.CROSS_PATCH:
                    continue
            else:
                if chain.neighbor_kind != ChainNeighborKind.PATCH or chain.neighbor_patch_id < 0:
                    continue
                raw_start_anchor = candidate_eval.raw_start_anchor
                raw_end_anchor = candidate_eval.raw_end_anchor
                if raw_start_anchor is None or raw_end_anchor is None:
                    continue
                if (
                    raw_start_anchor.source_kind != PlacementSourceKind.CROSS_PATCH
                    or raw_end_anchor.source_kind != PlacementSourceKind.CROSS_PATCH
                ):
                    continue
                if (
                    raw_start_anchor.source_ref[0] != chain.neighbor_patch_id
                    or raw_end_anchor.source_ref[0] != chain.neighbor_patch_id
                ):
                    continue
                if not frame_anchor_pair_is_axis_safe(
                    chain,
                    raw_start_anchor,
                    raw_end_anchor,
                    runtime_policy.final_scale,
                    effective_role=eff_role,
                ).is_safe:
                    continue
                ingress_start_anchor = raw_start_anchor
                ingress_end_anchor = raw_end_anchor

        anchor_count = _cf_anchor_count(ingress_start_anchor, ingress_end_anchor)
        if anchor_count <= 0:
            continue

        if eff_role not in {FrameRole.H_FRAME, FrameRole.V_FRAME}:
            continue
        if not using_primary_pair and candidate_eval.hv_adjacency <= 0:
            continue

        role_priority = 6 if using_primary_pair else (5 if anchor_count >= 2 else (4 if candidate_eval.hv_adjacency >= 2 else 3))
        if chain.is_corner_split:
            role_priority -= 1

        endpoint_neighbors = graph.get_chain_endpoint_neighbors(chain_ref[0], chain_ref[1], chain_ref[2])
        downstream_sides: list[str] = []
        if ingress_start_anchor is None:
            downstream_sides.append('start')
        if ingress_end_anchor is None:
            downstream_sides.append('end')
        if not downstream_sides:
            downstream_sides.extend(('start', 'end'))
        downstream_hv_count = 0
        downstream_max_length = 0.0
        seen_downstream_refs: set[ChainRef] = set()
        for downstream_side in downstream_sides:
            for neighbor_loop_index, neighbor_chain_index in endpoint_neighbors.get(downstream_side, []):
                neighbor_ref = (chain_ref[0], neighbor_loop_index, neighbor_chain_index)
                if neighbor_ref in seen_downstream_refs:
                    continue
                seen_downstream_refs.add(neighbor_ref)
                if neighbor_ref in runtime_policy.placed_chain_refs or neighbor_ref in runtime_policy.rejected_chain_refs:
                    continue
                neighbor_chain = graph.get_chain(*neighbor_ref)
                if neighbor_chain is None:
                    continue
                neighbor_role = runtime_policy.effective_placement_role(neighbor_ref, neighbor_chain)
                if neighbor_role not in {FrameRole.H_FRAME, FrameRole.V_FRAME}:
                    continue
                downstream_hv_count += 1
                downstream_max_length = max(
                    downstream_max_length,
                    _cf_chain_total_length(neighbor_chain, runtime_policy.final_scale),
                )

        direction_override = _try_inherit_direction(
            chain,
            node,
            ingress_start_anchor,
            ingress_end_anchor,
            graph,
            runtime_policy.point_registry,
            chain_ref=chain_ref,
            effective_role=eff_role,
            placed_chains_map=runtime_policy.placed_chains_map,
        )
        uv_points = _cf_place_chain(
            chain,
            node,
            ingress_start_anchor,
            ingress_end_anchor,
            runtime_policy.final_scale,
            direction_override,
            placed_chains_map=runtime_policy.placed_chains_map,
            graph=runtime_policy.graph,
            effective_role=eff_role,
            chain_ref=chain_ref,
            runtime_policy=runtime_policy,
        )
        if not uv_points or len(uv_points) != len(chain.vert_cos):
            continue

        candidate_rank = TreeIngressCandidateRank(
            role_priority=role_priority,
            downstream_hv_count=downstream_hv_count,
            downstream_max_length=downstream_max_length,
            chain_length=_cf_chain_total_length(chain, runtime_policy.final_scale),
        )
        if best_candidate is None or candidate_rank > best_candidate.rank:
            best_candidate = TreeIngressPlacementCandidate(
                rank=candidate_rank,
                chain_ref=chain_ref,
                chain=chain,
                effective_role=eff_role,
                start_anchor=ingress_start_anchor,
                end_anchor=ingress_end_anchor,
                anchor_adjustments=ingress_anchor_adjustments,
                uv_points=uv_points,
                downstream_hv_count=downstream_hv_count,
                role_priority=role_priority,
                hv_adjacency=candidate_eval.hv_adjacency,
            )

    if best_candidate is None:
        return False

    chain_ref = best_candidate.chain_ref
    chain = best_candidate.chain
    candidate_eff_role = best_candidate.effective_role
    anchor_start = best_candidate.start_anchor
    anchor_end = best_candidate.end_anchor
    anchor_adjustments = best_candidate.anchor_adjustments
    uv_points = best_candidate.uv_points
    downstream_hv_count = best_candidate.downstream_hv_count
    role_priority = best_candidate.role_priority
    hv_adjacency = best_candidate.hv_adjacency
    node = runtime_policy.graph.nodes.get(chain_ref[0])
    main_eval = (
        evaluate_candidate(
            runtime_policy,
            chain_ref,
            chain,
            node,
            apply_closure_preconstraint=True,
            compute_score=True,
        )
        if node is not None else
        FrontierCandidateEval(
            raw_start_anchor=None,
            raw_end_anchor=None,
            start_anchor=None,
            end_anchor=None,
            known=0,
            placed_in_patch=runtime_policy.placed_in_patch(chain_ref[0]),
        )
    )
    rescue_gap = _cf_build_frontier_rescue_gap(
        "tree_ingress",
        chain_ref,
        chain,
        main_eval,
        effective_role=main_eval.effective_role,
        hv_adjacency=hv_adjacency,
        downstream_support=downstream_hv_count,
    )

    if anchor_adjustments and not apply_anchor_adjustments(
        anchor_adjustments,
        graph,
        runtime_policy.placed_chains_map,
        runtime_policy.point_registry,
        runtime_policy.final_scale,
    ):
        runtime_policy.reject_chain(chain_ref)
        return False

    if anchor_start is not None:
        _rescue_primary_anchor_kind = anchor_start.source_kind
    elif anchor_end is not None:
        _rescue_primary_anchor_kind = anchor_end.source_kind
    else:
        _rescue_primary_anchor_kind = PlacementSourceKind.CHAIN
    ingress_eff_role = candidate_eff_role
    axis_authority_kind = runtime_policy.resolve_axis_authority_kind(
        chain_ref,
        chain,
        anchor_start,
        anchor_end,
        effective_role=ingress_eff_role,
    )
    span_authority_kind = runtime_policy.resolve_span_authority_kind(
        chain_ref,
        chain,
        anchor_start,
        anchor_end,
        effective_role=ingress_eff_role,
    )
    station_authority_kind = runtime_policy.resolve_station_authority_kind(
        chain_ref,
        chain,
        anchor_start,
        anchor_end,
        effective_role=ingress_eff_role,
    )
    parameter_authority_kind = runtime_policy.resolve_parameter_authority_kind(
        chain_ref,
        chain,
        anchor_start,
        anchor_end,
        effective_role=ingress_eff_role,
    )
    chain_placement = ScaffoldChainPlacement(
        patch_id=chain_ref[0],
        loop_index=chain_ref[1],
        chain_index=chain_ref[2],
        frame_role=ingress_eff_role,
        axis_authority_kind=axis_authority_kind,
        span_authority_kind=span_authority_kind,
        station_authority_kind=station_authority_kind,
        parameter_authority_kind=parameter_authority_kind,
        source_kind=PlacementSourceKind.CHAIN,
        anchor_count=_cf_anchor_count(anchor_start, anchor_end),
        primary_anchor_kind=_rescue_primary_anchor_kind,
        points=tuple(
            (ScaffoldPointKey(chain_ref[0], chain_ref[1], chain_ref[2], point_index), uv.copy())
            for point_index, uv in enumerate(uv_points)
        ),
    )

    runtime_policy.register_chain(
        chain_ref,
        chain,
        chain_placement,
        uv_points,
        runtime_policy.dependency_patches_from_anchors(chain_ref[0], anchor_start, anchor_end),
        placed_role=ingress_eff_role,
    )

    anchor_count = _cf_anchor_count(anchor_start, anchor_end)
    trace_console(
        f"[CFTUV][Frontier] Step {iteration}: "
        f"P{chain_ref[0]} L{chain_ref[1]}C{chain_ref[2]} "
        f"{ingress_eff_role.value} score:tree_ingress ep:{anchor_count} "
        f"a:{_cf_anchor_debug_label(anchor_start, anchor_end)} "
        f"note:priority={role_priority}:downstream_hv={downstream_hv_count}:hv_adj={hv_adjacency}"
    )
    if collector is not None:
        collector.record_placement(
            iteration=iteration,
            chain_ref=chain_ref,
            chain=chain,
            effective_role=ingress_eff_role,
            placement_path="tree_ingress",
            score=-1.0,
            start_anchor=anchor_start,
            end_anchor=anchor_end,
            placed_in_patch_before=runtime_policy.placed_in_patch(chain_ref[0]) - 1,
            is_closure_pair=(chain_ref in runtime_policy.closure_pair_refs),
            uv_points=uv_points,
            anchor_adjustment_applied=bool(anchor_adjustments),
            length_factor=main_eval.length_factor,
            downstream_count=main_eval.downstream_count,
            downstream_bonus=main_eval.downstream_bonus,
            isolation_preview=main_eval.isolation_preview,
            isolation_penalty=main_eval.isolation_penalty,
            structural_free_bonus=main_eval.structural_free_bonus,
            hv_adjacency=hv_adjacency,
            rank=main_eval.rank,
            rank_breakdown=main_eval.rank_breakdown,
            patch_context=main_eval.patch_context,
            corner_hints=main_eval.corner_hints,
            seam_relation=main_eval.seam_relation,
            seam_bonus=main_eval.seam_bonus,
            corner_bonus=main_eval.corner_bonus,
            shape_bonus=main_eval.shape_bonus,
            rescue_gap=rescue_gap,
        )
    return True
