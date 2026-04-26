"""
Layer: 3 - Relations

Rules:
- Build pairwise relations between patch-local run-use endpoint samples.
- Use only derived junction samples and measured vectors.
- Do not mutate lower-layer topology or geometry.
- Do not build world-facing semantics or solve data.
"""

from __future__ import annotations

from itertools import combinations

from scaffold_core.core.evidence import Evidence
from scaffold_core.ids import VertexId
from scaffold_core.layer_2_geometry.measures import EPSILON, dot, length, normalize
from scaffold_core.layer_3_relations.model import (
    ChainDirectionalRunUseJunctionSample,
    JunctionDirectionRelationKind,
    JunctionRunUseRelation,
    JunctionRunUseRelationKind,
)


OPPOSITE_COLLINEAR_MAX_DOT = -0.996
SAME_RAY_COLLINEAR_MIN_DOT = 0.996
ORTHOGONAL_MAX_ABS_DOT = 0.2
POLICY_NAME = "junction_run_use_relation_v0"


def build_junction_run_use_relations(
    samples: tuple[ChainDirectionalRunUseJunctionSample, ...],
) -> tuple[JunctionRunUseRelation, ...]:
    """Build unordered pairwise relations between samples at the same Vertex."""

    samples_by_vertex: dict[VertexId, list[ChainDirectionalRunUseJunctionSample]] = {}
    for sample in samples:
        samples_by_vertex.setdefault(sample.vertex_id, []).append(sample)

    relations: list[JunctionRunUseRelation] = []
    for vertex_id in sorted(samples_by_vertex, key=str):
        vertex_samples = tuple(sorted(samples_by_vertex[vertex_id], key=lambda item: item.id))
        relations.extend(
            _relation(vertex_id, first, second)
            for first, second in combinations(vertex_samples, 2)
        )
    return tuple(relations)


def _relation(
    vertex_id: VertexId,
    first: ChainDirectionalRunUseJunctionSample,
    second: ChainDirectionalRunUseJunctionSample,
) -> JunctionRunUseRelation:
    first_tangent = normalize(first.tangent_away_from_vertex)
    second_tangent = normalize(second.tangent_away_from_vertex)
    first_normal = normalize(first.owner_normal)
    second_normal = normalize(second.owner_normal)
    direction_dot = dot(first_tangent, second_tangent)
    normal_dot = dot(first_normal, second_normal)
    direction_relation = _direction_relation(first, second, first_tangent, second_tangent, direction_dot)
    kind = _relation_kind(direction_relation)
    confidence = _confidence(first, second, direction_relation)

    return JunctionRunUseRelation(
        id=f"junction_run_use_relation:{vertex_id}:{first.id}:{second.id}",
        vertex_id=vertex_id,
        first_sample_id=first.id,
        second_sample_id=second.id,
        first_run_use_id=first.run_use_id,
        second_run_use_id=second.run_use_id,
        direction_dot=direction_dot,
        normal_dot=normal_dot,
        direction_relation=direction_relation,
        kind=kind,
        confidence=confidence,
        evidence=(_evidence(first, second, direction_dot, normal_dot),),
    )


def _direction_relation(
    first: ChainDirectionalRunUseJunctionSample,
    second: ChainDirectionalRunUseJunctionSample,
    first_tangent,
    second_tangent,
    direction_dot: float,
) -> JunctionDirectionRelationKind:
    if (
        first.confidence <= 0.0
        or second.confidence <= 0.0
        or length(first_tangent) <= EPSILON
        or length(second_tangent) <= EPSILON
    ):
        return JunctionDirectionRelationKind.DEGENERATE
    if direction_dot <= OPPOSITE_COLLINEAR_MAX_DOT:
        return JunctionDirectionRelationKind.OPPOSITE_COLLINEAR
    if direction_dot >= SAME_RAY_COLLINEAR_MIN_DOT:
        return JunctionDirectionRelationKind.SAME_RAY_COLLINEAR
    if abs(direction_dot) <= ORTHOGONAL_MAX_ABS_DOT:
        return JunctionDirectionRelationKind.ORTHOGONAL
    return JunctionDirectionRelationKind.OBLIQUE


def _relation_kind(
    direction_relation: JunctionDirectionRelationKind,
) -> JunctionRunUseRelationKind:
    if direction_relation is JunctionDirectionRelationKind.OPPOSITE_COLLINEAR:
        return JunctionRunUseRelationKind.CONTINUATION_CANDIDATE
    if direction_relation is JunctionDirectionRelationKind.ORTHOGONAL:
        return JunctionRunUseRelationKind.CORNER_CONNECTOR
    if direction_relation is JunctionDirectionRelationKind.OBLIQUE:
        return JunctionRunUseRelationKind.OBLIQUE_CONNECTOR
    if direction_relation is JunctionDirectionRelationKind.SAME_RAY_COLLINEAR:
        return JunctionRunUseRelationKind.AMBIGUOUS
    return JunctionRunUseRelationKind.DEGENERATE


def _confidence(
    first: ChainDirectionalRunUseJunctionSample,
    second: ChainDirectionalRunUseJunctionSample,
    direction_relation: JunctionDirectionRelationKind,
) -> float:
    if direction_relation is JunctionDirectionRelationKind.DEGENERATE:
        return 0.0
    return min(first.confidence, second.confidence)


def _evidence(
    first: ChainDirectionalRunUseJunctionSample,
    second: ChainDirectionalRunUseJunctionSample,
    direction_dot: float,
    normal_dot: float,
) -> Evidence:
    return Evidence(
        source="layer_3_relations.junction_relations",
        summary="pairwise relation between endpoint samples at one Vertex",
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
