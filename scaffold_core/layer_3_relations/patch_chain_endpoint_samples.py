"""
Layer: 3 - Relations

Rules:
- Build patch-local PatchChain endpoint samples from PatchChainDirectionalEvidence records.
- Use Layer 2 geometry facts as derived evidence.
- Do not mutate Layer 1 topology or store normals on PatchChain.
- Do not build world-facing semantics or runtime solve data.
"""

from __future__ import annotations

from scaffold_core.core.evidence import Evidence
from scaffold_core.ids import PatchId, SourceVertexId, VertexId
from scaffold_core.layer_1_topology.model import PatchChain, SurfaceModel
from scaffold_core.layer_1_topology.queries import patch_chain_vertices
from scaffold_core.layer_2_geometry.facts import (
    ChainSegmentGeometryFacts,
    GeometryFactSnapshot,
    LocalFaceFanGeometryFacts,
    Vector3,
)
from scaffold_core.layer_2_geometry.measures import EPSILON, length, normalize
from scaffold_core.layer_3_relations.model import (
    PatchChainDirectionalEvidence,
    OwnerNormalSource,
    PatchChainEndpointSample,
    PatchChainEndpointRole,
)


POLICY_NAME = "g3c4_patch_chain_endpoint_samples"
RUN_DERIVED_SAMPLE_SOURCE = "RUN_DERIVED"
LOCAL_SEGMENT_SAMPLE_SOURCE = "LOCAL_SEGMENT"


def build_patch_chain_endpoint_samples(
    topology: SurfaceModel,
    geometry: GeometryFactSnapshot,
    directional_evidence_items: tuple[PatchChainDirectionalEvidence, ...],
) -> tuple[PatchChainEndpointSample, ...]:
    """Build endpoint samples for patch-local directional evidence."""

    source_vertex_to_vertices = _source_vertex_to_vertices(topology)
    local_face_fans_by_patch_vertex = {
        (fan.patch_id, fan.vertex_id): fan
        for fan in geometry.local_face_fan_facts.values()
    }
    samples: list[PatchChainEndpointSample] = []
    for directional_evidence in sorted(directional_evidence_items, key=lambda item: item.id):
        samples.extend(
            _samples_for_directional_evidence(
                topology,
                directional_evidence,
                geometry,
                source_vertex_to_vertices,
                local_face_fans_by_patch_vertex,
            )
        )
    samples.extend(
        _local_segment_samples(
            topology,
            geometry,
            tuple(samples),
            local_face_fans_by_patch_vertex,
        )
    )
    return tuple(samples)


def _samples_for_directional_evidence(
    topology: SurfaceModel,
    directional_evidence: PatchChainDirectionalEvidence,
    geometry: GeometryFactSnapshot,
    source_vertex_to_vertices: dict[SourceVertexId, tuple[VertexId, ...]],
    local_face_fans_by_patch_vertex: dict[tuple[PatchId, VertexId], LocalFaceFanGeometryFacts],
) -> tuple[PatchChainEndpointSample, ...]:
    return tuple(
        sample
        for sample in (
            _sample(
                topology=topology,
                directional_evidence=directional_evidence,
                role=PatchChainEndpointRole.START,
                source_vertex_id=directional_evidence.start_source_vertex_id,
                tangent_away_from_vertex=directional_evidence.direction,
                geometry=geometry,
                source_vertex_to_vertices=source_vertex_to_vertices,
                local_face_fans_by_patch_vertex=local_face_fans_by_patch_vertex,
            ),
            _sample(
                topology=topology,
                directional_evidence=directional_evidence,
                role=PatchChainEndpointRole.END,
                source_vertex_id=directional_evidence.end_source_vertex_id,
                tangent_away_from_vertex=_reverse(directional_evidence.direction),
                geometry=geometry,
                source_vertex_to_vertices=source_vertex_to_vertices,
                local_face_fans_by_patch_vertex=local_face_fans_by_patch_vertex,
            ),
        )
        if sample is not None
    )


