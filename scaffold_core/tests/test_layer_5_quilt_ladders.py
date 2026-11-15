"""
Layer: tests

Rules:
- A STRAIGHT_LADDER strip that lies in a quilt (plan Slice AI): with exactly
  one rail stitched and that rail laid by the quilt, the free rail follows
  the stitched rail across the profile lines and the width rule; every
  other case is not read, and says so unless it is expected.
- The user's rounded wall with the filter +Z (and hand-made SeamDirectives
  on it), and synthetic marked strips with hand-chosen directives.
- Every negative case is paired with a positive one. No production logic.
"""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import pytest

from dev.tools.scaffold_graph_debug.snapshot_io import load_source_snapshot
from scaffold_core.layer_4_features.model import FeatureConstraintKind, FeatureKind
from scaffold_core.layer_5_runtime import quilt_ladders
from scaffold_core.layer_5_runtime.pins import run_skeleton_solve
from scaffold_core.layer_5_runtime.skeleton import FRAME_FREE, UNFOLDED_FRAME
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations, run_pass_2_features, run_pass_3_filters
from scaffold_core.tests.fixtures.bevel_patches import make_marked_ladder_strip_source
from scaffold_core.user_filters.model import FilterOptions, FilterSnapshot, SeamDirective, SeamDirectiveKind

ROUNDED = Path(__file__).resolve().parent / "data" / "bevel_cases" / "u_rounded_wall_noise_top.capture.json"
UP = (0.0, 0.0, 1.0)
F36 = "patch:seed:f36"
EXACT = 1e-9
_CACHE: dict = {}

# Synthetic strips: rail A straight; rail B lifted off the plane (so the quilt has no rigid frame).
STRAIGHT_A = [(float(i), 0.0, 0.0) for i in range(4)]
LIFTED_B = [(0.0, 0.2, 0.0), (1.0, 0.5, 0.5), (2.0, 0.5, 0.5), (3.0, 0.3, 0.0)]  # end A 0.2 long, end B 0.3
FLAT_B = [(0.0, 0.2, 0.0), (1.0, 0.7, 0.0), (2.0, 0.7, 0.0), (3.0, 0.2, 0.0)]  # in the plane: a rigid quilt
# An L-shaped strip folded at its corner: flat, then climbing a slope; each rail has a run on each axis.
FOLDED_A = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 1.0, 0.3), (2.0, 2.0, 0.6), (2.0, 3.0, 0.9)]
FOLDED_B = [(0.0, 0.1, 0.0), (1.0, 0.1, 0.0), (1.9, 0.1, 0.0), (1.9, 1.0, 0.3), (1.9, 2.0, 0.6), (1.9, 3.0, 0.9)]


def _rounded():
    if "rounded" not in _CACHE:
        plain = run_pass_2_features(run_pass_1_relations(run_pass_0(load_source_snapshot(ROUNDED))))
        _CACHE["rounded"] = (plain, run_pass_3_filters(plain, FilterOptions(world_up=UP)))
    return _CACHE["rounded"]


def _short(patch_id) -> str:
    return str(patch_id).replace("patch:seed:", "")


def _solve_with(context, directives):
    return run_skeleton_solve(replace(context, filter_snapshot=FilterSnapshot(FilterOptions(UP), directives=tuple(directives))))


def _skeleton(solve, patch_id):
    island_id = solve.assembly.island_by_patch_id[patch_id]
    island = next(i for i in solve.assembly.islands if i.id == island_id)
    return island, next(s for s in solve.skeletons if s.island_id == island_id)


def _ladder(context, patch_id):
    return next(c for c in context.feature_snapshot.constraints
                if c.kind is FeatureConstraintKind.STRAIGHT_LADDER and str(c.patch_id) == patch_id)


def _pins(solve, patch_id):
    return {v.vertex_id: v.uv for v in solve.vertices if v.patch_id == patch_id and v.pinned}


def _not_read(solve, patch_id):
    return [d for d in solve.diagnostics if d.startswith(quilt_ladders.NOT_READ_PREFIX) and d.endswith(patch_id)]


def _stitched(context, island, uses) -> bool:
    chains = {str(context.topology_snapshot.patch_chains[use].chain_id) for use in uses}
    return bool(chains & set(island.stitched_chain_ids))


def _rail_axis(context, skeleton, uses) -> int:
    """0 when the longest run of the rail (tie: id) is on AXIS_A, 1 on AXIS_B."""

    runs = [e for e in context.relation_snapshot.patch_chain_directional_evidence if e.patch_chain_id in uses]
    longest = min(runs, key=lambda e: (-e.length, e.id))
    return {"AXIS_A": 0, "AXIS_B": 1}[skeleton.axis_role_by_run[longest.id]]


def _end_length(context, uses) -> float:
    return sum(e.length for e in context.relation_snapshot.patch_chain_directional_evidence if e.patch_chain_id in uses)


