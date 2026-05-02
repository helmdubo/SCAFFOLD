from __future__ import annotations

from dataclasses import replace
from heapq import heappop, heappush
from typing import Optional

try:
    from .console_debug import trace_console
    from .analysis import build_neighbor_inherited_roles
    from .constants import (
        ROOT_WEIGHT_AREA, ROOT_WEIGHT_FRAME, ROOT_WEIGHT_FREE_RATIO,
        ROOT_WEIGHT_HOLES, ROOT_WEIGHT_BASE,
        ATTACH_WEIGHT_SEAM, ATTACH_WEIGHT_PAIR, ATTACH_WEIGHT_TARGET, ATTACH_WEIGHT_OWNER,
        PAIR_WEIGHT_FRAME_CONT, PAIR_WEIGHT_ENDPOINT, PAIR_WEIGHT_CORNER,
        PAIR_WEIGHT_SEMANTIC, PAIR_WEIGHT_EP_STRENGTH, PAIR_WEIGHT_LOOP,
        CLOSURE_CUT_WEIGHT_FRAME_CONT, CLOSURE_CUT_WEIGHT_ENDPOINT_BRIDGE,
        CLOSURE_CUT_WEIGHT_ENDPOINT_STR, CLOSURE_CUT_WEIGHT_SEAM_NORM,
        CLOSURE_CUT_WEIGHT_FIXED_RATIO, CLOSURE_CUT_WEIGHT_SAME_AXIS,
        CLOSURE_CUT_WEIGHT_FREE_TOUCH, CLOSURE_CUT_WEIGHT_DIHEDRAL,
    )
    from .model import (
        BoundaryChain, FrameRole, LoopKind,
        PatchGraph, PatchNode,
        ChainRef, PatchEdgeKey, PatchType,
    )
    from .solve_records import (
        PatchCertainty, SolveComponentsResult, AttachmentCandidate,
        SolverGraph, SolveView, QuiltStep, QuiltStopReason, QuiltPlan, SolvePlan,
        AttachmentCandidatePreference, ChainPairSelection, AttachmentNeighborRef,
        ChainEndpointContext, EndpointMatch, EndpointBridgeMetrics, EndpointSupportStats,
        ClosureCutHeuristic, QuiltClosureCutAnalysis, PatchRoleCounts,
        SeamRelationProfile,
        ClosureChainPairMatch, ClosureChainPairCandidate,
        EDGE_PROPAGATE_MIN, EDGE_WEAK_MIN,
        _clamp01, _patch_pair_key,
    )
except ImportError:
    from console_debug import trace_console
    from analysis import build_neighbor_inherited_roles
    from constants import (
        ROOT_WEIGHT_AREA, ROOT_WEIGHT_FRAME, ROOT_WEIGHT_FREE_RATIO,
        ROOT_WEIGHT_HOLES, ROOT_WEIGHT_BASE,
        ATTACH_WEIGHT_SEAM, ATTACH_WEIGHT_PAIR, ATTACH_WEIGHT_TARGET, ATTACH_WEIGHT_OWNER,
        PAIR_WEIGHT_FRAME_CONT, PAIR_WEIGHT_ENDPOINT, PAIR_WEIGHT_CORNER,
        PAIR_WEIGHT_SEMANTIC, PAIR_WEIGHT_EP_STRENGTH, PAIR_WEIGHT_LOOP,
        CLOSURE_CUT_WEIGHT_FRAME_CONT, CLOSURE_CUT_WEIGHT_ENDPOINT_BRIDGE,
        CLOSURE_CUT_WEIGHT_ENDPOINT_STR, CLOSURE_CUT_WEIGHT_SEAM_NORM,
        CLOSURE_CUT_WEIGHT_FIXED_RATIO, CLOSURE_CUT_WEIGHT_SAME_AXIS,
        CLOSURE_CUT_WEIGHT_FREE_TOUCH, CLOSURE_CUT_WEIGHT_DIHEDRAL,
    )
    from model import (
        BoundaryChain, FrameRole, LoopKind,
        PatchGraph, PatchNode,
        ChainRef, PatchEdgeKey, PatchType,
    )
    from solve_records import (
        PatchCertainty, SolveComponentsResult, AttachmentCandidate,
        SolverGraph, SolveView, QuiltStep, QuiltStopReason, QuiltPlan, SolvePlan,
        AttachmentCandidatePreference, ChainPairSelection, AttachmentNeighborRef,
        ChainEndpointContext, EndpointMatch, EndpointBridgeMetrics, EndpointSupportStats,
        ClosureCutHeuristic, QuiltClosureCutAnalysis, PatchRoleCounts,
        SeamRelationProfile,
        ClosureChainPairMatch, ClosureChainPairCandidate,
        EDGE_PROPAGATE_MIN, EDGE_WEAK_MIN,
        _clamp01, _patch_pair_key,
    )


def _build_solve_view(graph: PatchGraph) -> SolveView:
    visible_loop_indices_by_patch: dict[int, tuple[int, ...]] = {}
    primary_loop_index_by_patch: dict[int, int] = {}
    locally_solvable_patch_ids: set[int] = set()

    for patch_id, node in graph.nodes.items():
        visible_loop_indices = tuple(
            loop_index
            for loop_index, boundary_loop in enumerate(node.boundary_loops)
            if boundary_loop.kind == LoopKind.OUTER
        )
        visible_loop_indices_by_patch[patch_id] = visible_loop_indices
        if visible_loop_indices:
            primary_loop_index_by_patch[patch_id] = visible_loop_indices[0]

        if visible_loop_indices and len(visible_loop_indices) == 1 and all(loop.chains for loop in node.boundary_loops):
            locally_solvable_patch_ids.add(patch_id)

    return SolveView(
        graph=graph,
        visible_loop_indices_by_patch=visible_loop_indices_by_patch,
        primary_loop_index_by_patch=primary_loop_index_by_patch,
        locally_solvable_patch_ids=frozenset(locally_solvable_patch_ids),
    )


def _iter_neighbor_chains(graph: PatchGraph, owner_patch_id: int, target_patch_id: int):
    """Compatibility shim during Phase 2 rollout.

    Hot-path solve entry points use SolveView directly. Remaining stateless callers
    can still route through the same central visibility layer here.
    """
    return _build_solve_view(graph).iter_attachment_neighbor_chains(owner_patch_id, target_patch_id)


def _build_solve_components(graph: PatchGraph, candidates: list[AttachmentCandidate]) -> SolveComponentsResult:
    adjacency = {patch_id: set() for patch_id in graph.nodes}

    for candidate in candidates:
        adjacency.setdefault(candidate.owner_patch_id, set()).add(candidate.target_patch_id)
        adjacency.setdefault(candidate.target_patch_id, set()).add(candidate.owner_patch_id)

    components: list[set[int]] = []
    component_by_patch: dict[int, int] = {}

    for patch_id in graph.nodes:
        if patch_id in component_by_patch:
            continue

        component = set()
        stack = [patch_id]
        while stack:
            current_id = stack.pop()
            if current_id in component:
                continue
            component.add(current_id)
            for neighbor_id in adjacency.get(current_id, ()):
                if neighbor_id not in component:
                    stack.append(neighbor_id)

        component_index = len(components)
        components.append(component)
        for component_patch_id in component:
            component_by_patch[component_patch_id] = component_index

    return SolveComponentsResult(components=components, component_by_patch=component_by_patch)


def _build_quilt_tree_edges(quilt_plan: QuiltPlan) -> set[PatchEdgeKey]:
    edges = set()
    for step in quilt_plan.steps:
        candidate = step.incoming_candidate
        if candidate is None:
            continue
        edges.add(_patch_pair_key(candidate.owner_patch_id, candidate.target_patch_id))
    return edges


