from __future__ import annotations

from dataclasses import dataclass, field

try:
    from .constants import CORNER_ANGLE_THRESHOLD_DEG
    from .model import ChainNeighborKind, FrameRole
except ImportError:
    from constants import CORNER_ANGLE_THRESHOLD_DEG
    from model import ChainNeighborKind, FrameRole


@dataclass(frozen=True)
class _LabelSequenceView:
    labels: tuple[str, ...] = ()


@dataclass(frozen=True)
class _PatchGraphJunctionReportSummary:
    total_junctions: int = 0
    interesting_junctions: tuple[object, ...] = ()
    open_junction_count: int = 0
    valence_histogram: tuple[tuple[int, int], ...] = ()

    @property
    def closed_junction_count(self) -> int:
        return max(0, self.total_junctions - self.open_junction_count)


@dataclass(frozen=True)
class _ChainConsoleView:
    chain_index: int
    role: str
    is_bridge: bool
    neighbor_kind: str
    neighbor_suffix: str
    transition: str
    start_vert_index: int
    end_vert_index: int
    start_corner_label: str
    end_corner_label: str
    edge_count: int
    length_3d: float
    start_endpoint_ref_labels: _LabelSequenceView = field(default_factory=_LabelSequenceView)
    end_endpoint_ref_labels: _LabelSequenceView = field(default_factory=_LabelSequenceView)


@dataclass(frozen=True)
class _RunConsoleView:
    run_index: int
    dominant_role: str
    start_corner_label: str
    end_corner_label: str
    total_length: float
    support_length: float
    gap_free_length: float
    max_free_gap_length: float
    projected_u_span: float
    projected_v_span: float
    chain_index_labels: _LabelSequenceView = field(default_factory=_LabelSequenceView)


@dataclass(frozen=True)
class _CornerConsoleView:
    corner_index: int
    corner_kind: str
    corner_type: str
    prev_chain_index: int
    next_chain_index: int
    vert_index: int
    turn_angle_deg: float
    is_sharp: bool


@dataclass(frozen=True)
class _LoopConsoleView:
    loop_index: int
    kind: str
    chain_count: int
    corner_count: int
    chain_views: tuple[_ChainConsoleView, ...] = ()
    run_views: tuple[_RunConsoleView, ...] = ()
    corner_views: tuple[_CornerConsoleView, ...] = ()


@dataclass(frozen=True)
class _PatchConsoleView:
    patch_id: int
    semantic_key: str
    patch_type: str
    world_facing: str
    face_count: int
    hole_count: int
    run_count: int
    chain_count: int
    corner_count: int
    h_count: int
    v_count: int
    free_count: int
    loop_kind_labels: _LabelSequenceView = field(default_factory=_LabelSequenceView)
    role_labels: _LabelSequenceView = field(default_factory=_LabelSequenceView)
    loop_views: tuple[_LoopConsoleView, ...] = ()
    # Structural interpretation fields
    strip_confidence: float = 0.0
    straighten_eligible: bool = False
    spine_axis: str = ""
    spine_length: float = 0.0
    terminal_count: int = 0
    branch_count: int = 0
    basis_u: str = ""
    basis_v: str = ""
    normal: str = ""


@dataclass(frozen=True)
class _JunctionConsoleView:
    vert_index: int
    valence: int
    is_open: bool
    has_mesh_border: bool
    has_seam_self: bool
    h_count: int
    v_count: int
    free_count: int
    patch_ref_labels: _LabelSequenceView = field(default_factory=_LabelSequenceView)
    signature_labels: _LabelSequenceView = field(default_factory=_LabelSequenceView)
    corner_ref_labels: _LabelSequenceView = field(default_factory=_LabelSequenceView)
    chain_ref_labels: _LabelSequenceView = field(default_factory=_LabelSequenceView)
    run_ref_labels: _LabelSequenceView = field(default_factory=_LabelSequenceView)