def _check_kept_together(context, solve, patch_id, *, width, lines_pinned, one_piece=True):
    """Each profile line with both rail vertices pinned: same place along one axis, width across.

    one_piece: that axis is the axis of the stitched rail's longest run for every line. Otherwise
    each line may lie in another piece (plan Slice AK); returns the along axis of every such line
    (0 for AXIS_A, 1 for AXIS_B) in profile-line order.
    """

    island, skeleton = _skeleton(solve, patch_id)
    assert skeleton.frame == FRAME_FREE
    assert skeleton.quilt_ladder_by_patch[patch_id] == quilt_ladders.QUILT_LADDER_READ
    assert _not_read(solve, patch_id) == []
    ladder = _ladder(context, patch_id).ladder
    stitched = [_stitched(context, island, uses) for uses in (ladder.rail_a_patch_chain_ids, ladder.rail_b_patch_chain_ids)]
    assert stitched.count(True) == 1
    along = _rail_axis(context, skeleton, ladder.rail_a_patch_chain_ids if stitched[0] else ladder.rail_b_patch_chain_ids)
    pins = _pins(solve, patch_id)
    both = [
        (pins[str(line.rail_a.vertex_id)], pins[str(line.rail_b.vertex_id)])
        for line in ladder.profile_lines
        if str(line.rail_a.vertex_id) in pins and str(line.rail_b.vertex_id) in pins
    ]
    assert len(both) == lines_pinned
    alongs = []
    for a, b in both:
        line_along = along if one_piece else (0 if abs(a[0] - b[0]) <= EXACT else 1)
        assert a[line_along] == pytest.approx(b[line_along], abs=EXACT)  # no shear
        assert abs(a[1 - line_along] - b[1 - line_along]) == pytest.approx(width, rel=EXACT)
        alongs.append(line_along)
    return island, skeleton, alongs


def _pinned_edge_errors(context, solve, island_id):
    """Relative length error of every source edge of the quilt whose two ends are pinned on its patch side."""

    source = context.source_snapshot
    pin = {(v.vertex_id, v.patch_id): v.uv for v in solve.vertices if v.pinned and v.island_id == island_id}
    errors = []
    for patch_id, patch in context.topology_snapshot.patches.items():
        seen = set()
        for face_id in patch.source_face_ids:
            for edge_id in source.faces[face_id].edge_ids:
                if edge_id in seen:
                    continue
                seen.add(edge_id)
                ends = source.edges[edge_id].vertex_ids
                uvs = [pin.get((solve.vertex_by_face_corner.get((str(face_id), str(v))), str(patch_id))) for v in ends]
                truth = math.dist(*(source.vertices[v].position for v in ends))
                if None not in uvs and truth > 1e-12:
                    errors.append(abs(math.dist(*uvs) - truth) / truth)
    return errors


# --------------------------------------------------------------------------- the user's rounded wall, +Z


