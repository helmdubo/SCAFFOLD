from __future__ import annotations

from typing import Optional

from .console_debug import trace_console
from .frontier_place import _cf_build_seed_placement, _cf_chain_total_length
from .frontier_score import _cf_bootstrap_runtime_score_caches, _cf_count_hv_adjacent_endpoints
from .frontier_state import FrontierLaunchContext, FrontierRuntimePolicy, _mark_neighbors_dirty
from .frontier_eval import _cf_choose_seed_chain
from .model import BoundaryChain, ChainRef, FrameRole, PatchEdgeKey, PatchGraph, PatchNode
from .solve_planning import _is_allowed_quilt_edge
from .solve_records import (
    ChainPoolEntry,
    FrontierBootstrapAttempt,
    FrontierBootstrapResult,
    QuiltPlan,
    SolveView,
)

try:
    from .analysis_records import BandSpineData
except ImportError:
    from analysis_records import BandSpineData


def _build_frontier_launch_context(
    graph: PatchGraph,
    quilt_plan: QuiltPlan,
    quilt_patch_ids: set[int],
    allowed_tree_edges: set[PatchEdgeKey],
    tree_ingress_partner_by_chain: dict[ChainRef, ChainRef],
    closure_pair_map: dict[ChainRef, ChainRef],
    final_scale: float,
    *,
    straighten_enabled: bool = False,
    inherited_role_map: Optional[dict[ChainRef, tuple[FrameRole, int]]] = None,
    patch_structural_summaries: Optional[dict] = None,
    patch_shape_classes: Optional[dict] = None,
    straighten_chain_refs: Optional[frozenset[ChainRef]] = None,
    band_spine_data: Optional[dict[int, BandSpineData]] = None,
) -> FrontierLaunchContext:
    return FrontierLaunchContext(
        graph=graph,
        quilt_patch_ids=quilt_patch_ids,
        allowed_tree_edges=allowed_tree_edges,
        final_scale=final_scale,
        seam_relation_by_edge=quilt_plan.seam_relation_by_edge,
        tree_ingress_partner_by_chain=tree_ingress_partner_by_chain,
        closure_pair_map=closure_pair_map,
        straighten_enabled=straighten_enabled,
        inherited_role_map=inherited_role_map or {},
        patch_structural_summaries=patch_structural_summaries or {},
        patch_shape_classes=patch_shape_classes or {},
        straighten_chain_refs=straighten_chain_refs or frozenset(),
        band_spine_data=band_spine_data or {},
    )


def seed_runtime_from_existing_scaffold_context(
    context: FrontierLaunchContext,
    solve_view: SolveView,
    quilt_plan: QuiltPlan,
) -> FrontierBootstrapAttempt:
    """Placeholder seam for future reverse/manual scaffold entry."""

    _ = context, solve_view, quilt_plan
    return FrontierBootstrapAttempt(result=None, error="existing_scaffold_seed_not_implemented")