def _rebuild_quilt_steps_with_forbidden_edges(
    quilt_plan: QuiltPlan,
    solver_graph: SolverGraph,
    forbidden_edge_keys: set[PatchEdgeKey],
) -> Optional[QuiltPlan]:
    quilt_patch_ids = set(quilt_plan.solved_patch_ids)
    quilt_patch_ids.add(quilt_plan.root_patch_id)
    if len(quilt_patch_ids) <= 1:
        return quilt_plan

    solved_patch_ids: set[int] = {quilt_plan.root_patch_id}
    ordered_patch_ids: list[int] = [quilt_plan.root_patch_id]
    steps: list[QuiltStep] = [
        QuiltStep(step_index=0, patch_id=quilt_plan.root_patch_id, is_root=True)
    ]
    frontier_heap = []
    queue_index = 0

    def enqueue_patch_candidates(patch_id: int) -> None:
        nonlocal queue_index
        for candidate in solver_graph.candidates_by_owner.get(patch_id, ()):
            if candidate.target_patch_id not in quilt_patch_ids:
                continue
            if candidate.target_patch_id in solved_patch_ids:
                continue
            edge_key = _patch_pair_key(candidate.owner_patch_id, candidate.target_patch_id)
            if edge_key in forbidden_edge_keys:
                continue
            heappush(frontier_heap, (-candidate.score, queue_index, candidate))
            queue_index += 1

    enqueue_patch_candidates(quilt_plan.root_patch_id)

    while frontier_heap and len(solved_patch_ids) < len(quilt_patch_ids):
        _, _, candidate = heappop(frontier_heap)
        if candidate.target_patch_id in solved_patch_ids:
            continue
        if candidate.target_patch_id not in quilt_patch_ids:
            continue
        edge_key = _patch_pair_key(candidate.owner_patch_id, candidate.target_patch_id)
        if edge_key in forbidden_edge_keys:
            continue

        solved_patch_ids.add(candidate.target_patch_id)
        ordered_patch_ids.append(candidate.target_patch_id)
        steps.append(
            QuiltStep(
                step_index=len(steps),
                patch_id=candidate.target_patch_id,
                is_root=False,
                incoming_candidate=candidate,
            )
        )
        enqueue_patch_candidates(candidate.target_patch_id)

    if solved_patch_ids != quilt_patch_ids:
        return None

    rebuilt = replace(quilt_plan)
    if not rebuilt.original_steps:
        rebuilt.original_steps = list(quilt_plan.steps)
    if not rebuilt.original_solved_patch_ids:
        rebuilt.original_solved_patch_ids = list(quilt_plan.solved_patch_ids)
    rebuilt.solved_patch_ids = ordered_patch_ids
    rebuilt.steps = steps
    return rebuilt


def _is_allowed_quilt_edge(
    allowed_tree_edges: set[PatchEdgeKey],
    patch_a_id: int,
    patch_b_id: int,
) -> bool:
    return _patch_pair_key(patch_a_id, patch_b_id) in allowed_tree_edges


def _build_patch_tree_adjacency(quilt_plan: QuiltPlan) -> dict[int, set[int]]:
    adjacency = {quilt_plan.root_patch_id: set()}
    for patch_id in quilt_plan.solved_patch_ids:
        adjacency.setdefault(patch_id, set())
    for edge_a, edge_b in _build_quilt_tree_edges(quilt_plan):
        adjacency.setdefault(edge_a, set()).add(edge_b)
        adjacency.setdefault(edge_b, set()).add(edge_a)
    return adjacency


def _find_patch_tree_path(
    patch_tree_adjacency: dict[int, set[int]],
    start_patch_id: int,
    target_patch_id: int,
) -> list[int]:
    if start_patch_id == target_patch_id:
        return [start_patch_id]
    if start_patch_id not in patch_tree_adjacency or target_patch_id not in patch_tree_adjacency:
        return []

    parents = {start_patch_id: -1}
    queue = [start_patch_id]
    queue_index = 0
    while queue_index < len(queue):
        current_patch_id = queue[queue_index]
        queue_index += 1
        for neighbor_patch_id in patch_tree_adjacency.get(current_patch_id, ()):
            if neighbor_patch_id in parents:
                continue
            parents[neighbor_patch_id] = current_patch_id
            if neighbor_patch_id == target_patch_id:
                path = [target_patch_id]
                cursor = target_patch_id
                while parents[cursor] >= 0:
                    cursor = parents[cursor]
                    path.append(cursor)
                path.reverse()
                return path
            queue.append(neighbor_patch_id)
    return []


def _count_patch_roles(node: PatchNode) -> PatchRoleCounts:
    outer_count = 0
    hole_count = 0
    chain_count = 0
    free_count = 0
    h_count = 0
    v_count = 0

    for boundary_loop in node.boundary_loops:
        if boundary_loop.kind == LoopKind.OUTER:
            outer_count += 1
        elif boundary_loop.kind == LoopKind.HOLE:
            hole_count += 1

        for chain in boundary_loop.chains:
            chain_count += 1
            if chain.frame_role == FrameRole.H_FRAME:
                h_count += 1
            elif chain.frame_role == FrameRole.V_FRAME:
                v_count += 1
            else:
                free_count += 1

    return PatchRoleCounts(
        outer_count=outer_count,
        hole_count=hole_count,
        chain_count=chain_count,
        free_count=free_count,
        h_count=h_count,
        v_count=v_count,
    )


def _frame_presence_strength(h_count: int, v_count: int) -> float:
    if h_count > 0 and v_count > 0:
        return 1.0
    if h_count > 0 or v_count > 0:
        return 0.6
    return 0.2


def _semantic_stability_bonus(node: PatchNode) -> float:
    patch_type = node.patch_type.value if hasattr(node.patch_type, 'value') else str(node.patch_type)
    world_facing = node.world_facing.value if hasattr(node.world_facing, 'value') else str(node.world_facing)
    if patch_type == "WALL" and world_facing == "SIDE":
        return 0.06
    if patch_type == "FLOOR" and world_facing in {"UP", "DOWN"}:
        return 0.06
    if patch_type == "SLOPE":
        return 0.04
    return 0.02


def _build_patch_certainty(node: PatchNode, solve_view: SolveView, max_area: float) -> PatchCertainty:
    role_counts = _count_patch_roles(node)
    local_solvable = solve_view.patch_is_locally_solvable(node.patch_id)
    if not local_solvable:
        return PatchCertainty(
            patch_id=node.patch_id,
            local_solvable=False,
            root_score=0.0,
            outer_count=role_counts.outer_count,
            hole_count=role_counts.hole_count,
            chain_count=role_counts.chain_count,
            free_count=role_counts.free_count,
            h_count=role_counts.h_count,
            v_count=role_counts.v_count,
            reasons=("local_gate=fail",),
        )

    area_norm = 0.0 if max_area <= 0.0 else _clamp01(node.area / max_area)
    free_ratio = 1.0 if role_counts.chain_count <= 0 else float(role_counts.free_count) / float(role_counts.chain_count)
    frame_strength = _frame_presence_strength(role_counts.h_count, role_counts.v_count)
    hole_factor = _clamp01(1.0 - min(role_counts.hole_count, 2) * 0.35)
    root_score = (
        ROOT_WEIGHT_AREA * area_norm
        + ROOT_WEIGHT_FRAME * frame_strength
        + ROOT_WEIGHT_FREE_RATIO * _clamp01(1.0 - free_ratio)
        + ROOT_WEIGHT_HOLES * hole_factor
        + ROOT_WEIGHT_BASE * 1.0
        + _semantic_stability_bonus(node)
    )
    root_score = _clamp01(root_score)

    reasons = (
        f"area={area_norm:.2f}",
        f"frame={frame_strength:.2f}",
        f"free={_clamp01(1.0 - free_ratio):.2f}",
        f"holes={hole_factor:.2f}",
    )
    return PatchCertainty(
        patch_id=node.patch_id,
        local_solvable=True,
        root_score=root_score,
        outer_count=role_counts.outer_count,
        hole_count=role_counts.hole_count,
        chain_count=role_counts.chain_count,
        free_count=role_counts.free_count,
        h_count=role_counts.h_count,
        v_count=role_counts.v_count,
        reasons=reasons,
    )