def test_the_bottom_strip_f36_keeps_its_rails_together_in_its_quilt(monkeypatch) -> None:
    plain, up = _rounded()
    solve = run_skeleton_solve(up)
    island, skeleton = _skeleton(solve, F36)
    # plan Slice AK: the two sides of each stitched Chain of the quilt are one line where they cover the
    # same segments; Layer 3 keeps the seams' sides in different families (a family does not cross a
    # seam with several runs), so here the join, not Layer 3, makes them one.
    family_of = {m: f.id for f in up.relation_snapshot.connected_direction_families for m in f.member_directional_evidence_ids}
    by_side: dict[tuple, list] = {}
    for e in up.relation_snapshot.patch_chain_directional_evidence:
        if str(e.parent_chain_id) in island.stitched_chain_ids and e.id in skeleton.orientation_by_run:
            by_side.setdefault((str(e.parent_chain_id), tuple(sorted(e.segment_indices))), []).append(e.id)
    pairs = [ids for ids in by_side.values() if len(ids) == 2]
    assert pairs and any(family_of.get(a) != family_of.get(b) for a, b in pairs)
    assert all(skeleton.line_by_run[a] == skeleton.line_by_run[b] for a, b in pairs)
    ladder = _ladder(up, F36).ladder
    ends = [(_stitched(up, island, uses), uses) for uses in (ladder.end_a_patch_chain_ids, ladder.end_b_patch_chain_ids)]
    stitched_ends = [uses for is_stitched, uses in ends if is_stitched]
    width = _end_length(up, stitched_ends[0]) if len(stitched_ends) == 1 else ladder.width
    assert len(stitched_ends) == 1  # one end leads, the other follows it
    # plan Slice AK: the stitched rail turns around f111's corner (a bridged right corner of f111 over the
    # 1.4 mm edge v208-v210), so the strip is read in two pieces: lines 0-19 along one axis, 20-21 along
    # the other, its rails together in each. Every line is pinned (before: 20, v210/v157 had no place).
    _island, _skeleton_, alongs = _check_kept_together(up, solve, F36, width=width, lines_pinned=22, one_piece=False)
    assert alongs == [alongs[0]] * 20 + [1 - alongs[0]] * 2
    pinned_sources = {v.source_vertex_id for v in solve.vertices if v.patch_id == F36 and v.pinned}
    assert {"v208", "v209", "v210", "v211", "v157", "v158"} <= pinned_sources
    assert not [d for d in solve.diagnostics if "without a pinned profile partner" in d and d.startswith(island.id)]
    assert not [d for d in skeleton.diagnostics if "contradictory" in d]
    # The one-face strip f95 at f111's other end measures the band's width 0.4218 against 0.4207: within
    # the drift of the 7 m quilt, not of the 0.42 m across it (plan Slice AK); 61 source vertices pinned.
    assert len({v.source_vertex_id for v in solve.vertices if v.island_id == island.id and v.pinned}) == 61
    # Pinned edges: f111 and f73 are now laid straight along f36 and keep their lengths only roughly
    # (measured 137 edges, mean 0.031; f111 max 0.24). The worst is f36's mitre edge on its free rail,
    # v209-v211, 40.8 mm in 3D and laid w * sqrt(2) = 0.107 around the square turn. Before the slice:
    # 74 edges, mean 0.0077, max 0.084, and the corner folded over after the fill.
    errors = _pinned_edge_errors(up, solve, island.id)
    assert len(errors) == 137
    assert sum(errors) / len(errors) < 0.035 and sorted(errors)[-2] < 0.25 and max(errors) == pytest.approx(1.61, abs=0.01)
    # The wall quilt: its strip f94 develops (no constraint); its 76 pins do not change.
    walls, wall_skeleton = _skeleton(solve, "patch:seed:f94")
    assert sum(1 for v in solve.vertices if v.island_id == walls.id) == 76
    assert dict(wall_skeleton.quilt_ladder_by_patch) == {} and wall_skeleton.ladder_ties == ()
    assert "patch:seed:f94" not in {str(c.patch_id) for c in up.feature_snapshot.constraints}
    # Paired negative: without the filter f36 is an island by itself.
    alone, _alone_skeleton = _skeleton(run_skeleton_solve(plain), F36)
    assert alone.patch_ids == (F36,)
    # Paired negative: without the join f73 is not read and the quilt pins fewer source vertices.
    from scaffold_core.layer_5_runtime import frame_free

    monkeypatch.setattr(frame_free, "join_stitched_lines", lambda runs, line_of, signs, stitched, diagnostics: (line_of, signs, None))
    apart = run_skeleton_solve(up)
    _island_apart, skeleton_apart = _skeleton(apart, F36)
    assert any(skeleton_apart.line_by_run[a] != skeleton_apart.line_by_run[b] for a, b in pairs)
    assert skeleton_apart.quilt_ladder_by_patch["patch:seed:f73"] == quilt_ladders.QUILT_LADDER_RAIL_NOT_LAID
    assert len({v.source_vertex_id for v in apart.vertices if v.island_id == island.id and v.pinned}) < 61


def test_a_strip_whose_quilt_pins_none_of_its_vertices_is_not_kept_together_and_says_so() -> None:
    # f35 meets the conditions in the top quilt, but the quilt gives none of its run ends both coordinates.
    _plain, up = _rounded()
    solve = run_skeleton_solve(up)
    _island, skeleton = _skeleton(solve, "patch:seed:f35")
    assert skeleton.quilt_ladder_by_patch["patch:seed:f35"] == quilt_ladders.QUILT_LADDER_NOTHING_PINNED
    assert _not_read(solve, "patch:seed:f35") == [
        f"{quilt_ladders.NOT_READ_PREFIX}, {quilt_ladders.QUILT_LADDER_NOTHING_PINNED}: patch:seed:f35"
    ]
    assert skeleton.ladder_ties == () and _pins(solve, "patch:seed:f35") == {}


def test_drop_strips_without_pins_keeps_a_strip_with_one_pinned_run_end() -> None:
    class Run:
        def __init__(self, run_id, patch_id):
            self.id, self.patch_id = run_id, patch_id

    corners = (("c0", "p"), ("c1", "p"))
    ties = (quilt_ladders.LadderTie(("v", "p"), "s", ("w", "p"), corners, 0.5, 0),
            quilt_ladders.LadderTie(("x", "q"), "s2", ("y", "q"), corners, 0.5, 0))
    runs = (Run("rp", "p"), Run("rq", "q"))
    node = {("rp", "START"): "n1", ("rp", "END"): "n2", ("rq", "START"): "n3", ("rq", "END"): "n4"}
    read = quilt_ladders.QUILT_LADDER_READ
    pieces = [f"{quilt_ladders.PIECES_PREFIX}, 1 profile lines on no piece -> not tied: {patch}" for patch in ("p", "q")]
    diagnostics: list[str] = list(pieces)
    outcomes, kept = quilt_ladders.drop_strips_without_pins({"p": read, "q": read}, ties, runs, node, {"n2"}, diagnostics)
    assert outcomes == {"p": read, "q": quilt_ladders.QUILT_LADDER_NOTHING_PINNED}
    assert kept == ties[:1]
    # q is not read after all: it loses its "read in pieces" diagnostic, p keeps its own.
    assert diagnostics == [pieces[0], f"{quilt_ladders.NOT_READ_PREFIX}, {quilt_ladders.QUILT_LADDER_NOTHING_PINNED}: q"]


