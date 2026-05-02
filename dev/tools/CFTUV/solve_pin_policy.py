from __future__ import annotations

from typing import Optional

try:
    from .model import BoundaryLoop, FrameRole, PatchGraph, ScaffoldChainPlacement, ScaffoldPatchPlacement
    from .solve_records import ChainPinDecision, PatchPinMap, PinPolicy
except ImportError:
    from model import BoundaryLoop, FrameRole, PatchGraph, ScaffoldChainPlacement, ScaffoldPatchPlacement
    from solve_records import ChainPinDecision, PatchPinMap, PinPolicy


_HV_ROLES = {FrameRole.H_FRAME, FrameRole.V_FRAME}


def _compute_scaffold_connected_chains(
    patch_placements,
    total_chains,
    root_chain_index,
    patch_id: Optional[int] = None,
    band_spine_data: Optional[dict] = None,
):
    """Найти H/V chains связанные с root через непрерывную цепочку H/V.

    Обход замкнутого loop: chains идут по порядку 0→1→...→N-1→0.
    Два соседних chain scaffold-connected если ОБА имеют H/V role.
    One-edge FREE chains (bridge, ≤2 вершин) прозрачны для BFS —
    пропускают связность к H/V chain за ними, но сами включаются
    в connected set (их endpoints = corners, уже запинены соседями).
    Длинные FREE chains разрывают scaffold connectivity.
    BFS от root_chain_index по H/V-adjacency.
    """
    patch_id = patch_placements[0].patch_id if patch_id is None and patch_placements else patch_id
    # Карта chain_index → (frame_role, point_count) для размещённых chains
    placed_info = {}
    for cp in patch_placements:
        placed_info[cp.chain_index] = (cp.frame_role, len(cp.points))

    if isinstance(band_spine_data, dict) and patch_id in band_spine_data:
        spine = band_spine_data[patch_id]
        connected = {
            chain_ref[2]
            for chain_ref in spine.chain_uv_targets.keys()
            if chain_ref[0] == patch_id and chain_ref[2] in placed_info
        }
        if connected:
            return frozenset(connected)

    # Root должен быть H/V, иначе нет scaffold вообще
    if root_chain_index not in placed_info or placed_info[root_chain_index][0] not in _HV_ROLES:
        return frozenset()

    # BFS только по H/V adjacency. FREE bridge больше не
    # проводит scaffold connectivity к следующему H/V chain.
    visited = {root_chain_index}
    queue = [root_chain_index]
    while queue:
        ci = queue.pop()
        for neighbor in [(ci - 1) % total_chains, (ci + 1) % total_chains]:
            if neighbor in visited:
                continue
            if neighbor not in placed_info:
                continue
            role, _ = placed_info[neighbor]
            if role in _HV_ROLES:
                visited.add(neighbor)
                queue.append(neighbor)

    return frozenset(visited)


def _free_endpoint_has_local_frame_anchor(
    boundary_loop: BoundaryLoop,
    chain_index: int,
    point_index: int,
    scaffold_connected_chains: frozenset[int],
) -> bool:
    """Check whether a FREE endpoint touches a connected local H/V chain in the same patch."""

    if chain_index < 0 or chain_index >= len(boundary_loop.chains):
        return False

    chain = boundary_loop.chains[chain_index]
    if chain.frame_role != FrameRole.FREE:
        return False

    if point_index == 0:
        corner_index = chain.start_corner_index
    elif point_index == len(chain.vert_indices) - 1:
        corner_index = chain.end_corner_index
    else:
        return False

    if corner_index < 0 or corner_index >= len(boundary_loop.corners):
        return False

    corner = boundary_loop.corners[corner_index]
    for neighbor_chain_index in (corner.prev_chain_index, corner.next_chain_index):
        if neighbor_chain_index == chain_index:
            continue
        if neighbor_chain_index not in scaffold_connected_chains:
            continue
        if neighbor_chain_index < 0 or neighbor_chain_index >= len(boundary_loop.chains):
            continue
        neighbor_chain = boundary_loop.chains[neighbor_chain_index]
        if neighbor_chain.frame_role in _HV_ROLES:
            return True

    return False


