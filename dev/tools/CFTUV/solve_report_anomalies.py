from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from mathutils import Vector

try:
    from .model import ChainRef, FrameAxisKind, FrameRole, PatchGraph, ScaffoldChainPlacement, ScaffoldMap
    from .solve_report_metrics import ScaffoldMetricsSummary
    from .solve_report_utils import (
        format_chain_address,
        format_chain_pair_address,
        format_patch_address,
        format_stall_address,
    )
    from .solve_records import (
        FRAME_COLUMN_GROUP_TOLERANCE,
        FRAME_ROW_GROUP_TOLERANCE,
        SCAFFOLD_CLOSURE_EPSILON,
        FrontierPlacementRecord,
        PatchTransferStatus,
    )
except ImportError:
    from model import ChainRef, FrameAxisKind, FrameRole, PatchGraph, ScaffoldChainPlacement, ScaffoldMap
    from solve_report_metrics import ScaffoldMetricsSummary
    from solve_report_utils import (
        format_chain_address,
        format_chain_pair_address,
        format_patch_address,
        format_stall_address,
    )
    from solve_records import (
        FRAME_COLUMN_GROUP_TOLERANCE,
        FRAME_ROW_GROUP_TOLERANCE,
        SCAFFOLD_CLOSURE_EPSILON,
        FrontierPlacementRecord,
        PatchTransferStatus,
    )


_HV_ROLES = {FrameRole.H_FRAME, FrameRole.V_FRAME}
_ANOMALY_MIN_AXIS_ERROR = 0.05
_ANOMALY_MIN_AXIS_PHASE = 0.05
_ANOMALY_MIN_SHARED_DELTA = 0.05


@dataclass(frozen=True)
class ReportAnomaly:
    priority: int
    magnitude: float
    address: str
    code: str
    detail: str
    quilt_index: Optional[int] = None
    patch_id: Optional[int] = None
    chain_ref: Optional[ChainRef] = None
    peer_chain_ref: Optional[ChainRef] = None


def _format_uv(uv: Vector) -> str:
    return f"({uv.x:.4f},{uv.y:.4f})"


def _short_anchor_kind(kind: str) -> str:
    if kind == "same_patch":
        return "SP"
    if kind == "cross_patch":
        return "XP"
    return "-"


def _frame_scatter_threshold(axis_kind: FrameAxisKind) -> float:
    tolerance = FRAME_ROW_GROUP_TOLERANCE if axis_kind == FrameAxisKind.ROW else FRAME_COLUMN_GROUP_TOLERANCE
    return max(tolerance * 32.0, 0.05)


def _is_actionable_unresolved_stall(stall) -> bool:
    """Отсекает нормальный exhausted-stop без реального проблемного остатка frontier."""
    if stall.rescue_succeeded:
        return False
    if (
        stall.best_rejected_ref is None
        and stall.best_rejected_score < 0.0
        and stall.available_count <= 0
        and stall.no_anchor_count <= 0
        and stall.below_threshold_count <= 0
    ):
        return False
    return True


def _chain_delta(chain_placement: ScaffoldChainPlacement) -> Vector:
    if len(chain_placement.points) < 2:
        return Vector((0.0, 0.0))
    return chain_placement.points[-1][1] - chain_placement.points[0][1]


def _chain_axis_error(chain_placement: ScaffoldChainPlacement) -> float:
    delta = _chain_delta(chain_placement)
    if chain_placement.frame_role == FrameRole.H_FRAME:
        return abs(delta.y)
    if chain_placement.frame_role == FrameRole.V_FRAME:
        return abs(delta.x)
    return 0.0


def _chain_cross_uv(chain_placement: ScaffoldChainPlacement) -> float:
    if not chain_placement.points:
        return 0.0
    if chain_placement.frame_role == FrameRole.H_FRAME:
        return sum(uv.y for _, uv in chain_placement.points) / float(len(chain_placement.points))
    if chain_placement.frame_role == FrameRole.V_FRAME:
        return sum(uv.x for _, uv in chain_placement.points) / float(len(chain_placement.points))
    return 0.0


def _build_quilt_chain_map(quilt) -> dict[ChainRef, ScaffoldChainPlacement]:
    chain_map: dict[ChainRef, ScaffoldChainPlacement] = {}
    for patch_placement in quilt.patches.values():
        if patch_placement is None:
            continue
        for chain_placement in patch_placement.chain_placements:
            chain_map[(chain_placement.patch_id, chain_placement.loop_index, chain_placement.chain_index)] = chain_placement
    return chain_map