def test_a_strip_outside_the_rigid_frame_of_its_quilt_says_so() -> None:
    # Reachable only behind a warped patch or a bent hinge; no capture or fixture builds one, so the rule is tested alone.
    class Constraint:
        def __init__(self, patch_id):
            self.patch_id = patch_id

    diagnostics: list[str] = []
    outcomes = quilt_ladders.rigid_frame_outcomes((Constraint("in"), Constraint("out")), {"in": None}, diagnostics)
    assert outcomes == {"in": quilt_ladders.QUILT_LADDER_RIGID_FRAME, "out": quilt_ladders.QUILT_LADDER_OUTSIDE_FRAME}
    assert diagnostics == [f"{quilt_ladders.NOT_READ_PREFIX}, {quilt_ladders.QUILT_LADDER_OUTSIDE_FRAME}: out"]


def test_a_strip_with_both_rails_stitched_is_not_read_and_says_nothing() -> None:
    plain, up = _rounded()
    flipped = [
        replace(d, kind=SeamDirectiveKind.JOIN) if {_short(d.first_patch_id), _short(d.second_patch_id)} == {"f36", "f110"}
        else d
        for d in up.filter_snapshot.directives
    ]
    solve = _solve_with(plain, flipped)
    island, skeleton = _skeleton(solve, F36)
    ladder = _ladder(plain, F36).ladder
    assert all(_stitched(plain, island, uses) for uses in (ladder.rail_a_patch_chain_ids, ladder.rail_b_patch_chain_ids))
    assert skeleton.quilt_ladder_by_patch[F36] == quilt_ladders.QUILT_LADDER_BOTH_STITCHED
    assert _not_read(solve, F36) == [] and not [d for d in solve.diagnostics if d.endswith(F36)]
    assert not [tie for tie in skeleton.ladder_ties if tie.key[1] == F36]
    # Paired positive: with the filter's own directives one rail is stitched and f36 is read.
    assert _skeleton(run_skeleton_solve(up), F36)[1].quilt_ladder_by_patch[F36] == quilt_ladders.QUILT_LADDER_READ


def test_a_strip_with_no_rail_stitched_is_not_read_and_says_so() -> None:
    plain, up = _rounded()
    (join,) = [d for d in up.filter_snapshot.directives
               if {_short(d.first_patch_id), _short(d.second_patch_id)} == {"f28", "f36"}]
    solve = _solve_with(plain, [join])
    island, skeleton = _skeleton(solve, F36)
    assert len(island.patch_ids) > 1
    assert skeleton.quilt_ladder_by_patch[F36] == quilt_ladders.QUILT_LADDER_NO_RAIL_STITCHED
    assert _not_read(solve, F36) == [f"{quilt_ladders.NOT_READ_PREFIX}, {quilt_ladders.QUILT_LADDER_NO_RAIL_STITCHED}: {F36}"]
    assert skeleton.ladder_ties == ()
    # Paired positive: the filter's own directives.
    assert _skeleton(run_skeleton_solve(up), F36)[1].quilt_ladder_by_patch[F36] == quilt_ladders.QUILT_LADDER_READ


def test_a_strip_whose_stitched_rail_the_quilt_does_not_lay_is_not_read_and_says_so() -> None:
    _plain, up = _rounded()
    solve = run_skeleton_solve(up)
    for patch_id in ("patch:seed:f71", "patch:seed:f96"):
        _island, skeleton = _skeleton(solve, patch_id)
        assert skeleton.quilt_ladder_by_patch[patch_id] == quilt_ladders.QUILT_LADDER_RAIL_NOT_LAID
        assert _not_read(solve, patch_id) == [
            f"{quilt_ladders.NOT_READ_PREFIX}, {quilt_ladders.QUILT_LADDER_RAIL_NOT_LAID}: {patch_id}"
        ]
        assert not [tie for tie in skeleton.ladder_ties if tie.key[1] == patch_id]
    # Paired positive: f36 in the same solve is read; so is f73 since plan Slice AK, its stitched rail lying
    # on f111, whose side on f36 is now one line with f36's rail. Its rail on f111 is laid in two pieces on one
    # axis around f111's curved middle (OBLIQUE): the lines between them are not tied, and say so.
    assert _skeleton(solve, F36)[1].quilt_ladder_by_patch[F36] == quilt_ladders.QUILT_LADDER_READ
    f73 = "patch:seed:f73"
    assert _skeleton(solve, f73)[1].quilt_ladder_by_patch[f73] == quilt_ladders.QUILT_LADDER_READ
    assert [d for d in solve.diagnostics if d.endswith(f73)] == [
        f"{quilt_ladders.PIECES_PREFIX}, 4 profile lines on no piece -> not tied: {f73}"
    ]


