from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from mathutils import Vector

try:
    from .model import (
        BoundaryChain,
        BoundaryCorner,
        ChainNeighborKind,
        ChainRef,
        FrameRole,
        LoopKind,
        PatchEdgeKey,
        PatchGraph,
        PatchNode,
        PlacementSourceKind,
    )
    from .solve_records import (
        CHAIN_FRONTIER_THRESHOLD,
        ChainAnchor,
        CornerScoringHints,
        FrontierLocalScoreDetails,
        FrontierRank,
        FrontierRankBreakdown,
        FrontierTopologyFacts,
        PatchScoringContext,
        PatchShapeProfile,
        SeamRelationProfile,
        _patch_pair_key,
    )
except ImportError:
    from model import (
        BoundaryChain,
        BoundaryCorner,
        ChainNeighborKind,
        ChainRef,
        FrameRole,
        LoopKind,
        PatchEdgeKey,
        PatchGraph,
        PatchNode,
        PlacementSourceKind,
    )
    from solve_records import (
        CHAIN_FRONTIER_THRESHOLD,
        ChainAnchor,
        CornerScoringHints,
        FrontierLocalScoreDetails,
        FrontierRank,
        FrontierRankBreakdown,
        FrontierTopologyFacts,
        PatchScoringContext,
        PatchShapeProfile,
        SeamRelationProfile,
        _patch_pair_key,
    )

if TYPE_CHECKING:
    try:
        from .frontier_state import FrontierRuntimePolicy
    except ImportError:
        from frontier_state import FrontierRuntimePolicy


def _is_allowed_quilt_edge(
    allowed_tree_edges: set[PatchEdgeKey],
    patch_a_id: int,
    patch_b_id: int,
) -> bool:
    return _patch_pair_key(patch_a_id, patch_b_id) in allowed_tree_edges


def _is_orthogonal_hv_pair(role_a: FrameRole, role_b: FrameRole) -> bool:
    return {role_a, role_b} == {FrameRole.H_FRAME, FrameRole.V_FRAME}


def _cf_chain_total_length(chain: BoundaryChain, final_scale: float) -> float:
    if len(chain.vert_cos) < 2:
        return 0.0
    return sum(
        (chain.vert_cos[index + 1] - chain.vert_cos[index]).length
        for index in range(len(chain.vert_cos) - 1)
    ) * final_scale


def _cf_bootstrap_runtime_score_caches(runtime_policy: "FrontierRuntimePolicy") -> None:
    runtime_policy._outer_chain_count_by_patch.clear()
    runtime_policy._frame_chain_count_by_patch.clear()
    runtime_policy._closure_pair_count_by_patch.clear()
    runtime_policy._shape_profile_by_patch.clear()

    for patch_id, node in runtime_policy.graph.nodes.items():
        outer_chain_count = 0
        frame_chain_count = 0
        for boundary_loop in node.boundary_loops:
            if boundary_loop.kind != LoopKind.OUTER:
                continue
            outer_chain_count += len(boundary_loop.chains)
            frame_chain_count += sum(
                1
                for chain in boundary_loop.chains
                if chain.frame_role in {FrameRole.H_FRAME, FrameRole.V_FRAME}
            )
        runtime_policy._outer_chain_count_by_patch[patch_id] = outer_chain_count
        runtime_policy._frame_chain_count_by_patch[patch_id] = frame_chain_count

    for chain_ref in runtime_policy.closure_pair_refs:
        patch_id = chain_ref[0]
        runtime_policy._closure_pair_count_by_patch[patch_id] = runtime_policy._closure_pair_count_by_patch.get(patch_id, 0) + 1

    for patch_id, node in runtime_policy.graph.nodes.items():
        runtime_policy._shape_profile_by_patch[patch_id] = _cf_build_patch_shape_profile(patch_id, node, runtime_policy)


def _cf_estimate_downstream_anchor_count(
    chain_ref: ChainRef,
    chain: BoundaryChain,
    graph: PatchGraph,
    runtime_policy: "FrontierRuntimePolicy",
) -> int:
    count = 0
    patch_id, loop_index, chain_index = chain_ref
    node = graph.nodes.get(patch_id)
    if node is None or loop_index >= len(node.boundary_loops):
        return 0
    boundary_loop = node.boundary_loops[loop_index]
    for corner in boundary_loop.corners:
        neighbor_idx = -1
        if corner.next_chain_index == chain_index:
            neighbor_idx = corner.prev_chain_index
        elif corner.prev_chain_index == chain_index:
            neighbor_idx = corner.next_chain_index
        if neighbor_idx >= 0:
            ref = (patch_id, loop_index, neighbor_idx)
            if runtime_policy.is_chain_available(ref):
                count += 1
    for vert_idx in (chain.start_vert_index, chain.end_vert_index):
        if vert_idx < 0:
            continue
        for ref in runtime_policy._vert_to_pool_refs.get(vert_idx, ()):
            if ref[0] != patch_id and runtime_policy.is_chain_available(ref):
                count += 1
    return count


def _cf_count_hv_adjacent_endpoints(
    graph: PatchGraph,
    chain_ref: ChainRef,
    runtime_policy: Optional["FrontierRuntimePolicy"] = None,
    effective_role: Optional[FrameRole] = None,
) -> int:
    chain = graph.get_chain(*chain_ref)
    if chain is None:
        return 0

    if effective_role is not None:
        chain_role = effective_role
    elif runtime_policy is not None:
        chain_role = runtime_policy.effective_placement_role(chain_ref, chain)
    else:
        chain_role = chain.frame_role
    _strong = {FrameRole.H_FRAME, FrameRole.V_FRAME, FrameRole.STRAIGHTEN}
    if chain_role not in _strong:
        return 0

    endpoint_neighbors = graph.get_chain_endpoint_neighbors(chain_ref[0], chain_ref[1], chain_ref[2])
    hv_adjacency = 0
    for endpoint_label in ("start", "end"):
        for neighbor_loop_index, neighbor_chain_index in endpoint_neighbors.get(endpoint_label, ()):
            neighbor_ref = (chain_ref[0], neighbor_loop_index, neighbor_chain_index)
            neighbor_chain = graph.get_chain(*neighbor_ref)
            if neighbor_chain is None:
                continue
            neighbor_role = (
                runtime_policy.resolved_placement_role(neighbor_ref, neighbor_chain)
                if runtime_policy is not None else
                neighbor_chain.frame_role
            )
            if neighbor_role in _strong:
                hv_adjacency += 1
                break
    return hv_adjacency