def _chain_endpoint_strength(
    graph: PatchGraph,
    patch_id: int,
    loop_index: int,
    chain_index: int,
    chain: BoundaryChain,
) -> float:
    score = 0.0
    if chain.start_corner_index >= 0:
        score += 0.35
    if chain.end_corner_index >= 0:
        score += 0.35

    neighbors = graph.get_chain_endpoint_neighbors(patch_id, loop_index, chain_index)
    if neighbors.get("start"):
        score += 0.15
    if neighbors.get("end"):
        score += 0.15
    return _clamp01(score)


def _get_chain_corner(graph: PatchGraph, patch_id: int, loop_index: int, corner_index: int):
    node = graph.nodes.get(patch_id)
    if node is None or loop_index < 0 or loop_index >= len(node.boundary_loops):
        return None
    boundary_loop = node.boundary_loops[loop_index]
    if corner_index < 0 or corner_index >= len(boundary_loop.corners):
        return None
    return boundary_loop.corners[corner_index]


def _get_chain_endpoint_context(
    graph: PatchGraph,
    patch_id: int,
    loop_index: int,
    chain_index: int,
    endpoint_label: str,
) -> Optional[ChainEndpointContext]:
    chain = graph.get_chain(patch_id, loop_index, chain_index)
    if chain is None:
        return None

    endpoint_neighbors = graph.get_chain_endpoint_neighbors(patch_id, loop_index, chain_index)
    if endpoint_label == 'start':
        return ChainEndpointContext(
            vert_index=chain.start_vert_index,
            corner=_get_chain_corner(graph, patch_id, loop_index, chain.start_corner_index),
            neighbors=tuple(endpoint_neighbors.get('start', ())),
        )
    return ChainEndpointContext(
        vert_index=chain.end_vert_index,
        corner=_get_chain_corner(graph, patch_id, loop_index, chain.end_corner_index),
        neighbors=tuple(endpoint_neighbors.get('end', ())),
    )


def _corner_similarity_strength(owner_corner, target_corner) -> float:
    if owner_corner is None or target_corner is None:
        return 0.0
    angle_delta = abs(owner_corner.turn_angle_deg - target_corner.turn_angle_deg)
    similarity = _clamp01(1.0 - (angle_delta / 90.0))
    sharp_avg = _clamp01(((owner_corner.turn_angle_deg / 90.0) + (target_corner.turn_angle_deg / 90.0)) * 0.5)
    return _clamp01(0.5 * similarity + 0.5 * sharp_avg)


def _find_endpoint_matches(owner_chain: BoundaryChain, target_chain: BoundaryChain) -> list[EndpointMatch]:
    owner_endpoints = (('start', owner_chain.start_vert_index), ('end', owner_chain.end_vert_index))
    target_endpoints = (('start', target_chain.start_vert_index), ('end', target_chain.end_vert_index))
    matches: list[EndpointMatch] = []
    for owner_label, owner_vert in owner_endpoints:
        if owner_vert < 0:
            continue
        for target_label, target_vert in target_endpoints:
            if owner_vert != target_vert or target_vert < 0:
                continue
            matches.append(EndpointMatch(
                owner_label=owner_label,
                target_label=target_label,
            ))
    return matches


def _endpoint_bridge_strength(
    graph: PatchGraph,
    owner_patch_id: int,
    owner_loop_index: int,
    owner_chain_index: int,
    owner_chain: BoundaryChain,
    target_patch_id: int,
    target_loop_index: int,
    target_chain_index: int,
    target_chain: BoundaryChain,
) -> EndpointBridgeMetrics:
    endpoint_matches = _find_endpoint_matches(owner_chain, target_chain)
    if not endpoint_matches:
        return EndpointBridgeMetrics(endpoint_bridge=0.0, corner_strength=0.0)

    bridge_scores = []
    corner_scores = []
    for endpoint_match in endpoint_matches:
        owner_ctx = _get_chain_endpoint_context(
            graph, owner_patch_id, owner_loop_index, owner_chain_index, endpoint_match.owner_label)
        target_ctx = _get_chain_endpoint_context(
            graph, target_patch_id, target_loop_index, target_chain_index, endpoint_match.target_label)
        if owner_ctx is None or target_ctx is None:
            continue

        corner_strength = _corner_similarity_strength(owner_ctx.corner, target_ctx.corner)
        corner_scores.append(corner_strength)

        best_neighbor_bridge = 0.0
        for owner_ref in owner_ctx.neighbors:
            owner_neighbor_chain = graph.get_chain(owner_patch_id, owner_ref[0], owner_ref[1])
            if owner_neighbor_chain is None:
                continue
            for target_ref in target_ctx.neighbors:
                target_neighbor_chain = graph.get_chain(target_patch_id, target_ref[0], target_ref[1])
                if target_neighbor_chain is None:
                    continue
                best_neighbor_bridge = max(
                    best_neighbor_bridge,
                    _frame_continuation_strength(owner_neighbor_chain.frame_role, target_neighbor_chain.frame_role),
                )

        bridge_scores.append(_clamp01(0.75 * best_neighbor_bridge + 0.25 * corner_strength))

    if not bridge_scores:
        return EndpointBridgeMetrics(endpoint_bridge=0.0, corner_strength=0.0)
    return EndpointBridgeMetrics(
        endpoint_bridge=_clamp01(sum(bridge_scores) / len(bridge_scores)),
        corner_strength=_clamp01(sum(corner_scores) / len(corner_scores)),
    )


def _frame_continuation_strength(
    owner_role: FrameRole,
    target_role: FrameRole,
    *,
    owner_inherited: bool = False,
    target_inherited: bool = False,
) -> float:
    owner_is_frame = owner_role in {FrameRole.H_FRAME, FrameRole.V_FRAME}
    target_is_frame = target_role in {FrameRole.H_FRAME, FrameRole.V_FRAME}
    inherited_count = int(owner_inherited) + int(target_inherited)

    if owner_is_frame and target_is_frame and owner_role == target_role:
        if inherited_count <= 0:
            return 1.0
        if inherited_count == 1:
            return 0.82
        return 0.70
    if owner_is_frame and target_is_frame:
        if inherited_count <= 0:
            return 0.55
        if inherited_count == 1:
            return 0.38
        return 0.28
    if owner_is_frame or target_is_frame:
        if owner_inherited or target_inherited:
            return 0.0
        return 0.05
    return 0.0


def _semantic_pair_strength(graph: PatchGraph, owner_patch_id: int, target_patch_id: int) -> float:
    owner_key = graph.get_patch_semantic_key(owner_patch_id)
    target_key = graph.get_patch_semantic_key(target_patch_id)
    if owner_key == target_key:
        return 1.0

    owner_type = owner_key.split('.', 1)[0]
    target_type = target_key.split('.', 1)[0]
    if owner_type == target_type:
        return 0.85

    pair = {owner_type, target_type}
    if pair == {'WALL', 'FLOOR'}:
        return 0.35
    if pair == {'WALL', 'SLOPE'}:
        return 0.55
    if pair == {'FLOOR', 'SLOPE'}:
        return 0.55
    return 0.40


def _loop_pair_strength(owner_loop_kind: LoopKind, target_loop_kind: LoopKind) -> float:
    if owner_loop_kind == LoopKind.OUTER and target_loop_kind == LoopKind.OUTER:
        return 1.0
    if owner_loop_kind == target_loop_kind:
        return 0.55
    return 0.35


