from __future__ import annotations

import math

try:
    from .console_debug import trace_console
    from .model import ChainNeighborKind, FrameRole
    from .analysis_records import (
        _ChainFrameConfidence,
        _ProjectedSpan2D,
        _FrameRunBuildEntry,
        _LoopFrameRunBuildResult,
        _FrameRun,
    )
except ImportError:
    from console_debug import trace_console
    from model import ChainNeighborKind, FrameRole
    from analysis_records import (
        _ChainFrameConfidence,
        _ProjectedSpan2D,
        _FrameRunBuildEntry,
        _LoopFrameRunBuildResult,
        _FrameRun,
    )


def _measure_chain_frame_confidence(chain, basis_u, basis_v, measure_chain_axis_metrics):
    """Measure chain confidence using the current asymmetric H/V semantics."""

    metrics = measure_chain_axis_metrics(chain.vert_cos, basis_u, basis_v)
    if metrics is None:
        return _ChainFrameConfidence(
            primary_support=float("-inf"),
            total_length=0.0,
            avg_deviation_score=0.0,
            max_deviation_score=0.0,
            vert_count=0,
            edge_count=0,
        )

    if chain.frame_role == FrameRole.H_FRAME:
        primary_support = metrics["h_support"]
        avg_deviation = metrics["h_avg_deviation"]
        max_deviation = metrics["h_max_deviation"]
    elif chain.frame_role == FrameRole.V_FRAME:
        primary_support = metrics["v_support"]
        avg_deviation = metrics["v_avg_deviation"]
        max_deviation = metrics["v_max_deviation"]
    else:
        return _ChainFrameConfidence(
            primary_support=float("-inf"),
            total_length=0.0,
            avg_deviation_score=0.0,
            max_deviation_score=0.0,
            vert_count=len(chain.vert_indices),
            edge_count=len(chain.edge_indices),
        )

    return _ChainFrameConfidence(
        primary_support=primary_support,
        total_length=metrics["total_length"],
        avg_deviation_score=-avg_deviation,
        max_deviation_score=-max_deviation,
        vert_count=len(chain.vert_indices),
        edge_count=len(chain.edge_indices),
    )


def _frame_run_chain_length(chain, basis_u, basis_v, measure_chain_axis_metrics):
    metrics = measure_chain_axis_metrics(chain.vert_cos, basis_u, basis_v)
    if metrics is not None:
        return metrics["total_length"]

    total = 0.0
    for point_index in range(len(chain.vert_cos) - 1):
        total += (chain.vert_cos[point_index + 1] - chain.vert_cos[point_index]).length
    return total


def _measure_frame_run_projected_span(points, basis_u, basis_v):
    if not points:
        return _ProjectedSpan2D(u_span=0.0, v_span=0.0)

    u_values = [point.dot(basis_u) for point in points]
    v_values = [point.dot(basis_v) for point in points]
    return _ProjectedSpan2D(
        u_span=max(u_values) - min(u_values),
        v_span=max(v_values) - min(v_values),
    )


def _measure_frame_run_chord_deviation(chain, basis_u, basis_v):
    if len(chain.vert_cos) < 2:
        return None

    basis_n = basis_u.cross(basis_v)
    if basis_n.length_squared < 1e-8:
        return None
    basis_n.normalize()

    chord = chain.vert_cos[-1] - chain.vert_cos[0]
    chord_length = chord.length
    if chord_length < 1e-6:
        return None

    dir_u = chord.dot(basis_u) / chord_length
    dir_v = chord.dot(basis_v) / chord_length
    dir_n = chord.dot(basis_n) / chord_length
    transverse = math.sqrt(max(0.0, dir_u * dir_u + dir_n * dir_n))
    return {
        "h_deviation": abs(dir_v),
        "v_deviation": transverse,
    }


def _infer_frame_run_gap_role(chains, chain_index, basis_u, basis_v, measure_chain_axis_metrics):
    """Infer only obvious same-role micro-gaps for diagnostics.

    This does not mutate chain roles and intentionally stays conservative.
    """

    chain_count = len(chains)
    if chain_count < 3:
        return None

    chain = chains[chain_index]
    if chain.frame_role != FrameRole.FREE:
        return None
    if chain.neighbor_kind != ChainNeighborKind.MESH_BORDER or chain.is_closed:
        return None

    prev_chain = chains[(chain_index - 1) % chain_count]
    next_chain = chains[(chain_index + 1) % chain_count]
    if prev_chain.frame_role != next_chain.frame_role:
        return None
    if prev_chain.frame_role not in (FrameRole.H_FRAME, FrameRole.V_FRAME):
        return None

    chain_metrics = measure_chain_axis_metrics(chain.vert_cos, basis_u, basis_v)
    prev_length = _frame_run_chain_length(prev_chain, basis_u, basis_v, measure_chain_axis_metrics)
    next_length = _frame_run_chain_length(next_chain, basis_u, basis_v, measure_chain_axis_metrics)
    chord_metrics = _measure_frame_run_chord_deviation(chain, basis_u, basis_v)
    if chain_metrics is None or chord_metrics is None:
        return None

    micro_gap_limit = max(0.10, min(prev_length, next_length) * 0.20)
    if chain_metrics["total_length"] > micro_gap_limit:
        return None

    carried_role = prev_chain.frame_role
    if carried_role == FrameRole.H_FRAME:
        if (
            chord_metrics["h_deviation"] < 0.035
            and chain_metrics["h_support"] > 1e-6
            and chain_metrics["h_avg_deviation"] < 0.10
        ):
            return FrameRole.H_FRAME
        return None

    if carried_role == FrameRole.V_FRAME:
        if (
            chord_metrics["v_deviation"] < 0.08
            and chain_metrics["v_support"] > 1e-6
            and chain_metrics["v_avg_deviation"] < 0.12
        ):
            return FrameRole.V_FRAME
        return None

    return None


