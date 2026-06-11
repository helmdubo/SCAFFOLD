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
    worst_equation_residuals: tuple[dict[str, Any], ...]


def apply_skeleton_solve(context: Any, islands: list[dict[str, Any]], rails: list[dict[str, Any]], assignments):
    relations = context.relation_snapshot
    evidence_by_id = {item.id: item for item in relations.patch_chain_directional_evidence}
    edge_by_patch_chain_id = {edge.patch_chain_id: edge for edge in relations.scaffold_edges}
    node_position_by_id = _node_position_by_id(relations.scaffold_nodes, context.geometry_facts)
    node_ids = tuple(node.id for node in relations.scaffold_nodes)
    island_by_patch_id = {
        patch_id: island["id"]
        for island in islands
        for patch_id in island["patch_ids"]
    }

    graph_a = UnionFind(node_ids)
    graph_b = UnionFind(node_ids)
    chain_rows = _axis_chain_rows(
        rails,
        evidence_by_id,
        edge_by_patch_chain_id,
        island_by_patch_id,
        node_position_by_id,
    )
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

    canonical_vertices = _canonical_vertices(relations.scaffold_nodes, systems, chain_rows)
    write_stats = _write_back(assignments, canonical_vertices)
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
        "canonical_vertices": canonical_vertices,
        "per_island": _per_island_report(islands, chain_rows, systems),
        "post_hoc_3d_spread_check": {
            "used_for_regrouping": False,
            "A": spread_checks["A"],
            "B": spread_checks["B"],
        },
        "write_back": write_stats,
    }


def _axis_chain_rows(rails, evidence_by_id, edge_by_patch_chain_id, island_by_patch_id, node_position_by_id):
    rows_by_key = {}
    for rail in rails:
        role = rail.get("axis_role")
        if role not in ("AXIS_A", "AXIS_B"):
            continue
        rail_direction = rail.get("axis_direction") or _rail_direction(
            evidence_by_id.get(member_id)
            for member_id in rail.get("member_directional_evidence_ids", ())
        )
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
            key = (island_id, role, str(edge.chain_id))
            row = {
                "island_id": island_id,
                "rail_id": rail["id"],
                "axis_role": role,
                "patch_chain_id": str(evidence.patch_chain_id),
                "chain_id": str(edge.chain_id),
                "start_node_id": edge.start_scaffold_node_id,
                "end_node_id": edge.end_scaffold_node_id,
                "orientation_sign": _edge_axis_sign(
                    edge.start_scaffold_node_id,
                    edge.end_scaffold_node_id,
                    node_position_by_id,
                    rail_direction,
                    evidence,
                ),
                "length": float(evidence.length),
            }
            if key not in rows_by_key or row["patch_chain_id"] < rows_by_key[key]["patch_chain_id"]:
                rows_by_key[key] = row
    return [
        rows_by_key[key]
        for key in sorted(rows_by_key)
    ]


def _rail_direction(evidence_items):
    items = [item for item in evidence_items if item is not None]
    if not items:
        return (0.0, 0.0, 0.0)
    seed = max(items, key=lambda item: (item.length, item.id)).direction
    if _vector_length(seed) == 0.0:
        return (0.0, 0.0, 0.0)
    seed = _normalize(seed)
    total = [0.0, 0.0, 0.0]
    for evidence in items:
        direction = evidence.direction
        if _vector_length(direction) == 0.0:
            continue
        direction = _normalize(direction)
        if _dot(direction, seed) < 0.0:
            direction = tuple(-value for value in direction)
        for index in range(3):
            total[index] += direction[index] * evidence.length
    vector = tuple(total)
    return _normalize(vector) if _vector_length(vector) > 0.0 else seed


def _node_position_by_id(scaffold_nodes, geometry):
    rows = {}
    for node in scaffold_nodes:
        positions = [
            geometry.vertex_facts[vertex_id].position
            for vertex_id in node.vertex_ids
            if vertex_id in geometry.vertex_facts
        ]
        if positions:
            rows[node.id] = tuple(
                sum(position[index] for position in positions) / len(positions)
                for index in range(3)
            )
    return rows


def _edge_axis_sign(start_node_id, end_node_id, node_position_by_id, rail_direction, evidence):
    start = node_position_by_id.get(start_node_id)
    end = node_position_by_id.get(end_node_id)
    if start is None or end is None or _vector_length(rail_direction) == 0.0:
        return int(evidence.orientation_sign)
    edge_direction = tuple(end[index] - start[index] for index in range(3))
    if _vector_length(edge_direction) == 0.0:
        return int(evidence.orientation_sign)
    return 1 if _dot(_normalize(edge_direction), rail_direction) >= 0.0 else -1


def _dot(first, second):
    return sum(first[index] * second[index] for index in range(3))


def _vector_length(vector):
    return sqrt(sum(value * value for value in vector))