def _sample(
    topology: SurfaceModel,
    directional_evidence: PatchChainDirectionalEvidence,
    role: PatchChainEndpointRole,
    source_vertex_id: SourceVertexId,
    tangent_away_from_vertex: Vector3,
    geometry: GeometryFactSnapshot,
    source_vertex_to_vertices: dict[SourceVertexId, tuple[VertexId, ...]],
    local_face_fans_by_patch_vertex: dict[tuple[PatchId, VertexId], LocalFaceFanGeometryFacts],
) -> PatchChainEndpointSample | None:
    vertex_id = _endpoint_vertex_id(
        topology,
        directional_evidence,
        role,
        source_vertex_id,
        source_vertex_to_vertices,
    )
    if vertex_id is None:
        return None

    owner_normal, owner_normal_source, owner_data = _owner_normal(
        directional_evidence,
        geometry,
        vertex_id,
        local_face_fans_by_patch_vertex,
    )
    tangent = normalize(tangent_away_from_vertex)
    normal = normalize(owner_normal)
    confidence = directional_evidence.confidence
    if tangent == (0.0, 0.0, 0.0) or owner_normal_source is OwnerNormalSource.UNKNOWN:
        confidence = 0.0
    elif normal == (0.0, 0.0, 0.0):
        confidence *= 0.5

    return PatchChainEndpointSample(
        id=f"patch_chain_endpoint_sample:{directional_evidence.id}:{role.value}",
        vertex_id=vertex_id,
        directional_evidence_id=directional_evidence.id,
        patch_chain_id=directional_evidence.patch_chain_id,
        patch_id=directional_evidence.patch_id,
        endpoint_role=role,
        tangent_away_from_vertex=tangent,
        owner_normal=normal,
        owner_normal_source=owner_normal_source,
        confidence=confidence,
        evidence=(
            _evidence(
                directional_evidence.id,
                source_vertex_id,
                owner_normal_source,
                owner_data,
                RUN_DERIVED_SAMPLE_SOURCE,
            ),
        ),
    )


def _local_segment_samples(
    topology: SurfaceModel,
    geometry: GeometryFactSnapshot,
    existing_samples: tuple[PatchChainEndpointSample, ...],
    local_face_fans_by_patch_vertex: dict[tuple[PatchId, VertexId], LocalFaceFanGeometryFacts],
) -> tuple[PatchChainEndpointSample, ...]:
    existing_keys = {
        (sample.patch_chain_id, sample.endpoint_role, sample.vertex_id)
        for sample in existing_samples
    }
    samples: list[PatchChainEndpointSample] = []
    for patch_chain in sorted(topology.patch_chains.values(), key=lambda item: str(item.id)):
        for role in (PatchChainEndpointRole.START, PatchChainEndpointRole.END):
            vertex_id = _topology_endpoint_vertex_id(topology, patch_chain, role)
            if (patch_chain.id, role, vertex_id) in existing_keys:
                continue
            sample = _local_segment_sample(
                topology,
                geometry,
                patch_chain,
                role,
                vertex_id,
                local_face_fans_by_patch_vertex,
            )
            if sample is not None:
                samples.append(sample)
    return tuple(samples)


def _local_segment_sample(
    topology: SurfaceModel,
    geometry: GeometryFactSnapshot,
    patch_chain: PatchChain,
    role: PatchChainEndpointRole,
    vertex_id: VertexId,
    local_face_fans_by_patch_vertex: dict[tuple[PatchId, VertexId], LocalFaceFanGeometryFacts],
) -> PatchChainEndpointSample | None:
    source_vertex_id, tangent_away_from_vertex, segment = _local_endpoint_segment_tangent(
        topology,
        geometry,
        patch_chain,
        role,
        vertex_id,
    )
    if source_vertex_id is None or segment is None:
        return None
    owner_normal, owner_normal_source, owner_data = _owner_normal_for_patch(
        patch_chain.patch_id,
        geometry,
        vertex_id,
        local_face_fans_by_patch_vertex,
    )
    tangent = normalize(tangent_away_from_vertex)
    normal = normalize(owner_normal)
    confidence = 1.0
    if tangent == (0.0, 0.0, 0.0) or owner_normal_source is OwnerNormalSource.UNKNOWN:
        confidence = 0.0
    elif normal == (0.0, 0.0, 0.0):
        confidence = 0.5
    directional_evidence_id = f"local_segment:{patch_chain.id}:{role.value}"
    return PatchChainEndpointSample(
        id=f"patch_chain_endpoint_sample:{directional_evidence_id}",
        vertex_id=vertex_id,
        directional_evidence_id=directional_evidence_id,
        patch_chain_id=patch_chain.id,
        patch_id=patch_chain.patch_id,
        endpoint_role=role,
        tangent_away_from_vertex=tangent,
        owner_normal=normal,
        owner_normal_source=owner_normal_source,
        confidence=confidence,
        evidence=(
            _evidence(
                directional_evidence_id,
                source_vertex_id,
                owner_normal_source,
                {
                    **owner_data,
                    "chain_id": str(patch_chain.chain_id),
                    "segment_index": segment.segment_index,
                    "source_edge_id": str(segment.source_edge_id),
                },
                LOCAL_SEGMENT_SAMPLE_SOURCE,
            ),
        ),
    )


