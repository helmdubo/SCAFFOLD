from __future__ import annotations

import math

try:
    from .model import ChainIncidence, ChainNeighborKind, FrameRole
    from .analysis_records import (
        _FrameRunEndpointSpec,
        _JunctionRunEndpointRef,
        _JunctionRolePair,
        _JunctionChainRef,
        _JunctionBuildEntry,
        _JunctionCornerRef,
        _Junction,
    )
except ImportError:
    from model import ChainIncidence, ChainNeighborKind, FrameRole
    from analysis_records import (
        _FrameRunEndpointSpec,
        _JunctionRunEndpointRef,
        _JunctionRolePair,
        _JunctionChainRef,
        _JunctionBuildEntry,
        _JunctionCornerRef,
        _Junction,
    )


def _build_junction_run_refs_by_corner(loop_frame_results):
    """Collect frame-run endpoint refs grouped by corner identity."""

    run_refs_by_corner = {}
    if not loop_frame_results:
        return run_refs_by_corner

    for (patch_id, loop_index), build_result in loop_frame_results.items():
        frame_runs = build_result.runs
        for run_index, frame_run in enumerate(frame_runs):
            endpoint_specs: list[_FrameRunEndpointSpec] = []
            if frame_run.start_corner_index >= 0:
                endpoint_specs.append(
                    _FrameRunEndpointSpec(endpoint_kind="start", corner_index=frame_run.start_corner_index)
                )
            if frame_run.end_corner_index >= 0 and frame_run.end_corner_index != frame_run.start_corner_index:
                endpoint_specs.append(
                    _FrameRunEndpointSpec(endpoint_kind="end", corner_index=frame_run.end_corner_index)
                )
            elif (
                frame_run.end_corner_index >= 0
                and frame_run.end_corner_index == frame_run.start_corner_index
                and endpoint_specs
            ):
                endpoint_specs = [
                    _FrameRunEndpointSpec(endpoint_kind="both", corner_index=frame_run.start_corner_index)
                ]

            for endpoint_spec in endpoint_specs:
                run_refs_by_corner.setdefault(
                    (patch_id, loop_index, endpoint_spec.corner_index),
                    [],
                ).append(
                    _JunctionRunEndpointRef(
                        patch_id=patch_id,
                        loop_index=loop_index,
                        run_index=run_index,
                        dominant_role=frame_run.dominant_role,
                        endpoint_kind=endpoint_spec.endpoint_kind,
                        corner_index=endpoint_spec.corner_index,
                    )
                )
    return {
        corner_key: tuple(run_refs)
        for corner_key, run_refs in run_refs_by_corner.items()
    }


def _junction_run_endpoint_ref_key(run_ref):
    return (run_ref.patch_id, run_ref.loop_index, run_ref.run_index, run_ref.endpoint_kind)


def _junction_corner_ref_key(corner_ref):
    return (corner_ref.patch_id, corner_ref.loop_index, corner_ref.corner_index)


def _junction_chain_ref_key(chain_ref):
    return (chain_ref.patch_id, chain_ref.loop_index, chain_ref.chain_index)


def _derive_junction_role_signature(graph, corner_refs):
    """Derive a deterministic role signature from the concrete corner topology."""

    role_pairs = []
    for corner_ref in corner_refs:
        prev_chain = graph.get_chain(corner_ref.patch_id, corner_ref.loop_index, corner_ref.prev_chain_index)
        next_chain = graph.get_chain(corner_ref.patch_id, corner_ref.loop_index, corner_ref.next_chain_index)
        if prev_chain is None or next_chain is None:
            continue
        role_pairs.append(
            _JunctionRolePair(
                prev_role=prev_chain.frame_role,
                next_role=next_chain.frame_role,
            )
        )
    return tuple(
        sorted(
            role_pairs,
            key=lambda pair: (pair.prev_role.value, pair.next_role.value),
        )
    )


