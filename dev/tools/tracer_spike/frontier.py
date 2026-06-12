"""
Anchor frontier and 2D composition for tracer spike v3.

This is disposable consumer tooling outside scaffold_core. It consumes existing
layout rows, G2 skeleton-solve diagnostics and Pass 1 graph records read-only.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


DEGENERATE_COORD_SHARE_LIMIT = 0.60


def apply_anchor_frontier(context: Any, islands, rails, assignments, skeleton_solve):
    node_by_vertex = _node_by_vertex(context.relation_snapshot.scaffold_nodes)
    canonical = _canonical_coords_by_vertex(context.relation_snapshot.scaffold_nodes, skeleton_solve)
    rail_rows = _rail_assignment_rows(assignments, rails, node_by_vertex)
    placement_order = _place_rails(islands, rail_rows)
    frontier_uv = _frontier_uv_by_vertex(placement_order, rail_rows)
    composition = _compose_uv(assignments, canonical, frontier_uv)
    diagnostics = _diagnostics(islands, assignments, canonical, composition, skeleton_solve)
    return {
        "policy": "tracer_spike_anchor_frontier_v0",
        "rank_tuple": ["viability", "axis_role_tier", "ingress", "length"],
        "placement_order": placement_order,
        "composition": composition,
        "diagnostics": diagnostics,
    }


def build_console_diagnostics(layout):
    summary = layout["summary"]
    diagnostics = layout["frontier"]["diagnostics"]
    histogram = diagnostics["rejected_stitch_defect_histogram"]
    axis = diagnostics["axis_components"]
    coverage = diagnostics["axis_coord_coverage_percent"]
    invariant = layout["skeleton_solve"]["axis_parallel_invariant"]
    lines = [
        "ARCHITECT SUMMARY",
        f"fixture={layout['fixture']} islands={summary['island_count']} rails={summary['rail_count']}",
        f"stitches accepted={summary['stitched_patch_pairs']} rejected={summary['blocked_patch_pairs']}",
        "rejected |defect| buckets "
        f"<1e-3={histogram['lt_1e-3']} 1e-3..1e-2={histogram['1e-3_to_1e-2']} "
        f"1e-2..1e-1={histogram['1e-2_to_1e-1']} >1e-1={histogram['gt_1e-1']}",
        "axis coords skeleton vertices "
        f"both={coverage['both']}% one={coverage['one']}% zero={coverage['zero']}%",
        f"components A={axis['A_component_count']} B={axis['B_component_count']}",
        "lstsq residuals "
        f"A={summary['skeleton_solve_residual_A']} B={summary['skeleton_solve_residual_B']}",
        f"invariant_violations={invariant['violation_count']} oblique_count={summary['unfolded_frame_oblique_count']} "
        f"unconstrained_components={summary['skeleton_solve_unconstrained_component_count']}",
        "degenerate islands="
        f"{','.join(diagnostics['degenerate_island_ids']) if diagnostics['degenerate_island_ids'] else 'none'}",
    ]
    return "\n".join(lines[:15])


def _node_by_vertex(scaffold_nodes):
    rows = {}
    for node in scaffold_nodes:
        for vertex_id in node.vertex_ids:
            rows[str(vertex_id)] = node.id
    return rows


def _canonical_coords_by_vertex(scaffold_nodes, skeleton_solve):
    if skeleton_solve.get("canonical_vertices"):
        return skeleton_solve["canonical_vertices"]
    graph_a = _component_lookup(skeleton_solve, "A")
    graph_b = _component_lookup(skeleton_solve, "B")
    axis_a_available = _axis_available(skeleton_solve, "A")
    axis_b_available = _axis_available(skeleton_solve, "B")
    rows = {}
    for node in scaffold_nodes:
        component_a = graph_a["component_by_node"].get(node.id)
        component_b = graph_b["component_by_node"].get(node.id)
        coord_a = _component_coord(graph_b, component_b) if axis_a_available else None
        coord_b = _component_coord(graph_a, component_a) if axis_b_available else None
        for vertex_id in node.vertex_ids:
            rows[str(vertex_id)] = {
                "A": coord_a,
                "B": coord_b,
                "node_id": node.id,
                "component_A": component_a,
                "component_B": component_b,
            }
    return rows


def _axis_available(skeleton_solve, axis_name):
    system = skeleton_solve["axis_systems"][axis_name]
    return system["variable_count"] > 1 and system["equation_count"] > 0


def _component_lookup(skeleton_solve, graph_name):
    component_by_node = {}
    coordinate_by_component = {}
    unconstrained = set()
    for component in skeleton_solve["component_graphs"][graph_name]["components"]:
        component_id = component["id"]
        coordinate_by_component[component_id] = component.get("canonical_coordinate")
        if component.get("unconstrained"):
            unconstrained.add(component_id)
        for node_id in component.get("node_ids", ()):
            component_by_node[node_id] = component_id
    return {
        "component_by_node": component_by_node,
        "coordinate_by_component": coordinate_by_component,
        "unconstrained": unconstrained,
    }


def _component_coord(graph, component_id):
    if component_id is None or component_id in graph["unconstrained"]:
        return None
    return graph["coordinate_by_component"].get(component_id)


def _rail_assignment_rows(assignments, rails, node_by_vertex):
    rail_by_id = {rail["id"]: rail for rail in rails}
    rows = defaultdict(list)
    for vertex_id, values in assignments.items():
        for value in values:
            rail = rail_by_id.get(str(value.get("source")))
            if rail is None:
                continue
            role = rail.get("axis_role") or "OBLIQUE"
            uv = value.get("frontier_seed_uv", value["uv"])
            station = _station(uv, role)
            rows[rail["id"]].append({
                "vertex_id": vertex_id,
                "node_id": node_by_vertex.get(vertex_id),
                "station": station,
                "uv": tuple(uv),
                "axis_role": role,
                "island_id": rail["island_id"],
                "rail_id": rail["id"],
            })
    for rail_id in rows:
        rows[rail_id].sort(key=lambda item: (item["station"], item["vertex_id"]))
    return rows


def _station(uv, role):
    if role == "AXIS_B":
        return float(uv[1])
    return float(uv[0])


def _place_rails(islands, rail_rows):
    placed_nodes_by_island = defaultdict(set)
    placed_vertices = set()
    remaining = set(rail_rows)
    order = []
    while remaining:
        ranked = [
            (_rank_rail(rail_rows[rail_id], placed_nodes_by_island), rail_id)
            for rail_id in remaining
        ]
        ranked.sort(reverse=True)
        rank, rail_id = ranked[0]
        remaining.remove(rail_id)
        rows = rail_rows[rail_id]
        island_id = rows[0]["island_id"] if rows else "island:unknown"
        anchors = [
            row for row in rows
            if row["node_id"] is not None and row["node_id"] in placed_nodes_by_island[island_id]
        ]
        for row in rows:
            placed_vertices.add(row["vertex_id"])
            if row["node_id"] is not None:
                placed_nodes_by_island[island_id].add(row["node_id"])
        order.append({
            "rail_id": rail_id,
            "island_id": island_id,
            "axis_role": rows[0]["axis_role"] if rows else "OBLIQUE",
            "rank": list(rank),
            "ingress": _ingress_label(len({row["node_id"] for row in anchors if row["node_id"]})),
            "anchor_vertex_ids": sorted({row["vertex_id"] for row in anchors}),
            "placed_vertex_count": len({row["vertex_id"] for row in rows}),
        })
    for island in islands:
        placed_nodes_by_island.setdefault(island["id"], set())
    return order


def _rank_rail(rows, placed_nodes_by_island):
    if not rows:
        return (0, 0, 0, 0.0)
    island_id = rows[0]["island_id"]
    role = rows[0]["axis_role"]
    anchor_count = len({
        row["node_id"] for row in rows
        if row["node_id"] is not None and row["node_id"] in placed_nodes_by_island[island_id]
    })
    ingress = 2 if anchor_count >= 2 else 1 if anchor_count == 1 else 0
    viability = 2 if anchor_count else 1
    role_tier = 1 if role in ("AXIS_A", "AXIS_B") else 0
    length = _rail_length(rows)
    return (viability, role_tier, ingress, length)


def _ingress_label(anchor_count):
    if anchor_count >= 2:
        return "both-anchored"
    if anchor_count == 1:
        return "single"
    return "none"


def _rail_length(rows):
    if len(rows) < 2:
        return 0.0
    return max(row["station"] for row in rows) - min(row["station"] for row in rows)


def _frontier_uv_by_vertex(placement_order, rail_rows):
    rail_index = {row["rail_id"]: index for index, row in enumerate(placement_order)}
    values = defaultdict(lambda: {"A": [], "B": []})
    for rail_id, rows in rail_rows.items():
        if not rows:
            continue
        role = rows[0]["axis_role"]
        min_station = min(row["station"] for row in rows)
        max_station = max(row["station"] for row in rows)
        for row_index, row in enumerate(rows):
            station = float(row_index) if max_station == min_station else row["station"] - min_station
            if role == "AXIS_A":
                values[row["vertex_id"]]["A"].append(station)
                values[row["vertex_id"]]["B"].append(station)
            elif role == "AXIS_B":
                values[row["vertex_id"]]["A"].append(station)
                values[row["vertex_id"]]["B"].append(station)
            else:
                values[row["vertex_id"]]["A"].append(row["uv"][0])
                values[row["vertex_id"]]["B"].append(row["uv"][1])
    return {
        vertex_id: {
            "A": _mean(axes["A"]),
            "B": _mean(axes["B"]),
        }
        for vertex_id, axes in values.items()
    }


def _compose_uv(assignments, canonical, frontier_uv):
    stats = {"both_axis": 0, "one_axis": 0, "zero_axis": 0, "updated_assignments": 0}
    rows = {}
    for vertex_id, values in assignments.items():
        if not any(value.get("pinned") for value in values):
            continue
        canonical_row = canonical.get(vertex_id, {})
        frontier_row = frontier_uv.get(vertex_id, {})
        has_a = canonical_row.get("A") is not None
        has_b = canonical_row.get("B") is not None
        a_value = canonical_row.get("A") if has_a else frontier_row.get("A")
        b_value = canonical_row.get("B") if has_b else frontier_row.get("B")
        if a_value is None or b_value is None:
            fallback = values[0]["uv"]
            a_value = fallback[0] if a_value is None else a_value
            b_value = fallback[1] if b_value is None else b_value
        axis_count = int(has_a) + int(has_b)
        if axis_count == 2:
            if vertex_id in canonical:
                stats["both_axis"] += 1
        elif axis_count == 1:
            if vertex_id in canonical:
                stats["one_axis"] += 1
        else:
            if vertex_id in canonical:
                stats["zero_axis"] += 1
        uv = [round(float(a_value), 6), round(float(b_value), 6)]
        rows[vertex_id] = {"uv": uv, "axis_count": axis_count}
        for value in values:
            if value.get("pinned"):
                value["uv"] = uv
                value["frontier_composed"] = True
                stats["updated_assignments"] += 1
    _break_degenerate_shared_lines(assignments, rows)
    stats["vertex_axis_counts"] = rows
    return stats


def _break_degenerate_shared_lines(assignments, composed_rows):
    vertices_by_island = _pinned_vertices_by_island(assignments)
    for island_vertices in vertices_by_island.values():
        for axis, index in (("A", 0), ("B", 1)):
            counts = Counter(round(float(uv[index]), 6) for uv in island_vertices.values())
            if not counts:
                continue
            value, count = counts.most_common(1)[0]
            if count / len(island_vertices) <= DEGENERATE_COORD_SHARE_LIMIT:
                continue
            affected = [
                vertex_id for vertex_id, uv in sorted(island_vertices.items())
                if round(float(uv[index]), 6) == value
                and composed_rows.get(vertex_id, {}).get("axis_count", 0) < 2
            ]
            for offset_index, vertex_id in enumerate(affected):
                row = composed_rows[vertex_id]
                row["uv"][index] = round(float(row["uv"][index]) + 0.01 * (offset_index + 1), 6)
                row["degenerate_break"] = axis
                for value_row in assignments.get(vertex_id, ()):
                    if value_row.get("pinned"):
                        value_row["uv"] = list(row["uv"])
                        value_row["frontier_degenerate_break"] = axis


def _diagnostics(islands, assignments, canonical, composition, skeleton_solve):
    pinned_by_island = _pinned_vertices_by_island(assignments)
    degenerate = []
    share_rows = {}
    for island in islands:
        island_id = island["id"]
        vertices = pinned_by_island.get(island_id, {})
        degenerate_axes, shares = _degenerate_axes(vertices)
        share_rows[island_id] = shares
        if degenerate_axes:
            degenerate.append(island_id)
    coverage = _axis_coverage_percent(composition)
    return {
        "axis_coord_coverage_percent": coverage,
        "axis_components": {
            "A_component_count": skeleton_solve["component_graphs"]["A"]["component_count"],
            "B_component_count": skeleton_solve["component_graphs"]["B"]["component_count"],
        },
        "degenerate_island_ids": degenerate,
        "coordinate_share_by_island": share_rows,
        "canonical_vertex_count": len(canonical),
        "frontier_updated_assignments": composition["updated_assignments"],
    }


def rejected_stitch_defect_histogram(stitch_decisions):
    buckets = Counter({"lt_1e-3": 0, "1e-3_to_1e-2": 0, "1e-2_to_1e-1": 0, "gt_1e-1": 0})
    for decision in stitch_decisions:
        if decision.get("accepted"):
            continue
        for value in decision.get("vertex_angle_defects", {}).values():
            if value is None:
                continue
            magnitude = abs(float(value))
            if magnitude < 1.0e-3:
                buckets["lt_1e-3"] += 1
            elif magnitude < 1.0e-2:
                buckets["1e-3_to_1e-2"] += 1
            elif magnitude < 1.0e-1:
                buckets["1e-2_to_1e-1"] += 1
            else:
                buckets["gt_1e-1"] += 1
    return dict(buckets)


def _pinned_vertices_by_island(assignments):
    rows = defaultdict(dict)
    for vertex_id, values in assignments.items():
        for value in values:
            if value.get("pinned"):
                rows[value["island_id"]][vertex_id] = tuple(value["uv"])
    return rows


def _degenerate_axes(vertices):
    if not vertices:
        return [], {"A": 0.0, "B": 0.0}
    shares = {}
    degenerate = []
    for axis, index in (("A", 0), ("B", 1)):
        counts = Counter(round(float(uv[index]), 6) for uv in vertices.values())
        share = max(counts.values()) / len(vertices)
        shares[axis] = round(share, 6)
        if share > DEGENERATE_COORD_SHARE_LIMIT:
            degenerate.append(axis)
    return degenerate, shares


def _axis_coverage_percent(composition):
    total = composition["both_axis"] + composition["one_axis"] + composition["zero_axis"]
    if total == 0:
        return {"both": 0.0, "one": 0.0, "zero": 0.0}
    return {
        "both": round(100.0 * composition["both_axis"] / total, 2),
        "one": round(100.0 * composition["one_axis"] / total, 2),
        "zero": round(100.0 * composition["zero_axis"] / total, 2),
    }


def _mean(values):
    return sum(values) / len(values) if values else None
