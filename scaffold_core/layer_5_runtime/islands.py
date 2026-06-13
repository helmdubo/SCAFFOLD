"""
Layer: 5 - Runtime

Rules:
- Island assembly: spanning tree of Level A stitch decisions.
- Would-be-interior vertices use raw Layer 2 angle sums; chain endpoints
  with remaining cut incidence are excluded (T-junction rule, G5a).
- SEAM_SELF never stitches; non-tree seams stay cut.
- Read-only over lower layers; no UV or semantic roles here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import pi
from typing import Any, Mapping

STITCH_DEFECT_TOLERANCE = 1e-3


@dataclass(frozen=True)
class StitchDecision:
    chain_id: str
    first_patch_id: str
    second_patch_id: str
    accepted: bool
    reason: str
    vertex_defects: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class Island:
    id: str
    patch_ids: tuple[str, ...]
    stitched_chain_ids: tuple[str, ...]


@dataclass(frozen=True)
class IslandAssembly:
    islands: tuple[Island, ...]
    decisions: tuple[StitchDecision, ...]
    island_by_patch_id: Mapping[str, str]


def build_islands(context: Any) -> IslandAssembly:
    """Assemble islands via a spanning tree of accepted stitches."""

    topology = context.topology_snapshot
    relations = context.relation_snapshot
    source = context.source_snapshot
    angle_by_source_vertex = _angle_by_source_vertex(context)
    cut_chains_by_vertex = _chain_ids_by_source_vertex(source, topology)
    border_vertices = _border_source_vertices(source)
    self_seam_chain_ids = {
        str(junction.matched_chain_id)
        for junction in relations.scaffold_junctions
        if junction.kind.value == "SELF_SEAM" and junction.matched_chain_id is not None
    }

    parents = {str(patch_id): str(patch_id) for patch_id in topology.patches}

    def find(item: str) -> str:
        while parents[item] != item:
            parents[item] = parents[parents[item]]
            item = parents[item]
        return item

    decisions: list[StitchDecision] = []
    # LEVEL_B_PLACEHOLDER: tree-edge priority is longest-seam-first; the
    # future Layer 4 grammar owns smarter stitch preferences.
    adjacencies = sorted(
        relations.patch_adjacencies.values(),
        key=lambda item: (-_chain_edge_count(topology, item.chain_id), str(item.id)),
    )
    for adjacency in adjacencies:
        chain_id = str(adjacency.chain_id)
        first = str(adjacency.first_patch_id)
        second = str(adjacency.second_patch_id)
        if chain_id in self_seam_chain_ids or first == second:
            decisions.append(StitchDecision(chain_id, first, second, False, "SEAM_SELF always splits"))
            continue
        accepted, reason, defects = _gate(
            source,
            topology,
            chain_id,
            angle_by_source_vertex,
            cut_chains_by_vertex,
            border_vertices,
        )
        if accepted and find(first) != find(second):
            parents[max(find(first), find(second))] = min(find(first), find(second))
            decisions.append(StitchDecision(chain_id, first, second, True, reason, defects))
        elif accepted:
            decisions.append(StitchDecision(chain_id, first, second, False, "non-tree seam stays cut", defects))
        else:
            decisions.append(StitchDecision(chain_id, first, second, False, reason, defects))

    members: dict[str, list[str]] = {}
    for patch_id in sorted(parents, key=str):
        members.setdefault(find(patch_id), []).append(patch_id)
    stitched_by_root: dict[str, list[str]] = {}
    for decision in decisions:
        if decision.accepted:
            stitched_by_root.setdefault(find(decision.first_patch_id), []).append(decision.chain_id)
    islands: list[Island] = []
    island_by_patch: dict[str, str] = {}
    for index, root in enumerate(sorted(members)):
        island_id = f"island:{index}"
        islands.append(Island(
            id=island_id,
            patch_ids=tuple(members[root]),
            stitched_chain_ids=tuple(sorted(stitched_by_root.get(root, ()))),
        ))
        for patch_id in members[root]:
            island_by_patch[patch_id] = island_id
    return IslandAssembly(tuple(islands), tuple(decisions), island_by_patch)


def _gate(source, topology, chain_id, angle_by_source_vertex, cut_chains_by_vertex, border_vertices):
    chain = topology.chains[_key(topology.chains, chain_id)]
    interior, endpoints = _chain_vertex_split(source, chain)
    candidates = set(interior)
    for endpoint in endpoints:
        other_cuts = cut_chains_by_vertex.get(endpoint, set()) - {chain_id}
        if not other_cuts and endpoint not in border_vertices:
            candidates.add(endpoint)
    defects: dict[str, float] = {}
    for source_vertex_id in sorted(candidates):
        angle = angle_by_source_vertex.get(source_vertex_id)
        if angle is None:
            return False, f"missing angle data at {source_vertex_id}", {}
        defects[source_vertex_id] = 2.0 * pi - angle
    failing = {key: value for key, value in defects.items() if abs(value) > STITCH_DEFECT_TOLERANCE}
    if failing:
        return False, "angle defect exceeds stitch limit", failing
    return True, "all would-be interior vertices have near-zero defect", defects


def _chain_vertex_split(source, chain) -> tuple[tuple[str, ...], tuple[str, ...]]:
    counts: dict[str, int] = {}
    for edge_id in chain.source_edge_ids:
        for vertex_id in source.edges[_key(source.edges, str(edge_id))].vertex_ids:
            counts[str(vertex_id)] = counts.get(str(vertex_id), 0) + 1
    interior = tuple(sorted(v for v, count in counts.items() if count >= 2))
    endpoints = tuple(sorted(v for v, count in counts.items() if count == 1))
    return interior, endpoints


def _chain_ids_by_source_vertex(source, topology) -> dict[str, set[str]]:
    incident: dict[str, set[str]] = {}
    for chain in topology.chains.values():
        for edge_id in chain.source_edge_ids:
            for vertex_id in source.edges[_key(source.edges, str(edge_id))].vertex_ids:
                incident.setdefault(str(vertex_id), set()).add(str(chain.id))
    return incident


def _chain_edge_count(topology, chain_id) -> int:
    return len(topology.chains[_key(topology.chains, str(chain_id))].source_edge_ids)


def _angle_by_source_vertex(context) -> dict[str, float]:
    angles: dict[str, float] = {}
    topology = context.topology_snapshot
    for vertex_id, facts in context.geometry_facts.vertex_facts.items():
        vertex = topology.vertices.get(vertex_id)
        if vertex is None:
            continue
        for source_vertex_id in vertex.source_vertex_ids:
            angles[str(source_vertex_id)] = facts.interior_angle_sum
    return angles


def _border_source_vertices(source) -> set[str]:
    selected = {str(face_id) for face_id in source.selected_face_ids} or {
        str(face_id) for face_id in source.faces
    }
    face_count_by_edge: dict[str, int] = {}
    for face_id, face in source.faces.items():
        if str(face_id) not in selected:
            continue
        for edge_id in face.edge_ids:
            face_count_by_edge[str(edge_id)] = face_count_by_edge.get(str(edge_id), 0) + 1
    border: set[str] = set()
    for edge_id, count in face_count_by_edge.items():
        if count != 2:
            for vertex_id in source.edges[_key(source.edges, edge_id)].vertex_ids:
                border.add(str(vertex_id))
    return border


def _key(mapping, wanted: str):
    for key in mapping:
        if str(key) == wanted:
            return key
    raise KeyError(wanted)
