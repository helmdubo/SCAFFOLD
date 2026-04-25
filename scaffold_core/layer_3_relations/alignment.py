"""
Layer: 3 - Relations

Rules:
- Build conservative alignment classes from ChainDirectionalRunUse records.
- Use direction-family grouping only.
- Do not mutate lower-layer snapshots.
- Do not build patch axes or world-facing semantics.
"""

from __future__ import annotations

from scaffold_core.core.evidence import Evidence
from scaffold_core.layer_2_geometry.facts import Vector3
from scaffold_core.layer_2_geometry.measures import EPSILON, dot, normalize
from scaffold_core.layer_3_relations.model import (
    AlignmentClass,
    AlignmentClassKind,
    ChainDirectionalRunUse,
)


ALIGNMENT_DIRECTION_COS_TOLERANCE = 0.996
POLICY_NAME = "g3c2_alignment_classes"


def build_alignment_classes(
    run_uses: tuple[ChainDirectionalRunUse, ...],
) -> tuple[AlignmentClass, ...]:
    """Group directional run uses into sign-insensitive direction families."""

    groups: list[list[ChainDirectionalRunUse]] = []
    for run_use in sorted(run_uses, key=lambda item: item.id):
        if not _is_eligible(run_use):
            continue
        for group in groups:
            if _is_direction_compatible(run_use.direction, group[0].direction):
                group.append(run_use)
                break
        else:
            groups.append([run_use])

    classes = tuple(_alignment_class(index, tuple(group)) for index, group in enumerate(groups))
    return tuple(sorted(classes, key=lambda item: item.id))


def _is_eligible(run_use: ChainDirectionalRunUse) -> bool:
    return (
        run_use.length > EPSILON
        and run_use.confidence > 0.0
        and normalize(run_use.direction) != (0.0, 0.0, 0.0)
    )


def _is_direction_compatible(left: Vector3, right: Vector3) -> bool:
    left_direction = normalize(left)
    right_direction = normalize(right)
    if left_direction == (0.0, 0.0, 0.0) or right_direction == (0.0, 0.0, 0.0):
        return False
    return abs(dot(left_direction, right_direction)) >= ALIGNMENT_DIRECTION_COS_TOLERANCE


def _alignment_class(
    index: int,
    members: tuple[ChainDirectionalRunUse, ...],
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
        member_run_use_ids=tuple(member.id for member in members),
        patch_ids=tuple(sorted({member.patch_id for member in members}, key=str)),
        dominant_direction=dominant_direction,
        kind=kind,
        confidence=confidence,
        evidence=(_evidence(members),),
    )


def _dominant_direction(members: tuple[ChainDirectionalRunUse, ...]) -> Vector3:
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
    members: tuple[ChainDirectionalRunUse, ...],
    dominant_direction: Vector3,
) -> float:
    if not members or dominant_direction == (0.0, 0.0, 0.0):
        return 0.0
    return min(abs(dot(normalize(member.direction), dominant_direction)) for member in members)


def _evidence(members: tuple[ChainDirectionalRunUse, ...]) -> Evidence:
    return Evidence(
        source="layer_3_relations.alignment",
        summary="sign-insensitive direction-family grouping",
        data={
            "policy": POLICY_NAME,
            "member_count": len(members),
            "cos_tolerance": ALIGNMENT_DIRECTION_COS_TOLERANCE,
        },
    )
