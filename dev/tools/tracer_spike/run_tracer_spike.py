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

from scaffold_core.layer_2_geometry.measures import dot, length, normalize, subtract
from scaffold_core.layer_3_relations.model import ScaffoldJunctionKind
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
from scaffold_core.tests.fixtures.beveled_wall_corner import make_beveled_wall_corner_source
from scaffold_core.tests.fixtures.cylinder_tube import (
    make_cylinder_tube_without_caps_with_two_seams_source,
)
from scaffold_core.tests.fixtures.detached_parallel_walls import make_detached_parallel_walls_source
from scaffold_core.tests.fixtures.l_corridor_tunnel import make_l_corridor_tunnel_seamed_folds_source
from scaffold_core.tests.fixtures.tube_with_cap import make_tube_with_cap_source


ANGLE_DEFECT_STITCH_LIMIT = 1.0e-3
AXIS_MATCH_DOT = 0.99
REPORTS_DIR = Path(__file__).resolve().parent / "reports"
FIXTURES = {
    "beveled_wall_corner": make_beveled_wall_corner_source,
    "l_corridor_tunnel_seamed_folds": make_l_corridor_tunnel_seamed_folds_source,
    "cylinder_tube_two_seams": make_cylinder_tube_without_caps_with_two_seams_source,
    "tube_with_cap": make_tube_with_cap_source,
    "detached_parallel_walls": make_detached_parallel_walls_source,
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
    topology = context.topology_snapshot
    geometry = context.geometry_facts
    relations = context.relation_snapshot
    evidence_by_id = {evidence.id: evidence for evidence in relations.patch_chain_directional_evidence}
    patch_vertices = _patch_vertices(topology, geometry)
    islands, stitch_decisions, self_seam_chain_ids = _build_islands(
        topology,
        geometry,
        relations,
        evidence_by_id,
    )
    rail_rows, improvisations = _build_rails(islands, relations, evidence_by_id)
    assignments: dict[str, list[dict[str, object]]] = defaultdict(list)
    rail_records = []
    ambiguities: list[str] = []
    for island in islands:
        island_rails = [rail for rail in rail_rows if rail["island_id"] == island["id"]]
        for row_index, rail in enumerate(island_rails):
            member_order = _ordered_member_ids(rail, relations)
            cursor = 0.0
            rail_assignments = []
            for member_id in member_order:
                evidence = evidence_by_id[member_id]
                start_ids = _topology_vertex_ids_for_source(topology, evidence.start_source_vertex_id)
                end_ids = _topology_vertex_ids_for_source(topology, evidence.end_source_vertex_id)
                u0 = cursor
                u1 = cursor + evidence.length
                cursor = u1
                for vertex_id in start_ids:
                    if vertex_id in patch_vertices[evidence.patch_id]:
                        _assign(assignments, vertex_id, island["id"], (u0, float(row_index)), True, rail["id"])
                        rail_assignments.append(str(vertex_id))
                for vertex_id in end_ids:
                    if vertex_id in patch_vertices[evidence.patch_id]:
                        _assign(assignments, vertex_id, island["id"], (u1, float(row_index)), True, rail["id"])
                        rail_assignments.append(str(vertex_id))
            rail_records.append({
                "id": rail["id"],
                "island_id": island["id"],
                "source": rail["source"],
                "member_directional_evidence_ids": list(member_order),
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
    }
    return {
        "fixture": fixture_name,
        "angle_defect_stitch_limit": ANGLE_DEFECT_STITCH_LIMIT,
        "vertices": vertices,
        "islands": islands,
        "rails": rail_records,
        "stitch_decisions": stitch_decisions,
        "self_seam_chain_ids": sorted(self_seam_chain_ids),
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


def _build_rails(islands, relations, evidence_by_id):
    island_by_patch_id = {
        patch_id: island["id"]
        for island in islands
        for patch_id in island["patch_ids"]
    }
    rails = []
    covered_member_ids: set[str] = set()
    improvisations = []
    for family in sorted(relations.connected_direction_families, key=lambda item: item.id):
        members_by_island: dict[str, list[str]] = defaultdict(list)
        for member_id in family.member_directional_evidence_ids:
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
                "member_directional_evidence_ids": tuple(sorted(member_ids)),
            })

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
        })
        improvisations.append(
            f"{island_id} {patch_id} {role}: PatchAxes grouped {len(member_ids)} singleton/ungrouped rail runs"
        )
    return rails, improvisations


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
    graph = defaultdict(set)
    member_set = set(member_ids)
    for record in family.crossing_records:
        first = record.get("first_directional_evidence_id")
        second = record.get("second_directional_evidence_id")
        if first in member_set and second in member_set:
            graph[first].add(second)
            graph[second].add(first)
    if not graph:
        return member_ids
    leaves = sorted(member_id for member_id in member_ids if len(graph[member_id]) <= 1)
    start = leaves[0] if leaves else sorted(member_ids)[0]
    visited = set()
    ordered = []
    stack = [start]
    while stack:
        member_id = stack.pop()
        if member_id in visited:
            continue
        visited.add(member_id)
        ordered.append(member_id)
        stack.extend(sorted(graph[member_id] - visited, reverse=True))
    ordered.extend(member_id for member_id in member_ids if member_id not in visited)
    return tuple(ordered)