def test_a_ladder_whose_run_end_is_not_on_it_is_not_read_and_says_so() -> None:
    _plain, up = _rounded()
    constraint = _ladder(up, F36)
    lines = constraint.ladder.profile_lines
    broken_line = replace(lines[5], rail_a=replace(lines[5].rail_a, vertex_id="no_such_vertex"))
    broken = replace(constraint, ladder=replace(constraint.ladder, profile_lines=lines[:5] + (broken_line,) + lines[6:]))
    features = up.feature_snapshot
    tampered = replace(up, feature_snapshot=replace(features, constraints=tuple(
        broken if c is constraint else c for c in features.constraints
    )))
    solve = run_skeleton_solve(tampered)
    _island, skeleton = _skeleton(solve, F36)
    if skeleton.quilt_ladder_by_patch[F36] != quilt_ladders.QUILT_LADDER_OFF_LADDER:
        pytest.fail("the vertex replaced is not a run end of f36")
    assert _not_read(solve, F36) == [f"{quilt_ladders.NOT_READ_PREFIX}, {quilt_ladders.QUILT_LADDER_OFF_LADDER}: {F36}"]
    assert not [tie for tie in skeleton.ladder_ties if tie.key[1] == F36]
    # Paired positive: the untouched constraint is read.
    assert _skeleton(run_skeleton_solve(up), F36)[1].quilt_ladder_by_patch[F36] == quilt_ladders.QUILT_LADDER_READ


# --------------------------------------------------------------------------- synthetic strips


def _synthetic(rail_a, rail_b, joins=(), splits=()):
    """A marked strip and its four neighbours; JOIN / SPLIT the strip's seams to the named ones (A, B, EA, EB)."""

    key = (tuple(rail_a), tuple(rail_b), tuple(joins), tuple(splits))
    if key not in _CACHE:
        context = run_pass_2_features(run_pass_1_relations(run_pass_0(make_marked_ladder_strip_source(rail_a, rail_b))))
        bevels = context.feature_snapshot.bevels
        (strip,) = [r for r in bevels if r.kind is FeatureKind.BEVEL_STRIP]
        neighbour = {"A": str(strip.rail_a_neighbour_patch_ids[0]), "B": str(strip.rail_b_neighbour_patch_ids[0])}
        for junction in (r for r in bevels if r.kind is FeatureKind.BEVEL_JUNCTION):
            (contact,) = junction.joined_strips
            neighbour["E" + contact.strip_end.value] = str(junction.patch_id)
        directives = []
        for adjacency in context.relation_snapshot.patch_adjacencies.values():
            pair = {str(adjacency.first_patch_id), str(adjacency.second_patch_id)}
            for names, kind in ((joins, SeamDirectiveKind.JOIN), (splits, SeamDirectiveKind.SPLIT)):
                if any(pair == {str(strip.patch_id), neighbour[name]} for name in names):
                    directives.append(SeamDirective(
                        adjacency.chain_id, adjacency.first_patch_id, adjacency.second_patch_id, kind, "test"
                    ))
        _CACHE[key] = (context, _solve_with(context, directives), str(strip.patch_id))
    return _CACHE[key]


@pytest.mark.parametrize(("splits", "width"), (
    (("B", "EB"), 0.2),  # end A stitched leads: the free end B (0.3 long) follows it
    (("B", "EA"), 0.3),  # end B stitched leads
    (("B", "EA", "EB"), None),  # no end stitched: the constraint's width
), ids=("end_a_leads", "end_b_leads", "no_end"))
def test_a_synthetic_strip_with_rail_a_stitched_follows_the_width_rule(splits, width) -> None:
    context, solve, patch_id = _synthetic(STRAIGHT_A, LIFTED_B, joins=("A",), splits=splits)
    ladder = _ladder(context, patch_id).ladder
    island, _skeleton_ = _skeleton(solve, patch_id)
    stitched_ends = [_stitched(context, island, uses) for uses in (ladder.end_a_patch_chain_ids, ladder.end_b_patch_chain_ids)]
    assert stitched_ends == ["EA" not in splits, "EB" not in splits]
    expected = ladder.width if width is None else width
    assert width is None or expected != pytest.approx(ladder.width)  # the rule, not the constraint, gives it
    _check_kept_together(context, solve, patch_id, width=expected, lines_pinned=len(ladder.profile_lines))
    assert not [d for d in solve.diagnostics if "contradictory" in d or "without a pinned profile partner" in d]