@dataclass(frozen=True)
class _PatchGraphSummaryConsoleView:
    valence_labels: _LabelSequenceView = field(default_factory=_LabelSequenceView)
    total_junctions: int = 0
    interesting_junction_count: int = 0
    open_junction_count: int = 0
    closed_junction_count: int = 0


@dataclass(frozen=True)
class _PatchGraphConsoleView:
    patch_views: tuple[_PatchConsoleView, ...] = ()
    junction_views: tuple[_JunctionConsoleView, ...] = ()
    aggregate_counts: object = None
    junction_summary: _PatchGraphJunctionReportSummary = field(default_factory=_PatchGraphJunctionReportSummary)
    summary_view: _PatchGraphSummaryConsoleView = field(default_factory=_PatchGraphSummaryConsoleView)


def _build_label_sequence_view(labels):
    return _LabelSequenceView(labels=tuple(labels))


def _format_label_sequence_view(label_view):
    if not label_view.labels:
        return "[]"
    return "[" + " ".join(label_view.labels) + "]"


def _build_chain_ref_labels(chain_refs):
    return _build_label_sequence_view(
        f"L{loop_index}C{chain_index}" for loop_index, chain_index in chain_refs
    )


def _build_frame_run_chain_index_labels(chain_indices):
    return _build_label_sequence_view(
        f"C{chain_index}" for chain_index in chain_indices
    )


def _build_patch_id_labels(patch_ids):
    return _build_label_sequence_view(
        f"P{patch_id}" for patch_id in patch_ids
    )


def _build_junction_corner_ref_labels(corner_refs):
    return _build_label_sequence_view(
        f"P{corner_ref.patch_id}L{corner_ref.loop_index}K{corner_ref.corner_index}"
        for corner_ref in corner_refs
    )


def _build_junction_chain_ref_labels(chain_refs):
    return _build_label_sequence_view(
        f"P{chain_ref.patch_id}L{chain_ref.loop_index}C{chain_ref.chain_index}"
        for chain_ref in chain_refs
    )


def _build_junction_run_ref_labels(run_endpoint_refs):
    return _build_label_sequence_view(
        f"P{run_ref.patch_id}L{run_ref.loop_index}R{run_ref.run_index}:{run_ref.endpoint_kind}"
        for run_ref in run_endpoint_refs
    )


def _build_junction_role_signature_labels(role_signature):
    return _build_label_sequence_view(
        f"{role_pair.prev_role.value}->{role_pair.next_role.value}"
        for role_pair in role_signature
    )


def _build_patch_graph_junction_report_summary(derived_topology):
    """Build presentation-only junction aggregates over canonical derived topology."""

    interesting_junctions = sorted(
        [
            junction
            for junction in derived_topology.junctions
            if junction.valence >= 2 or junction.has_seam_self
        ],
        key=lambda junction: (
            0 if not junction.is_open else 1,
            -junction.valence,
            junction.vert_index,
        ),
    )

    valence_histogram: dict[int, int] = {}
    open_junction_count = 0
    for junction in derived_topology.junctions:
        valence_histogram[junction.valence] = valence_histogram.get(junction.valence, 0) + 1
        if junction.is_open:
            open_junction_count += 1

    return _PatchGraphJunctionReportSummary(
        total_junctions=len(derived_topology.junctions),
        interesting_junctions=tuple(interesting_junctions),
        open_junction_count=open_junction_count,
        valence_histogram=tuple(sorted(valence_histogram.items())),
    )


def _build_patch_graph_summary_console_view(junction_summary):
    """Build typed summary/count labels over canonical junction report summary."""

    return _PatchGraphSummaryConsoleView(
        valence_labels=_build_label_sequence_view(
            f"v{valence}:{count}" for valence, count in junction_summary.valence_histogram
        ),
        total_junctions=junction_summary.total_junctions,
        interesting_junction_count=len(junction_summary.interesting_junctions),
        open_junction_count=junction_summary.open_junction_count,
        closed_junction_count=junction_summary.closed_junction_count,
    )


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


