"""
Disposable Skeleton Frontier tracer spike for SCAFFOLD Slice E.

This file is consumer tooling outside scaffold_core. It imports the public
pipeline and fixture constructors, runs Pass 0/Pass 1, emits JSON layout dumps,
and writes the consumption report that Slice F will review.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict, deque
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scaffold_core.ids import SourceEdgeId, SourceFaceId, SourceMeshId, SourceVertexId
from scaffold_core.layer_0_source.snapshot import (
    MeshEdgeRef,
    MeshFaceRef,
    MeshVertexRef,
    SourceMeshSnapshot,
)
from scaffold_core.layer_2_geometry.measures import dot, length, normalize, subtract
from scaffold_core.layer_1_topology.model import BoundaryLoopKind
from scaffold_core.layer_3_relations.model import ScaffoldJunctionKind
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
from scaffold_core.tests.fixtures.beveled_wall_corner import make_beveled_wall_corner_source
from scaffold_core.tests.fixtures.cylinder_tube import (
    make_cylinder_tube_without_caps_with_two_seams_source,
)
from scaffold_core.tests.fixtures.detached_parallel_walls import make_detached_parallel_walls_source
from scaffold_core.tests.fixtures.l_corridor_tunnel import make_l_corridor_tunnel_seamed_folds_source
from scaffold_core.tests.fixtures.tube_with_cap import make_tube_with_cap_source


def make_wall_with_window_spike_source() -> SourceMeshSnapshot:
    """Return a spike-local planar wall patch with one rectangular window hole."""

    o0 = SourceVertexId("o0")
    o1 = SourceVertexId("o1")
    o2 = SourceVertexId("o2")
    o3 = SourceVertexId("o3")
    w0 = SourceVertexId("w0")
    w1 = SourceVertexId("w1")
    w2 = SourceVertexId("w2")
    w3 = SourceVertexId("w3")

    e_outer_bottom = SourceEdgeId("a_outer_bottom")
    e_outer_right = SourceEdgeId("a_outer_right")
    e_outer_top = SourceEdgeId("a_outer_top")
    e_outer_left = SourceEdgeId("a_outer_left")
    e_window_bottom = SourceEdgeId("z_window_bottom")
    e_window_right = SourceEdgeId("z_window_right")
    e_window_top = SourceEdgeId("z_window_top")
    e_window_left = SourceEdgeId("z_window_left")
    e_lower_right = SourceEdgeId("m_lower_right")
    e_upper_right = SourceEdgeId("m_upper_right")
    e_upper_left = SourceEdgeId("m_upper_left")
    e_lower_left = SourceEdgeId("m_lower_left")

    f_bottom = SourceFaceId("f_bottom")
    f_right = SourceFaceId("f_right")
    f_top = SourceFaceId("f_top")
    f_left = SourceFaceId("f_left")

    return SourceMeshSnapshot(
        id=SourceMeshId("wall_with_window_spike"),
        vertices={
            o0: MeshVertexRef(o0, (0.0, 0.0, 0.0)),
            o1: MeshVertexRef(o1, (4.0, 0.0, 0.0)),
            o2: MeshVertexRef(o2, (4.0, 3.0, 0.0)),
            o3: MeshVertexRef(o3, (0.0, 3.0, 0.0)),
            w0: MeshVertexRef(w0, (1.0, 1.0, 0.0)),
            w1: MeshVertexRef(w1, (3.0, 1.0, 0.0)),
            w2: MeshVertexRef(w2, (3.0, 2.0, 0.0)),
            w3: MeshVertexRef(w3, (1.0, 2.0, 0.0)),
        },
        edges={
            e_outer_bottom: MeshEdgeRef(e_outer_bottom, (o0, o1)),
            e_outer_right: MeshEdgeRef(e_outer_right, (o1, o2)),
            e_outer_top: MeshEdgeRef(e_outer_top, (o2, o3)),
            e_outer_left: MeshEdgeRef(e_outer_left, (o3, o0)),
            e_window_bottom: MeshEdgeRef(e_window_bottom, (w0, w1)),
            e_window_right: MeshEdgeRef(e_window_right, (w1, w2)),
            e_window_top: MeshEdgeRef(e_window_top, (w2, w3)),
            e_window_left: MeshEdgeRef(e_window_left, (w3, w0)),
            e_lower_right: MeshEdgeRef(e_lower_right, (o1, w1)),
            e_upper_right: MeshEdgeRef(e_upper_right, (o2, w2)),
            e_upper_left: MeshEdgeRef(e_upper_left, (o3, w3)),
            e_lower_left: MeshEdgeRef(e_lower_left, (o0, w0)),
        },
        faces={
            f_bottom: MeshFaceRef(
                f_bottom,
                (o0, o1, w1, w0),
                (e_outer_bottom, e_lower_right, e_window_bottom, e_lower_left),
            ),
            f_right: MeshFaceRef(
                f_right,
                (o1, o2, w2, w1),
                (e_outer_right, e_upper_right, e_window_right, e_lower_right),
            ),
            f_top: MeshFaceRef(
                f_top,
                (o2, o3, w3, w2),
                (e_outer_top, e_upper_left, e_window_top, e_upper_right),
            ),
            f_left: MeshFaceRef(
                f_left,
                (o3, o0, w0, w3),
                (e_outer_left, e_lower_left, e_window_left, e_upper_left),
            ),
        },
        selected_face_ids=(f_bottom, f_right, f_top, f_left),
    )


ANGLE_DEFECT_STITCH_LIMIT = 1.0e-3
AXIS_MATCH_DOT = 0.99
AXIS_ROLE_MIN_DOT = 0.85
AXIS_ROLE_TIE_EPSILON = 1.0e-6
REPORTS_DIR = Path(__file__).resolve().parent / "reports"
FIXTURES = {
    "beveled_wall_corner": make_beveled_wall_corner_source,
    "l_corridor_tunnel_seamed_folds": make_l_corridor_tunnel_seamed_folds_source,
    "cylinder_tube_two_seams": make_cylinder_tube_without_caps_with_two_seams_source,
    "tube_with_cap": make_tube_with_cap_source,
    "detached_parallel_walls": make_detached_parallel_walls_source,
    "wall_with_window_spike": make_wall_with_window_spike_source,
}
RELATION_FIELDS_READ = {
    "patch_adjacencies",
    "patch_chain_directional_evidence",
    "scaffold_junctions",
    "connected_direction_families",
    "patch_axes",
}
RELATION_FIELDS_NEVER_READ = (
    "chain_continuations",
    "chain_directional_runs",
    "loop_corners",
    "patch_chain_endpoint_samples",
    "patch_chain_endpoint_relations",
    "scaffold_nodes",
    "scaffold_edges",
    "scaffold_graph",
    "side_surface_continuity_evidence",
    "surface_flow_compatibility_evidence",
    "scaffold_node_incident_edge_relations",
    "shared_chain_patch_chain_relations",
    "scaffold_continuity_components",
    "alignment_classes",
    "diagnostics",
)


def main() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    fixture_summaries = []
    for fixture_name, factory in FIXTURES.items():
        context = run_pass_1_relations(run_pass_0(factory()))
        layout = build_layout_dump(fixture_name, context)
        fixture_summaries.append(layout["summary"])
        output_path = REPORTS_DIR / f"{fixture_name}.json"
        output_path.write_text(json.dumps(layout, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = build_consumption_report(fixture_summaries)
    (REPORTS_DIR / "consumption_report.md").write_text(report, encoding="utf-8")


def build_layout_dump(fixture_name: str, context) -> dict[str, object]:
    source = context.source_snapshot
    topology = context.topology_snapshot
    geometry = context.geometry_facts
    relations = context.relation_snapshot
    evidence_by_id = {evidence.id: evidence for evidence in relations.patch_chain_directional_evidence}
    patch_vertices = _patch_vertices(topology, source)
    member_info_by_id = _member_info_by_id(topology, relations, evidence_by_id)
    islands, stitch_decisions, self_seam_chain_ids = _build_islands(
        topology,
        geometry,
        relations,
        evidence_by_id,
    )
    axis_roles_by_island, family_axis_roles, axis_ambiguities = _build_island_axis_roles(
        islands,
        relations,
        evidence_by_id,
    )
    inner_loop_index = _build_inner_loop_index(topology, source, islands, patch_vertices)
    rail_rows, improvisations, inner_loop_placement = _build_rails(
        islands,
        topology,
        relations,
        evidence_by_id,
        axis_roles_by_island,
        family_axis_roles,
        inner_loop_index,
    )
    assignments: dict[str, list[dict[str, object]]] = defaultdict(list)
    rail_records = []
    ambiguities: list[str] = list(axis_ambiguities)
    for island in islands:
        island_rails = [rail for rail in rail_rows if rail["island_id"] == island["id"]]
        for row_index, rail in enumerate(island_rails):
            member_order = _ordered_member_ids(rail, relations)
            cursor = 0.0
            rail_assignments = []
            for member_id in member_order:
                evidence = evidence_by_id[member_id]
                member_info = member_info_by_id[member_id]
                for vertex_id, station in _member_assignment_points(
                    member_info,
                    evidence,
                    rail,
                    topology,
                    source,
                    patch_vertices,
                ):
                    if vertex_id in patch_vertices[evidence.patch_id]:
                        _assign(
                            assignments,
                            vertex_id,
                            island["id"],
                            (cursor + station, float(row_index)),
                            True,
                            rail["id"],
                        )
                        rail_assignments.append(str(vertex_id))
                cursor += evidence.length
            rail_records.append({
                "id": rail["id"],
                "island_id": island["id"],
                "source": rail["source"],
                "axis_role": rail.get("axis_role"),
                "loop_kind": rail.get("loop_kind"),
                "patch_chain_id": rail.get("patch_chain_id"),
                "member_directional_evidence_ids": list(member_order),
                "branch_records": dict(rail.get("branch_records", {})),
                "assigned_vertex_ids": sorted(set(rail_assignments)),
            })
        _assign_missing_island_vertices(
            assignments,
            island,
            patch_vertices,
            topology,
            geometry,
            relations,
            len(island_rails),
        )
    vertices, assignment_ambiguities = _final_vertex_dump(assignments)
    ambiguities.extend(assignment_ambiguities)
    inner_loop_placement = _finalize_inner_loop_placement(
        inner_loop_placement,
        inner_loop_index,
        vertices,
    )
    for island in islands:
        island["vertex_ids"] = sorted(
            str(vertex_id)
            for patch_id in island["patch_ids"]
            for vertex_id in patch_vertices[patch_id]
        )
    summary = {
        "fixture": fixture_name,
        "island_count": len(islands),
        "rail_count": len(rail_records),
        "stitched_patch_pairs": sum(1 for decision in stitch_decisions if decision["accepted"]),
        "blocked_patch_pairs": sum(1 for decision in stitch_decisions if not decision["accepted"]),
        "self_seam_chain_count": len(self_seam_chain_ids),
        "improvisation_count": len(improvisations),
        "ambiguity_count": len(ambiguities),
        "axis_role_family_count": sum(
            len(island_axis_roles["families"])
            for island_axis_roles in axis_roles_by_island.values()
        ),
        "axis_role_ambiguity_count": len(axis_ambiguities),
        "inner_loop_chain_count": sum(
            stats["inner_patch_chain_count"]
            for stats in inner_loop_placement.values()
        ),
        "inner_loop_chains_placed": sum(
            stats["inner_patch_chains_placed"]
            for stats in inner_loop_placement.values()
        ),
        "inner_loop_fallback_vertex_count": sum(
            stats["fallback_vertex_count"]
            for stats in inner_loop_placement.values()
        ),
    }
    return {
        "fixture": fixture_name,
        "angle_defect_stitch_limit": ANGLE_DEFECT_STITCH_LIMIT,
        "axis_role_min_dot": AXIS_ROLE_MIN_DOT,
        "vertices": vertices,
        "islands": islands,
        "island_axis_roles": axis_roles_by_island,
        "rails": rail_records,
        "stitch_decisions": stitch_decisions,
        "self_seam_chain_ids": sorted(self_seam_chain_ids),
        "inner_loop_placement": inner_loop_placement,
        "improvisations": improvisations,
        "ambiguities": ambiguities,
        "consumed_relation_fields": sorted(RELATION_FIELDS_READ),
        "summary": summary,
    }


def _build_islands(topology, geometry, relations, evidence_by_id):
    patch_scores = {
        patch_id: _patch_family_presence_score(patch_id, relations, evidence_by_id)
        for patch_id in topology.patches
    }
    adjacencies_by_patch = defaultdict(list)
    for adjacency in relations.patch_adjacencies.values():
        adjacencies_by_patch[adjacency.first_patch_id].append(adjacency)
        adjacencies_by_patch[adjacency.second_patch_id].append(adjacency)
    self_seam_chain_ids = {
        str(junction.matched_chain_id)
        for junction in relations.scaffold_junctions
        if junction.kind is ScaffoldJunctionKind.SELF_SEAM and junction.matched_chain_id is not None
    }
    unvisited = set(topology.patches)
    islands = []
    stitch_decisions = []
    island_index = 0
    while unvisited:
        seed = sorted(unvisited, key=lambda patch_id: (-patch_scores[patch_id], str(patch_id)))[0]
        queue = deque([seed])
        unvisited.remove(seed)
        patch_ids = {seed}
        seed_score = patch_scores[seed]
        while queue:
            patch_id = queue.popleft()
            for adjacency in sorted(adjacencies_by_patch[patch_id], key=lambda item: item.id):
                neighbor = (
                    adjacency.second_patch_id
                    if adjacency.first_patch_id == patch_id
                    else adjacency.first_patch_id
                )
                if neighbor not in unvisited:
                    continue
                accepted, reason, vertex_defects = _stitch_decision(
                    topology,
                    geometry,
                    adjacency,
                    self_seam_chain_ids,
                )
                stitch_decisions.append({
                    "from_patch_id": str(patch_id),
                    "to_patch_id": str(neighbor),
                    "patch_adjacency_id": adjacency.id,
                    "chain_id": str(adjacency.chain_id),
                    "accepted": accepted,
                    "reason": reason,
                    "vertex_angle_defects": vertex_defects,
                })
                if not accepted:
                    continue
                unvisited.remove(neighbor)
                patch_ids.add(neighbor)
                queue.append(neighbor)
        islands.append({
            "id": f"island:{island_index}",
            "seed_patch_id": str(seed),
            "seed_connected_family_presence": seed_score,
            "patch_ids": sorted((str(patch_id) for patch_id in patch_ids)),
        })
        island_index += 1
    return islands, stitch_decisions, self_seam_chain_ids


def _patch_family_presence_score(patch_id, relations, evidence_by_id) -> float:
    score = 0.0
    for family in relations.connected_direction_families:
        family_patch_length = sum(
            evidence_by_id[member_id].length
            for member_id in family.member_directional_evidence_ids
            if evidence_by_id[member_id].patch_id == patch_id
        )
        score = max(score, family_patch_length)
    return score


def _stitch_decision(topology, geometry, adjacency, self_seam_chain_ids):
    if str(adjacency.chain_id) in self_seam_chain_ids:
        return False, "SEAM_SELF chains always remain island boundaries", {}
    chain = topology.chains[adjacency.chain_id]
    vertex_ids = tuple(dict.fromkeys((chain.start_vertex_id, chain.end_vertex_id)))
    vertex_defects = {}
    for vertex_id in vertex_ids:
        facts = geometry.vertex_facts.get(vertex_id)
        if facts is None:
            vertex_defects[str(vertex_id)] = None
            return False, "missing VertexGeometryFacts.angle_defect", vertex_defects
        vertex_defects[str(vertex_id)] = facts.angle_defect
    if all(abs(value) < ANGLE_DEFECT_STITCH_LIMIT for value in vertex_defects.values()):
        return True, "all would-be interior vertices have near-zero angle defect", vertex_defects
    return False, "angle defect exceeds stitch limit", vertex_defects


def _build_island_axis_roles(islands, relations, evidence_by_id):
    axis_roles_by_island = {}
    family_axis_roles = {}
    ambiguities = []
    for island in islands:
        island_id = island["id"]
        patch_ids = set(island["patch_ids"])
        family_rows = []
        for family in sorted(relations.connected_direction_families, key=lambda item: item.id):
            members = [
                evidence_by_id[member_id]
                for member_id in family.member_directional_evidence_ids
                if str(evidence_by_id[member_id].patch_id) in patch_ids
            ]
            if not members:
                continue
            family_rows.append({
                "family_id": family.id,
                "length": sum(member.length for member in members),
                "direction": _weighted_direction(members),
                "member_count": len(members),
                "patch_ids": sorted({str(member.patch_id) for member in members}),
            })

        axis_a = _select_axis_a(island_id, family_rows, ambiguities)
        axis_b = _select_axis_b(island_id, family_rows, axis_a, ambiguities)
        axis_context = {"axis_a": axis_a, "axis_b": axis_b}
        classified_rows = []
        for row in family_rows:
            role = _axis_role_for_direction(row["direction"], axis_context)
            family_axis_roles[(island_id, row["family_id"])] = role
            dot_a = _axis_dot(row["direction"], axis_a)
            dot_b = _axis_dot(row["direction"], axis_b)
            if (
                axis_a is not None
                and axis_b is not None
                and max(dot_a, dot_b) >= AXIS_ROLE_MIN_DOT
                and abs(dot_a - dot_b) <= AXIS_ROLE_TIE_EPSILON
            ):
                ambiguities.append(
                    f"{island_id} {row['family_id']}: tied AXIS_A/AXIS_B projection; picked {role}"
                )
            classified_rows.append({
                "family_id": row["family_id"],
                "role": role,
                "length": round(row["length"], 6),
                "direction": _round_vector(row["direction"]),
                "dot_axis_a": round(dot_a, 6) if axis_a is not None else None,
                "dot_axis_b": round(dot_b, 6) if axis_b is not None else None,
                "member_count": row["member_count"],
                "patch_ids": row["patch_ids"],
            })

        axis_roles_by_island[island_id] = {
            "axis_a": _axis_record(axis_a),
            "axis_b": _axis_record(axis_b),
            "families": classified_rows,
            "ambiguities": [
                ambiguity
                for ambiguity in ambiguities
                if ambiguity.startswith(f"{island_id} ")
            ],
        }
    return axis_roles_by_island, family_axis_roles, ambiguities


def _select_axis_a(island_id, family_rows, ambiguities):
    if not family_rows:
        return None
    rows = sorted(family_rows, key=lambda row: (-row["length"], row["family_id"]))
    top = rows[0]
    tied = [
        row["family_id"]
        for row in rows
        if abs(row["length"] - top["length"]) <= AXIS_ROLE_TIE_EPSILON
    ]
    if len(tied) > 1:
        ambiguities.append(
            f"{island_id}: AXIS_A family length tie {tied}; picked {top['family_id']}"
        )
    return {
        "family_id": top["family_id"],
        "direction": top["direction"],
        "length": top["length"],
    }


def _select_axis_b(island_id, family_rows, axis_a, ambiguities):
    if axis_a is None:
        return None
    candidates = [
        row for row in family_rows
        if row["family_id"] != axis_a["family_id"]
    ]
    if not candidates:
        return None
    scored = []
    for row in candidates:
        orthogonality = 1.0 - abs(dot(row["direction"], axis_a["direction"]))
        scored.append((orthogonality, row["length"], row))
    scored.sort(key=lambda item: (-item[0], -item[1], item[2]["family_id"]))
    top_orthogonality, top_length, top = scored[0]
    tied = [
        row["family_id"]
        for orthogonality, row_length, row in scored
        if (
            abs(orthogonality - top_orthogonality) <= AXIS_ROLE_TIE_EPSILON
            and abs(row_length - top_length) <= AXIS_ROLE_TIE_EPSILON
        )
    ]
    if len(tied) > 1:
        ambiguities.append(
            f"{island_id}: AXIS_B orthogonality/length tie {tied}; picked {top['family_id']}"
        )
    return {
        "family_id": top["family_id"],
        "direction": top["direction"],
        "length": top["length"],
        "orthogonality_score": top_orthogonality,
    }


def _axis_role_for_direction(direction, axis_context):
    axis_a = axis_context.get("axis_a")
    axis_b = axis_context.get("axis_b")
    dot_a = _axis_dot(direction, axis_a)
    dot_b = _axis_dot(direction, axis_b)
    if dot_a < AXIS_ROLE_MIN_DOT and dot_b < AXIS_ROLE_MIN_DOT:
        return "OBLIQUE"
    if dot_a >= dot_b:
        return "AXIS_A"
    return "AXIS_B"


def _axis_dot(direction, axis):
    if axis is None:
        return 0.0
    if length(direction) == 0.0 or length(axis["direction"]) == 0.0:
        return 0.0
    return abs(dot(normalize(direction), normalize(axis["direction"])))


def _axis_record(axis):
    if axis is None:
        return None
    record = {
        "seed_family_id": axis["family_id"],
        "direction": _round_vector(axis["direction"]),
        "length": round(axis["length"], 6),
    }
    if "orthogonality_score" in axis:
        record["orthogonality_score"] = round(axis["orthogonality_score"], 6)
    return record


def _weighted_direction(evidence_items):
    if not evidence_items:
        return (0.0, 0.0, 0.0)
    seed = max(evidence_items, key=lambda item: (item.length, item.id)).direction
    if length(seed) == 0.0:
        return (0.0, 0.0, 0.0)
    seed = normalize(seed)
    total = [0.0, 0.0, 0.0]
    for evidence in evidence_items:
        direction = evidence.direction
        if length(direction) == 0.0:
            continue
        direction = normalize(direction)
        if dot(direction, seed) < 0.0:
            direction = tuple(-value for value in direction)
        for index in range(3):
            total[index] += direction[index] * evidence.length
    vector = tuple(total)
    if length(vector) == 0.0:
        return seed
    return normalize(vector)


def _round_vector(vector):
    return [round(float(value), 6) for value in vector]


def _build_inner_loop_index(topology, source, islands, patch_vertices):
    island_by_patch_id = {
        patch_id: island["id"]
        for island in islands
        for patch_id in island["patch_ids"]
    }
    patch_chain_ids_by_island = defaultdict(list)
    vertex_ids_by_island = defaultdict(set)
    for loop in sorted(topology.loops.values(), key=lambda item: item.id):
        if loop.kind is not BoundaryLoopKind.INNER and loop.loop_index < 1:
            continue
        island_id = island_by_patch_id.get(str(loop.patch_id))
        if island_id is None:
            continue
        for patch_chain_id in loop.patch_chain_ids:
            patch_chain_ids_by_island[island_id].append(patch_chain_id)
            patch_chain = topology.patch_chains[patch_chain_id]
            path_points = _patch_chain_path_points(patch_chain_id, topology, source, patch_vertices)
            if path_points:
                for vertex_id, _station in path_points:
                    vertex_ids_by_island[island_id].add(vertex_id)
                continue
            if patch_chain.start_vertex_id is not None:
                vertex_ids_by_island[island_id].add(patch_chain.start_vertex_id)
            if patch_chain.end_vertex_id is not None:
                vertex_ids_by_island[island_id].add(patch_chain.end_vertex_id)
    return {
        "patch_chain_ids_by_island": {
            island_id: tuple(sorted(patch_chain_ids, key=str))
            for island_id, patch_chain_ids in patch_chain_ids_by_island.items()
        },
        "vertex_ids_by_island": {
            island_id: set(vertex_ids)
            for island_id, vertex_ids in vertex_ids_by_island.items()
        },
    }


def _initial_inner_loop_placement(inner_loop_index):
    placement = {}
    for island_id, patch_chain_ids in inner_loop_index["patch_chain_ids_by_island"].items():
        placement[island_id] = {
            "inner_patch_chain_count": len(patch_chain_ids),
            "inner_patch_chains_placed": 0,
            "inner_patch_chains_fallback": 0,
            "inner_loop_rail_count": 0,
            "inner_member_count": 0,
            "inner_vertex_count": len(inner_loop_index["vertex_ids_by_island"].get(island_id, ())),
            "fallback_vertex_count": 0,
            "placed_vertex_count": 0,
        }
    return placement


def _evidence_ids_for_patch_chain(evidence_by_id, patch_chain_id):
    return tuple(
        evidence.id
        for evidence in sorted(evidence_by_id.values(), key=lambda item: item.id)
        if evidence.patch_chain_id == patch_chain_id
    )


def _build_rails(islands, topology, relations, evidence_by_id, axis_roles_by_island, family_axis_roles, inner_loop_index):
    island_by_patch_id = {
        patch_id: island["id"]
        for island in islands
        for patch_id in island["patch_ids"]
    }
    inner_member_ids = {
        evidence_id
        for patch_chain_ids in inner_loop_index["patch_chain_ids_by_island"].values()
        for patch_chain_id in patch_chain_ids
        for evidence_id in _evidence_ids_for_patch_chain(evidence_by_id, patch_chain_id)
    }
    rails = []
    covered_member_ids: set[str] = set()
    improvisations = []
    for family in sorted(relations.connected_direction_families, key=lambda item: item.id):
        members_by_island: dict[str, list[str]] = defaultdict(list)
        for member_id in family.member_directional_evidence_ids:
            if member_id in inner_member_ids:
                continue
            evidence = evidence_by_id[member_id]
            island_id = island_by_patch_id.get(str(evidence.patch_id))
            if island_id is not None:
                members_by_island[island_id].append(member_id)
        for island_id, member_ids in sorted(members_by_island.items()):
            if len(member_ids) < 2:
                continue
            covered_member_ids.update(member_ids)
            rails.append({
                "id": f"{family.id}:{island_id}",
                "source": "ConnectedDirectionFamily",
                "family_id": family.id,
                "island_id": island_id,
                "axis_role": family_axis_roles.get((island_id, family.id), "OBLIQUE"),
                "loop_kind": "OUTER_OR_SHARED",
                "member_directional_evidence_ids": tuple(sorted(member_ids)),
                "branch_records": {
                    member_id: tuple(neighbor_ids)
                    for member_id, neighbor_ids in family.branch_records.items()
                    if member_id in member_ids
                },
            })

    inner_loop_placement = _initial_inner_loop_placement(inner_loop_index)
    for island_id, patch_chain_ids in sorted(inner_loop_index["patch_chain_ids_by_island"].items()):
        for patch_chain_id in patch_chain_ids:
            member_ids = _evidence_ids_for_patch_chain(evidence_by_id, patch_chain_id)
            if not member_ids:
                inner_loop_placement[island_id]["inner_patch_chains_fallback"] += 1
                continue
            covered_member_ids.update(member_ids)
            role = _axis_role_for_direction(
                _weighted_direction([evidence_by_id[member_id] for member_id in member_ids]),
                axis_roles_by_island.get(island_id, {}),
            )
            rails.append({
                "id": f"inner_loop:{island_id}:{patch_chain_id}",
                "source": "Inner loop chain rail",
                "family_id": None,
                "island_id": island_id,
                "axis_role": role,
                "loop_kind": "INNER",
                "patch_chain_id": str(patch_chain_id),
                "member_directional_evidence_ids": tuple(member_ids),
                "branch_records": {},
            })
            inner_loop_placement[island_id]["inner_patch_chains_placed"] += 1
            inner_loop_placement[island_id]["inner_loop_rail_count"] += 1
            inner_loop_placement[island_id]["inner_member_count"] += len(member_ids)

    fallback_groups: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for evidence in sorted(evidence_by_id.values(), key=lambda item: item.id):
        if evidence.id in covered_member_ids:
            continue
        island_id = island_by_patch_id.get(str(evidence.patch_id))
        if island_id is None:
            continue
        role = _patch_axes_role(evidence, relations.patch_axes.get(evidence.patch_id))
        fallback_groups[(island_id, str(evidence.patch_id), role)].append(evidence.id)
    for (island_id, patch_id, role), member_ids in sorted(fallback_groups.items()):
        rails.append({
            "id": f"patch_axes:{island_id}:{patch_id}:{role}",
            "source": "PatchAxes fallback for singleton or ungrouped in-patch rail",
            "family_id": None,
            "island_id": island_id,
            "member_directional_evidence_ids": tuple(sorted(member_ids)),
            "branch_records": {},
        })
        improvisations.append(
            f"{island_id} {patch_id} {role}: PatchAxes grouped {len(member_ids)} singleton/ungrouped rail runs"
        )
    return rails, improvisations, inner_loop_placement


def _patch_axes_role(evidence, axes) -> str:
    if axes is None:
        return "NO_PATCH_AXES"
    direction = normalize(evidence.direction)
    if length(axes.primary_direction) > 0.0:
        if abs(dot(direction, normalize(axes.primary_direction))) > AXIS_MATCH_DOT:
            return "PRIMARY"
    if length(axes.secondary_direction) > 0.0:
        if abs(dot(direction, normalize(axes.secondary_direction))) > AXIS_MATCH_DOT:
            return "SECONDARY"
    return "UNMATCHED_PATCH_AXES"


def _ordered_member_ids(rail, relations):
    member_ids = tuple(rail["member_directional_evidence_ids"])
    family_id = rail.get("family_id")
    if family_id is None:
        return member_ids
    family = next(
        family for family in relations.connected_direction_families
        if family.id == family_id
    )
    member_set = set(member_ids)
    ordered = [
        member_id
        for member_id in family.ordered_member_directional_evidence_ids
        if member_id in member_set
    ]
    ordered.extend(member_id for member_id in member_ids if member_id not in ordered)
    return tuple(ordered)


def _patch_vertices(topology, source=None):
    patch_vertices = defaultdict(set)
    topology_vertices_by_source = defaultdict(list)
    for vertex in topology.vertices.values():
        for source_vertex_id in vertex.source_vertex_ids:
            topology_vertices_by_source[source_vertex_id].append(vertex.id)
    for patch in topology.patches.values():
        for loop_id in patch.loop_ids:
            loop = topology.loops[loop_id]
            for patch_chain_id in loop.patch_chain_ids:
                patch_chain = topology.patch_chains[patch_chain_id]
                if patch_chain.start_vertex_id is not None:
                    patch_vertices[patch.id].add(patch_chain.start_vertex_id)
                if patch_chain.end_vertex_id is not None:
                    patch_vertices[patch.id].add(patch_chain.end_vertex_id)
                if source is None:
                    continue
                chain = topology.chains[patch_chain.chain_id]
                for source_edge_id in chain.source_edge_ids:
                    for source_vertex_id in source.edges[source_edge_id].vertex_ids:
                        for vertex_id in topology_vertices_by_source[source_vertex_id]:
                            patch_vertices[patch.id].add(vertex_id)
    return patch_vertices


def _member_info_by_id(topology, relations, evidence_by_id):
    member_info = {}
    for family in relations.connected_direction_families:
        for member_id, member in family.member_map.items():
            member_info[member_id] = {
                "patch_chain_id": member[0],
                "scaffold_edge_id": member[1],
                "start_vertex_id": member[2],
                "end_vertex_id": member[3],
            }
    for evidence in evidence_by_id.values():
        if evidence.id in member_info:
            continue
        patch_chain = topology.patch_chains[evidence.patch_chain_id]
        member_info[evidence.id] = {
            "patch_chain_id": patch_chain.id,
            "scaffold_edge_id": None,
            "start_vertex_id": patch_chain.start_vertex_id,
            "end_vertex_id": patch_chain.end_vertex_id,
        }
    return member_info


def _member_assignment_points(member_info, evidence, rail, topology, source, patch_vertices):
    if rail.get("loop_kind") == "INNER":
        path_points = _patch_chain_path_points(
            member_info["patch_chain_id"],
            topology,
            source,
            patch_vertices,
        )
        if path_points:
            return path_points
    return _member_endpoint_points(member_info, evidence.length)


def _member_endpoint_points(member_info, member_length):
    points = []
    start_vertex_id = member_info["start_vertex_id"]
    end_vertex_id = member_info["end_vertex_id"]
    if start_vertex_id is not None:
        points.append((start_vertex_id, 0.0))
    if end_vertex_id is not None and end_vertex_id != start_vertex_id:
        points.append((end_vertex_id, member_length))
    return tuple(points)


def _patch_chain_path_points(patch_chain_id, topology, source, patch_vertices):
    if source is None:
        return ()
    patch_chain = topology.patch_chains[patch_chain_id]
    chain = topology.chains[patch_chain.chain_id]
    if not chain.source_edge_ids:
        return ()
    source_vertex_ids = _ordered_source_vertex_ids_for_chain(source, chain.source_edge_ids)
    if not source_vertex_ids:
        return ()
    if patch_chain.orientation_sign < 0:
        source_vertex_ids = tuple(reversed(source_vertex_ids))
    if len(source_vertex_ids) > 1 and source_vertex_ids[0] == source_vertex_ids[-1]:
        source_vertex_ids = source_vertex_ids[:-1]

    source_to_vertex_id = _source_vertex_to_patch_vertex_id(
        topology,
        patch_vertices,
        patch_chain.patch_id,
    )
    points = []
    seen_vertices = set()
    station = 0.0
    previous_source_vertex_id = None
    for source_vertex_id in source_vertex_ids:
        if previous_source_vertex_id is not None:
            station += _source_vertex_distance(source, previous_source_vertex_id, source_vertex_id)
        vertex_id = source_to_vertex_id.get(str(source_vertex_id))
        previous_source_vertex_id = source_vertex_id
        if vertex_id is None or vertex_id in seen_vertices:
            continue
        points.append((vertex_id, station))
        seen_vertices.add(vertex_id)
    return tuple(points)


def _ordered_source_vertex_ids_for_chain(source, source_edge_ids):
    if not source_edge_ids:
        return ()
    first_edge = source.edges[source_edge_ids[0]]
    ordered = [first_edge.vertex_ids[0], first_edge.vertex_ids[1]]
    for source_edge_id in source_edge_ids[1:]:
        edge_vertex_ids = source.edges[source_edge_id].vertex_ids
        current = ordered[-1]
        if edge_vertex_ids[0] == current:
            ordered.append(edge_vertex_ids[1])
        elif edge_vertex_ids[1] == current:
            ordered.append(edge_vertex_ids[0])
        elif edge_vertex_ids[0] == ordered[0]:
            ordered.insert(0, edge_vertex_ids[1])
        elif edge_vertex_ids[1] == ordered[0]:
            ordered.insert(0, edge_vertex_ids[0])
        else:
            ordered.extend(edge_vertex_ids)
    return tuple(ordered)


def _source_vertex_to_patch_vertex_id(topology, patch_vertices, patch_id):
    mapping = {}
    patch_vertex_ids = patch_vertices[patch_id]
    for vertex_id in sorted(patch_vertex_ids, key=str):
        vertex = topology.vertices[vertex_id]
        for source_vertex_id in vertex.source_vertex_ids:
            mapping.setdefault(str(source_vertex_id), vertex_id)
    return mapping


def _source_vertex_distance(source, first_source_vertex_id, second_source_vertex_id):
    first_position = source.vertices[first_source_vertex_id].position
    second_position = source.vertices[second_source_vertex_id].position
    return length(subtract(second_position, first_position))


def _assign(assignments, vertex_id, island_id, uv, pinned, source):
    assignments[str(vertex_id)].append({
        "island_id": island_id,
        "uv": [round(float(uv[0]), 6), round(float(uv[1]), 6)],
        "pinned": pinned,
        "source": source,
    })


def _assign_missing_island_vertices(assignments, island, patch_vertices, topology, geometry, relations, row_offset):
    patch_ids = island["patch_ids"]
    origin = _island_origin(patch_ids, patch_vertices, geometry)
    for patch_id_text in patch_ids:
        patch_id = next(patch_id for patch_id in topology.patches if str(patch_id) == patch_id_text)
        axes = relations.patch_axes.get(patch_id)
        primary = _axis_or_default(axes.primary_direction if axes is not None else None, (1.0, 0.0, 0.0))
        secondary = _axis_or_default(axes.secondary_direction if axes is not None else None, (0.0, 1.0, 0.0))
        for vertex_id in patch_vertices[patch_id]:
            if any(value["island_id"] == island["id"] for value in assignments.get(str(vertex_id), ())):
                continue
            facts = geometry.vertex_facts.get(vertex_id)
            if facts is None:
                continue
            relative = subtract(facts.position, origin)
            uv = (dot(relative, primary), float(row_offset) + dot(relative, secondary))
            _assign(assignments, vertex_id, island["id"], uv, False, "fallback patch-axis projection")


def _island_origin(patch_id_texts, patch_vertices, geometry):
    positions = []
    for patch_id_text in patch_id_texts:
        for patch_id, vertex_ids in patch_vertices.items():
            if str(patch_id) != patch_id_text:
                continue
            positions.extend(
                geometry.vertex_facts[vertex_id].position
                for vertex_id in vertex_ids
                if vertex_id in geometry.vertex_facts
            )
    if not positions:
        return (0.0, 0.0, 0.0)
    return tuple(min(position[index] for position in positions) for index in range(3))


def _axis_or_default(axis, default):
    if axis is not None and length(axis) > 0.0:
        return normalize(axis)
    return default


def _finalize_inner_loop_placement(inner_loop_placement, inner_loop_index, vertices):
    finalized = {
        island_id: dict(stats)
        for island_id, stats in inner_loop_placement.items()
    }
    vertex_rows_by_island_and_vertex = defaultdict(list)
    for row in vertices.values():
        vertex_rows_by_island_and_vertex[(row["island_id"], row["vertex_id"])].append(row)
    for island_id, vertex_ids in inner_loop_index["vertex_ids_by_island"].items():
        stats = finalized.setdefault(
            island_id,
            {
                "inner_patch_chain_count": 0,
                "inner_patch_chains_placed": 0,
                "inner_patch_chains_fallback": 0,
                "inner_loop_rail_count": 0,
                "inner_member_count": 0,
                "inner_vertex_count": len(vertex_ids),
                "fallback_vertex_count": 0,
                "placed_vertex_count": 0,
            },
        )
        stats["inner_vertex_count"] = len(vertex_ids)
        fallback_vertex_count = 0
        placed_vertex_count = 0
        for vertex_id in vertex_ids:
            rows = vertex_rows_by_island_and_vertex.get((island_id, str(vertex_id)), ())
            if not rows:
                fallback_vertex_count += 1
                continue
            sources = {
                source
                for row in rows
                for source in row.get("assignment_sources", ())
            }
            if "fallback patch-axis projection" in sources:
                fallback_vertex_count += 1
            else:
                placed_vertex_count += 1
        stats["fallback_vertex_count"] = fallback_vertex_count
        stats["placed_vertex_count"] = placed_vertex_count
    return finalized


def _final_vertex_dump(assignments):
    vertices = {}
    ambiguities = []
    for vertex_id, values in sorted(assignments.items()):
        islands = sorted(set(value["island_id"] for value in values))
        if len(islands) > 1:
            ambiguities.append(
                f"{vertex_id}: assigned to multiple islands {islands}; emitted one entry per island"
            )
            for island_id in islands:
                island_values = [value for value in values if value["island_id"] == island_id]
                vertices[f"{vertex_id}@{island_id}"] = _collapse_vertex_values(vertex_id, island_values)
            continue
        if len({tuple(value["uv"]) for value in values}) > 1:
            ambiguities.append(
                f"{vertex_id}: multiple rail UV assignments collapsed by arithmetic mean"
            )
        vertices[vertex_id] = _collapse_vertex_values(vertex_id, values)
    return vertices, ambiguities


def _collapse_vertex_values(vertex_id, values):
    uv = [
        round(sum(value["uv"][axis] for value in values) / len(values), 6)
        for axis in (0, 1)
    ]
    return {
        "vertex_id": vertex_id,
        "uv": uv,
        "pinned": any(value["pinned"] for value in values),
        "island_id": values[0]["island_id"],
        "assignment_sources": sorted(set(str(value["source"]) for value in values)),
    }


def build_consumption_report(fixture_summaries) -> str:
    fixture_lines = "\n".join(
        "- {fixture}: islands={island_count}, rails={rail_count}, stitched={stitched_patch_pairs}, "
        "blocked={blocked_patch_pairs}, self_seam_chains={self_seam_chain_count}, "
        "axis_families={axis_role_family_count}, inner_chains={inner_loop_chains_placed}/"
        "{inner_loop_chain_count}, inner_fallback_vertices={inner_loop_fallback_vertex_count}, "
        "improvisations={improvisation_count}, ambiguities={ambiguity_count}".format(**summary)
        for summary in fixture_summaries
    )
    output_lines = "\n".join(
        f"- `{summary['fixture']}.json`"
        for summary in fixture_summaries
    )
    never_read_lines = "\n".join(f"- `{field}`" for field in RELATION_FIELDS_NEVER_READ)
    return f"""# Tracer Spike v3 Consumption Report

