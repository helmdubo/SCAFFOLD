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
from scaffold_core.ids import SourceVertexId, VertexId
from scaffold_core.layer_1_topology.model import SurfaceModel
from scaffold_core.layer_2_geometry.facts import GeometryFactSnapshot, Vector3
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

    source_vertex_to_vertex = _source_vertex_to_vertex(topology)
    samples: list[ChainDirectionalRunUseJunctionSample] = []
    for run_use in sorted(run_uses, key=lambda item: item.id):
        samples.extend(_samples_for_run_use(run_use, geometry, source_vertex_to_vertex))
    return tuple(samples)


def _samples_for_run_use(
    run_use: ChainDirectionalRunUse,
    geometry: GeometryFactSnapshot,
    source_vertex_to_vertex: dict[SourceVertexId, VertexId],
) -> tuple[ChainDirectionalRunUseJunctionSample, ...]:
    owner_normal, owner_normal_source = _owner_normal(run_use, geometry)
    return tuple(
        sample
        for sample in (
            _sample(
                run_use=run_use,
                role=RunUseEndpointRole.START,
                source_vertex_id=run_use.start_source_vertex_id,
                tangent_away_from_vertex=run_use.direction,
                owner_normal=owner_normal,
                owner_normal_source=owner_normal_source,
                source_vertex_to_vertex=source_vertex_to_vertex,
            ),
            _sample(
                run_use=run_use,
                role=RunUseEndpointRole.END,
                source_vertex_id=run_use.end_source_vertex_id,
                tangent_away_from_vertex=_reverse(run_use.direction),
                owner_normal=owner_normal,
                owner_normal_source=owner_normal_source,
                source_vertex_to_vertex=source_vertex_to_vertex,
            ),
        )
        if sample is not None
    )


def _sample(
    run_use: ChainDirectionalRunUse,
    role: RunUseEndpointRole,
    source_vertex_id: SourceVertexId,
    tangent_away_from_vertex: Vector3,
    owner_normal: Vector3,
    owner_normal_source: OwnerNormalSource,
    source_vertex_to_vertex: dict[SourceVertexId, VertexId],
) -> ChainDirectionalRunUseJunctionSample | None:
    vertex_id = source_vertex_to_vertex.get(source_vertex_id)
    if vertex_id is None:
        return None

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
        evidence=(_evidence(run_use, source_vertex_id, owner_normal_source),),
    )


def _owner_normal(
    run_use: ChainDirectionalRunUse,
    geometry: GeometryFactSnapshot,
) -> tuple[Vector3, OwnerNormalSource]:
    patch_facts = geometry.patch_facts.get(run_use.patch_id)
    if patch_facts is None:
        return (0.0, 0.0, 0.0), OwnerNormalSource.UNKNOWN
    source = (
        OwnerNormalSource.PATCH_AGGREGATE_NORMAL
        if length(patch_facts.normal) > EPSILON
        else OwnerNormalSource.UNKNOWN
    )
    return patch_facts.normal, source


def _source_vertex_to_vertex(topology: SurfaceModel) -> dict[SourceVertexId, VertexId]:
    return {
        source_vertex_id: vertex.id
        for vertex in topology.vertices.values()
        for source_vertex_id in vertex.source_vertex_ids
    }


def _reverse(vector: Vector3) -> Vector3:
    return (-vector[0], -vector[1], -vector[2])


def _evidence(
    run_use: ChainDirectionalRunUse,
    source_vertex_id: SourceVertexId,
    owner_normal_source: OwnerNormalSource,
) -> Evidence:
    return Evidence(
        source="layer_3_relations.junction_samples",
        summary="endpoint sample derived from ChainDirectionalRunUse",
        data={
            "policy": POLICY_NAME,
            "run_use_id": run_use.id,
            "source_vertex_id": str(source_vertex_id),
            "owner_normal_source": owner_normal_source.value,
        },
    )