def _cf_preview_would_be_connected(
    chain_ref: ChainRef,
    chain: BoundaryChain,
    runtime_policy: "FrontierRuntimePolicy",
    graph: PatchGraph,
    effective_role: Optional[FrameRole] = None,
) -> bool:
    _strong = {FrameRole.H_FRAME, FrameRole.V_FRAME, FrameRole.STRAIGHTEN}
    chain_role = effective_role if effective_role is not None else runtime_policy.effective_placement_role(chain_ref, chain)
    if chain_role not in _strong:
        return True

    patch_id, loop_index, chain_index = chain_ref
    if runtime_policy.placed_in_patch(patch_id) == 0:
        return True

    node = graph.nodes.get(patch_id)
    if node is None or loop_index >= len(node.boundary_loops):
        return True
    boundary_loop = node.boundary_loops[loop_index]
    # ARCHITECTURAL_DEBT: F3_LOOP_PREVNEXT
    # Loop-neighbor lookup is still derived on demand from loop ordering rather
    # than explicit ChainUse prev/next links. See docs/architectural_debt.md.
    for neighbor_idx in boundary_loop.oriented_neighbor_chain_indices(chain_index):
        neighbor_ref = (patch_id, loop_index, neighbor_idx)
        if neighbor_ref not in runtime_policy.placed_chain_refs:
            continue
        neighbor_chain = boundary_loop.chains[neighbor_idx]
        neighbor_role = runtime_policy.resolved_placement_role(neighbor_ref, neighbor_chain)
        if neighbor_role in _strong:
            return True

    for vert_idx in (chain.start_vert_index, chain.end_vert_index):
        if vert_idx < 0:
            continue
        for other_ref in runtime_policy._vert_to_pool_refs.get(vert_idx, ()):
            if other_ref in runtime_policy.placed_chain_refs:
                other_chain = graph.get_chain(*other_ref)
                if other_chain:
                    other_role = runtime_policy.resolved_placement_role(other_ref, other_chain)
                    if other_role in _strong:
                        return True

    return False


def _cf_role_tier(
    chain_ref: ChainRef,
    chain: BoundaryChain,
    node: PatchNode,
    graph: PatchGraph,
    quilt_patch_ids: set[int],
    allowed_tree_edges: set[PatchEdgeKey],
    runtime_policy: Optional["FrontierRuntimePolicy"] = None,
    effective_role: Optional[FrameRole] = None,
) -> tuple[int, str]:
    # Check non-native roles: STRAIGHTEN, inherited H/V, or regular FREE.
    if chain.frame_role not in {FrameRole.H_FRAME, FrameRole.V_FRAME}:
        if runtime_policy is not None:
            eff_role = effective_role if effective_role is not None else runtime_policy.effective_placement_role(chain_ref, chain)
            if eff_role == FrameRole.STRAIGHTEN:
                # STRAIGHTEN: strong role from BAND shape classification.
                # Between native H/V (tier 3) and FREE (tier 0).
                return 2, 'straighten_band_side'
            if runtime_policy.band_cap_role(chain_ref) in {FrameRole.H_FRAME, FrameRole.V_FRAME}:
                return 2, 'band_cap_spine'
            if eff_role in {FrameRole.H_FRAME, FrameRole.V_FRAME}:
                # Inherited role: stronger than free, weaker than true H/V
                return 2, 'free_inherited_hv'
        if len(chain.vert_cos) <= 2:
            return 1, 'free_bridge'
        return 0, 'free_regular'

    if chain.is_corner_split:
        return 2, 'hv_corner_split'

    if (
        chain.neighbor_kind == ChainNeighborKind.PATCH
        and chain.neighbor_patch_id in quilt_patch_ids
        and _is_allowed_quilt_edge(allowed_tree_edges, chain_ref[0], chain.neighbor_patch_id)
    ):
        neighbor_node = graph.nodes.get(chain.neighbor_patch_id)
        if neighbor_node is not None and neighbor_node.patch_type == node.patch_type:
            return 5, 'hv_cross_patch_same_type'
        return 4, 'hv_cross_patch_mixed_type'

    return 3, 'hv_regular'


def _cf_clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _cf_chain_polyline_length_3d(chain: BoundaryChain) -> float:
    if len(chain.vert_cos) < 2:
        return 0.0
    return sum(
        (chain.vert_cos[index + 1] - chain.vert_cos[index]).length
        for index in range(len(chain.vert_cos) - 1)
    )


def _cf_patch_shape_backbone_bias(shape_profile: Optional[PatchShapeProfile]) -> float:
    if shape_profile is None:
        return 0.0
    return _cf_clamp01(
        (0.45 * shape_profile.rectilinearity)
        + (0.35 * shape_profile.frame_dominance)
        + (0.20 * shape_profile.elongation)
    )


def _cf_patch_shape_closure_sensitivity(shape_profile: Optional[PatchShapeProfile]) -> float:
    if shape_profile is None:
        return 0.0
    return _cf_clamp01(
        (0.45 * shape_profile.hole_ratio)
        + (0.35 * shape_profile.seam_multiplicity_hint)
        + (0.20 * shape_profile.elongation)
    )