def _report_frame_run_invariant_violation(patch_id, loop_index, rule_code, detail):
    trace_console(
        f"[CFTUV][TopologyInvariant] Patch {patch_id} Loop {loop_index} {rule_code} {detail}"
    )


def _derive_effective_frame_roles(chains, basis_u, basis_v, measure_chain_axis_metrics):
    """Derive conservative continuity roles used by frame-run diagnostics."""

    effective_roles = []
    for chain_index, chain in enumerate(chains):
        inferred_gap_role = _infer_frame_run_gap_role(
            chains,
            chain_index,
            basis_u,
            basis_v,
            measure_chain_axis_metrics,
        )
        effective_roles.append(inferred_gap_role if inferred_gap_role is not None else chain.frame_role)
    return tuple(effective_roles)


def _derive_frame_run_entries(chains, effective_roles):
    """Partition loop chains into cyclic continuity runs by effective role."""

    if not chains:
        return []

    run_entries: list[_FrameRunBuildEntry] = []
    current_indices = [0]
    current_role = effective_roles[0]

    for chain_index in range(1, len(chains)):
        if effective_roles[chain_index] == current_role:
            current_indices.append(chain_index)
            continue
        run_entries.append(
            _FrameRunBuildEntry(
                dominant_role=current_role,
                chain_indices=tuple(current_indices),
            )
        )
        current_indices = [chain_index]
        current_role = effective_roles[chain_index]

    run_entries.append(
        _FrameRunBuildEntry(
            dominant_role=current_role,
            chain_indices=tuple(current_indices),
        )
    )

    if (
        len(run_entries) > 1
        and run_entries[0].dominant_role == run_entries[-1].dominant_role
    ):
        merged_role = run_entries[-1].dominant_role
        merged_indices = run_entries[-1].chain_indices + run_entries[0].chain_indices
        run_entries = [
            _FrameRunBuildEntry(
                dominant_role=merged_role,
                chain_indices=merged_indices,
            )
        ] + run_entries[1:-1]

    return run_entries


def _build_frame_run(chains, effective_roles, basis_u, basis_v, patch_id, loop_index, chain_indices, measure_chain_axis_metrics):
    if not chain_indices:
        return None

    dominant_role = effective_roles[chain_indices[0]]
    run_points = []
    total_length = 0.0
    support_length = 0.0
    gap_free_length = 0.0
    max_free_gap_length = 0.0

    for local_index, chain_index in enumerate(chain_indices):
        chain = chains[chain_index]
        chain_length = _frame_run_chain_length(chain, basis_u, basis_v, measure_chain_axis_metrics)
        total_length += chain_length

        if chain.frame_role == dominant_role:
            support_length += chain_length
        elif dominant_role != FrameRole.FREE and chain.frame_role == FrameRole.FREE:
            gap_free_length += chain_length
            max_free_gap_length = max(max_free_gap_length, chain_length)
        elif dominant_role == FrameRole.FREE:
            support_length += chain_length

        chain_points = [point.copy() for point in chain.vert_cos]
        if not chain_points:
            continue
        if local_index == 0:
            run_points.extend(chain_points)
            continue
        if run_points and (run_points[-1] - chain_points[0]).length_squared <= 1e-12:
            run_points.extend(chain_points[1:])
        else:
            run_points.extend(chain_points)

    projected_span = _measure_frame_run_projected_span(run_points, basis_u, basis_v)
    first_chain = chains[chain_indices[0]]
    last_chain = chains[chain_indices[-1]]
    return _FrameRun(
        patch_id=patch_id,
        loop_index=loop_index,
        chain_indices=tuple(chain_indices),
        dominant_role=dominant_role,
        start_corner_index=first_chain.start_corner_index,
        end_corner_index=last_chain.end_corner_index,
        total_length=total_length,
        support_length=support_length,
        gap_free_length=gap_free_length,
        max_free_gap_length=max_free_gap_length,
        projected_u_span=projected_span.u_span,
        projected_v_span=projected_span.v_span,
    )


