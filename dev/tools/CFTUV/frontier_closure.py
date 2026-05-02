from __future__ import annotations

try:
    from .console_debug import trace_console
    from .model import BoundaryChain, ChainRef, FrameRole, PatchEdgeKey, PatchGraph
    from .solve_planning import _iter_neighbor_chains
    from .solve_records import ClosureChainPairCandidate, ClosureChainPairMatch, QuiltPlan
except ImportError:
    from console_debug import trace_console
    from model import BoundaryChain, ChainRef, FrameRole, PatchEdgeKey, PatchGraph
    from solve_planning import _iter_neighbor_chains
    from solve_records import ClosureChainPairCandidate, ClosureChainPairMatch, QuiltPlan


def _match_non_tree_closure_chain_pairs(
    graph: PatchGraph,
    owner_patch_id: int,
    target_patch_id: int,
) -> list[ClosureChainPairMatch]:
    def _chain_polyline_length(chain: BoundaryChain) -> float:
        if len(chain.vert_cos) < 2:
            return 0.0
        return sum(
            (chain.vert_cos[index + 1] - chain.vert_cos[index]).length
            for index in range(len(chain.vert_cos) - 1)
        )

    owner_refs = _iter_neighbor_chains(graph, owner_patch_id, target_patch_id)
    target_refs = _iter_neighbor_chains(graph, target_patch_id, owner_patch_id)
    pair_candidates: list[ClosureChainPairCandidate] = []

    for owner_ref in owner_refs:
        owner_chain = owner_ref.chain
        if owner_chain.frame_role not in {FrameRole.H_FRAME, FrameRole.V_FRAME}:
            continue
        owner_vert_set = set(owner_chain.vert_indices)
        if not owner_vert_set:
            continue
        for target_ref in target_refs:
            target_chain = target_ref.chain
            if target_chain.frame_role != owner_chain.frame_role:
                continue
            target_vert_set = set(target_chain.vert_indices)
            shared_vert_count = len(owner_vert_set & target_vert_set)
            if shared_vert_count <= 0:
                continue
            pair_score = (shared_vert_count * 1000) - abs(len(owner_chain.vert_indices) - len(target_chain.vert_indices))
            owner_chain_length = _chain_polyline_length(owner_chain)
            target_chain_length = _chain_polyline_length(target_chain)
            if owner_chain_length > 0.0 and target_chain_length > 0.0:
                representative_length = min(owner_chain_length, target_chain_length)
            else:
                representative_length = max(owner_chain_length, target_chain_length)
            pair_candidates.append(
                ClosureChainPairCandidate(
                    score=pair_score,
                    representative_length=representative_length,
                    match=ClosureChainPairMatch(
                        owner_ref=(owner_patch_id, owner_ref.loop_index, owner_ref.chain_index),
                        owner_chain=owner_chain,
                        target_ref=(target_patch_id, target_ref.loop_index, target_ref.chain_index),
                        target_chain=target_chain,
                        shared_vert_count=shared_vert_count,
                    ),
                )
            )

    # При равном topological match оставляем более длинный seam-carrier primary,
    # чтобы короткая пара оставалась intentional closure seam на tube/ring topology.
    pair_candidates.sort(
        key=lambda item: (item.score, item.representative_length),
        reverse=True,
    )
    matched_owner_refs = set()
    matched_target_refs = set()
    matched_pairs: list[ClosureChainPairMatch] = []
    for candidate in pair_candidates:
        match = candidate.match
        if match.owner_ref in matched_owner_refs or match.target_ref in matched_target_refs:
            continue
        matched_owner_refs.add(match.owner_ref)
        matched_target_refs.add(match.target_ref)
        matched_pairs.append(match)

    return matched_pairs


