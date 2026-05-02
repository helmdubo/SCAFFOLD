from __future__ import annotations

from dataclasses import dataclass, field

from mathutils import Vector

try:
    from .model import FrameAxisKind, PatchGraph, ScaffoldMap, ScaffoldQuiltPlacement
    from .solve_records import PatchTransferStatus, PatchTransferTargetsState
    from .solve_transfer import _build_patch_transfer_targets
except ImportError:
    from model import FrameAxisKind, PatchGraph, ScaffoldMap, ScaffoldQuiltPlacement
    from solve_records import PatchTransferStatus, PatchTransferTargetsState
    from solve_transfer import _build_patch_transfer_targets


ReportPatchKey = tuple[int, int]


@dataclass(frozen=True)
class ScaffoldMetricsSummary:
    """Сводка агрегатов scaffold/reporting без влияния на solve."""

    quilt_count: int = 0
    graph_patch_count: int = 0
    scaffold_report_patch_count: int = 0
    unsupported_report_patch_count: int = 0
    unsupported_patch_ids: tuple[int, ...] = ()
    invalid_closure_patch_ids: tuple[int, ...] = ()
    closure_seam_count: int = 0
    max_closure_span_mismatch: float = 0.0
    max_closure_axis_phase: float = 0.0
    frame_group_count: int = 0
    max_row_scatter: float = 0.0
    max_column_scatter: float = 0.0
    unresolved_stall_count: int = 0
    transfer_scaffold_points: int = 0
    transfer_resolved_scaffold_points: int = 0
    transfer_uv_targets_resolved: int = 0
    transfer_unresolved_scaffold_points: int = 0
    transfer_missing_uv_targets: int = 0
    transfer_conflicting_uv_targets: int = 0
    transfer_pinned_uv_targets: int = 0
    transfer_unpinned_uv_targets: int = 0
    transfer_invalid_scaffold_patch_count: int = 0
    transfer_missing_patch_count: int = 0
    transfer_states_by_patch: dict[ReportPatchKey, PatchTransferTargetsState] = field(default_factory=dict)


def collect_report_quilt_patch_ids(quilt: ScaffoldQuiltPlacement) -> list[int]:
    """Порядок patch ids для root scaffold report."""

    patch_ids: list[int] = []
    for patch_id in [quilt.root_patch_id] + [pid for pid in quilt.patches.keys() if pid != quilt.root_patch_id]:
        if patch_id not in quilt.patches:
            continue
        patch_ids.append(patch_id)
    if not patch_ids:
        patch_ids = [quilt.root_patch_id]
    return patch_ids


