from __future__ import annotations

from typing import Optional

from mathutils import Vector

try:
    from .model import FrameAxisKind, FrameRole, FormattedReport, PatchGraph, ScaffoldMap
    from .solve_report_anomalies import (
        ReportAnomaly,
        collect_scaffold_anomalies,
        format_scaffold_anomaly_lines,
    )
    from .solve_report_metrics import (
        collect_report_quilt_patch_ids,
        collect_scaffold_metrics,
    )
    from .solve_report_utils import (
        ReportingMode,
        ReportingOptions,
        coerce_reporting_options,
        format_chain_address,
        format_chain_pair_address,
        format_corner_address,
        format_patch_address,
        format_patch_pair_address,
    )
    from .solve_records import AttachmentCandidate, ClosureCutHeuristic, FrontierPlacementRecord, SolverGraph, SolvePlan
    from .solve_planning import _analyze_quilt_closure_cuts, _build_quilt_tree_edges
    from .solve_transfer import (
        _build_patch_transfer_targets,
        _format_scaffold_uv_points,
        _ordered_quilt_patch_ids,
    )
    from .solve_instrumentation import format_quilt_telemetry_summary, format_quilt_telemetry_detail
except ImportError:
    from model import FrameAxisKind, FrameRole, FormattedReport, PatchGraph, ScaffoldMap
    from solve_report_anomalies import (
        ReportAnomaly,
        collect_scaffold_anomalies,
        format_scaffold_anomaly_lines,
    )
    from solve_report_metrics import (
        collect_report_quilt_patch_ids,
        collect_scaffold_metrics,
    )
    from solve_report_utils import (
        ReportingMode,
        ReportingOptions,
        coerce_reporting_options,
        format_chain_address,
        format_chain_pair_address,
        format_corner_address,
        format_patch_address,
        format_patch_pair_address,
    )
    from solve_records import AttachmentCandidate, ClosureCutHeuristic, FrontierPlacementRecord, SolverGraph, SolvePlan
    from solve_planning import _analyze_quilt_closure_cuts, _build_quilt_tree_edges
    from solve_transfer import (
        _build_patch_transfer_targets,
        _format_scaffold_uv_points,
        _ordered_quilt_patch_ids,
    )
    from solve_instrumentation import format_quilt_telemetry_summary, format_quilt_telemetry_detail


_HV_ROLES = {FrameRole.H_FRAME, FrameRole.V_FRAME}


def _build_anomaly_maps(
    anomalies: tuple[ReportAnomaly, ...],
) -> tuple[dict[int, dict[int, list[ReportAnomaly]]], dict[int, dict[int, list[ReportAnomaly]]]]:
    patch_map: dict[int, dict[int, list[ReportAnomaly]]] = {}
    chain_map: dict[int, dict[int, list[ReportAnomaly]]] = {}
    for anomaly in anomalies:
        if anomaly.quilt_index is None:
            continue
        if anomaly.patch_id is not None:
            patch_map.setdefault(anomaly.quilt_index, {}).setdefault(anomaly.patch_id, []).append(anomaly)
        if anomaly.chain_ref is not None:
            chain_map.setdefault(anomaly.quilt_index, {}).setdefault(anomaly.chain_ref[0], []).append(anomaly)
        if anomaly.peer_chain_ref is not None:
            chain_map.setdefault(anomaly.quilt_index, {}).setdefault(anomaly.peer_chain_ref[0], []).append(anomaly)
    return patch_map, chain_map


def _format_delta(start_uv: Vector, end_uv: Vector) -> Vector:
    return end_uv - start_uv


def _format_uv_pair(uv: Vector) -> str:
    return f"({uv.x:.4f},{uv.y:.4f})"


def _format_chain_axis_error(chain_placement) -> float:
    if len(chain_placement.points) < 2:
        return 0.0
    delta = _format_delta(chain_placement.points[0][1], chain_placement.points[-1][1])
    if chain_placement.frame_role == FrameRole.H_FRAME:
        return abs(delta.y)
    if chain_placement.frame_role == FrameRole.V_FRAME:
        return abs(delta.x)
    return 0.0


def _anchor_kind_short(kind: str) -> str:
    if kind == "same_patch":
        return "SP"
    if kind == "cross_patch":
        return "XP"
    return "-"


def _format_compact_chain_line(
    quilt_index: int,
    chain_placement,
    chain_anomalies: list[ReportAnomaly],
    placement_record: Optional[FrontierPlacementRecord],
) -> str:
    start_uv = chain_placement.points[0][1]
    end_uv = chain_placement.points[-1][1]
    delta = _format_delta(start_uv, end_uv)
    axis_error = _format_chain_axis_error(chain_placement)
    anomaly = chain_anomalies[0] if chain_anomalies else None
    code = anomaly.code if anomaly is not None else "diagnostic"
    inherited_label = "1" if placement_record is not None and placement_record.direction_inherited else "0"
    anchor_label = (
        f"{_anchor_kind_short(placement_record.start_anchor_kind)}/"
        f"{_anchor_kind_short(placement_record.end_anchor_kind)}"
        if placement_record is not None else "-/-"
    )
    status_label = placement_record.placement_path if placement_record is not None else "-"
    return (
        f"    Chain {format_chain_address((chain_placement.patch_id, chain_placement.loop_index, chain_placement.chain_index), quilt_index=quilt_index)} "
        f"{chain_placement.frame_role.value} pts:{len(chain_placement.points)} "
        f"start:{_format_uv_pair(start_uv)} end:{_format_uv_pair(end_uv)} "
        f"d:{_format_uv_pair(delta)} axis:{axis_error:.6f} "
        f"inh:{inherited_label} anchor:{anchor_label} code:{code} st:{status_label}"
    )