def _effective_planning_role(
    chain_ref: ChainRef,
    chain: BoundaryChain,
    inherited_role_map: dict[ChainRef, tuple[FrameRole, int]],
) -> FrameRole:
    if chain.frame_role != FrameRole.FREE:
        return chain.frame_role
    inherited = inherited_role_map.get(chain_ref)
    if inherited is None:
        return FrameRole.FREE
    return inherited[0]


def _has_inherited_planning_role(
    chain_ref: ChainRef,
    chain: BoundaryChain,
    inherited_role_map: dict[ChainRef, tuple[FrameRole, int]],
) -> bool:
    return (
        chain.frame_role == FrameRole.FREE
        and _effective_planning_role(chain_ref, chain, inherited_role_map) in {FrameRole.H_FRAME, FrameRole.V_FRAME}
    )


def _rank_chain_pairs(
    graph: PatchGraph,
    owner_patch_id: int,
    owner_refs: list[AttachmentNeighborRef],
    target_patch_id: int,
    target_refs: list[AttachmentNeighborRef],
    inherited_role_map: dict[ChainRef, tuple[FrameRole, int]],
) -> list[tuple[ChainPairSelection, float]]:
    ranked_pairs: list[tuple[ChainPairSelection, float]] = []
    semantic_strength = _semantic_pair_strength(graph, owner_patch_id, target_patch_id)

    for owner_ref in owner_refs:
        owner_chain_ref = (owner_patch_id, owner_ref.loop_index, owner_ref.chain_index)
        owner_effective_role = _effective_planning_role(owner_chain_ref, owner_ref.chain, inherited_role_map)
        owner_inherited = _has_inherited_planning_role(owner_chain_ref, owner_ref.chain, inherited_role_map)
        owner_endpoint = _chain_endpoint_strength(
            graph, owner_patch_id, owner_ref.loop_index, owner_ref.chain_index, owner_ref.chain)
        for target_ref in target_refs:
            target_chain_ref = (target_patch_id, target_ref.loop_index, target_ref.chain_index)
            target_effective_role = _effective_planning_role(target_chain_ref, target_ref.chain, inherited_role_map)
            target_inherited = _has_inherited_planning_role(target_chain_ref, target_ref.chain, inherited_role_map)
            target_endpoint = _chain_endpoint_strength(
                graph, target_patch_id, target_ref.loop_index, target_ref.chain_index, target_ref.chain)
            endpoint_strength = (owner_endpoint + target_endpoint) * 0.5
            frame_continuation = _frame_continuation_strength(
                owner_effective_role,
                target_effective_role,
                owner_inherited=owner_inherited,
                target_inherited=target_inherited,
            )
            bridge_metrics = _endpoint_bridge_strength(
                graph,
                owner_patch_id,
                owner_ref.loop_index,
                owner_ref.chain_index,
                owner_ref.chain,
                target_patch_id,
                target_ref.loop_index,
                target_ref.chain_index,
                target_ref.chain,
            )
            endpoint_bridge = bridge_metrics.endpoint_bridge
            corner_strength = bridge_metrics.corner_strength
            pair_strength = (
                PAIR_WEIGHT_FRAME_CONT * frame_continuation
                + PAIR_WEIGHT_ENDPOINT * endpoint_bridge
                + PAIR_WEIGHT_CORNER * corner_strength
                + PAIR_WEIGHT_SEMANTIC * semantic_strength
                + PAIR_WEIGHT_EP_STRENGTH * endpoint_strength
                + PAIR_WEIGHT_LOOP * _loop_pair_strength(owner_ref.boundary_loop.kind, target_ref.boundary_loop.kind)
            )
            owner_chain_length = _chain_polyline_length(owner_ref.chain)
            target_chain_length = _chain_polyline_length(target_ref.chain)
            if owner_chain_length > 0.0 and target_chain_length > 0.0:
                representative_length = min(owner_chain_length, target_chain_length)
            else:
                representative_length = max(owner_chain_length, target_chain_length)

            ranked_pairs.append((
                ChainPairSelection(
                    owner_ref=owner_ref,
                    target_ref=target_ref,
                    pair_strength=_clamp01(pair_strength),
                    endpoint_strength=_clamp01(endpoint_strength),
                    frame_continuation=_clamp01(frame_continuation),
                    endpoint_bridge=_clamp01(endpoint_bridge),
                    corner_strength=_clamp01(corner_strength),
                    semantic_strength=_clamp01(semantic_strength),
                ),
                representative_length,
            ))

    ranked_pairs.sort(
        key=lambda item: (item[0].pair_strength, item[1]),
        reverse=True,
    )
    return ranked_pairs


def _best_chain_pair(
    graph: PatchGraph,
    owner_patch_id: int,
    owner_refs: list[AttachmentNeighborRef],
    target_patch_id: int,
    target_refs: list[AttachmentNeighborRef],
    inherited_role_map: dict[ChainRef, tuple[FrameRole, int]],
) -> Optional[ChainPairSelection]:
    ranked_pairs = _rank_chain_pairs(
        graph,
        owner_patch_id,
        owner_refs,
        target_patch_id,
        target_refs,
        inherited_role_map,
    )
    return ranked_pairs[0][0] if ranked_pairs else None