def _patch_vertices(topology, geometry):
    source_to_topology_ids = _source_to_topology_vertex_ids(topology)
    patch_vertices = defaultdict(set)
    for patch in topology.patches.values():
        for loop_id in patch.loop_ids:
            loop = topology.loops[loop_id]
            for patch_chain_id in loop.patch_chain_ids:
                patch_chain = topology.patch_chains[patch_chain_id]
                if patch_chain.start_vertex_id is not None:
                    patch_vertices[patch.id].add(patch_chain.start_vertex_id)
                if patch_chain.end_vertex_id is not None:
                    patch_vertices[patch.id].add(patch_chain.end_vertex_id)
                chain_facts = geometry.chain_facts.get(patch_chain.chain_id)
                if chain_facts is None:
                    continue
                for source_vertex_id in chain_facts.source_vertex_run:
                    patch_vertices[patch.id].update(source_to_topology_ids.get(source_vertex_id, ()))
    return patch_vertices


def _source_to_topology_vertex_ids(topology):
    result = defaultdict(list)
    for vertex in topology.vertices.values():
        for source_vertex_id in vertex.source_vertex_ids:
            result[source_vertex_id].append(vertex.id)
    return result


def _topology_vertex_ids_for_source(topology, source_vertex_id):
    return tuple(_source_to_topology_vertex_ids(topology).get(source_vertex_id, ()))


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
        "improvisations={improvisation_count}, ambiguities={ambiguity_count}".format(**summary)
        for summary in fixture_summaries
    )
    never_read_lines = "\n".join(f"- `{field}`" for field in RELATION_FIELDS_NEVER_READ)
    return f"""# Tracer Spike v0 Consumption Report

Generated by `dev/tools/tracer_spike/run_tracer_spike.py`.

## Fixture Outputs

{fixture_lines}

JSON layout dumps live next to this report:

- `beveled_wall_corner.json`
- `l_corridor_tunnel_seamed_folds.json`
- `cylinder_tube_two_seams.json`
- `tube_with_cap.json`
- `detached_parallel_walls.json`

## RelationSnapshot Fields Read Per Decision

- Island seed: `connected_direction_families`, `patch_chain_directional_evidence`.
- Patch stitch gate: `patch_adjacencies`, `scaffold_junctions`; paired with `GeometryFactSnapshot.vertex_facts.angle_defect` and `SurfaceModel.chains`.
- Rail extraction: `connected_direction_families`, `patch_chain_directional_evidence`.
- In-patch singleton pairing fallback: `patch_axes`.
- Vertex/arc-length layout support: `patch_chain_directional_evidence`; paired with `GeometryFactSnapshot.chain_facts`, `GeometryFactSnapshot.vertex_facts`, `SurfaceModel.patch_chains`, `SurfaceModel.loops`, and `SurfaceModel.vertices`.

## RelationSnapshot Fields Never Read

{never_read_lines}

## Missing Information Improvised

- No direct rail-order/orientation record exists for a `ConnectedDirectionFamily`; the spike ordered members by the crossing-record graph and then by id when necessary.
- No explicit family-to-ScaffoldEdge segment map exists; the spike mapped directional evidence back through source vertices and patch membership.
- No approved in-patch opposite-rail grouping exists for singleton families; the spike used `PatchAxes` to group singleton or ungrouped runs inside one patch.
- No UV scale, packing, island origin, or pin policy exists in Layer 3; the spike used raw arc length, row offsets, and pinned all rail endpoints.
- The stitch rule says "vertices that become interior"; the spike approximated that set as the two endpoints of the shared `Chain`.
- Reports need topology vertex ids, but directional evidence stores source vertex ids; the spike mapped source vertices to topology vertices and emitted per-island duplicates if one topology id crossed islands.
- `ConnectedDirectionFamily.crossing_records` are untyped dictionaries; the spike consumed `first_directional_evidence_id` and `second_directional_evidence_id` keys as a shadow API.

## Arbitrary Choices And Ambiguity

- If a family crossing graph had multiple leaves or valence greater than 2, the spike picked the lexicographically first leaf/id as the rail start.
- If multiple rails assigned different UVs to the same vertex inside one island, the spike collapsed them with an arithmetic mean and recorded the ambiguity in the JSON dump.
- If several patches tied for longest family presence, the seed patch was chosen lexicographically.
- When a patch pair had multiple admissible shared seams, the first BFS stitch reached the neighbor and later equivalent seams were not separately used for island membership.
- PatchAxes fallback grouped by primary/secondary axis only; it did not infer top/bottom/left/right semantic rail roles.

## Slice F Inputs

- Promote family crossing records from untyped payloads or provide a typed read API if consumers are expected to order rails.
- Provide an explicit directional-evidence-to-graph-edge/endpoint map if tracer consumers should avoid source-vertex reverse lookup.
- Decide whether singleton in-patch rail pairing belongs in core evidence or remains a consumer fallback via `PatchAxes`.
- Clarify the exact vertex set for the angle-defect stitch gate on multi-segment shared chains.
- Define whether pinned UV skeleton output is future core behavior or remains external spike/tooling.
"""


if __name__ == "__main__":
    main()
