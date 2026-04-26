"""
Layer: 3 - Relations

Rules:
- Build conservative alignment classes from PatchChainDirectionalEvidence records.
- Use direction-family grouping only.
- Do not mutate lower-layer snapshots.
- Do not build world-facing semantics.
"""

from __future__ import annotations

from scaffold_core.core.evidence import Evidence
from scaffold_core.ids import PatchId
from scaffold_core.layer_1_topology.model import SurfaceModel
from scaffold_core.layer_2_geometry.facts import Vector3
from scaffold_core.layer_2_geometry.measures import EPSILON, dot, normalize
from scaffold_core.layer_3_relations.model import (
    AlignmentClass,
    AlignmentClassKind,
    PatchChainDirectionalEvidence,
    PatchAxes,
    PatchAxisSource,
)


ALIGNMENT_DIRECTION_COS_TOLERANCE = 0.996
PATCH_AXES_NON_PARALLEL_MAX_DOT = 0.2
POLICY_NAME = "g3c2_alignment_classes"
PATCH_AXES_POLICY_NAME = "patch_axes_v0_no_world_bias"


def build_alignment_classes(
    directional_evidence_items: tuple[PatchChainDirectionalEvidence, ...],
) -> tuple[AlignmentClass, ...]:
    """Group directional run uses into sign-insensitive direction families."""

    groups: list[list[PatchChainDirectionalEvidence]] = []
    for directional_evidence in sorted(directional_evidence_items, key=lambda item: item.id):
        if not _is_eligible(directional_evidence):
            continue
        for group in groups:
            if _is_direction_compatible(directional_evidence.direction, group[0].direction):
                group.append(directional_evidence)
                break
        else:
            groups.append([directional_evidence])

    classes = tuple(_alignment_class(index, tuple(group)) for index, group in enumerate(groups))
    return tuple(sorted(classes, key=lambda item: item.id))


def build_patch_axes(
    topology: SurfaceModel,
    directional_evidence_items: tuple[PatchChainDirectionalEvidence, ...],
    alignment_classes: tuple[AlignmentClass, ...],
) -> dict[PatchId, PatchAxes]:
    """Select up to two dominant alignment classes per Patch."""

    directional_evidence_by_id = {directional_evidence.id: directional_evidence for directional_evidence in directional_evidence_items}
    return {
        patch_id: _patch_axes_for_patch(patch_id, directional_evidence_by_id, alignment_classes)
        for patch_id in sorted(topology.patches, key=str)
    }


def _is_eligible(directional_evidence: PatchChainDirectionalEvidence) -> bool:
    return (
        directional_evidence.length > EPSILON
        and directional_evidence.confidence > 0.0
        and normalize(directional_evidence.direction) != (0.0, 0.0, 0.0)
    )


def _is_direction_compatible(left: Vector3, right: Vector3) -> bool:
    left_direction = normalize(left)
    right_direction = normalize(right)
    if left_direction == (0.0, 0.0, 0.0) or right_direction == (0.0, 0.0, 0.0):
        return False
    return abs(dot(left_direction, right_direction)) >= ALIGNMENT_DIRECTION_COS_TOLERANCE


def _alignment_class(
    index: int,
    members: tuple[PatchChainDirectionalEvidence, ...],
) -> AlignmentClass:
    dominant_direction = _dominant_direction(members)
    confidence = _confidence(members, dominant_direction)
    kind = (
        AlignmentClassKind.LINEAR
        if confidence >= ALIGNMENT_DIRECTION_COS_TOLERANCE
        else AlignmentClassKind.UNKNOWN
    )
    return AlignmentClass(
        id=f"alignment:{index}",
        member_directional_evidence_ids=tuple(member.id for member in members),
        patch_ids=tuple(sorted({member.patch_id for member in members}, key=str)),
        dominant_direction=dominant_direction,
        kind=kind,
        confidence=confidence,
        evidence=(_evidence(members),),
    )


def _dominant_direction(members: tuple[PatchChainDirectionalEvidence, ...]) -> Vector3:
    reference = normalize(members[0].direction)
    weighted = (0.0, 0.0, 0.0)
    for member in members:
        direction = normalize(member.direction)
        if dot(direction, reference) < 0.0:
            direction = (-direction[0], -direction[1], -direction[2])
        weighted = (
            weighted[0] + direction[0] * member.length,
            weighted[1] + direction[1] * member.length,
            weighted[2] + direction[2] * member.length,
        )
    return _canonicalize_direction(normalize(weighted))


def _canonicalize_direction(direction: Vector3) -> Vector3:
    for component in direction:
        if abs(component) <= EPSILON:
            continue
        if component < 0.0:
            return (-direction[0], -direction[1], -direction[2])
        return direction
    return direction


def _confidence(
    members: tuple[PatchChainDirectionalEvidence, ...],
    dominant_direction: Vector3,
) -> float:
    if not members or dominant_direction == (0.0, 0.0, 0.0):
        return 0.0
    return min(abs(dot(normalize(member.direction), dominant_direction)) for member in members)


def _evidence(members: tuple[PatchChainDirectionalEvidence, ...]) -> Evidence:
    return Evidence(
        source="layer_3_relations.alignment",
        summary="sign-insensitive direction-family grouping",
        data={
            "policy": POLICY_NAME,
            "member_count": len(members),
            "cos_tolerance": ALIGNMENT_DIRECTION_COS_TOLERANCE,
        },
    )