def _build_attachment_candidate(
    solve_view: SolveView,
    owner_patch_id: int,
    target_patch_id: int,
    seam,
    patch_scores: dict[int, PatchCertainty],
    max_shared_length: float,
    inherited_role_map: dict[ChainRef, tuple[FrameRole, int]],
) -> Optional[AttachmentCandidate]:
    graph = solve_view.graph
    owner_score = patch_scores[owner_patch_id]
    target_score = patch_scores[target_patch_id]
    if not solve_view.patch_types_compatible(owner_patch_id, target_patch_id):
        return None
    owner_refs = solve_view.iter_attachment_neighbor_chains(owner_patch_id, target_patch_id)
    target_refs = solve_view.iter_attachment_neighbor_chains(target_patch_id, owner_patch_id)

    if not owner_refs or not target_refs:
        return None

    best_pair = _best_chain_pair(
        graph,
        owner_patch_id,
        owner_refs,
        target_patch_id,
        target_refs,
        inherited_role_map,
    )
    if best_pair is None:
        return None

    # Если лучшая пара — FREE+FREE (frame_continuation == 0),
    # нет структурной опоры для anchor propagation → отдельный quilt.
    owner_ref = best_pair.owner_ref
    target_ref = best_pair.target_ref
    owner_loop_index = owner_ref.loop_index
    owner_chain_index = owner_ref.chain_index
    owner_loop = owner_ref.boundary_loop
    owner_chain = owner_ref.chain
    target_loop_index = target_ref.loop_index
    target_chain_index = target_ref.chain_index
    target_loop = target_ref.boundary_loop
    target_chain = target_ref.chain
    owner_chain_ref = (owner_patch_id, owner_loop_index, owner_chain_index)
    target_chain_ref = (target_patch_id, target_loop_index, target_chain_index)
    owner_effective_role = _effective_planning_role(owner_chain_ref, owner_chain, inherited_role_map)
    target_effective_role = _effective_planning_role(target_chain_ref, target_chain, inherited_role_map)
    owner_inherited = _has_inherited_planning_role(owner_chain_ref, owner_chain, inherited_role_map)
    target_inherited = _has_inherited_planning_role(target_chain_ref, target_chain, inherited_role_map)
    raw_free_free_pair = (
        owner_chain.frame_role == FrameRole.FREE
        and target_chain.frame_role == FrameRole.FREE
    )
    inherited_hv_support = (
        owner_effective_role in {FrameRole.H_FRAME, FrameRole.V_FRAME}
        and target_effective_role in {FrameRole.H_FRAME, FrameRole.V_FRAME}
        and owner_effective_role == target_effective_role
        and owner_inherited
        and target_inherited
    )

    if best_pair.frame_continuation <= 0.0:
        return None
    if raw_free_free_pair and not inherited_hv_support:
        return None

    seam_norm = 1.0 if max_shared_length <= 0.0 else _clamp01(seam.shared_length / max_shared_length)
    ambiguity_penalty = min(0.15, 0.05 * max(0, len(owner_refs) - 1) + 0.05 * max(0, len(target_refs) - 1))

    if not owner_score.local_solvable or not target_score.local_solvable:
        total_score = 0.0
    else:
        total_score = (
            ATTACH_WEIGHT_SEAM * seam_norm
            + ATTACH_WEIGHT_PAIR * best_pair.pair_strength
            + ATTACH_WEIGHT_TARGET * target_score.root_score
            + ATTACH_WEIGHT_OWNER * owner_score.root_score
            - ambiguity_penalty
        )
        owner_is_frame = owner_effective_role in {FrameRole.H_FRAME, FrameRole.V_FRAME}
        target_is_frame = target_effective_role in {FrameRole.H_FRAME, FrameRole.V_FRAME}
        if owner_is_frame ^ target_is_frame:
            total_score -= max(0.0, 0.12 - 0.10 * best_pair.endpoint_bridge)
        elif not owner_is_frame and not target_is_frame:
            total_score -= max(0.0, 0.25 - 0.20 * best_pair.endpoint_bridge)
        if target_score.hole_count > 0:
            total_score -= min(0.08, target_score.hole_count * 0.04)
        total_score = _clamp01(total_score)

    reasons = (
        f"seam={seam_norm:.2f}",
        f"pair={best_pair.pair_strength:.2f}",
        f"cont={best_pair.frame_continuation:.2f}",
        f"roles={owner_effective_role.value}<->{target_effective_role.value}",
        f"inh={int(owner_inherited)}{int(target_inherited)}",
        f"bridge={best_pair.endpoint_bridge:.2f}",
        f"corner={best_pair.corner_strength:.2f}",
        f"sem={best_pair.semantic_strength:.2f}",
        f"ep={best_pair.endpoint_strength:.2f}",
        f"target={target_score.root_score:.2f}",
        f"amb={ambiguity_penalty:.2f}",
    )
    return AttachmentCandidate(
        owner_patch_id=owner_patch_id,
        target_patch_id=target_patch_id,
        score=total_score,
        seam_length=seam.shared_length,
        seam_norm=seam_norm,
        best_pair_strength=best_pair.pair_strength,
        frame_continuation=best_pair.frame_continuation,
        endpoint_bridge=best_pair.endpoint_bridge,
        corner_strength=best_pair.corner_strength,
        semantic_strength=best_pair.semantic_strength,
        endpoint_strength=best_pair.endpoint_strength,
        owner_certainty=owner_score.root_score,
        target_certainty=target_score.root_score,
        ambiguity_penalty=ambiguity_penalty,
        owner_loop_index=owner_loop_index,
        owner_chain_index=owner_chain_index,
        target_loop_index=target_loop_index,
        target_chain_index=target_chain_index,
        owner_loop_kind=owner_loop.kind,
        target_loop_kind=target_loop.kind,
        owner_role=owner_effective_role,
        target_role=target_effective_role,
        owner_transition=graph.describe_chain_transition(owner_patch_id, owner_chain),
        target_transition=graph.describe_chain_transition(target_patch_id, target_chain),
        reasons=reasons,
    )


def _match_seam_relation_secondary_pairs(
    graph: PatchGraph,
    patch_a_id: int,
    patch_b_id: int,
) -> tuple[tuple[ChainRef, ChainRef], ...]:
    """Matched secondary seam carriers for one undirected patch edge."""
    owner_refs = _iter_neighbor_chains(graph, patch_a_id, patch_b_id)
    target_refs = _iter_neighbor_chains(graph, patch_b_id, patch_a_id)
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
                        owner_ref=(patch_a_id, owner_ref.loop_index, owner_ref.chain_index),
                        owner_chain=owner_chain,
                        target_ref=(patch_b_id, target_ref.loop_index, target_ref.chain_index),
                        target_chain=target_chain,
                        shared_vert_count=shared_vert_count,
                    ),
                )
            )

    pair_candidates.sort(
        key=lambda item: (item.score, item.representative_length),
        reverse=True,
    )

    matched_owner_refs = set()
    matched_target_refs = set()
    matched_pairs: list[tuple[ChainRef, ChainRef]] = []
    for candidate in pair_candidates:
        match = candidate.match
        if match.owner_ref in matched_owner_refs or match.target_ref in matched_target_refs:
            continue
        matched_owner_refs.add(match.owner_ref)
        matched_target_refs.add(match.target_ref)
        matched_pairs.append((match.owner_ref, match.target_ref))

    return tuple(matched_pairs)


def _build_seam_relation_profile(
    solve_view: SolveView,
    candidate: AttachmentCandidate,
    max_shared_length: float,
    inherited_role_map: dict[ChainRef, tuple[FrameRole, int]],
) -> SeamRelationProfile:
    graph = solve_view.graph
    edge_key = _patch_pair_key(candidate.owner_patch_id, candidate.target_patch_id)
    owner_refs = solve_view.iter_attachment_neighbor_chains(candidate.owner_patch_id, candidate.target_patch_id)
    target_refs = solve_view.iter_attachment_neighbor_chains(candidate.target_patch_id, candidate.owner_patch_id)
    ranked_pairs = _rank_chain_pairs(
        graph,
        candidate.owner_patch_id,
        owner_refs,
        candidate.target_patch_id,
        target_refs,
        inherited_role_map,
    )

    primary_pair = (
        (candidate.owner_patch_id, candidate.owner_loop_index, candidate.owner_chain_index),
        (candidate.target_patch_id, candidate.target_loop_index, candidate.target_chain_index),
    )
    primary_pair_key = frozenset(primary_pair)

    strongest_secondary_strength = 0.0
    for pair_selection, _ in ranked_pairs:
        pair_refs = frozenset((
            (candidate.owner_patch_id, pair_selection.owner_ref.loop_index, pair_selection.owner_ref.chain_index),
            (candidate.target_patch_id, pair_selection.target_ref.loop_index, pair_selection.target_ref.chain_index),
        ))
        if pair_refs == primary_pair_key:
            continue
        strongest_secondary_strength = pair_selection.pair_strength
        break

    secondary_pairs = tuple(
        pair
        for pair in _match_seam_relation_secondary_pairs(graph, edge_key[0], edge_key[1])
        if frozenset(pair) != primary_pair_key
    )
    support_denominator = max(len(owner_refs), len(target_refs), 1)
    support_asymmetry = _clamp01(abs(len(owner_refs) - len(target_refs)) / support_denominator)
    seam_norm = 1.0 if max_shared_length <= 0.0 else _clamp01(candidate.seam_length / max_shared_length)
    ingress_preference = _clamp01(
        (0.45 * candidate.best_pair_strength)
        + (0.35 * seam_norm)
        + (0.20 * candidate.frame_continuation)
    )

    return SeamRelationProfile(
        edge_key=edge_key,
        primary_pair=primary_pair,
        secondary_pairs=secondary_pairs,
        secondary_pair_count=len(secondary_pairs),
        pair_strength_gap=_clamp01(candidate.best_pair_strength - strongest_secondary_strength),
        is_closure_like=(len(secondary_pairs) > 0),
        support_asymmetry=support_asymmetry,
        ingress_preference=ingress_preference,
    )


