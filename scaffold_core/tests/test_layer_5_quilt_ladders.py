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
# An L-shaped strip folded at its corner: each rail has a run on each axis.
FOLDED_A = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 1.0, 0.5), (2.0, 2.0, 1.0)]
FOLDED_B = [(0.0, 0.2, 0.0), (1.0, 0.2, 0.0), (1.8, 0.2, 0.0), (1.8, 1.0, 0.5), (1.8, 2.0, 1.0)]


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


def _check_kept_together(context, solve, patch_id, *, width, lines_pinned):
    """Each profile line with both rail vertices pinned: same place along the stitched rail's axis, width across."""

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
    for a, b in both:
        assert a[along] == pytest.approx(b[along], abs=EXACT)  # no shear
        assert abs(a[1 - along] - b[1 - along]) == pytest.approx(width, rel=EXACT)
    return island, skeleton


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


def test_the_bottom_strip_f36_keeps_its_rails_together_in_its_quilt() -> None:
    plain, up = _rounded()
    solve = run_skeleton_solve(up)
    island, skeleton = _skeleton(solve, F36)
    ladder = _ladder(up, F36).ladder
    ends = [(_stitched(up, island, uses), uses) for uses in (ladder.end_a_patch_chain_ids, ladder.end_b_patch_chain_ids)]
    stitched_ends = [uses for is_stitched, uses in ends if is_stitched]
    width = _end_length(up, stitched_ends[0]) if len(stitched_ends) == 1 else ladder.width
    assert len(stitched_ends) == 1  # one end leads, the other follows it
    _check_kept_together(up, solve, F36, width=width, lines_pinned=20)
    # Two free-rail vertices have a partner without a pin: unpinned and counted.
    assert f"{island.id}: 2 ladder rail vertices without a pinned profile partner -> unpinned" in solve.diagnostics
    assert not [d for d in skeleton.diagnostics if "contradictory" in d]
    # The bottom quilt's pinned edges keep their 3D length (measured mean 0.0077, max 0.084;
    # before Slice AI 0.048 and 0.624, the rails sheared by 0.10).
    errors = _pinned_edge_errors(up, solve, island.id)
    assert len(errors) == 74
    assert sum(errors) / len(errors) < 0.01 and max(errors) < 0.1
    # The wall quilt: its strip f94 develops (no constraint); its 76 pins do not change.
    walls, wall_skeleton = _skeleton(solve, "patch:seed:f94")
    assert sum(1 for v in solve.vertices if v.island_id == walls.id) == 76
    assert dict(wall_skeleton.quilt_ladder_by_patch) == {} and wall_skeleton.ladder_ties == ()
    assert "patch:seed:f94" not in {str(c.patch_id) for c in up.feature_snapshot.constraints}
    # Paired negative: without the filter f36 is an island by itself.
    alone, _alone_skeleton = _skeleton(run_skeleton_solve(plain), F36)
    assert alone.patch_ids == (F36,)


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
    for patch_id in ("patch:seed:f71", "patch:seed:f73", "patch:seed:f96"):
        _island, skeleton = _skeleton(solve, patch_id)
        assert skeleton.quilt_ladder_by_patch[patch_id] == quilt_ladders.QUILT_LADDER_RAIL_NOT_LAID
        assert _not_read(solve, patch_id) == [
            f"{quilt_ladders.NOT_READ_PREFIX}, {quilt_ladders.QUILT_LADDER_RAIL_NOT_LAID}: {patch_id}"
        ]
        assert not [tie for tie in skeleton.ladder_ties if tie.key[1] == patch_id]
    # Paired positive: f36 in the same solve is read.
    assert _skeleton(solve, F36)[1].quilt_ladder_by_patch[F36] == quilt_ladders.QUILT_LADDER_READ


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


def test_a_free_rail_with_a_run_on_the_across_axis_is_not_read_and_says_so() -> None:
    context, solve, patch_id = _synthetic(FOLDED_A, FOLDED_B, joins=("A",), splits=("B",))
    _island, skeleton = _skeleton(solve, patch_id)
    assert skeleton.frame == FRAME_FREE
    assert skeleton.quilt_ladder_by_patch[patch_id] == quilt_ladders.QUILT_LADDER_FREE_RAIL_ACROSS
    assert _not_read(solve, patch_id) == [
        f"{quilt_ladders.NOT_READ_PREFIX}, {quilt_ladders.QUILT_LADDER_FREE_RAIL_ACROSS}: {patch_id}"
    ]
    assert skeleton.ladder_ties == ()
    # Paired positive: a strip whose free rail stays on the rail axis is read.
    _c, read, read_id = _synthetic(STRAIGHT_A, LIFTED_B, joins=("A",), splits=("B", "EB"))
    assert _skeleton(read, read_id)[1].quilt_ladder_by_patch[read_id] == quilt_ladders.QUILT_LADDER_READ


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
