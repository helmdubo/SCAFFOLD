from __future__ import annotations

import time
from typing import Optional

try:
    from .analysis_records import BandSpineData
    from .console_debug import trace_console
    from .frontier_bootstrap import (
        bootstrap_frontier_runtime as _frontier_bootstrap_runtime,
        build_frontier_chain_pool as _frontier_build_chain_pool,
        index_frontier_chain_pool as _frontier_index_chain_pool,
    )
    from .frontier_closure import (
        _build_quilt_closure_pair_map,
        _build_tree_ingress_partner_map,
        _iter_quilt_closure_chain_pairs,
        _match_non_tree_closure_chain_pairs,
    )
    from .frontier_eval import (
        _cf_choose_seed_chain,
        _cf_frame_anchor_pair_is_axis_safe,
        build_stop_diagnostics as _frontier_eval_build_stop_diagnostics,
        evaluate_candidate as _frontier_eval_evaluate_candidate,
        select_best_frontier_candidate as _frontier_eval_select_best_frontier_candidate,
        try_place_frontier_candidate as _frontier_eval_try_place_frontier_candidate,
    )
    from .frontier_finalize import _finalize_quilt_scaffold_frontier
    from .frontier_place import (
        _cf_apply_anchor_adjustments,
        _cf_build_seed_placement,
        _cf_chain_total_length,
    )
    from .frontier_rescue import (
        _cf_try_place_closure_follow_candidate,
        _cf_try_place_tree_ingress_candidate,
    )
    from .frontier_score import (
        _cf_bootstrap_runtime_score_caches,
        _cf_build_corner_scoring_hints,
        _cf_build_frontier_rank,
        _cf_build_patch_scoring_context,
        _cf_chain_seam_relation,
        _cf_count_hv_adjacent_endpoints,
        _cf_frontier_rank_debug_label,
        _cf_score_candidate,
    )
    from .frontier_state import FrontierRuntimePolicy, _mark_neighbors_dirty
    from .model import (
        BoundaryChain,
        ChainRef,
        FrameRole,
        PatchEdgeKey,
        PatchGraph,
        PatchNode,
        PatchPlacementStatus,
        ScaffoldMap,
        ScaffoldPatchPlacement,
        ScaffoldQuiltPlacement,
    )
    from .solve_instrumentation import FrontierTelemetryCollector, collect_stall_snapshot
    from .solve_planning import (
        _build_quilt_tree_edges,
        _build_solve_view,
        _is_allowed_quilt_edge,
        _restore_original_quilt_plan,
    )
    from .solve_records import (
        CHAIN_FRONTIER_THRESHOLD,
        ChainPoolEntry,
        FrontierBootstrapAttempt,
        FrontierBootstrapResult,
        FrontierCandidateEval,
        FrontierPlacementCandidate,
        FrontierStopDiagnostics,
        QuiltPlan,
        SolvePlan,
        SolveView,
    )
