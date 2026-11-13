"""
Layer: 3 - Relations

Rules:
- Build RunCornerRelation v0 evidence: the patch's own interior angle where
  two directional-run ends meet in one patch-use view.
- Build RunBridgedCornerRelation v0 evidence from those corners: two OTHER
  corners joined by one bridge run that together turn by a right angle.
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
    PatchChainEndpointRole,
    PatchChainEndpointSample,
    RunBridgedCornerRelation,
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


def build_run_bridged_corner_relations(
    run_corner_relations: tuple[RunCornerRelation, ...],
) -> tuple[RunBridgedCornerRelation, ...]:
    """Right corners of a patch surface turned over exactly one bridge run.

    A directional run is straight on the surface, so along it the boundary
    does not turn; it turns only at corners, by pi - interior angle. For
    arriving run A, bridge C and leaving run B of one loop, with A.END-C.START
    and C.END-B.START both OTHER corners, the turn from A to B is the sum of
    the two turns: the corners together make the angle first + second - pi.
    A record is emitted when run_corner_kind calls that angle RIGHT. No length
    is read; C may be any length. Corners of kind RIGHT or STRAIGHT never
    take part. Only two consecutive corners are summed, so each record spans
    exactly one bridge run; a chain of OTHER corners may give several
    overlapping records, one per bridge whose two corners add up to a right
    angle. The record says nothing about C's axis role.
    """

    other_corners: list[tuple[str, str, RunCornerRelation]] = []
    for corner in run_corner_relations:
        pair = _arriving_leaving(corner)
        if corner.kind is RunCornerKind.OTHER and pair is not None:
            other_corners.append((pair[0], pair[1], corner))
    corners_by_arriving_run: dict[str, list[tuple[str, RunCornerRelation]]] = {}
    for arriving, leaving, corner in other_corners:
        corners_by_arriving_run.setdefault(arriving, []).append((leaving, corner))
    records: dict[str, RunBridgedCornerRelation] = {}
    for arriving, bridge, first in other_corners:
        for leaving, second in corners_by_arriving_run.get(bridge, ()):
            if len({arriving, bridge, leaving}) != 3 or first.patch_id != second.patch_id:
                continue
            angle = first.interior_angle_sum + second.interior_angle_sum - pi
            if run_corner_kind(angle) is not RunCornerKind.RIGHT:
                continue
            record_id = f"run_bridged_corner:{first.id}+{second.id}"
            records[record_id] = RunBridgedCornerRelation(
                id=record_id,
                patch_id=first.patch_id,
                arriving_directional_evidence_id=arriving,
                bridge_directional_evidence_id=bridge,
                leaving_directional_evidence_id=leaving,
                arriving_corner_id=first.id,
                leaving_corner_id=second.id,
                arriving_interior_angle_sum=first.interior_angle_sum,
                leaving_interior_angle_sum=second.interior_angle_sum,
                interior_angle_sum=angle,
                confidence=min(first.confidence, second.confidence),
            )
    return tuple(records[record_id] for record_id in sorted(records))


def _arriving_leaving(corner: RunCornerRelation) -> tuple[str, str] | None:
    """(run whose END arrives, run whose START leaves), or None for another role pair."""

    run_by_role = {
        corner.first_endpoint_role: corner.first_directional_evidence_id,
        corner.second_endpoint_role: corner.second_directional_evidence_id,
    }
    arriving = run_by_role.get(PatchChainEndpointRole.END)
    leaving = run_by_role.get(PatchChainEndpointRole.START)
    if arriving is None or leaving is None:
        return None
    return arriving, leaving
