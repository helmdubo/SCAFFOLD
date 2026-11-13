"""
Layer: tests

Rules:
- Layer 3 RunCornerRelation v0 and RunBridgedCornerRelation v0 tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from math import cos, pi, radians, sin

import pytest

from scaffold_core.layer_3_relations.direction_families import GEODESIC_STRAIGHT_TOLERANCE
from scaffold_core.layer_3_relations.model import PatchChainEndpointRole, RunCornerKind, RunCornerRelation
from scaffold_core.layer_3_relations.run_corners import build_run_bridged_corner_relations, run_corner_kind
from scaffold_core.layer_5_runtime.pins import run_skeleton_solve
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
from scaffold_core.tests.fixtures.cylinder_tube import make_cylinder_tube_without_caps_with_one_seam_source
from scaffold_core.tests.fixtures.run_corner_sheets import (
    make_cut_corner_rectangle_source,
    make_flat_l_sheet_source,
    make_folded_l_sheet_source,
    make_folded_sheet_source,
    make_hexagon_source,
    make_notched_sheet_source,
    make_outline_face_source,
)
from scaffold_core.tests.fixtures.single_patch import make_single_quad_source
from scaffold_core.tests.test_layer_5_runtime import _load_capture


def _relations(source):
    return run_pass_1_relations(run_pass_0(source)).relation_snapshot


def _corner_at(relations, source_vertex: str):
    """Kinds and angles (degrees) of the corners at one source vertex."""

    evidence = {e.id: e for e in relations.patch_chain_directional_evidence}
    found = []
    for corner in relations.run_corner_relations:
        run = evidence[corner.first_directional_evidence_id]
        end = run.start_source_vertex_id if corner.first_endpoint_role.value == "START" else run.end_source_vertex_id
        if str(end) == source_vertex:
            found.append((corner.kind, round(corner.interior_angle_sum * 180.0 / pi, 1)))
    return found


def test_quad_corners_are_right() -> None:
    relations = _relations(make_single_quad_source())

    assert Counter(c.kind for c in relations.run_corner_relations) == {RunCornerKind.RIGHT: 4}


def test_hexagon_corners_are_other() -> None:
    relations = _relations(make_hexagon_source())

    assert Counter(c.kind for c in relations.run_corner_relations) == {RunCornerKind.OTHER: 6}
    assert {round(c.interior_angle_sum, 6) for c in relations.run_corner_relations} == {round(2.0 * pi / 3.0, 6)}


def test_l_outline_reflex_corner_is_right_like_the_convex_ones() -> None:
    relations = _relations(make_flat_l_sheet_source())

    assert Counter(c.kind for c in relations.run_corner_relations) == {RunCornerKind.RIGHT: 6}
    assert _corner_at(relations, "e") == [(RunCornerKind.RIGHT, 270.0)]
    assert sorted(round(c.interior_angle_sum * 180.0 / pi) for c in relations.run_corner_relations) == [
        90, 90, 90, 90, 90, 270,
    ]


def test_folded_sheet_corner_reads_the_patch_angle_not_3d_directions() -> None:
    relations = _relations(make_folded_sheet_source())

    # b-p and p-w are perpendicular in 3D; the patch angle at p is 135 degrees.
    assert _corner_at(relations, "p") == [(RunCornerKind.OTHER, 135.0)]
    # w-q and q-a are perpendicular in 3D; the patch angle at q is 180 degrees.
    assert _corner_at(relations, "q") == [(RunCornerKind.STRAIGHT, 180.0)]
    assert _corner_at(relations, "a") == [(RunCornerKind.RIGHT, 90.0)]


def test_run_corner_kind_tolerance_is_the_geodesic_tolerance() -> None:
    inside, outside = GEODESIC_STRAIGHT_TOLERANCE * 0.99, GEODESIC_STRAIGHT_TOLERANCE * 1.01
    assert run_corner_kind(pi + inside) is RunCornerKind.STRAIGHT
    assert run_corner_kind(pi + outside) is RunCornerKind.OTHER
    for right in (pi / 2.0, 3.0 * pi / 2.0):
        assert run_corner_kind(right - inside) is RunCornerKind.RIGHT
        assert run_corner_kind(right + inside) is RunCornerKind.RIGHT
        assert run_corner_kind(right - outside) is RunCornerKind.OTHER
        assert run_corner_kind(right + outside) is RunCornerKind.OTHER
    assert run_corner_kind(pi / 2.0 + pi / 6.0) is RunCornerKind.OTHER  # 120 degrees
    assert run_corner_kind(pi / 4.0) is RunCornerKind.OTHER


def _self_seam_chain_ids(context) -> set[str]:
    uses = Counter((str(pc.chain_id), str(pc.patch_id)) for pc in context.topology_snapshot.patch_chains.values())
    return {chain_id for (chain_id, _patch_id), count in uses.items() if count > 1}


@pytest.mark.parametrize(
    "make_source",
    [
        make_folded_sheet_source,
        make_folded_l_sheet_source,
        lambda: _load_capture("artist_arch_bevel.json"),
        lambda: _load_capture("artist_cyl_multiseam.json"),
        lambda: _load_capture("artist_cross_band.json"),
    ],
)
def test_straight_corners_coincide_with_in_patch_geodesic_crossings(make_source) -> None:
    context = run_pass_1_relations(run_pass_0(make_source()))
    relations = context.relation_snapshot
    evidence = {e.id: e for e in relations.patch_chain_directional_evidence}
    self_seam = _self_seam_chain_ids(context)
    straight = {
        (frozenset((c.first_directional_evidence_id, c.second_directional_evidence_id)), c.run_endpoint_junction_id)
        for c in relations.run_corner_relations
        if c.kind is RunCornerKind.STRAIGHT
        # DD-45: a SEAM_SELF chain never continues; its straight corners stay evidence.
        and str(evidence[c.first_directional_evidence_id].parent_chain_id) not in self_seam
        and str(evidence[c.second_directional_evidence_id].parent_chain_id) not in self_seam
    }
    crossings = {
        (frozenset((c.first_directional_evidence_id, c.second_directional_evidence_id)), c.run_endpoint_junction_id)
        for family in relations.connected_direction_families
        for c in family.crossing_records
        if c.kind == "IN_PATCH_GEODESIC"
    }

    assert straight
    assert straight == crossings


def test_run_ends_on_two_seam_sides_make_no_corner() -> None:
    # One-seam tube: at each seam end the run ends of the two seam sides share
    # a junction but sit on different occurrences; they are no corner of the band.
    context = run_pass_1_relations(run_pass_0(make_cylinder_tube_without_caps_with_one_seam_source()))
    relations = context.relation_snapshot
    evidence = {e.id: e for e in relations.patch_chain_directional_evidence}
    (seam_chain_id,) = _self_seam_chain_ids(context)

    seam_corners = [
        corner for corner in relations.run_corner_relations
        if seam_chain_id in {
            str(evidence[corner.first_directional_evidence_id].parent_chain_id),
            str(evidence[corner.second_directional_evidence_id].parent_chain_id),
        }
    ]
    assert len(seam_corners) == 4  # each seam side meets the two rims at its own occurrences
    for corner in seam_corners:
        assert len(corner.vertex_ids) == 1
        assert corner.kind is RunCornerKind.RIGHT
        assert evidence[corner.first_directional_evidence_id].patch_chain_id != (
            evidence[corner.second_directional_evidence_id].patch_chain_id
        )
        assert str(evidence[corner.first_directional_evidence_id].parent_chain_id) != str(
            evidence[corner.second_directional_evidence_id].parent_chain_id
        )
    (skeleton,) = run_skeleton_solve(context).skeletons
    assert skeleton.frame == "FRAME_FREE"
    assert not [d for d in skeleton.diagnostics if "bipartition" in d]
    assert set(skeleton.axis_role_by_run.values()) == {"AXIS_A", "AXIS_B"}


def test_run_corners_stay_inside_one_patch_loop_and_one_occurrence() -> None:
    relations = _relations(_load_capture("artist_arch_bevel.json"))
    evidence = {e.id: e for e in relations.patch_chain_directional_evidence}
    junctions = {j.id: j for j in relations.run_endpoint_junctions}

    # The arch has junctions where runs of two patches meet (rim and cap).
    assert any(len(set(j.incident_patch_ids)) > 1 for j in junctions.values())
    assert relations.run_corner_relations
    for corner in relations.run_corner_relations:
        first = evidence[corner.first_directional_evidence_id]
        second = evidence[corner.second_directional_evidence_id]
        assert first.patch_id == second.patch_id == corner.patch_id
        assert first.loop_id == second.loop_id
        assert len(corner.vertex_ids) == 1
        assert corner.vertex_ids[0] in junctions[corner.run_endpoint_junction_id].topology_vertex_ids


def _bridged(relations):
    """(arriving, bridge, leaving) as source-vertex pairs and the combined angle in degrees."""

    evidence = {e.id: e for e in relations.patch_chain_directional_evidence}

    def name(run_id):
        run = evidence[run_id]
        return f"{run.start_source_vertex_id}-{run.end_source_vertex_id}"

    return sorted(
        (
            name(c.arriving_directional_evidence_id),
            name(c.bridge_directional_evidence_id),
            name(c.leaving_directional_evidence_id),
            round(c.interior_angle_sum * 180.0 / pi, 6),
        )
        for c in relations.run_bridged_corner_relations
    )


def test_cut_corner_is_a_convex_right_corner_bridged_by_the_cut() -> None:
    relations = _relations(make_cut_corner_rectangle_source())

    assert _bridged(relations) == [("b-c", "c-d", "d-g", 90.0)]
    (record,) = relations.run_bridged_corner_relations
    corners = {c.id: c for c in relations.run_corner_relations}
    first, second = corners[record.arriving_corner_id], corners[record.leaving_corner_id]
    assert first.kind is second.kind is RunCornerKind.OTHER
    assert round(record.arriving_interior_angle_sum * 180.0 / pi, 6) == 135.0
    assert record.leaving_interior_angle_sum == second.interior_angle_sum
    assert record.interior_angle_sum < pi  # convex
    assert record.patch_id == first.patch_id == second.patch_id


def test_chamfered_notch_corners_are_reflex_right_corners_bridged_by_their_chamfers() -> None:
    # jamb -> chamfer -> top and top -> chamfer -> jamb turn right by 90 degrees
    # in two 45-degree steps; the two chamfers are themselves at a right angle
    # across the notch top. The top-left chamfer is a convex one.
    relations = _relations(make_notched_sheet_source(folded=False))

    assert _bridged(relations) == [
        ("a1-j1", "j1-j2", "j2-j3", 270.0),
        ("a4-t1", "t1-t2", "t2-a0", 90.0),
        ("j1-j2", "j2-j3", "j3-j4", 270.0),
        ("j2-j3", "j3-j4", "j4-a2", 270.0),
    ]


def test_any_split_of_a_right_angle_over_one_bridge_qualifies() -> None:
    relations = _relations(make_cut_corner_rectangle_source(first_turn_degrees=30.0))

    assert _bridged(relations) == [("b-c", "c-d", "d-g", 90.0)]
    (record,) = relations.run_bridged_corner_relations
    assert round(record.arriving_interior_angle_sum * 180.0 / pi, 6) == 150.0
    assert round(record.leaving_interior_angle_sum * 180.0 / pi, 6) == 120.0


def _turtle(turns_and_lengths, start=(0.0, 0.0)):
    """Outline points from a start, walking +x, turning left by each angle (degrees) after each run."""

    points, heading = [start], 0.0
    for length, turn in turns_and_lengths:
        x, y = points[-1]
        points.append((x + length * cos(radians(heading)), y + length * sin(radians(heading))))
        heading += turn
    return tuple(points[:-1])


def test_two_turns_that_do_not_add_up_to_a_right_angle_make_no_bridged_corner() -> None:
    # Turns 45 then 30 degrees (interior 135 and 150): 75 degrees together.
    outline = _turtle([(4.0, 45.0), (1.0, 30.0), (2.0, 105.0), (5.225, 90.0), (2.639, 90.0)])
    relations = _relations(make_outline_face_source("turns_45_30", outline))

    assert Counter(c.kind for c in relations.run_corner_relations)[RunCornerKind.OTHER] == 3
    assert relations.run_bridged_corner_relations == ()


def test_a_right_angle_turned_over_two_bridge_runs_makes_no_bridged_corner() -> None:
    # Three 30-degree turns over two cut runs: no pair of turns is a right angle (v0: one bridge).
    outline = _turtle([(4.0, 90.0), (1.0, 30.0), (0.5, 30.0), (0.5, 30.0), (3.317, 90.0), (1.683, 90.0)])
    relations = _relations(make_outline_face_source("two_bridges", outline))

    assert sorted(round(c.interior_angle_sum * 180.0 / pi) for c in relations.run_corner_relations) == [
        90, 90, 90, 150, 150, 150,
    ]
    assert relations.run_bridged_corner_relations == ()


def _record(record_id, arriving, leaving, angle, kind=None):
    return RunCornerRelation(
        id=record_id,
        kind=kind or run_corner_kind(angle),
        run_endpoint_junction_id=f"junction:{record_id}",
        patch_id="patch:p",
        vertex_ids=(f"vertex:{record_id}",),
        first_directional_evidence_id=arriving,
        first_endpoint_role=PatchChainEndpointRole.END,
        second_directional_evidence_id=leaving,
        second_endpoint_role=PatchChainEndpointRole.START,
        interior_angle_sum=angle,
        confidence=1.0,
    )


def test_right_and_straight_corners_and_repeated_runs_never_bridge() -> None:
    # Each pair of corners adds up to a right angle, but one corner is RIGHT
    # or STRAIGHT, or the leaving run is the arriving run again.
    cases = [
        (_record("x", "a", "c", 0.5 * pi), _record("y", "c", "b", pi)),
        (_record("x", "a", "c", pi), _record("y", "c", "b", 0.5 * pi)),
        (_record("x", "a", "c", 0.75 * pi), _record("y", "c", "a", 0.75 * pi)),
    ]
    for corners in cases:
        assert build_run_bridged_corner_relations(corners) == ()
    # Two START ends are no arriving/leaving pair.
    starts = replace(_record("x", "a", "c", 0.75 * pi), first_endpoint_role=PatchChainEndpointRole.START)
    assert build_run_bridged_corner_relations((starts, _record("y", "c", "b", 0.75 * pi))) == ()
    # The same two OTHER corners with distinct runs do bridge.
    (record,) = build_run_bridged_corner_relations((_record("x", "a", "c", 0.75 * pi), _record("y", "c", "b", 0.75 * pi)))
    assert (record.arriving_directional_evidence_id, record.bridge_directional_evidence_id,
            record.leaving_directional_evidence_id) == ("a", "c", "b")
    assert (record.arriving_corner_id, record.leaving_corner_id) == ("x", "y")


@pytest.mark.parametrize("make_source", [make_cut_corner_rectangle_source, make_notched_sheet_source])
def test_bridged_corners_are_the_same_whether_or_not_the_patch_is_planar(make_source) -> None:
    flat = _relations(make_source(folded=False) if make_source is make_notched_sheet_source else make_source())
    folded = _relations(make_source(folded=True))

    assert flat.run_bridged_corner_relations
    assert _bridged(flat) == _bridged(folded)


def test_a_right_corner_at_the_tolerance_edge_never_takes_part() -> None:
    # Hand-made RunCornerRelation records (no fixture hits these angles): a
    # RIGHT corner at pi/2 + 0.09 (inside the DD-45 tolerance 0.1) and an OTHER
    # corner at pi - 0.11 (just outside STRAIGHT). Together they make
    # pi/2 - 0.02, which run_corner_kind calls RIGHT, but one corner is not
    # OTHER, so no record. Two OTHER corners with the same sum do bridge.
    right_edge, near_straight = 0.5 * pi + 0.09, pi - 0.11
    assert run_corner_kind(right_edge) is RunCornerKind.RIGHT
    assert run_corner_kind(near_straight) is RunCornerKind.OTHER
    assert run_corner_kind(right_edge + near_straight - pi) is RunCornerKind.RIGHT

    for corners in (
        (_record("x", "a", "c", right_edge), _record("y", "c", "b", near_straight)),
        (_record("x", "a", "c", near_straight), _record("y", "c", "b", right_edge)),
    ):
        assert build_run_bridged_corner_relations(corners) == ()
    other_pair = (_record("x", "a", "c", 0.5 * pi + 0.11), _record("y", "c", "b", pi - 0.13))
    assert len(build_run_bridged_corner_relations(other_pair)) == 1