Generated by `dev/tools/tracer_spike/run_tracer_spike.py`.

## Fixture Outputs

{fixture_lines}

JSON layout dumps live next to this report:

{output_lines}

## RelationSnapshot Fields Read Per Decision

- Island seed: `connected_direction_families`, `patch_chain_directional_evidence`.
- Patch stitch gate: `patch_adjacencies`, `scaffold_junctions`; paired with `GeometryFactSnapshot.vertex_facts.angle_defect` and `SurfaceModel.chains`.
- Rail extraction: `connected_direction_families.member_directional_evidence_ids`, `connected_direction_families.ordered_member_directional_evidence_ids`, `connected_direction_families.branch_records`, `connected_direction_families.member_map`, `patch_chain_directional_evidence`.
- Island-local axis roles: `connected_direction_families`, `patch_chain_directional_evidence`.
- Inner loop placement: Layer 1 `BoundaryLoop.loop_index/kind`, `PatchChain`, `Chain.source_edge_ids`; paired with `SourceMeshSnapshot.edges/vertices`.
- In-patch singleton pairing fallback: `patch_axes`.
- Vertex/arc-length layout support: `connected_direction_families.member_map`, `patch_chain_directional_evidence`; paired with `GeometryFactSnapshot.vertex_facts`, `SurfaceModel.patch_chains`, and `SurfaceModel.loops`.

