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
from scaffold_core.layer_1_topology.model import ChainUse, SurfaceModel
from scaffold_core.layer_1_topology.queries import chain_use_vertices, chain_uses_for_chain
from scaffold_core.layer_2_geometry.facts import GeometryFactSnapshot, Vector3
from scaffold_core.layer_2_geometry.measures import cross, dot, length, normalize, subtract
from scaffold_core.layer_3_relations.model import DihedralKind, PatchAdjacency, RelationSnapshot


ANGLE_TOLERANCE_RADIANS = 1.0e-6


def build_relation_snapshot(
    topology: SurfaceModel,
    geometry: GeometryFactSnapshot,
) -> RelationSnapshot:
    """Build G3a derived relations."""

    patch_adjacencies: dict[str, PatchAdjacency] = {}
    for chain_id in topology.chains:
        uses = chain_uses_for_chain(topology, chain_id)
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

    return RelationSnapshot(patch_adjacencies=patch_adjacencies)


def _is_normal_patch_adjacency(uses: tuple[ChainUse, ...]) -> bool:
    return len(uses) == 2 and uses[0].patch_id != uses[1].patch_id


def _build_patch_adjacency(
    topology: SurfaceModel,
    geometry: GeometryFactSnapshot,
    chain_id: ChainId,
    first_use: ChainUse,
    second_use: ChainUse,
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
        first_chain_use_id=first_use.id,
        second_chain_use_id=second_use.id,
        shared_length=geometry.chain_facts[chain_id].length,
        signed_angle_radians=signed_angle,
        dihedral_kind=dihedral_kind,
    )


def _chain_use_direction(
    topology: SurfaceModel,
    geometry: GeometryFactSnapshot,
    use: ChainUse,
) -> Vector3:
    start_vertex_id, end_vertex_id = chain_use_vertices(topology, use.id)
    start = geometry.vertex_facts[start_vertex_id].position
    end = geometry.vertex_facts[end_vertex_id].position
    return normalize(subtract(end, start))


def _chain_pair_direction(
    topology: SurfaceModel,
    geometry: GeometryFactSnapshot,
    first_use: ChainUse,
    second_use: ChainUse,
) -> Vector3:
    first_direction = _chain_use_direction(topology, geometry, first_use)
    second_direction = _chain_use_direction(topology, geometry, second_use)
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