def _chain_length(chain):
    """Compute a polyline length for the debug/report view."""

    if len(chain.vert_cos) < 2:
        return 0.0

    length = 0.0
    for index in range(len(chain.vert_cos) - 1):
        length += (chain.vert_cos[index + 1] - chain.vert_cos[index]).length
    return length


def _build_chain_console_view(graph, patch_id, loop_index, chain_index, chain):
    """Build one typed chain console view."""

    role = _enum_value(chain.frame_role)
    neighbor_kind = _enum_value(chain.neighbor_kind)
    neighbor_suffix = ""
    if neighbor_kind == ChainNeighborKind.PATCH.value:
        neighbor_node = graph.nodes.get(chain.neighbor_patch_id)
        neighbor_semantic = graph.get_patch_semantic_key(chain.neighbor_patch_id) if neighbor_node else "UNKNOWN"
        neighbor_suffix = f" -> Patch {chain.neighbor_patch_id}:{neighbor_semantic}"

    endpoint_neighbors = graph.get_chain_endpoint_neighbors(patch_id, loop_index, chain_index)
    return _ChainConsoleView(
        chain_index=chain_index,
        role=role,
        is_bridge=(role == FrameRole.FREE.value and len(chain.vert_cos) <= 2),
        neighbor_kind=neighbor_kind,
        neighbor_suffix=neighbor_suffix,
        transition=graph.describe_chain_transition(patch_id, chain),
        start_vert_index=chain.start_vert_index,
        end_vert_index=chain.end_vert_index,
        start_corner_label=str(chain.start_corner_index) if chain.start_corner_index >= 0 else "-",
        end_corner_label=str(chain.end_corner_index) if chain.end_corner_index >= 0 else "-",
        edge_count=len(chain.edge_indices),
        length_3d=_chain_length(chain),
        start_endpoint_ref_labels=_build_chain_ref_labels(endpoint_neighbors["start"]),
        end_endpoint_ref_labels=_build_chain_ref_labels(endpoint_neighbors["end"]),
    )


def _build_run_console_view(run_index, frame_run):
    """Build one typed frame-run console view."""

    return _RunConsoleView(
        run_index=run_index,
        dominant_role=frame_run.dominant_role.value,
        start_corner_label=str(frame_run.start_corner_index) if frame_run.start_corner_index >= 0 else "-",
        end_corner_label=str(frame_run.end_corner_index) if frame_run.end_corner_index >= 0 else "-",
        total_length=frame_run.total_length,
        support_length=frame_run.support_length,
        gap_free_length=frame_run.gap_free_length,
        max_free_gap_length=frame_run.max_free_gap_length,
        projected_u_span=frame_run.projected_u_span,
        projected_v_span=frame_run.projected_v_span,
        chain_index_labels=_build_frame_run_chain_index_labels(frame_run.chain_indices),
    )


def _build_corner_console_view(corner_index, corner):
    """Build one typed corner console view."""

    return _CornerConsoleView(
        corner_index=corner_index,
        corner_kind=corner.corner_kind.value,
        corner_type=corner.corner_type,
        prev_chain_index=corner.prev_chain_index,
        next_chain_index=corner.next_chain_index,
        vert_index=corner.vert_index,
        turn_angle_deg=corner.turn_angle_deg,
        is_sharp=(corner.turn_angle_deg >= CORNER_ANGLE_THRESHOLD_DEG),
    )