def _patch_axes_for_patch(
    patch_id: PatchId,
    directional_evidence_by_id: dict[str, PatchChainDirectionalEvidence],
    alignment_classes: tuple[AlignmentClass, ...],
) -> PatchAxes:
    scored = tuple(
        item
        for item in (
            _patch_alignment_score(patch_id, alignment_class, directional_evidence_by_id)
            for alignment_class in alignment_classes
        )
    )
    viable = tuple(item for item in scored if item[1] > EPSILON)
    if not viable:
        return _patch_axes(
            patch_id=patch_id,
            primary=None,
            secondary=None,
            scored=scored,
            primary_score=0.0,
            secondary_score=0.0,
        )

    ordered = tuple(sorted(viable, key=lambda item: (-item[1], item[0].id)))
    primary = ordered[0]
    secondary = next(
        (
            candidate
            for candidate in ordered[1:]
            if _non_parallel(primary[0].dominant_direction, candidate[0].dominant_direction)
        ),
        None,
    )
    return _patch_axes(
        patch_id=patch_id,
        primary=primary,
        secondary=secondary,
        scored=scored,
        primary_score=primary[1],
        secondary_score=secondary[1] if secondary is not None else 0.0,
    )


def _patch_alignment_score(
    patch_id: PatchId,
    alignment_class: AlignmentClass,
    directional_evidence_by_id: dict[str, PatchChainDirectionalEvidence],
) -> tuple[AlignmentClass, float]:
    return (
        alignment_class,
        sum(
            directional_evidence.length
            for directional_evidence_id in alignment_class.member_directional_evidence_ids
            for directional_evidence in (directional_evidence_by_id[directional_evidence_id],)
            if directional_evidence.patch_id == patch_id
        ),
    )


def _non_parallel(first: Vector3, second: Vector3) -> bool:
    return abs(dot(normalize(first), normalize(second))) <= PATCH_AXES_NON_PARALLEL_MAX_DOT


def _patch_axes(
    patch_id: PatchId,
    primary: tuple[AlignmentClass, float] | None,
    secondary: tuple[AlignmentClass, float] | None,
    scored: tuple[tuple[AlignmentClass, float], ...],
    primary_score: float,
    secondary_score: float,
) -> PatchAxes:
    if primary is None:
        source = PatchAxisSource.NO_ALIGNMENT
        confidence = 0.0
        primary_direction = (0.0, 0.0, 0.0)
        secondary_direction = (0.0, 0.0, 0.0)
    elif secondary is None:
        source = PatchAxisSource.SINGLE_ALIGNMENT
        confidence = 0.5 * primary[0].confidence
        primary_direction = primary[0].dominant_direction
        secondary_direction = (0.0, 0.0, 0.0)
    else:
        source = PatchAxisSource.DUAL_ALIGNMENT
        confidence = min(
            primary[0].confidence,
            secondary[0].confidence,
            1.0 - abs(dot(primary[0].dominant_direction, secondary[0].dominant_direction)),
        )
        primary_direction = primary[0].dominant_direction
        secondary_direction = secondary[0].dominant_direction

    return PatchAxes(
        patch_id=patch_id,
        primary_alignment_class_id=primary[0].id if primary is not None else None,
        secondary_alignment_class_id=secondary[0].id if secondary is not None else None,
        primary_direction=primary_direction,
        secondary_direction=secondary_direction,
        source=source,
        confidence=confidence,
        evidence=(
            _patch_axes_evidence(
                scored=scored,
                primary=primary,
                secondary=secondary,
                primary_score=primary_score,
                secondary_score=secondary_score,
            ),
        ),
    )


def _patch_axes_evidence(
    scored: tuple[tuple[AlignmentClass, float], ...],
    primary: tuple[AlignmentClass, float] | None,
    secondary: tuple[AlignmentClass, float] | None,
    primary_score: float,
    secondary_score: float,
) -> Evidence:
    return Evidence(
        source="layer_3_relations.alignment",
        summary="PatchAxes selected from AlignmentClass length scores",
        data={
            "policy": PATCH_AXES_POLICY_NAME,
            "candidate_count": len(tuple(item for item in scored if item[1] > EPSILON)),
            "primary_score": primary_score,
            "secondary_score": secondary_score,
            "candidate_scores": _candidate_scores(scored, primary, secondary),
        },
    )


def _candidate_scores(
    scored: tuple[tuple[AlignmentClass, float], ...],
    primary: tuple[AlignmentClass, float] | None,
    secondary: tuple[AlignmentClass, float] | None,
) -> tuple[dict[str, object], ...]:
    primary_class = primary[0] if primary is not None else None
    secondary_class = secondary[0] if secondary is not None else None
    ordered = tuple(sorted(scored, key=lambda item: (-item[1], item[0].id)))
    return tuple(
        {
            "alignment_class_id": alignment_class.id,
            "patch_length_score": score,
            "dot_with_primary": (
                None
                if primary_class is None or alignment_class.id == primary_class.id
                else abs(dot(alignment_class.dominant_direction, primary_class.dominant_direction))
            ),
            "selected_as": _candidate_selection(alignment_class, score, primary_class, secondary_class),
        }
        for alignment_class, score in ordered
    )


def _candidate_selection(
    alignment_class: AlignmentClass,
    score: float,
    primary: AlignmentClass | None,
    secondary: AlignmentClass | None,
) -> str:
    if score <= EPSILON:
        return "REJECTED_ZERO_PATCH_LENGTH"
    if primary is not None and alignment_class.id == primary.id:
        return "PRIMARY"
    if secondary is not None and alignment_class.id == secondary.id:
        return "SECONDARY"
    if primary is not None and not _non_parallel(alignment_class.dominant_direction, primary.dominant_direction):
        return "REJECTED_PARALLEL"
    return "REJECTED_LOWER_SCORE"