except ImportError:
    from analysis_records import BandSpineData
    from console_debug import trace_console
    from frontier_bootstrap import (
        bootstrap_frontier_runtime as _frontier_bootstrap_runtime,
        build_frontier_chain_pool as _frontier_build_chain_pool,
        index_frontier_chain_pool as _frontier_index_chain_pool,
    )
    from frontier_closure import (
        _build_quilt_closure_pair_map,
        _build_tree_ingress_partner_map,
        _iter_quilt_closure_chain_pairs,
        _match_non_tree_closure_chain_pairs,
    )
    from frontier_eval import (
        _cf_choose_seed_chain,
        _cf_frame_anchor_pair_is_axis_safe,
        build_stop_diagnostics as _frontier_eval_build_stop_diagnostics,
        evaluate_candidate as _frontier_eval_evaluate_candidate,
        select_best_frontier_candidate as _frontier_eval_select_best_frontier_candidate,
        try_place_frontier_candidate as _frontier_eval_try_place_frontier_candidate,
    )
    from frontier_finalize import _finalize_quilt_scaffold_frontier
    from frontier_place import (
        _cf_apply_anchor_adjustments,
        _cf_build_seed_placement,
        _cf_chain_total_length,
    )
    from frontier_rescue import (
        _cf_try_place_closure_follow_candidate,
        _cf_try_place_tree_ingress_candidate,
    )
    from frontier_score import (
        _cf_bootstrap_runtime_score_caches,
        _cf_build_corner_scoring_hints,
        _cf_build_frontier_rank,
        _cf_build_patch_scoring_context,
        _cf_chain_seam_relation,
        _cf_count_hv_adjacent_endpoints,
        _cf_frontier_rank_debug_label,
        _cf_score_candidate,
    )
    from frontier_state import FrontierRuntimePolicy, _mark_neighbors_dirty
    from model import (
        BoundaryChain,
        ChainRef,
        FrameRole,
        PatchEdgeKey,
        PatchGraph,
        PatchNode,
        PatchPlacementStatus,
        ScaffoldMap,
        ScaffoldPatchPlacement,
        ScaffoldQuiltPlacement,
    )
    from solve_instrumentation import FrontierTelemetryCollector, collect_stall_snapshot
    from solve_planning import (
        _build_quilt_tree_edges,
        _build_solve_view,
        _is_allowed_quilt_edge,
        _restore_original_quilt_plan,
    )
    from solve_records import (
        CHAIN_FRONTIER_THRESHOLD,
        ChainPoolEntry,
        FrontierBootstrapAttempt,
        FrontierBootstrapResult,
        FrontierCandidateEval,
        FrontierPlacementCandidate,
        FrontierStopDiagnostics,
        QuiltPlan,
        SolvePlan,
        SolveView,
    )


def _cf_evaluate_candidate_runtime_policy(
    runtime_policy: FrontierRuntimePolicy,
    chain_ref: ChainRef,
    chain: BoundaryChain,
    node: PatchNode,
    apply_closure_preconstraint: bool = False,
    compute_score: bool = False,
) -> FrontierCandidateEval:
    return _frontier_eval_evaluate_candidate(
        runtime_policy,
        chain_ref,
        chain,
        node,
        apply_closure_preconstraint=apply_closure_preconstraint,
        compute_score=compute_score,
        is_allowed_quilt_edge=_is_allowed_quilt_edge,
        build_patch_scoring_context=_cf_build_patch_scoring_context,
        chain_seam_relation=_cf_chain_seam_relation,
        build_corner_scoring_hints=_cf_build_corner_scoring_hints,
        score_candidate=_cf_score_candidate,
        build_frontier_rank=_cf_build_frontier_rank,
    )


def _cf_build_stop_diagnostics_runtime_policy(
    runtime_policy: FrontierRuntimePolicy,
    all_chain_pool: list[ChainPoolEntry],
) -> FrontierStopDiagnostics:
    return _frontier_eval_build_stop_diagnostics(
        runtime_policy,
        all_chain_pool,
        evaluate_candidate_fn=_cf_evaluate_candidate_runtime_policy,
    )


def _cf_select_best_frontier_candidate(
    runtime_policy: FrontierRuntimePolicy,
    all_chain_pool: list[ChainPoolEntry],
) -> Optional[FrontierPlacementCandidate]:
    return _frontier_eval_select_best_frontier_candidate(
        runtime_policy,
        all_chain_pool,
        evaluate_candidate_fn=_cf_evaluate_candidate_runtime_policy,
    )


def _cf_try_place_frontier_candidate(
    runtime_policy: FrontierRuntimePolicy,
    candidate: FrontierPlacementCandidate,
    iteration: int,
    *,
    collector: Optional[FrontierTelemetryCollector] = None,
) -> bool:
    return _frontier_eval_try_place_frontier_candidate(
        runtime_policy,
        candidate,
        iteration,
        apply_anchor_adjustments_fn=_cf_apply_anchor_adjustments,
        frontier_rank_debug_label=_cf_frontier_rank_debug_label,
        collector=collector,
    )