def _format_int_list_brief(values, *, limit: int = 8) -> str:
    items = list(values)
    if not items:
        return "[]"
    if len(items) <= limit:
        return "[" + ", ".join(str(item) for item in items) + "]"
    shown = ", ".join(str(item) for item in items[:limit])
    return f"[{shown}, +{len(items) - limit}]"


def _format_label_list_brief(values, *, limit: int = 4) -> str:
    items = sorted({str(item) for item in values if str(item)})
    if not items:
        return "[]"
    if len(items) <= limit:
        return "[" + ", ".join(items) + "]"
    shown = ", ".join(items[:limit])
    return f"[{shown}, +{len(items) - limit}]"


def _format_build_order_summary(
    build_order,
    *,
    quilt_index: int,
    head: int = 3,
    tail: int = 2,
) -> str:
    refs = list(build_order)
    if not refs:
        return "steps:0"
    addresses = [
        format_chain_address(
            (patch_id, loop_index, chain_index),
            quilt_index=quilt_index,
        )
        for patch_id, loop_index, chain_index in refs
    ]
    if len(addresses) <= head + tail + 1:
        return f"steps:{len(addresses)} refs:[" + ", ".join(addresses) + "]"
    first_block = ", ".join(addresses[:head])
    last_block = ", ".join(addresses[-tail:])
    return f"steps:{len(addresses)} first:[{first_block}] last:[{last_block}]"


def _format_pin_reason_summary(pin_map) -> str:
    if pin_map is None:
        return "-"
    counts: dict[str, int] = {}
    for decision in pin_map.chain_decisions:
        counts[decision.reason] = counts.get(decision.reason, 0) + 1
    if not counts:
        return "-"
    return ", ".join(
        f"{reason}={counts[reason]}"
        for reason in sorted(counts)
    )


def _format_optional_metric(value: Optional[float]) -> str:
    if value is None:
        return "-"
    return f"{value:.6f}"


def _format_singular_union_line(item, *, quilt_index: int) -> str:
    split_ref = "-"
    if item.split_chain_ref is not None:
        split_ref = format_chain_address(item.split_chain_ref, quilt_index=quilt_index)
    return (
        f"{item.axis_kind.value} comp:{item.component_id} junction:{item.junction_vert_index} "
        f"split:{split_ref} spread:{item.original_spread:.6f}->{item.resolved_spread:.6f} "
        f"resolved:{'Y' if item.resolved else 'N'} reason:{item.reason or '-'}"
    )


def _format_sibling_group_line(group) -> str:
    return (
        f"P{group.patch_id} {group.role.value} "
        f"members:{len(group.members)} target:{group.target_length:.6f}"
    )


def _append_skeleton_report_lines(
    lines: list[str],
    skeleton_report,
    *,
    quilt_index: int,
    summary_prefix: str,
    summary_label: str,
    detail_prefix: str,
    forensic_mode: bool,
) -> None:
    if skeleton_report is None:
        return

    lines.append(
        f"{summary_prefix}{summary_label}: "
        f"applied:{'Y' if skeleton_report.applied else 'N'} "
        f"rows:{skeleton_report.row_component_count} "
        f"cols:{skeleton_report.col_component_count} "
        f"singular:{skeleton_report.singular_union_count} "
        f"siblings:{skeleton_report.sibling_group_count} "
        f"pure_free:{skeleton_report.pure_free_junction_count} "
        f"unc_row:{skeleton_report.unconstrained_row_junction_count} "
        f"unc_col:{skeleton_report.unconstrained_col_junction_count} "
        f"residual_u:{_format_optional_metric(skeleton_report.residual_u)} "
        f"residual_v:{_format_optional_metric(skeleton_report.residual_v)} "
        f"notes:{_format_label_list_brief(skeleton_report.notes, limit=6)}"
    )

    if not forensic_mode:
        return

    singular_unions = ()
    if skeleton_report.skeleton_graphs is not None:
        singular_unions = skeleton_report.skeleton_graphs.singular_unions
    for item in singular_unions:
        lines.append(f"{detail_prefix}singular {_format_singular_union_line(item, quilt_index=quilt_index)}")

    for group in skeleton_report.sibling_groups:
        lines.append(f"{detail_prefix}sibling {_format_sibling_group_line(group)}")


