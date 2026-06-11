"""
Disposable skeleton solve for tracer spike v3.

This module is outside scaffold_core and consumes Pass 0/1 snapshots read-only.
It implements a small dense-lstsq consumer pass over existing ScaffoldNodes,
ScaffoldEdges and G1 island-local axis-role views.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import sqrt
from typing import Any

import numpy as np


GAUGE_WEIGHT = 1.0e6
LEVEL_B_PLACEHOLDER_NOTE = (
    "LEVEL_B_PLACEHOLDER: sibling equivalence for repeated openings is deferred "
    "until walls.004/G4 validates which grammar constraint should own it."
)


class UnionFind:
    def __init__(self, values):
        self.parent = {value: value for value in values}

    def find(self, value):
        parent = self.parent.setdefault(value, value)
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, first, second):
        first_root = self.find(first)
        second_root = self.find(second)
        if first_root == second_root:
            return
        root = min(first_root, second_root)
        other = max(first_root, second_root)
        self.parent[other] = root

    def components(self):
        rows = defaultdict(list)
        for value in sorted(self.parent):
            rows[self.find(value)].append(value)
        return {root: tuple(values) for root, values in rows.items()}


@dataclass(frozen=True)
class AxisSystem:
    coordinate_name: str
    component_graph_name: str
    equation_role: str
    component_by_node: dict[str, str]
    values_by_component: dict[str, float]
    residual_rms: float
    equation_count: int
    variable_count: int
    unconstrained_components: tuple[str, ...]


def apply_skeleton_solve(context: Any, islands: list[dict[str, Any]], rails: list[dict[str, Any]], assignments):
    relations = context.relation_snapshot
    evidence_by_id = {item.id: item for item in relations.patch_chain_directional_evidence}
    edge_by_patch_chain_id = {edge.patch_chain_id: edge for edge in relations.scaffold_edges}
    node_ids = tuple(node.id for node in relations.scaffold_nodes)
    island_by_patch_id = {
        patch_id: island["id"]
        for island in islands
        for patch_id in island["patch_ids"]
    }

    graph_a = UnionFind(node_ids)
    graph_b = UnionFind(node_ids)
    rail_by_id = {rail["id"]: rail for rail in rails}
    chain_rows = _axis_chain_rows(rails, evidence_by_id, edge_by_patch_chain_id, island_by_patch_id)
    for row in chain_rows:
        if row["axis_role"] == "AXIS_A":
            graph_a.union(row["start_node_id"], row["end_node_id"])
        elif row["axis_role"] == "AXIS_B":
            graph_b.union(row["start_node_id"], row["end_node_id"])

    components_a = graph_a.components()
    components_b = graph_b.components()
    component_a_by_node = _component_by_node(components_a)
    component_b_by_node = _component_by_node(components_b)
    seed_nodes_by_island = _seed_nodes_by_island(islands, relations)
    systems = {
        "A": _solve_axis(
            coordinate_name="A",
            component_graph_name="B",
            equation_role="AXIS_A",
            components=components_b,
            component_by_node=component_b_by_node,
            chain_rows=chain_rows,
            seed_nodes_by_island=seed_nodes_by_island,
        ),
        "B": _solve_axis(
            coordinate_name="B",
            component_graph_name="A",
            equation_role="AXIS_B",
            components=components_a,
            component_by_node=component_a_by_node,
            chain_rows=chain_rows,
            seed_nodes_by_island=seed_nodes_by_island,
        ),
    }
    spread_checks = {
        "A": _spread_report(components_a, relations.scaffold_nodes, context.source_snapshot),
        "B": _spread_report(components_b, relations.scaffold_nodes, context.source_snapshot),
    }

    write_stats = _write_back(assignments, rail_by_id, systems)
    return {
        "policy": "tracer_spike_skeleton_solve_v0",
        "level_b_placeholder": LEVEL_B_PLACEHOLDER_NOTE,
        "component_graphs": {
            "A": _component_report(components_a, systems["B"], spread_checks["A"]),
            "B": _component_report(components_b, systems["A"], spread_checks["B"]),
        },
        "axis_systems": {
            axis: _axis_system_report(system)
            for axis, system in systems.items()
        },
        "per_island": _per_island_report(islands, chain_rows, systems),
        "post_hoc_3d_spread_check": {
            "used_for_regrouping": False,
            "A": spread_checks["A"],
            "B": spread_checks["B"],
        },
        "write_back": write_stats,
    }


def _axis_chain_rows(rails, evidence_by_id, edge_by_patch_chain_id, island_by_patch_id):
    rows = []
    seen = set()
    for rail in rails:
        role = rail.get("axis_role")
        if role not in ("AXIS_A", "AXIS_B"):
            continue
        for member_id in rail.get("member_directional_evidence_ids", ()):
            evidence = evidence_by_id.get(member_id)
            if evidence is None:
                continue
            edge = edge_by_patch_chain_id.get(evidence.patch_chain_id)
            if edge is None:
                continue
            island_id = rail["island_id"]
            if island_by_patch_id.get(str(evidence.patch_id)) != island_id:
                continue
            key = (
                island_id,
                role,
                str(edge.chain_id),
                edge.start_scaffold_node_id,
                edge.end_scaffold_node_id,
                round(float(evidence.length), 12),
            )
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "island_id": island_id,
                "rail_id": rail["id"],
                "axis_role": role,
                "patch_chain_id": str(evidence.patch_chain_id),
                "chain_id": str(edge.chain_id),
                "start_node_id": edge.start_scaffold_node_id,
                "end_node_id": edge.end_scaffold_node_id,
                "orientation_sign": int(evidence.orientation_sign),
                "length": float(evidence.length),
            })
    return rows


def _component_by_node(components):
    return {
        node_id: root
        for root, node_ids in components.items()
        for node_id in node_ids
    }


def _seed_nodes_by_island(islands, relations):
    seed_nodes = {}
    for island in islands:
        seed_patch_id = island["seed_patch_id"]
        candidates = [
            edge.start_scaffold_node_id
            for edge in relations.scaffold_edges
            if str(edge.patch_id) == seed_patch_id
        ]
        candidates.extend(
            edge.end_scaffold_node_id
            for edge in relations.scaffold_edges
            if str(edge.patch_id) == seed_patch_id
        )
        seed_nodes[island["id"]] = min(candidates) if candidates else None
    return seed_nodes


def _solve_axis(
    coordinate_name,
    component_graph_name,
    equation_role,
    components,
    component_by_node,
    chain_rows,
    seed_nodes_by_island,
):
    component_ids = sorted(components)
    variable_index = {component_id: index for index, component_id in enumerate(component_ids)}
    matrix_rows = []
    rhs = []
    for row in chain_rows:
        if row["axis_role"] != equation_role:
            continue
        first_component = component_by_node.get(row["start_node_id"])
        second_component = component_by_node.get(row["end_node_id"])
        if first_component is None or second_component is None or first_component == second_component:
            continue
        rhs_value = row["orientation_sign"] * row["length"]
        if second_component < first_component:
            first_component, second_component = second_component, first_component
            rhs_value = -rhs_value
        rhs_value = abs(rhs_value)
        matrix_row = [0.0] * len(component_ids)
        matrix_row[variable_index[first_component]] = -1.0
        matrix_row[variable_index[second_component]] = 1.0
        matrix_rows.append(matrix_row)
        rhs.append(rhs_value)

    gauged = set()
    for seed_node_id in seed_nodes_by_island.values():
        if seed_node_id is None:
            continue
        component_id = component_by_node.get(seed_node_id)
        if component_id is None or component_id in gauged:
            continue
        matrix_row = [0.0] * len(component_ids)
        matrix_row[variable_index[component_id]] = GAUGE_WEIGHT
        matrix_rows.append(matrix_row)
        rhs.append(0.0)
        gauged.add(component_id)

    if not component_ids:
        values = {}
        residual_rms = 0.0
    elif not matrix_rows:
        values = {component_id: 0.0 for component_id in component_ids}
        residual_rms = 0.0
    else:
        matrix = np.asarray(matrix_rows, dtype=float)
        target = np.asarray(rhs, dtype=float)
        solution, *_ = np.linalg.lstsq(matrix, target, rcond=None)
        residual = matrix @ solution - target
        residual_rms = float(sqrt(float(np.mean(residual * residual)))) if len(residual) else 0.0
        values = {
            component_id: round(float(solution[index]), 6)
            for component_id, index in variable_index.items()
        }

    constrained = _constrained_components(chain_rows, equation_role, component_by_node) | gauged
    unconstrained = tuple(
        component_id for component_id in component_ids
        if component_id not in constrained
    )
    return AxisSystem(
        coordinate_name=coordinate_name,
        component_graph_name=component_graph_name,
        equation_role=equation_role,
        component_by_node=dict(component_by_node),
        values_by_component=values,
        residual_rms=round(residual_rms, 12),
        equation_count=sum(1 for row in chain_rows if row["axis_role"] == equation_role),
        variable_count=len(component_ids),
        unconstrained_components=unconstrained,
    )


def _constrained_components(chain_rows, equation_role, component_by_node):
    constrained = set()
    for row in chain_rows:
        if row["axis_role"] != equation_role:
            continue
        for node_field in ("start_node_id", "end_node_id"):
            component_id = component_by_node.get(row[node_field])
            if component_id is not None:
                constrained.add(component_id)
    return constrained


def _write_back(assignments, rail_by_id, systems):
    del systems
    axis_rows = []
    for vertex_id, rows in assignments.items():
        for row in rows:
            rail = rail_by_id.get(str(row.get("source")))
            if rail is None or rail.get("axis_role") not in ("AXIS_A", "AXIS_B"):
                continue
            u, v = row["uv"]
            axis_rows.append((vertex_id, rail["id"], rail["axis_role"], float(u), float(v)))
    solved_vertices, residual_rms = _solve_vertex_writeback(axis_rows)
    changed = 0
    for vertex_id, solved_uv in solved_vertices.items():
        for row in assignments.get(vertex_id, ()):
            if not row.get("pinned"):
                continue
            row["uv"] = solved_uv
            row["skeleton_solve"] = True
            changed += 1
    return {
        "pinned_assignment_updates": changed,
        "skeleton_vertex_count": len(solved_vertices),
        "vertex_writeback_residual_rms": residual_rms,
        "note": "Canonical write-back solved rail-station constraints after dense component solve.",
    }


def _solve_vertex_writeback(axis_rows):
    vertex_ids = sorted({row[0] for row in axis_rows})
    if not vertex_ids:
        return {}, 0.0
    variable_names = []
    for vertex_id in vertex_ids:
        variable_names.extend((f"vertex:{vertex_id}:A", f"vertex:{vertex_id}:B"))
    for rail_id in sorted({row[1] for row in axis_rows}):
        variable_names.extend((f"rail:{rail_id}:offset", f"rail:{rail_id}:fixed"))
    variable_index = {name: index for index, name in enumerate(variable_names)}
    rows = []
    rhs = []

    def add_equation(coefficients, target, weight=1.0):
        row = [0.0] * len(variable_names)
        for name, coefficient in coefficients.items():
            row[variable_index[name]] = coefficient * weight
        rows.append(row)
        rhs.append(target * weight)

    for vertex_id, rail_id, axis_role, station_u, station_v in axis_rows:
        vertex_a = f"vertex:{vertex_id}:A"
        vertex_b = f"vertex:{vertex_id}:B"
        rail_offset = f"rail:{rail_id}:offset"
        rail_fixed = f"rail:{rail_id}:fixed"
        if axis_role == "AXIS_A":
            add_equation({vertex_a: 1.0, rail_offset: -1.0}, station_u)
            add_equation({vertex_b: 1.0, rail_fixed: -1.0}, 0.0)
        elif axis_role == "AXIS_B":
            add_equation({vertex_a: 1.0, rail_fixed: -1.0}, 0.0)
            add_equation({vertex_b: 1.0, rail_offset: -1.0}, station_u if station_u else station_v)

    first_vertex = vertex_ids[0]
    add_equation({f"vertex:{first_vertex}:A": 1.0}, 0.0, GAUGE_WEIGHT)
    add_equation({f"vertex:{first_vertex}:B": 1.0}, 0.0, GAUGE_WEIGHT)
    matrix = np.asarray(rows, dtype=float)
    target = np.asarray(rhs, dtype=float)
    solution, *_ = np.linalg.lstsq(matrix, target, rcond=None)
    residual = matrix @ solution - target
    residual_rms = float(sqrt(float(np.mean(residual * residual)))) if len(residual) else 0.0
    solved = {}
    for vertex_id in vertex_ids:
        solved[vertex_id] = [
            round(float(solution[variable_index[f"vertex:{vertex_id}:A"]]), 6),
            round(float(solution[variable_index[f"vertex:{vertex_id}:B"]]), 6),
        ]
    return solved, round(residual_rms, 12)


def _spread_report(components, scaffold_nodes, source_snapshot):
    node_by_id = {node.id: node for node in scaffold_nodes}
    report = {}
    for component_id, node_ids in components.items():
        positions = []
        for node_id in node_ids:
            node = node_by_id.get(node_id)
            if node is None:
                continue
            for source_vertex_id in node.source_vertex_ids:
                source_vertex = source_snapshot.vertices.get(source_vertex_id)
                if source_vertex is not None:
                    positions.append(source_vertex.position)
        report[component_id] = {
            "source_position_spread": round(_max_position_spread(positions), 6),
            "unconstrained_by_spread": False,
        }
    return report


def _max_position_spread(positions):
    if len(positions) < 2:
        return 0.0
    maximum = 0.0
    for index, first in enumerate(positions):
        for second in positions[index + 1:]:
            distance = sqrt(sum((second[axis] - first[axis]) ** 2 for axis in range(3)))
            maximum = max(maximum, distance)
    return maximum


def _component_report(components, coordinate_system, spread_checks):
    return {
        "component_count": len(components),
        "components": [
            {
                "id": component_id,
                "node_ids": list(node_ids),
                "canonical_coordinate": coordinate_system.values_by_component.get(component_id),
                "unconstrained": component_id in coordinate_system.unconstrained_components,
                "post_hoc_3d_spread": spread_checks.get(component_id, {}),
            }
            for component_id, node_ids in sorted(components.items())
        ],
    }


def _axis_system_report(system):
    return {
        "coordinate": system.coordinate_name,
        "component_graph": system.component_graph_name,
        "equation_role": system.equation_role,
        "variable_count": system.variable_count,
        "equation_count": system.equation_count,
        "residual_rms": system.residual_rms,
        "unconstrained_components": list(system.unconstrained_components),
    }


def _per_island_report(islands, chain_rows, systems):
    rows_by_island = defaultdict(list)
    for row in chain_rows:
        rows_by_island[row["island_id"]].append(row)
    report = {}
    for island in islands:
        island_id = island["id"]
        rows = rows_by_island.get(island_id, ())
        report[island_id] = {
            "axis_a_chain_count": sum(1 for row in rows if row["axis_role"] == "AXIS_A"),
            "axis_b_chain_count": sum(1 for row in rows if row["axis_role"] == "AXIS_B"),
            "residual_A": systems["A"].residual_rms,
            "residual_B": systems["B"].residual_rms,
            "skeleton_chains": [
                {
                    "rail_id": row["rail_id"],
                    "axis_role": row["axis_role"],
                    "chain_id": row["chain_id"],
                    "length": round(row["length"], 6),
                }
                for row in rows
            ],
        }
    return report
