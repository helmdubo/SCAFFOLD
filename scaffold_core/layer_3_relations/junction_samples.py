"""
Layer: 3 - Relations

Rules:
- Build patch-local junction endpoint samples from ChainDirectionalRunUse records.
- Use Layer 2 geometry facts as derived evidence.
- Do not mutate Layer 1 topology or store normals on ChainUse.
- Do not build world-facing semantics or runtime solve data.
"""

from __future__ import annotations

from scaffold_core.core.evidence import Evidence
from scaffold_core.ids import PatchId, SourceVertexId, VertexId
from scaffold_core.layer_1_topology.model import SurfaceModel
from scaffold_core.layer_1_topology.queries import chain_use_vertices
from scaffold_core.layer_2_geometry.facts import GeometryFactSnapshot, Vector3, VertexFanGeometryFacts
from scaffold_core.layer_2_geometry.measures import EPSILON, length, normalize
from scaffold_core.layer_3_relations.model import (
    ChainDirectionalRunUse,
    ChainDirectionalRunUseJunctionSample,
    OwnerNormalSource,
    RunUseEndpointRole,
)


POLICY_NAME = "g3c4_junction_samples"


def build_junction_samples(
    topology: SurfaceModel,
    geometry: GeometryFactSnapshot,
    run_uses: tuple[ChainDirectionalRunUse, ...],
) -> tuple[ChainDirectionalRunUseJunctionSample, ...]:
    """Build endpoint samples for patch-local directional run uses."""

    source_vertex_to_vertices = _source_vertex_to_vertices(topology)
    vertex_fans_by_patch_vertex = {
        (fan.patch_id, fan.vertex_id): fan
        for fan in geometry.vertex_fan_facts.values()
    }
    samples: list[ChainDirectionalRunUseJunctionSample] = []
    for run_use in sorted(run_uses, key=lambda item: item.id):
        samples.extend(
            _samples_for_run_use(
                topology,
                run_use,
                geometry,
                source_vertex_to_vertices,
                vertex_fans_by_patch_vertex,
            )
        )
    return tuple(samples)


def _samples_for_run_use(
    topology: SurfaceModel,
    run_use: ChainDirectionalRunUse,
    geometry: GeometryFactSnapshot,
    source_vertex_to_vertices: dict[SourceVertexId, tuple[VertexId, ...]],
    vertex_fans_by_patch_vertex: dict[tuple[PatchId, VertexId], VertexFanGeometryFacts],
) -> tuple[ChainDirectionalRunUseJunctionSample, ...]:
    return tuple(
        sample
        for sample in (
            _sample(
                topology=topology,
                run_use=run_use,
                role=RunUseEndpointRole.START,
                source_vertex_id=run_use.start_source_vertex_id,
                tangent_away_from_vertex=run_use.direction,
                geometry=geometry,
                source_vertex_to_vertices=source_vertex_to_vertices,
                vertex_fans_by_patch_vertex=vertex_fans_by_patch_vertex,
            ),
            _sample(
                topology=topology,
                run_use=run_use,
                role=RunUseEndpointRole.END,
                source_vertex_id=run_use.end_source_vertex_id,
                tangent_away_from_vertex=_reverse(run_use.direction),
                geometry=geometry,
                source_vertex_to_vertices=source_vertex_to_vertices,
                vertex_fans_by_patch_vertex=vertex_fans_by_patch_vertex,
            ),
        )
        if sample is not None
    )


def _sample(
    topology: SurfaceModel,
    run_use: ChainDirectionalRunUse,
    role: RunUseEndpointRole,
    source_vertex_id: SourceVertexId,
    tangent_away_from_vertex: Vector3,
    geometry: GeometryFactSnapshot,
    source_vertex_to_vertices: dict[SourceVertexId, tuple[VertexId, ...]],
    vertex_fans_by_patch_vertex: dict[tuple[PatchId, VertexId], VertexFanGeometryFacts],
) -> ChainDirectionalRunUseJunctionSample | None:
    vertex_id = _endpoint_vertex_id(
        topology,
        run_use,
        role,
        source_vertex_id,
        source_vertex_to_vertices,
    )
    if vertex_id is None:
        return None

    owner_normal, owner_normal_source, owner_data = _owner_normal(
        run_use,
        geometry,
        vertex_id,
        vertex_fans_by_patch_vertex,
    )
    tangent = normalize(tangent_away_from_vertex)
    normal = normalize(owner_normal)
    confidence = run_use.confidence
    if tangent == (0.0, 0.0, 0.0) or owner_normal_source is OwnerNormalSource.UNKNOWN:
        confidence = 0.0
    elif normal == (0.0, 0.0, 0.0):
        confidence *= 0.5

    return ChainDirectionalRunUseJunctionSample(
        id=f"junction_sample:{run_use.id}:{role.value}",
        vertex_id=vertex_id,
        run_use_id=run_use.id,
        chain_use_id=run_use.chain_use_id,
        patch_id=run_use.patch_id,
        endpoint_role=role,
        tangent_away_from_vertex=tangent,
        owner_normal=normal,
        owner_normal_source=owner_normal_source,
        confidence=confidence,
        evidence=(_evidence(run_use, source_vertex_id, owner_normal_source, owner_data),),
    )