def _build_loop_console_view(graph, patch_id, loop_summary, boundary_loop, frame_runs_by_loop):
    """Build one typed loop console view."""

    chain_records = boundary_loop.iter_oriented_chain_records()
    if not chain_records:
        chain_records = tuple(
            (graph.get_chain_use(patch_id, loop_summary.loop_index, chain_index), chain)
            for chain_index, chain in enumerate(boundary_loop.chains)
        )

    chain_views = tuple(
        _build_chain_console_view(graph, patch_id, loop_summary.loop_index, chain_use.chain_index, chain)
        for chain_use, chain in chain_records
        if chain_use is not None
    )
    run_views = tuple(
        _build_run_console_view(run_index, frame_run)
        for run_index, frame_run in enumerate(frame_runs_by_loop.get((patch_id, loop_summary.loop_index), ()))
    )
    corner_views = tuple(
        _build_corner_console_view(corner_index, corner)
        for corner_index, corner in enumerate(boundary_loop.corners)
    )
    return _LoopConsoleView(
        loop_index=loop_summary.loop_index,
        kind=_enum_value(loop_summary.kind),
        chain_count=loop_summary.chain_count,
        corner_count=loop_summary.corner_count,
        chain_views=chain_views,
        run_views=run_views,
        corner_views=corner_views,
    )


def _build_patch_console_view(graph, patch_summary, frame_runs_by_loop):
    """Build one typed patch console view in canonical derived order."""

    node = graph.nodes.get(patch_summary.patch_id)
    if node is None:
        return None

    loop_views = []
    for loop_summary in patch_summary.loop_summaries:
        loop_index = loop_summary.loop_index
        if loop_index < 0 or loop_index >= len(node.boundary_loops):
            continue
        loop_views.append(
            _build_loop_console_view(
                graph,
                patch_summary.patch_id,
                loop_summary,
                node.boundary_loops[loop_index],
                frame_runs_by_loop,
            )
        )

    return _PatchConsoleView(
        patch_id=patch_summary.patch_id,
        semantic_key=patch_summary.semantic_key,
        patch_type=_enum_value(patch_summary.patch_type),
        world_facing=_enum_value(patch_summary.world_facing),
        face_count=patch_summary.face_count,
        hole_count=patch_summary.hole_count,
        run_count=patch_summary.run_count,
        chain_count=patch_summary.chain_count,
        corner_count=patch_summary.corner_count,
        h_count=patch_summary.h_count,
        v_count=patch_summary.v_count,
        free_count=patch_summary.free_count,
        loop_kind_labels=_build_label_sequence_view(
            _enum_value(kind) for kind in patch_summary.loop_kinds
        ),
        role_labels=_build_label_sequence_view(
            _enum_value(role) for role in patch_summary.role_sequence
        ),
        loop_views=tuple(loop_views),
        strip_confidence=patch_summary.strip_confidence,
        straighten_eligible=patch_summary.straighten_eligible,
        spine_axis=_enum_value(patch_summary.spine_axis) if hasattr(patch_summary.spine_axis, 'value') else str(patch_summary.spine_axis),
        spine_length=patch_summary.spine_length,
        terminal_count=patch_summary.terminal_count,
        branch_count=patch_summary.branch_count,
        basis_u=f"({node.basis_u.x:.4f},{node.basis_u.y:.4f},{node.basis_u.z:.4f})",
        basis_v=f"({node.basis_v.x:.4f},{node.basis_v.y:.4f},{node.basis_v.z:.4f})",
        normal=f"({node.normal.x:.4f},{node.normal.y:.4f},{node.normal.z:.4f})",
    )


def _build_junction_console_view(junction):
    """Build one typed junction console view."""

    return _JunctionConsoleView(
        vert_index=junction.vert_index,
        valence=junction.valence,
        is_open=junction.is_open,
        has_mesh_border=junction.has_mesh_border,
        has_seam_self=junction.has_seam_self,
        h_count=junction.h_count,
        v_count=junction.v_count,
        free_count=junction.free_count,
        patch_ref_labels=_build_patch_id_labels(junction.patch_ids),
        signature_labels=_build_junction_role_signature_labels(junction.role_signature),
        corner_ref_labels=_build_junction_corner_ref_labels(junction.corner_refs),
        chain_ref_labels=_build_junction_chain_ref_labels(junction.chain_refs),
        run_ref_labels=_build_junction_run_ref_labels(junction.run_endpoint_refs),
    )