def build_solver_graph(
    graph: PatchGraph,
    straighten_enabled: bool = False,
) -> SolverGraph:
    solver_graph = SolverGraph()
    solve_view = _build_solve_view(graph)
    inherited_role_map = build_neighbor_inherited_roles(graph) if straighten_enabled else {}

    max_area = max((node.area for node in graph.nodes.values()), default=0.0)
    for patch_id, node in graph.nodes.items():
        solver_graph.patch_scores[patch_id] = _build_patch_certainty(node, solve_view, max_area)

    solver_graph.max_shared_length = max((edge.shared_length for edge in graph.edges.values()), default=0.0)
    for seam in graph.edges.values():
        forward = _build_attachment_candidate(
            solve_view,
            seam.patch_a_id,
            seam.patch_b_id,
            seam,
            solver_graph.patch_scores,
            solver_graph.max_shared_length,
            inherited_role_map,
        )
        backward = _build_attachment_candidate(
            solve_view,
            seam.patch_b_id,
            seam.patch_a_id,
            seam,
            solver_graph.patch_scores,
            solver_graph.max_shared_length,
            inherited_role_map,
        )
        for candidate in (forward, backward):
            if candidate is None:
                continue
            solver_graph.candidates.append(candidate)
            solver_graph.candidates_by_owner.setdefault(candidate.owner_patch_id, []).append(candidate)

    for candidate_list in solver_graph.candidates_by_owner.values():
        candidate_list.sort(key=lambda candidate: candidate.score, reverse=True)
    solver_graph.candidates.sort(key=lambda candidate: (candidate.owner_patch_id, -candidate.score, candidate.target_patch_id))
    edge_candidate_map = _build_quilt_edge_candidate_map(solver_graph, set(graph.nodes.keys()))
    solver_graph.seam_relation_by_edge = {
        edge_key: _build_seam_relation_profile(
            solve_view,
            candidate,
            solver_graph.max_shared_length,
            inherited_role_map,
        )
        for edge_key, candidate in edge_candidate_map.items()
    }
    components_result = _build_solve_components(graph, solver_graph.candidates)
    solver_graph.solve_components = components_result.components
    solver_graph.component_by_patch = components_result.component_by_patch
    return solver_graph


def choose_best_root(remaining_patch_ids: set[int], solver_graph: SolverGraph) -> Optional[int]:
    valid_patch_ids = [
        patch_id
        for patch_id in remaining_patch_ids
        if solver_graph.patch_scores.get(patch_id) and solver_graph.patch_scores[patch_id].local_solvable
    ]
    if not valid_patch_ids:
        return None
    return max(
        valid_patch_ids,
        key=lambda patch_id: (
            solver_graph.patch_scores[patch_id].root_score,
            solver_graph.patch_scores[patch_id].h_count + solver_graph.patch_scores[patch_id].v_count,
            -solver_graph.patch_scores[patch_id].free_count,
            patch_id,
        ),
    )


def plan_solve_phase1(
    graph: PatchGraph,
    solver_graph: Optional[SolverGraph] = None,
    propagate_threshold: float = EDGE_PROPAGATE_MIN,
    weak_threshold: float = EDGE_WEAK_MIN,
) -> SolvePlan:
    solver_graph = solver_graph or build_solver_graph(graph)
    remaining_patch_ids = set(graph.nodes.keys())
    quilts: list[QuiltPlan] = []
    skipped_patch_ids: list[int] = []
    queue_index = 0

    while remaining_patch_ids:
        root_patch_id = choose_best_root(remaining_patch_ids, solver_graph)
        if root_patch_id is None:
            skipped_patch_ids.extend(sorted(remaining_patch_ids))
            break

        root_score = solver_graph.patch_scores[root_patch_id].root_score
        component_index = solver_graph.component_by_patch.get(root_patch_id, -1)
        quilt = QuiltPlan(
            quilt_index=len(quilts),
            component_index=component_index,
            root_patch_id=root_patch_id,
            root_score=root_score,
        )

        solved_patch_ids: set[int] = set()
        frontier_heap = []

        def enqueue_patch_candidates(patch_id: int) -> None:
            nonlocal queue_index
            for candidate in solver_graph.candidates_by_owner.get(patch_id, []):
                if candidate.target_patch_id in solved_patch_ids:
                    continue
                if candidate.target_patch_id not in remaining_patch_ids:
                    continue
                heappush(frontier_heap, (-candidate.score, queue_index, candidate))
                queue_index += 1

        solved_patch_ids.add(root_patch_id)
        remaining_patch_ids.remove(root_patch_id)
        quilt.solved_patch_ids.append(root_patch_id)
        quilt.steps.append(QuiltStep(step_index=0, patch_id=root_patch_id, is_root=True))
        enqueue_patch_candidates(root_patch_id)

        while frontier_heap:
            best_score, _, candidate = frontier_heap[0]
            if -best_score < propagate_threshold:
                deferred = []
                rejected = []
                seen_keys = set()
                while frontier_heap:
                    _, _, pending = heappop(frontier_heap)
                    if pending.target_patch_id in solved_patch_ids:
                        continue
                    if pending.target_patch_id not in remaining_patch_ids:
                        continue
                    key = (pending.owner_patch_id, pending.target_patch_id)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    if pending.score >= weak_threshold:
                        deferred.append(pending)
                    else:
                        rejected.append(pending)
                deferred.sort(key=lambda item: item.score, reverse=True)
                rejected.sort(key=lambda item: item.score, reverse=True)
                quilt.deferred_candidates = deferred
                quilt.rejected_candidates = rejected
                quilt.stop_reason = QuiltStopReason.FRONTIER_BELOW_THRESHOLD
                break

            _, _, candidate = heappop(frontier_heap)
            if candidate.target_patch_id in solved_patch_ids:
                continue
            if candidate.target_patch_id not in remaining_patch_ids:
                continue

            solved_patch_ids.add(candidate.target_patch_id)
            remaining_patch_ids.remove(candidate.target_patch_id)
            quilt.solved_patch_ids.append(candidate.target_patch_id)
            quilt.steps.append(
                QuiltStep(
                    step_index=len(quilt.steps),
                    patch_id=candidate.target_patch_id,
                    is_root=False,
                    incoming_candidate=candidate,
                )
            )
            enqueue_patch_candidates(candidate.target_patch_id)

        if quilt.stop_reason == QuiltStopReason.UNSET:
            quilt.stop_reason = QuiltStopReason.FRONTIER_EXHAUSTED
        quilt = _apply_quilt_closure_cut_recommendations(graph, solver_graph, quilt)
        quilts.append(quilt)

    quilts = _attach_quilt_seam_relation_profiles(solver_graph, quilts)


    return SolvePlan(
        quilts=quilts,
        skipped_patch_ids=skipped_patch_ids,
        propagate_threshold=propagate_threshold,
        weak_threshold=weak_threshold,
    )

def _attach_quilt_seam_relation_profiles(
    solver_graph: SolverGraph,
    quilts: list[QuiltPlan],
) -> list[QuiltPlan]:
    for quilt in quilts:
        quilt_patch_ids = set(quilt.solved_patch_ids)
        quilt_patch_ids.add(quilt.root_patch_id)
        quilt.seam_relation_by_edge = {
            edge_key: profile
            for edge_key, profile in solver_graph.seam_relation_by_edge.items()
            if edge_key[0] in quilt_patch_ids and edge_key[1] in quilt_patch_ids
        }
    return quilts

def _choose_root_loop(node: PatchNode) -> int:
    best_loop_index = -1
    best_score = (-1, -1, -1)
    for loop_index, boundary_loop in enumerate(node.boundary_loops):
        frame_count = sum(1 for chain in boundary_loop.chains if chain.frame_role in {FrameRole.H_FRAME, FrameRole.V_FRAME})
        corner_count = len(boundary_loop.corners)
        derived_bonus = 1 if frame_count <= 0 and corner_count >= 4 else 0
        if frame_count <= 0 and not derived_bonus:
            continue
        outer_bonus = 1 if boundary_loop.kind == LoopKind.OUTER else 0
        score = (outer_bonus, frame_count, derived_bonus)
        if score > best_score:
            best_score = score
            best_loop_index = loop_index
    return best_loop_index


