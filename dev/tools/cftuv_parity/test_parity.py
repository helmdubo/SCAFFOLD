"""Headless checks for the pure parts of the CFTUV parity scoreboard."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from dev.tools.cftuv_parity.parity import (
    AXIS_LINE,
    FREE_LINE,
    NOT_LINE,
    SHAPED,
    Use,
    _scaffold_use,
    classify_uv_polyline,
    oblique_causes,
    score_uses,
    weighted_median,
)


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