def test_with_both_ends_stitched_each_keeps_its_length_and_the_free_rail_runs_straight_between() -> None:
    """Ends 0.2 and 0.3 long, both stitched: the free rail goes straight from one free corner to the other."""

    context, solve, patch_id = _synthetic(STRAIGHT_A, LIFTED_B, joins=("A",), splits=("B",))
    ladder = _ladder(context, patch_id).ladder
    island, skeleton = _skeleton(solve, patch_id)
    assert all(_stitched(context, island, uses) for uses in (ladder.end_a_patch_chain_ids, ladder.end_b_patch_chain_ids))
    assert skeleton.quilt_ladder_by_patch[patch_id] == quilt_ladders.QUILT_LADDER_READ
    pins = _pins(solve, patch_id)
    for line in ladder.profile_lines:
        a, b = pins[str(line.rail_a.vertex_id)], pins[str(line.rail_b.vertex_id)]
        assert a[0] == pytest.approx(b[0], abs=EXACT)
        assert b[1] - a[1] == pytest.approx(0.2 + 0.1 * line.u / ladder.length, rel=EXACT)
    # Paired positive: with one end stitched both ends take its length.
    _c, one, one_id = _synthetic(STRAIGHT_A, LIFTED_B, joins=("A",), splits=("B", "EB"))
    one_pins = _pins(one, one_id)
    last = ladder.profile_lines[-1]
    assert one_pins[str(last.rail_b.vertex_id)][1] - one_pins[str(last.rail_a.vertex_id)][1] == pytest.approx(0.2)


def test_a_strip_whose_stitched_rail_turns_a_corner_is_read_in_two_pieces_with_its_rails_together_in_each() -> None:
    # plan Slice AK: before, a single rail axis was read, so the folded strip was "free rail across" and not read.
    context, solve, patch_id = _synthetic(FOLDED_A, FOLDED_B, joins=("A",), splits=("B", "EB"))
    ladder = _ladder(context, patch_id).ladder
    island, skeleton = _skeleton(solve, patch_id)
    assert skeleton.frame == FRAME_FREE
    assert skeleton.quilt_ladder_by_patch[patch_id] == quilt_ladders.QUILT_LADDER_READ
    # Two runs of the stitched rail meet at the corner line on two axes: that line is in no piece.
    ties = [tie for tie in skeleton.ladder_ties if tie.key[1] == patch_id]
    tied = {tie.key[0]: tie.along_index for tie in ties}
    lines = ladder.profile_lines
    free = [str(line.rail_b.vertex_id if _stitched(context, island, ladder.rail_a_patch_chain_ids) else line.rail_a.vertex_id)
            for line in lines]
    assert free[2] not in tied and len(tied) == len(lines) - 1
    assert len({tied[vertex] for vertex in free[:2]}) == 1 and len({tied[vertex] for vertex in free[3:]}) == 1
    assert tied[free[0]] != tied[free[-1]]
    assert f"{quilt_ladders.PIECES_PREFIX}, 1 profile lines on no piece -> not tied: {patch_id}" in solve.diagnostics
    assert not [d for d in solve.diagnostics if "contradictory" in d or "partner" in d]
    # Rails together in each piece: one coordinate shared, the same distance across throughout the piece.
    pins = _pins(solve, patch_id)
    for piece in (lines[:2], lines[3:]):
        pairs = [(pins[str(line.rail_a.vertex_id)], pins[str(line.rail_b.vertex_id)]) for line in piece]
        along = 0 if abs(pairs[0][0][0] - pairs[0][1][0]) <= EXACT else 1
        for a, b in pairs:
            assert a[along] == pytest.approx(b[along], abs=EXACT)
            assert abs(a[1 - along] - b[1 - along]) == pytest.approx(abs(pairs[0][0][1 - along] - pairs[0][1][1 - along]), abs=EXACT)
    # Paired negative: a straight strip is read in one piece, every line tied on one axis.
    _c, straight, straight_id = _synthetic(STRAIGHT_A, LIFTED_B, joins=("A",), splits=("B", "EB"))
    assert len({tie.along_index for tie in _skeleton(straight, straight_id)[1].ladder_ties}) == 1


class _Line:
    def __init__(self, index):
        self.rail_a = _Vertex(f"a{index}")
        self.rail_b = _Vertex(f"b{index}")
        self.u = float(index)
        self.across = ()


class _Vertex:
    def __init__(self, name):
        self.vertex_id = name
        self.source_vertex_id = name


