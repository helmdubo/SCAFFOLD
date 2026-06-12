"""
Layer: 3 - Relations

Rules:
- Build ConnectedDirectionFamily evidence over existing directional and graph records.
- Propagate only through ScaffoldGraph connectivity and shared PatchChain relations.
- Do not mutate ScaffoldGraph, ScaffoldContinuityComponent, AlignmentClass, or Layer 1 identity.
- Do not build traces, rails, circuits, UV, solve, feature, API, UI, or runtime semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, pi, sin
from typing import Mapping

from scaffold_core.core.evidence import Evidence
from scaffold_core.ids import ChainId, PatchChainId, PatchId, VertexId
from scaffold_core.layer_1_topology.model import SurfaceModel
from scaffold_core.layer_1_topology.queries import patch_chains_for_chain
from scaffold_core.layer_2_geometry.facts import GeometryFactSnapshot, Vector3
from scaffold_core.layer_2_geometry.measures import EPSILON, add, cross, dot, length, normalize, scale
from scaffold_core.layer_3_relations.model import (
    ConnectedDirectionFamily,
    CrossingRecord,
    PatchAdjacency,
    PatchChainDirectionalEvidence,
    PatchChainEndpointRole,
    PatchChainEndpointSample,
    RunEndpointJunction,
    ScaffoldEdge,
    ScaffoldNode,
    ScaffoldNodeIncidentEdgeRelationKind,
    SharedChainPatchChainRelation,
)
from scaffold_core.layer_3_relations.scaffold_graph_relations import COMPATIBLE_NORMAL_MIN_DOT


POLICY_NAME = "connected_direction_family_v1"
DIRECTION_COMPATIBILITY_MIN_DOT = 0.996
GEODESIC_STRAIGHT_TOLERANCE = 0.1
SHARED_CHAIN_NORMAL_MIN_DOT = 0.9


@dataclass(frozen=True)
class _CrossingCandidate:
    first_directional_evidence_id: str
    second_directional_evidence_id: str
    record: CrossingRecord
    confidence: float


def build_connected_direction_families(
    topology: SurfaceModel,
    geometry: GeometryFactSnapshot,
    patch_adjacencies: Mapping[str, PatchAdjacency],
    directional_evidence_items: tuple[PatchChainDirectionalEvidence, ...],
    endpoint_samples: tuple[PatchChainEndpointSample, ...],
    scaffold_nodes: tuple[ScaffoldNode, ...],
    scaffold_edges: tuple[ScaffoldEdge, ...],
    run_endpoint_junctions: tuple[RunEndpointJunction, ...],
    scaffold_node_incident_edge_relations,
    shared_chain_relations: tuple[SharedChainPatchChainRelation, ...],
) -> tuple[ConnectedDirectionFamily, ...]:
    """Build DD-43/DD-45 connectivity-propagated direction-family evidence."""

    seeds = tuple(
        sorted(
            (
                item
                for item in directional_evidence_items
                if item.confidence > 0.0 and length(item.direction) > EPSILON
            ),
            key=lambda item: item.id,
        )
    )
    if not seeds:
        return ()

    evidence_by_id = {item.id: item for item in seeds}
    evidence_by_patch_chain = _evidence_by_patch_chain(seeds)
    sample_evidence_ids_by_sample_id = _sample_evidence_ids_by_sample_id(
        endpoint_samples,
        evidence_by_id,
        evidence_by_patch_chain,
    )
    sample_by_id = {sample.id: sample for sample in endpoint_samples}
    samples_by_evidence_id = _samples_by_evidence_id(endpoint_samples, sample_evidence_ids_by_sample_id)
    edge_by_patch_chain_id = {edge.patch_chain_id: edge for edge in scaffold_edges}
    adjacency_by_patch_pair = _adjacency_by_patch_pair(patch_adjacencies)
    self_seam_chain_ids = _self_seam_chain_ids(topology)

    shared_chain_candidates = _shared_chain_crossings(
        geometry,
        patch_adjacencies,
        shared_chain_relations,
        evidence_by_patch_chain,
        samples_by_evidence_id,
    )
    crossing_candidates = (
        *shared_chain_candidates,
        *_same_patch_shared_chain_bridges(evidence_by_id, shared_chain_candidates),
        *_node_crossings(
            geometry,
            scaffold_nodes,
            scaffold_node_incident_edge_relations,
            sample_by_id,
            sample_evidence_ids_by_sample_id,
            evidence_by_id,
            edge_by_patch_chain_id,
            adjacency_by_patch_pair,
            self_seam_chain_ids,
        ),
        *_in_patch_geodesic_crossings(
            geometry,
            run_endpoint_junctions,
            evidence_by_id,
            samples_by_evidence_id,
            self_seam_chain_ids,
        ),
    )
    components = _connected_components(evidence_by_id, crossing_candidates)
    family_crossings = _crossings_by_component(components, crossing_candidates)

    families: list[ConnectedDirectionFamily] = []
    for index, member_ids in enumerate(sorted(components.values(), key=lambda ids: tuple(ids))):
        members = tuple(evidence_by_id[member_id] for member_id in member_ids)
        crossings = tuple(sorted(
            family_crossings.get(tuple(member_ids), ()),
            key=lambda item: (
                item.kind,
                item.scaffold_node_id or "",
                item.run_endpoint_junction_id or "",
                str(item.shared_chain_id or ""),
                item.first_directional_evidence_id,
                item.second_directional_evidence_id,
            ),
        ))
        ordered_member_ids, branch_records = _ordered_members_and_branches(member_ids, crossings)
        member_map = _family_member_map(
            member_ids,
            evidence_by_id,
            edge_by_patch_chain_id,
            samples_by_evidence_id,
        )
        confidence_values = [member.confidence for member in members]
        confidence_values.extend(crossing.confidence for crossing in crossings)
        confidence = min(confidence_values) if confidence_values else 0.0
        families.append(
            ConnectedDirectionFamily(
                id=f"connected_direction_family:{index}",
                member_directional_evidence_ids=tuple(member_ids),
                patch_ids=tuple(sorted({member.patch_id for member in members}, key=str)),
                crossing_records=crossings,
                ordered_member_directional_evidence_ids=ordered_member_ids,
                branch_records=branch_records,
                member_map=member_map,
                confidence=confidence,
                evidence=(_family_evidence(member_ids, crossings, confidence),),
            )
        )
    return tuple(families)


def _in_patch_geodesic_crossings(
    geometry: GeometryFactSnapshot,
    run_endpoint_junctions: tuple[RunEndpointJunction, ...],
    evidence_by_id: Mapping[str, PatchChainDirectionalEvidence],
    samples_by_evidence_id: Mapping[str, tuple[PatchChainEndpointSample, ...]],
    self_seam_chain_ids: set[ChainId],
) -> tuple[_CrossingCandidate, ...]:
    local_face_fans = _local_face_fans_by_patch_vertex(geometry)
    candidates: list[_CrossingCandidate] = []
    for junction in sorted(run_endpoint_junctions, key=lambda item: item.id):
        occurrences = tuple(junction.incident_run_endpoint_occurrences)
        for first_index, first_occurrence in enumerate(occurrences):
            first_id, first_role = first_occurrence
            first = evidence_by_id.get(first_id)
            if first is None:
                continue
            for second_id, second_role in occurrences[first_index + 1:]:
                second = evidence_by_id.get(second_id)
                if second is None:
                    continue
                if not _can_attempt_in_patch_geodesic(
                    first,
                    first_role,
                    second,
                    second_role,
                    self_seam_chain_ids,
                ):
                    continue
                angle = _patch_occurrence_angle(
                    local_face_fans,
                    first.patch_id,
                    _pair_endpoint_vertex_ids(
                        samples_by_evidence_id,
                        first.id,
                        first_role,
                        second.id,
                        second_role,
                        junction.topology_vertex_ids,
                    ),
                )
                if angle is None or abs(angle - pi) > GEODESIC_STRAIGHT_TOLERANCE:
                    continue
                confidence = min(first.confidence, second.confidence, junction.confidence)
                candidates.append(_CrossingCandidate(
                    first_directional_evidence_id=first.id,
                    second_directional_evidence_id=second.id,
                    record=CrossingRecord(
                        kind="IN_PATCH_GEODESIC",
                        scaffold_node_id=junction.anchor_scaffold_node_id,
                        shared_chain_id=None,
                        patch_adjacency_id=None,
                        first_directional_evidence_id=first.id,
                        second_directional_evidence_id=second.id,
                        first_patch_chain_id=first.patch_chain_id,
                        second_patch_chain_id=second.patch_chain_id,
                        first_patch_id=first.patch_id,
                        second_patch_id=second.patch_id,
                        signed_dihedral_radians=0.0,
                        transported_direction_dot=1.0,
                        transported_normal_dot=None,
                        confidence=confidence,
                        measured_angle_radians=angle,
                        run_endpoint_junction_id=junction.id,
                    ),
                    confidence=confidence,
                ))
    return tuple(_deduplicate_crossings(candidates))


def _can_attempt_in_patch_geodesic(
    first: PatchChainDirectionalEvidence,
    first_role: PatchChainEndpointRole,
    second: PatchChainDirectionalEvidence,
    second_role: PatchChainEndpointRole,
    self_seam_chain_ids: set[ChainId],
) -> bool:
    if first.id == second.id:
        return False
    if first.patch_id != second.patch_id or first.loop_id != second.loop_id:
        return False
    if first_role is second_role:
        return False
    return first.parent_chain_id not in self_seam_chain_ids and second.parent_chain_id not in self_seam_chain_ids


def _pair_endpoint_vertex_ids(
    samples_by_evidence_id: Mapping[str, tuple[PatchChainEndpointSample, ...]],
    first_id: str,
    first_role: PatchChainEndpointRole,
    second_id: str,
    second_role: PatchChainEndpointRole,
    fallback_vertex_ids: tuple[VertexId, ...],
) -> tuple[VertexId, ...]:
    vertex_ids = tuple(
        sample.vertex_id
        for evidence_id, role in ((first_id, first_role), (second_id, second_role))
        for sample in samples_by_evidence_id.get(evidence_id, ())
        if sample.endpoint_role is role
    )
    return tuple(sorted(set(vertex_ids), key=str)) or fallback_vertex_ids


def _local_face_fans_by_patch_vertex(geometry: GeometryFactSnapshot):
    fans: dict[tuple[PatchId, VertexId], list] = {}
    for fan in geometry.local_face_fan_facts.values():
        fans.setdefault((fan.patch_id, fan.vertex_id), []).append(fan)
    return {
        key: tuple(sorted(values, key=lambda item: item.id))
        for key, values in fans.items()
    }


def _patch_occurrence_angle(
    local_face_fans_by_patch_vertex,
    patch_id: PatchId,
    topology_vertex_ids: tuple[VertexId, ...],
) -> float | None:
    fans = tuple(
        fan
        for vertex_id in topology_vertex_ids
        for fan in local_face_fans_by_patch_vertex.get((patch_id, vertex_id), ())
    )
    if not fans:
        return None
    angles = tuple(sorted(fan.interior_angle_sum for fan in fans))
    first_angle = angles[0]
    if all(abs(angle - first_angle) <= EPSILON for angle in angles[1:]):
        return first_angle
    return None


def _self_seam_chain_ids(topology: SurfaceModel) -> set[ChainId]:
    self_seam_chain_ids: set[ChainId] = set()
    for chain_id in topology.chains:
        patch_ids = tuple(use.patch_id for use in patch_chains_for_chain(topology, chain_id))
        if len(patch_ids) != len(set(patch_ids)):
            self_seam_chain_ids.add(chain_id)
    return self_seam_chain_ids


def _shared_chain_crossings(
    geometry: GeometryFactSnapshot,
    patch_adjacencies: Mapping[str, PatchAdjacency],
    shared_chain_relations: tuple[SharedChainPatchChainRelation, ...],
    evidence_by_patch_chain: Mapping[PatchChainId, tuple[PatchChainDirectionalEvidence, ...]],
    samples_by_evidence_id: Mapping[str, tuple[PatchChainEndpointSample, ...]],
) -> tuple[_CrossingCandidate, ...]:
    candidates: list[_CrossingCandidate] = []
    for relation in sorted(shared_chain_relations, key=lambda item: item.id):
        adjacency = patch_adjacencies.get(relation.patch_adjacency_id or "")
        axis = _transport_axis(geometry, relation.chain_id, ())
        for first in evidence_by_patch_chain.get(relation.first_patch_chain_id, ()):
            for second in evidence_by_patch_chain.get(relation.second_patch_chain_id, ()):
                shared_source_edge_ids = tuple(
                    sorted(set(first.source_edge_ids) & set(second.source_edge_ids), key=str)
                )
                if not shared_source_edge_ids:
                    continue
                signed_dihedral = _signed_dihedral_for_patch_order(
                    adjacency,
                    first.patch_id,
                    second.patch_id,
                )
                transport_dot = _transport_direction_dot(first.direction, second.direction, axis, signed_dihedral)
                if transport_dot < DIRECTION_COMPATIBILITY_MIN_DOT:
                    continue
                normal_dot = _max_endpoint_normal_dot(
                    samples_by_evidence_id.get(first.id, ()),
                    samples_by_evidence_id.get(second.id, ()),
                    axis,
                    signed_dihedral,
                )
                normal_gate = normal_dot is not None and normal_dot >= SHARED_CHAIN_NORMAL_MIN_DOT
                if not normal_gate:
                    continue
                confidence = min(first.confidence, second.confidence, relation.confidence)
                candidates.append(_CrossingCandidate(
                    first_directional_evidence_id=first.id,
                    second_directional_evidence_id=second.id,
                    record=CrossingRecord(
                        kind="SHARED_CHAIN",
                        scaffold_node_id=None,
                        shared_chain_id=relation.chain_id,
                        patch_adjacency_id=relation.patch_adjacency_id,
                        first_directional_evidence_id=first.id,
                        second_directional_evidence_id=second.id,
                        first_patch_chain_id=first.patch_chain_id,
                        second_patch_chain_id=second.patch_chain_id,
                        first_patch_id=first.patch_id,
                        second_patch_id=second.patch_id,
                        signed_dihedral_radians=signed_dihedral,
                        transported_direction_dot=transport_dot,
                        transported_normal_dot=normal_dot,
                        confidence=confidence,
                    ),
                    confidence=confidence,
                ))
    return tuple(candidates)


def _same_patch_shared_chain_bridges(
    evidence_by_id: Mapping[str, PatchChainDirectionalEvidence],
    shared_chain_candidates: tuple[_CrossingCandidate, ...],
) -> tuple[_CrossingCandidate, ...]:
    shared_chain_ids_by_evidence_id: dict[str, set[str]] = {}
    for candidate in shared_chain_candidates:
        shared_chain_id = candidate.record.shared_chain_id
        if shared_chain_id is None:
            continue
        shared_chain_ids_by_evidence_id.setdefault(
            candidate.first_directional_evidence_id,
            set(),
        ).add(str(shared_chain_id))
        shared_chain_ids_by_evidence_id.setdefault(
            candidate.second_directional_evidence_id,
            set(),
        ).add(str(shared_chain_id))

    evidence_by_patch: dict[PatchId, list[PatchChainDirectionalEvidence]] = {}
    for evidence_id in shared_chain_ids_by_evidence_id:
        evidence = evidence_by_id[evidence_id]
        evidence_by_patch.setdefault(evidence.patch_id, []).append(evidence)

    candidates: list[_CrossingCandidate] = []
    for patch_id in sorted(evidence_by_patch, key=str):
        patch_evidence = tuple(sorted(evidence_by_patch[patch_id], key=lambda item: item.id))
        for first_index, first in enumerate(patch_evidence):
            for second in patch_evidence[first_index + 1:]:
                transport_dot = _transport_direction_dot(
                    first.direction,
                    second.direction,
                    (0.0, 0.0, 0.0),
                    0.0,
                )
                if transport_dot < DIRECTION_COMPATIBILITY_MIN_DOT:
                    continue
                confidence = min(first.confidence, second.confidence)
                candidates.append(_CrossingCandidate(
                    first_directional_evidence_id=first.id,
                    second_directional_evidence_id=second.id,
                    record=CrossingRecord(
                        kind="SAME_PATCH_SHARED_CHAIN_BRIDGE",
                        scaffold_node_id=None,
                        shared_chain_id=None,
                        patch_adjacency_id=None,
                        first_directional_evidence_id=first.id,
                        second_directional_evidence_id=second.id,
                        first_patch_chain_id=first.patch_chain_id,
                        second_patch_chain_id=second.patch_chain_id,
                        first_patch_id=patch_id,
                        second_patch_id=patch_id,
                        signed_dihedral_radians=0.0,
                        transported_direction_dot=transport_dot,
                        transported_normal_dot=None,
                        confidence=confidence,
                    ),
                    confidence=confidence,
                ))
    return tuple(candidates)


def _node_crossings(
    geometry: GeometryFactSnapshot,
    scaffold_nodes: tuple[ScaffoldNode, ...],
    scaffold_node_incident_edge_relations,
    sample_by_id: Mapping[str, PatchChainEndpointSample],
    sample_evidence_ids_by_sample_id: Mapping[str, tuple[str, ...]],
    evidence_by_id: Mapping[str, PatchChainDirectionalEvidence],
    edge_by_patch_chain_id: Mapping[PatchChainId, ScaffoldEdge],
    adjacency_by_patch_pair: Mapping[frozenset[PatchId], PatchAdjacency],
    self_seam_chain_ids: set[ChainId],
) -> tuple[_CrossingCandidate, ...]:
    node_ids = {node.id for node in scaffold_nodes}
    candidates: list[_CrossingCandidate] = []
    for relation in sorted(scaffold_node_incident_edge_relations, key=lambda item: item.id):
        if relation.scaffold_node_id not in node_ids:
            continue
        if relation.kind in {
            ScaffoldNodeIncidentEdgeRelationKind.MISSING_ENDPOINT_EVIDENCE,
            ScaffoldNodeIncidentEdgeRelationKind.DEGRADED,
        }:
            continue
        first_sample = sample_by_id.get(relation.first_endpoint_sample_id or "")
        second_sample = sample_by_id.get(relation.second_endpoint_sample_id or "")
        if first_sample is None or second_sample is None:
            continue
        if _is_degraded_sample(first_sample) or _is_degraded_sample(second_sample):
            continue
        for first_id in sample_evidence_ids_by_sample_id.get(first_sample.id, ()):
            for second_id in sample_evidence_ids_by_sample_id.get(second_sample.id, ()):
                if first_id == second_id:
                    continue
                first = evidence_by_id.get(first_id)
                second = evidence_by_id.get(second_id)
                if first is None or second is None:
                    continue
                first_edge = edge_by_patch_chain_id.get(first.patch_chain_id)
                second_edge = edge_by_patch_chain_id.get(second.patch_chain_id)
                if first_edge is None or second_edge is None:
                    continue
                if first_edge.chain_id in self_seam_chain_ids or second_edge.chain_id in self_seam_chain_ids:
                    continue
                if first_edge.chain_id == second_edge.chain_id:
                    continue
                adjacency = None
                axis = (0.0, 0.0, 0.0)
                signed_dihedral = 0.0
                if first.patch_id != second.patch_id:
                    adjacency = adjacency_by_patch_pair.get(frozenset((first.patch_id, second.patch_id)))
                    if adjacency is None:
                        continue
                    axis = _transport_axis(geometry, adjacency.chain_id, ())
                    signed_dihedral = _local_signed_dihedral_for_samples(
                        first_sample,
                        second_sample,
                        axis,
                    )
                    if signed_dihedral is None:
                        signed_dihedral = _signed_dihedral_for_patch_order(
                            adjacency,
                            first.patch_id,
                            second.patch_id,
                        )
                first_direction = _endpoint_local_direction(geometry, first, first_sample.endpoint_role)
                second_direction = _endpoint_local_direction(geometry, second, second_sample.endpoint_role)
                transport_dot = _transport_direction_dot(first_direction, second_direction, axis, signed_dihedral)
                if transport_dot < DIRECTION_COMPATIBILITY_MIN_DOT:
                    continue
                confidence = min(first.confidence, second.confidence, first_sample.confidence, second_sample.confidence)
                candidates.append(_CrossingCandidate(
                    first_directional_evidence_id=first.id,
                    second_directional_evidence_id=second.id,
                    record=CrossingRecord(
                        kind="SCAFFOLD_NODE",
                        scaffold_node_id=relation.scaffold_node_id,
                        shared_chain_id=adjacency.chain_id if adjacency is not None else None,
                        patch_adjacency_id=adjacency.id if adjacency is not None else None,
                        first_directional_evidence_id=first.id,
                        second_directional_evidence_id=second.id,
                        first_patch_chain_id=first.patch_chain_id,
                        second_patch_chain_id=second.patch_chain_id,
                        first_patch_id=first.patch_id,
                        second_patch_id=second.patch_id,
                        signed_dihedral_radians=signed_dihedral,
                        transported_direction_dot=transport_dot,
                        transported_normal_dot=None,
                        confidence=confidence,
                    ),
                    confidence=confidence,
                ))
    return tuple(_deduplicate_crossings(candidates))


def _evidence_by_patch_chain(
    directional_evidence_items: tuple[PatchChainDirectionalEvidence, ...],
) -> dict[PatchChainId, tuple[PatchChainDirectionalEvidence, ...]]:
    items: dict[PatchChainId, list[PatchChainDirectionalEvidence]] = {}
    for item in directional_evidence_items:
        items.setdefault(item.patch_chain_id, []).append(item)
    return {
        patch_chain_id: tuple(sorted(values, key=lambda item: item.id))
        for patch_chain_id, values in items.items()
    }


def _sample_evidence_ids_by_sample_id(
    endpoint_samples: tuple[PatchChainEndpointSample, ...],
    evidence_by_id: Mapping[str, PatchChainDirectionalEvidence],
    evidence_by_patch_chain: Mapping[PatchChainId, tuple[PatchChainDirectionalEvidence, ...]],
) -> dict[str, tuple[str, ...]]:
    sample_evidence_ids: dict[str, tuple[str, ...]] = {}
    for sample in endpoint_samples:
        if sample.directional_evidence_id in evidence_by_id:
            sample_evidence_ids[sample.id] = (sample.directional_evidence_id,)
            continue
        source_edge_id = _sample_source_edge_id(sample)
        segment_index = _sample_segment_index(sample)
        candidates = tuple(
            item.id
            for item in evidence_by_patch_chain.get(sample.patch_chain_id, ())
            if (
                source_edge_id is not None
                and source_edge_id in {str(edge_id) for edge_id in item.source_edge_ids}
            )
            or (
                segment_index is not None
                and segment_index in item.segment_indices
            )
        )
        sample_evidence_ids[sample.id] = tuple(sorted(candidates))
    return sample_evidence_ids


def _samples_by_evidence_id(
    endpoint_samples: tuple[PatchChainEndpointSample, ...],
    sample_evidence_ids_by_sample_id: Mapping[str, tuple[str, ...]],
) -> dict[str, tuple[PatchChainEndpointSample, ...]]:
    samples: dict[str, list[PatchChainEndpointSample]] = {}
    for sample in endpoint_samples:
        for evidence_id in sample_evidence_ids_by_sample_id.get(sample.id, ()):
            samples.setdefault(evidence_id, []).append(sample)
    return {
        evidence_id: tuple(sorted(values, key=lambda item: item.id))
        for evidence_id, values in samples.items()
    }


def _sample_source_edge_id(sample: PatchChainEndpointSample) -> str | None:
    if not sample.evidence:
        return None
    value = sample.evidence[0].data.get("source_edge_id")
    return str(value) if value is not None else None


def _sample_segment_index(sample: PatchChainEndpointSample) -> int | None:
    if not sample.evidence:
        return None
    value = sample.evidence[0].data.get("segment_index")
    return int(value) if isinstance(value, int) else None


def _adjacency_by_patch_pair(
    patch_adjacencies: Mapping[str, PatchAdjacency],
) -> dict[frozenset[PatchId], PatchAdjacency]:
    return {
        frozenset((adjacency.first_patch_id, adjacency.second_patch_id)): adjacency
        for adjacency in patch_adjacencies.values()
    }


def _transport_axis(
    geometry: GeometryFactSnapshot,
    chain_id,
    fallback_vectors: tuple[Vector3, ...],
) -> Vector3:
    chain_facts = geometry.chain_facts.get(chain_id)
    if chain_facts is not None:
        if length(chain_facts.chord_direction) > EPSILON:
            return chain_facts.chord_direction
        for segment in chain_facts.segments:
            if length(segment.direction) > EPSILON:
                return segment.direction
    for vector in fallback_vectors:
        if length(vector) > EPSILON:
            return normalize(vector)
    return (0.0, 0.0, 0.0)


def _signed_dihedral_for_patch_order(
    adjacency: PatchAdjacency | None,
    first_patch_id: PatchId,
    second_patch_id: PatchId,
) -> float:
    if adjacency is None:
        return 0.0
    if (
        adjacency.first_patch_id == first_patch_id
        and adjacency.second_patch_id == second_patch_id
    ):
        return adjacency.signed_angle_radians
    if (
        adjacency.first_patch_id == second_patch_id
        and adjacency.second_patch_id == first_patch_id
    ):
        return -adjacency.signed_angle_radians
    return adjacency.signed_angle_radians


def _local_signed_dihedral_for_samples(
    first_sample: PatchChainEndpointSample,
    second_sample: PatchChainEndpointSample,
    axis: Vector3,
) -> float | None:
    if (
        length(axis) <= EPSILON
        or length(first_sample.owner_normal) <= EPSILON
        or length(second_sample.owner_normal) <= EPSILON
    ):
        return None
    normalized_axis = normalize(axis)
    first_normal = normalize(first_sample.owner_normal)
    second_normal = normalize(second_sample.owner_normal)
    return atan2(
        dot(normalized_axis, cross(first_normal, second_normal)),
        dot(first_normal, second_normal),
    )


def _endpoint_local_direction(
    geometry: GeometryFactSnapshot,
    evidence: PatchChainDirectionalEvidence,
    role: PatchChainEndpointRole,
) -> Vector3:
    chain_facts = geometry.chain_facts.get(evidence.parent_chain_id)
    if chain_facts is None:
        return evidence.direction
    segments_by_index = {
        segment.segment_index: segment
        for segment in chain_facts.segments
    }
    source_vertex_id = (
        evidence.start_source_vertex_id
        if role is PatchChainEndpointRole.START
        else evidence.end_source_vertex_id
    )
    for segment_index in evidence.segment_indices:
        segment = segments_by_index.get(segment_index)
        if segment is None:
            continue
        if segment.start_source_vertex_id == source_vertex_id and length(segment.direction) > EPSILON:
            return segment.direction
        if segment.end_source_vertex_id == source_vertex_id and length(segment.direction) > EPSILON:
            return scale(segment.direction, -1.0)
    return evidence.direction


def _transport_direction_dot(
    first_direction: Vector3,
    second_direction: Vector3,
    axis: Vector3,
    signed_dihedral: float,
) -> float:
    transported = _rotate_around_axis(first_direction, axis, signed_dihedral)
    return abs(dot(normalize(transported), normalize(second_direction)))


def _rotate_around_axis(vector: Vector3, axis: Vector3, angle: float) -> Vector3:
    axis = normalize(axis)
    if length(axis) <= EPSILON:
        return vector
    return add(
        add(
            scale(vector, cos(angle)),
            scale(cross(axis, vector), sin(angle)),
        ),
        scale(axis, dot(axis, vector) * (1.0 - cos(angle))),
    )


def _max_endpoint_normal_dot(
    first_samples: tuple[PatchChainEndpointSample, ...],
    second_samples: tuple[PatchChainEndpointSample, ...],
    axis: Vector3,
    signed_dihedral: float,
) -> float | None:
    normal_dots = [
        dot(
            normalize(_rotate_around_axis(first.owner_normal, axis, signed_dihedral)),
            normalize(second.owner_normal),
        )
        for first in first_samples
        for second in second_samples
        if first.vertex_id == second.vertex_id
        and not _is_degraded_sample(first)
        and not _is_degraded_sample(second)
        and length(first.owner_normal) > EPSILON
        and length(second.owner_normal) > EPSILON
    ]
    return max(normal_dots) if normal_dots else None


def _is_degraded_sample(sample: PatchChainEndpointSample) -> bool:
    return sample.confidence <= 0.0 or length(sample.tangent_away_from_vertex) <= EPSILON


def _deduplicate_crossings(
    candidates: list[_CrossingCandidate],
) -> tuple[_CrossingCandidate, ...]:
    seen: set[tuple[str, str, str, str, str, str]] = set()
    unique: list[_CrossingCandidate] = []
    for candidate in sorted(
        candidates,
        key=lambda item: (
            min(item.first_directional_evidence_id, item.second_directional_evidence_id),
            max(item.first_directional_evidence_id, item.second_directional_evidence_id),
            item.record.kind,
            item.record.scaffold_node_id or "",
            item.record.run_endpoint_junction_id or "",
            str(item.record.shared_chain_id or ""),
        ),
    ):
        key = (
            min(candidate.first_directional_evidence_id, candidate.second_directional_evidence_id),
            max(candidate.first_directional_evidence_id, candidate.second_directional_evidence_id),
            candidate.record.kind,
            candidate.record.scaffold_node_id or "",
            candidate.record.run_endpoint_junction_id or "",
            str(candidate.record.shared_chain_id or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return tuple(unique)


def _connected_components(
    evidence_by_id: Mapping[str, PatchChainDirectionalEvidence],
    crossing_candidates: tuple[_CrossingCandidate, ...],
) -> dict[str, tuple[str, ...]]:
    parents = {evidence_id: evidence_id for evidence_id in evidence_by_id}

    def find(evidence_id: str) -> str:
        while parents[evidence_id] != evidence_id:
            parents[evidence_id] = parents[parents[evidence_id]]
            evidence_id = parents[evidence_id]
        return evidence_id

    def union(first_id: str, second_id: str) -> None:
        first_root = find(first_id)
        second_root = find(second_id)
        if first_root == second_root:
            return
        if first_root < second_root:
            parents[second_root] = first_root
        else:
            parents[first_root] = second_root

    for crossing in crossing_candidates:
        union(crossing.first_directional_evidence_id, crossing.second_directional_evidence_id)

    components: dict[str, list[str]] = {}
    for evidence_id in sorted(evidence_by_id):
        components.setdefault(find(evidence_id), []).append(evidence_id)
    return {
        root: tuple(member_ids)
        for root, member_ids in components.items()
    }


def _crossings_by_component(
    components: Mapping[str, tuple[str, ...]],
    crossing_candidates: tuple[_CrossingCandidate, ...],
) -> dict[tuple[str, ...], tuple[CrossingRecord, ...]]:
    component_by_member_id = {
        member_id: tuple(member_ids)
        for member_ids in components.values()
        for member_id in member_ids
    }
    crossings: dict[tuple[str, ...], list[CrossingRecord]] = {}
    for candidate in crossing_candidates:
        first_component = component_by_member_id[candidate.first_directional_evidence_id]
        second_component = component_by_member_id[candidate.second_directional_evidence_id]
        if first_component != second_component:
            continue
        crossings.setdefault(first_component, []).append(candidate.record)
    return {
        member_ids: tuple(records)
        for member_ids, records in crossings.items()
    }


def _ordered_members_and_branches(
    member_ids: tuple[str, ...],
    crossings: tuple[CrossingRecord, ...],
) -> tuple[tuple[str, ...], Mapping[str, tuple[str, ...]]]:
    graph: dict[str, set[str]] = {member_id: set() for member_id in member_ids}
    member_set = set(member_ids)
    for crossing in crossings:
        first_id = crossing.first_directional_evidence_id
        second_id = crossing.second_directional_evidence_id
        if first_id not in member_set or second_id not in member_set:
            continue
        graph[first_id].add(second_id)
        graph[second_id].add(first_id)

    branch_records = {
        member_id: tuple(sorted(neighbor_ids))
        for member_id, neighbor_ids in sorted(graph.items())
        if len(neighbor_ids) > 2
    }
    if not crossings:
        return member_ids, branch_records

    ordered: list[str] = []
    visited: set[str] = set()
    start_candidates = sorted(member_id for member_id, neighbors in graph.items() if len(neighbors) <= 1)
    start_candidates.extend(member_id for member_id in sorted(member_ids) if member_id not in start_candidates)
    for start_id in start_candidates:
        if start_id in visited:
            continue
        stack = [start_id]
        while stack:
            member_id = stack.pop()
            if member_id in visited:
                continue
            visited.add(member_id)
            ordered.append(member_id)
            stack.extend(sorted(graph[member_id] - visited, reverse=True))
    ordered.extend(member_id for member_id in member_ids if member_id not in visited)
    return tuple(ordered), branch_records


def _family_member_map(
    member_ids: tuple[str, ...],
    evidence_by_id: Mapping[str, PatchChainDirectionalEvidence],
    edge_by_patch_chain_id: Mapping[PatchChainId, ScaffoldEdge],
    samples_by_evidence_id: Mapping[str, tuple[PatchChainEndpointSample, ...]],
) -> Mapping[str, tuple[PatchChainId, str | None, VertexId | None, VertexId | None]]:
    member_map: dict[str, tuple[PatchChainId, str | None, VertexId | None, VertexId | None]] = {}
    for member_id in member_ids:
        evidence = evidence_by_id[member_id]
        edge = edge_by_patch_chain_id.get(evidence.patch_chain_id)
        samples = samples_by_evidence_id.get(member_id, ())
        member_map[member_id] = (
            evidence.patch_chain_id,
            edge.id if edge is not None else None,
            _sample_vertex_id(samples, PatchChainEndpointRole.START),
            _sample_vertex_id(samples, PatchChainEndpointRole.END),
        )
    return member_map


def _sample_vertex_id(
    samples: tuple[PatchChainEndpointSample, ...],
    role: PatchChainEndpointRole,
) -> VertexId | None:
    role_samples = tuple(sample for sample in samples if sample.endpoint_role is role)
    if not role_samples:
        return None
    return sorted(role_samples, key=lambda item: item.id)[0].vertex_id


def _family_evidence(
    member_ids: tuple[str, ...],
    crossings: tuple[CrossingRecord, ...],
    confidence: float,
) -> Evidence:
    return Evidence(
        source="layer_3_relations.direction_families",
        summary="ConnectedDirectionFamily v1 propagated over graph and geodesic in-patch crossings",
        data={
            "policy": POLICY_NAME,
            "member_count": len(member_ids),
            "crossing_count": len(crossings),
            "direction_compatibility_min_dot": DIRECTION_COMPATIBILITY_MIN_DOT,
            "geodesic_straight_tolerance": GEODESIC_STRAIGHT_TOLERANCE,
            "compatible_normal_min_dot": COMPATIBLE_NORMAL_MIN_DOT,
            "shared_chain_normal_min_dot": SHARED_CHAIN_NORMAL_MIN_DOT,
            "confidence": confidence,
        },
    )