def _build_quilt_telemetry_map(quilt) -> dict[ChainRef, FrontierPlacementRecord]:
    telemetry = getattr(quilt, "frontier_telemetry", None)
    if telemetry is None:
        return {}
    return {record.chain_ref: record for record in telemetry.placement_records}


def _make_hv_chain_anomaly(
    chain_ref: ChainRef,
    quilt_index: int,
    chain_placement: ScaffoldChainPlacement,
    placement_record: Optional[FrontierPlacementRecord],
) -> Optional[ReportAnomaly]:
    if chain_placement.frame_role not in _HV_ROLES or len(chain_placement.points) < 2:
        return None

    axis_error = _chain_axis_error(chain_placement)
    start_uv = chain_placement.points[0][1]
    end_uv = chain_placement.points[-1][1]
    delta = _chain_delta(chain_placement)
    address = format_chain_address(chain_ref, quilt_index=quilt_index)

    anchor_label = "-/-"
    inherited_flag = "0"
    status_label = "placed"

    if placement_record is not None:
        anchor_label = (
            f"{_short_anchor_kind(placement_record.start_anchor_kind)}/"
            f"{_short_anchor_kind(placement_record.end_anchor_kind)}"
        )
        inherited_flag = "1" if placement_record.direction_inherited else "0"

    code = ""
    priority = 0
    magnitude = axis_error
    if placement_record is not None and placement_record.frame_role != chain_placement.frame_role:
        code = "frame_role_mismatch"
        priority = 4
        status_label = f"telemetry:{placement_record.frame_role.value}"
        magnitude = 1.0
    elif placement_record is not None and placement_record.placement_path != "main" and placement_record.anchor_count <= 0:
        code = "direction_conflict"
        priority = 5
        status_label = f"{placement_record.placement_path}_zero_anchor"
        magnitude = max(axis_error, 1.0)
    elif axis_error > _ANOMALY_MIN_AXIS_ERROR:
        code = "axis_drift"
        priority = 6
        status_label = "axis_error"
    elif placement_record is not None and placement_record.hv_adjacency <= 0:
        code = "hv_adjacency_conflict"
        priority = 7
        status_label = f"{placement_record.placement_path}_hv0"
        magnitude = 1.0
    else:
        return None

    return ReportAnomaly(
        priority=priority,
        magnitude=magnitude,
        address=address,
        code=code,
        detail=(
            f"{chain_placement.frame_role.value} pts:{len(chain_placement.points)} "
            f"start:{_format_uv(start_uv)} end:{_format_uv(end_uv)} "
            f"d:{_format_uv(delta)} axis:{axis_error:.6f} inh:{inherited_flag} "
            f"anchor:{anchor_label} st:{status_label}"
        ),
        quilt_index=quilt_index,
        patch_id=chain_ref[0],
        chain_ref=chain_ref,
    )


def _dedupe_anomalies(anomalies: list[ReportAnomaly]) -> list[ReportAnomaly]:
    best_by_key: dict[tuple[str, str], ReportAnomaly] = {}
    for anomaly in anomalies:
        key = (anomaly.address, anomaly.code)
        current = best_by_key.get(key)
        if current is None or (anomaly.priority, -anomaly.magnitude) < (current.priority, -current.magnitude):
            best_by_key[key] = anomaly
    return list(best_by_key.values())