def _iter_quilt_closure_chain_pairs(
    graph: PatchGraph,
    quilt_patch_ids: set[int],
    allowed_tree_edges: set[PatchEdgeKey],
    tree_ingress_pair_map: dict[PatchEdgeKey, frozenset[ChainRef]] | None = None,
):
    """Iterate closure-side chain pairs inside one quilt."""

    quilt_patch_pairs = sorted(
        edge_key
        for edge_key in graph.edges.keys()
        if edge_key[0] in quilt_patch_ids and edge_key[1] in quilt_patch_ids
    )

    for owner_patch_id, target_patch_id in quilt_patch_pairs:
        matched_pairs = _match_non_tree_closure_chain_pairs(graph, owner_patch_id, target_patch_id)
        if not matched_pairs:
            continue

        if (owner_patch_id, target_patch_id) in allowed_tree_edges:
            primary_pair_refs = None
            if tree_ingress_pair_map is not None:
                primary_pair_refs = tree_ingress_pair_map.get((owner_patch_id, target_patch_id))
            if primary_pair_refs is not None:
                matched_pairs = [
                    match
                    for match in matched_pairs
                    if frozenset((match.owner_ref, match.target_ref)) != primary_pair_refs
                ]
            else:
                matched_pairs = matched_pairs[1:]
            if not matched_pairs:
                continue

        yield owner_patch_id, target_patch_id, matched_pairs


def _build_quilt_closure_pair_map(
    graph: PatchGraph,
    quilt_plan: QuiltPlan,
    quilt_patch_ids: set[int],
    allowed_tree_edges: set[PatchEdgeKey],
) -> dict[ChainRef, ChainRef]:
    tree_ingress_pair_map: dict[PatchEdgeKey, frozenset[ChainRef]] = {}
    for edge_key in sorted(allowed_tree_edges):
        owner_patch_id, target_patch_id = edge_key
        matched_pairs = _match_non_tree_closure_chain_pairs(graph, owner_patch_id, target_patch_id)
        if not matched_pairs:
            continue
        primary_match = matched_pairs[0]
        tree_ingress_pair_map[edge_key] = frozenset((
            primary_match.owner_ref,
            primary_match.target_ref,
        ))
        trace_console(
            f"[CFTUV][Frontier] Tree pair {owner_patch_id}-{target_patch_id}: "
            f"P{primary_match.owner_ref[0]} L{primary_match.owner_ref[1]}C{primary_match.owner_ref[2]}"
            f"<->"
            f"P{primary_match.target_ref[0]} L{primary_match.target_ref[1]}C{primary_match.target_ref[2]}"
        )

    for step in quilt_plan.steps:
        candidate = step.incoming_candidate
        if candidate is None:
            continue
        edge_key = (
            min(candidate.owner_patch_id, candidate.target_patch_id),
            max(candidate.owner_patch_id, candidate.target_patch_id),
        )
        if edge_key in tree_ingress_pair_map:
            continue
        tree_ingress_pair_map[edge_key] = frozenset((
            (candidate.owner_patch_id, candidate.owner_loop_index, candidate.owner_chain_index),
            (candidate.target_patch_id, candidate.target_loop_index, candidate.target_chain_index),
        ))

    pair_map: dict[ChainRef, ChainRef] = {}
    for _owner_patch_id, _target_patch_id, matched_pairs in _iter_quilt_closure_chain_pairs(
        graph,
        quilt_patch_ids,
        allowed_tree_edges,
        tree_ingress_pair_map,
    ):
        for match in matched_pairs:
            pair_map[match.owner_ref] = match.target_ref
            pair_map[match.target_ref] = match.owner_ref
    return pair_map


def _build_tree_ingress_partner_map(quilt_plan: QuiltPlan) -> dict[ChainRef, ChainRef]:
    partner_map: dict[ChainRef, ChainRef] = {}
    for step in quilt_plan.steps:
        candidate = step.incoming_candidate
        if candidate is None:
            continue
        owner_ref = (
            candidate.owner_patch_id,
            candidate.owner_loop_index,
            candidate.owner_chain_index,
        )
        target_ref = (
            candidate.target_patch_id,
            candidate.target_loop_index,
            candidate.target_chain_index,
        )
        partner_map[owner_ref] = target_ref
        partner_map[target_ref] = owner_ref
    return partner_map