def _derive_junction_chain_refs(graph, corner_refs):
    """Derive unique chain refs touched by the corner set."""

    chain_refs_by_key = {}
    for corner_ref in corner_refs:
        for chain_index in (corner_ref.prev_chain_index, corner_ref.next_chain_index):
            chain = graph.get_chain(corner_ref.patch_id, corner_ref.loop_index, chain_index)
            if chain is None:
                continue
            chain_key = (corner_ref.patch_id, corner_ref.loop_index, chain_index)
            if chain_key in chain_refs_by_key:
                continue
            chain_refs_by_key[chain_key] = _JunctionChainRef(
                patch_id=corner_ref.patch_id,
                loop_index=corner_ref.loop_index,
                chain_index=chain_index,
                frame_role=chain.frame_role,
                neighbor_kind=chain.neighbor_kind,
                chain_use=graph.get_chain_use(corner_ref.patch_id, corner_ref.loop_index, chain_index),
            )
    return tuple(sorted(
        chain_refs_by_key.values(),
        key=lambda ref: (ref.patch_id, ref.loop_index, ref.chain_index),
    ))


def _resolve_chain_incidence_side(chain, corner_vert_index):
    if corner_vert_index == chain.start_vert_index:
        return "start"
    if corner_vert_index == chain.end_vert_index:
        return "end"
    return ""


def _iter_reference_points(chain, side):
    if side == "start":
        return chain.vert_cos[1:]
    if side == "end":
        return reversed(chain.vert_cos[:-1])
    return ()


def _measure_incidence_angle(chain, corner_co, side):
    for point in _iter_reference_points(chain, side):
        delta = point - corner_co
        dx = float(getattr(delta, "x", 0.0))
        dy = float(getattr(delta, "y", 0.0))
        if (dx * dx) + (dy * dy) <= 1e-12:
            continue
        return math.atan2(dy, dx)
    return 0.0


def _derive_junction_disk_cycle(graph, corner_refs):
    # ARCHITECTURAL_DEBT: F2_CORNERFAN
    # Circular disk-cycle order is recomputed inline here rather than sourced
    # from a first-class CornerFan object. See docs/architectural_debt.md.
    incidences_by_key = {}

    for corner_ref in corner_refs:
        node = graph.nodes.get(corner_ref.patch_id)
        if node is None or corner_ref.loop_index < 0 or corner_ref.loop_index >= len(node.boundary_loops):
            continue

        boundary_loop = node.boundary_loops[corner_ref.loop_index]
        if corner_ref.corner_index < 0 or corner_ref.corner_index >= len(boundary_loop.corners):
            continue

        corner = boundary_loop.corners[corner_ref.corner_index]
        for chain_index in (corner_ref.prev_chain_index, corner_ref.next_chain_index):
            if chain_index < 0 or chain_index >= len(boundary_loop.chains):
                continue

            chain = boundary_loop.chains[chain_index]
            side = _resolve_chain_incidence_side(chain, corner.vert_index)
            if not side:
                continue

            chain_use = graph.get_chain_use(corner_ref.patch_id, corner_ref.loop_index, chain_index)
            if chain_use is None:
                continue

            incidence_key = (corner_ref.patch_id, corner_ref.loop_index, chain_index, side)
            incidences_by_key[incidence_key] = ChainIncidence(
                chain_use=chain_use,
                role=chain_use.role_in_loop,
                side=side,
                angle=_measure_incidence_angle(chain, corner.vert_co, side),
            )

    return tuple(
        sorted(
            incidences_by_key.values(),
            key=lambda incidence: (
                incidence.angle,
                incidence.chain_use.patch_id,
                incidence.chain_use.loop_index,
                incidence.chain_use.position_in_loop,
                incidence.side,
            ),
        )
    )


