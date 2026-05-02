"""P7 post-frontier skeleton solve.

Builds junction-based row/column components, solves canonical junction coords,
and rebuilds scaffold chain points before transfer/conformal.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Any

from mathutils import Vector

try:
    from .constants import (
        SKELETON_COL_SPREAD_TOLERANCE,
        SKELETON_GAUGE_WEIGHT,
        SKELETON_MAX_CYCLE_RESIDUAL_APPLY,
        SKELETON_MAX_RESIDUAL_WARN,
        SKELETON_ROW_SPREAD_TOLERANCE,
        SKELETON_SIBLING_LENGTH_TOLERANCE,
        SKELETON_SIBLING_WEIGHT,
        USE_SKELETON_SOLVE,
    )
    from .analysis_records import _Junction, _PatchGraphDerivedTopology
    from .console_debug import trace_console
    from .frontier_place import (
        _cf_rebuild_chain_points_for_endpoints,
        _placement_normalized_stations,
    )
    from .shape_types import PatchShapeClass
    from .model import (
        ChainId,
        ChainGapReport,
        ChainRef,
        FrameAxisKind,
        FrameRole,
        PatchGraph,
        PatchPlacementStatus,
        ScaffoldMap,
        ScaffoldChainPlacement,
        ScaffoldPatchPlacement,
        ScaffoldPointKey,
        ScaffoldQuiltPlacement,
        SkeletonFlags,
    )
    from .solve_diagnostics import (
        _collect_quilt_closure_seam_reports,
        _collect_quilt_frame_alignment_reports,
        _print_quilt_closure_seam_reports,
        _print_quilt_frame_alignment_reports,
    )
    from .solve_records import (
        FRAME_COLUMN_GROUP_TOLERANCE,
        FRAME_ROW_GROUP_TOLERANCE,
    )
    from .solve_planning import _build_quilt_tree_edges
except ImportError:
    from constants import (
        SKELETON_COL_SPREAD_TOLERANCE,
        SKELETON_GAUGE_WEIGHT,
        SKELETON_MAX_CYCLE_RESIDUAL_APPLY,
        SKELETON_MAX_RESIDUAL_WARN,
        SKELETON_ROW_SPREAD_TOLERANCE,
        SKELETON_SIBLING_LENGTH_TOLERANCE,
        SKELETON_SIBLING_WEIGHT,
        USE_SKELETON_SOLVE,
    )
    from analysis_records import _Junction, _PatchGraphDerivedTopology
    from console_debug import trace_console
    from frontier_place import (
        _cf_rebuild_chain_points_for_endpoints,
        _placement_normalized_stations,
    )
    from shape_types import PatchShapeClass
    from model import (
        ChainId,
        ChainGapReport,
        ChainRef,
        FrameAxisKind,
        FrameRole,
        PatchGraph,
        PatchPlacementStatus,
        ScaffoldMap,
        ScaffoldChainPlacement,
        ScaffoldPatchPlacement,
        ScaffoldPointKey,
        ScaffoldQuiltPlacement,
        SkeletonFlags,
    )
    from solve_diagnostics import (
        _collect_quilt_closure_seam_reports,
        _collect_quilt_frame_alignment_reports,
        _print_quilt_closure_seam_reports,
        _print_quilt_frame_alignment_reports,
    )
    from solve_records import (
        FRAME_COLUMN_GROUP_TOLERANCE,
        FRAME_ROW_GROUP_TOLERANCE,
    )
    from solve_planning import _build_quilt_tree_edges


JunctionId = int


@dataclass(frozen=True)
class SingularUnionReport:
    """Отчёт safety-pass о конфликтном skeleton component."""

    axis_kind: FrameAxisKind
    component_id: int
    junction_vert_index: int
    split_chain_ref: ChainRef | None = None
    original_spread: float = 0.0
    resolved_spread: float = 0.0
    resolved: bool = False
    reason: str = ""


@dataclass(frozen=True)
class SkeletonGraphs:
    row_parent: dict[JunctionId, JunctionId] = field(default_factory=dict)
    col_parent: dict[JunctionId, JunctionId] = field(default_factory=dict)
    row_component_members: dict[int, list[JunctionId]] = field(default_factory=dict)
    col_component_members: dict[int, list[JunctionId]] = field(default_factory=dict)
    row_component_of_junction: dict[JunctionId, int] = field(default_factory=dict)
    col_component_of_junction: dict[JunctionId, int] = field(default_factory=dict)
    singular_unions: tuple[SingularUnionReport, ...] = ()
    junctions: tuple[_Junction, ...] = ()
    junctions_by_vert_index: dict[int, _Junction] = field(default_factory=dict)


@dataclass(frozen=True)
class SkeletonSolveReport:
    """Report for one quilt-level skeleton solve pass."""

    applied: bool = False
    row_component_count: int = 0
    col_component_count: int = 0
    singular_union_count: int = 0
    sibling_group_count: int = 0
    residual_u: float | None = None
    residual_v: float | None = None
    notes: tuple[str, ...] = ("skeleton_solve_not_integrated",)
    skeleton_graphs: SkeletonGraphs | None = None
    sibling_groups: tuple["SiblingGroup", ...] = ()
    junctions: tuple[_Junction, ...] = ()
    junctions_by_vert_index: dict[int, _Junction] = field(default_factory=dict)
    quilt_scaffold: ScaffoldQuiltPlacement | None = None
    solved_u_components: dict[int, float] = field(default_factory=dict)
    solved_v_components: dict[int, float] = field(default_factory=dict)
    pure_free_junction_count: int = 0
    unconstrained_row_junction_count: int = 0
    unconstrained_col_junction_count: int = 0


@dataclass(frozen=True)
class SkeletonSolveInput:
    graph: PatchGraph
    derived_topology: _PatchGraphDerivedTopology
    quilt_scaffold: ScaffoldQuiltPlacement
    final_scale: float = 1.0


@dataclass(frozen=True)
class SiblingGroup:
    patch_id: int
    role: FrameRole
    members: tuple[ChainId, ...] = ()
    target_length: float = 0.0


@dataclass(frozen=True)
class SkeletonAxisSolveResult:
    axis_kind: FrameAxisKind
    component_values: dict[int, float] = field(default_factory=dict)
    residual_norm: float = 0.0
    variable_count: int = 0
    equation_count: int = 0


@dataclass(frozen=True)
class _SkeletonAxisEdge:
    axis_kind: FrameAxisKind
    chain_ref: ChainRef
    endpoint_a: int
    endpoint_b: int


@dataclass(frozen=True)
class _SiblingCandidate:
    patch_id: int
    role: FrameRole
    chain_id: ChainId
    chain_ref: ChainRef
    line_component_id: int
    length_3d: float


@dataclass(frozen=True)
class _PlacedChainSolveInfo:
    chain_id: ChainId
    chain_ref: ChainRef
    role: FrameRole
    axis_sign: int
    target_length: float
    start_vert_index: int
    end_vert_index: int
    start_row_component_id: int | None
    end_row_component_id: int | None
    start_col_component_id: int | None
    end_col_component_id: int | None
    placement: ScaffoldChainPlacement


@dataclass(frozen=True)
class _AxisEquation:
    coefficients: tuple[tuple[int, float], ...]
    rhs: float
    weight: float = 1.0


def _uf_find(parent, item):
    root = item
    while parent[root] != root:
        root = parent[root]
    while parent[item] != item:
        next_item = parent[item]
        parent[item] = root
        item = next_item
    return root


def _uf_union(parent, left, right):
    if left not in parent:
        parent[left] = left
    if right not in parent:
        parent[right] = right
    left_root = _uf_find(parent, left)
    right_root = _uf_find(parent, right)
    if left_root == right_root:
        return
    if left_root < right_root:
        parent[right_root] = left_root
    else:
        parent[left_root] = right_root


def _component_spread(members, junctions_by_vert_index, axis_kind):
    coords = [
        junctions_by_vert_index[junction_id].vert_co
        for junction_id in members
        if junction_id in junctions_by_vert_index
    ]
    if len(coords) < 2:
        return 0.0
    if axis_kind == FrameAxisKind.ROW:
        z_values = [float(coord.z) for coord in coords]
        return max(z_values) - min(z_values)
    min_x = min(float(coord.x) for coord in coords)
    max_x = max(float(coord.x) for coord in coords)
    min_y = min(float(coord.y) for coord in coords)
    max_y = max(float(coord.y) for coord in coords)
    return math.hypot(max_x - min_x, max_y - min_y)


def _chain_length_3d(chain):
    if len(chain.vert_cos) < 2:
        return 0.0

    length_3d = 0.0
    prev_vert_co = chain.vert_cos[0]
    for vert_co in chain.vert_cos[1:]:
        length_3d += float((vert_co - prev_vert_co).length)
        prev_vert_co = vert_co
    return length_3d


def _collect_chain_role_overrides(quilt_scaffold, allowed_patch_ids=None):
    role_by_chain_ref = {}
    if quilt_scaffold is None:
        return role_by_chain_ref

    for patch_id in sorted(quilt_scaffold.patches):
        if allowed_patch_ids is not None and patch_id not in allowed_patch_ids:
            continue
        patch_placement = quilt_scaffold.patches[patch_id]
        if patch_placement is None or patch_placement.notes:
            continue
        for chain_placement in patch_placement.chain_placements:
            role_by_chain_ref[
                (chain_placement.patch_id, chain_placement.loop_index, chain_placement.chain_index)
            ] = chain_placement.frame_role
    return role_by_chain_ref


def _resolved_chain_role(chain_use, chain_role_by_ref=None):
    if not chain_role_by_ref:
        return chain_use.role_in_loop
    return chain_role_by_ref.get(
        (chain_use.patch_id, chain_use.loop_index, chain_use.chain_index),
        chain_use.role_in_loop,
    )


def _build_axis_edges(
    graph,
    junctions_by_vert_index,
    axis_kind,
    allowed_patch_ids=None,
    chain_role_by_ref=None,
):
    role = FrameRole.H_FRAME if axis_kind == FrameAxisKind.ROW else FrameRole.V_FRAME
    seen_chain_refs = set()
    edges = []

    for chain_use in sorted(
        graph.chain_use_by_ref.values(),
        key=lambda item: (item.patch_id, item.loop_index, item.position_in_loop, item.chain_index),
    ):
        if allowed_patch_ids is not None and chain_use.patch_id not in allowed_patch_ids:
            continue
        if _resolved_chain_role(chain_use, chain_role_by_ref) != role:
            continue
        if chain_use.chain_id in seen_chain_refs:
            continue

        chain = graph.get_chain(chain_use.patch_id, chain_use.loop_index, chain_use.chain_index)
        if chain is None:
            continue
        if chain.start_vert_index == chain.end_vert_index:
            continue
        if chain.start_vert_index not in junctions_by_vert_index or chain.end_vert_index not in junctions_by_vert_index:
            continue

        seen_chain_refs.add(chain_use.chain_id)
        edges.append(
            _SkeletonAxisEdge(
                axis_kind=axis_kind,
                chain_ref=(chain_use.patch_id, chain_use.loop_index, chain_use.chain_index),
                endpoint_a=chain.start_vert_index,
                endpoint_b=chain.end_vert_index,
            )
        )

    return edges


def _build_axis_parent(actual_junction_ids, edges):
    parent = {junction_id: junction_id for junction_id in actual_junction_ids}
    for edge in edges:
        _uf_union(parent, edge.endpoint_a, edge.endpoint_b)
    return parent


def _build_axis_components(actual_junction_ids, parent):
    members_by_root = {}
    for junction_id in actual_junction_ids:
        root = _uf_find(parent, junction_id)
        members_by_root.setdefault(root, []).append(junction_id)

    ordered_members = sorted(
        (sorted(members) for members in members_by_root.values()),
        key=lambda members: (members[0], len(members)),
    )

    component_members = {}
    component_of_junction = {}
    for component_id, members in enumerate(ordered_members):
        component_members[component_id] = members
        for junction_id in members:
            component_of_junction[junction_id] = component_id
    return component_members, component_of_junction


def _replace_edge_endpoint_with_phantom(edges, edge_index, junction_vert_index, phantom_id):
    updated_edges = list(edges)
    edge = updated_edges[edge_index]
    if edge.endpoint_a == junction_vert_index:
        updated_edges[edge_index] = replace(edge, endpoint_a=phantom_id)
    elif edge.endpoint_b == junction_vert_index:
        updated_edges[edge_index] = replace(edge, endpoint_b=phantom_id)
    return updated_edges


def _evaluate_split_candidate(
    actual_junction_ids,
    edges,
    axis_kind,
    junctions_by_vert_index,
    component_members,
    junction_vert_index,
    edge_index,
    phantom_id,
):
    updated_edges = _replace_edge_endpoint_with_phantom(edges, edge_index, junction_vert_index, phantom_id)
    parent = _build_axis_parent(actual_junction_ids, updated_edges)
    updated_component_members, _ = _build_axis_components(actual_junction_ids, parent)

    max_spread = 0.0
    for members in updated_component_members.values():
        if not (set(members) & set(component_members)):
            continue
        max_spread = max(max_spread, _component_spread(members, junctions_by_vert_index, axis_kind))
    return updated_edges, max_spread


def _resolve_singular_component(
    axis_kind,
    component_id,
    component_members,
    edges,
    actual_junction_ids,
    junctions_by_vert_index,
    next_phantom_id,
    chain_role_by_ref=None,
):
    original_spread = _component_spread(component_members, junctions_by_vert_index, axis_kind)
    if original_spread <= 0.0:
        return None, next_phantom_id

    role = FrameRole.H_FRAME if axis_kind == FrameAxisKind.ROW else FrameRole.V_FRAME
    member_set = set(component_members)
    best_resolution = None

    for junction_vert_index in sorted(component_members):
        junction = junctions_by_vert_index.get(junction_vert_index)
        if junction is None or junction.valence < 5:
            continue

        axis_incidences = [
            incidence
            for incidence in junction.ordered_disk_cycle()
            if _resolved_chain_role(incidence.chain_use, chain_role_by_ref) == role
        ]
        if len(axis_incidences) < 2:
            continue

        for incidence in axis_incidences:
            chain_ref = (
                incidence.chain_use.patch_id,
                incidence.chain_use.loop_index,
                incidence.chain_use.chain_index,
            )
            for edge_index, edge in enumerate(edges):
                if edge.chain_ref != chain_ref:
                    continue
                if edge.endpoint_a not in member_set or edge.endpoint_b not in member_set:
                    continue
                updated_edges, resolved_spread = _evaluate_split_candidate(
                    actual_junction_ids,
                    edges,
                    axis_kind,
                    junctions_by_vert_index,
                    component_members,
                    junction_vert_index,
                    edge_index,
                    next_phantom_id,
                )
                if best_resolution is None or resolved_spread < best_resolution[0]:
                    best_resolution = (
                        resolved_spread,
                        updated_edges,
                        chain_ref,
                        junction_vert_index,
                    )
                break

    if best_resolution is None:
        return SingularUnionReport(
            axis_kind=axis_kind,
            component_id=component_id,
            junction_vert_index=min(component_members),
            original_spread=original_spread,
            resolved_spread=original_spread,
            resolved=False,
            reason="no_split_candidate",
        ), next_phantom_id

    resolved_spread, updated_edges, chain_ref, junction_vert_index = best_resolution
    tolerance = (
        SKELETON_ROW_SPREAD_TOLERANCE
        if axis_kind == FrameAxisKind.ROW
        else SKELETON_COL_SPREAD_TOLERANCE
    )
    if resolved_spread > tolerance or resolved_spread >= original_spread:
        return SingularUnionReport(
            axis_kind=axis_kind,
            component_id=component_id,
            junction_vert_index=junction_vert_index,
            split_chain_ref=chain_ref,
            original_spread=original_spread,
            resolved_spread=resolved_spread,
            resolved=False,
            reason="split_failed_open",
        ), next_phantom_id

    report = SingularUnionReport(
        axis_kind=axis_kind,
        component_id=component_id,
        junction_vert_index=junction_vert_index,
        split_chain_ref=chain_ref,
        original_spread=original_spread,
        resolved_spread=resolved_spread,
        resolved=True,
        reason="singular_split",
    )
    return (report, updated_edges), next_phantom_id - 1


def _build_axis_graph(
    axis_kind,
    graph,
    junctions_by_vert_index,
    allowed_patch_ids=None,
    chain_role_by_ref=None,
):
    actual_junction_ids = sorted(junctions_by_vert_index.keys())
    edges = _build_axis_edges(
        graph,
        junctions_by_vert_index,
        axis_kind,
        allowed_patch_ids=allowed_patch_ids,
        chain_role_by_ref=chain_role_by_ref,
    )
    tolerance = (
        SKELETON_ROW_SPREAD_TOLERANCE
        if axis_kind == FrameAxisKind.ROW
        else SKELETON_COL_SPREAD_TOLERANCE
    )
    singular_reports = []
    split_junction_ids = set()
    unconstrained_junction_ids = set()
    next_phantom_id = -1

    for _ in range(max(1, len(actual_junction_ids))):
        parent = _build_axis_parent(actual_junction_ids, edges)
        component_members, component_of_junction = _build_axis_components(actual_junction_ids, parent)
        inconsistent_components = [
            (component_id, members)
            for component_id, members in component_members.items()
            if _component_spread(members, junctions_by_vert_index, axis_kind) > tolerance
        ]
        if not inconsistent_components:
            return (
                parent,
                component_members,
                component_of_junction,
                singular_reports,
                split_junction_ids,
                unconstrained_junction_ids,
            )

        changed = False
        for component_id, members in inconsistent_components:
            resolution, next_phantom_id = _resolve_singular_component(
                axis_kind,
                component_id,
                members,
                edges,
                actual_junction_ids,
                junctions_by_vert_index,
                next_phantom_id,
                chain_role_by_ref=chain_role_by_ref,
            )
            if resolution is None:
                continue
            if isinstance(resolution, tuple):
                report, edges = resolution
                singular_reports.append(report)
                split_junction_ids.add(report.junction_vert_index)
                changed = True
            else:
                singular_reports.append(resolution)
                unconstrained_junction_ids.update(members)
        if not changed:
            break

    parent = _build_axis_parent(actual_junction_ids, edges)
    component_members, component_of_junction = _build_axis_components(actual_junction_ids, parent)
    for members in component_members.values():
        if _component_spread(members, junctions_by_vert_index, axis_kind) > tolerance:
            unconstrained_junction_ids.update(members)
    return (
        parent,
        component_members,
        component_of_junction,
        singular_reports,
        split_junction_ids,
        unconstrained_junction_ids,
    )


def _annotate_junctions(
    junctions_source,
    row_component_of_junction,
    col_component_of_junction,
    row_split_junction_ids,
    col_split_junction_ids,
    unconstrained_row_junction_ids,
    unconstrained_col_junction_ids,
):
    junctions = []
    junctions_by_vert_index = {}
    for junction in junctions_source:
        flags = SkeletonFlags(junction.skeleton_flags)
        if junction.free_count > 0 and junction.h_count == 0 and junction.v_count == 0:
            flags |= SkeletonFlags.PURE_FREE
        if junction.vert_index in row_split_junction_ids or junction.vert_index in col_split_junction_ids:
            flags |= SkeletonFlags.SINGULAR_SPLIT
        if junction.vert_index in unconstrained_row_junction_ids:
            flags |= SkeletonFlags.UNCONSTRAINED_ROW
        if junction.vert_index in unconstrained_col_junction_ids:
            flags |= SkeletonFlags.UNCONSTRAINED_COL

        annotated = replace(
            junction,
            row_component_id=row_component_of_junction.get(junction.vert_index),
            col_component_id=col_component_of_junction.get(junction.vert_index),
            skeleton_flags=flags,
        )
        junctions.append(annotated)
        junctions_by_vert_index[annotated.vert_index] = annotated
    return tuple(junctions), junctions_by_vert_index


def _iter_sibling_candidates(
    graph,
    skeleton_graphs,
    allowed_patch_ids=None,
    chain_role_by_ref=None,
):
    if not graph.chain_use_by_ref:
        graph.rebuild_chain_use_index()

    junctions_by_vert_index = skeleton_graphs.junctions_by_vert_index
    for patch_id in sorted(graph.nodes):
        if allowed_patch_ids is not None and patch_id not in allowed_patch_ids:
            continue
        node = graph.nodes[patch_id]
        seen_chain_ids = set()

        for loop_index in range(len(node.boundary_loops)):
            for chain_use in node.iter_boundary_loop_oriented(loop_index):
                if chain_use.chain_id in seen_chain_ids:
                    continue
                resolved_role = _resolved_chain_role(chain_use, chain_role_by_ref)
                if resolved_role not in (FrameRole.H_FRAME, FrameRole.V_FRAME):
                    continue

                chain = graph.get_chain(chain_use.patch_id, chain_use.loop_index, chain_use.chain_index)
                if chain is None:
                    continue

                start_junction = junctions_by_vert_index.get(chain.start_vert_index)
                end_junction = junctions_by_vert_index.get(chain.end_vert_index)
                if start_junction is None or end_junction is None:
                    continue

                if resolved_role == FrameRole.H_FRAME:
                    line_component_id = start_junction.row_component_id
                    if line_component_id is None or end_junction.row_component_id != line_component_id:
                        continue
                else:
                    line_component_id = start_junction.col_component_id
                    if line_component_id is None or end_junction.col_component_id != line_component_id:
                        continue

                seen_chain_ids.add(chain_use.chain_id)
                yield _SiblingCandidate(
                    patch_id=patch_id,
                    role=resolved_role,
                    chain_id=chain_use.chain_id,
                    chain_ref=(chain_use.patch_id, chain_use.loop_index, chain_use.chain_index),
                    line_component_id=line_component_id,
                    length_3d=_chain_length_3d(chain),
                )


def _sibling_candidates_match(left, right):
    if left.patch_id != right.patch_id or left.role != right.role:
        return False
    if left.chain_id == right.chain_id:
        return False
    if left.line_component_id == right.line_component_id:
        return False

    longer_length = max(left.length_3d, right.length_3d)
    if longer_length <= 0.0:
        return False
    tolerance = SKELETON_SIBLING_LENGTH_TOLERANCE * longer_length
    return abs(left.length_3d - right.length_3d) < tolerance


def build_sibling_groups(
    graph: PatchGraph,
    skeleton_graphs: SkeletonGraphs,
    *,
    allowed_patch_ids=None,
    chain_role_by_ref=None,
) -> tuple[SiblingGroup, ...]:
    """S3: builds minimal same-patch sibling equivalence groups."""

    grouped_candidates = {}
    for candidate in _iter_sibling_candidates(
        graph,
        skeleton_graphs,
        allowed_patch_ids=allowed_patch_ids,
        chain_role_by_ref=chain_role_by_ref,
    ):
        grouped_candidates.setdefault((candidate.patch_id, candidate.role), []).append(candidate)

    sibling_groups = []
    for patch_id, role in sorted(grouped_candidates, key=lambda item: (item[0], item[1].value)):
        candidates = sorted(
            grouped_candidates[(patch_id, role)],
            key=lambda item: (item.length_3d, item.chain_ref),
        )
        if len(candidates) < 2:
            continue

        parent = {index: index for index in range(len(candidates))}
        for left_index, left_candidate in enumerate(candidates):
            for right_index in range(left_index + 1, len(candidates)):
                if _sibling_candidates_match(left_candidate, candidates[right_index]):
                    _uf_union(parent, left_index, right_index)

        members_by_root = {}
        for candidate_index in range(len(candidates)):
            root_index = _uf_find(parent, candidate_index)
            members_by_root.setdefault(root_index, []).append(candidates[candidate_index])

        for member_candidates in members_by_root.values():
            if len(member_candidates) < 2:
                continue
            sibling_groups.append(
                SiblingGroup(
                    patch_id=patch_id,
                    role=role,
                    members=tuple(sorted((candidate.chain_id for candidate in member_candidates))),
                    target_length=sum(candidate.length_3d for candidate in member_candidates) / float(len(member_candidates)),
                )
            )

    return tuple(
        sorted(
            sibling_groups,
            key=lambda item: (item.patch_id, item.role.value, item.members),
        )
    )


def _axis_role(axis_kind):
    return FrameRole.H_FRAME if axis_kind == FrameAxisKind.COLUMN else FrameRole.V_FRAME


def _collect_quilt_placed_chain_infos(
    graph,
    quilt_scaffold,
    skeleton_graphs,
    final_scale,
    allowed_patch_ids=None,
):
    placed_chain_infos = {}
    if not graph.chain_use_by_ref:
        graph.rebuild_chain_use_index()

    junctions_by_vert_index = skeleton_graphs.junctions_by_vert_index
    for patch_id in sorted(quilt_scaffold.patches):
        if allowed_patch_ids is not None and patch_id not in allowed_patch_ids:
            continue
        patch_placement = quilt_scaffold.patches[patch_id]
        if patch_placement is None or patch_placement.notes:
            continue
        for chain_placement in patch_placement.chain_placements:
            chain_use = graph.get_chain_use(
                chain_placement.patch_id,
                chain_placement.loop_index,
                chain_placement.chain_index,
            )
            chain = graph.get_chain(
                chain_placement.patch_id,
                chain_placement.loop_index,
                chain_placement.chain_index,
            )
            if chain_use is None or chain is None:
                continue
            if chain_use.chain_id in placed_chain_infos:
                continue

            start_junction = junctions_by_vert_index.get(chain.start_vert_index)
            end_junction = junctions_by_vert_index.get(chain.end_vert_index)
            placed_chain_infos[chain_use.chain_id] = _PlacedChainSolveInfo(
                chain_id=chain_use.chain_id,
                chain_ref=(chain_use.patch_id, chain_use.loop_index, chain_use.chain_index),
                role=chain_placement.frame_role,
                axis_sign=_placement_axis_sign(chain_use, chain_placement),
                target_length=_chain_length_3d(chain) * float(final_scale),
                start_vert_index=chain.start_vert_index,
                end_vert_index=chain.end_vert_index,
                start_row_component_id=None if start_junction is None else start_junction.row_component_id,
                end_row_component_id=None if end_junction is None else end_junction.row_component_id,
                start_col_component_id=None if start_junction is None else start_junction.col_component_id,
                end_col_component_id=None if end_junction is None else end_junction.col_component_id,
                placement=chain_placement,
            )
    return placed_chain_infos


def _collect_component_coord_samples(
    graph,
    quilt_scaffold,
    skeleton_graphs,
    axis_kind,
    allowed_patch_ids=None,
):
    samples = {}
    if not graph.chain_use_by_ref:
        graph.rebuild_chain_use_index()

    for patch_id in sorted(quilt_scaffold.patches):
        if allowed_patch_ids is not None and patch_id not in allowed_patch_ids:
            continue
        patch_placement = quilt_scaffold.patches[patch_id]
        if patch_placement is None or patch_placement.notes:
            continue
        for chain_placement in patch_placement.chain_placements:
            if not chain_placement.points:
                continue
            chain = graph.get_chain(
                chain_placement.patch_id,
                chain_placement.loop_index,
                chain_placement.chain_index,
            )
            if chain is None:
                continue
            start_junction = skeleton_graphs.junctions_by_vert_index.get(chain.start_vert_index)
            end_junction = skeleton_graphs.junctions_by_vert_index.get(chain.end_vert_index)
            if axis_kind == FrameAxisKind.COLUMN:
                start_component_id = None if start_junction is None else start_junction.col_component_id
                end_component_id = None if end_junction is None else end_junction.col_component_id
                start_value = float(chain_placement.points[0][1].x)
                end_value = float(chain_placement.points[-1][1].x)
            else:
                start_component_id = None if start_junction is None else start_junction.row_component_id
                end_component_id = None if end_junction is None else end_junction.row_component_id
                start_value = float(chain_placement.points[0][1].y)
                end_value = float(chain_placement.points[-1][1].y)

            if start_component_id is not None:
                samples.setdefault(start_component_id, []).append(start_value)
            if end_component_id is not None:
                samples.setdefault(end_component_id, []).append(end_value)
    return {
        component_id: sum(values) / float(len(values))
        for component_id, values in samples.items()
        if values
    }


def _axis_components_for_chain(chain_info, axis_kind):
    if axis_kind == FrameAxisKind.COLUMN:
        if chain_info.role != FrameRole.H_FRAME:
            return None, None
        return chain_info.start_col_component_id, chain_info.end_col_component_id
    if chain_info.role != FrameRole.V_FRAME:
        return None, None
    return chain_info.start_row_component_id, chain_info.end_row_component_id


def _placement_axis_sign(chain_use, chain_placement):
    """Временный S4 bridge: используем фактическое направление placed chain."""

    if len(chain_placement.points) >= 2:
        start_uv = chain_placement.points[0][1]
        end_uv = chain_placement.points[-1][1]
        if chain_placement.frame_role == FrameRole.H_FRAME:
            return 1 if end_uv.x >= start_uv.x else -1
        if chain_placement.frame_role == FrameRole.V_FRAME:
            return 1 if end_uv.y >= start_uv.y else -1
    return chain_use.axis_sign


def _build_axis_equations(
    axis_kind,
    placed_chain_infos,
    sibling_groups,
    component_coord_samples,
    fixed_component_samples=None,
):
    axis_role = _axis_role(axis_kind)
    equations = []
    variable_ids = set()
    placed_by_chain_id = {}

    for chain_id, chain_info in placed_chain_infos.items():
        start_component_id, end_component_id = _axis_components_for_chain(chain_info, axis_kind)
        if chain_info.role != axis_role:
            continue
        if start_component_id is None or end_component_id is None:
            continue
        variable_ids.add(start_component_id)
        variable_ids.add(end_component_id)
        placed_by_chain_id[chain_id] = chain_info
        equations.append(
            _AxisEquation(
                coefficients=((start_component_id, -1.0), (end_component_id, 1.0)),
                rhs=float(chain_info.axis_sign) * float(chain_info.target_length),
                weight=1.0,
            )
        )

    sibling_role = FrameRole.H_FRAME if axis_kind == FrameAxisKind.COLUMN else FrameRole.V_FRAME
    for sibling_group in sibling_groups:
        if sibling_group.role != sibling_role:
            continue
        sibling_members = [
            placed_by_chain_id[chain_id]
            for chain_id in sibling_group.members
            if chain_id in placed_by_chain_id
        ]
        if len(sibling_members) < 2:
            continue
        sibling_members.sort(key=lambda item: item.chain_ref)
        base_info = sibling_members[0]
        base_start_component_id, base_end_component_id = _axis_components_for_chain(base_info, axis_kind)
        for member_info in sibling_members[1:]:
            member_start_component_id, member_end_component_id = _axis_components_for_chain(member_info, axis_kind)
            equations.append(
                _AxisEquation(
                    coefficients=(
                        (member_start_component_id, -float(member_info.axis_sign)),
                        (member_end_component_id, float(member_info.axis_sign)),
                        (base_start_component_id, float(base_info.axis_sign)),
                        (base_end_component_id, -float(base_info.axis_sign)),
                    ),
                    rhs=0.0,
                    weight=SKELETON_SIBLING_WEIGHT,
                )
            )

    anchored_component_ids = set()
    if fixed_component_samples:
        for component_id, fixed_value in sorted(fixed_component_samples.items()):
            if component_id not in variable_ids:
                continue
            anchored_component_ids.add(component_id)
            equations.append(
                _AxisEquation(
                    coefficients=((component_id, 1.0),),
                    rhs=float(fixed_value),
                    weight=SKELETON_GAUGE_WEIGHT,
                )
            )

    if variable_ids and not anchored_component_ids:
        anchor_component_id = min(component_coord_samples) if component_coord_samples else min(variable_ids)
        anchor_value = float(component_coord_samples.get(anchor_component_id, 0.0))
        equations.append(
            _AxisEquation(
                coefficients=((anchor_component_id, 1.0),),
                rhs=anchor_value,
                weight=SKELETON_GAUGE_WEIGHT,
            )
        )

    return tuple(sorted(variable_ids)), tuple(equations)


def _solve_dense_normal_equations(variable_ids, equations):
    if not variable_ids:
        return {}

    variable_to_index = {component_id: index for index, component_id in enumerate(variable_ids)}
    variable_count = len(variable_ids)
    ata = [
        [0.0 for _ in range(variable_count)]
        for _ in range(variable_count)
    ]
    atb = [0.0 for _ in range(variable_count)]

    for equation in equations:
        row = [0.0 for _ in range(variable_count)]
        for component_id, coefficient in equation.coefficients:
            row[variable_to_index[component_id]] += float(coefficient)
        weighted_scale = math.sqrt(max(float(equation.weight), 0.0))
        weighted_row = [coefficient * weighted_scale for coefficient in row]
        weighted_rhs = float(equation.rhs) * weighted_scale

        for left_index in range(variable_count):
            atb[left_index] += weighted_row[left_index] * weighted_rhs
            if abs(weighted_row[left_index]) <= 1e-12:
                continue
            for right_index in range(variable_count):
                ata[left_index][right_index] += weighted_row[left_index] * weighted_row[right_index]

    augmented = [
        ata[row_index][:] + [atb[row_index]]
        for row_index in range(variable_count)
    ]

    for pivot_index in range(variable_count):
        pivot_row = max(
            range(pivot_index, variable_count),
            key=lambda row_index: abs(augmented[row_index][pivot_index]),
        )
        pivot_value = augmented[pivot_row][pivot_index]
        if abs(pivot_value) <= 1e-12:
            augmented[pivot_row][pivot_index] = 1e-12
            pivot_value = augmented[pivot_row][pivot_index]
        if pivot_row != pivot_index:
            augmented[pivot_index], augmented[pivot_row] = augmented[pivot_row], augmented[pivot_index]

        for column_index in range(pivot_index, variable_count + 1):
            augmented[pivot_index][column_index] /= pivot_value

        for row_index in range(variable_count):
            if row_index == pivot_index:
                continue
            factor = augmented[row_index][pivot_index]
            if abs(factor) <= 1e-12:
                continue
            for column_index in range(pivot_index, variable_count + 1):
                augmented[row_index][column_index] -= factor * augmented[pivot_index][column_index]

    return {
        component_id: augmented[variable_to_index[component_id]][variable_count]
        for component_id in variable_ids
    }


def _compute_axis_residual(component_values, equations):
    residual_sq = 0.0
    for equation in equations:
        lhs = 0.0
        for component_id, coefficient in equation.coefficients:
            lhs += float(coefficient) * float(component_values.get(component_id, 0.0))
        residual_sq += (lhs - float(equation.rhs)) ** 2
    return math.sqrt(residual_sq)


def _solve_axis(
    axis_kind,
    placed_chain_infos,
    sibling_groups,
    component_coord_samples,
    fixed_component_samples=None,
):
    variable_ids, equations = _build_axis_equations(
        axis_kind,
        placed_chain_infos,
        sibling_groups,
        component_coord_samples,
        fixed_component_samples=fixed_component_samples,
    )
    if not variable_ids:
        return SkeletonAxisSolveResult(axis_kind=axis_kind)

    component_values = _solve_dense_normal_equations(variable_ids, equations)
    return SkeletonAxisSolveResult(
        axis_kind=axis_kind,
        component_values=component_values,
        residual_norm=_compute_axis_residual(component_values, equations),
        variable_count=len(variable_ids),
        equation_count=len(equations),
    )


def _annotate_canonical_junctions(junctions, solved_u_components, solved_v_components):
    annotated_junctions = []
    junctions_by_vert_index = {}
    for junction in junctions:
        annotated = replace(
            junction,
            canonical_u=(
                None
                if junction.col_component_id is None
                else solved_u_components.get(junction.col_component_id)
            ),
            canonical_v=(
                None
                if junction.row_component_id is None
                else solved_v_components.get(junction.row_component_id)
            ),
        )
        annotated_junctions.append(annotated)
        junctions_by_vert_index[annotated.vert_index] = annotated
    return tuple(annotated_junctions), junctions_by_vert_index


def _compute_patch_chain_gap_reports(patch_placements, total_chains):
    if total_chains < 2 or not patch_placements:
        return 0.0, ()

    placements_by_chain_index = {
        placement.chain_index: placement
        for placement in patch_placements
    }
    reports = []
    max_gap = 0.0
    for chain_index in sorted(placements_by_chain_index):
        next_chain_index = (chain_index + 1) % total_chains
        current_placement = placements_by_chain_index[chain_index]
        next_placement = placements_by_chain_index.get(next_chain_index)
        if next_placement is None or not current_placement.points or not next_placement.points:
            continue
        gap = (current_placement.points[-1][1] - next_placement.points[0][1]).length
        reports.append(
            ChainGapReport(
                chain_index=chain_index,
                next_chain_index=next_chain_index,
                gap=gap,
            )
        )
        max_gap = max(max_gap, gap)
    return max_gap, tuple(reports)


def _canonical_uv_for_junction(junction, fallback_uv):
    if junction is None or junction.canonical_u is None or junction.canonical_v is None:
        return fallback_uv.copy()
    return Vector((float(junction.canonical_u), float(junction.canonical_v)))


def _rebuild_chain_placement(graph, chain_placement, junctions_by_vert_index, final_scale):
    if not chain_placement.points:
        return chain_placement

    chain = graph.get_chain(
        chain_placement.patch_id,
        chain_placement.loop_index,
        chain_placement.chain_index,
    )
    if chain is None:
        return chain_placement

    start_junction = junctions_by_vert_index.get(chain.start_vert_index)
    end_junction = junctions_by_vert_index.get(chain.end_vert_index)
    start_uv = _canonical_uv_for_junction(start_junction, chain_placement.points[0][1])
    end_uv = _canonical_uv_for_junction(end_junction, chain_placement.points[-1][1])

    station_map = (
        _placement_normalized_stations(chain_placement)
        if chain_placement.frame_role in {FrameRole.H_FRAME, FrameRole.V_FRAME}
        else None
    )
    rebuilt_uvs = _cf_rebuild_chain_points_for_endpoints(
        chain,
        start_uv,
        end_uv,
        final_scale,
        effective_role=chain_placement.frame_role,
        station_map=station_map,
    )
    if rebuilt_uvs is None or len(rebuilt_uvs) != len(chain_placement.points):
        rebuilt_uvs = [uv.copy() for _, uv in chain_placement.points]
        if rebuilt_uvs:
            rebuilt_uvs[0] = start_uv.copy()
            rebuilt_uvs[-1] = end_uv.copy()

    return replace(
        chain_placement,
        points=tuple(
            (point_key, rebuilt_uvs[point_index].copy())
            for point_index, (point_key, _) in enumerate(chain_placement.points)
        ),
    )


def _rebuild_patch_placement(graph, patch_placement, rebuilt_chain_placements):
    node = graph.nodes.get(patch_placement.patch_id)
    if node is None or patch_placement.loop_index < 0 or patch_placement.loop_index >= len(node.boundary_loops):
        return replace(patch_placement, chain_placements=rebuilt_chain_placements)

    boundary_loop = node.boundary_loops[patch_placement.loop_index]
    rebuilt_chain_placements = sorted(rebuilt_chain_placements, key=lambda item: item.chain_index)
    placed_chains_map = {
        (placement.patch_id, placement.loop_index, placement.chain_index): placement
        for placement in rebuilt_chain_placements
    }

    corner_positions = {}
    for corner_index, corner in enumerate(boundary_loop.corners):
        prev_ref = (patch_placement.patch_id, patch_placement.loop_index, corner.prev_chain_index)
        next_ref = (patch_placement.patch_id, patch_placement.loop_index, corner.next_chain_index)
        if prev_ref in placed_chains_map and placed_chains_map[prev_ref].points:
            corner_positions[corner_index] = placed_chains_map[prev_ref].points[-1][1].copy()
        elif next_ref in placed_chains_map and placed_chains_map[next_ref].points:
            corner_positions[corner_index] = placed_chains_map[next_ref].points[0][1].copy()

    all_points = [
        point.copy()
        for placement in rebuilt_chain_placements
        for _, point in placement.points
    ]
    if all_points:
        bbox_min = Vector((min(point.x for point in all_points), min(point.y for point in all_points)))
        bbox_max = Vector((max(point.x for point in all_points), max(point.y for point in all_points)))
    else:
        bbox_min = Vector((0.0, 0.0))
        bbox_max = Vector((0.0, 0.0))

    total_chains = len(boundary_loop.chains)
    placed_chain_indices = {placement.chain_index for placement in rebuilt_chain_placements}
    if len(placed_chain_indices) >= total_chains:
        status = PatchPlacementStatus.COMPLETE
    elif placed_chain_indices:
        status = PatchPlacementStatus.PARTIAL
    else:
        status = PatchPlacementStatus.EMPTY

    closure_error = patch_placement.closure_error
    closure_valid = patch_placement.closure_valid
    if status == PatchPlacementStatus.COMPLETE and total_chains >= 2 and rebuilt_chain_placements:
        if rebuilt_chain_placements[-1].points and rebuilt_chain_placements[0].points:
            closure_error = (rebuilt_chain_placements[-1].points[-1][1] - rebuilt_chain_placements[0].points[0][1]).length
            closure_valid = closure_error < 0.05

    max_chain_gap, gap_reports = _compute_patch_chain_gap_reports(rebuilt_chain_placements, total_chains)
    unplaced_chain_indices = tuple(
        chain_index
        for chain_index in range(total_chains)
        if chain_index not in placed_chain_indices
    )

    return replace(
        patch_placement,
        corner_positions=corner_positions,
        chain_placements=rebuilt_chain_placements,
        bbox_min=bbox_min,
        bbox_max=bbox_max,
        closure_error=closure_error,
        closure_valid=closure_valid,
        status=status,
        unplaced_chain_indices=unplaced_chain_indices,
        max_chain_gap=max_chain_gap,
        gap_reports=gap_reports,
    )


def _rebuild_quilt_scaffold(
    graph,
    quilt_scaffold,
    junctions_by_vert_index,
    final_scale,
    allowed_patch_ids=None,
):
    rebuilt_patches = {}
    for patch_id, patch_placement in quilt_scaffold.patches.items():
        if allowed_patch_ids is not None and patch_id not in allowed_patch_ids:
            rebuilt_patches[patch_id] = patch_placement
            continue
        if patch_placement is None or patch_placement.notes:
            rebuilt_patches[patch_id] = patch_placement
            continue
        rebuilt_chain_placements = [
            _rebuild_chain_placement(
                graph,
                chain_placement,
                junctions_by_vert_index,
                final_scale,
            )
            for chain_placement in patch_placement.chain_placements
        ]
        rebuilt_patches[patch_id] = _rebuild_patch_placement(
            graph,
            patch_placement,
            rebuilt_chain_placements,
        )
    return replace(quilt_scaffold, patches=rebuilt_patches)


def _collect_quilt_patch_ids(quilt_scaffold) -> frozenset[int]:
    return frozenset(
        patch_id
        for patch_id, patch_placement in quilt_scaffold.patches.items()
        if patch_placement is not None and not patch_placement.notes
    )


def _collect_quilt_semantic_keys(graph: PatchGraph, quilt_patch_ids) -> frozenset[str]:
    return frozenset(
        graph.get_patch_semantic_key(patch_id)
        for patch_id in quilt_patch_ids
        if patch_id in graph.nodes
    )


def _is_pure_wall_side_quilt(graph: PatchGraph, quilt_scaffold) -> bool:
    quilt_patch_ids = _collect_quilt_patch_ids(quilt_scaffold)
    if not quilt_patch_ids:
        return False
    return _collect_quilt_semantic_keys(graph, quilt_patch_ids) == frozenset({"WALL.SIDE"})


def _filter_junctions_for_patch_ids(
    derived_topology: _PatchGraphDerivedTopology,
    allowed_patch_ids=None,
) -> tuple[tuple[_Junction, ...], dict[int, _Junction]]:
    if not allowed_patch_ids:
        return derived_topology.junctions, dict(derived_topology.junctions_by_vert_index)

    allowed_patch_ids = set(allowed_patch_ids)
    junctions = tuple(
        junction
        for junction in derived_topology.junctions
        if any(patch_id in allowed_patch_ids for patch_id in junction.patch_ids)
    )
    return junctions, {junction.vert_index: junction for junction in junctions}


def build_skeleton_graphs(
    graph: PatchGraph,
    derived_topology: _PatchGraphDerivedTopology,
    *,
    allowed_patch_ids=None,
    chain_role_by_ref=None,
) -> SkeletonGraphs:
    """S2: строит row/column graphs и аннотирует junction component ids."""

    junctions_source, junctions_by_vert_index = _filter_junctions_for_patch_ids(
        derived_topology,
        allowed_patch_ids=allowed_patch_ids,
    )
    (
        row_parent,
        row_component_members,
        row_component_of_junction,
        row_reports,
        row_split_junction_ids,
        unconstrained_row_junction_ids,
    ) = _build_axis_graph(
        FrameAxisKind.ROW,
        graph,
        junctions_by_vert_index,
        allowed_patch_ids=allowed_patch_ids,
        chain_role_by_ref=chain_role_by_ref,
    )
    (
        col_parent,
        col_component_members,
        col_component_of_junction,
        col_reports,
        col_split_junction_ids,
        unconstrained_col_junction_ids,
    ) = _build_axis_graph(
        FrameAxisKind.COLUMN,
        graph,
        junctions_by_vert_index,
        allowed_patch_ids=allowed_patch_ids,
        chain_role_by_ref=chain_role_by_ref,
    )

    junctions, junctions_by_vert_index = _annotate_junctions(
        junctions_source,
        row_component_of_junction,
        col_component_of_junction,
        row_split_junction_ids,
        col_split_junction_ids,
        unconstrained_row_junction_ids,
        unconstrained_col_junction_ids,
    )

    return SkeletonGraphs(
        row_parent=row_parent,
        col_parent=col_parent,
        row_component_members=row_component_members,
        col_component_members=col_component_members,
        row_component_of_junction=row_component_of_junction,
        col_component_of_junction=col_component_of_junction,
        singular_unions=tuple(row_reports + col_reports),
        junctions=junctions,
        junctions_by_vert_index=junctions_by_vert_index,
    )


def _junction_flag_counts(junctions):
    pure_free_junction_count = 0
    unconstrained_row_junction_count = 0
    unconstrained_col_junction_count = 0
    for junction in junctions:
        if junction.skeleton_flags & SkeletonFlags.PURE_FREE:
            pure_free_junction_count += 1
        if junction.skeleton_flags & SkeletonFlags.UNCONSTRAINED_ROW:
            unconstrained_row_junction_count += 1
        if junction.skeleton_flags & SkeletonFlags.UNCONSTRAINED_COL:
            unconstrained_col_junction_count += 1
    return (
        pure_free_junction_count,
        unconstrained_row_junction_count,
        unconstrained_col_junction_count,
    )


def _quilt_has_non_tree_closure(quilt_plan) -> bool:
    if quilt_plan is None:
        return False
    seam_relation_by_edge = getattr(quilt_plan, "seam_relation_by_edge", {})
    if not seam_relation_by_edge:
        return False
    tree_edges = _build_quilt_tree_edges(quilt_plan)
    return any(edge_key not in tree_edges for edge_key in seam_relation_by_edge.keys())


def apply_skeleton_solve(quilt: Any, diagnostics: Any = None) -> SkeletonSolveReport:
    """S4 module-level skeleton solve without pipeline integration."""

    _ = diagnostics
    if not isinstance(quilt, SkeletonSolveInput):
        return SkeletonSolveReport()

    quilt_patch_ids = _collect_quilt_patch_ids(quilt.quilt_scaffold)
    chain_role_by_ref = _collect_chain_role_overrides(
        quilt.quilt_scaffold,
        allowed_patch_ids=quilt_patch_ids,
    )
    if not _is_pure_wall_side_quilt(quilt.graph, quilt.quilt_scaffold):
        return SkeletonSolveReport(
            applied=False,
            quilt_scaffold=quilt.quilt_scaffold,
            notes=("skeleton_skip_non_wall_quilt",),
        )
    skeleton_graphs = build_skeleton_graphs(
        quilt.graph,
        quilt.derived_topology,
        allowed_patch_ids=quilt_patch_ids,
        chain_role_by_ref=chain_role_by_ref,
    )
    sibling_groups = build_sibling_groups(
        quilt.graph,
        skeleton_graphs,
        allowed_patch_ids=quilt_patch_ids,
        chain_role_by_ref=chain_role_by_ref,
    )
    (
        pure_free_junction_count,
        unconstrained_row_junction_count,
        unconstrained_col_junction_count,
    ) = _junction_flag_counts(skeleton_graphs.junctions)
    placed_chain_infos = _collect_quilt_placed_chain_infos(
        quilt.graph,
        quilt.quilt_scaffold,
        skeleton_graphs,
        quilt.final_scale,
        allowed_patch_ids=quilt_patch_ids,
    )
    if not placed_chain_infos:
        return SkeletonSolveReport(
            applied=False,
            row_component_count=len(skeleton_graphs.row_component_members),
            col_component_count=len(skeleton_graphs.col_component_members),
            singular_union_count=len(skeleton_graphs.singular_unions),
            sibling_group_count=len(sibling_groups),
            skeleton_graphs=skeleton_graphs,
            sibling_groups=sibling_groups,
            junctions=skeleton_graphs.junctions,
            junctions_by_vert_index=skeleton_graphs.junctions_by_vert_index,
            quilt_scaffold=quilt.quilt_scaffold,
            notes=("skeleton_solve_empty_quilt",),
            pure_free_junction_count=pure_free_junction_count,
            unconstrained_row_junction_count=unconstrained_row_junction_count,
            unconstrained_col_junction_count=unconstrained_col_junction_count,
        )

    component_coord_samples_u = _collect_component_coord_samples(
        quilt.graph,
        quilt.quilt_scaffold,
        skeleton_graphs,
        FrameAxisKind.COLUMN,
        allowed_patch_ids=quilt_patch_ids,
    )
    component_coord_samples_v = _collect_component_coord_samples(
        quilt.graph,
        quilt.quilt_scaffold,
        skeleton_graphs,
        FrameAxisKind.ROW,
        allowed_patch_ids=quilt_patch_ids,
    )
    solved_u = _solve_axis(
        FrameAxisKind.COLUMN,
        placed_chain_infos,
        sibling_groups,
        component_coord_samples_u,
    )
    solved_v = _solve_axis(
        FrameAxisKind.ROW,
        placed_chain_infos,
        sibling_groups,
        component_coord_samples_v,
    )
    junctions, junctions_by_vert_index = _annotate_canonical_junctions(
        skeleton_graphs.junctions,
        solved_u.component_values,
        solved_v.component_values,
    )
    rebuilt_quilt_scaffold = _rebuild_quilt_scaffold(
        quilt.graph,
        quilt.quilt_scaffold,
        junctions_by_vert_index,
        quilt.final_scale,
        allowed_patch_ids=quilt_patch_ids,
    )

    notes = []
    if solved_u.residual_norm > SKELETON_MAX_RESIDUAL_WARN:
        notes.append("skeleton_residual_u_warn")
    if solved_v.residual_norm > SKELETON_MAX_RESIDUAL_WARN:
        notes.append("skeleton_residual_v_warn")
    if not notes:
        notes.append("skeleton_solve_applied")

    return SkeletonSolveReport(
        applied=True,
        row_component_count=len(skeleton_graphs.row_component_members),
        col_component_count=len(skeleton_graphs.col_component_members),
        singular_union_count=len(skeleton_graphs.singular_unions),
        sibling_group_count=len(sibling_groups),
        residual_u=solved_u.residual_norm,
        residual_v=solved_v.residual_norm,
        notes=tuple(notes),
        skeleton_graphs=skeleton_graphs,
        sibling_groups=sibling_groups,
        junctions=junctions,
        junctions_by_vert_index=junctions_by_vert_index,
        quilt_scaffold=rebuilt_quilt_scaffold,
        solved_u_components=solved_u.component_values,
        solved_v_components=solved_v.component_values,
        pure_free_junction_count=pure_free_junction_count,
        unconstrained_row_junction_count=unconstrained_row_junction_count,
        unconstrained_col_junction_count=unconstrained_col_junction_count,
    )


def apply_skeleton_solve_to_scaffold_map(
    graph: PatchGraph,
    derived_topology: _PatchGraphDerivedTopology,
    scaffold_map: ScaffoldMap,
    *,
    solve_plan=None,
    final_scale: float = 1.0,
) -> tuple[ScaffoldMap, tuple[SkeletonSolveReport, ...]]:
    """S5 integration helper over the full scaffold map."""

    if not USE_SKELETON_SOLVE or not scaffold_map.quilts:
        return scaffold_map, ()

    quilt_plan_by_index = {
        quilt.quilt_index: quilt
        for quilt in getattr(solve_plan, "quilts", ())
    }
    updated_quilts = []
    reports = []

    for quilt_scaffold in scaffold_map.quilts:
        quilt_plan = quilt_plan_by_index.get(quilt_scaffold.quilt_index)
        has_non_tree_closure = _quilt_has_non_tree_closure(quilt_plan)
        if has_non_tree_closure:
            report = SkeletonSolveReport(
                applied=False,
                quilt_scaffold=quilt_scaffold,
                notes=("skeleton_skip_non_tree_closure",),
            )
            quilt_scaffold.skeleton_solve_report = report
            reports.append(report)
            updated_quilts.append(quilt_scaffold)
            trace_console(
                f"[CFTUV][Skeleton] Quilt {quilt_scaffold.quilt_index}: "
                f"skip non-tree closure quilt"
            )
            continue

        report = apply_skeleton_solve(
            SkeletonSolveInput(
                graph=graph,
                derived_topology=derived_topology,
                quilt_scaffold=quilt_scaffold,
                final_scale=final_scale,
            )
        )

        reports.append(report)

        updated_quilt = report.quilt_scaffold if report.quilt_scaffold is not None else quilt_scaffold
        updated_quilt.skeleton_solve_report = report
        if report.notes == ("skeleton_skip_non_wall_quilt",):
            trace_console(
                f"[CFTUV][Skeleton] Quilt {updated_quilt.quilt_index}: "
                f"skip non-wall-or-mixed quilt"
            )

        quilt_plan = quilt_plan_by_index.get(updated_quilt.quilt_index)
        if quilt_plan is not None:
            allowed_tree_edges = _build_quilt_tree_edges(quilt_plan)
            placed_chains_map = {
                (placement.patch_id, placement.loop_index, placement.chain_index): placement
                for patch_placement in updated_quilt.patches.values()
                if patch_placement is not None and not patch_placement.notes
                for placement in patch_placement.chain_placements
            }
            updated_quilt.closure_seam_reports = _collect_quilt_closure_seam_reports(
                graph,
                quilt_plan,
                updated_quilt,
                placed_chains_map,
                final_scale,
                allowed_tree_edges,
            )
            updated_quilt.frame_alignment_reports = _collect_quilt_frame_alignment_reports(
                graph,
                quilt_plan,
                updated_quilt,
                final_scale,
                updated_quilt.closure_seam_reports,
            )
            _print_quilt_closure_seam_reports(updated_quilt.quilt_index, updated_quilt.closure_seam_reports)
            _print_quilt_frame_alignment_reports(updated_quilt.quilt_index, updated_quilt.frame_alignment_reports)

        if report.residual_u is not None or report.residual_v is not None:
            trace_console(
                f"[CFTUV][Skeleton] Quilt {updated_quilt.quilt_index}: "
                f"rows={report.row_component_count} cols={report.col_component_count} "
                f"splits={report.singular_union_count} siblings={report.sibling_group_count} "
                f"residual_u={float(report.residual_u or 0.0):.6f} "
                f"residual_v={float(report.residual_v or 0.0):.6f}"
            )

        updated_quilts.append(updated_quilt)

    return ScaffoldMap(quilts=updated_quilts), tuple(reports)


__all__ = [
    "SkeletonSolveInput",
    "SingularUnionReport",
    "SkeletonGraphs",
    "SkeletonSolveReport",
    "SkeletonAxisSolveResult",
    "SiblingGroup",
    "build_skeleton_graphs",
    "build_sibling_groups",
    "apply_skeleton_solve",
    "apply_skeleton_solve_to_scaffold_map",
]
