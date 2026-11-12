"""
Layer: 3 - Relations

Rules:
- Build RunCornerRelation v0 evidence: the patch's own interior angle where
  two directional-run ends meet in one patch-use view.
- Reuse the DD-45 in-patch pairing and angle source; no second angle rule.
- Evidence only: create no family, crossing, rail, node or Layer 1 identity.
- Do not use world directions, UV, solve, feature, API, UI or runtime semantics.
"""

from __future__ import annotations

from math import pi

from scaffold_core.layer_2_geometry.facts import GeometryFactSnapshot
from scaffold_core.layer_3_relations.direction_families import (
    GEODESIC_STRAIGHT_TOLERANCE,
    in_patch_run_end_pairs,
)
from scaffold_core.layer_3_relations.model import (
    PatchChainDirectionalEvidence,
    PatchChainEndpointSample,
    RunCornerKind,
    RunCornerRelation,
    RunEndpointJunction,
)

# A right corner is convex (pi/2) or reflex (3*pi/2) within the DD-45 tolerance.
RIGHT_CORNER_ANGLES = (pi / 2.0, 3.0 * pi / 2.0)


def build_run_corner_relations(
    geometry: GeometryFactSnapshot,
    directional_evidence_items: tuple[PatchChainDirectionalEvidence, ...],
    endpoint_samples: tuple[PatchChainEndpointSample, ...],
    run_endpoint_junctions: tuple[RunEndpointJunction, ...],
) -> tuple[RunCornerRelation, ...]:
    records: dict[str, RunCornerRelation] = {}
    for pair in in_patch_run_end_pairs(
        geometry,
        directional_evidence_items,
        endpoint_samples,
        run_endpoint_junctions,
    ):
        if len(pair.vertex_ids) != 1:
            continue  # the two ends sit on different seam sides: no corner of the patch
        record_id = (
            f"run_corner:{pair.junction.id}:{pair.first.id}:{pair.first_role.value}"
            f":{pair.second.id}:{pair.second_role.value}"
        )
        records[record_id] = RunCornerRelation(
            id=record_id,
            kind=run_corner_kind(pair.angle),
            run_endpoint_junction_id=pair.junction.id,
            patch_id=pair.first.patch_id,
            vertex_ids=pair.vertex_ids,
            first_directional_evidence_id=pair.first.id,
            first_endpoint_role=pair.first_role,
            second_directional_evidence_id=pair.second.id,
            second_endpoint_role=pair.second_role,
            interior_angle_sum=pair.angle,
            confidence=min(pair.first.confidence, pair.second.confidence, pair.junction.confidence),
        )
    return tuple(records[record_id] for record_id in sorted(records))


def run_corner_kind(angle: float) -> RunCornerKind:
    if abs(angle - pi) <= GEODESIC_STRAIGHT_TOLERANCE:
        return RunCornerKind.STRAIGHT
    if any(abs(angle - right) <= GEODESIC_STRAIGHT_TOLERANCE for right in RIGHT_CORNER_ANGLES):
        return RunCornerKind.RIGHT
    return RunCornerKind.OTHER