def _derive_junction_run_endpoint_refs(corner_refs, run_refs_by_corner):
    """Derive unique run endpoint refs touched by the corner set."""

    run_endpoint_refs_by_key = {}
    for corner_ref in corner_refs:
        for run_ref in run_refs_by_corner.get(_junction_corner_ref_key(corner_ref), []):
            run_endpoint_refs_by_key[_junction_run_endpoint_ref_key(run_ref)] = run_ref
    return tuple(sorted(
        run_endpoint_refs_by_key.values(),
        key=lambda ref: (ref.patch_id, ref.loop_index, ref.run_index, ref.endpoint_kind),
    ))


def _collect_patch_graph_junction_entries(graph):
    """Collect typed junction build entries from final corner topology."""

    junction_entries = {}
    for patch_id in sorted(graph.nodes.keys()):
        node = graph.nodes[patch_id]
        for loop_index, boundary_loop in enumerate(node.boundary_loops):
            for corner_index, corner in enumerate(boundary_loop.corners):
                if corner.vert_index < 0:
                    continue

                entry = junction_entries.setdefault(
                    corner.vert_index,
                    _JunctionBuildEntry(
                        vert_index=corner.vert_index,
                        vert_co=corner.vert_co.copy(),
                    ),
                )
                entry.patch_ids.add(patch_id)
                entry.corner_refs.append(
                    _JunctionCornerRef(
                        patch_id=patch_id,
                        loop_index=loop_index,
                        corner_index=corner_index,
                        prev_chain_index=corner.prev_chain_index,
                        next_chain_index=corner.next_chain_index,
                    )
                )
    return junction_entries


def _materialize_junction(graph, entry, run_refs_by_corner):
    """Finalize one junction build entry into the immutable report view."""

    corner_refs = tuple(sorted(
        entry.corner_refs,
        key=lambda ref: (ref.patch_id, ref.loop_index, ref.corner_index),
    ))
    chain_refs = _derive_junction_chain_refs(graph, corner_refs)
    disk_cycle = _derive_junction_disk_cycle(graph, corner_refs)
    run_endpoint_refs = _derive_junction_run_endpoint_refs(corner_refs, run_refs_by_corner)
    patch_ids = tuple(sorted(entry.patch_ids))
    role_signature = _derive_junction_role_signature(graph, corner_refs)

    h_count = sum(1 for chain_ref in chain_refs if chain_ref.frame_role == FrameRole.H_FRAME)
    v_count = sum(1 for chain_ref in chain_refs if chain_ref.frame_role == FrameRole.V_FRAME)
    free_count = sum(1 for chain_ref in chain_refs if chain_ref.frame_role == FrameRole.FREE)
    has_mesh_border = any(
        chain_ref.neighbor_kind == ChainNeighborKind.MESH_BORDER for chain_ref in chain_refs
    )
    has_seam_self = any(
        chain_ref.neighbor_kind == ChainNeighborKind.SEAM_SELF for chain_ref in chain_refs
    )

    return _Junction(
        vert_index=entry.vert_index,
        vert_co=entry.vert_co.copy(),
        corner_refs=corner_refs,
        chain_refs=chain_refs,
        disk_cycle=disk_cycle,
        run_endpoint_refs=run_endpoint_refs,
        role_signature=role_signature,
        patch_ids=patch_ids,
        valence=len(corner_refs),
        has_mesh_border=has_mesh_border,
        has_seam_self=has_seam_self,
        is_open=has_mesh_border,
        h_count=h_count,
        v_count=v_count,
        free_count=free_count,
    )


def _build_patch_graph_junctions(graph, run_refs_by_corner=None):
    """Build a diagnostic-only junction view from final patch/loop/corner topology."""

    run_refs_by_corner = run_refs_by_corner or {}
    junction_entries = _collect_patch_graph_junction_entries(graph)
    return [
        _materialize_junction(graph, junction_entries[vert_index], run_refs_by_corner)
        for vert_index in sorted(junction_entries.keys())
    ]
