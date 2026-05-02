from __future__ import annotations

try:
    from .model import FormattedReport
    from .analysis_reporting import (
        _serialize_patch_graph_report_summary,
        _serialize_patch_graph_snapshot_summary,
        _serialize_patch_graph_report_lines,
        _serialize_patch_graph_snapshot_lines,
        _build_patch_graph_console_view,
    )
    from .analysis_corners import (
        _measure_chain_axis_metrics,
    )
    from .analysis_derived import (
        _build_patch_graph_derived_topology as _build_patch_graph_derived_topology_unvalidated,
    )
    from .analysis_topology import (
        validate_solver_input_mesh,
        format_solver_input_preflight_report,
        get_expanded_islands,
        build_patch_graph,
        _report_graph_topology_invariant_violation,
        _report_junction_invariant_violation,
    )
    from .analysis_validation import (
        _validate_patch_graph_junctions as _validate_patch_graph_junctions_impl,
        _validate_patch_graph_derived_topology as _validate_patch_graph_derived_topology_impl,
        _validate_patch_graph_console_view as _validate_patch_graph_console_view_impl,
    )
except ImportError:
    from model import FormattedReport
    from analysis_reporting import (
        _serialize_patch_graph_report_summary,
        _serialize_patch_graph_snapshot_summary,
        _serialize_patch_graph_report_lines,
        _serialize_patch_graph_snapshot_lines,
        _build_patch_graph_console_view,
    )
    from analysis_corners import (
        _measure_chain_axis_metrics,
    )
    from analysis_derived import (
        _build_patch_graph_derived_topology as _build_patch_graph_derived_topology_unvalidated,
    )
    from analysis_topology import (
        validate_solver_input_mesh,
        format_solver_input_preflight_report,
        get_expanded_islands,
        build_patch_graph,
        _report_graph_topology_invariant_violation,
        _report_junction_invariant_violation,
    )
    from analysis_validation import (
        _validate_patch_graph_junctions as _validate_patch_graph_junctions_impl,
        _validate_patch_graph_derived_topology as _validate_patch_graph_derived_topology_impl,
        _validate_patch_graph_console_view as _validate_patch_graph_console_view_impl,
    )


def _build_patch_graph_derived_topology(graph):
    """Build the canonical derived topology bundle over the final PatchGraph."""

    derived_topology = _build_patch_graph_derived_topology_unvalidated(
        graph,
        _measure_chain_axis_metrics,
    )
    _validate_patch_graph_junctions(graph, derived_topology)
    _validate_patch_graph_derived_topology(graph, derived_topology)
    return derived_topology


def build_patch_graph_derived_topology(graph):
    """Public facade for canonical derived topology over PatchGraph."""

    return _build_patch_graph_derived_topology(graph)


def _validate_patch_graph_junctions(graph, derived_topology):
    return _validate_patch_graph_junctions_impl(
        graph,
        derived_topology,
        _report_junction_invariant_violation,
    )


def _validate_patch_graph_derived_topology(graph, derived_topology):
    return _validate_patch_graph_derived_topology_impl(
        graph,
        derived_topology,
        _report_graph_topology_invariant_violation,
    )


def _validate_patch_graph_console_view(derived_topology, console_view):
    return _validate_patch_graph_console_view_impl(
        derived_topology,
        console_view,
        _report_graph_topology_invariant_violation,
    )


def _build_patch_graph_console_view_validated(graph, derived_topology):
    """Build and validate typed console/snapshot view rows."""

    console_view = _build_patch_graph_console_view(graph, derived_topology)
    _validate_patch_graph_console_view(derived_topology, console_view)
    return console_view


def build_neighbor_inherited_roles(graph):
    """Extract chain-level inherited role map from structural interpretation.

    Returns dict[ChainRef, (FrameRole, source_patch_id)] — the same structural
    facts computed by the analysis layer, exposed for solve/frontier consumption.
    """
    derived_topology = _build_patch_graph_derived_topology(graph)
    return dict(derived_topology.neighbor_inherited_roles)


def build_straighten_structural_support(graph):
    """Extract structural support facts for straighten-aware solve/runtime."""

    derived_topology = _build_patch_graph_derived_topology(graph)
    return (
        dict(derived_topology.neighbor_inherited_roles),
        dict(derived_topology.patch_summaries_by_id),
        dict(derived_topology.patch_shape_classes),
        derived_topology.straighten_chain_refs,
        dict(derived_topology.band_spine_data),
    )


def format_patch_graph_report(graph, mesh_name=None) -> FormattedReport:
    """Build text lines for the System Console PatchGraph report."""

    derived_topology = _build_patch_graph_derived_topology(graph)
    console_view = _build_patch_graph_console_view_validated(graph, derived_topology)
    return FormattedReport(
        lines=_serialize_patch_graph_report_lines(console_view, mesh_name=mesh_name),
        summary=_serialize_patch_graph_report_summary(console_view),
    )


def format_patch_graph_snapshot_report(graph, mesh_name=None) -> FormattedReport:
    """Build a compact, stable PatchGraph snapshot for regression baselines."""

    derived_topology = _build_patch_graph_derived_topology(graph)
    console_view = _build_patch_graph_console_view_validated(graph, derived_topology)
    return FormattedReport(
        lines=_serialize_patch_graph_snapshot_lines(console_view, mesh_name=mesh_name),
        summary=_serialize_patch_graph_snapshot_summary(console_view),
    )