class _Run:
    def __init__(self, run_id, use, length=1.0):
        self.id, self.patch_id, self.patch_chain_id, self.length = run_id, "strip", use, length


def _fake_strip(free_roles, stitched_roles, line_count=4):
    """A strip of line_count profile lines: rail A stitched, rail B free, one run per step on each rail.

    stitched_roles / free_roles: the role of the run over each step (None: OBLIQUE). Ends: one run each.
    """

    ladder = type("Ladder", (), {})()
    ladder.profile_lines = tuple(_Line(i) for i in range(line_count))
    ladder.rail_a_patch_chain_ids, ladder.rail_b_patch_chain_ids = ("ra",), ("rb",)
    ladder.end_a_patch_chain_ids, ladder.end_b_patch_chain_ids = ("ea",), ("eb",)
    ladder.width, ladder.length = 1.0, float(line_count - 1)
    constraint = type("Constraint", (), {"patch_id": "strip", "ladder": ladder})()
    chains = {"ra": "stitched", "rb": "free", "ea": "end a", "eb": "end b"}
    patch_chain_by_id = {use: type("Use", (), {"chain_id": chain})() for use, chain in chains.items()}
    runs, roles, signs, vertex_by_run_end = [], {}, {}, {}
    for rail, rail_roles in (("a", stitched_roles), ("b", free_roles)):
        for step, role in enumerate(rail_roles):
            e = _Run(f"r{rail}{step}", f"r{rail}")
            runs.append(e)
            roles[e.id] = role or "OBLIQUE"
            signs[e.id] = 1.0
            vertex_by_run_end[(e.id, "START")], vertex_by_run_end[(e.id, "END")] = f"{rail}{step}", f"{rail}{step + 1}"
    for end, line in (("ea", 0), ("eb", line_count - 1)):
        e = _Run(end, end)
        runs.append(e)
        roles[e.id] = "OBLIQUE"
        vertex_by_run_end[(e.id, "START")], vertex_by_run_end[(e.id, "END")] = f"a{line}", f"b{line}"
    island = type("Island", (), {"stitched_chain_ids": ("stitched",)})()
    return constraint, island, runs, roles, signs, vertex_by_run_end, patch_chain_by_id


def test_the_stitched_rail_is_cut_into_pieces_where_its_axis_changes() -> None:
    # A bridged turn: A, an OBLIQUE bridge, B. Each piece ties its own lines along its own axis.
    constraint, island, runs, roles, signs, vertex_by_run_end, uses = _fake_strip(
        ["AXIS_A", None, "AXIS_B"], ["AXIS_A", None, "AXIS_B"]
    )
    diagnostics: list[str] = []
    _lengths, ties, outcomes = quilt_ladders.read_quilt_ladders(
        [constraint], island, runs, roles, signs, vertex_by_run_end, uses, diagnostics
    )
    assert outcomes == {"strip": quilt_ladders.QUILT_LADDER_READ} and diagnostics == []
    assert [(tie.key[0], tie.partner[0], tie.along_index, tie.t, tuple(c[0] for c in tie.corners)) for tie in ties] == [
        ("b0", "a0", 0, 0.0, ("b0", "b1")), ("b1", "a1", 0, 1.0, ("b0", "b1")),
        ("b2", "a2", 1, 0.0, ("b2", "b3")), ("b3", "a3", 1, 1.0, ("b2", "b3")),
    ]
    # The free runs within a piece and on its axis lose their signs; the free bridge keeps its own.
    assert "rb0" not in signs and "rb2" not in signs and signs["rb1"] == 1.0
    # A plain right turn: the corner line is held on both axes and lies in no piece.
    constraint, island, runs, roles, signs, vertex_by_run_end, uses = _fake_strip(["AXIS_A", "AXIS_B"], ["AXIS_A", "AXIS_B"], 3)
    diagnostics = []
    _lengths, ties, outcomes = quilt_ladders.read_quilt_ladders(
        [constraint], island, runs, roles, signs, vertex_by_run_end, uses, diagnostics
    )
    assert outcomes == {"strip": quilt_ladders.QUILT_LADDER_READ}
    assert [(tie.key[0], tie.along_index) for tie in ties] == [("b0", 0), ("b2", 1)]
    assert diagnostics == [f"{quilt_ladders.PIECES_PREFIX}, 1 profile lines on no piece -> not tied: strip"]
    # Two runs of one axis on either side of an OBLIQUE step are two pieces: no run holds that step.
    constraint, island, runs, roles, signs, vertex_by_run_end, uses = _fake_strip(
        ["AXIS_A", None, "AXIS_A"], ["AXIS_A", None, "AXIS_A"]
    )
    _lengths, ties, _outcomes = quilt_ladders.read_quilt_ladders(
        [constraint], island, runs, roles, signs, vertex_by_run_end, uses, []
    )
    assert [tuple(c[0] for c in tie.corners) for tie in ties] == [("b0", "b1")] * 2 + [("b2", "b3")] * 2


