"""
Layer: 3 - Relations

Rules:
- Build pairwise relations between patch-local PatchChain endpoint samples.
- Use only derived endpoint samples and measured vectors.
- Do not mutate lower-layer topology or geometry.
- Do not build world-facing semantics or solve data.
"""

from __future__ import annotations

from itertools import combinations

from scaffold_core.core.evidence import Evidence
from scaffold_core.ids import VertexId
from scaffold_core.layer_2_geometry.measures import EPSILON, dot, length, normalize
from scaffold_core.layer_3_relations.model import (
    EndpointDirectionRelationKind,
    PatchChainEndpointRelationKind,
    PatchChainEndpointRelation,
    PatchChainEndpointSample,
)


OPPOSITE_COLLINEAR_MAX_DOT = -0.996
SAME_RAY_COLLINEAR_MIN_DOT = 0.996
ORTHOGONAL_MAX_ABS_DOT = 0.2
POLICY_NAME = "patch_chain_endpoint_relation_v0"


def build_patch_chain_endpoint_relations(
    samples: tuple[PatchChainEndpointSample, ...],
) -> tuple[PatchChainEndpointRelation, ...]:
    """Build unordered pairwise relations between samples at the same Vertex."""

    samples_by_vertex: dict[VertexId, list[PatchChainEndpointSample]] = {}
    for sample in samples:
        samples_by_vertex.setdefault(sample.vertex_id, []).append(sample)

    relations: list[PatchChainEndpointRelation] = []
    for vertex_id in sorted(samples_by_vertex, key=str):
        vertex_samples = tuple(sorted(samples_by_vertex[vertex_id], key=lambda item: item.id))
        relations.extend(
            _relation(vertex_id, first, second)
            for first, second in combinations(vertex_samples, 2)
        )
    return tuple(relations)


def _relation(
    vertex_id: VertexId,
    first: PatchChainEndpointSample,
    second: PatchChainEndpointSample,
) -> PatchChainEndpointRelation:
    first_tangent = normalize(first.tangent_away_from_vertex)
    second_tangent = normalize(second.tangent_away_from_vertex)
    first_normal = normalize(first.owner_normal)
    second_normal = normalize(second.owner_normal)
    direction_dot = dot(first_tangent, second_tangent)
    normal_dot = dot(first_normal, second_normal)
    direction_relation = _direction_relation(first, second, first_tangent, second_tangent, direction_dot)
    kind = _relation_kind(direction_relation)
    confidence = _confidence(first, second, direction_relation)

    return PatchChainEndpointRelation(
        id=f"patch_chain_endpoint_relation:{vertex_id}:{first.id}:{second.id}",
        vertex_id=vertex_id,
        first_sample_id=first.id,
        second_sample_id=second.id,
        first_directional_evidence_id=first.directional_evidence_id,
        second_directional_evidence_id=second.directional_evidence_id,
        direction_dot=direction_dot,
        normal_dot=normal_dot,
        direction_relation=direction_relation,
        kind=kind,
        confidence=confidence,
        evidence=(_evidence(first, second, direction_dot, normal_dot),),
    )


def _direction_relation(
    first: PatchChainEndpointSample,
    second: PatchChainEndpointSample,
    first_tangent,
    second_tangent,
    direction_dot: float,
) -> EndpointDirectionRelationKind:
    if (
        first.confidence <= 0.0
        or second.confidence <= 0.0
        or length(first_tangent) <= EPSILON
        or length(second_tangent) <= EPSILON
    ):
        return EndpointDirectionRelationKind.DEGENERATE
    if direction_dot <= OPPOSITE_COLLINEAR_MAX_DOT:
        return EndpointDirectionRelationKind.OPPOSITE_COLLINEAR
    if direction_dot >= SAME_RAY_COLLINEAR_MIN_DOT:
        return EndpointDirectionRelationKind.SAME_RAY_COLLINEAR
    if abs(direction_dot) <= ORTHOGONAL_MAX_ABS_DOT:
        return EndpointDirectionRelationKind.ORTHOGONAL
    return EndpointDirectionRelationKind.OBLIQUE


def _relation_kind(
    direction_relation: EndpointDirectionRelationKind,
) -> PatchChainEndpointRelationKind:
    if direction_relation is EndpointDirectionRelationKind.OPPOSITE_COLLINEAR:
        return PatchChainEndpointRelationKind.CONTINUATION_CANDIDATE
    if direction_relation is EndpointDirectionRelationKind.ORTHOGONAL:
        return PatchChainEndpointRelationKind.CORNER_CONNECTOR
    if direction_relation is EndpointDirectionRelationKind.OBLIQUE:
        return PatchChainEndpointRelationKind.OBLIQUE_CONNECTOR
    if direction_relation is EndpointDirectionRelationKind.SAME_RAY_COLLINEAR:
        return PatchChainEndpointRelationKind.AMBIGUOUS
    return PatchChainEndpointRelationKind.DEGENERATE


def _confidence(
    first: PatchChainEndpointSample,
    second: PatchChainEndpointSample,
    direction_relation: EndpointDirectionRelationKind,
) -> float:
    if direction_relation is EndpointDirectionRelationKind.DEGENERATE:
        return 0.0
    return min(first.confidence, second.confidence)


def _evidence(
    first: PatchChainEndpointSample,
    second: PatchChainEndpointSample,
    direction_dot: float,
    normal_dot: float,
) -> Evidence:
    return Evidence(
        source="layer_3_relations.patch_chain_endpoint_relations",
        summary="pairwise relation between PatchChain endpoint samples at one Vertex",
        data={
            "policy": POLICY_NAME,
            "direction_dot": direction_dot,
            "normal_dot": normal_dot,
            "first_patch_id": str(first.patch_id),
            "second_patch_id": str(second.patch_id),
            "first_owner_normal_source": first.owner_normal_source.value,
            "second_owner_normal_source": second.owner_normal_source.value,
        },
    )
