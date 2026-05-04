"""
Layer: 3 - Relations

Rules:
- Build derived relation snapshots from Layer 1 topology and Layer 2 geometry.
- Do not mutate lower-layer snapshots.
- Do not derive features, runtime solve data, UV data, API data, or UI data.
"""

from __future__ import annotations

from math import atan2

from scaffold_core.ids import ChainId
from scaffold_core.layer_1_topology.model import PatchChain, SurfaceModel
from scaffold_core.layer_1_topology.queries import patch_chain_vertices, patch_chains_for_chain
from scaffold_core.layer_2_geometry.facts import GeometryFactSnapshot, Vector3
from scaffold_core.layer_2_geometry.measures import cross, dot, length, normalize, subtract
from scaffold_core.layer_3_relations.alignment import build_alignment_classes, build_patch_axes
from scaffold_core.layer_3_relations.chain_refinement import (
    build_patch_chain_directional_evidence,
    build_chain_directional_runs,
)
from scaffold_core.layer_3_relations.continuation import build_chain_continuations
from scaffold_core.layer_3_relations.loop_corners import build_loop_corners
from scaffold_core.layer_3_relations.model import DihedralKind, PatchAdjacency, RelationSnapshot
from scaffold_core.layer_3_relations.patch_chain_endpoint_relations import (
    build_patch_chain_endpoint_relations,
)
from scaffold_core.layer_3_relations.patch_chain_endpoint_samples import build_patch_chain_endpoint_samples
from scaffold_core.layer_3_relations.scaffold_continuity import build_scaffold_continuity_components
from scaffold_core.layer_3_relations.scaffold_graph import build_scaffold_graph
from scaffold_core.layer_3_relations.scaffold_graph_relations import build_scaffold_graph_relations
from scaffold_core.layer_3_relations.scaffold_junctions import build_scaffold_junctions
from scaffold_core.layer_3_relations.scaffold_nodes import build_scaffold_nodes


ANGLE_TOLERANCE_RADIANS = 1.0e-6


def build_relation_snapshot(
    topology: SurfaceModel,
    geometry: GeometryFactSnapshot,
) -> RelationSnapshot:
    """Build G3a derived relations."""

    patch_adjacencies: dict[str, PatchAdjacency] = {}
    for chain_id in topology.chains:
        uses = patch_chains_for_chain(topology, chain_id)
        if not _is_normal_patch_adjacency(uses):
            continue

        first_use, second_use = uses
        adjacency = _build_patch_adjacency(
            topology,
            geometry,
            chain_id,
            first_use,
            second_use,
        )
        patch_adjacencies[adjacency.id] = adjacency

    chain_directional_runs = build_chain_directional_runs(topology, geometry)
    patch_chain_directional_evidence = build_patch_chain_directional_evidence(
        topology,
        chain_directional_runs,
    )
    loop_corners = build_loop_corners(topology)
    patch_chain_endpoint_samples = build_patch_chain_endpoint_samples(
        topology,
        geometry,
        patch_chain_directional_evidence,
    )
    patch_chain_endpoint_relations = build_patch_chain_endpoint_relations(patch_chain_endpoint_samples)
    scaffold_nodes = build_scaffold_nodes(
        topology,
        loop_corners,
        patch_chain_endpoint_samples,
        patch_chain_endpoint_relations,
    )
    scaffold_edges, scaffold_graph = build_scaffold_graph(topology, scaffold_nodes)
    scaffold_junctions = build_scaffold_junctions(scaffold_nodes, scaffold_edges)
    alignment_classes = build_alignment_classes(patch_chain_directional_evidence)
    side_surface_continuity_evidence, scaffold_node_incident_edge_relations, shared_chain_patch_chain_relations = build_scaffold_graph_relations(
        scaffold_nodes,
        scaffold_edges,
        patch_chain_endpoint_samples,
        patch_chain_endpoint_relations,
        patch_adjacencies,
        loop_corners,
        alignment_classes,
    )
    scaffold_continuity_components = build_scaffold_continuity_components(
        scaffold_edges,
        scaffold_node_incident_edge_relations,
    )
    return RelationSnapshot(
        patch_adjacencies=patch_adjacencies,
        chain_continuations=build_chain_continuations(topology),
        chain_directional_runs=chain_directional_runs,
        patch_chain_directional_evidence=patch_chain_directional_evidence,
        loop_corners=loop_corners,
        patch_chain_endpoint_samples=patch_chain_endpoint_samples,
        patch_chain_endpoint_relations=patch_chain_endpoint_relations,
        scaffold_nodes=scaffold_nodes,
        scaffold_edges=scaffold_edges,
        scaffold_graph=scaffold_graph,
        scaffold_junctions=scaffold_junctions,
        side_surface_continuity_evidence=side_surface_continuity_evidence,
        scaffold_node_incident_edge_relations=scaffold_node_incident_edge_relations,
        shared_chain_patch_chain_relations=shared_chain_patch_chain_relations,
        scaffold_continuity_components=scaffold_continuity_components,
        alignment_classes=alignment_classes,
        patch_axes=build_patch_axes(
            topology,
            patch_chain_directional_evidence,
            alignment_classes,
        ),
    )