def _owner_normal(
    directional_evidence: PatchChainDirectionalEvidence,
    geometry: GeometryFactSnapshot,
    vertex_id: VertexId,
    local_face_fans_by_patch_vertex: dict[tuple[PatchId, VertexId], LocalFaceFanGeometryFacts],
) -> tuple[Vector3, OwnerNormalSource, dict[str, object]]:
    return _owner_normal_for_patch(
        directional_evidence.patch_id,
        geometry,
        vertex_id,
        local_face_fans_by_patch_vertex,
    )


def _owner_normal_for_patch(
    patch_id: PatchId,
    geometry: GeometryFactSnapshot,
    vertex_id: VertexId,
    local_face_fans_by_patch_vertex: dict[tuple[PatchId, VertexId], LocalFaceFanGeometryFacts],
) -> tuple[Vector3, OwnerNormalSource, dict[str, object]]:
    local_face_fan = local_face_fans_by_patch_vertex.get((patch_id, vertex_id))
    if local_face_fan is not None and length(local_face_fan.normal) > EPSILON:
        return (
            local_face_fan.normal,
            OwnerNormalSource.LOCAL_FACE_FAN_NORMAL,
            {"local_face_fan_id": local_face_fan.id},
        )

    patch_facts = geometry.patch_facts.get(patch_id)
    if patch_facts is None:
        return (0.0, 0.0, 0.0), OwnerNormalSource.UNKNOWN, {}
    source = (
        OwnerNormalSource.PATCH_AGGREGATE_NORMAL
        if length(patch_facts.normal) > EPSILON
        else OwnerNormalSource.UNKNOWN
    )
    return patch_facts.normal, source, {}


def _topology_endpoint_vertex_id(
    topology: SurfaceModel,
    patch_chain: PatchChain,
    role: PatchChainEndpointRole,
) -> VertexId:
    start_vertex_id, end_vertex_id = patch_chain_vertices(topology, patch_chain.id)
    return start_vertex_id if role is PatchChainEndpointRole.START else end_vertex_id


def _local_endpoint_segment_tangent(
    topology: SurfaceModel,
    geometry: GeometryFactSnapshot,
    patch_chain: PatchChain,
    role: PatchChainEndpointRole,
    vertex_id: VertexId,
) -> tuple[SourceVertexId | None, Vector3, ChainSegmentGeometryFacts | None]:
    chain_facts = geometry.chain_facts.get(patch_chain.chain_id)
    if chain_facts is None:
        return None, (0.0, 0.0, 0.0), None
    vertex = topology.vertices.get(vertex_id)
    if vertex is None:
        return None, (0.0, 0.0, 0.0), None
    source_vertex_ids = frozenset(vertex.source_vertex_ids)
    segments = (
        chain_facts.segments
        if role is PatchChainEndpointRole.START
        else tuple(reversed(chain_facts.segments))
    )
    for segment in segments:
        if segment.start_source_vertex_id in source_vertex_ids:
            return segment.start_source_vertex_id, segment.vector, segment
        if segment.end_source_vertex_id in source_vertex_ids:
            return segment.end_source_vertex_id, _reverse(segment.vector), segment
    return None, (0.0, 0.0, 0.0), None


def _endpoint_vertex_id(
    topology: SurfaceModel,
    directional_evidence: PatchChainDirectionalEvidence,
    role: PatchChainEndpointRole,
    source_vertex_id: SourceVertexId,
    source_vertex_to_vertices: dict[SourceVertexId, tuple[VertexId, ...]],
) -> VertexId | None:
    patch_chain = topology.patch_chains.get(directional_evidence.patch_chain_id)
    if patch_chain is not None:
        start_vertex_id, end_vertex_id = patch_chain_vertices(topology, patch_chain.id)
        start_sources = topology.vertices[start_vertex_id].source_vertex_ids
        end_sources = topology.vertices[end_vertex_id].source_vertex_ids
        if role is PatchChainEndpointRole.START and source_vertex_id in start_sources:
            return start_vertex_id
        if role is PatchChainEndpointRole.END and source_vertex_id in end_sources:
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
    directional_evidence_id: str,
    source_vertex_id: SourceVertexId,
    owner_normal_source: OwnerNormalSource,
    owner_data: dict[str, object],
    sample_source: str,
) -> Evidence:
    return Evidence(
        source="layer_3_relations.patch_chain_endpoint_samples",
        summary="PatchChain endpoint sample",
        data={
            "policy": POLICY_NAME,
            "sample_source": sample_source,
            "directional_evidence_id": directional_evidence_id,
            "source_vertex_id": str(source_vertex_id),
            "owner_normal_source": owner_normal_source.value,
            **owner_data,
        },
    )