def _cf_build_patch_shape_profile(
    patch_id: int,
    node: PatchNode,
    runtime_policy: "FrontierRuntimePolicy",
) -> PatchShapeProfile:
    outer_points: list[Vector] = []
    outer_chain_count = 0
    hole_chain_count = 0
    total_outer_length = 0.0
    hv_outer_length = 0.0
    h_outer_length = 0.0
    v_outer_length = 0.0
    patch_neighbor_chain_count = 0
    patch_neighbor_ids: set[int] = set()

    for boundary_loop in node.boundary_loops:
        if boundary_loop.kind == LoopKind.OUTER:
            outer_points.extend(boundary_loop.vert_cos)
            for chain in boundary_loop.chains:
                outer_chain_count += 1
                chain_length = _cf_chain_polyline_length_3d(chain)
                total_outer_length += chain_length
                if chain.frame_role == FrameRole.H_FRAME:
                    hv_outer_length += chain_length
                    h_outer_length += chain_length
                elif chain.frame_role == FrameRole.V_FRAME:
                    hv_outer_length += chain_length
                    v_outer_length += chain_length
                if chain.neighbor_kind == ChainNeighborKind.PATCH:
                    patch_neighbor_chain_count += 1
                    if chain.neighbor_patch_id >= 0:
                        patch_neighbor_ids.add(chain.neighbor_patch_id)
        elif boundary_loop.kind == LoopKind.HOLE:
            hole_chain_count += len(boundary_loop.chains)

    if not outer_points:
        outer_points.extend(node.mesh_verts)
    if not outer_points:
        outer_points.append(node.centroid)

    origin = node.centroid
    projected_u = [(co - origin).dot(node.basis_u) for co in outer_points]
    projected_v = [(co - origin).dot(node.basis_v) for co in outer_points]
    width = (max(projected_u) - min(projected_u)) if projected_u else 0.0
    height = (max(projected_v) - min(projected_v)) if projected_v else 0.0
    long_span = max(width, height)
    short_span = min(width, height)
    elongation = 0.0 if long_span <= 1e-8 else _cf_clamp01(1.0 - (short_span / long_span))

    if total_outer_length > 1e-8:
        rectilinearity = _cf_clamp01(hv_outer_length / total_outer_length)
    elif outer_chain_count > 0:
        rectilinearity = _cf_clamp01(runtime_policy.frame_chain_count(patch_id) / outer_chain_count)
    else:
        rectilinearity = 0.0

    hv_outer_total = h_outer_length + v_outer_length
    if hv_outer_total > 1e-8:
        frame_dominance = _cf_clamp01(abs(h_outer_length - v_outer_length) / hv_outer_total)
    else:
        frame_dominance = 0.0

    total_chain_count = outer_chain_count + hole_chain_count
    hole_ratio = _cf_clamp01(hole_chain_count / total_chain_count) if total_chain_count > 0 else 0.0

    closure_density = (
        _cf_clamp01(runtime_policy.closure_pair_count(patch_id) / outer_chain_count)
        if outer_chain_count > 0 else 0.0
    )
    repeated_neighbor_density = (
        _cf_clamp01(max(0, patch_neighbor_chain_count - len(patch_neighbor_ids)) / outer_chain_count)
        if outer_chain_count > 0 else 0.0
    )
    seam_multiplicity_hint = max(closure_density, repeated_neighbor_density)

    return PatchShapeProfile(
        elongation=elongation,
        rectilinearity=rectilinearity,
        hole_ratio=hole_ratio,
        frame_dominance=frame_dominance,
        seam_multiplicity_hint=seam_multiplicity_hint,
    )


def _cf_build_patch_scoring_context(
    chain_ref: ChainRef,
    runtime_policy: "FrontierRuntimePolicy",
) -> PatchScoringContext:
    patch_id = chain_ref[0]
    placed_chain_count = runtime_policy.placed_in_patch(patch_id)
    placed_h_count = runtime_policy.placed_backbone_h_in_patch(patch_id)
    placed_v_count = runtime_policy.placed_backbone_v_in_patch(patch_id)
    placed_free_count = runtime_policy.placed_backbone_free_in_patch(patch_id)
    outer_chain_count = runtime_policy.outer_chain_count(patch_id)
    frame_chain_count = runtime_policy.frame_chain_count(patch_id)
    closure_pair_count = runtime_policy.closure_pair_count(patch_id)

    placed_ratio = (placed_chain_count / outer_chain_count) if outer_chain_count > 0 else 0.0
    frame_progress = placed_h_count + placed_v_count
    hv_coverage_ratio = (frame_progress / frame_chain_count) if frame_chain_count > 0 else 0.0
    same_patch_backbone_strength = hv_coverage_ratio if frame_chain_count > 0 else placed_ratio

    shape_profile = runtime_policy.shape_profile(patch_id)
    shape_closure_sensitivity = _cf_patch_shape_closure_sensitivity(shape_profile)
    closure_base = (closure_pair_count / outer_chain_count) if outer_chain_count > 0 else 0.0
    progress_relief = same_patch_backbone_strength if frame_chain_count > 0 else placed_ratio
    closure_pressure = _cf_clamp01(
        (closure_base * (1.0 - progress_relief))
        + (0.15 * shape_closure_sensitivity)
    )

    return PatchScoringContext(
        patch_id=patch_id,
        placed_chain_count=placed_chain_count,
        placed_h_count=placed_h_count,
        placed_v_count=placed_v_count,
        placed_free_count=placed_free_count,
        placed_ratio=placed_ratio,
        hv_coverage_ratio=hv_coverage_ratio,
        same_patch_backbone_strength=same_patch_backbone_strength,
        closure_pressure=closure_pressure,
        is_untouched=(placed_chain_count == 0),
        has_secondary_seam_pairs=(closure_pair_count > 0),
        shape_profile=shape_profile,
    )