def _validate_loop_frame_runs(boundary_loop, frame_runs, effective_roles, patch_id, loop_index):
    """Validate frame-run continuity against final loop chain topology."""

    chains = list(boundary_loop.chains)
    if not chains:
        if frame_runs:
            _report_frame_run_invariant_violation(
                patch_id,
                loop_index,
                "FR1",
                f"unexpected_runs_for_empty_loop count={len(frame_runs)}",
            )
        return frame_runs

    seen_chain_indices: list[int] = []
    chain_count = len(chains)
    for run_index, frame_run in enumerate(frame_runs):
        if not frame_run.chain_indices:
            _report_frame_run_invariant_violation(
                patch_id,
                loop_index,
                "FR1",
                f"empty_run run={run_index}",
            )
            continue

        first_chain = chains[frame_run.chain_indices[0]]
        last_chain = chains[frame_run.chain_indices[-1]]
        if frame_run.start_corner_index != first_chain.start_corner_index:
            _report_frame_run_invariant_violation(
                patch_id,
                loop_index,
                "FR3",
                f"start_corner_mismatch run={run_index} expected={first_chain.start_corner_index} actual={frame_run.start_corner_index}",
            )
        if frame_run.end_corner_index != last_chain.end_corner_index:
            _report_frame_run_invariant_violation(
                patch_id,
                loop_index,
                "FR3",
                f"end_corner_mismatch run={run_index} expected={last_chain.end_corner_index} actual={frame_run.end_corner_index}",
            )

        for local_index, chain_index in enumerate(frame_run.chain_indices):
            seen_chain_indices.append(chain_index)
            if chain_index < 0 or chain_index >= chain_count:
                _report_frame_run_invariant_violation(
                    patch_id,
                    loop_index,
                    "FR1",
                    f"chain_index_out_of_range run={run_index} chain={chain_index} count={chain_count}",
                )
                continue

            expected_role = effective_roles[chain_index]
            if expected_role != frame_run.dominant_role:
                _report_frame_run_invariant_violation(
                    patch_id,
                    loop_index,
                    "FR2",
                    f"role_mismatch run={run_index} chain={chain_index} expected={expected_role.value} actual={frame_run.dominant_role.value}",
                )

            if local_index == 0:
                continue
            prev_chain_index = frame_run.chain_indices[local_index - 1]
            expected_chain_index = (prev_chain_index + 1) % chain_count
            if chain_index != expected_chain_index:
                _report_frame_run_invariant_violation(
                    patch_id,
                    loop_index,
                    "FR4",
                    f"non_contiguous_run run={run_index} prev={prev_chain_index} actual={chain_index} expected={expected_chain_index}",
                )

    expected_coverage = list(range(chain_count))
    actual_coverage = sorted(seen_chain_indices)
    if actual_coverage != expected_coverage:
        _report_frame_run_invariant_violation(
            patch_id,
            loop_index,
            "FR1",
            f"coverage_mismatch expected={expected_coverage} actual={actual_coverage}",
        )

    if len(seen_chain_indices) != len(set(seen_chain_indices)):
        _report_frame_run_invariant_violation(
            patch_id,
            loop_index,
            "FR1",
            f"duplicate_chain_coverage seen={seen_chain_indices}",
        )

    return frame_runs


def _build_loop_frame_run_result(boundary_loop, basis_u, basis_v, patch_id, loop_index, measure_chain_axis_metrics):
    """Build and validate diagnostic continuity runs over final chains of one loop."""

    chains = list(boundary_loop.chains)
    if not chains:
        return _LoopFrameRunBuildResult(effective_roles=(), runs=())

    effective_roles = _derive_effective_frame_roles(chains, basis_u, basis_v, measure_chain_axis_metrics)
    run_entries = _derive_frame_run_entries(chains, effective_roles)

    frame_runs = []
    for run_entry in run_entries:
        frame_run = _build_frame_run(
            chains,
            effective_roles,
            basis_u,
            basis_v,
            patch_id,
            loop_index,
            run_entry.chain_indices,
            measure_chain_axis_metrics,
        )
        if frame_run is not None:
            frame_runs.append(frame_run)
    _validate_loop_frame_runs(boundary_loop, frame_runs, effective_roles, patch_id, loop_index)
    return _LoopFrameRunBuildResult(effective_roles=effective_roles, runs=tuple(frame_runs))


def _build_patch_graph_loop_frame_results(graph, measure_chain_axis_metrics):
    """Build per-loop derived frame-run results for the PatchGraph."""

    loop_frame_results = {}
    for patch_id in sorted(graph.nodes.keys()):
        node = graph.nodes[patch_id]
        for loop_index, boundary_loop in enumerate(node.boundary_loops):
            build_result = _build_loop_frame_run_result(
                boundary_loop,
                node.basis_u,
                node.basis_v,
                patch_id,
                loop_index,
                measure_chain_axis_metrics,
            )
            loop_frame_results[(patch_id, loop_index)] = build_result
    return loop_frame_results
