"""
Layer: 5 - Runtime

Rules:
- Per-axis least-squares solve of one island skeleton (G5a): nodes joined by
  cross-axis runs share one coordinate (a component); each own-axis run is
  one length equation between two components.
- Every connected group of equations is solved with its own gauge; no
  singular block is left to the dense solver.
- An island with a rigid unfolded frame anchors every group to the frame:
  the mean of its nodes' solved coordinate equals the mean of their frame
  coordinate. Without a frame only the largest group keeps coordinates;
  the others stay unpinned with one diagnostic per axis.
- Contradictions -> UNCONSTRAINED + diagnostics, never silent smearing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from scaffold_core.layer_2_geometry.measures import dot, normalize

RESIDUAL_TOLERANCE = 1e-5
# Modelling drift the solve absorbs: 1 mm per metre of the island's span
# along the axis (plan Slice S); larger residuals are contradictions.
RESIDUAL_TOLERANCE_PER_SPAN = 1e-3
GAUGE_WEIGHT = 1e6


@dataclass(frozen=True)
class AxisSolve:
    axis: str
    coordinate_by_node: Mapping[str, float]
    residual_max: float
    unconstrained_components: tuple[int, ...]
    equation_count: int
    # Framed island: nodes whose coordinate is their frame coordinate alone
    # (their component has no equation on this axis).
    frame_only_nodes: frozenset[str] = field(default_factory=frozenset)


def axis_components(runs, roles, role_name, node_by_run_end):
    parents: dict[str, str] = {}

    def find(item: str) -> str:
        parents.setdefault(item, item)
        while parents[item] != item:
            parents[item] = parents[parents[item]]
            item = parents[item]
        return item

    for e in runs:
        start = node_by_run_end[(e.id, "START")]
        end = node_by_run_end[(e.id, "END")]
        parents.setdefault(start, start)
        parents.setdefault(end, end)
        if roles.get(e.id) == role_name:
            ra, rb = find(start), find(end)
            if ra != rb:
                parents[max(ra, rb)] = min(ra, rb)
    return {node: find(node) for node in parents}


def solve_axis(
    axis_name, runs, roles, signs, node_by_run_end, diagnostics, direction_of=None, drift=None, length_of=None,
    frame_coordinate_by_node=None,
):
    """P7 semantics: the A coordinate lives on COLUMN components (nodes
    connected by AXIS_B runs share one A value) and is constrained by
    AXIS_A run lengths; symmetric for B on ROW components.

    direction_of supplies run directions in the island frame when one exists.
    length_of overrides run lengths (a strip island's scaled lengths).
    frame_coordinate_by_node gives, in an island with a rigid unfolded frame,
    each node's frame coordinate along this axis; None without a frame.
    """

    own_role = "AXIS_A" if axis_name == "AXIS_A" else "AXIS_B"
    cross_role = "AXIS_B" if axis_name == "AXIS_A" else "AXIS_A"
    component_of = axis_components(runs, roles, cross_role, node_by_run_end)
    equations = []
    for e in runs:
        if roles.get(e.id) != own_role or e.id not in signs:
            continue  # an unsigned run (unordered island rail) adds no equation
        start = component_of.get(node_by_run_end[(e.id, "START")])
        end = component_of.get(node_by_run_end[(e.id, "END")])
        if start is None or end is None or start == end:
            continue
        run_length = e.length if length_of is None else length_of[e.id]
        equations.append([start, end, signs[e.id] * run_length, e.id, e])
    # Runs connecting the same two cross-components are mutually parallel
    # on a developable region: normalize their signs to the group's first
    # run so parallel columns/rails cannot contradict each other.
    reference_by_pair = {}
    for equation in equations:
        start, end, value, _eid, e = equation
        pair = (min(start, end), max(start, end))
        direction = e.direction if direction_of is None else direction_of[e.id]
        oriented = tuple(c * (1.0 if value >= 0.0 else -1.0) for c in direction)
        if pair not in reference_by_pair:
            reference_by_pair[pair] = (oriented, start, end)
            continue
        ref_dir, _ref_start, _ref_end = reference_by_pair[pair]
        # On a developable region runs between the same two rails are
        # parallel: the coordinate grows along the reference direction,
        # so the equation sign follows the dot sign alone.
        if dot(normalize(oriented), normalize(ref_dir)) < 0.0:
            equation[2] = -value
    equations = [(eq[0], eq[1], eq[2], eq[3]) for eq in equations]
    coords, residuals = _lstsq(equations)
    if drift is None:
        spans = [
            max(coords[component] for component in group) - min(coords[component] for component in group)
            for group in _equation_groups(equations)
        ]
        drift = RESIDUAL_TOLERANCE_PER_SPAN * max(spans, default=0.0)
    # In a rigid frame the jog check and the solve share one drift (plan Slice U).
    tolerance = max(RESIDUAL_TOLERANCE, drift)
    bad = [i for i, r in enumerate(residuals) if abs(r) > tolerance]
    unconstrained: tuple[int, ...] = ()
    bad_components: set[str] = set()
    kept = equations
    if bad:
        bad_components = {equations[i][0] for i in bad} | {equations[i][1] for i in bad}
        diagnostics.append(
            f"{axis_name}: {len(bad)} contradictory equations -> UNCONSTRAINED components"
        )
        kept = [
            eq for index, eq in enumerate(equations)
            if index not in set(bad) and eq[0] not in bad_components and eq[1] not in bad_components
        ]
        coords, residuals = _lstsq(kept)
        unconstrained = tuple(sorted({index for index in bad}))
    residual_max = max((abs(r) for r in residuals), default=0.0)
    coords, alone = _place_groups(
        axis_name, coords, kept, component_of, bad_components, frame_coordinate_by_node, diagnostics
    )
    coordinate_by_node = {
        node: coords[component]
        for node, component in component_of.items()
        if component in coords
    }
    frame_only = frozenset(node for node, component in component_of.items() if component in alone)
    return AxisSolve(axis_name, coordinate_by_node, residual_max, unconstrained, len(equations), frame_only)


def _place_groups(axis_name, coords, equations, component_of, excluded, frame_coordinate_by_node, diagnostics):
    """Give each equation group (and each component without an equation) its origin.

    Framed island: a group is shifted so the mean of its nodes' solved
    coordinate equals the mean of their frame coordinate; a component with no
    equation takes the mean frame coordinate of its nodes. Without a frame the
    largest group (by node count; tie: the group holding the lexically
    smallest node id) keeps its coordinates and the other groups are dropped.
    Dropped groups are counted in one diagnostic. Every equation comes from
    a framed run, so in a frame each group has framed nodes. UNCONSTRAINED
    components stay excluded.
    Returns the placed coordinates and the components placed from the frame
    alone.
    """

    nodes_by_component: dict[str, list[str]] = {}
    for node, component in sorted(component_of.items()):
        nodes_by_component.setdefault(component, []).append(node)
    groups = _equation_groups(equations)
    dropped: list[list[str]] = []
    placed: dict[str, float] = {}
    alone: set[str] = set()
    if frame_coordinate_by_node is None:
        if groups:
            main = min(groups, key=lambda group: (
                -sum(len(nodes_by_component[component]) for component in group),
                min(node for component in group for node in nodes_by_component[component]),
            ))
            placed = {component: coords[component] for component in main}
            dropped = [group for group in groups if group is not main]
    else:
        grouped = {component for group in groups for component in group}
        singles = [
            [component] for component in sorted(nodes_by_component)
            if component not in grouped and component not in excluded
        ]
        for group in groups + singles:
            offsets = [
                frame_coordinate_by_node[node] - coords.get(component, 0.0)
                for component in group
                for node in nodes_by_component[component]
                if node in frame_coordinate_by_node
            ]
            if not offsets:
                continue  # only a component with no equation can lie outside the frame
            shift = sum(offsets) / len(offsets)
            if group[0] not in grouped:
                alone.add(group[0])
            for component in group:
                placed[component] = coords.get(component, 0.0) + shift
    if dropped:
        node_count = sum(len(nodes_by_component[component]) for group in dropped for component in group)
        diagnostics.append(
            f"{axis_name}: {node_count} nodes in {len(dropped)} equation groups not tied to the gauge -> unpinned"
        )
    return placed, alone


def _equation_groups(equations) -> list[list[str]]:
    """Components joined by equations, each group sorted, groups by first member."""

    parents: dict[str, str] = {}

    def find(item: str) -> str:
        parents.setdefault(item, item)
        while parents[item] != item:
            parents[item] = parents[parents[item]]
            item = parents[item]
        return item

    for start, end, _value, _eid in equations:
        ra, rb = find(start), find(end)
        if ra != rb:
            parents[max(ra, rb)] = min(ra, rb)
    members: dict[str, list[str]] = {}
    for item in sorted(parents):
        members.setdefault(find(item), []).append(item)
    return [members[root] for root in sorted(members)]


def _lstsq(equations):
    """Least squares per equation group; each group gauges its first component."""

    coords: dict[str, float] = {}
    group_of: dict[str, int] = {}
    groups = _equation_groups(equations)
    for group_index, group in enumerate(groups):
        for node in group:
            group_of[node] = group_index
    equations_by_group: dict[int, list] = {}
    for equation in equations:
        equations_by_group.setdefault(group_of[equation[0]], []).append(equation)
    for group_index, nodes in enumerate(groups):
        index = {node: i for i, node in enumerate(nodes)}
        n = len(nodes)
        ata = [[0.0] * n for _ in range(n)]
        atb = [0.0] * n
        for start, end, value, _eid in equations_by_group[group_index]:
            for (a, ca) in ((index[end], 1.0), (index[start], -1.0)):
                atb[a] += ca * value
                for (b, cb) in ((index[end], 1.0), (index[start], -1.0)):
                    ata[a][b] += ca * cb
        # gauge: pin the group's first node to zero
        ata[0][0] += GAUGE_WEIGHT
        solution = _solve_dense(ata, atb)
        coords.update({node: solution[index[node]] for node in nodes})
    residuals = [coords[end] - coords[start] - value for start, end, value, _eid in equations]
    return coords, residuals


def _solve_dense(matrix, vector):
    n = len(vector)
    a = [row[:] + [vector[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-12:
            continue
        a[col], a[pivot] = a[pivot], a[col]
        factor = a[col][col]
        a[col] = [v / factor for v in a[col]]
        for row in range(n):
            if row != col and abs(a[row][col]) > 0.0:
                scale = a[row][col]
                a[row] = [rv - scale * cv for rv, cv in zip(a[row], a[col])]
    return [a[i][n] for i in range(n)]