def _attachment_candidate_preference_key(candidate: AttachmentCandidate) -> AttachmentCandidatePreference:
    return AttachmentCandidatePreference(
        score=candidate.score,
        frame_continuation=candidate.frame_continuation,
        endpoint_bridge=candidate.endpoint_bridge,
        endpoint_strength=candidate.endpoint_strength,
        best_pair_strength=candidate.best_pair_strength,
        seam_norm=candidate.seam_norm,
    )


def _select_preferred_edge_candidate(
    current: Optional[AttachmentCandidate],
    candidate: AttachmentCandidate,
) -> AttachmentCandidate:
    if current is None:
        return candidate
    current_key = _attachment_candidate_preference_key(current)
    candidate_key = _attachment_candidate_preference_key(candidate)
    return candidate if candidate_key > current_key else current


def _count_chain_endpoint_support(
    graph: PatchGraph,
    patch_id: int,
    loop_index: int,
    chain_index: int,
    chain_role: FrameRole,
) -> EndpointSupportStats:
    fixed_endpoint_count = 0
    same_axis_endpoint_count = 0
    free_touched_endpoint_count = 0

    for endpoint_label in ('start', 'end'):
        endpoint_ctx = _get_chain_endpoint_context(graph, patch_id, loop_index, chain_index, endpoint_label)
        if endpoint_ctx is None:
            continue
        neighbor_roles = []
        for neighbor_loop_index, neighbor_chain_index in endpoint_ctx.neighbors:
            neighbor_chain = graph.get_chain(patch_id, neighbor_loop_index, neighbor_chain_index)
            if neighbor_chain is None:
                continue
            neighbor_roles.append(neighbor_chain.frame_role)

        if any(role in {FrameRole.H_FRAME, FrameRole.V_FRAME} for role in neighbor_roles):
            fixed_endpoint_count += 1
        if chain_role in {FrameRole.H_FRAME, FrameRole.V_FRAME} and any(role == chain_role for role in neighbor_roles):
            same_axis_endpoint_count += 1
        if any(role == FrameRole.FREE for role in neighbor_roles):
            free_touched_endpoint_count += 1

    return EndpointSupportStats(
        fixed_endpoint_count=fixed_endpoint_count,
        same_axis_endpoint_count=same_axis_endpoint_count,
        free_touched_endpoint_count=free_touched_endpoint_count,
    )


def _chain_polyline_length(chain: Optional[BoundaryChain]) -> float:
    if chain is None or len(chain.vert_cos) < 2:
        return 0.0
    return sum(
        (chain.vert_cos[index + 1] - chain.vert_cos[index]).length
        for index in range(len(chain.vert_cos) - 1)
    )

def _find_seam_junction_hv_strength(graph, seam, patch_a_id, patch_b_id):
    """Ищет сильнейшую H/V chain pair на junction vertices seam.
    
    Не требует direct neighbor — только shared vertex на seam.
    Возвращает (frame_continuation, owner_loop, owner_chain, target_loop, target_chain) или None.
    """
    shared_verts = set(seam.shared_vert_indices)
    node_a = graph.nodes.get(patch_a_id)
    node_b = graph.nodes.get(patch_b_id)
    if node_a is None or node_b is None:
        return None

    def _hv_chains_touching(node, vert_set):
        results = []
        for li, loop in enumerate(node.boundary_loops):
            if loop.kind != LoopKind.OUTER:
                continue
            for ci, chain in enumerate(loop.chains):
                if chain.frame_role not in (FrameRole.H_FRAME, FrameRole.V_FRAME):
                    continue
                touch = set()
                if chain.start_vert_index in vert_set:
                    touch.add(chain.start_vert_index)
                if chain.end_vert_index in vert_set:
                    touch.add(chain.end_vert_index)
                if touch:
                    results.append((li, ci, chain, touch))
        return results

    chains_a = _hv_chains_touching(node_a, shared_verts)
    chains_b = _hv_chains_touching(node_b, shared_verts)
    
    best = None
    best_strength = -1.0
    for li_a, ci_a, ca, verts_a in chains_a:
        for li_b, ci_b, cb, verts_b in chains_b:
            if not (verts_a & verts_b):
                continue
            strength = _frame_continuation_strength(ca.frame_role, cb.frame_role)
            if strength > best_strength:
                best_strength = strength
                best = (strength, li_a, ci_a, li_b, ci_b)
    
    return best

def _closure_cut_support_class(
    fixed_endpoint_count: int,
    same_axis_endpoint_count: int,
    free_touched_endpoint_count: int,
) -> str:
    if fixed_endpoint_count >= 4 and same_axis_endpoint_count >= 2 and free_touched_endpoint_count == 0:
        return 'rigid'
    if fixed_endpoint_count >= 3 and same_axis_endpoint_count >= 1 and free_touched_endpoint_count <= 1:
        return 'stable'
    if fixed_endpoint_count >= 2 and free_touched_endpoint_count <= 2:
        return 'mixed'
    return 'weak'


def _closure_cut_support_rank(support_class: str) -> int:
    return {
        'weak': 0,
        'mixed': 1,
        'stable': 2,
        'rigid': 3,
    }.get(support_class, 0)


def _closure_cut_support_label(score: float) -> str:
    if score >= 0.80:
        return 'rigid'
    if score >= 0.62:
        return 'stable'
    if score >= 0.45:
        return 'mixed'
    return 'weak'

def _dihedral_cut_preference(graph, candidate):
    """Preference for cutting this seam based on dihedral convexity.

    Concave (inner corner) → high preference (1.0) = natural UV break.
    Convex (outer corner) → low preference (0.0) = prefer UV continuity.
    Neutral / non-PATCH / no chain → 0.5 (no influence).
    """
    owner_chain = graph.get_chain(
        candidate.owner_patch_id,
        candidate.owner_loop_index,
        candidate.owner_chain_index,
    )
    if owner_chain is None:
        return 0.5

    convexity = owner_chain.dihedral_convexity
    return max(0.0, min(1.0, 0.5 - 0.5 * convexity))