def _cf_chain_seam_relation(
    chain_ref: ChainRef,
    chain: BoundaryChain,
    runtime_policy: "FrontierRuntimePolicy",
) -> Optional[SeamRelationProfile]:
    if chain.neighbor_kind != ChainNeighborKind.PATCH or chain.neighbor_patch_id < 0:
        return None
    return runtime_policy.seam_relation(chain_ref[0], chain.neighbor_patch_id)


def _cf_seam_relation_membership(
    seam_relation: Optional[SeamRelationProfile],
    chain_ref: ChainRef,
) -> str:
    if seam_relation is None:
        return 'none'
    if chain_ref in seam_relation.primary_pair:
        return 'primary'
    for pair in seam_relation.secondary_pairs:
        if chain_ref in pair:
            return 'secondary'
    return 'support'


def _cf_corner_turn_strength(
    corner: BoundaryCorner,
    chain_role: FrameRole,
    other_role: Optional[FrameRole],
) -> float:
    angle = abs(float(corner.turn_angle_deg))
    if angle <= 1e-6:
        return 0.0
    if (
        other_role in {FrameRole.H_FRAME, FrameRole.V_FRAME}
        and chain_role in {FrameRole.H_FRAME, FrameRole.V_FRAME}
        and _is_orthogonal_hv_pair(chain_role, other_role)
    ):
        return max(0.0, 1.0 - (min(abs(angle - 90.0), 90.0) / 90.0))
    return min(1.0, angle / 180.0)


def _cf_build_corner_scoring_hints(
    chain_ref: ChainRef,
    chain: BoundaryChain,
    graph: PatchGraph,
    runtime_policy: Optional["FrontierRuntimePolicy"] = None,
    effective_role: Optional[FrameRole] = None,
) -> CornerScoringHints:
    patch_id, loop_index, chain_index = chain_ref
    node = graph.nodes.get(patch_id)
    if node is None or loop_index < 0 or loop_index >= len(node.boundary_loops):
        return CornerScoringHints()

    boundary_loop = node.boundary_loops[loop_index]

    chain_role = effective_role if effective_role is not None else chain.frame_role

    def _endpoint_corner(corner_index: int) -> tuple[Optional[BoundaryCorner], Optional[FrameRole]]:
        if corner_index < 0 or corner_index >= len(boundary_loop.corners):
            return None, None
        corner = boundary_loop.corners[corner_index]
        other_role: Optional[FrameRole] = None
        other_chain_index = -1
        # ARCHITECTURAL_DEBT: F3_LOOP_PREVNEXT
        # Frontier corner-turn reasoning still reconstructs local prev/next
        # chain context from BoundaryCorner instead of ChainUse adjacency.
        if corner.prev_chain_index == chain_index and corner.next_chain_index != chain_index:
            other_chain_index = corner.next_chain_index
            other_role = corner.next_role
        elif corner.next_chain_index == chain_index and corner.prev_chain_index != chain_index:
            other_chain_index = corner.prev_chain_index
            other_role = corner.prev_role
        if runtime_policy is not None and other_chain_index >= 0:
            other_ref = (patch_id, loop_index, other_chain_index)
            other_chain = graph.get_chain(*other_ref)
            if other_chain is not None:
                other_role = runtime_policy.resolved_placement_role(other_ref, other_chain)
        return corner, other_role

    start_corner, start_other_role = _endpoint_corner(chain.start_corner_index)
    end_corner, end_other_role = _endpoint_corner(chain.end_corner_index)

    start_turn_strength = (
        _cf_corner_turn_strength(start_corner, chain_role, start_other_role)
        if start_corner is not None else 0.0
    )
    end_turn_strength = (
        _cf_corner_turn_strength(end_corner, chain_role, end_other_role)
        if end_corner is not None else 0.0
    )

    orthogonal_turn_count = 0
    same_role_continuation_strength = 0.0
    has_geometric_corner = False
    has_junction_corner = False

    for corner, other_role in (
        (start_corner, start_other_role),
        (end_corner, end_other_role),
    ):
        if corner is None:
            continue
        if corner.is_geometric:
            has_geometric_corner = True
        else:
            has_junction_corner = True
        if (
            other_role in {FrameRole.H_FRAME, FrameRole.V_FRAME}
            and chain_role in {FrameRole.H_FRAME, FrameRole.V_FRAME}
            and _is_orthogonal_hv_pair(chain_role, other_role)
        ):
            orthogonal_turn_count += 1
        if other_role == chain_role:
            same_role_continuation_strength += 0.5 if not corner.is_geometric else 0.25

    return CornerScoringHints(
        start_turn_strength=start_turn_strength,
        end_turn_strength=end_turn_strength,
        orthogonal_turn_count=orthogonal_turn_count,
        same_role_continuation_strength=min(1.0, same_role_continuation_strength),
        has_geometric_corner=has_geometric_corner,
        has_junction_corner=has_junction_corner,
    )