def _build_patch_graph_console_view(graph, derived_topology):
    """Build typed console/snapshot view rows over canonical derived topology."""

    junction_summary = _build_patch_graph_junction_report_summary(derived_topology)
    patch_views = tuple(
        patch_view
        for patch_view in (
            _build_patch_console_view(graph, patch_summary, derived_topology.frame_runs_by_loop)
            for patch_summary in derived_topology.patch_summaries
        )
        if patch_view is not None
    )
    junction_views = tuple(
        _build_junction_console_view(junction)
        for junction in junction_summary.interesting_junctions
    )
    return _PatchGraphConsoleView(
        patch_views=patch_views,
        junction_views=junction_views,
        aggregate_counts=derived_topology.aggregate_counts,
        junction_summary=junction_summary,
        summary_view=_build_patch_graph_summary_console_view(junction_summary),
    )


def _serialize_chain_console_view(chain_view):
    """Serialize one typed chain console view into a stable report line."""

    bridge_tag = " [BRIDGE]" if chain_view.is_bridge else ""
    return (
        f"      Chain {chain_view.chain_index}: {chain_view.role}{bridge_tag} | "
        f"neighbor:{chain_view.neighbor_kind}{chain_view.neighbor_suffix} | transition:{chain_view.transition} | "
        f"verts:{chain_view.start_vert_index}->{chain_view.end_vert_index} | "
        f"corners:{chain_view.start_corner_label}->{chain_view.end_corner_label} | "
        f"ep:start{_format_label_sequence_view(chain_view.start_endpoint_ref_labels)} "
        f"end{_format_label_sequence_view(chain_view.end_endpoint_ref_labels)} | "
        f"edges:{chain_view.edge_count} | length:{chain_view.length_3d:.4f}"
    )


def _serialize_run_console_view(run_view):
    """Serialize one typed frame-run console view into a stable report line."""

    return (
        f"      Run {run_view.run_index}: {run_view.dominant_role} | "
        f"chains:{_format_label_sequence_view(run_view.chain_index_labels)} | "
        f"corners:{run_view.start_corner_label}->{run_view.end_corner_label} | "
        f"total:{run_view.total_length:.4f} support:{run_view.support_length:.4f} "
        f"free_gap:{run_view.gap_free_length:.4f} max_gap:{run_view.max_free_gap_length:.4f} | "
        f"span:u={run_view.projected_u_span:.4f} v={run_view.projected_v_span:.4f}"
    )


def _serialize_corner_console_view(corner_view):
    """Serialize one typed corner console view into a stable report line."""

    return (
        f"      Corner {corner_view.corner_index}: {corner_view.corner_kind} {corner_view.corner_type} | "
        f"chains:{corner_view.prev_chain_index}->{corner_view.next_chain_index} | "
        f"vert:{corner_view.vert_index} | turn:{corner_view.turn_angle_deg:.1f} | "
        f"sharp:{'Y' if corner_view.is_sharp else 'N'}"
    )


def _serialize_loop_console_view(loop_view):
    """Serialize one typed loop console view into stable report lines."""

    lines = [
        f"    Loop {loop_view.loop_index}: {loop_view.kind} | chains:{loop_view.chain_count} corners:{loop_view.corner_count}"
    ]
    lines.extend(_serialize_chain_console_view(chain_view) for chain_view in loop_view.chain_views)
    lines.extend(_serialize_run_console_view(run_view) for run_view in loop_view.run_views)
    lines.extend(_serialize_corner_console_view(corner_view) for corner_view in loop_view.corner_views)
    return lines