def _cf_bootstrap_frontier_runtime(
    graph: PatchGraph,
    solve_view: SolveView,
    quilt_plan: QuiltPlan,
    root_node: PatchNode,
    quilt_patch_ids: set[int],
    allowed_tree_edges: set[PatchEdgeKey],
    closure_pair_map: dict[ChainRef, ChainRef],
    tree_ingress_partner_by_chain: dict[ChainRef, ChainRef],
    final_scale: float,
    straighten_enabled: bool = False,
    inherited_role_map: Optional[dict] = None,
    patch_structural_summaries: Optional[dict] = None,
    patch_shape_classes: Optional[dict] = None,
    straighten_chain_refs: Optional[frozenset] = None,
    band_spine_data: Optional[dict[int, BandSpineData]] = None,
) -> FrontierBootstrapAttempt:
    return _frontier_bootstrap_runtime(
        graph,
        solve_view,
        quilt_plan,
        root_node,
        quilt_patch_ids,
        allowed_tree_edges,
        closure_pair_map,
        tree_ingress_partner_by_chain,
        final_scale,
        straighten_enabled=straighten_enabled,
        inherited_role_map=inherited_role_map,
        patch_structural_summaries=patch_structural_summaries,
        patch_shape_classes=patch_shape_classes,
        straighten_chain_refs=straighten_chain_refs,
        band_spine_data=band_spine_data,
    )


def _cf_build_frontier_chain_pool(
    solve_view: SolveView,
    graph: PatchGraph,
    ordered_quilt_patch_ids: list[int],
    seed_ref: ChainRef,
) -> list[ChainPoolEntry]:
    return _frontier_build_chain_pool(
        solve_view,
        graph,
        ordered_quilt_patch_ids,
        seed_ref,
    )


def _cf_index_frontier_chain_pool(
    runtime_policy: FrontierRuntimePolicy,
    all_chain_pool: list[ChainPoolEntry],
    seed_ref: ChainRef,
    seed_chain: BoundaryChain,
) -> None:
    _frontier_index_chain_pool(
        runtime_policy,
        all_chain_pool,
        seed_ref,
        seed_chain,
    )


def _cf_record_seed_telemetry(
    collector: FrontierTelemetryCollector,
    graph: PatchGraph,
    runtime_policy: FrontierRuntimePolicy,
    seed_ref: ChainRef,
    seed_chain: BoundaryChain,
    seed_score: float,
) -> None:
    seed_placement = runtime_policy.placed_chains_map.get(seed_ref)
    if seed_placement is None:
        return
    collector.record_seed_placement(
        chain_ref=seed_ref,
        chain=seed_chain,
        effective_role=runtime_policy.effective_placement_role(seed_ref, seed_chain),
        score=seed_score,
        uv_points=[uv.copy() for _, uv in seed_placement.points],
        is_closure_pair=(seed_ref in runtime_policy.closure_pair_refs),
        hv_adjacency=_cf_count_hv_adjacent_endpoints(graph, seed_ref, runtime_policy=runtime_policy)
        if seed_placement.frame_role in {FrameRole.H_FRAME, FrameRole.V_FRAME}
        else 0,
    )