def _cf_build_frontier_rank(
    chain_ref: ChainRef,
    chain: BoundaryChain,
    node: PatchNode,
    known: int,
    graph: PatchGraph,
    topology_facts: FrontierTopologyFacts,
    patch_context: PatchScoringContext,
    quilt_patch_ids: set[int],
    allowed_tree_edges: set[PatchEdgeKey],
    runtime_policy: "FrontierRuntimePolicy",
    score: float,
    seam_relation: Optional[SeamRelationProfile] = None,
    seam_bonus: float = 0.0,
    shape_bonus: float = 0.0,
    closure_pair_refs: Optional[frozenset[ChainRef]] = None,
    start_anchor: Optional[ChainAnchor] = None,
    end_anchor: Optional[ChainAnchor] = None,
    effective_role: Optional[FrameRole] = None,
) -> tuple[FrontierRank, FrontierRankBreakdown]:
    is_hv = topology_facts.is_hv
    same_patch_anchor_count = topology_facts.same_patch_anchor_count
    cross_patch_anchor_count = topology_facts.cross_patch_anchor_count

    viability_tier = 1 if score >= CHAIN_FRONTIER_THRESHOLD else 0
    viability_label = 'viable' if viability_tier else 'below_threshold'
    role_tier, role_label = _cf_role_tier(
        chain_ref,
        chain,
        node,
        graph,
        quilt_patch_ids,
        allowed_tree_edges,
        runtime_policy=runtime_policy,
        effective_role=effective_role,
    )

    if topology_facts.is_secondary_closure and same_patch_anchor_count == 0 and cross_patch_anchor_count > 0:
        if patch_context.is_untouched:
            role_tier = min(role_tier, 1)
            role_label = f"{role_label}:closure_secondary_untouched"
        elif patch_context.same_patch_backbone_strength < 0.5:
            role_tier = min(role_tier, 2)
            role_label = f"{role_label}:closure_secondary_early"

    if known >= 2:
        ingress_tier = 3
        ingress_label = 'dual_anchor'
    elif not patch_context.is_untouched:
        ingress_tier = 2
        ingress_label = 'single_anchor_patch_progress'
    elif known == 1:
        ingress_tier = 1
        ingress_label = 'single_anchor_ingress'
    else:
        ingress_tier = 0
        ingress_label = 'unanchored'

    if is_hv:
        if not topology_facts.would_be_connected:
            patch_fit_tier = 0
            patch_fit_label = 'isolated_hv'
        elif not patch_context.is_untouched:
            patch_fit_tier = 2
            patch_fit_label = f"same_patch_backbone:{patch_context.same_patch_backbone_strength:.2f}"
        else:
            patch_fit_tier = 1
            patch_fit_label = 'hv_ingress'
    else:
        patch_fit_tier = 1 if not patch_context.is_untouched else 0
        patch_fit_label = (
            f"patch_progress:{patch_context.placed_ratio:.2f}"
            if not patch_context.is_untouched else
            'untouched_free'
        )

    anchor_tier = (same_patch_anchor_count * 3) + min(topology_facts.hv_adjacency, 2)
    if same_patch_anchor_count == 0 and cross_patch_anchor_count > 0:
        anchor_tier = max(0, anchor_tier - 1)
    anchor_label = (
        f"sp:{same_patch_anchor_count}"
        f"/xp:{cross_patch_anchor_count}"
        f"/hv:{min(topology_facts.hv_adjacency, 2)}"
    )

    if topology_facts.is_secondary_closure:
        if same_patch_anchor_count == 0 and cross_patch_anchor_count > 0:
            closure_risk_tier = 0
            closure_label = f"closure_cross_patch_only:{patch_context.closure_pressure:.2f}"
        elif patch_context.is_untouched:
            closure_risk_tier = 1
            closure_label = f"closure_patch_ingress:{patch_context.closure_pressure:.2f}"
        else:
            closure_risk_tier = 2
            closure_label = f"closure_supported:{patch_context.closure_pressure:.2f}"
    else:
        closure_risk_tier = 3
        closure_label = f"regular:{patch_context.closure_pressure:.2f}"

    seam_membership = _cf_seam_relation_membership(seam_relation, chain_ref)
    if seam_relation is None:
        seam_label = 'seam:none'
    else:
        if seam_membership == 'primary' and same_patch_anchor_count == 0 and cross_patch_anchor_count > 0:
            anchor_tier += 1
        elif seam_membership == 'secondary':
            if patch_context.is_untouched:
                closure_risk_tier = min(closure_risk_tier, 0)
            elif patch_context.same_patch_backbone_strength < 0.5:
                closure_risk_tier = min(closure_risk_tier, 1)
        elif (
            seam_membership == 'support'
            and seam_relation.is_closure_like
            and same_patch_anchor_count == 0
            and cross_patch_anchor_count > 0
        ):
            anchor_tier = max(0, anchor_tier - 1)
        seam_label = (
            f"seam:{seam_membership}"
            f"/sec:{seam_relation.secondary_pair_count}"
            f"/gap:{seam_relation.pair_strength_gap:.2f}"
            f"/as:{seam_relation.support_asymmetry:.2f}"
            f"/in:{seam_relation.ingress_preference:.2f}"
            f"/b:{seam_bonus:+.2f}"
        )

    shape_profile = patch_context.shape_profile
    if shape_profile is None:
        shape_label = 'shape:none'
    else:
        shape_label = (
            f"shape:{shape_bonus:+.2f}"
            f"/r{shape_profile.rectilinearity:.2f}"
            f"/b{_cf_patch_shape_backbone_bias(shape_profile):.2f}"
            f"/c{_cf_patch_shape_closure_sensitivity(shape_profile):.2f}"
        )

    rank = FrontierRank(
        viability_tier=viability_tier,
        role_tier=role_tier,
        ingress_tier=ingress_tier,
        patch_fit_tier=patch_fit_tier,
        anchor_tier=anchor_tier,
        closure_risk_tier=closure_risk_tier,
        local_score=score,
        tie_length=_cf_chain_total_length(chain, runtime_policy.final_scale),
    )
    breakdown = FrontierRankBreakdown(
        viability_label=viability_label,
        role_label=role_label,
        ingress_label=ingress_label,
        patch_fit_label=patch_fit_label,
        anchor_label=anchor_label,
        closure_label=closure_label,
        seam_label=seam_label,
        shape_label=shape_label,
        summary=(
            f"{viability_label}>{role_label}>{ingress_label}>"
            f"{patch_fit_label}>{anchor_label}>{closure_label}>{seam_label}>{shape_label}"
        ),
    )
    return rank, breakdown