def _serialize_patch_console_view(patch_view):
    """Serialize one typed patch console view into stable report lines."""

    strip_tag = ""
    if patch_view.strip_confidence > 0.01 or patch_view.spine_length > 0.0:
        eligible_flag = "Y" if patch_view.straighten_eligible else "N"
        strip_tag = (
            f" | strip:{patch_view.strip_confidence:.2f} eligible:{eligible_flag}"
            f" spine:{patch_view.spine_axis} len:{patch_view.spine_length:.1f}"
            f" T:{patch_view.terminal_count} B:{patch_view.branch_count}"
        )
    basis_tag = ""
    if patch_view.basis_u:
        basis_tag = f"\n    basis: U={patch_view.basis_u} V={patch_view.basis_v} N={patch_view.normal}"
    lines = [
        f"  Patch {patch_view.patch_id}: {patch_view.patch_type} | facing:{patch_view.world_facing} | {patch_view.face_count}f | "
        f"loops:{len(patch_view.loop_views)}{_format_label_sequence_view(patch_view.loop_kind_labels)} "
        f"chains:{patch_view.chain_count} corners:{patch_view.corner_count} | "
        f"roles:{_format_label_sequence_view(patch_view.role_labels)}"
        f"{strip_tag}"
        f"{basis_tag}"
    ]
    for loop_view in patch_view.loop_views:
        lines.extend(_serialize_loop_console_view(loop_view))
    return lines


def _serialize_junction_console_view(junction_view):
    """Serialize one typed junction console view into a stable report line."""

    return (
        f"    Junction V{junction_view.vert_index}: valence:{junction_view.valence} "
        f"patches:{_format_label_sequence_view(junction_view.patch_ref_labels)} "
        f"open:{'Y' if junction_view.is_open else 'N'} border:{'Y' if junction_view.has_mesh_border else 'N'} "
        f"self:{'Y' if junction_view.has_seam_self else 'N'} | "
        f"roles:H{junction_view.h_count} V{junction_view.v_count} F{junction_view.free_count} | "
        f"signature:{_format_label_sequence_view(junction_view.signature_labels)} | "
        f"corners:{_format_label_sequence_view(junction_view.corner_ref_labels)} | "
        f"chains:{_format_label_sequence_view(junction_view.chain_ref_labels)} | "
        f"runs:{_format_label_sequence_view(junction_view.run_ref_labels)}"
    )


def _serialize_patch_graph_report_summary(console_view):
    """Serialize the full report summary over typed console view counts."""

    aggregate = console_view.aggregate_counts
    summary_view = console_view.summary_view
    return (
        f"Patches: {aggregate.total_patches} (W:{aggregate.walls} F:{aggregate.floors} S:{aggregate.slopes} 1f:{aggregate.singles}) | "
        f"Loops: {aggregate.total_loops} Chains: {aggregate.total_chains} Corners: {aggregate.total_corners} "
        f"Sharp:{aggregate.total_sharp_corners} Holes: {aggregate.total_holes} | "
        f"Roles: H:{aggregate.total_h} V:{aggregate.total_v} Free:{aggregate.total_free} | "
        f"Facing: Up:{aggregate.total_up} Down:{aggregate.total_down} Side:{aggregate.total_side} | "
        f"Neighbors: Patch:{aggregate.total_patch_links} Self:{aggregate.total_self_seams} Border:{aggregate.total_mesh_borders} | "
        f"Junctions: {summary_view.total_junctions} Interesting:{summary_view.interesting_junction_count}"
    )


def _serialize_patch_graph_snapshot_summary(console_view):
    """Serialize the stable snapshot summary over typed console view counts."""

    aggregate = console_view.aggregate_counts
    summary_view = console_view.summary_view
    return (
        f"PatchGraph snapshot | patches:{aggregate.total_patches} loops:{aggregate.total_loops} chains:{aggregate.total_chains} "
        f"corners:{aggregate.total_corners} runs:{aggregate.total_run_h + aggregate.total_run_v + aggregate.total_run_free} "
        f"junctions:{summary_view.total_junctions}"
    )