def _decide_chain_pin(
    chain_placement: ScaffoldChainPlacement,
    boundary_loop: Optional[BoundaryLoop],
    conformal_patch: bool,
    scaffold_connected: bool,
    scaffold_connected_chains: frozenset[int],
    band_spine_data: Optional[dict] = None,
) -> ChainPinDecision:
    """Вычислить pin decision для одного chain placement.

    Реализует те же правила что и старый _should_pin_scaffold_point +
    _free_endpoint_has_local_frame_anchor, но как per-chain решение.
    """
    chain_index = chain_placement.chain_index
    role = chain_placement.frame_role
    point_count = len(chain_placement.points)
    chain_ref = (chain_placement.patch_id, chain_placement.loop_index, chain_index)

    if isinstance(band_spine_data, dict):
        spine = band_spine_data.get(chain_placement.patch_id)
        if spine is not None and chain_ref in spine.chain_uv_targets:
            return ChainPinDecision(
                chain_index=chain_index, frame_role=role,
                pin_all=True, pin_endpoints_only=False, pin_start=False, pin_end=False,
                pin_nothing=False, reason='band_spine_connected',
            )

    if conformal_patch:
        return ChainPinDecision(
            chain_index=chain_index, frame_role=role,
            pin_all=False, pin_endpoints_only=False, pin_start=False, pin_end=False,
            pin_nothing=True, reason='conformal_patch',
        )

    if role in _HV_ROLES:
        if scaffold_connected:
            return ChainPinDecision(
                chain_index=chain_index, frame_role=role,
                pin_all=True, pin_endpoints_only=False, pin_start=False, pin_end=False,
                pin_nothing=False, reason='connected_hv',
            )
        else:
            return ChainPinDecision(
                chain_index=chain_index, frame_role=role,
                pin_all=False, pin_endpoints_only=False, pin_start=False, pin_end=False,
                pin_nothing=True, reason='isolated_hv',
            )

    # FREE chain в mixed patch: пинятся только endpoints с local H/V anchor
    if boundary_loop is None or point_count <= 0:
        return ChainPinDecision(
            chain_index=chain_index, frame_role=role,
            pin_all=False, pin_endpoints_only=False, pin_start=False, pin_end=False,
            pin_nothing=True, reason='free_no_boundary',
        )

    pin_start = _free_endpoint_has_local_frame_anchor(
        boundary_loop, chain_index, 0, scaffold_connected_chains,
    )
    # Конечная точка: point_count-1 (для single-point chain та же точка что и 0)
    last_idx = point_count - 1
    pin_end = (
        _free_endpoint_has_local_frame_anchor(
            boundary_loop, chain_index, last_idx, scaffold_connected_chains,
        )
        if last_idx > 0 else False
    )

    if pin_start or pin_end:
        return ChainPinDecision(
            chain_index=chain_index, frame_role=role,
            pin_all=False, pin_endpoints_only=True, pin_start=pin_start, pin_end=pin_end,
            pin_nothing=False, reason='free_with_hv_anchor',
        )
    else:
        return ChainPinDecision(
            chain_index=chain_index, frame_role=role,
            pin_all=False, pin_endpoints_only=False, pin_start=False, pin_end=False,
            pin_nothing=True, reason='free_no_anchor',
        )


def preview_chain_pin_decision(
    chain_placement: ScaffoldChainPlacement,
    boundary_loop: Optional[BoundaryLoop],
    conformal_patch: bool,
    scaffold_connected: bool,
    scaffold_connected_chains: frozenset[int],
    band_spine_data: Optional[dict] = None,
    policy: PinPolicy = PinPolicy(),
) -> ChainPinDecision:
    """Preview pin decision for a single chain without full PatchPinMap.

    Usable from frontier builder to estimate pin impact before commit.
    Returns the same decision as build_patch_pin_map would for the same chain.
    Infrastructure for future scoring (P5) — not called from hot path.
    """
    return _decide_chain_pin(
        chain_placement,
        boundary_loop,
        conformal_patch,
        scaffold_connected,
        scaffold_connected_chains,
        band_spine_data,
    )


def build_patch_pin_map(
    graph: PatchGraph,
    patch_placement: ScaffoldPatchPlacement,
    band_spine_data: Optional[dict] = None,
    policy: PinPolicy = PinPolicy(),
) -> PatchPinMap:
    """Build complete pin map for one patch from scaffold placement data.

    Does NOT touch BMesh or UV. Pure function over PatchGraph + scaffold.
    """
    node = graph.nodes.get(patch_placement.patch_id)
    conformal_patch = all(
        cp.frame_role == FrameRole.FREE for cp in patch_placement.chain_placements
    )
    scaffold_connected_chains = patch_placement.scaffold_connected_chains

    decisions = []
    for cp in patch_placement.chain_placements:
        boundary_loop = None
        if node is not None and 0 <= cp.loop_index < len(node.boundary_loops):
            boundary_loop = node.boundary_loops[cp.loop_index]
        is_connected = cp.chain_index in scaffold_connected_chains
        dec = _decide_chain_pin(
            cp,
            boundary_loop,
            conformal_patch,
            is_connected,
            scaffold_connected_chains,
            band_spine_data,
        )
        decisions.append(dec)

    return PatchPinMap(
        patch_id=patch_placement.patch_id,
        loop_index=patch_placement.loop_index,
        conformal_patch=conformal_patch,
        scaffold_connected_chains=scaffold_connected_chains,
        chain_decisions=tuple(decisions),
    )