def test_a_free_rail_with_a_run_on_the_across_axis_of_its_piece_is_not_read_and_says_so() -> None:
    constraint, island, runs, roles, signs, vertex_by_run_end, uses = _fake_strip(
        ["AXIS_A", "AXIS_B", "AXIS_A"], ["AXIS_A", "AXIS_A", "AXIS_A"]
    )
    diagnostics: list[str] = []
    _lengths, ties, outcomes = quilt_ladders.read_quilt_ladders(
        [constraint], island, runs, roles, signs, vertex_by_run_end, uses, diagnostics
    )
    assert outcomes == {"strip": quilt_ladders.QUILT_LADDER_FREE_RAIL_ACROSS} and ties == ()
    assert diagnostics == [f"{quilt_ladders.NOT_READ_PREFIX}, {quilt_ladders.QUILT_LADDER_FREE_RAIL_ACROSS}: strip"]
    assert all(run_id in signs for run_id in ("rb0", "rb1", "rb2"))
    # Paired positive: the same run on the across axis of the piece it lies in is read (the turn above).
    constraint, island, runs, roles, signs, vertex_by_run_end, uses = _fake_strip(
        ["AXIS_A", "AXIS_B", "AXIS_B"], ["AXIS_A", "AXIS_B", "AXIS_B"]
    )
    assert quilt_ladders.read_quilt_ladders(
        [constraint], island, runs, roles, signs, vertex_by_run_end, uses, []
    )[2] == {"strip": quilt_ladders.QUILT_LADDER_READ}
    # Paired negative: a stitched rail with no signed run on an axis has no piece and is not laid.
    constraint, island, runs, roles, signs, vertex_by_run_end, uses = _fake_strip(["AXIS_A"] * 3, [None] * 3)
    assert quilt_ladders.read_quilt_ladders(
        [constraint], island, runs, roles, signs, vertex_by_run_end, uses, []
    )[2] == {"strip": quilt_ladders.QUILT_LADDER_RAIL_NOT_LAID}


def test_a_strip_in_a_quilt_with_a_rigid_frame_is_unfolded_exactly_and_says_nothing() -> None:
    context, solve, patch_id = _synthetic(STRAIGHT_A, FLAT_B, joins=("A",), splits=("B",))
    _island, skeleton = _skeleton(solve, patch_id)
    assert skeleton.frame == UNFOLDED_FRAME
    assert skeleton.quilt_ladder_by_patch[patch_id] == quilt_ladders.QUILT_LADDER_RIGID_FRAME
    assert _not_read(solve, patch_id) == [] and skeleton.ladder_ties == ()
    position = {str(k): v.position for k, v in context.source_snapshot.vertices.items()}
    pins = [v for v in solve.vertices if v.patch_id == patch_id and v.pinned]
    assert len(pins) >= 4
    for i, a in enumerate(pins):  # planar: every pin at its true distance from every other
        for b in pins[i + 1:]:
            truth = math.dist(position[a.source_vertex_id], position[b.source_vertex_id])
            assert math.dist(a.uv, b.uv) == pytest.approx(truth, rel=1e-9)
    # Paired positive: lifted off the plane, the same quilt is frame-free and reads the strip.
    _c, read, read_id = _synthetic(STRAIGHT_A, LIFTED_B, joins=("A",), splits=("B", "EB"))
    assert _skeleton(read, read_id)[1].frame == FRAME_FREE


def test_tie_free_rails_never_moves_a_run_end_pin_and_unpins_a_vertex_without_partner() -> None:
    corners = (("c0", "p"), ("c1", "p"))
    tie = quilt_ladders.LadderTie(("v", "p"), "s", ("w", "p"), corners, 0.25, 0)
    other = quilt_ladders.LadderTie(("x", "p"), "s2", ("y", "p"), corners, 0.5, 1)
    pins = {("w", "p"): (1.0, 5.0), ("c0", "p"): (0.0, 2.0), ("c1", "p"): (4.0, 4.0), ("x", "p"): (0.5, 0.5)}
    placed, cleared, untied = quilt_ladders.tie_free_rails((tie, other), pins, frozenset())
    # Along from its partner, across a quarter of the way from corner end A to corner end B.
    assert placed == {("v", "p"): ("s", (1.0, 2.5))}
    assert cleared == {("x", "p")} and untied == 1  # its partner y has no pin: the station pin goes
    assert quilt_ladders.tie_free_rails((tie,), pins, frozenset({("v", "p")})) == ({}, set(), 0)
    # One corner pinned: its row.
    one_corner = {key: uv for key, uv in pins.items() if key != ("c1", "p")}
    assert quilt_ladders.tie_free_rails((tie,), one_corner, frozenset())[0] == {("v", "p"): ("s", (1.0, 2.0))}