def collect_scaffold_metrics(
    graph: PatchGraph,
    scaffold_map: ScaffoldMap,
    *,
    bm=None,
) -> ScaffoldMetricsSummary:
    """Общий collector агрегатов для root report и regression snapshot."""

    unsupported_patch_ids: set[int] = set()
    invalid_closure_patch_ids: set[int] = set()
    transfer_states_by_patch: dict[ReportPatchKey, PatchTransferTargetsState] = {}

    scaffold_report_patch_count = 0
    unsupported_report_patch_count = 0
    closure_seam_count = 0
    max_closure_span_mismatch = 0.0
    max_closure_axis_phase = 0.0
    frame_group_count = 0
    max_row_scatter = 0.0
    max_column_scatter = 0.0
    unresolved_stall_count = 0

    transfer_scaffold_points = 0
    transfer_resolved_scaffold_points = 0
    transfer_uv_targets_resolved = 0
    transfer_unresolved_scaffold_points = 0
    transfer_missing_uv_targets = 0
    transfer_conflicting_uv_targets = 0
    transfer_pinned_uv_targets = 0
    transfer_unpinned_uv_targets = 0
    transfer_invalid_scaffold_patch_count = 0
    transfer_missing_patch_count = 0

    for quilt in scaffold_map.quilts:
        report_patch_ids = collect_report_quilt_patch_ids(quilt)
        scaffold_report_patch_count += len(report_patch_ids)

        for patch_id in report_patch_ids:
            patch_placement = quilt.patches.get(patch_id)
            if patch_placement is None or patch_placement.notes:
                unsupported_report_patch_count += 1

        closure_reports = getattr(quilt, "closure_seam_reports", ())
        closure_seam_count += len(closure_reports)
        if closure_reports:
            max_closure_span_mismatch = max(
                max_closure_span_mismatch,
                max((report.span_mismatch for report in closure_reports), default=0.0),
            )
            max_closure_axis_phase = max(
                max_closure_axis_phase,
                max((report.axis_phase_offset_max for report in closure_reports), default=0.0),
            )

        frame_reports = getattr(quilt, "frame_alignment_reports", ())
        frame_group_count += len(frame_reports)
        if frame_reports:
            max_row_scatter = max(
                max_row_scatter,
                max(
                    (report.scatter_max for report in frame_reports if report.axis_kind == FrameAxisKind.ROW),
                    default=0.0,
                ),
            )
            max_column_scatter = max(
                max_column_scatter,
                max(
                    (report.scatter_max for report in frame_reports if report.axis_kind == FrameAxisKind.COLUMN),
                    default=0.0,
                ),
            )

        telemetry = getattr(quilt, "frontier_telemetry", None)
        if telemetry is not None:
            unresolved_stall_count += int(getattr(telemetry, "stalls_unresolved", 0))

        for patch_id, patch_placement in quilt.patches.items():
            if patch_placement is None or patch_placement.notes or not patch_placement.closure_valid:
                unsupported_patch_ids.add(patch_id)
            if patch_placement is not None and not patch_placement.notes and not patch_placement.closure_valid:
                invalid_closure_patch_ids.add(patch_id)

            if bm is None:
                continue

            if patch_placement is None:
                transfer_state = PatchTransferTargetsState(status=PatchTransferStatus.MISSING_PATCH)
            else:
                transfer_state = _build_patch_transfer_targets(
                    bm,
                    graph,
                    patch_placement,
                    Vector((0.0, 0.0)),
                )
            transfer_states_by_patch[(quilt.quilt_index, patch_id)] = transfer_state

            transfer_scaffold_points += int(transfer_state.scaffold_points)
            transfer_resolved_scaffold_points += int(transfer_state.resolved_scaffold_points)
            transfer_uv_targets_resolved += int(transfer_state.uv_targets_resolved)
            transfer_unresolved_scaffold_points += int(transfer_state.unresolved_scaffold_points)
            transfer_missing_uv_targets += int(transfer_state.missing_uv_targets)
            transfer_conflicting_uv_targets += int(transfer_state.conflicting_uv_targets)
            transfer_pinned_uv_targets += int(transfer_state.pinned_uv_targets)
            transfer_unpinned_uv_targets += int(transfer_state.unpinned_uv_targets)
            transfer_invalid_scaffold_patch_count += int(transfer_state.invalid_scaffold_patches)
            if transfer_state.status == PatchTransferStatus.MISSING_PATCH:
                transfer_missing_patch_count += 1

    return ScaffoldMetricsSummary(
        quilt_count=len(scaffold_map.quilts),
        graph_patch_count=len(graph.nodes),
        scaffold_report_patch_count=scaffold_report_patch_count,
        unsupported_report_patch_count=unsupported_report_patch_count,
        unsupported_patch_ids=tuple(sorted(unsupported_patch_ids)),
        invalid_closure_patch_ids=tuple(sorted(invalid_closure_patch_ids)),
        closure_seam_count=closure_seam_count,
        max_closure_span_mismatch=max_closure_span_mismatch,
        max_closure_axis_phase=max_closure_axis_phase,
        frame_group_count=frame_group_count,
        max_row_scatter=max_row_scatter,
        max_column_scatter=max_column_scatter,
        unresolved_stall_count=unresolved_stall_count,
        transfer_scaffold_points=transfer_scaffold_points,
        transfer_resolved_scaffold_points=transfer_resolved_scaffold_points,
        transfer_uv_targets_resolved=transfer_uv_targets_resolved,
        transfer_unresolved_scaffold_points=transfer_unresolved_scaffold_points,
        transfer_missing_uv_targets=transfer_missing_uv_targets,
        transfer_conflicting_uv_targets=transfer_conflicting_uv_targets,
        transfer_pinned_uv_targets=transfer_pinned_uv_targets,
        transfer_unpinned_uv_targets=transfer_unpinned_uv_targets,
        transfer_invalid_scaffold_patch_count=transfer_invalid_scaffold_patch_count,
        transfer_missing_patch_count=transfer_missing_patch_count,
        transfer_states_by_patch=transfer_states_by_patch,
    )