def format_root_scaffold_report(
    graph: PatchGraph,
    scaffold_map: ScaffoldMap,
    mesh_name: Optional[str] = None,
    reporting: Optional[ReportingOptions] = None,
    *,
    mode: Optional[ReportingMode | str] = None,
) -> FormattedReport:
    reporting = coerce_reporting_options(reporting, mode=mode)
    metrics = collect_scaffold_metrics(graph, scaffold_map)
    anomalies = collect_scaffold_anomalies(
        graph,
        scaffold_map,
        metrics,
        include_transfer=False,
    )
    patch_anomaly_map, chain_anomaly_map = _build_anomaly_maps(anomalies)
    forensic_mode = reporting.mode == ReportingMode.FORENSIC
    lines = []
    if mesh_name:
        lines.append(f"Mesh: {mesh_name}")
    lines.extend(format_scaffold_anomaly_lines(anomalies))
    lines.append("")
    for quilt in scaffold_map.quilts:
        placed_patch_ids = collect_report_quilt_patch_ids(quilt)
        telemetry = getattr(quilt, 'frontier_telemetry', None)
        telemetry_map = (
            {record.chain_ref: record for record in telemetry.placement_records}
            if telemetry is not None else {}
        )
        lines.append(
            f"Quilt {quilt.quilt_index}: "
            f"root={format_patch_address(quilt.root_patch_id, quilt_index=quilt.quilt_index)} "
            f"({graph.get_patch_semantic_key(quilt.root_patch_id)}) | patches:{placed_patch_ids}"
        )
        closure_reports = getattr(quilt, 'closure_seam_reports', ())
        frame_reports = getattr(quilt, 'frame_alignment_reports', ())
        if closure_reports:
            closure_span_mismatch = max((report.span_mismatch for report in closure_reports), default=0.0)
            closure_axis_phase = max((report.axis_phase_offset_max for report in closure_reports), default=0.0)
            lines.append(
                f"  ClosureSeams: {len(closure_reports)} | "
                f"max_span_mismatch:{closure_span_mismatch:.6f} | "
                f"max_axis_phase:{closure_axis_phase:.6f}"
            )
            if forensic_mode:
                for report in closure_reports:
                    seam_addr = format_chain_pair_address(
                        (report.owner_patch_id, report.owner_loop_index, report.owner_chain_index),
                        (report.target_patch_id, report.target_loop_index, report.target_chain_index),
                        quilt_index=quilt.quilt_index,
                    )
                    lines.append(
                        "    "
                        + f"{seam_addr} "
                        + f"{report.frame_role.value} mode:{report.anchor_mode.value} "
                        + f"a:{report.owner_anchor_count}/{report.target_anchor_count} "
                        + f"span3d:{report.canonical_3d_span:.6f} "
                        + f"uv:{report.owner_uv_span:.6f}/{report.target_uv_span:.6f} "
                        + f"mismatch:{report.span_mismatch:.6f} "
                        + f"axis:{report.owner_axis_error:.6f}/{report.target_axis_error:.6f} "
                        + f"phase:{report.axis_phase_offset_max:.6f}/{report.axis_phase_offset_mean:.6f} "
                        + f"cross:{report.cross_axis_offset_max:.6f}/{report.cross_axis_offset_mean:.6f} "
                        + f"uvd:{report.shared_uv_delta_max:.6f}/{report.shared_uv_delta_mean:.6f} "
                        + f"path:{report.tree_patch_distance} free:{report.free_bridge_count}"
                    )
        if frame_reports:
            row_scatter = max((report.scatter_max for report in frame_reports if report.axis_kind == FrameAxisKind.ROW), default=0.0)
            column_scatter = max((report.scatter_max for report in frame_reports if report.axis_kind == FrameAxisKind.COLUMN), default=0.0)
            lines.append(
                f"  FrameGroups: {len(frame_reports)} | "
                f"max_row_scatter:{row_scatter:.6f} | "
                f"max_column_scatter:{column_scatter:.6f}"
            )
            if forensic_mode:
                for report in frame_reports:
                    coord_label = (
                        f"z:{report.class_coord_a:.6f}"
                        if report.axis_kind == FrameAxisKind.ROW
                        else f"xy:({report.class_coord_a:.6f},{report.class_coord_b:.6f})"
                    )
                    refs_label = ','.join(
                        format_chain_address(
                            (patch_id, loop_index, chain_index),
                            quilt_index=quilt.quilt_index,
                        )
                        for patch_id, loop_index, chain_index in report.member_refs
                    )
                    closure_tag = " closure:1" if report.closure_sensitive else " closure:0"
                    lines.append(
                        "    "
                        + f"{report.axis_kind.value} {report.frame_role.value} {coord_label} "
                        + f"chains:{report.chain_count} target:{report.target_cross_uv:.6f} "
                        + f"scatter:{report.scatter_max:.6f}/{report.scatter_mean:.6f} "
                        + f"weight:{report.total_weight:.6f}{closure_tag} refs:[{refs_label}]"
                    )
        _append_skeleton_report_lines(
            lines,
            getattr(quilt, 'skeleton_solve_report', None),
            quilt_index=quilt.quilt_index,
            summary_prefix="  ",
            summary_label="Skeleton",
            detail_prefix="    ",
            forensic_mode=forensic_mode,
        )
        if telemetry is not None:
            for tline in format_quilt_telemetry_summary(telemetry, reporting=reporting):
                lines.append(tline)
            if forensic_mode:
                for tline in format_quilt_telemetry_detail(telemetry, reporting=reporting):
                    lines.append(tline)

        for patch_id in placed_patch_ids:
            patch_placement = quilt.patches.get(patch_id)
            signature = graph.get_patch_semantic_key(patch_id)
            patch_addr = format_patch_address(patch_id, quilt_index=quilt.quilt_index)
            patch_anomalies = patch_anomaly_map.get(quilt.quilt_index, {}).get(patch_id, [])
            patch_chain_anomalies = chain_anomaly_map.get(quilt.quilt_index, {}).get(patch_id, [])
            suspicious_chain_refs = {
                anomaly.chain_ref
                for anomaly in patch_chain_anomalies
                if anomaly.chain_ref is not None and anomaly.chain_ref[0] == patch_id
            }
            suspicious_chain_refs.update(
                anomaly.peer_chain_ref
                for anomaly in patch_chain_anomalies
                if anomaly.peer_chain_ref is not None and anomaly.peer_chain_ref[0] == patch_id
            )
            if patch_placement is None:
                lines.append(f"  {patch_addr} ({signature}) | scaffold:missing")
                continue
            if patch_placement.notes:
                lines.append(
                    f"  {patch_addr} ({signature}) | scaffold:unsupported | "
                    f"notes:{', '.join(patch_placement.notes)}"
                )
                continue

            scaffold_status = 'ok' if patch_placement.closure_valid else 'invalid_closure'
            root_chain_label = "-"
            if patch_placement.root_chain_index >= 0:
                root_chain_label = format_chain_address(
                    (patch_id, patch_placement.loop_index, patch_placement.root_chain_index),
                    quilt_index=quilt.quilt_index,
                )
            lines.append(
                f"  {patch_addr} ({signature}) | loop:{patch_placement.loop_index} | start_chain:{root_chain_label} | "
                f"bbox:({patch_placement.bbox_min.x:.4f}, {patch_placement.bbox_min.y:.4f}) -> ({patch_placement.bbox_max.x:.4f}, {patch_placement.bbox_max.y:.4f}) | "
                f"closure:{patch_placement.closure_error:.6f} | max_gap:{patch_placement.max_chain_gap:.6f} | "
                f"chains:{len(patch_placement.chain_placements)} corners:{len(patch_placement.corner_positions)} "
                f"gaps:{len(patch_placement.gap_reports)} suspicious:{len(suspicious_chain_refs)} "
                f"status:{scaffold_status}"
            )
            node = graph.nodes.get(patch_id)
            if node is None or patch_placement.loop_index < 0 or patch_placement.loop_index >= len(node.boundary_loops):
                continue
            if not forensic_mode:
                if suspicious_chain_refs and reporting.mode == ReportingMode.DIAGNOSTIC:
                    suspicious_chain_lines = []
                    for chain_placement in patch_placement.chain_placements:
                        chain_ref = (patch_id, patch_placement.loop_index, chain_placement.chain_index)
                        if chain_ref not in suspicious_chain_refs:
                            continue
                        chain_specific_anomalies = [
                            anomaly for anomaly in patch_chain_anomalies
                            if anomaly.chain_ref == chain_ref or anomaly.peer_chain_ref == chain_ref
                        ]
                        suspicious_chain_lines.append(
                            _format_compact_chain_line(
                                quilt.quilt_index,
                                chain_placement,
                                chain_specific_anomalies,
                                telemetry_map.get(chain_ref),
                            )
                        )
                    lines.extend(suspicious_chain_lines)
                elif patch_anomalies and reporting.mode == ReportingMode.DIAGNOSTIC:
                    lines.append("    detail: compact | raw:forensic")
                continue

            boundary_loop = node.boundary_loops[patch_placement.loop_index]
            if patch_placement.gap_reports:
                for gap_report in patch_placement.gap_reports:
                    lines.append(
                        f"    Gap {gap_report.chain_index}->{gap_report.next_chain_index}: {gap_report.gap:.6f}"
                    )
            for corner_index in sorted(patch_placement.corner_positions.keys()):
                point = patch_placement.corner_positions[corner_index]
                turn_angle = 0.0
                prev_chain = '-'
                next_chain = '-'
                if 0 <= corner_index < len(boundary_loop.corners):
                    corner = boundary_loop.corners[corner_index]
                    turn_angle = corner.turn_angle_deg
                    prev_chain = corner.prev_chain_index
                    next_chain = corner.next_chain_index
                lines.append(
                    f"    {format_corner_address(patch_id, patch_placement.loop_index, corner_index, quilt_index=quilt.quilt_index)}: "
                    f"({point.x:.4f}, {point.y:.4f}) | chains:{prev_chain}->{next_chain} | turn:{turn_angle:.1f}"
                )
            sc_set = patch_placement.scaffold_connected_chains
            for chain_placement in patch_placement.chain_placements:
                if not chain_placement.points:
                    continue
                start_point = chain_placement.points[0][1]
                end_point = chain_placement.points[-1][1]
                isolated_tag = ""
                if chain_placement.frame_role in _HV_ROLES and chain_placement.chain_index not in sc_set:
                    isolated_tag = " [ISOLATED]"
                chain_addr = format_chain_address(
                    (patch_id, patch_placement.loop_index, chain_placement.chain_index),
                    quilt_index=quilt.quilt_index,
                )
                lines.append(
                    f"    {chain_placement.source_kind.value.title()} {chain_addr}: {chain_placement.frame_role.value} | "
                    f"points:{len(chain_placement.points)} | start:({start_point.x:.4f}, {start_point.y:.4f}) | "
                    f"end:({end_point.x:.4f}, {end_point.y:.4f}) | uv:{_format_scaffold_uv_points(chain_placement.points)}{isolated_tag}"
                )

    summary = (
        f"Scaffold quilts: {metrics.quilt_count} | Patches: {metrics.scaffold_report_patch_count} | "
        f"Unsupported: {metrics.unsupported_report_patch_count} | "
        f"Invalid closure: {len(metrics.invalid_closure_patch_ids)} | "
        f"Closure seams: {metrics.closure_seam_count} | "
        f"Max seam mismatch: {metrics.max_closure_span_mismatch:.6f} | "
        f"Max seam phase: {metrics.max_closure_axis_phase:.6f} | "
        f"Frame groups: {metrics.frame_group_count} | "
        f"Max row scatter: {metrics.max_row_scatter:.6f} | "
        f"Max column scatter: {metrics.max_column_scatter:.6f}"
    )
    return FormattedReport(lines=lines, summary=summary)