def _owner_normal(
    run_use: ChainDirectionalRunUse,
    geometry: GeometryFactSnapshot,
    vertex_id: VertexId,
    vertex_fans_by_patch_vertex: dict[tuple[PatchId, VertexId], VertexFanGeometryFacts],
) -> tuple[Vector3, OwnerNormalSource, dict[str, object]]:
    vertex_fan = vertex_fans_by_patch_vertex.get((run_use.patch_id, vertex_id))
    if vertex_fan is not None and length(vertex_fan.normal) > EPSILON:
        return (
            vertex_fan.normal,
            OwnerNormalSource.VERTEX_FAN_NORMAL,
            {"vertex_fan_id": vertex_fan.id},
        )

    patch_facts = geometry.patch_facts.get(run_use.patch_id)
    if patch_facts is None:
        return (0.0, 0.0, 0.0), OwnerNormalSource.UNKNOWN, {}
    source = (
        OwnerNormalSource.PATCH_AGGREGATE_NORMAL
        if length(patch_facts.normal) > EPSILON
        else OwnerNormalSource.UNKNOWN
    )
    return patch_facts.normal, source, {}


def _endpoint_vertex_id(
    topology: SurfaceModel,
    run_use: ChainDirectionalRunUse,
    role: RunUseEndpointRole,
    source_vertex_id: SourceVertexId,
    source_vertex_to_vertices: dict[SourceVertexId, tuple[VertexId, ...]],
) -> VertexId | None:
    chain_use = topology.chain_uses.get(run_use.chain_use_id)
    if chain_use is not None:
        start_vertex_id, end_vertex_id = chain_use_vertices(topology, chain_use.id)
        start_sources = topology.vertices[start_vertex_id].source_vertex_ids
        end_sources = topology.vertices[end_vertex_id].source_vertex_ids
        if role is RunUseEndpointRole.START and source_vertex_id in start_sources:
            return start_vertex_id
        if role is RunUseEndpointRole.END and source_vertex_id in end_sources:
            return end_vertex_id

    vertex_ids = source_vertex_to_vertices.get(source_vertex_id, ())
    if VertexId(f"vertex:{source_vertex_id}") in vertex_ids:
        return VertexId(f"vertex:{source_vertex_id}")
    return vertex_ids[0] if vertex_ids else None


def _source_vertex_to_vertices(topology: SurfaceModel) -> dict[SourceVertexId, tuple[VertexId, ...]]:
    vertex_ids_by_source: dict[SourceVertexId, list[VertexId]] = {}
    for vertex in topology.vertices.values():
        for source_vertex_id in vertex.source_vertex_ids:
            vertex_ids_by_source.setdefault(source_vertex_id, []).append(vertex.id)
    return {
        source_vertex_id: tuple(sorted(vertex_ids, key=str))
        for source_vertex_id, vertex_ids in vertex_ids_by_source.items()
    }


def _reverse(vector: Vector3) -> Vector3:
    return (-vector[0], -vector[1], -vector[2])


def _evidence(
    run_use: ChainDirectionalRunUse,
    source_vertex_id: SourceVertexId,
    owner_normal_source: OwnerNormalSource,
    owner_data: dict[str, object],
) -> Evidence:
    return Evidence(
        source="layer_3_relations.junction_samples",
        summary="endpoint sample derived from ChainDirectionalRunUse",
        data={
            "policy": POLICY_NAME,
            "run_use_id": run_use.id,
            "source_vertex_id": str(source_vertex_id),
            "owner_normal_source": owner_normal_source.value,
            **owner_data,
        },
    )