def bootstrap_frontier_runtime(
    graph: PatchGraph,
    solve_view: SolveView,
    quilt_plan: QuiltPlan,
    root_node: PatchNode,
    quilt_patch_ids: set[int],
    allowed_tree_edges: set[PatchEdgeKey],
    closure_pair_map: dict[ChainRef, ChainRef],
    tree_ingress_partner_by_chain: dict[ChainRef, ChainRef],
    final_scale: float,
    *,
    straighten_enabled: bool = False,
    inherited_role_map: Optional[dict[ChainRef, tuple[FrameRole, int]]] = None,
    patch_structural_summaries: Optional[dict] = None,
    patch_shape_classes: Optional[dict] = None,
    straighten_chain_refs: Optional[frozenset[ChainRef]] = None,
    band_spine_data: Optional[dict[int, BandSpineData]] = None,
) -> FrontierBootstrapAttempt:
    seed_result = _cf_choose_seed_chain(
        solve_view,
        graph,
        root_node,
        quilt_patch_ids,
        allowed_tree_edges,
        is_allowed_quilt_edge=_is_allowed_quilt_edge,
        count_hv_adjacent_endpoints=_cf_count_hv_adjacent_endpoints,
    )
    if seed_result is None:
        return FrontierBootstrapAttempt(result=None, error="no_seed_chain")

    seed_ref = (quilt_plan.root_patch_id, seed_result.loop_index, seed_result.chain_index)
    seed_chain = seed_result.chain
    launch_context = _build_frontier_launch_context(
        graph,
        quilt_plan,
        quilt_patch_ids,
        allowed_tree_edges,
        tree_ingress_partner_by_chain,
        closure_pair_map,
        final_scale,
        straighten_enabled=straighten_enabled,
        inherited_role_map=inherited_role_map,
        patch_structural_summaries=patch_structural_summaries,
        patch_shape_classes=patch_shape_classes,
        straighten_chain_refs=straighten_chain_refs,
        band_spine_data=band_spine_data,
    )
    runtime_policy = FrontierRuntimePolicy(context=launch_context)
    _cf_bootstrap_runtime_score_caches(runtime_policy)

    seed_effective_role = runtime_policy.seed_placement_role(seed_ref, seed_chain)
    seed_station_authority_kind = runtime_policy.resolve_station_authority_kind(
        seed_ref,
        seed_chain,
        effective_role=seed_effective_role,
    )
    seed_payload = _cf_build_seed_placement(
        seed_ref,
        seed_chain,
        root_node,
        final_scale,
        effective_role=seed_effective_role,
        axis_authority_kind=runtime_policy.resolve_axis_authority_kind(
            seed_ref,
            seed_chain,
            effective_role=seed_effective_role,
        ),
        span_authority_kind=runtime_policy.resolve_span_authority_kind(
            seed_ref,
            seed_chain,
            effective_role=seed_effective_role,
        ),
        station_authority_kind=seed_station_authority_kind,
        parameter_authority_kind=runtime_policy.resolve_parameter_authority_kind(
            seed_ref,
            seed_chain,
            effective_role=seed_effective_role,
        ),
        station_map=runtime_policy.resolve_shared_station_map(
            seed_ref,
            seed_chain,
            effective_role=seed_effective_role,
            station_authority_kind=seed_station_authority_kind,
        ),
        target_span=runtime_policy.resolve_target_span(
            seed_ref,
            seed_chain,
            effective_role=seed_effective_role,
        ),
        runtime_policy=runtime_policy,
    )
    if seed_payload is None:
        return FrontierBootstrapAttempt(result=None, error="seed_placement_failed")

    runtime_policy.register_chain(
        seed_ref,
        seed_chain,
        seed_payload.placement,
        seed_payload.uv_points,
        (),
        placed_role=seed_effective_role,
    )

    trace_console(
        f"[CFTUV][Frontier] Seed: P{seed_ref[0]} L{seed_ref[1]}C{seed_ref[2]} "
        f"{seed_effective_role.value} "
        f"({seed_payload.uv_points[0].x:.4f},{seed_payload.uv_points[0].y:.4f})"
        f"->({seed_payload.uv_points[-1].x:.4f},{seed_payload.uv_points[-1].y:.4f})"
        f" score:{seed_result.score:.2f}"
        f" len:{_cf_chain_total_length(seed_chain, final_scale):.4f}"
        f"{f' hv_adj:{_cf_count_hv_adjacent_endpoints(graph, seed_ref, runtime_policy=runtime_policy)}' if seed_effective_role in {FrameRole.H_FRAME, FrameRole.V_FRAME} else ''}"
    )
    if allowed_tree_edges:
        edge_labels = [f"{edge[0]}-{edge[1]}" for edge in sorted(allowed_tree_edges)]
        trace_console(f"[CFTUV][Frontier] Tree edges: {edge_labels}")

    return FrontierBootstrapAttempt(
        result=FrontierBootstrapResult(
            runtime_policy=runtime_policy,
            seed_ref=seed_ref,
            seed_chain=seed_chain,
            seed_score=seed_result.score,
        )
    )


def build_frontier_chain_pool(
    solve_view: SolveView,
    graph: PatchGraph,
    ordered_quilt_patch_ids: list[int],
    seed_ref: ChainRef,
) -> list[ChainPoolEntry]:
    all_chain_pool: list[ChainPoolEntry] = []
    for patch_id in ordered_quilt_patch_ids:
        node = graph.nodes.get(patch_id)
        if node is None:
            continue
        for chain_use, _loop, chain in solve_view.iter_visible_chain_records(patch_id):
            chain_ref = (chain_use.patch_id, chain_use.loop_index, chain_use.chain_index)
            if chain_ref == seed_ref:
                continue
            all_chain_pool.append(
                ChainPoolEntry(
                    chain_ref=chain_ref,
                    chain=chain,
                    node=node,
                )
            )
    return all_chain_pool


def index_frontier_chain_pool(
    runtime_policy: FrontierRuntimePolicy,
    all_chain_pool: list[ChainPoolEntry],
    seed_ref: ChainRef,
    seed_chain: BoundaryChain,
) -> None:
    vert_to_pool: dict[int, list[ChainRef]] = {}
    patch_to_pool: dict[int, list[ChainRef]] = {}
    for pool_entry in all_chain_pool:
        patch_to_pool.setdefault(pool_entry.chain_ref[0], []).append(pool_entry.chain_ref)
        for vert_index in pool_entry.chain.vert_indices:
            vert_to_pool.setdefault(vert_index, []).append(pool_entry.chain_ref)
    for vert_index in seed_chain.vert_indices:
        vert_to_pool.setdefault(vert_index, []).append(seed_ref)
    runtime_policy._vert_to_pool_refs = vert_to_pool
    runtime_policy._patch_to_pool_refs = patch_to_pool
    _mark_neighbors_dirty(runtime_policy, seed_ref, seed_chain)


__all__ = [
    "_build_frontier_launch_context",
    "seed_runtime_from_existing_scaffold_context",
    "bootstrap_frontier_runtime",
    "build_frontier_chain_pool",
    "index_frontier_chain_pool",
]
