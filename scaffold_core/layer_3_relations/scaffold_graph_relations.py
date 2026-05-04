"""
Layer: 3 - Relations

Rules:
- Build evidence relations over existing ScaffoldNode and ScaffoldEdge records.
- Use final PatchChains and implemented endpoint/adjacency evidence only.
- Do not mutate Layer 1 topology or graph identity.
- Do not build traces, circuits, rails, feature, runtime, solve or UV data.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from dataclasses import dataclass
from typing import Mapping

from scaffold_core.core.evidence import Evidence
from scaffold_core.ids import BoundaryLoopId, ChainId, PatchChainId, PatchId, VertexId
from scaffold_core.layer_2_geometry.measures import EPSILON, dot, length, normalize
from scaffold_core.layer_3_relations.model import (
    EndpointDirectionRelationKind,
    OwnerNormalSource,
    PatchAdjacency,
    PatchChainEndpointRelation,
    PatchChainEndpointRole,
    PatchChainEndpointSample,
    LoopCorner,
    ScaffoldEdge,
    ScaffoldNode,
    ScaffoldNodeIncidentEdgeRelation,
    ScaffoldNodeIncidentEdgeRelationKind,
    SideSurfaceContinuityEvidence,
    SharedChainPatchChainRelation,
    SharedChainPatchChainRelationKind,
)


NODE_INCIDENT_EDGE_POLICY_NAME = "scaffold_node_incident_edge_relation_v1"
SIDE_SURFACE_CONTINUITY_POLICY_NAME = "side_surface_continuity_evidence_v0"
SHARED_CHAIN_POLICY_NAME = "shared_chain_patch_chain_relation_v0"
OPPOSITE_COLLINEAR_MAX_DOT = -0.996
SAME_RAY_COLLINEAR_MIN_DOT = 0.996
ORTHOGONAL_MAX_ABS_DOT = 0.2
COMPATIBLE_NORMAL_MIN_DOT = 0.7
DIVERGENT_NORMAL_MAX_DOT = 0.25
SLIDING_BASE_KINDS = frozenset({
    ScaffoldNodeIncidentEdgeRelationKind.ORTHOGONAL_CORNER,
    ScaffoldNodeIncidentEdgeRelationKind.SAME_RAY_AMBIGUOUS,
})


@dataclass(frozen=True)
class _IncidentEdgeOccurrence:
    scaffold_node_id: str
    scaffold_edge: ScaffoldEdge
    endpoint_role: PatchChainEndpointRole
    endpoint_sample: PatchChainEndpointSample | None


def build_scaffold_graph_relations(
    scaffold_nodes: tuple[ScaffoldNode, ...],
    scaffold_edges: tuple[ScaffoldEdge, ...],
    endpoint_samples: tuple[PatchChainEndpointSample, ...],
    endpoint_relations: tuple[PatchChainEndpointRelation, ...],
    patch_adjacencies: Mapping[str, PatchAdjacency],
    loop_corners: tuple[LoopCorner, ...] = (),
) -> tuple[
    tuple[SideSurfaceContinuityEvidence, ...],
    tuple[ScaffoldNodeIncidentEdgeRelation, ...],
    tuple[SharedChainPatchChainRelation, ...],
]:
    """Build node-local edge-pair and cross-patch shared Chain relations."""

    edge_by_patch_chain_id = {
        edge.patch_chain_id: edge
        for edge in scaffold_edges
    }
    samples_by_patch_chain_and_role = _samples_by_patch_chain_and_role(endpoint_samples)
    relation_by_sample_pair = _relation_by_sample_pair(endpoint_relations)
    occurrences_by_node_id = _occurrences_by_node_id(
        scaffold_nodes,
        edge_by_patch_chain_id,
        samples_by_patch_chain_and_role,
    )
    side_surface_evidence = build_side_surface_continuity_evidence(
        scaffold_nodes,
        occurrences_by_node_id,
        relation_by_sample_pair,
        loop_corners,
    )
    incident_edge_relations = build_scaffold_node_incident_edge_relations(
        scaffold_nodes,
        occurrences_by_node_id,
        relation_by_sample_pair,
        side_surface_evidence,
    )
    shared_chain_relations = build_shared_chain_patch_chain_relations(
        scaffold_edges,
        patch_adjacencies,
    )
    return side_surface_evidence, incident_edge_relations, shared_chain_relations


def build_side_surface_continuity_evidence(
    scaffold_nodes: tuple[ScaffoldNode, ...],
    occurrences_by_node_id: Mapping[str, tuple[_IncidentEdgeOccurrence, ...]],
    relation_by_sample_pair: Mapping[tuple[str, str], PatchChainEndpointRelation],
    loop_corners: tuple[LoopCorner, ...],
) -> tuple[SideSurfaceContinuityEvidence, ...]:
    """Build explicit same-side surface evidence before incident classification."""

    loop_corner_by_ordered_pair = _loop_corner_by_ordered_pair(loop_corners)
    records: list[SideSurfaceContinuityEvidence] = []
    for node in sorted(scaffold_nodes, key=lambda item: item.id):
        occurrences = tuple(sorted(
            occurrences_by_node_id.get(node.id, ()),
            key=_occurrence_sort_key,
        ))
        for first, second in combinations(occurrences, 2):
            endpoint_relation = _endpoint_relation_for_occurrences(
                first,
                second,
                relation_by_sample_pair,
            )
            record = _side_surface_continuity_evidence(
                node,
                first,
                second,
                endpoint_relation,
                loop_corner_by_ordered_pair,
            )
            if record is not None:
                records.append(record)
    return tuple(records)


def build_scaffold_node_incident_edge_relations(
    scaffold_nodes: tuple[ScaffoldNode, ...],
    occurrences_by_node_id: Mapping[str, tuple[_IncidentEdgeOccurrence, ...]],
    relation_by_sample_pair: Mapping[tuple[str, str], PatchChainEndpointRelation],
    side_surface_evidence: tuple[SideSurfaceContinuityEvidence, ...],
) -> tuple[ScaffoldNodeIncidentEdgeRelation, ...]:
    """Build complete node-local pair relations over edge endpoint occurrences."""

    side_surface_evidence_by_pair = _side_surface_evidence_by_pair(side_surface_evidence)
    relations: list[ScaffoldNodeIncidentEdgeRelation] = []
    for node in sorted(scaffold_nodes, key=lambda item: item.id):
        occurrences = tuple(sorted(
            occurrences_by_node_id.get(node.id, ()),
            key=_occurrence_sort_key,
        ))
        for first, second in combinations(occurrences, 2):
            endpoint_relation = _endpoint_relation_for_occurrences(
                first,
                second,
                relation_by_sample_pair,
            )
            relations.append(_incident_edge_relation(
                node,
                first,
                second,
                endpoint_relation,
                side_surface_evidence_by_pair.get(_node_occurrence_pair_key(node.id, first, second)),
                occurrences,
            ))
    return tuple(relations)


def build_shared_chain_patch_chain_relations(
    scaffold_edges: tuple[ScaffoldEdge, ...],
    patch_adjacencies: Mapping[str, PatchAdjacency],
) -> tuple[SharedChainPatchChainRelation, ...]:
    """Build cross-patch relation records for ScaffoldEdges sharing one Chain."""

    edges_by_chain_id: dict[ChainId, list[ScaffoldEdge]] = defaultdict(list)
    for edge in scaffold_edges:
        edges_by_chain_id[edge.chain_id].append(edge)

    adjacency_id_by_chain_and_patch_pair = _adjacency_id_by_chain_and_patch_pair(patch_adjacencies)
    relations: list[SharedChainPatchChainRelation] = []
    for chain_id in sorted(edges_by_chain_id, key=str):
        chain_edges = tuple(sorted(edges_by_chain_id[chain_id], key=lambda edge: edge.id))
        if len(chain_edges) != 2:
            continue
        for first_edge, second_edge in combinations(chain_edges, 2):
            if first_edge.patch_id == second_edge.patch_id:
                continue
            patch_pair = _patch_pair(first_edge.patch_id, second_edge.patch_id)
            relations.append(
                _shared_chain_relation(
                    first_edge,
                    second_edge,
                    adjacency_id_by_chain_and_patch_pair.get((chain_id, patch_pair)),
                )
            )
    return tuple(relations)


def _samples_by_patch_chain_and_role(
    endpoint_samples: tuple[PatchChainEndpointSample, ...],
) -> dict[tuple[PatchChainId, PatchChainEndpointRole], tuple[PatchChainEndpointSample, ...]]:
    samples: dict[tuple[PatchChainId, PatchChainEndpointRole], list[PatchChainEndpointSample]] = {}
    for sample in sorted(endpoint_samples, key=lambda item: item.id):
        samples.setdefault((sample.patch_chain_id, sample.endpoint_role), []).append(sample)
    return {
        key: tuple(value)
        for key, value in samples.items()
    }


def _relation_by_sample_pair(
    endpoint_relations: tuple[PatchChainEndpointRelation, ...],
) -> dict[tuple[str, str], PatchChainEndpointRelation]:
    return {
        _sample_pair_key(relation.first_sample_id, relation.second_sample_id): relation
        for relation in endpoint_relations
    }


def _occurrences_by_node_id(
    scaffold_nodes: tuple[ScaffoldNode, ...],
    edge_by_patch_chain_id: Mapping[PatchChainId, ScaffoldEdge],
    samples_by_patch_chain_and_role: Mapping[
        tuple[PatchChainId, PatchChainEndpointRole],
        tuple[PatchChainEndpointSample, ...],
    ],
) -> dict[str, tuple[_IncidentEdgeOccurrence, ...]]:
    node_by_id = {
        node.id: node
        for node in scaffold_nodes
    }
    occurrences_by_node_id: dict[str, list[_IncidentEdgeOccurrence]] = defaultdict(list)
    for edge in sorted(edge_by_patch_chain_id.values(), key=lambda item: item.id):
        for node_id, endpoint_role in (
            (edge.start_scaffold_node_id, PatchChainEndpointRole.START),
            (edge.end_scaffold_node_id, PatchChainEndpointRole.END),
        ):
            node = node_by_id.get(node_id)
            if node is None:
                continue
            occurrences_by_node_id[node_id].append(
                _IncidentEdgeOccurrence(
                    scaffold_node_id=node_id,
                    scaffold_edge=edge,
                    endpoint_role=endpoint_role,
                    endpoint_sample=_sample_for_node_occurrence(
                        node,
                        samples_by_patch_chain_and_role.get((edge.patch_chain_id, endpoint_role), ()),
                    ),
                )
            )
    return {
        node_id: tuple(occurrences)
        for node_id, occurrences in occurrences_by_node_id.items()
    }


def _sample_for_node_occurrence(
    node: ScaffoldNode,
    samples: tuple[PatchChainEndpointSample, ...],
) -> PatchChainEndpointSample | None:
    node_vertex_ids = frozenset(node.vertex_ids)
    node_samples = tuple(
        sample
        for sample in samples
        if sample.vertex_id in node_vertex_ids
    )
    if not node_samples:
        return None
    return sorted(node_samples, key=lambda item: item.id)[0]


def _occurrence_sort_key(
    occurrence: _IncidentEdgeOccurrence,
) -> tuple[str, str, str, str]:
    return (
        occurrence.endpoint_role.value,
        occurrence.scaffold_edge.id,
        str(occurrence.scaffold_edge.patch_chain_id),
        occurrence.endpoint_sample.id if occurrence.endpoint_sample is not None else "",
    )


def _sample_pair_key(first_sample_id: str, second_sample_id: str) -> tuple[str, str]:
    return tuple(sorted((first_sample_id, second_sample_id)))


def _endpoint_relation_for_occurrences(
    first: _IncidentEdgeOccurrence,
    second: _IncidentEdgeOccurrence,
    relation_by_sample_pair: Mapping[tuple[str, str], PatchChainEndpointRelation],
) -> PatchChainEndpointRelation | None:
    if first.endpoint_sample is None or second.endpoint_sample is None:
        return None
    return relation_by_sample_pair.get(
        _sample_pair_key(first.endpoint_sample.id, second.endpoint_sample.id)
    )


def _incident_edge_relation(
    node: ScaffoldNode,
    first: _IncidentEdgeOccurrence,
    second: _IncidentEdgeOccurrence,
    endpoint_relation: PatchChainEndpointRelation | None,
    side_surface_evidence: SideSurfaceContinuityEvidence | None,
    node_occurrences: tuple[_IncidentEdgeOccurrence, ...],
) -> ScaffoldNodeIncidentEdgeRelation:
    first_edge = first.scaffold_edge
    second_edge = second.scaffold_edge
    direction_dot, normal_dot = _dot_values(first, second, endpoint_relation)
    base_kind = _incident_edge_kind(first, second, endpoint_relation, direction_dot, normal_dot)
    recurrence_evidence_present = _has_recurrent_previous_chain(first, second, node_occurrences)
    should_promote_sliding = _should_promote_surface_sliding(
        first,
        second,
        node_occurrences,
        base_kind,
        side_surface_evidence,
    )
    kind = (
        ScaffoldNodeIncidentEdgeRelationKind.SURFACE_SLIDING_CONTINUATION_CANDIDATE
        if should_promote_sliding
        else base_kind
    )
    confidence = _incident_edge_confidence(node, first, second, endpoint_relation, kind)
    return ScaffoldNodeIncidentEdgeRelation(
        id=(
            "scaffold_node_incident_edge_relation:"
            f"{node.id}:{_occurrence_id(first)}:{_occurrence_id(second)}"
        ),
        kind=kind,
        policy=NODE_INCIDENT_EDGE_POLICY_NAME,
        scaffold_node_id=node.id,
        first_scaffold_edge_id=first_edge.id,
        second_scaffold_edge_id=second_edge.id,
        first_patch_chain_id=first_edge.patch_chain_id,
        second_patch_chain_id=second_edge.patch_chain_id,
        first_endpoint_role=first.endpoint_role,
        second_endpoint_role=second.endpoint_role,
        first_endpoint_sample_id=first.endpoint_sample.id if first.endpoint_sample is not None else None,
        second_endpoint_sample_id=second.endpoint_sample.id if second.endpoint_sample is not None else None,
        patch_chain_endpoint_relation_id=endpoint_relation.id if endpoint_relation is not None else None,
        direction_dot=direction_dot,
        normal_dot=normal_dot,
        confidence=confidence,
        evidence=(_incident_edge_evidence(
            node,
            first,
            second,
            endpoint_relation,
            kind,
            confidence,
            base_kind,
            side_surface_evidence if should_promote_sliding else None,
            recurrence_evidence_present,
        ),),
    )


def _incident_edge_kind(
    first: _IncidentEdgeOccurrence,
    second: _IncidentEdgeOccurrence,
    endpoint_relation: PatchChainEndpointRelation | None,
    direction_dot: float | None,
    normal_dot: float | None,
) -> ScaffoldNodeIncidentEdgeRelationKind:
    if first.endpoint_sample is None or second.endpoint_sample is None:
        return ScaffoldNodeIncidentEdgeRelationKind.MISSING_ENDPOINT_EVIDENCE
    if (
        direction_dot is None
        or _is_degraded_sample(first.endpoint_sample)
        or _is_degraded_sample(second.endpoint_sample)
        or (
            endpoint_relation is not None
            and endpoint_relation.direction_relation is EndpointDirectionRelationKind.DEGENERATE
        )
    ):
        return ScaffoldNodeIncidentEdgeRelationKind.DEGRADED
    if direction_dot >= SAME_RAY_COLLINEAR_MIN_DOT:
        return ScaffoldNodeIncidentEdgeRelationKind.SAME_RAY_AMBIGUOUS
    has_strong_normal_evidence = _has_strong_normal_evidence(
        first.endpoint_sample,
        second.endpoint_sample,
        normal_dot,
    )
    if direction_dot <= OPPOSITE_COLLINEAR_MAX_DOT:
        if (
            has_strong_normal_evidence
            and normal_dot is not None
            and normal_dot <= DIVERGENT_NORMAL_MAX_DOT
        ):
            return ScaffoldNodeIncidentEdgeRelationKind.CROSS_SURFACE_CONNECTOR
        if (
            has_strong_normal_evidence
            and normal_dot is not None
            and normal_dot >= COMPATIBLE_NORMAL_MIN_DOT
        ):
            return ScaffoldNodeIncidentEdgeRelationKind.SURFACE_CONTINUATION_CANDIDATE
        return ScaffoldNodeIncidentEdgeRelationKind.STRAIGHT_CONTINUATION_CANDIDATE
    if abs(direction_dot) <= ORTHOGONAL_MAX_ABS_DOT:
        return ScaffoldNodeIncidentEdgeRelationKind.ORTHOGONAL_CORNER
    if has_strong_normal_evidence and normal_dot is not None and normal_dot <= DIVERGENT_NORMAL_MAX_DOT:
        return ScaffoldNodeIncidentEdgeRelationKind.CROSS_SURFACE_CONNECTOR
    return ScaffoldNodeIncidentEdgeRelationKind.OBLIQUE_CONNECTOR


def _dot_values(
    first: _IncidentEdgeOccurrence,
    second: _IncidentEdgeOccurrence,
    endpoint_relation: PatchChainEndpointRelation | None,
) -> tuple[float | None, float | None]:
    if endpoint_relation is not None:
        return endpoint_relation.direction_dot, endpoint_relation.normal_dot
    if first.endpoint_sample is None or second.endpoint_sample is None:
        return None, None
    first_tangent = normalize(first.endpoint_sample.tangent_away_from_vertex)
    second_tangent = normalize(second.endpoint_sample.tangent_away_from_vertex)
    first_normal = normalize(first.endpoint_sample.owner_normal)
    second_normal = normalize(second.endpoint_sample.owner_normal)
    if length(first_tangent) <= EPSILON or length(second_tangent) <= EPSILON:
        return None, None
    direction_dot = dot(first_tangent, second_tangent)
    normal_dot = (
        dot(first_normal, second_normal)
        if length(first_normal) > EPSILON and length(second_normal) > EPSILON
        else None
    )
    return direction_dot, normal_dot


def _is_degraded_sample(sample: PatchChainEndpointSample) -> bool:
    return (
        sample.confidence <= 0.0
        or length(sample.tangent_away_from_vertex) <= EPSILON
    )


def _has_strong_normal_evidence(
    first: PatchChainEndpointSample,
    second: PatchChainEndpointSample,
    normal_dot: float | None,
) -> bool:
    return (
        normal_dot is not None
        and first.owner_normal_source is not OwnerNormalSource.UNKNOWN
        and second.owner_normal_source is not OwnerNormalSource.UNKNOWN
        and length(first.owner_normal) > EPSILON
        and length(second.owner_normal) > EPSILON
        and first.confidence > 0.0
        and second.confidence > 0.0
    )


def _should_promote_surface_sliding(
    first: _IncidentEdgeOccurrence,
    second: _IncidentEdgeOccurrence,
    node_occurrences: tuple[_IncidentEdgeOccurrence, ...],
    base_kind: ScaffoldNodeIncidentEdgeRelationKind,
    side_surface_evidence: SideSurfaceContinuityEvidence | None,
) -> bool:
    if side_surface_evidence is None or base_kind not in SLIDING_BASE_KINDS:
        return False
    return True


def _side_surface_continuity_evidence(
    node: ScaffoldNode,
    first: _IncidentEdgeOccurrence,
    second: _IncidentEdgeOccurrence,
    endpoint_relation: PatchChainEndpointRelation | None,
    loop_corner_by_ordered_pair: Mapping[
        tuple[PatchId, BoundaryLoopId, VertexId, PatchChainId, PatchChainId],
        LoopCorner,
    ],
) -> SideSurfaceContinuityEvidence | None:
    if first.endpoint_sample is None or second.endpoint_sample is None:
        return None
    _, normal_dot = _dot_values(first, second, endpoint_relation)
    if first.scaffold_edge.patch_id != second.scaffold_edge.patch_id:
        return None
    if first.scaffold_edge.loop_id != second.scaffold_edge.loop_id:
        return None
    if first.scaffold_edge.chain_id == second.scaffold_edge.chain_id:
        return None
    if first.endpoint_role is not PatchChainEndpointRole.END:
        return None
    if second.endpoint_role is not PatchChainEndpointRole.START:
        return None
    if first.endpoint_sample.vertex_id != second.endpoint_sample.vertex_id:
        return None
    loop_corner = loop_corner_by_ordered_pair.get(
        _loop_corner_pair_key(
            first.scaffold_edge.patch_id,
            first.scaffold_edge.loop_id,
            first.endpoint_sample.vertex_id,
            first.scaffold_edge.patch_chain_id,
            second.scaffold_edge.patch_chain_id,
        )
    )
    if loop_corner is None:
        return None
    if (
        first.endpoint_sample.owner_normal_source
        is not OwnerNormalSource.LOCAL_FACE_FAN_NORMAL
        or second.endpoint_sample.owner_normal_source
        is not OwnerNormalSource.LOCAL_FACE_FAN_NORMAL
    ):
        return None
    if not _has_strong_normal_evidence(first.endpoint_sample, second.endpoint_sample, normal_dot):
        return None
    if normal_dot is None or normal_dot < COMPATIBLE_NORMAL_MIN_DOT:
        return None
    if _is_degraded_sample(first.endpoint_sample) or _is_degraded_sample(second.endpoint_sample):
        return None
    if (
        endpoint_relation is not None
        and endpoint_relation.direction_relation is EndpointDirectionRelationKind.DEGENERATE
    ):
        return None
    confidence_values = [
        node.confidence,
        first.scaffold_edge.confidence,
        second.scaffold_edge.confidence,
        first.endpoint_sample.confidence,
        second.endpoint_sample.confidence,
    ]
    if endpoint_relation is not None:
        confidence_values.append(endpoint_relation.confidence)
    confidence = min(confidence_values)
    evidence_id = (
        "side_surface_continuity_evidence:"
        f"{node.id}:{_occurrence_id(first)}:{_occurrence_id(second)}"
    )
    return SideSurfaceContinuityEvidence(
        id=evidence_id,
        scaffold_node_id=node.id,
        first_scaffold_edge_id=first.scaffold_edge.id,
        second_scaffold_edge_id=second.scaffold_edge.id,
        first_patch_chain_id=first.scaffold_edge.patch_chain_id,
        second_patch_chain_id=second.scaffold_edge.patch_chain_id,
        first_endpoint_role=first.endpoint_role,
        second_endpoint_role=second.endpoint_role,
        patch_id=first.scaffold_edge.patch_id,
        loop_id=first.scaffold_edge.loop_id,
        first_chain_id=first.scaffold_edge.chain_id,
        second_chain_id=second.scaffold_edge.chain_id,
        vertex_id=first.endpoint_sample.vertex_id,
        source_vertex_ids=tuple(sorted(node.source_vertex_ids, key=str)),
        first_endpoint_sample_id=first.endpoint_sample.id,
        second_endpoint_sample_id=second.endpoint_sample.id,
        normal_dot=normal_dot,
        normal_evidence_source=OwnerNormalSource.LOCAL_FACE_FAN_NORMAL.value,
        confidence=confidence,
        evidence=(_side_surface_evidence(
            node,
            first,
            second,
            endpoint_relation,
            normal_dot,
            confidence,
            loop_corner,
        ),),
    )


def _side_surface_evidence_by_pair(
    evidence_records: tuple[SideSurfaceContinuityEvidence, ...],
) -> dict[tuple[str, str, str], SideSurfaceContinuityEvidence]:
    return {
        (
            record.scaffold_node_id,
            f"{record.first_endpoint_role.value}:{record.first_scaffold_edge_id}:{record.first_patch_chain_id}:{record.first_endpoint_sample_id}",
            f"{record.second_endpoint_role.value}:{record.second_scaffold_edge_id}:{record.second_patch_chain_id}:{record.second_endpoint_sample_id}",
        ): record
        for record in evidence_records
    }


def _node_occurrence_pair_key(
    node_id: str,
    first: _IncidentEdgeOccurrence,
    second: _IncidentEdgeOccurrence,
) -> tuple[str, str, str]:
    return (node_id, _occurrence_id(first), _occurrence_id(second))


def _loop_corner_by_ordered_pair(
    loop_corners: tuple[LoopCorner, ...],
) -> dict[tuple[PatchId, BoundaryLoopId, VertexId, PatchChainId, PatchChainId], LoopCorner]:
    return {
        _loop_corner_pair_key(
            corner.patch_id,
            corner.loop_id,
            corner.vertex_id,
            corner.previous_patch_chain_id,
            corner.next_patch_chain_id,
        ): corner
        for corner in loop_corners
    }


def _loop_corner_pair_key(
    patch_id: PatchId,
    loop_id: BoundaryLoopId,
    vertex_id: VertexId,
    previous_patch_chain_id: PatchChainId,
    next_patch_chain_id: PatchChainId,
) -> tuple[PatchId, BoundaryLoopId, VertexId, PatchChainId, PatchChainId]:
    return (
        patch_id,
        loop_id,
        vertex_id,
        previous_patch_chain_id,
        next_patch_chain_id,
    )


def _has_recurrent_previous_chain(
    first: _IncidentEdgeOccurrence,
    second: _IncidentEdgeOccurrence,
    node_occurrences: tuple[_IncidentEdgeOccurrence, ...],
) -> bool:
    duplicated_chain_keys = _same_patch_chain_keys_with_recurrence(node_occurrences)
    first_key = (first.scaffold_edge.chain_id, first.scaffold_edge.patch_id)
    second_key = (second.scaffold_edge.chain_id, second.scaffold_edge.patch_id)
    return first_key in duplicated_chain_keys and second_key not in duplicated_chain_keys


def _same_patch_chain_keys_with_recurrence(
    node_occurrences: tuple[_IncidentEdgeOccurrence, ...],
) -> frozenset[tuple[ChainId, PatchId]]:
    edge_ids_by_chain_patch: dict[tuple[ChainId, PatchId], set[str]] = defaultdict(set)
    for occurrence in node_occurrences:
        edge = occurrence.scaffold_edge
        edge_ids_by_chain_patch[(edge.chain_id, edge.patch_id)].add(edge.id)
    return frozenset(
        key
        for key, edge_ids in edge_ids_by_chain_patch.items()
        if len(edge_ids) >= 2
    )


def _incident_edge_confidence(
    node: ScaffoldNode,
    first: _IncidentEdgeOccurrence,
    second: _IncidentEdgeOccurrence,
    endpoint_relation: PatchChainEndpointRelation | None,
    kind: ScaffoldNodeIncidentEdgeRelationKind,
) -> float:
    if kind is ScaffoldNodeIncidentEdgeRelationKind.MISSING_ENDPOINT_EVIDENCE:
        return 0.0
    confidence_values = [
        node.confidence,
        first.scaffold_edge.confidence,
        second.scaffold_edge.confidence,
    ]
    if first.endpoint_sample is not None:
        confidence_values.append(first.endpoint_sample.confidence)
    if second.endpoint_sample is not None:
        confidence_values.append(second.endpoint_sample.confidence)
    if endpoint_relation is not None:
        confidence_values.append(endpoint_relation.confidence)
    return min(confidence_values)


def _occurrence_id(occurrence: _IncidentEdgeOccurrence) -> str:
    return (
        f"{occurrence.endpoint_role.value}:"
        f"{occurrence.scaffold_edge.id}:"
        f"{occurrence.scaffold_edge.patch_chain_id}:"
        f"{occurrence.endpoint_sample.id if occurrence.endpoint_sample is not None else 'missing_sample'}"
    )


def _incident_edge_evidence(
    node: ScaffoldNode,
    first: _IncidentEdgeOccurrence,
    second: _IncidentEdgeOccurrence,
    endpoint_relation: PatchChainEndpointRelation | None,
    kind: ScaffoldNodeIncidentEdgeRelationKind,
    confidence: float,
    base_kind: ScaffoldNodeIncidentEdgeRelationKind,
    side_surface_evidence: SideSurfaceContinuityEvidence | None,
    recurrence_evidence_present: bool,
) -> Evidence:
    first_edge = first.scaffold_edge
    second_edge = second.scaffold_edge
    data = {
        "policy": NODE_INCIDENT_EDGE_POLICY_NAME,
        "scaffold_node_id": node.id,
        "first_scaffold_edge_id": first_edge.id,
        "second_scaffold_edge_id": second_edge.id,
        "first_patch_chain_id": str(first_edge.patch_chain_id),
        "second_patch_chain_id": str(second_edge.patch_chain_id),
        "first_endpoint_role": first.endpoint_role.value,
        "second_endpoint_role": second.endpoint_role.value,
        "first_endpoint_sample_id": first.endpoint_sample.id if first.endpoint_sample is not None else None,
        "second_endpoint_sample_id": second.endpoint_sample.id if second.endpoint_sample is not None else None,
        "patch_chain_endpoint_relation_id": endpoint_relation.id if endpoint_relation is not None else None,
        "endpoint_relation_kind": endpoint_relation.kind.value if endpoint_relation is not None else None,
        "kind": kind.value,
        "original_tangent_local_category": base_kind.value,
        "confidence": confidence,
    }
    if side_surface_evidence is not None:
        data.update({
            "side_surface_continuity_evidence_id": side_surface_evidence.id,
            "same_side_surface_evidence_source": SIDE_SURFACE_CONTINUITY_POLICY_NAME,
            "normal_evidence_source": side_surface_evidence.normal_evidence_source,
            "materialized_vertex_id": str(side_surface_evidence.vertex_id),
            "source_vertex_ids": [
                str(source_vertex_id)
                for source_vertex_id in side_surface_evidence.source_vertex_ids
            ],
            "patch_id": str(side_surface_evidence.patch_id),
            "loop_id": str(side_surface_evidence.loop_id),
            "first_chain_id": str(side_surface_evidence.first_chain_id),
            "second_chain_id": str(side_surface_evidence.second_chain_id),
            "normal_dot": side_surface_evidence.normal_dot,
            "recurrence_evidence_present": recurrence_evidence_present,
        })
    return Evidence(
        source="layer_3_relations.scaffold_graph_relations",
        summary="node-local ScaffoldEdge endpoint occurrence pair relation",
        data=data,
    )


def _side_surface_evidence(
    node: ScaffoldNode,
    first: _IncidentEdgeOccurrence,
    second: _IncidentEdgeOccurrence,
    endpoint_relation: PatchChainEndpointRelation | None,
    normal_dot: float,
    confidence: float,
    loop_corner: LoopCorner,
) -> Evidence:
    return Evidence(
        source="layer_3_relations.scaffold_graph_relations",
        summary="same-side surface flow evidence between edge endpoint occurrences",
        data={
            "policy": SIDE_SURFACE_CONTINUITY_POLICY_NAME,
            "scaffold_node_id": node.id,
            "first_scaffold_edge_id": first.scaffold_edge.id,
            "second_scaffold_edge_id": second.scaffold_edge.id,
            "first_patch_chain_id": str(first.scaffold_edge.patch_chain_id),
            "second_patch_chain_id": str(second.scaffold_edge.patch_chain_id),
            "first_endpoint_role": first.endpoint_role.value,
            "second_endpoint_role": second.endpoint_role.value,
            "patch_id": str(first.scaffold_edge.patch_id),
            "loop_id": str(first.scaffold_edge.loop_id),
            "first_chain_id": str(first.scaffold_edge.chain_id),
            "second_chain_id": str(second.scaffold_edge.chain_id),
            "vertex_id": str(first.endpoint_sample.vertex_id) if first.endpoint_sample is not None else None,
            "source_vertex_ids": [
                str(source_vertex_id)
                for source_vertex_id in sorted(node.source_vertex_ids, key=str)
            ],
            "first_endpoint_sample_id": first.endpoint_sample.id if first.endpoint_sample is not None else None,
            "second_endpoint_sample_id": second.endpoint_sample.id if second.endpoint_sample is not None else None,
            "patch_chain_endpoint_relation_id": endpoint_relation.id if endpoint_relation is not None else None,
            "loop_corner_id": loop_corner.id,
            "position_in_loop": loop_corner.position_in_loop,
            "normal_dot": normal_dot,
            "normal_evidence_source": OwnerNormalSource.LOCAL_FACE_FAN_NORMAL.value,
            "confidence": confidence,
        },
    )


def _adjacency_id_by_chain_and_patch_pair(
    patch_adjacencies: Mapping[str, PatchAdjacency],
) -> dict[tuple[ChainId, tuple[PatchId, PatchId]], str]:
    return {
        (adjacency.chain_id, _patch_pair(adjacency.first_patch_id, adjacency.second_patch_id)): adjacency.id
        for adjacency in patch_adjacencies.values()
    }


def _shared_chain_relation(
    first_edge: ScaffoldEdge,
    second_edge: ScaffoldEdge,
    patch_adjacency_id: str | None,
) -> SharedChainPatchChainRelation:
    confidence = min(first_edge.confidence, second_edge.confidence)
    return SharedChainPatchChainRelation(
        id=f"shared_chain_patch_chain_relation:{first_edge.chain_id}:{first_edge.id}:{second_edge.id}",
        kind=SharedChainPatchChainRelationKind.CROSS_PATCH_SHARED_CHAIN,
        policy=SHARED_CHAIN_POLICY_NAME,
        chain_id=first_edge.chain_id,
        first_scaffold_edge_id=first_edge.id,
        second_scaffold_edge_id=second_edge.id,
        first_patch_chain_id=first_edge.patch_chain_id,
        second_patch_chain_id=second_edge.patch_chain_id,
        first_patch_id=first_edge.patch_id,
        second_patch_id=second_edge.patch_id,
        patch_adjacency_id=patch_adjacency_id,
        confidence=confidence,
        evidence=(_shared_chain_evidence(first_edge, second_edge, patch_adjacency_id, confidence),),
    )


def _shared_chain_evidence(
    first_edge: ScaffoldEdge,
    second_edge: ScaffoldEdge,
    patch_adjacency_id: str | None,
    confidence: float,
) -> Evidence:
    return Evidence(
        source="layer_3_relations.scaffold_graph_relations",
        summary="cross-patch ScaffoldEdges share one final Chain",
        data={
            "policy": SHARED_CHAIN_POLICY_NAME,
            "chain_id": str(first_edge.chain_id),
            "first_scaffold_edge_id": first_edge.id,
            "second_scaffold_edge_id": second_edge.id,
            "first_patch_chain_id": str(first_edge.patch_chain_id),
            "second_patch_chain_id": str(second_edge.patch_chain_id),
            "first_patch_id": str(first_edge.patch_id),
            "second_patch_id": str(second_edge.patch_id),
            "patch_adjacency_id": patch_adjacency_id,
            "confidence": confidence,
        },
    )


def _patch_pair(first_patch_id: PatchId, second_patch_id: PatchId) -> tuple[PatchId, PatchId]:
    return tuple(sorted((first_patch_id, second_patch_id), key=str))