def _cf_frontier_rank_debug_label(rank: Optional[FrontierRank]) -> str:
    if rank is None:
        return '-'
    return (
        f"{rank.viability_tier}/"
        f"{rank.role_tier}/"
        f"{rank.ingress_tier}/"
        f"{rank.patch_fit_tier}/"
        f"{rank.anchor_tier}/"
        f"{rank.closure_risk_tier}"
    )


def _cf_build_frontier_topology_facts(
    chain_ref: ChainRef,
    chain: BoundaryChain,
    graph: PatchGraph,
    runtime_policy: "FrontierRuntimePolicy",
    known: int,
    start_anchor: Optional[ChainAnchor],
    end_anchor: Optional[ChainAnchor],
    closure_pair_refs: Optional[frozenset[ChainRef]] = None,
    effective_role: Optional[FrameRole] = None,
) -> FrontierTopologyFacts:
    eff_role = effective_role if effective_role is not None else runtime_policy.effective_placement_role(chain_ref, chain)
    is_bridge = eff_role == FrameRole.FREE and len(chain.vert_cos) <= 2
    is_hv = eff_role in (FrameRole.H_FRAME, FrameRole.V_FRAME)
    same_patch_anchor_count = sum(
        1 for anchor in (start_anchor, end_anchor)
        if anchor is not None and anchor.source_kind == PlacementSourceKind.SAME_PATCH
    )
    cross_patch_anchor_count = sum(
        1 for anchor in (start_anchor, end_anchor)
        if anchor is not None and anchor.source_kind == PlacementSourceKind.CROSS_PATCH
    )
    hv_adjacency = _cf_count_hv_adjacent_endpoints(
        graph,
        chain_ref,
        runtime_policy=runtime_policy,
        effective_role=eff_role,
    )
    if is_hv:
        for anchor in (start_anchor, end_anchor):
            if anchor is None or anchor.source_kind != PlacementSourceKind.CROSS_PATCH:
                continue
            src_chain = graph.get_chain(*anchor.source_ref)
            if src_chain is not None and src_chain.frame_role in {FrameRole.H_FRAME, FrameRole.V_FRAME}:
                hv_adjacency += 1
                break

    would_be_connected = _cf_preview_would_be_connected(
        chain_ref,
        chain,
        runtime_policy,
        graph,
        effective_role=eff_role,
    )
    return FrontierTopologyFacts(
        is_hv=is_hv,
        is_bridge=is_bridge,
        same_patch_anchor_count=same_patch_anchor_count,
        cross_patch_anchor_count=cross_patch_anchor_count,
        hv_adjacency=hv_adjacency,
        would_be_connected=would_be_connected if is_hv else True,
        is_secondary_closure=bool(known > 0 and closure_pair_refs and chain_ref in closure_pair_refs),
    )


def _cf_score_topology_baseline(
    chain_ref: ChainRef,
    chain: BoundaryChain,
    node: PatchNode,
    known: int,
    graph: PatchGraph,
    quilt_patch_ids: set[int],
    allowed_tree_edges: set[PatchEdgeKey],
    topology_facts: FrontierTopologyFacts,
) -> float:
    score = 0.0
    if topology_facts.is_hv:
        if chain.is_corner_split:
            score += 0.4
        elif (
            chain.neighbor_kind == ChainNeighborKind.PATCH
            and chain.neighbor_patch_id in quilt_patch_ids
            and _is_allowed_quilt_edge(allowed_tree_edges, chain_ref[0], chain.neighbor_patch_id)
        ):
            current_type = node.patch_type
            neighbor_node = graph.nodes.get(chain.neighbor_patch_id)
            neighbor_type = neighbor_node.patch_type if neighbor_node else None
            score += 2.0 if current_type == neighbor_type else 1.5
        else:
            score += 1.0
    elif topology_facts.is_bridge:
        score += 0.1

    if known == 2:
        score += 0.8
    elif known == 1:
        score += 0.3

    if topology_facts.is_bridge and known < 2:
        score -= 0.45
    return score


def _cf_score_patch_anchor_context(
    patch_context: PatchScoringContext,
    topology_facts: FrontierTopologyFacts,
    score_hv_adj_full_bonus: float,
    score_hv_adj_isolated_penalty: float,
    score_bridge_first_patch_penalty: float,
    score_bridge_cross_patch_penalty: float,
) -> float:
    score = 0.0
    if not patch_context.is_untouched:
        score += 0.2

    score += 0.1 * topology_facts.same_patch_anchor_count
    if topology_facts.same_patch_anchor_count == 0 and topology_facts.cross_patch_anchor_count > 0:
        score -= 0.35 if not patch_context.is_untouched else 0.25

    if topology_facts.is_hv:
        if topology_facts.hv_adjacency >= 2:
            score += score_hv_adj_full_bonus
        elif topology_facts.hv_adjacency <= 0:
            placed_hv = patch_context.placed_h_count + patch_context.placed_v_count
            has_same_patch_anchor = topology_facts.same_patch_anchor_count > 0
            if placed_hv == 0:
                # Bootstrap: первый H/V chain в патче — минимальный штраф,
                # чтобы запустить scaffold.
                score -= score_hv_adj_isolated_penalty * 0.15
            elif has_same_patch_anchor:
                # H/V chain bridging через FREE секцию, но имеет anchor
                # от уже placed chain — не изолирован, штраф снижен.
                score -= score_hv_adj_isolated_penalty * 0.35
            else:
                score -= score_hv_adj_isolated_penalty

    if topology_facts.is_bridge and patch_context.is_untouched:
        score -= score_bridge_first_patch_penalty
    if topology_facts.is_bridge and topology_facts.same_patch_anchor_count == 0 and topology_facts.cross_patch_anchor_count > 0:
        score -= score_bridge_cross_patch_penalty
    return score