## RelationSnapshot Fields Never Read

{never_read_lines}

## Missing Information Improvised

- No approved in-patch opposite-rail grouping exists for singleton families; the spike used `PatchAxes` to group singleton or ungrouped runs inside one patch.
- No UV scale, packing, island origin, or pin policy exists in Layer 3; the spike used raw arc length, row offsets, and pinned all rail endpoints.
- The stitch rule says "vertices that become interior"; the spike approximated that set as the two endpoints of the shared `Chain`.
- `ConnectedDirectionFamily.member_map` gives start/end topology vertices only; the spike no longer emits mid-chain vertices unless they are endpoints of a directional member.
- `ConnectedDirectionFamily.branch_records` preserves branch ambiguity but does not define a branch traversal policy for UV rows.
- Axis roles are island-local consumer classifications; the spike used weighted family directions and deterministic tie-breaks, not stored frame-role labels.
- Inner closed chains expose only one topology endpoint in `member_map`; the spike walked `Chain.source_edge_ids` to pin all rim vertices.

## Arbitrary Choices And Ambiguity

- If `ConnectedDirectionFamily.branch_records` is non-empty, the spike records the branch ambiguity and still uses the exported deterministic member order for row placement.
- If multiple rails assigned different UVs to the same vertex inside one island, the spike collapsed them with an arithmetic mean and recorded the ambiguity in the JSON dump.
- If several patches tied for longest family presence, the seed patch was chosen lexicographically.
- If two families tied while selecting AXIS_A or AXIS_B, the spike recorded the tie and picked lexicographically.
- When a patch pair had multiple admissible shared seams, the first BFS stitch reached the neighbor and later equivalent seams were not separately used for island membership.
- PatchAxes fallback grouped by primary/secondary axis only; it did not infer top/bottom/left/right semantic rail roles.

## Slice F Inputs

- Decide whether singleton in-patch rail pairing belongs in core evidence or remains a consumer fallback via `PatchAxes`.
- Clarify the exact vertex set for the angle-defect stitch gate on multi-segment shared chains.
- Define whether pinned UV skeleton output is future core behavior or remains external spike/tooling.
- Decide whether mid-chain skeleton vertices should be exposed in `member_map` or remain outside the typed family API.
"""


if __name__ == "__main__":
    main()