def collect_scaffold_anomalies(
    graph: PatchGraph,
    scaffold_map: ScaffoldMap,
    metrics: ScaffoldMetricsSummary,
    *,
    include_transfer: bool,
) -> tuple[ReportAnomaly, ...]:
    anomalies: list[ReportAnomaly] = []

    for quilt in scaffold_map.quilts:
        chain_map = _build_quilt_chain_map(quilt)
        telemetry_map = _build_quilt_telemetry_map(quilt)

        for patch_id, patch_placement in quilt.patches.items():
            patch_addr = format_patch_address(patch_id, quilt_index=quilt.quilt_index)
            if patch_placement is None:
                anomalies.append(
                    ReportAnomaly(
                        priority=0,
                        magnitude=1.0,
                        address=patch_addr,
                        code="missing_patch",
                        detail="status:missing",
                        quilt_index=quilt.quilt_index,
                        patch_id=patch_id,
                    )
                )
                continue
            if patch_placement.notes:
                anomalies.append(
                    ReportAnomaly(
                        priority=1,
                        magnitude=float(len(patch_placement.notes)),
                        address=patch_addr,
                        code="unsupported_patch",
                        detail=f"notes:{','.join(patch_placement.notes)}",
                        quilt_index=quilt.quilt_index,
                        patch_id=patch_id,
                    )
                )
            elif not patch_placement.closure_valid:
                anomalies.append(
                    ReportAnomaly(
                        priority=2,
                        magnitude=max(abs(patch_placement.closure_error), abs(patch_placement.max_chain_gap)),
                        address=patch_addr,
                        code="closure_invalid",
                        detail=(
                            f"closure:{patch_placement.closure_error:.6f} "
                            f"gap:{patch_placement.max_chain_gap:.6f} "
                            f"unplaced:{len(patch_placement.unplaced_chain_indices)}"
                        ),
                        quilt_index=quilt.quilt_index,
                        patch_id=patch_id,
                    )
                )

            if not include_transfer:
                continue

            transfer_state = metrics.transfer_states_by_patch.get((quilt.quilt_index, patch_id))
            if transfer_state is None:
                continue
            if transfer_state.conflicting_uv_targets > 0:
                anomalies.append(
                    ReportAnomaly(
                        priority=3,
                        magnitude=float(transfer_state.conflicting_uv_targets),
                        address=patch_addr,
                        code="transfer_conflict",
                        detail=(
                            f"conflicts:{transfer_state.conflicting_uv_targets} "
                            f"resolved:{transfer_state.resolved_scaffold_points}/{transfer_state.scaffold_points} "
                            f"pins:{transfer_state.pinned_uv_targets}/{transfer_state.unpinned_uv_targets}"
                        ),
                        quilt_index=quilt.quilt_index,
                        patch_id=patch_id,
                    )
                )
            if transfer_state.missing_uv_targets > 0:
                anomalies.append(
                    ReportAnomaly(
                        priority=4,
                        magnitude=float(transfer_state.missing_uv_targets),
                        address=patch_addr,
                        code="missing_uv_targets",
                        detail=(
                            f"missing:{transfer_state.missing_uv_targets} "
                            f"resolved:{transfer_state.uv_targets_resolved} "
                            f"status:{transfer_state.status.value}"
                        ),
                        quilt_index=quilt.quilt_index,
                        patch_id=patch_id,
                    )
                )
            if transfer_state.unresolved_scaffold_points > 0:
                anomalies.append(
                    ReportAnomaly(
                        priority=5,
                        magnitude=float(transfer_state.unresolved_scaffold_points),
                        address=patch_addr,
                        code="unresolved_scaffold",
                        detail=(
                            f"unresolved:{transfer_state.unresolved_scaffold_points} "
                            f"resolved:{transfer_state.resolved_scaffold_points}/{transfer_state.scaffold_points} "
                            f"status:{transfer_state.status.value}"
                        ),
                        quilt_index=quilt.quilt_index,
                        patch_id=patch_id,
                    )
                )
            if transfer_state.status == PatchTransferStatus.MISSING_PATCH:
                anomalies.append(
                    ReportAnomaly(
                        priority=0,
                        magnitude=1.0,
                        address=patch_addr,
                        code="missing_patch",
                        detail="transfer:missing",
                        quilt_index=quilt.quilt_index,
                        patch_id=patch_id,
                    )
                )

        telemetry = getattr(quilt, "frontier_telemetry", None)
        if telemetry is not None:
            for stall in telemetry.stall_records:
                if not _is_actionable_unresolved_stall(stall):
                    continue
                if stall.best_rejected_ref is not None:
                    stall_addr = format_chain_address(stall.best_rejected_ref, quilt_index=quilt.quilt_index)
                    stall_patch_id: Optional[int] = stall.best_rejected_ref[0]
                else:
                    stall_addr = format_stall_address(stall.iteration, quilt_index=quilt.quilt_index)
                    stall_patch_id = None
                anomalies.append(
                    ReportAnomaly(
                        priority=3,
                        magnitude=max(abs(stall.best_rejected_score), float(stall.available_count)),
                        address=stall_addr,
                        code="stall_unresolved",
                        detail=(
                            f"score:{stall.best_rejected_score:.3f} "
                            f"available:{stall.available_count} "
                            f"no_anchor:{stall.no_anchor_count} "
                            f"rescue:{stall.rescue_attempted}={'Y' if stall.rescue_succeeded else 'N'}"
                        ),
                        quilt_index=quilt.quilt_index,
                        patch_id=stall_patch_id,
                        chain_ref=stall.best_rejected_ref,
                    )
                )

        closure_reports = getattr(quilt, "closure_seam_reports", ())
        for report in closure_reports:
            seam_addr = format_chain_pair_address(
                (report.owner_patch_id, report.owner_loop_index, report.owner_chain_index),
                (report.target_patch_id, report.target_loop_index, report.target_chain_index),
                quilt_index=quilt.quilt_index,
            )
            max_axis_error = max(report.owner_axis_error, report.target_axis_error)
            if report.span_mismatch > SCAFFOLD_CLOSURE_EPSILON:
                anomalies.append(
                    ReportAnomaly(
                        priority=4,
                        magnitude=report.span_mismatch,
                        address=seam_addr,
                        code="closure_seam_mismatch",
                        detail=(
                            f"mismatch:{report.span_mismatch:.6f} "
                            f"phase:{report.axis_phase_offset_max:.6f} "
                            f"delta:{report.shared_uv_delta_max:.6f}"
                        ),
                        quilt_index=quilt.quilt_index,
                        patch_id=report.owner_patch_id,
                        chain_ref=(report.owner_patch_id, report.owner_loop_index, report.owner_chain_index),
                        peer_chain_ref=(report.target_patch_id, report.target_loop_index, report.target_chain_index),
                    )
                )
            elif (
                report.axis_phase_offset_max > _ANOMALY_MIN_AXIS_PHASE
                or max_axis_error > _ANOMALY_MIN_AXIS_ERROR
                or report.shared_uv_delta_max > _ANOMALY_MIN_SHARED_DELTA
            ):
                anomalies.append(
                    ReportAnomaly(
                        priority=5,
                        magnitude=max(report.axis_phase_offset_max, max_axis_error, report.shared_uv_delta_max),
                        address=seam_addr,
                        code="axis_drift",
                        detail=(
                            f"phase:{report.axis_phase_offset_max:.6f} "
                            f"axis:{max_axis_error:.6f} "
                            f"delta:{report.shared_uv_delta_max:.6f}"
                        ),
                        quilt_index=quilt.quilt_index,
                        patch_id=report.owner_patch_id,
                        chain_ref=(report.owner_patch_id, report.owner_loop_index, report.owner_chain_index),
                        peer_chain_ref=(report.target_patch_id, report.target_loop_index, report.target_chain_index),
                    )
                )

        frame_reports = getattr(quilt, "frame_alignment_reports", ())
        for report in frame_reports:
            if report.scatter_max <= _frame_scatter_threshold(report.axis_kind):
                continue

            worst_ref: Optional[ChainRef] = None
            worst_scatter = -1.0
            for member_ref in report.member_refs:
                chain_placement = chain_map.get(member_ref)
                if chain_placement is None:
                    continue
                member_scatter = abs(_chain_cross_uv(chain_placement) - report.target_cross_uv)
                if member_scatter > worst_scatter:
                    worst_scatter = member_scatter
                    worst_ref = member_ref

            if worst_ref is None:
                continue

            anomalies.append(
                ReportAnomaly(
                    priority=6,
                    magnitude=worst_scatter,
                    address=format_chain_address(worst_ref, quilt_index=quilt.quilt_index),
                    code="frame_scatter",
                    detail=(
                        f"scatter:{worst_scatter:.6f} "
                        f"target:{report.target_cross_uv:.6f} "
                        f"chains:{report.chain_count}"
                    ),
                    quilt_index=quilt.quilt_index,
                    patch_id=worst_ref[0],
                    chain_ref=worst_ref,
                )
            )

        for chain_ref, chain_placement in chain_map.items():
            anomaly = _make_hv_chain_anomaly(
                chain_ref,
                quilt.quilt_index,
                chain_placement,
                telemetry_map.get(chain_ref),
            )
            if anomaly is not None:
                anomalies.append(anomaly)

    anomalies = _dedupe_anomalies(anomalies)
    anomalies.sort(key=lambda item: (item.priority, -item.magnitude, item.address, item.code))
    return tuple(anomalies)


def format_scaffold_anomaly_lines(anomalies: tuple[ReportAnomaly, ...]) -> list[str]:
    if not anomalies:
        return ["Anomalies: none"]

    lines = [f"Anomalies: {len(anomalies)}"]
    for anomaly in anomalies:
        lines.append(f"  - {anomaly.address} {anomaly.code} {anomaly.detail}")
    return lines


def collect_scaffold_anomaly_lines(
    graph: PatchGraph,
    scaffold_map: ScaffoldMap,
    metrics: ScaffoldMetricsSummary,
    *,
    include_transfer: bool,
) -> list[str]:
    return format_scaffold_anomaly_lines(
        collect_scaffold_anomalies(
            graph,
            scaffold_map,
            metrics,
            include_transfer=include_transfer,
        )
    )