def _cf_score_closure_guard(
    patch_context: PatchScoringContext,
    topology_facts: FrontierTopologyFacts,
) -> float:
    if not topology_facts.is_secondary_closure:
        return 0.0
    if topology_facts.same_patch_anchor_count == 0 and topology_facts.cross_patch_anchor_count > 0:
        return -(0.9 if not patch_context.is_untouched else 1.1)
    if patch_context.is_untouched:
        return -0.7
    return 0.0


def _cf_score_seam_relation_hint(
    chain_ref: ChainRef,
    patch_context: PatchScoringContext,
    topology_facts: FrontierTopologyFacts,
    seam_relation: Optional[SeamRelationProfile],
) -> float:
    seam_bonus = 0.0
    seam_membership = _cf_seam_relation_membership(seam_relation, chain_ref)
    if seam_relation is None:
        return seam_bonus
    if seam_membership == 'primary':
        if topology_facts.is_hv and topology_facts.same_patch_anchor_count == 0 and topology_facts.cross_patch_anchor_count > 0:
            seam_bonus += 0.05 * seam_relation.ingress_preference
        elif topology_facts.is_hv and patch_context.is_untouched:
            seam_bonus += 0.03 * seam_relation.ingress_preference
    elif seam_membership == 'secondary':
        early_gate = _cf_clamp01(1.0 - patch_context.same_patch_backbone_strength)
        seam_bonus -= 0.06 * early_gate * (1.0 - seam_relation.pair_strength_gap)
    elif seam_relation.is_closure_like and topology_facts.same_patch_anchor_count == 0 and topology_facts.cross_patch_anchor_count > 0:
        seam_bonus -= 0.03 * seam_relation.support_asymmetry
    return seam_bonus


def _cf_score_shape_hint(
    chain_ref: ChainRef,
    patch_context: PatchScoringContext,
    topology_facts: FrontierTopologyFacts,
    shape_profile: Optional[PatchShapeProfile],
    closure_pair_refs: Optional[frozenset[ChainRef]] = None,
) -> float:
    shape_bonus = 0.0
    shape_backbone_bias = _cf_patch_shape_backbone_bias(shape_profile)
    shape_closure_sensitivity = _cf_patch_shape_closure_sensitivity(shape_profile)
    if shape_profile is None:
        return shape_bonus

    if topology_facts.is_hv:
        if patch_context.is_untouched:
            shape_bonus += 0.08 * shape_backbone_bias
        elif patch_context.same_patch_backbone_strength < 0.5:
            shape_bonus += 0.04 * shape_backbone_bias
    elif patch_context.is_untouched:
        free_guard = 0.6 * shape_profile.rectilinearity + 0.4 * shape_profile.frame_dominance
        if topology_facts.is_bridge:
            shape_bonus -= 0.03 * _cf_clamp01(free_guard)
        else:
            shape_bonus -= 0.05 * _cf_clamp01(free_guard)

    if closure_pair_refs and chain_ref in closure_pair_refs:
        progress_gate = 1.0 - patch_context.placed_ratio
        shape_bonus -= 0.05 * shape_closure_sensitivity * _cf_clamp01(progress_gate)
    return shape_bonus


def _cf_score_corner_hint(
    topology_facts: FrontierTopologyFacts,
    corner_hints: Optional[CornerScoringHints],
) -> float:
    if corner_hints is None:
        return 0.0
    avg_turn_strength = (
        corner_hints.start_turn_strength + corner_hints.end_turn_strength
    ) * 0.5
    corner_bonus = 0.0
    if topology_facts.is_hv:
        corner_bonus += 0.04 * min(2, corner_hints.orthogonal_turn_count)
        corner_bonus += 0.04 * corner_hints.same_role_continuation_strength
    else:
        corner_bonus += 0.02 * corner_hints.same_role_continuation_strength
    corner_bonus += 0.02 * avg_turn_strength
    if corner_hints.has_junction_corner and not corner_hints.has_geometric_corner:
        corner_bonus += 0.01
    return corner_bonus