def format_regression_snapshot_report(
    bm,
    graph: PatchGraph,
    solve_plan: Optional[SolvePlan],
    scaffold_map: ScaffoldMap,
    mesh_name: Optional[str] = None,
    reporting: Optional[ReportingOptions] = None,
    *,
    mode: Optional[ReportingMode | str] = None,
) -> FormattedReport:
    reporting = coerce_reporting_options(reporting, mode=mode)
    metrics = collect_scaffold_metrics(graph, scaffold_map, bm=bm)
    anomalies = collect_scaffold_anomalies(
        graph,
        scaffold_map,
        metrics,
        include_transfer=True,
    )
    patch_anomaly_map, chain_anomaly_map = _build_anomaly_maps(anomalies)
    forensic_mode = reporting.mode == ReportingMode.FORENSIC
    lines = []
    if mesh_name:
        lines.append(f"Mesh: {mesh_name}")
    lines.extend(format_scaffold_anomaly_lines(anomalies))
    lines.append("")

    solve_plan = solve_plan or SolvePlan()
    quilt_plan_by_index = {quilt.quilt_index: quilt for quilt in solve_plan.quilts}
    unsupported_patch_ids = list(metrics.unsupported_patch_ids)
    invalid_closure_patch_ids = list(metrics.invalid_closure_patch_ids)

    lines.append(f"Patches: {metrics.graph_patch_count}")
    lines.append(f"Quilts: {metrics.quilt_count}")
    lines.append(f"Skipped patches: {_format_int_list_brief(sorted(solve_plan.skipped_patch_ids))}")
    lines.append(f"Unsupported patches: {_format_int_list_brief(unsupported_patch_ids)}")
    lines.append(f"Invalid closure patches: {_format_int_list_brief(invalid_closure_patch_ids)}")
    lines.append(f"Conformal fallback patches: {len(unsupported_patch_ids)}")
    lines.append(
        "Closure seams: "
        f"{metrics.closure_seam_count} | max_span_mismatch:{metrics.max_closure_span_mismatch:.6f} | "
        f"max_axis_phase:{metrics.max_closure_axis_phase:.6f}"
    )
    lines.append(
        "Frame groups: "
        f"{metrics.frame_group_count} | max_row_scatter:{metrics.max_row_scatter:.6f} | "
        f"max_column_scatter:{metrics.max_column_scatter:.6f}"
    )

    for quilt_scaffold in scaffold_map.quilts:
        quilt_plan = quilt_plan_by_index.get(quilt_scaffold.quilt_index)
        ordered_patch_ids = _ordered_quilt_patch_ids(quilt_scaffold, quilt_plan)
        if not ordered_patch_ids:
            ordered_patch_ids = sorted(quilt_scaffold.patches.keys())
        quilt_anomalies = [
            anomaly for anomaly in anomalies
            if anomaly.quilt_index == quilt_scaffold.quilt_index
        ]

        lines.append("")
        lines.append(f"## Quilt {quilt_scaffold.quilt_index}")
        lines.append(
            f"root_patch: "
            f"{format_patch_address(quilt_scaffold.root_patch_id, quilt_index=quilt_scaffold.quilt_index)}"
        )
        lines.append(f"patch_ids: {_format_int_list_brief(ordered_patch_ids, limit=12)}")
        lines.append(
            f"status: stop:{quilt_plan.stop_reason.value if quilt_plan is not None else ''} "
            f"patches:{len(ordered_patch_ids)} anomalies:{len(quilt_anomalies)}"
        )
        if forensic_mode:
            lines.append(
                "build_order: "
                + "[" + ", ".join(
                    format_chain_address(
                        (patch_id, loop_index, chain_index),
                        quilt_index=quilt_scaffold.quilt_index,
                    )
                    for patch_id, loop_index, chain_index in quilt_scaffold.build_order
                ) + "]"
            )
        else:
            lines.append(
                f"build_order: {_format_build_order_summary(quilt_scaffold.build_order, quilt_index=quilt_scaffold.quilt_index)}"
            )

        quilt_unsupported_patch_ids = sorted(
            patch_id
            for patch_id in ordered_patch_ids
            if quilt_scaffold.patches.get(patch_id) is not None
            and quilt_scaffold.patches[patch_id].notes
        )
        quilt_invalid_closure_patch_ids = sorted(
            patch_id
            for patch_id in ordered_patch_ids
            if quilt_scaffold.patches.get(patch_id) is not None
            and not quilt_scaffold.patches[patch_id].notes
            and not quilt_scaffold.patches[patch_id].closure_valid
        )
        if forensic_mode or quilt_unsupported_patch_ids or quilt_invalid_closure_patch_ids:
            lines.append(f"unsupported_patch_ids: {_format_int_list_brief(quilt_unsupported_patch_ids)}")
            lines.append(f"invalid_closure_patch_ids: {_format_int_list_brief(quilt_invalid_closure_patch_ids)}")

        closure_reports = getattr(quilt_scaffold, 'closure_seam_reports', ())
        if closure_reports:
            if forensic_mode:
                lines.append("closure_seams:")
                for report in closure_reports:
                    lines.append(
                        "  - "
                        + format_chain_pair_address(
                            (report.owner_patch_id, report.owner_loop_index, report.owner_chain_index),
                            (report.target_patch_id, report.target_loop_index, report.target_chain_index),
                            quilt_index=quilt_scaffold.quilt_index,
                        )
                        + " "
                        + f"{report.frame_role.value} mode:{report.anchor_mode.value} "
                        + f"mismatch:{report.span_mismatch:.6f} phase:{report.axis_phase_offset_max:.6f} "
                        + f"free:{report.free_bridge_count}"
                    )
            else:
                seam_anomaly_count = sum(
                    1
                    for anomaly in quilt_anomalies
                    if anomaly.peer_chain_ref is not None
                    and anomaly.code in {"closure_seam_mismatch", "axis_drift"}
                )
                lines.append(
                    f"closure_seams: {len(closure_reports)} "
                    f"suspicious:{seam_anomaly_count} "
                    f"max_mismatch:{max((report.span_mismatch for report in closure_reports), default=0.0):.6f} "
                    f"max_phase:{max((report.axis_phase_offset_max for report in closure_reports), default=0.0):.6f}"
                )
        else:
            lines.append("closure_seams: 0")

        frame_reports = getattr(quilt_scaffold, 'frame_alignment_reports', ())
        if frame_reports:
            if forensic_mode:
                lines.append("frame_groups:")
                for report in frame_reports:
                    coord_label = (
                        f"z:{report.class_coord_a:.6f}"
                        if report.axis_kind == FrameAxisKind.ROW
                        else f"xy:({report.class_coord_a:.6f},{report.class_coord_b:.6f})"
                    )
                    lines.append(
                        "  - "
                        + f"{report.axis_kind.value} {report.frame_role.value} {coord_label} "
                        + f"chains:{report.chain_count} target:{report.target_cross_uv:.6f} "
                        + f"scatter:{report.scatter_max:.6f}/{report.scatter_mean:.6f}"
                    )
            else:
                frame_outlier_count = sum(
                    1 for anomaly in quilt_anomalies
                    if anomaly.code == "frame_scatter"
                )
                lines.append(
                    f"frame_groups: {len(frame_reports)} "
                    f"outliers:{frame_outlier_count} "
                    f"max_row_scatter:{max((report.scatter_max for report in frame_reports if report.axis_kind == FrameAxisKind.ROW), default=0.0):.6f} "
                    f"max_column_scatter:{max((report.scatter_max for report in frame_reports if report.axis_kind == FrameAxisKind.COLUMN), default=0.0):.6f}"
                )
        else:
            lines.append("frame_groups: 0")

        _append_skeleton_report_lines(
            lines,
            getattr(quilt_scaffold, 'skeleton_solve_report', None),
            quilt_index=quilt_scaffold.quilt_index,
            summary_prefix="",
            summary_label="skeleton",
            detail_prefix="  - ",
            forensic_mode=forensic_mode,
        )

        telemetry = getattr(quilt_scaffold, 'frontier_telemetry', None)
        telemetry_map = (
            {record.chain_ref: record for record in telemetry.placement_records}
            if telemetry is not None else {}
        )
        if telemetry is not None:
            for tline in format_quilt_telemetry_summary(telemetry, reporting=reporting):
                lines.append(tline)

        lines.append("patches:")
        for patch_id in ordered_patch_ids:
            patch_placement = quilt_scaffold.patches.get(patch_id)
            patch_addr = format_patch_address(patch_id, quilt_index=quilt_scaffold.quilt_index)
            if patch_placement is None:
                lines.append(f"  - {patch_addr} status:missing_patch")
                continue

            transfer_state = metrics.transfer_states_by_patch.get((quilt_scaffold.quilt_index, patch_id))
            if transfer_state is None:
                transfer_state = _build_patch_transfer_targets(
                    bm,
                    graph,
                    patch_placement,
                    Vector((0.0, 0.0)),
                )
            node = graph.nodes.get(patch_id)
            signature = graph.get_patch_semantic_key(patch_id)
            patch_anomalies = patch_anomaly_map.get(quilt_scaffold.quilt_index, {}).get(patch_id, [])
            patch_chain_anomalies = chain_anomaly_map.get(quilt_scaffold.quilt_index, {}).get(patch_id, [])
            suspicious_chain_refs = {
                anomaly.chain_ref
                for anomaly in patch_chain_anomalies
                if anomaly.chain_ref is not None and anomaly.chain_ref[0] == patch_id
            }
            suspicious_chain_refs.update(
                anomaly.peer_chain_ref
                for anomaly in patch_chain_anomalies
                if anomaly.peer_chain_ref is not None and anomaly.peer_chain_ref[0] == patch_id
            )
            root_chain_label = "-"
            if patch_placement.root_chain_index >= 0:
                root_chain_label = format_chain_address(
                    (patch_id, patch_placement.loop_index, patch_placement.root_chain_index),
                    quilt_index=quilt_scaffold.quilt_index,
                )
            total_chains = len(patch_placement.chain_placements)
            if node is not None and 0 <= patch_placement.loop_index < len(node.boundary_loops):
                total_chains = len(node.boundary_loops[patch_placement.loop_index].chains)
                sc_count = len(patch_placement.scaffold_connected_chains)
            else:
                sc_count = len(patch_placement.scaffold_connected_chains)

            pin_total = transfer_state.pinned_uv_targets + transfer_state.unpinned_uv_targets
            patch_codes = sorted({
                anomaly.code
                for anomaly in (*patch_anomalies, *patch_chain_anomalies)
            })
            patch_parts = [
                f"{patch_addr} {signature}",
                f"status:{patch_placement.status.value}",
                f"transfer:{transfer_state.status.value}",
                f"loop:{patch_placement.loop_index}",
                f"root:{root_chain_label}",
                f"chains:{len(patch_placement.chain_placements)}/{total_chains}",
                f"sc:{sc_count}/{total_chains}",
                f"pts:{transfer_state.resolved_scaffold_points}/{transfer_state.scaffold_points}",
                f"uv:{transfer_state.uv_targets_resolved}",
                f"pin:{transfer_state.pinned_uv_targets}/{pin_total}",
            ]
            if patch_placement.max_chain_gap > 0.0:
                patch_parts.append(f"gap:{patch_placement.max_chain_gap:.6f}")
            if (not patch_placement.closure_valid) or abs(patch_placement.closure_error) > 0.0:
                patch_parts.append(f"closure:{patch_placement.closure_error:.6f}")
            if transfer_state.conflicting_uv_targets > 0:
                patch_parts.append(f"conflicts:{transfer_state.conflicting_uv_targets}")
            if transfer_state.missing_uv_targets > 0:
                patch_parts.append(f"missing:{transfer_state.missing_uv_targets}")
            if transfer_state.unresolved_scaffold_points > 0:
                patch_parts.append(f"unresolved:{transfer_state.unresolved_scaffold_points}")
            if patch_placement.unplaced_chain_indices:
                patch_parts.append(
                    f"unplaced:{_format_int_list_brief(patch_placement.unplaced_chain_indices, limit=6)}"
                )
            if patch_placement.dependency_patches:
                patch_parts.append(
                    f"deps:{_format_int_list_brief(patch_placement.dependency_patches, limit=6)}"
                )
            if patch_placement.notes:
                patch_parts.append(f"notes:{','.join(patch_placement.notes)}")
            if suspicious_chain_refs:
                patch_parts.append(f"suspicious:{len(suspicious_chain_refs)}")
            if patch_codes:
                patch_parts.append(f"flags:{_format_label_list_brief(patch_codes)}")
            lines.append("  - " + " ".join(patch_parts))

            if transfer_state.pin_map is not None:
                if forensic_mode:
                    pin_parts = [
                        f"{format_chain_address((patch_id, patch_placement.loop_index, dec.chain_index), quilt_index=quilt_scaffold.quilt_index)}:{dec.reason}"
                        for dec in transfer_state.pin_map.chain_decisions
                    ]
                    lines.append(f"    pin_reasons:[{', '.join(pin_parts)}]")
                elif patch_codes or suspicious_chain_refs or transfer_state.conflicting_uv_targets > 0:
                    lines.append(f"    pin_reasons:{_format_pin_reason_summary(transfer_state.pin_map)}")

            if suspicious_chain_refs:
                for chain_placement in patch_placement.chain_placements:
                    chain_ref = (patch_id, patch_placement.loop_index, chain_placement.chain_index)
                    if chain_ref not in suspicious_chain_refs:
                        continue
                    chain_specific_anomalies = [
                        anomaly for anomaly in patch_chain_anomalies
                        if anomaly.chain_ref == chain_ref or anomaly.peer_chain_ref == chain_ref
                    ]
                    lines.append(
                        _format_compact_chain_line(
                            quilt_scaffold.quilt_index,
                            chain_placement,
                            chain_specific_anomalies,
                            telemetry_map.get(chain_ref),
                        )
                    )

    summary = (
        f"Regression snapshot | quilts:{metrics.quilt_count} | patches:{metrics.graph_patch_count} | "
        f"unsupported:{len(unsupported_patch_ids)} | invalid_closure:{len(invalid_closure_patch_ids)} | "
        f"conformal_fallback_patches:{len(unsupported_patch_ids)}"
    )
    return FormattedReport(lines=lines, summary=summary)