def _build_closure_cut_heuristic(
    graph: PatchGraph,
    candidate: AttachmentCandidate,
) -> ClosureCutHeuristic:
    owner_support = _count_chain_endpoint_support(
        graph,
        candidate.owner_patch_id,
        candidate.owner_loop_index,
        candidate.owner_chain_index,
        candidate.owner_role,
    )
    target_support = _count_chain_endpoint_support(
        graph,
        candidate.target_patch_id,
        candidate.target_loop_index,
        candidate.target_chain_index,
        candidate.target_role,
    )

    fixed_endpoint_count = owner_support.fixed_endpoint_count + target_support.fixed_endpoint_count
    same_axis_endpoint_count = owner_support.same_axis_endpoint_count + target_support.same_axis_endpoint_count
    free_touched_endpoint_count = owner_support.free_touched_endpoint_count + target_support.free_touched_endpoint_count
    fixed_ratio = fixed_endpoint_count / 4.0
    same_axis_ratio = same_axis_endpoint_count / 4.0
    free_touch_ratio = free_touched_endpoint_count / 4.0
    support_class = _closure_cut_support_class(
        fixed_endpoint_count,
        same_axis_endpoint_count,
        free_touched_endpoint_count,
    )
    owner_chain = graph.get_chain(
        candidate.owner_patch_id,
        candidate.owner_loop_index,
        candidate.owner_chain_index,
    )
    target_chain = graph.get_chain(
        candidate.target_patch_id,
        candidate.target_loop_index,
        candidate.target_chain_index,
    )
    owner_chain_length = _chain_polyline_length(owner_chain)
    target_chain_length = _chain_polyline_length(target_chain)
    if owner_chain_length > 0.0 and target_chain_length > 0.0:
        representative_chain_length = min(owner_chain_length, target_chain_length)
    else:
        representative_chain_length = max(owner_chain_length, target_chain_length)
    dihedral_pref = _dihedral_cut_preference(graph, candidate)
    score = _clamp01(
        CLOSURE_CUT_WEIGHT_FRAME_CONT * candidate.frame_continuation
        + CLOSURE_CUT_WEIGHT_ENDPOINT_BRIDGE * candidate.endpoint_bridge
        + CLOSURE_CUT_WEIGHT_ENDPOINT_STR * candidate.endpoint_strength
        + CLOSURE_CUT_WEIGHT_SEAM_NORM * candidate.seam_norm
        + CLOSURE_CUT_WEIGHT_FIXED_RATIO * fixed_ratio
        + CLOSURE_CUT_WEIGHT_SAME_AXIS * same_axis_ratio
        + CLOSURE_CUT_WEIGHT_FREE_TOUCH * (1.0 - free_touch_ratio)
        + CLOSURE_CUT_WEIGHT_DIHEDRAL * dihedral_pref
    )
    reasons = (
        f"fc={candidate.frame_continuation:.2f}",
        f"bridge={candidate.endpoint_bridge:.2f}",
        f"ep={candidate.endpoint_strength:.2f}",
        f"class={support_class}",
        f"rigid={fixed_endpoint_count}/4",
        f"axis={same_axis_endpoint_count}/4",
        f"free={free_touched_endpoint_count}/4",
        f"len={representative_chain_length:.4f}",
        f"dihedral={dihedral_pref:.2f}",
    )
    return ClosureCutHeuristic(
        edge_key=_patch_pair_key(candidate.owner_patch_id, candidate.target_patch_id),
        candidate=candidate,
        score=score,
        support_label=_closure_cut_support_label(score),
        support_class=support_class,
        fixed_endpoint_count=fixed_endpoint_count,
        same_axis_endpoint_count=same_axis_endpoint_count,
        free_touched_endpoint_count=free_touched_endpoint_count,
        representative_chain_length=representative_chain_length,
        reasons=reasons,
    )


def _build_quilt_edge_candidate_map(
    solver_graph: SolverGraph,
    quilt_patch_ids: set[int],
) -> dict[PatchEdgeKey, AttachmentCandidate]:
    edge_candidate_map: dict[PatchEdgeKey, AttachmentCandidate] = {}
    for candidate in solver_graph.candidates:
        if candidate.owner_patch_id not in quilt_patch_ids or candidate.target_patch_id not in quilt_patch_ids:
            continue
        edge_key = _patch_pair_key(candidate.owner_patch_id, candidate.target_patch_id)
        edge_candidate_map[edge_key] = _select_preferred_edge_candidate(edge_candidate_map.get(edge_key), candidate)
    return edge_candidate_map


def _analyze_quilt_closure_cuts(
    graph: PatchGraph,
    solver_graph: SolverGraph,
    quilt_plan: QuiltPlan,
) -> tuple[QuiltClosureCutAnalysis, ...]:
    quilt_patch_ids = set(quilt_plan.solved_patch_ids)
    quilt_patch_ids.add(quilt_plan.root_patch_id)
    tree_edges = _build_quilt_tree_edges(quilt_plan)
    patch_tree_adjacency = _build_patch_tree_adjacency(quilt_plan)
    edge_candidate_map = _build_quilt_edge_candidate_map(solver_graph, quilt_patch_ids)
    non_tree_edges = sorted(
        edge_key
        for edge_key in edge_candidate_map.keys()
        if edge_key not in tree_edges
    )

    analyses = []
    for edge_key in non_tree_edges:
        patch_path = _find_patch_tree_path(patch_tree_adjacency, edge_key[0], edge_key[1])
        if len(patch_path) < 2:
            continue
        cycle_edge_keys = [
            _patch_pair_key(patch_path[index], patch_path[index + 1])
            for index in range(len(patch_path) - 1)
        ]
        cycle_edge_keys.append(edge_key)

        cycle_edges = []
        for cycle_edge_key in cycle_edge_keys:
            cycle_candidate = edge_candidate_map.get(cycle_edge_key)
            if cycle_candidate is None:
                continue
            cycle_edges.append(_build_closure_cut_heuristic(graph, cycle_candidate))
        if not cycle_edges:
            continue

        current_cut = next((item for item in cycle_edges if item.edge_key == edge_key), None)
        if current_cut is None:
            continue
        recommended_cut = max(
            cycle_edges,
            key=lambda item: (
                _closure_cut_support_rank(item.support_class),
                item.same_axis_endpoint_count,
                item.fixed_endpoint_count,
                -item.free_touched_endpoint_count,
                -item.representative_chain_length,
                item.score,
                item.edge_key,
            ),
        )
        analyses.append(
            QuiltClosureCutAnalysis(
                current_cut=current_cut,
                recommended_cut=recommended_cut,
                path_patch_ids=tuple(patch_path),
                cycle_edges=tuple(sorted(
                    cycle_edges,
                    key=lambda item: (
                        item.edge_key != recommended_cut.edge_key,
                        item.edge_key != current_cut.edge_key,
                        -item.score,
                        item.edge_key,
                    ),
                )),
            )
        )

    return tuple(analyses)


def _apply_quilt_closure_cut_recommendations(
    graph: PatchGraph,
    solver_graph: SolverGraph,
    quilt_plan: QuiltPlan,
) -> QuiltPlan:
    if len(quilt_plan.steps) <= 2:
        return quilt_plan

    current_quilt = quilt_plan
    seen_tree_signatures = set()

    for _ in range(max(2, len(quilt_plan.steps) + 1)):
        current_tree_edges = frozenset(_build_quilt_tree_edges(current_quilt))
        if current_tree_edges in seen_tree_signatures:
            break
        seen_tree_signatures.add(current_tree_edges)

        analyses = _analyze_quilt_closure_cuts(graph, solver_graph, current_quilt)
        swap_analyses = [
            analysis
            for analysis in analyses
            if analysis.current_cut.edge_key != analysis.recommended_cut.edge_key
        ]
        if not swap_analyses:
            break

        forbidden_edge_keys = {analysis.recommended_cut.edge_key for analysis in swap_analyses}
        rebuilt_quilt = _rebuild_quilt_steps_with_forbidden_edges(
            current_quilt,
            solver_graph,
            forbidden_edge_keys,
        )
        if rebuilt_quilt is None:
            break

        rebuilt_tree_edges = _build_quilt_tree_edges(rebuilt_quilt)
        if rebuilt_tree_edges == _build_quilt_tree_edges(current_quilt):
            break

        swap_labels = ", ".join(
            f"{analysis.current_cut.edge_key[0]}-{analysis.current_cut.edge_key[1]}"
            f"->{analysis.recommended_cut.edge_key[0]}-{analysis.recommended_cut.edge_key[1]}"
            for analysis in swap_analyses
        )
        trace_console(
            f"[CFTUV][Plan] Quilt {quilt_plan.quilt_index}: closure cut swap {swap_labels}"
        )
        current_quilt = rebuilt_quilt

    return current_quilt


def _restore_original_quilt_plan(quilt_plan: QuiltPlan) -> Optional[QuiltPlan]:
    if not quilt_plan.original_steps:
        return None
    return replace(
        quilt_plan,
        solved_patch_ids=list(quilt_plan.original_solved_patch_ids),
        steps=list(quilt_plan.original_steps),
        original_solved_patch_ids=[],
        original_steps=[],
    )