def _is_normal_patch_adjacency(uses: tuple[PatchChain, ...]) -> bool:
    return len(uses) == 2 and uses[0].patch_id != uses[1].patch_id


def _build_patch_adjacency(
    topology: SurfaceModel,
    geometry: GeometryFactSnapshot,
    chain_id: ChainId,
    first_use: PatchChain,
    second_use: PatchChain,
) -> PatchAdjacency:
    first_normal = geometry.patch_facts[first_use.patch_id].normal
    second_normal = geometry.patch_facts[second_use.patch_id].normal
    edge_direction = _chain_pair_direction(topology, geometry, first_use, second_use)
    if length(first_normal) == 0.0 or length(second_normal) == 0.0 or length(edge_direction) == 0.0:
        signed_angle = 0.0
        dihedral_kind = DihedralKind.UNDEFINED
    else:
        signed_angle = _signed_angle(first_normal, second_normal, edge_direction)
        dihedral_kind = _dihedral_kind(signed_angle)
    adjacency_id = f"adjacency:{chain_id}:{first_use.patch_id}:{second_use.patch_id}"

    return PatchAdjacency(
        id=adjacency_id,
        first_patch_id=first_use.patch_id,
        second_patch_id=second_use.patch_id,
        chain_id=chain_id,
        first_patch_chain_id=first_use.id,
        second_patch_chain_id=second_use.id,
        shared_length=geometry.chain_facts[chain_id].length,
        signed_angle_radians=signed_angle,
        dihedral_kind=dihedral_kind,
    )


def _patch_chain_direction(
    topology: SurfaceModel,
    geometry: GeometryFactSnapshot,
    use: PatchChain,
) -> Vector3:
    start_vertex_id, end_vertex_id = patch_chain_vertices(topology, use.id)
    start = geometry.vertex_facts[start_vertex_id].position
    end = geometry.vertex_facts[end_vertex_id].position
    return normalize(subtract(end, start))


def _chain_pair_direction(
    topology: SurfaceModel,
    geometry: GeometryFactSnapshot,
    first_use: PatchChain,
    second_use: PatchChain,
) -> Vector3:
    first_direction = _patch_chain_direction(topology, geometry, first_use)
    second_direction = _patch_chain_direction(topology, geometry, second_use)
    return normalize(subtract(first_direction, second_direction))


def _signed_angle(
    first_normal: Vector3,
    second_normal: Vector3,
    edge_direction: Vector3,
) -> float:
    sine = dot(cross(first_normal, second_normal), edge_direction)
    cosine = dot(first_normal, second_normal)
    return atan2(sine, cosine)


def _dihedral_kind(signed_angle: float) -> DihedralKind:
    if abs(signed_angle) <= ANGLE_TOLERANCE_RADIANS:
        return DihedralKind.COPLANAR
    if signed_angle > 0.0:
        return DihedralKind.CONVEX
    if signed_angle < 0.0:
        return DihedralKind.CONCAVE
    return DihedralKind.UNDEFINED