def _format_closure_cut_heuristic(item: ClosureCutHeuristic) -> str:
    candidate = item.candidate
    return (
        f"{item.edge_key[0]}-{item.edge_key[1]} cut:{item.score:.2f} {item.support_label} "
        f"| roles:{candidate.owner_role.value}<->{candidate.target_role.value} "
        f"| refs:L{candidate.owner_loop_index}C{candidate.owner_chain_index}->"
        f"L{candidate.target_loop_index}C{candidate.target_chain_index} "
        f"| {' '.join(item.reasons)}"
    )


def _format_patch_signature(graph: PatchGraph, patch_id: int) -> str:
    return graph.get_patch_semantic_key(patch_id)


def _format_candidate_line(candidate: AttachmentCandidate) -> str:
    return (
        f"{format_patch_pair_address(candidate.owner_patch_id, candidate.target_patch_id)} | score:{candidate.score:.2f} "
        f"| seam:{candidate.seam_length:.4f} | roles:{candidate.owner_role.value}<->{candidate.target_role.value} "
        f"| loops:{candidate.owner_loop_kind.value}<->{candidate.target_loop_kind.value} "
        f"| refs:{format_chain_pair_address((candidate.owner_patch_id, candidate.owner_loop_index, candidate.owner_chain_index), (candidate.target_patch_id, candidate.target_loop_index, candidate.target_chain_index))}"
    )