def _cf_build_frontier_local_score_details(
    chain_ref: ChainRef,
    chain: BoundaryChain,
    graph: PatchGraph,
    patch_context: PatchScoringContext,
    runtime_policy: "FrontierRuntimePolicy",
    topology_facts: FrontierTopologyFacts,
    corner_hints: Optional[CornerScoringHints] = None,
    seam_relation: Optional[SeamRelationProfile] = None,
    closure_pair_refs: Optional[frozenset[ChainRef]] = None,
    *,
    score_free_length_scale: float,
    score_free_length_cap: float,
    score_downstream_scale: float,
    score_downstream_cap: float,
    score_isolated_hv_penalty: float,
    score_free_strip_connector: float,
    score_free_frame_neighbor: float,
) -> FrontierLocalScoreDetails:
    length_factor = 0.0
    if not topology_facts.is_hv:
        chain_len = _cf_chain_total_length(chain, runtime_policy.final_scale)
        length_factor = min(score_free_length_cap, chain_len * score_free_length_scale)

    downstream_count = _cf_estimate_downstream_anchor_count(chain_ref, chain, graph, runtime_policy)
    downstream_bonus = min(score_downstream_cap, downstream_count * score_downstream_scale)

    isolation_penalty = 0.0
    if topology_facts.is_hv and not topology_facts.would_be_connected:
        isolation_penalty = score_isolated_hv_penalty

    structural_free_bonus = 0.0
    if not topology_facts.is_hv and not topology_facts.is_bridge:
        neighbors = graph.get_chain_endpoint_neighbors(chain_ref[0], chain_ref[1], chain_ref[2])
        start_has_hv = any(
            graph.get_chain(chain_ref[0], li, ci) is not None
            and graph.get_chain(chain_ref[0], li, ci).frame_role in {FrameRole.H_FRAME, FrameRole.V_FRAME}
            for li, ci in neighbors.get("start", [])
        )
        end_has_hv = any(
            graph.get_chain(chain_ref[0], li, ci) is not None
            and graph.get_chain(chain_ref[0], li, ci).frame_role in {FrameRole.H_FRAME, FrameRole.V_FRAME}
            for li, ci in neighbors.get("end", [])
        )
        if start_has_hv and end_has_hv:
            structural_free_bonus = score_free_strip_connector
        elif start_has_hv or end_has_hv:
            structural_free_bonus = score_free_frame_neighbor

    seam_bonus = _cf_score_seam_relation_hint(
        chain_ref,
        patch_context,
        topology_facts,
        seam_relation,
    )
    shape_bonus = _cf_score_shape_hint(
        chain_ref,
        patch_context,
        topology_facts,
        patch_context.shape_profile,
        closure_pair_refs=closure_pair_refs,
    )
    corner_bonus = _cf_score_corner_hint(topology_facts, corner_hints)

    return FrontierLocalScoreDetails(
        length_factor=length_factor,
        downstream_count=downstream_count,
        downstream_bonus=downstream_bonus,
        isolation_penalty=isolation_penalty,
        structural_free_bonus=structural_free_bonus,
        seam_bonus=seam_bonus,
        corner_bonus=corner_bonus,
        shape_bonus=shape_bonus,
    )


def _cf_score_candidate_layered(
    chain_ref,
    chain,
    node,
    known,
    graph,
    patch_context: PatchScoringContext,
    quilt_patch_ids,
    allowed_tree_edges,
    runtime_policy: "FrontierRuntimePolicy",
    corner_hints: Optional[CornerScoringHints] = None,
    seam_relation: Optional[SeamRelationProfile] = None,
    closure_pair_refs=None,
    start_anchor: Optional[ChainAnchor] = None,
    end_anchor: Optional[ChainAnchor] = None,
    effective_role: Optional[FrameRole] = None,
):
    try:
        from .constants import (
            SCORE_BRIDGE_CROSS_PATCH_PENALTY,
            SCORE_BRIDGE_FIRST_PATCH_PENALTY,
            SCORE_DOWNSTREAM_CAP,
            SCORE_DOWNSTREAM_SCALE,
            SCORE_FREE_FRAME_NEIGHBOR,
            SCORE_FREE_LENGTH_CAP,
            SCORE_FREE_LENGTH_SCALE,
            SCORE_FREE_STRIP_CONNECTOR,
            SCORE_HV_ADJ_FULL_BONUS,
            SCORE_HV_ADJ_ISOLATED_PENALTY,
            SCORE_ISOLATED_HV_PENALTY,
        )
    except ImportError:
        from constants import (
            SCORE_BRIDGE_CROSS_PATCH_PENALTY,
            SCORE_BRIDGE_FIRST_PATCH_PENALTY,
            SCORE_DOWNSTREAM_CAP,
            SCORE_DOWNSTREAM_SCALE,
            SCORE_FREE_FRAME_NEIGHBOR,
            SCORE_FREE_LENGTH_CAP,
            SCORE_FREE_LENGTH_SCALE,
            SCORE_FREE_STRIP_CONNECTOR,
            SCORE_HV_ADJ_FULL_BONUS,
            SCORE_HV_ADJ_ISOLATED_PENALTY,
            SCORE_ISOLATED_HV_PENALTY,
        )

    topology_facts = _cf_build_frontier_topology_facts(
        chain_ref,
        chain,
        graph,
        runtime_policy,
        known,
        start_anchor,
        end_anchor,
        closure_pair_refs=closure_pair_refs,
        effective_role=effective_role,
    )
    score = 0.0
    score += _cf_score_topology_baseline(
        chain_ref,
        chain,
        node,
        known,
        graph,
        quilt_patch_ids,
        allowed_tree_edges,
        topology_facts,
    )
    score += _cf_score_patch_anchor_context(
        patch_context,
        topology_facts,
        SCORE_HV_ADJ_FULL_BONUS,
        SCORE_HV_ADJ_ISOLATED_PENALTY,
        SCORE_BRIDGE_FIRST_PATCH_PENALTY,
        SCORE_BRIDGE_CROSS_PATCH_PENALTY,
    )
    score += _cf_score_closure_guard(
        patch_context,
        topology_facts,
    )

    score_details = _cf_build_frontier_local_score_details(
        chain_ref,
        chain,
        graph,
        patch_context,
        runtime_policy,
        topology_facts,
        corner_hints=corner_hints,
        seam_relation=seam_relation,
        closure_pair_refs=closure_pair_refs,
        score_free_length_scale=SCORE_FREE_LENGTH_SCALE,
        score_free_length_cap=SCORE_FREE_LENGTH_CAP,
        score_downstream_scale=SCORE_DOWNSTREAM_SCALE,
        score_downstream_cap=SCORE_DOWNSTREAM_CAP,
        score_isolated_hv_penalty=SCORE_ISOLATED_HV_PENALTY,
        score_free_strip_connector=SCORE_FREE_STRIP_CONNECTOR,
        score_free_frame_neighbor=SCORE_FREE_FRAME_NEIGHBOR,
    )
    score += score_details.length_factor
    score += score_details.downstream_bonus
    score -= score_details.isolation_penalty
    score += score_details.structural_free_bonus
    score += score_details.seam_bonus
    score += score_details.corner_bonus
    score += score_details.shape_bonus
    return score, topology_facts, score_details


_cf_score_candidate = _cf_score_candidate_layered