def _normalize(vector):
    size = _vector_length(vector)
    if size == 0.0:
        return (0.0, 0.0, 0.0)
    return tuple(value / size for value in vector)


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
    length_equations = []
    for row in chain_rows:
        if row["axis_role"] != equation_role:
            continue
        first_component = component_by_node.get(row["start_node_id"])
        second_component = component_by_node.get(row["end_node_id"])
        if first_component is None or second_component is None or first_component == second_component:
            continue
        rhs_value = row["orientation_sign"] * row["length"]
        matrix_row = [0.0] * len(component_ids)
        matrix_row[variable_index[first_component]] = -1.0
        matrix_row[variable_index[second_component]] = 1.0
        matrix_rows.append(matrix_row)
        rhs.append(rhs_value)
        length_equations.append({
            "chain_id": row["chain_id"],
            "patch_chain_id": row["patch_chain_id"],
            "first_component": first_component,
            "second_component": second_component,
            "rhs": rhs_value,
            "length": row["length"],
            "orientation_sign": row["orientation_sign"],
        })

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
        equation_residuals = _equation_residuals(solution, variable_index, length_equations)
        residual_rms = _residual_rms(equation_residuals)
        values = {
            component_id: round(float(solution[index]), 6)
            for component_id, index in variable_index.items()
        }
        worst_equation_residuals = _worst_equation_residuals(equation_residuals)
    if not matrix_rows:
        worst_equation_residuals = ()

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
        equation_count=len(length_equations),
        variable_count=len(component_ids),
        unconstrained_components=unconstrained,
        worst_equation_residuals=worst_equation_residuals,
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


def _equation_residuals(solution, variable_index, equations):
    rows = []
    for equation in equations:
        first = solution[variable_index[equation["first_component"]]]
        second = solution[variable_index[equation["second_component"]]]
        residual = float(second - first - equation["rhs"])
        rows.append({
            **equation,
            "residual": residual,
            "abs_residual": abs(residual),
        })
    return rows


def _residual_rms(equation_residuals):
    if not equation_residuals:
        return 0.0
    return float(sqrt(sum(row["residual"] ** 2 for row in equation_residuals) / len(equation_residuals)))


def _worst_equation_residuals(equation_residuals):
    rows = sorted(equation_residuals, key=lambda row: (-row["abs_residual"], row["chain_id"]))[:3]
    return tuple(
        {
            "chain_id": row["chain_id"],
            "patch_chain_id": row["patch_chain_id"],
            "residual": round(row["residual"], 12),
            "abs_residual": round(row["abs_residual"], 12),
            "rhs": round(row["rhs"], 6),
            "length": round(row["length"], 6),
            "orientation_sign": row["orientation_sign"],
        }
        for row in rows
    )


def _canonical_vertices(scaffold_nodes, systems, chain_rows):
    axis_node_ids = {
        row[field]
        for row in chain_rows
        for field in ("start_node_id", "end_node_id")
    }
    rows = {}
    for node in scaffold_nodes:
        if node.id not in axis_node_ids:
            continue
        coord_a, component_a = _coord_for_node(systems["A"], node.id)
        coord_b, component_b = _coord_for_node(systems["B"], node.id)
        for vertex_id in node.vertex_ids:
            rows[str(vertex_id)] = {
                "A": coord_a,
                "B": coord_b,
                "component_A": component_a,
                "component_B": component_b,
                "axis_count": int(coord_a is not None) + int(coord_b is not None),
            }
    return rows


def _coord_for_node(system, node_id):
    component_id = system.component_by_node.get(node_id)
    if component_id is None or component_id in system.unconstrained_components:
        return None, component_id
    return system.values_by_component.get(component_id), component_id


def _write_back(assignments, canonical_vertices):
    solved_vertices = {
        vertex_id: row
        for vertex_id, row in canonical_vertices.items()
        if row["A"] is not None and row["B"] is not None
    }
    changed = 0
    added = 0
    for vertex_id, canonical in solved_vertices.items():
        solved_uv = [round(float(canonical["A"]), 6), round(float(canonical["B"]), 6)]
        rows = assignments.setdefault(vertex_id, [])
        pinned_rows = [row for row in rows if row.get("pinned")]
        if not pinned_rows:
            rows.append({
                "island_id": None,
                "uv": solved_uv,
                "pinned": True,
                "source": "skeleton canonical component write-back",
                "skeleton_solve": True,
            })
            added += 1
            continue
        for row in pinned_rows:
            if not row.get("pinned"):
                continue
            row["uv"] = solved_uv
            row["skeleton_solve"] = True
            changed += 1
    return {
        "pinned_assignment_updates": changed,
        "pinned_assignment_additions": added,
        "skeleton_vertex_count": len(solved_vertices),
        "axis_coord_coverage_percent": _canonical_coverage(canonical_vertices),
        "note": "Canonical component write-back owns vertices with both axis coordinates; frontier handles one/zero-axis fallback.",
    }


def _canonical_coverage(canonical_vertices):
    counts = {0: 0, 1: 0, 2: 0}
    for row in canonical_vertices.values():
        counts[row["axis_count"]] += 1
    total = sum(counts.values())
    if total == 0:
        return {"both": 0.0, "one": 0.0, "zero": 0.0}
    return {
        "both": round(100.0 * counts[2] / total, 2),
        "one": round(100.0 * counts[1] / total, 2),
        "zero": round(100.0 * counts[0] / total, 2),
    }


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
        "worst_equation_residuals": list(system.worst_equation_residuals),
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