def _serialize_patch_graph_topology_line(console_view):
    """Serialize the snapshot topology totals line."""

    aggregate = console_view.aggregate_counts
    return (
        f"patches:{aggregate.total_patches} loops:{aggregate.total_loops} chains:{aggregate.total_chains} "
        f"corners:{aggregate.total_corners} holes:{aggregate.total_holes}"
    )


def _serialize_patch_graph_roles_line(console_view):
    """Serialize the snapshot role totals line."""

    aggregate = console_view.aggregate_counts
    return (
        f"H:{aggregate.total_h} V:{aggregate.total_v} Free:{aggregate.total_free} | "
        f"Runs: H:{aggregate.total_run_h} V:{aggregate.total_run_v} Free:{aggregate.total_run_free}"
    )


def _serialize_patch_graph_neighbors_line(console_view):
    """Serialize the snapshot neighbor totals line."""

    aggregate = console_view.aggregate_counts
    return f"Patch:{aggregate.total_patch_links} Self:{aggregate.total_self_seams} Border:{aggregate.total_mesh_borders}"


def _serialize_patch_graph_junctions_line(console_view):
    """Serialize the snapshot junction summary line."""

    summary_view = console_view.summary_view
    return (
        f"total:{summary_view.total_junctions} interesting:{summary_view.interesting_junction_count} "
        f"open:{summary_view.open_junction_count} closed:{summary_view.closed_junction_count} "
        f"valence:{_format_label_sequence_view(summary_view.valence_labels)}"
    )


def _serialize_patch_graph_report_lines(console_view, mesh_name=None):
    """Serialize the full typed console view into System Console report lines."""

    lines = []
    if mesh_name:
        lines.append(f"Mesh: {mesh_name}")

    for patch_view in console_view.patch_views:
        lines.extend(_serialize_patch_console_view(patch_view))

    if console_view.junction_views:
        lines.append(
            f"  Junctions: {_serialize_patch_graph_junctions_line(console_view)}"
        )
        lines.extend(
            _serialize_junction_console_view(junction_view)
            for junction_view in console_view.junction_views
        )

    return lines


def _serialize_patch_graph_snapshot_lines(console_view, mesh_name=None):
    """Serialize the typed console view into stable snapshot lines."""

    lines = []
    if mesh_name:
        lines.append(f"Mesh: {mesh_name}")

    for patch_view in console_view.patch_views:
        lines.append(
            f"P{patch_view.patch_id} {patch_view.semantic_key} | "
            f"faces:{patch_view.face_count} loops:{len(patch_view.loop_views)} "
            f"holes:{patch_view.hole_count} "
            f"chains:{patch_view.chain_count} corners:{patch_view.corner_count} "
            f"runs:{patch_view.run_count} | "
            f"roles:H{patch_view.h_count} V{patch_view.v_count} F{patch_view.free_count}"
        )

    lines.append(f"Topology: {_serialize_patch_graph_topology_line(console_view)}")
    lines.append(f"Roles: {_serialize_patch_graph_roles_line(console_view)}")
    lines.append(f"Neighbors: {_serialize_patch_graph_neighbors_line(console_view)}")
    lines.append(f"Junctions: {_serialize_patch_graph_junctions_line(console_view)}")
    for junction_view in console_view.junction_views:
        lines.append(
            f"JV{junction_view.vert_index} valence:{junction_view.valence} "
            f"open:{'Y' if junction_view.is_open else 'N'} border:{'Y' if junction_view.has_mesh_border else 'N'} "
            f"self:{'Y' if junction_view.has_seam_self else 'N'} "
            f"patches:{_format_label_sequence_view(junction_view.patch_ref_labels)} "
            f"signature:{_format_label_sequence_view(junction_view.signature_labels)} "
            f"corners:{_format_label_sequence_view(junction_view.corner_ref_labels)}"
        )

    return lines