def build_quilt_scaffold_chain_frontier(
    graph: PatchGraph,
    quilt_plan: QuiltPlan,
    final_scale: float,
    straighten_enabled: bool = False,
    inherited_role_map: Optional[dict] = None,
    patch_structural_summaries: Optional[dict] = None,
    patch_shape_classes: Optional[dict] = None,
    straighten_chain_refs: Optional[frozenset] = None,
    band_spine_data: Optional[dict[int, BandSpineData]] = None,
) -> ScaffoldQuiltPlacement:
    """Build chain-first scaffold for a single quilt."""

    quilt_scaffold = ScaffoldQuiltPlacement(
        quilt_index=quilt_plan.quilt_index,
        root_patch_id=quilt_plan.root_patch_id,
    )
    quilt_patch_ids = set(quilt_plan.solved_patch_ids)
    quilt_patch_ids.add(quilt_plan.root_patch_id)
    solve_view = _build_solve_view(graph)
    allowed_tree_edges = _build_quilt_tree_edges(quilt_plan)
    closure_pair_map = _build_quilt_closure_pair_map(graph, quilt_plan, quilt_patch_ids, allowed_tree_edges)
    tree_ingress_partner_by_chain = _build_tree_ingress_partner_map(quilt_plan)
    ordered_quilt_patch_ids = list(quilt_plan.solved_patch_ids)
    if quilt_plan.root_patch_id not in ordered_quilt_patch_ids:
        ordered_quilt_patch_ids.append(quilt_plan.root_patch_id)

    root_node = graph.nodes.get(quilt_plan.root_patch_id)
    if root_node is None:
        return quilt_scaffold

    bootstrap_attempt = _cf_bootstrap_frontier_runtime(
        graph,
        solve_view,
        quilt_plan,
        root_node,
        quilt_patch_ids,
        allowed_tree_edges,
        closure_pair_map,
        tree_ingress_partner_by_chain,
        final_scale,
        straighten_enabled=straighten_enabled,
        inherited_role_map=inherited_role_map,
        patch_structural_summaries=patch_structural_summaries,
        patch_shape_classes=patch_shape_classes,
        straighten_chain_refs=straighten_chain_refs,
        band_spine_data=band_spine_data,
    )
    if bootstrap_attempt.result is None:
        quilt_scaffold.patches[quilt_plan.root_patch_id] = ScaffoldPatchPlacement(
            patch_id=quilt_plan.root_patch_id,
            loop_index=-1,
            root_chain_index=-1,
            notes=(bootstrap_attempt.error or "frontier_bootstrap_failed",),
            status=PatchPlacementStatus.UNSUPPORTED,
        )
        return quilt_scaffold

    bootstrap_result = bootstrap_attempt.result
    runtime_policy = bootstrap_result.runtime_policy
    seed_ref = bootstrap_result.seed_ref
    seed_chain = bootstrap_result.seed_chain
    all_chain_pool = _cf_build_frontier_chain_pool(
        solve_view,
        graph,
        ordered_quilt_patch_ids,
        seed_ref,
    )
    _cf_index_frontier_chain_pool(runtime_policy, all_chain_pool, seed_ref, seed_chain)

    collector = FrontierTelemetryCollector(quilt_index=quilt_plan.quilt_index)
    _cf_record_seed_telemetry(
        collector,
        graph,
        runtime_policy,
        seed_ref,
        seed_chain,
        bootstrap_result.seed_score,
    )

    max_iter = len(all_chain_pool) + 10
    iteration = 0
    t0 = time.perf_counter()
    for iteration in range(1, max_iter + 1):
        best_candidate = _cf_select_best_frontier_candidate(runtime_policy, all_chain_pool)

        if best_candidate is None or best_candidate.score < CHAIN_FRONTIER_THRESHOLD:
            stall_snapshot = collect_stall_snapshot(
                cached_evals=runtime_policy._cached_evals,
                placed_chain_refs=runtime_policy.placed_chain_refs,
                rejected_chain_refs=runtime_policy.rejected_chain_refs,
                placed_count_by_patch=runtime_policy.placed_count_by_patch,
                quilt_patch_ids=runtime_policy.quilt_patch_ids,
                all_chain_pool=all_chain_pool,
            )
            collector.record_stall(
                iteration=iteration,
                best_rejected_score=stall_snapshot[0],
                best_rejected_ref=stall_snapshot[1],
                best_rejected_role=stall_snapshot[2],
                best_rejected_anchor_count=stall_snapshot[3],
                available_count=stall_snapshot[4],
                no_anchor_count=stall_snapshot[5],
                below_threshold_count=stall_snapshot[6],
                patches_with_placed=stall_snapshot[7],
                patches_untouched=stall_snapshot[8],
            )

            if _cf_try_place_tree_ingress_candidate(
                runtime_policy,
                all_chain_pool,
                iteration,
                evaluate_candidate=_cf_evaluate_candidate_runtime_policy,
                is_allowed_quilt_edge=_is_allowed_quilt_edge,
                frame_anchor_pair_is_axis_safe=_cf_frame_anchor_pair_is_axis_safe,
                apply_anchor_adjustments=_cf_apply_anchor_adjustments,
                collector=collector,
            ):
                collector.update_last_stall_rescue("tree_ingress", True)
                continue
            if _cf_try_place_closure_follow_candidate(
                runtime_policy,
                all_chain_pool,
                closure_pair_map,
                iteration,
                evaluate_candidate=_cf_evaluate_candidate_runtime_policy,
                collector=collector,
            ):
                collector.update_last_stall_rescue("closure_follow", True)
                continue

            collector.update_last_stall_rescue("none", False)
            stop_diag = _cf_build_stop_diagnostics_runtime_policy(runtime_policy, all_chain_pool)
            trace_console(
                f"[CFTUV][Frontier] STOP: remaining={stop_diag.remaining_count} "
                f"no_anchor={stop_diag.no_anchor_count} low_score={stop_diag.low_score_count} "
                f"rejected={stop_diag.rejected_count}"
            )
            trace_console(
                f"[CFTUV][Frontier] Patches: placed_in={len(stop_diag.placed_patch_ids)} "
                f"untouched={len(stop_diag.untouched_patch_ids)} "
                f"no_anchor_patches={len(stop_diag.no_anchor_patch_ids)}"
            )
            if stop_diag.untouched_patch_ids and len(stop_diag.untouched_patch_ids) <= 20:
                trace_console(f"[CFTUV][Frontier] Untouched patches: {list(stop_diag.untouched_patch_ids)}")
            break

        if not _cf_try_place_frontier_candidate(
            runtime_policy,
            best_candidate,
            iteration,
            collector=collector,
        ):
            continue

    t1 = time.perf_counter()
    trace_console(
        f"[CFTUV][Frontier] Quilt {quilt_plan.quilt_index}: "
        f"frontier {t1 - t0:.4f}s "
        f"iters={iteration} placed={runtime_policy.total_placed()}/{len(all_chain_pool) + 1} "
        f"cache_hits={runtime_policy._cache_hits}"
    )

    total_available = len(all_chain_pool) + 1
    finalized_scaffold = _finalize_quilt_scaffold_frontier(
        graph,
        solve_view,
        quilt_plan,
        quilt_scaffold,
        runtime_policy,
        final_scale,
        allowed_tree_edges,
        seed_ref,
        total_available,
    )
    quilt_scaffold = finalized_scaffold.quilt_scaffold
    quilt_scaffold.frontier_telemetry = collector.finalize()
    untouched_patch_ids = finalized_scaffold.untouched_patch_ids
    if untouched_patch_ids:
        fallback_quilt_plan = _restore_original_quilt_plan(quilt_plan)
        if fallback_quilt_plan is not None:
            trace_console(
                f"[CFTUV][Plan] Quilt {quilt_plan.quilt_index}: "
                f"revert closure cut swap, untouched patches={sorted(untouched_patch_ids)}"
            )
            return build_quilt_scaffold_chain_frontier(
                graph,
                fallback_quilt_plan,
                final_scale,
                straighten_enabled=straighten_enabled,
                inherited_role_map=inherited_role_map,
                patch_structural_summaries=patch_structural_summaries,
                patch_shape_classes=patch_shape_classes,
                straighten_chain_refs=straighten_chain_refs,
                band_spine_data=band_spine_data,
            )

    return quilt_scaffold


def build_root_scaffold_map(
    graph: PatchGraph,
    solve_plan: Optional[SolvePlan] = None,
    final_scale: float = 1.0,
    straighten_enabled: bool = False,
    inherited_role_map: Optional[dict] = None,
    patch_structural_summaries: Optional[dict] = None,
    patch_shape_classes: Optional[dict] = None,
    straighten_chain_refs: Optional[frozenset] = None,
    band_spine_data: Optional[dict[int, BandSpineData]] = None,
) -> ScaffoldMap:
    """Build ScaffoldMap using chain-first strongest-frontier algorithm."""

    scaffold_map = ScaffoldMap()
    if solve_plan is None:
        return scaffold_map

    for quilt in solve_plan.quilts:
        quilt_scaffold = build_quilt_scaffold_chain_frontier(
            graph, quilt, final_scale,
            straighten_enabled=straighten_enabled,
            inherited_role_map=inherited_role_map,
            patch_structural_summaries=patch_structural_summaries,
            patch_shape_classes=patch_shape_classes,
            straighten_chain_refs=straighten_chain_refs,
            band_spine_data=band_spine_data,
        )
        scaffold_map.quilts.append(quilt_scaffold)

    return scaffold_map
