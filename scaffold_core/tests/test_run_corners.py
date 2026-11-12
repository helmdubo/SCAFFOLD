"""
Layer: tests

Rules:
- Layer 3 RunCornerRelation v0 tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

from collections import Counter
from math import pi

import pytest

from scaffold_core.layer_3_relations.direction_families import GEODESIC_STRAIGHT_TOLERANCE
from scaffold_core.layer_3_relations.model import RunCornerKind
from scaffold_core.layer_3_relations.run_corners import run_corner_kind
from scaffold_core.layer_5_runtime.pins import run_skeleton_solve
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
from scaffold_core.tests.fixtures.cylinder_tube import make_cylinder_tube_without_caps_with_one_seam_source
from scaffold_core.tests.fixtures.run_corner_sheets import (
    make_flat_l_sheet_source,
    make_folded_l_sheet_source,
    make_folded_sheet_source,
    make_hexagon_source,
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
