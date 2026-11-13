"""Headless checks for the pure parts of the CFTUV parity scoreboard."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from dev.tools.cftuv_parity.parity import (
    AXIS_LINE,
    FREE_LINE,
    NOT_LINE,
    REFERENCE_DIR,
    SHAPED,
    STRAIGHTEN_STRIPS,
    Use,
    _replay,
    _scaffold_use,
    corner_turns,
    classify_uv_polyline,
    oblique_causes,
    sample_pairs,
    score_uses,
    shape_agreement,
    summarize_shapes,
    weighted_median,
)

# A patch outline in metres (Scaffold) and its reference: the same shape
# turned by a quarter turn, scaled by 0.25 UV per metre and moved.
SHAPE_M = [(0.0, 0.0), (4.0, 0.0), (4.0, 2.0), (1.0, 3.0), (0.0, 2.0)]


def _reference_of(points, scale=0.25):
    return [(5.0 - scale * v, 7.0 + scale * u) for u, v in points]


def test_rotated_scaled_shape_agrees_fully():
    points = list(zip(SHAPE_M, _reference_of(SHAPE_M)))
    pairs, agree = shape_agreement(points, 0.25, extent=1.0)
    assert pairs == 10 and agree == 10
    summary = summarize_shapes({"P": (pairs, agree)})
    assert summary == {"shape": 1.0, "torn": 0, "scored": 1, "pairs": 10}


def test_one_corner_moved_far_tears_the_patch():
    moved = list(SHAPE_M)
    moved[3] = (30.0, -12.0)  # an arbitrary pin coordinate
    points = list(zip(moved, _reference_of(SHAPE_M)))
    pairs, agree = shape_agreement(points, 0.25, extent=1.0)
    assert (pairs, agree) == (10, 6)  # the 4 pairs through the moved corner fail
    summary = summarize_shapes({"P": (pairs, agree), "Q": (10, 10)})
    assert summary["torn"] == 1 and summary["scored"] == 2
    assert summary["shape"] == pytest.approx(16 / 20)


def test_fewer_than_three_common_pins_is_not_scored():
    points = list(zip(SHAPE_M[:2], _reference_of(SHAPE_M[:2])))
    assert shape_agreement(points, 0.25, extent=1.0) is None
    assert shape_agreement(list(zip(SHAPE_M, _reference_of(SHAPE_M))), None, extent=1.0) is None
    assert summarize_shapes({"P": None}) == {"shape": None, "torn": 0, "scored": 0, "pairs": 0}


def test_pair_sampling_is_deterministic_and_bounded():
    assert sample_pairs(4) == [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
    big = sample_pairs(100)  # 4950 pairs -> every 17th
    assert len(big) <= 300 and big == sample_pairs(100)
    assert big[:2] == [(0, 1), (0, 18)] and all(i < j < 100 for i, j in big)


def test_straight_polylines_on_axes():
    assert classify_uv_polyline([(0, 0), (0.5, 0), (1, 0)])[:2] == (AXIS_LINE, "U")
    assert classify_uv_polyline([(0, 1), (0, 0.4), (0, 0)])[:2] == (AXIS_LINE, "V")
    # 0.5 degree off U still counts as an axis line; 3 degrees does not.
    assert classify_uv_polyline([(0, 0), (1, 0.0087)])[:2] == (AXIS_LINE, "U")
    assert classify_uv_polyline([(0, 0), (1, 0.0524)])[:2] == (FREE_LINE, None)


def test_bent_and_closed_polylines_are_shaped():
    assert classify_uv_polyline([(0, 0), (0.5, 0.1), (1, 0)])[0] == SHAPED
    assert classify_uv_polyline([(0, 0), (1, 0), (1, 1), (0, 0)])[0] == SHAPED
    # A wobble below the tolerance (1% of UV length) stays straight.
    cls, axis, length, deviation = classify_uv_polyline([(0, 0), (0.5, 0.004), (1, 0)])
    assert (cls, axis) == (AXIS_LINE, "U")
    assert deviation == pytest.approx(0.004, rel=1e-3)
    assert length == pytest.approx(1.0, abs=1e-4)


def test_weighted_median():
    assert weighted_median([(0.25, 3.0), (0.5, 1.0)]) == 0.25
    assert weighted_median([]) is None


def _use(uid, patch, length, ref, ref_axis, sc, sc_axis, ref_pins=(), sc_pins=()):
    return Use(
        id=uid, patch_id=patch, length=length, ref_class=ref, ref_axis=ref_axis, uv_length=length,
        sc_class=sc, sc_axis=sc_axis, ref_pins=frozenset(ref_pins), sc_pins=frozenset(sc_pins),
    )


def test_scores_on_a_tiny_case():
    uses = [
        # Patch P: a rectangle both tools see as lines, but Scaffold swaps axes
        # by a quarter turn (not scored) and pins one corner the reference does not.
        _use("a", "P", 2.0, AXIS_LINE, "U", AXIS_LINE, "AXIS_B", [("P", 1)], [("P", 1)]),
        _use("b", "P", 1.0, AXIS_LINE, "V", AXIS_LINE, "AXIS_A", [("P", 2)], [("P", 2), ("P", 9)]),
        _use("c", "P", 2.0, AXIS_LINE, "U", AXIS_LINE, "AXIS_B"),
        _use("d", "P", 1.0, AXIS_LINE, "V", NOT_LINE, None, [("P", 3)]),
        # Patch Q: a shaped chain Scaffold claims as a line.
        _use("e", "Q", 4.0, SHAPED, None, AXIS_LINE, "AXIS_A"),
    ]
    scores = score_uses(uses)
    assert scores.line_recall == pytest.approx(5.0 / 6.0)
    assert scores.false_lines == pytest.approx(4.0 / 9.0)
    assert scores.pin_cov == pytest.approx(2.0 / 3.0)
    assert scores.pin_extra == pytest.approx(1.0 / 3.0)
    assert scores.axis_pairs == 3
    assert scores.axis_agree == 1.0
    assert (scores.patches, scores.ref_structured, scores.sc_structured, scores.both_structured) == (2, 1, 2, 1)


def test_axis_disagreement_is_counted():
    uses = [
        _use("a", "P", 1.0, AXIS_LINE, "U", AXIS_LINE, "AXIS_A"),
        _use("b", "P", 1.0, AXIS_LINE, "V", AXIS_LINE, "AXIS_A"),
    ]
    assert score_uses(uses).axis_agree == 0.0


def _skeleton(roles, frame="UNFOLDED", diagnostics=(), lines=None):
    return SimpleNamespace(
        axis_role_by_run=roles,
        line_by_run=lines or {run: f"line:{run}" for run in roles},
        vertex_by_run_end={(run, end): f"{run}:{end}" for run in roles for end in ("START", "END")},
        frame=frame,
        diagnostics=diagnostics,
    )


def test_scaffold_use_line_and_failures():
    runs = [SimpleNamespace(id="r1"), SimpleNamespace(id="r2")]
    on_line = {("r1:START", "P"): (0.0, 2.0), ("r1:END", "P"): (1.0, 2.0), ("r2:END", "P"): (3.0, 2.0)}
    skeleton = _skeleton({"r1": "AXIS_A", "r2": "AXIS_A"})
    assert _scaffold_use(runs, skeleton, "P", on_line, 3.0)[:2] == (AXIS_LINE, "AXIS_A")
    off_line = {**on_line, ("r2:END", "P"): (3.0, 2.5)}
    assert _scaffold_use(runs, skeleton, "P", off_line, 3.0)[2] == "PINS_OFF_LINE"
    assert _scaffold_use(runs, skeleton, "P", {}, 3.0)[2] == "ENDS_UNPINNED"
    mixed = _skeleton({"r1": "AXIS_A", "r2": "AXIS_B"})
    assert _scaffold_use(runs, mixed, "P", on_line, 3.0)[2] == "MIXED_ROLES"
    conflict = _skeleton(
        {"r1": "AXIS_A", "r2": "OBLIQUE"}, frame="FRAME_FREE",
        diagnostics=("axis bipartition conflict: line:r2 -> OBLIQUE",),
    )
    causes = oblique_causes(conflict)
    assert causes == {"line:r2": "OBLIQUE_CONFLICT"}
    assert _scaffold_use(runs, conflict, "P", on_line, 3.0, causes)[2] == "OBLIQUE_CONFLICT"
    unlinked = _skeleton({"r1": "OBLIQUE", "r2": "OBLIQUE"}, frame="FRAME_FREE")
    assert _scaffold_use(runs, unlinked, "P", on_line, 3.0)[2] == "OBLIQUE_UNLINKED"
    assert _scaffold_use([], skeleton, "P", on_line, 3.0)[2] == "NO_RUNS"


@pytest.mark.parametrize("name", ["Main_wall", "Arc"])
def test_reference_right_corners_turn_by_the_corner_law(name):
    # Frame-free islands orient their lines from corner handedness: no
    # corner against the law, no mirrored island (Main_wall was twisted).
    context, solve = _replay(REFERENCE_DIR / f"{name}.capture.json", STRAIGHTEN_STRIPS[name])
    with_law, checked, mirrored = corner_turns(context.relation_snapshot, solve)
    assert checked > 10
    assert with_law == checked
    assert mirrored == 0


def test_reference_column_back_face_leaves_its_island_as_a_strip():
    # The flat back face is stitched to both caps only across its two short
    # straight ends, so with strips on it leaves its island and is laid as a
    # rectangle with every boundary vertex pinned (CFTUV pins all 46); the
    # caps become islands of their own with pins.
    context, solve = _replay(REFERENCE_DIR / "collumn.capture.json", STRAIGHTEN_STRIPS["collumn"])
    assembly = solve.assembly
    patches_by_island = {island.id: island.patch_ids for island in assembly.islands}
    frame_by_island = {skeleton.island_id: skeleton.frame for skeleton in solve.skeletons}
    back = "patch:seed:f355"
    assert patches_by_island[assembly.island_by_patch_id[back]] == (back,)
    assert frame_by_island[assembly.island_by_patch_id[back]] == "STRIP"
    assert len({v.vertex_id for v in solve.vertices if v.pinned and v.patch_id == back}) == 46
    for cap in ("patch:seed:f0", "patch:seed:f353"):
        assert patches_by_island[assembly.island_by_patch_id[cap]] == (cap,)
        assert any(v.pinned and v.patch_id == cap for v in solve.vertices)
    # Only seams the angle gate accepts get the leaving reason: the two bent
    # sides, shared with the body, keep the gate's own refusal.
    reasons = {
        decision.reason
        for decision in assembly.decisions
        if {decision.first_patch_id, decision.second_patch_id} == {back, "patch:seed:f1"}
    }
    assert reasons == {"angle defect exceeds stitch limit"}