def format_solve_plan_report(
    graph: PatchGraph,
    solver_graph: SolverGraph,
    solve_plan: SolvePlan,
    mesh_name: Optional[str] = None,
    reporting: Optional[ReportingOptions] = None,
    *,
    mode: Optional[ReportingMode | str] = None,
) -> FormattedReport:
    reporting = coerce_reporting_options(reporting, mode=mode)
    lines: list[str] = []
    if mesh_name:
        lines.append(f"Mesh: {mesh_name}")
    lines.append(
        f"Thresholds: propagate>={solve_plan.propagate_threshold:.2f} weak>={solve_plan.weak_threshold:.2f}"
    )

    components = solver_graph.solve_components or graph.connected_components()
    for component_index, component in enumerate(components):
        patch_ids = sorted(component)
        lines.append(f"Component {component_index}: patches={patch_ids}")
        lines.append("  Patch Certainty:")
        component_scores = sorted(
            (solver_graph.patch_scores[patch_id] for patch_id in patch_ids),
            key=lambda item: item.root_score,
            reverse=True,
        )
        for certainty in component_scores:
            lines.append(
                "    "
                + f"{format_patch_address(certainty.patch_id)}: {_format_patch_signature(graph, certainty.patch_id)} "
                + f"| local:{'Y' if certainty.local_solvable else 'N'} | root:{certainty.root_score:.2f} "
                + f"| loops:outer={certainty.outer_count} hole={certainty.hole_count} "
                + f"| chains:{certainty.chain_count} H:{certainty.h_count} V:{certainty.v_count} Free:{certainty.free_count}"
            )
            if certainty.reasons:
                lines.append(f"      reasons: {' | '.join(certainty.reasons)}")

        component_candidates = [
            candidate
            for candidate in solver_graph.candidates
            if candidate.owner_patch_id in component and candidate.target_patch_id in component
        ]
        if component_candidates:
            lines.append("  Conductivity:")
            for candidate in sorted(component_candidates, key=lambda item: (-item.score, item.owner_patch_id, item.target_patch_id)):
                lines.append("    " + _format_candidate_line(candidate))
                lines.append(
                    "      "
                    + f"transitions:{candidate.owner_transition} | {candidate.target_transition} "
                    + f"| seam:{candidate.seam_norm:.2f} pair:{candidate.best_pair_strength:.2f} "
                    + f"cont:{candidate.frame_continuation:.2f} bridge:{candidate.endpoint_bridge:.2f} "
                    + f"corner:{candidate.corner_strength:.2f} sem:{candidate.semantic_strength:.2f} "
                    + f"ep:{candidate.endpoint_strength:.2f} amb:{candidate.ambiguity_penalty:.2f}"
                )

    closure_cut_analyses_by_quilt = {
        quilt.quilt_index: _analyze_quilt_closure_cuts(graph, solver_graph, quilt)
        for quilt in solve_plan.quilts
    }

    for quilt in solve_plan.quilts:
        tree_edges = sorted(_build_quilt_tree_edges(quilt))
        closure_cut_analyses = closure_cut_analyses_by_quilt.get(quilt.quilt_index, ())
        lines.append(
            f"Quilt {quilt.quilt_index}: component={quilt.component_index} "
            f"root={format_patch_address(quilt.root_patch_id, quilt_index=quilt.quilt_index)} "
            f"({_format_patch_signature(graph, quilt.root_patch_id)}) root_score={quilt.root_score:.2f}"
        )
        if tree_edges:
            lines.append(
                "  Tree edges: " + ", ".join(f"{edge_key[0]}-{edge_key[1]}" for edge_key in tree_edges)
            )
        for step in quilt.steps:
            if step.is_root or step.incoming_candidate is None:
                lines.append(
                    f"  Step {step.step_index}: ROOT {format_patch_address(step.patch_id, quilt_index=quilt.quilt_index)} "
                    f"({_format_patch_signature(graph, step.patch_id)})"
                )
                continue
            candidate = step.incoming_candidate
            lines.append(
                f"  Step {step.step_index}: "
                f"{format_patch_pair_address(candidate.owner_patch_id, step.patch_id, quilt_index=quilt.quilt_index)} "
                f"| score:{candidate.score:.2f} | roles:{candidate.owner_role.value}<->{candidate.target_role.value}"
            )
            lines.append(
                "    "
                + f"refs:{format_chain_pair_address((candidate.owner_patch_id, candidate.owner_loop_index, candidate.owner_chain_index), (step.patch_id, candidate.target_loop_index, candidate.target_chain_index), quilt_index=quilt.quilt_index)} "
                + f"| transitions:{candidate.owner_transition} | {candidate.target_transition}"
            )
        if closure_cut_analyses:
            lines.append("  Closure cuts:")
            for analysis_index, analysis in enumerate(closure_cut_analyses):
                current_edge = f"{analysis.current_cut.edge_key[0]}-{analysis.current_cut.edge_key[1]}"
                recommended_edge = f"{analysis.recommended_cut.edge_key[0]}-{analysis.recommended_cut.edge_key[1]}"
                decision = (
                    f"keep {current_edge}"
                    if analysis.current_cut.edge_key == analysis.recommended_cut.edge_key
                    else f"swap {current_edge} -> {recommended_edge}"
                )
                lines.append(
                    f"    Cycle {analysis_index}: path={list(analysis.path_patch_ids)} | decision:{decision}"
                )
                lines.append("      current: " + _format_closure_cut_heuristic(analysis.current_cut))
                lines.append("      best:    " + _format_closure_cut_heuristic(analysis.recommended_cut))
                for cycle_edge in analysis.cycle_edges:
                    marker = ""
                    if cycle_edge.edge_key == analysis.recommended_cut.edge_key:
                        marker += " [BEST]"
                    if cycle_edge.edge_key == analysis.current_cut.edge_key:
                        marker += " [CURRENT]"
                    lines.append("      edge: " + _format_closure_cut_heuristic(cycle_edge) + marker)
        lines.append(f"  Stop: {quilt.stop_reason.value}")
        if quilt.deferred_candidates:
            lines.append("  Deferred frontier:")
            for candidate in quilt.deferred_candidates:
                lines.append("    " + _format_candidate_line(candidate))
        if quilt.rejected_candidates:
            lines.append("  Rejected frontier:")
            for candidate in quilt.rejected_candidates:
                lines.append("    " + _format_candidate_line(candidate))

    if solve_plan.skipped_patch_ids:
        lines.append(f"Skipped patches: {sorted(solve_plan.skipped_patch_ids)}")

    total_steps = sum(len(quilt.steps) for quilt in solve_plan.quilts)
    total_deferred = sum(len(quilt.deferred_candidates) for quilt in solve_plan.quilts)
    total_rejected = sum(len(quilt.rejected_candidates) for quilt in solve_plan.quilts)
    total_closure_cycles = sum(len(items) for items in closure_cut_analyses_by_quilt.values())
    total_cut_swaps = sum(
        1
        for analyses in closure_cut_analyses_by_quilt.values()
        for analysis in analyses
        if analysis.current_cut.edge_key != analysis.recommended_cut.edge_key
    )
    summary = (
        f"Quilts: {len(solve_plan.quilts)} | Steps: {total_steps} | "
        f"Deferred: {total_deferred} | Rejected: {total_rejected} | "
        f"ClosureCycles: {total_closure_cycles} | CutSwaps: {total_cut_swaps} | "
        f"Skipped: {len(solve_plan.skipped_patch_ids)}"
    )
    return FormattedReport(lines=lines, summary=summary)





