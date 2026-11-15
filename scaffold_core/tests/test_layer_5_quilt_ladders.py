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
from scaffold_core.layer_3_relations.model import RunCornerKind
from scaffold_core.layer_4_features.model import FeatureConstraintKind, FeatureKind
from scaffold_core.layer_5_runtime import frame_free, quilt_ladders
from scaffold_core.layer_5_runtime import skeleton as skeleton_module
from scaffold_core.layer_5_runtime.pins import run_skeleton_solve
from scaffold_core.layer_5_runtime.skeleton import FRAME_FREE, UNFOLDED_FRAME
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations, run_pass_2_features, run_pass_3_filters
from scaffold_core.tests.fixtures.bevel_patches import make_marked_cut_ring_source, make_marked_ladder_strip_source
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
    # the drift of the 7 m quilt, not of the 0.42 m across it (plan Slice AK). 69 source vertices pinned:
    # 61 before plan Slice AL, which made f73's stitched rail one line and pinned the four inner-side vertices
    # of f111's curved middle (v168..v174) and their four profile partners on f73's free rail.
    assert len({v.source_vertex_id for v in solve.vertices if v.island_id == island.id and v.pinned}) == 69
    # Pinned edges: f111 and f73 are now laid straight along f36 and keep their lengths only roughly
    # (measured 137 edges, mean 0.031; f111 max 0.24). The worst is f36's mitre edge on its free rail,
    # v209-v211, 40.8 mm in 3D and laid w * sqrt(2) = 0.107 around the square turn. Before the slice:
    # 74 edges, mean 0.0077, max 0.084, and the corner folded over after the fill. Plan Slice AL: 167 edges
    # (137 before it, mean 0.031, second largest 0.24); f111's inner side and f73's rails now take the band's
    # 0.63 m of difference evenly along their whole length (6.865 on 6.233, 10.1 % on every one of those
    # edges, as the user's own layout does with 9.5 %) instead of 34 % on the middle edges alone.
    errors = _pinned_edge_errors(up, solve, island.id)
    assert len(errors) == 167
    assert sum(errors) / len(errors) < 0.05 and sorted(errors)[-2] < 0.19 and max(errors) == pytest.approx(1.61, abs=0.01)
    # The wall quilt: its strip f94 develops (no constraint); its 76 pins do not change.
    walls, wall_skeleton = _skeleton(solve, "patch:seed:f94")
    assert sum(1 for v in solve.vertices if v.island_id == walls.id) == 76
    assert dict(wall_skeleton.quilt_ladder_by_patch) == {} and wall_skeleton.ladder_ties == ()
    assert "patch:seed:f94" not in {str(c.patch_id) for c in up.feature_snapshot.constraints}
    # Paired negative: without the filter f36 is an island by itself.
    alone, _alone_skeleton = _skeleton(run_skeleton_solve(plain), F36)
    assert alone.patch_ids == (F36,)
    # Paired negative: without the join f73 is not read and the quilt pins fewer source vertices.
    monkeypatch.setattr(frame_free, "join_stitched_lines", lambda runs, line_of, signs, stitched, diagnostics: (line_of, signs, None))
    apart = run_skeleton_solve(up)
    _island_apart, skeleton_apart = _skeleton(apart, F36)
    assert any(skeleton_apart.line_by_run[a] != skeleton_apart.line_by_run[b] for a, b in pairs)
    assert skeleton_apart.quilt_ladder_by_patch["patch:seed:f73"] == quilt_ladders.QUILT_LADDER_RAIL_NOT_LAID
    assert len({v.source_vertex_id for v in apart.vertices if v.island_id == island.id and v.pinned}) < 61


def test_the_mark_makes_f73s_coarse_stitched_rail_one_line_laid_evenly_and_read_in_one_piece() -> None:
    # plan Slice AL: f111's inner side (f73's stitched rail) turns 6.5-12.4 degrees per vertex, so Layer 3
    # cuts it into 7 lines; the middle five were reached by no right corner and laid by nothing. The mark
    # makes it one line, which gives no length (6.233 m in 3D between ends the quilt fixes 6.865 apart).
    _plain, up = _rounded()
    solve = run_skeleton_solve(up)
    f73, f111 = "patch:seed:f73", "patch:seed:f111"
    island, skeleton = _skeleton(solve, f73)
    assert f"{frame_free.MARKED_RAIL_PREFIX} from 7 lines, no length equation, 6.2331 m in 3D laid at 6.8648 m:" \
           f" {f73} (v160..v157)" in skeleton.diagnostics
    ladder = _ladder(up, f73).ladder
    ties = [tie for tie in skeleton.ladder_ties if tie.key[1] == f73]
    assert len(ties) == len(ladder.profile_lines) == 12  # one piece: every profile line tied
    assert len({tie.along_index for tie in ties}) == 1
    along = ties[0].along_index
    # The inner side: every run-end node on the inner row, stations in proportion to 3D length.
    position = {str(k): v.position for k, v in up.source_snapshot.vertices.items()}
    pin = {v.source_vertex_id: v.uv for v in solve.vertices if v.patch_id == f111 and v.pinned}
    inner = ["v160", "v180", "v178", "v176", "v174", "v172", "v170", "v168", "v166", "v164", "v162", "v157"]
    assert {"v174", "v172", "v170", "v168"} <= set(pin)
    assert all(pin[v][1 - along] == pytest.approx(pin["v160"][1 - along], abs=EXACT) for v in inner)
    ratios = [abs(pin[b][along] - pin[a][along]) / math.dist(position[a], position[b]) for a, b in zip(inner, inner[1:])]
    assert max(ratios) - min(ratios) < 1e-9 and ratios[0] == pytest.approx(6.8648 / 6.2331, abs=1e-4)
    inner_runs = [e for e in up.relation_snapshot.patch_chain_directional_evidence if e.patch_chain_id == f"patch_chain:{f111}:0:1"]
    assert inner_runs and all(e.id in skeleton.unmeasured_run_ids for e in inner_runs)
    stitched_rail = [e for e in up.relation_snapshot.patch_chain_directional_evidence
                     if e.patch_chain_id in ladder.rail_a_patch_chain_ids + ladder.rail_b_patch_chain_ids
                     and str(e.parent_chain_id) in island.stitched_chain_ids]
    assert stitched_rail and all(e.id in skeleton.unmeasured_run_ids for e in stitched_rail)
    # Only the rail's Chain is unmeasured: f95's side, which Layer 3 continues from the inner side on the same
    # line beyond the rail's end, keeps its length equation.
    assert set(skeleton.unmeasured_run_ids) == {e.id for e in inner_runs + stitched_rail}
    f95_side = "patch_chain_directional_evidence:patch_chain:patch:seed:f95:0:3:0"
    assert skeleton.line_by_run[f95_side] == skeleton.line_by_run[inner_runs[0].id]
    # The outer side (f36's stitched rail) already was one line: it keeps its length equations, laid at 1:1.
    outer_runs = [e for e in up.relation_snapshot.patch_chain_directional_evidence if e.patch_chain_id == f"patch_chain:{f111}:0:0"]
    assert outer_runs and not any(e.id in skeleton.unmeasured_run_ids for e in outer_runs)
    arc_line = skeleton.line_by_run[max(outer_runs, key=lambda e: (e.length, e.id)).id]  # the 90-degree arc, one line
    straight = [e for e in outer_runs if skeleton.line_by_run[e.id] == arc_line]
    assert len(straight) == 17
    for e in straight:
        start, end = pin[str(e.start_source_vertex_id)], pin[str(e.end_source_vertex_id)]
        assert math.dist(start, end) == pytest.approx(e.length, rel=1e-4)
    assert not [d for d in skeleton.diagnostics if "contradictory" in d or d.startswith(quilt_ladders.PIECES_PREFIX)]
    # The top quilt (noisy f0) still pins nothing: its mark joins are not made (see the f71 test).
    top, _top_skeleton = _skeleton(solve, "patch:seed:f35")
    assert not [v for v in solve.vertices if v.island_id == top.id and v.pinned]


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
    # Plan Slice AL: on the noisy top f0 the marked rails made one line would meet right corners of both axes,
    # so none of the top quilt's mark joins is made and its lines stay Layer 3's (no conflict, no stations).
    assert f"{frame_free.MARKED_RAILS_KEPT_PREFIX}: patch:seed:f35, patch:seed:f71, patch:seed:f96" in skeleton.diagnostics
    assert not [d for d in skeleton.diagnostics if "conflict" in d or d.startswith(frame_free.MARKED_RAIL_PREFIX)]
    assert skeleton.unmeasured_run_ids == frozenset()
    # Paired positive: f36 in the same solve is read; so is f73 since plan Slice AK, its stitched rail lying
    # on f111, whose side on f36 is one line with f36's rail. Since plan Slice AL its rail on f111 is one line
    # around f111's curved middle, read in one piece: every profile line tied.
    assert _skeleton(solve, F36)[1].quilt_ladder_by_patch[F36] == quilt_ladders.QUILT_LADDER_READ
    f73 = "patch:seed:f73"
    assert _skeleton(solve, f73)[1].quilt_ladder_by_patch[f73] == quilt_ladders.QUILT_LADDER_READ
    assert not [d for d in solve.diagnostics if d.startswith(quilt_ladders.PIECES_PREFIX) and d.endswith(f73)]


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


def _synthetic(rail_a, rail_b, joins=(), splits=(), beyond_a=None, moved=()):
    """A marked strip and its four neighbours; JOIN / SPLIT the strip's seams to the named ones (A, B, EA, EB).

    beyond_a: the far side of the neighbour beyond rail A (default: rail A mirrored); moved: (vertex, position)
    pairs placed after the fixture is built.
    """

    key = (tuple(rail_a), tuple(rail_b), tuple(joins), tuple(splits), tuple(beyond_a or ()), tuple(moved))
    if key not in _CACHE:
        source = make_marked_ladder_strip_source(rail_a, rail_b, beyond_a=beyond_a)
        if moved:
            positions = dict(moved)
            source = replace(source, vertices={
                vertex_id: replace(ref, position=positions.get(str(vertex_id), ref.position))
                for vertex_id, ref in source.vertices.items()
            })
        context = run_pass_2_features(run_pass_1_relations(run_pass_0(source)))
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
        _DIRECTIVES[key] = tuple(directives)
        _CACHE[key] = (context, _solve_with(context, directives), str(strip.patch_id))
    return _CACHE[key]


_DIRECTIVES: dict = {}


def _without_mark_joins(monkeypatch, *args, **kwargs):
    """The solve of the same synthetic quilt with the mark joins switched off: the lines as HEAD had them."""

    context, _solve, patch_id = _synthetic(*args, **kwargs)
    key = (tuple(args[0]), tuple(args[1]), tuple(kwargs.get("joins", ())), tuple(kwargs.get("splits", ())),
           tuple(kwargs.get("beyond_a") or ()), tuple(kwargs.get("moved", ())))
    monkeypatch.setattr(
        skeleton_module, "_join_marked_rails",
        lambda _island, _runs, line_of, signs, length_by_line, *_rest: (line_of, signs, length_by_line, None, ()),
    )
    return context, _solve_with(context, _DIRECTIVES[key]), patch_id


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


# --------------------------------------------------------------------------- the mark makes the stitched rail one line


# Rail A bends in the plane by 16.7 degrees at four vertices (a coarse arc: each junction stops its Layer 3
# family), rail B follows it lifted in the middle (no rigid frame). The neighbour beyond rail A is a flat row
# whose far side is straight and 5 m long: the quilt fixes rail A's two ends 5 m apart.
BUMP_A = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.3, 0.0), (3.0, 0.3, 0.0), (4.0, 0.0, 0.0), (5.0, 0.0, 0.0)]
BUMP_B = [(0.0, 0.3, 0.0), (1.0, 0.3, 0.0), (2.0, 0.6, 0.2), (3.0, 0.6, 0.2), (4.0, 0.3, 0.0), (5.0, 0.3, 0.0)]
FAR_A = [(float(i), -1.0, 0.0) for i in range(6)]


def _rail_runs(context, skeleton, uses):
    runs = [e for e in context.relation_snapshot.patch_chain_directional_evidence if e.patch_chain_id in uses]
    return sorted((e for e in runs if e.id in skeleton.axis_role_by_run), key=lambda e: min(e.segment_indices))


def _families(context, runs):
    family_of = {m: f.id for f in context.relation_snapshot.connected_direction_families for m in f.member_directional_evidence_ids}
    return {family_of.get(e.id) for e in runs}


def test_a_marked_rail_cut_into_several_lines_is_one_line_with_no_length_and_stations_by_3d_length() -> None:
    context, solve, patch_id = _synthetic(BUMP_A, BUMP_B, joins=("A",), splits=("B", "EB"), beyond_a=FAR_A)
    ladder = _ladder(context, patch_id).ladder
    island, skeleton = _skeleton(solve, patch_id)
    assert skeleton.frame == FRAME_FREE and _stitched(context, island, ladder.rail_a_patch_chain_ids)
    rail = _rail_runs(context, skeleton, ladder.rail_a_patch_chain_ids)
    assert len(rail) == 5 and len(_families(context, rail)) == 5  # Layer 3: five lines
    # One island line; its runs (and the neighbour's runs on the same segments) give no length equation.
    stitched_chain = str(rail[0].parent_chain_id)
    sides = [e for e in context.relation_snapshot.patch_chain_directional_evidence if str(e.parent_chain_id) == stitched_chain]
    assert len(sides) == 10 and len({skeleton.line_by_run[e.id] for e in sides}) == 1
    # Only the runs on the rail's Chain are unmeasured (its two sides). The side of the junction at end B that
    # Layer 3 continues straight from the rail's last run shares the line and keeps its length equation.
    line = skeleton.line_by_run[rail[0].id]
    on_line = {run_id for run_id, line_id in skeleton.line_by_run.items() if line_id == line}
    assert set(skeleton.unmeasured_run_ids) == {e.id for e in sides}
    assert len(on_line - {e.id for e in sides}) == 1  # the junction's side: on the line, measured
    length = sum(e.length for e in rail)
    assert length == pytest.approx(5.0881, abs=1e-4)
    first, last = (str(ladder.profile_lines[i].rail_a.source_vertex_id) for i in (0, -1))
    names = {f"{patch_id} ({first}..{last})", f"{patch_id} ({last}..{first})"}
    marked = [d for d in solve.diagnostics if d.startswith(frame_free.MARKED_RAIL_PREFIX)]
    assert len(marked) == 1  # one diagnostic per stretch
    head = f"{frame_free.MARKED_RAIL_PREFIX} from 5 lines, no length equation, {length:.4f} m in 3D laid at 5.0000 m: "
    assert marked[0].startswith(head) and marked[0][len(head):] in names
    assert not [d for d in solve.diagnostics if "contradictory" in d or "partner" in d or d.startswith(quilt_ladders.PIECES_PREFIX)]
    # Its nodes lie on one row, at stations in proportion to 3D length between its two laid ends.
    pins = _pins(solve, patch_id)
    along = _rail_axis(context, skeleton, ladder.rail_a_patch_chain_ids)
    rail_pins = [pins[str(line.rail_a.vertex_id)] for line in ladder.profile_lines]
    assert all(p[1 - along] == pytest.approx(rail_pins[0][1 - along], abs=EXACT) for p in rail_pins)
    walked = [0.0]
    for a, b in zip(BUMP_A, BUMP_A[1:]):
        walked.append(walked[-1] + math.dist(a, b))
    for p, w in zip(rail_pins, walked):
        assert abs(p[along] - rail_pins[0][along]) == pytest.approx(5.0 * w / walked[-1], abs=1e-9)
    # Read in one piece: every profile line tied, the rails together across the end's width.
    _check_kept_together(context, solve, patch_id, width=0.3, lines_pinned=len(ladder.profile_lines))
    assert len([tie for tie in skeleton.ladder_ties if tie.key[1] == patch_id]) == len(ladder.profile_lines)


def test_the_free_rail_of_a_marked_strip_is_not_joined() -> None:
    context, solve, patch_id = _synthetic(BUMP_A, BUMP_B, joins=("A",), splits=("B", "EB"), beyond_a=FAR_A)
    ladder = _ladder(context, patch_id).ladder
    _island, skeleton = _skeleton(solve, patch_id)
    free = _rail_runs(context, skeleton, ladder.rail_b_patch_chain_ids)
    assert len(free) == 5 and len({skeleton.line_by_run[e.id] for e in free}) == 5
    assert not any(e.id in skeleton.unmeasured_run_ids for e in free)
    # Paired positive: the stitched rail beside it is one line.
    assert len({skeleton.line_by_run[e.id] for e in _rail_runs(context, skeleton, ladder.rail_a_patch_chain_ids)}) == 1


def test_a_marked_rail_with_fewer_than_two_laid_nodes_gets_no_stations_and_says_so() -> None:
    # The neighbour's far side mirrors rail A's coarse arc: nothing in the quilt ties rail A's two ends.
    context, solve, patch_id = _synthetic(BUMP_A, BUMP_B, joins=("A",), splits=("B", "EB"))
    ladder = _ladder(context, patch_id).ladder
    _island, skeleton = _skeleton(solve, patch_id)
    assert skeleton.unmeasured_run_ids
    marked = [d for d in solve.diagnostics if d.startswith(frame_free.MARKED_RAIL_PREFIX)]
    assert len(marked) == 1 and marked[0].startswith(
        f"{frame_free.MARKED_RAIL_PREFIX} from 5 lines, no length equation, 5.0881 m in 3D, "
        f"no stations: fewer than two of its nodes are laid: {patch_id} ("
    )
    pins = _pins(solve, patch_id)
    inner = [str(line.rail_a.vertex_id) for line in ladder.profile_lines[1:-1]]
    assert not [vertex for vertex in inner if vertex in pins]  # no stations, no extrapolation
    # Paired positive: with the straight far side both ends are laid and every inner node is a station.
    _c, laid, laid_id = _synthetic(BUMP_A, BUMP_B, joins=("A",), splits=("B", "EB"), beyond_a=FAR_A)
    assert all(vertex in _pins(laid, laid_id) for vertex in inner)


def test_on_the_mirrored_case_the_mark_loses_pins_head_had_as_a_stated_limit(monkeypatch) -> None:
    # Rule 2 is unconditional: the joined rail gives no length equation even where nothing else in the quilt
    # ties its two ends. Without the join (HEAD) the rail's Layer 3 lines keep their lengths and pin p1_0 and
    # p1_1 (rail A on profile lines 0 and 1); with the join neither is laid. The slice states this price.
    context, solve, patch_id = _synthetic(BUMP_A, BUMP_B, joins=("A",), splits=("B", "EB"))
    _c, head, _p = _without_mark_joins(monkeypatch, BUMP_A, BUMP_B, joins=("A",), splits=("B", "EB"))
    head_pins, pins = _pins(head, patch_id), _pins(solve, patch_id)
    lost = sorted(vertex for vertex in head_pins if vertex not in pins)
    assert lost == ["vertex:p1_0", "vertex:p1_1"]
    assert not [vertex for vertex in pins if vertex not in head_pins]
    # Paired positive: with the straight far side the joined rail is laid and keeps them.
    _c, laid, laid_id = _synthetic(BUMP_A, BUMP_B, joins=("A",), splits=("B", "EB"), beyond_a=FAR_A)
    assert all(vertex in _pins(laid, laid_id) for vertex in lost)


def test_a_marked_rail_that_already_is_one_line_keeps_its_length_equations() -> None:
    context, solve, patch_id = _synthetic(STRAIGHT_A, LIFTED_B, joins=("A",), splits=("B", "EB"))
    ladder = _ladder(context, patch_id).ladder
    _island, skeleton = _skeleton(solve, patch_id)
    rail = _rail_runs(context, skeleton, ladder.rail_a_patch_chain_ids)
    assert len({skeleton.line_by_run[e.id] for e in rail}) == 1
    assert skeleton.unmeasured_run_ids == frozenset()
    assert not [d for d in solve.diagnostics if d.startswith(frame_free.MARKED_RAIL_PREFIX)]
    pins = _pins(solve, patch_id)
    ends = [pins[str(line.rail_a.vertex_id)] for line in (ladder.profile_lines[0], ladder.profile_lines[-1])]
    assert math.dist(*ends) == pytest.approx(3.0, abs=EXACT)  # laid at its length
    # Paired negative: a rail the mark made from several lines gives no length.
    _c, bump, bump_id = _synthetic(BUMP_A, BUMP_B, joins=("A",), splits=("B", "EB"), beyond_a=FAR_A)
    assert _skeleton(bump, bump_id)[1].unmeasured_run_ids


def test_a_right_corner_on_the_marked_rail_cuts_the_join() -> None:
    # The folded strip's stitched rail turns a right corner (on both sides of its Chain): two lines, each with
    # its own length, read in two pieces as in plan Slice AK. The bridged case, cut on the neighbour's side
    # only, is f36's mitre on the user's mesh (test_the_bottom_strip_f36_keeps_its_rails_together_in_its_quilt).
    context, solve, patch_id = _synthetic(FOLDED_A, FOLDED_B, joins=("A",), splits=("B", "EB"))
    ladder = _ladder(context, patch_id).ladder
    _island, skeleton = _skeleton(solve, patch_id)
    rail = _rail_runs(context, skeleton, ladder.rail_a_patch_chain_ids)
    assert len({skeleton.line_by_run[e.id] for e in rail}) == 2
    assert {skeleton.axis_role_by_run[e.id] for e in rail} == {"AXIS_A", "AXIS_B"}
    assert skeleton.unmeasured_run_ids == frozenset()
    assert not [d for d in solve.diagnostics if d.startswith(frame_free.MARKED_RAIL_PREFIX)]
    # Paired positive: without a corner the rail Layer 3 cut is joined (the bump above).
    _c, bump, bump_id = _synthetic(BUMP_A, BUMP_B, joins=("A",), splits=("B", "EB"), beyond_a=FAR_A)
    assert any(d.startswith(frame_free.MARKED_RAIL_PREFIX) for d in bump.diagnostics)


# Rail A turns a right corner at one vertex; the free rail turns it over three vertices, so it has no RIGHT or
# bridged corner and joining rail A across its corner brings the quilt no conflict: only the cut keeps it apart.
CUT_A = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.6, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 0.5, 0.15), (2.0, 1.0, 0.3),
         (2.0, 2.0, 0.6)]
CUT_B = [(0.0, 0.1, 0.0), (1.0, 0.1, 0.0), (1.6, 0.1, 0.0), (1.85, 0.15, 0.0), (1.9, 0.4, 0.12), (1.9, 1.0, 0.3),
         (1.9, 2.0, 0.6)]


def test_a_right_corner_on_the_marked_rail_cuts_the_join_where_no_conflict_would_stop_it() -> None:
    context, solve, patch_id = _synthetic(CUT_A, CUT_B, joins=("A",), splits=("B", "EB"))
    ladder = _ladder(context, patch_id).ladder
    _island, skeleton = _skeleton(solve, patch_id)
    assert skeleton.frame == FRAME_FREE
    rail = _rail_runs(context, skeleton, ladder.rail_a_patch_chain_ids)
    assert len(rail) == 2 and len({skeleton.line_by_run[e.id] for e in rail}) == 2
    assert [skeleton.axis_role_by_run[e.id] for e in rail] == ["AXIS_A", "AXIS_B"]
    # The free rail turns its corner with no RIGHT and no bridged corner between two of its runs.
    free = {e.id for e in context.relation_snapshot.patch_chain_directional_evidence
            if e.patch_chain_id in ladder.rail_b_patch_chain_ids}
    relations = context.relation_snapshot
    assert not [c for c in relations.run_corner_relations if c.kind is RunCornerKind.RIGHT
                and c.first_directional_evidence_id in free and c.second_directional_evidence_id in free]
    assert not [c for c in relations.run_bridged_corner_relations if c.bridge_directional_evidence_id in free]
    assert skeleton.unmeasured_run_ids == frozenset()
    assert not [d for d in solve.diagnostics if d.startswith((frame_free.MARKED_RAIL_PREFIX, frame_free.MARKED_RAILS_KEPT_PREFIX))]
    # Paired positive: without a corner the rail Layer 3 cut is joined (the bump).
    _c, bump, bump_id = _synthetic(BUMP_A, BUMP_B, joins=("A",), splits=("B", "EB"), beyond_a=FAR_A)
    assert any(d.startswith(frame_free.MARKED_RAIL_PREFIX) for d in bump.diagnostics)


def test_when_the_lines_conflict_without_the_joins_too_the_result_is_that_without_the_mark(monkeypatch) -> None:
    # No capture has an island whose own lines conflict; a conflict is injected in every bipartition: its
    # first reached line (by id) is degraded to OBLIQUE, as a conflict does. The joins then fall back, the
    # result equals the run without mark joins, and the diagnostic still holds.
    real = frame_free.bipartition_families

    def conflicting(*args, **kwargs):
        axis_by_line = dict(real(*args, **kwargs))
        if axis_by_line:
            axis_by_line[min(axis_by_line)] = "OBLIQUE"
        return axis_by_line

    monkeypatch.setattr(frame_free, "bipartition_families", conflicting)
    context, _cached, patch_id = _synthetic(BUMP_A, BUMP_B, joins=("A",), splits=("B", "EB"), beyond_a=FAR_A)
    directives = _DIRECTIVES[(tuple(BUMP_A), tuple(BUMP_B), ("A",), ("B", "EB"), tuple(FAR_A), ())]
    solve = _solve_with(context, directives)
    _island, skeleton = _skeleton(solve, patch_id)
    assert f"{frame_free.MARKED_RAILS_KEPT_PREFIX}: {patch_id}" in skeleton.diagnostics
    assert skeleton.unmeasured_run_ids == frozenset()
    monkeypatch.setattr(
        skeleton_module, "_join_marked_rails",
        lambda _island, _runs, line_of, signs, length_by_line, *_rest: (line_of, signs, length_by_line, None, ()),
    )
    head = _solve_with(context, directives)
    _head_island, before = _skeleton(head, patch_id)
    assert skeleton.line_by_run == before.line_by_run and skeleton.axis_role_by_run == before.axis_role_by_run
    assert _pins(solve, patch_id) == _pins(head, patch_id)
    assert [d for d in skeleton.diagnostics if not d.startswith(frame_free.MARKED_RAILS_KEPT_PREFIX)] == list(before.diagnostics)


class _RailRun:
    def __init__(self, index, length, orientation_sign):
        ends = (f"s{index}", f"s{index + 1}")  # along the Chain's segment order
        self.id, self.length, self.orientation_sign = f"r{index}", length, orientation_sign
        self.start_source_vertex_id, self.end_source_vertex_id = ends if orientation_sign == 1 else ends[::-1]


@pytest.mark.parametrize("orientation_sign", (1, -1), ids=("use_forward", "use_backward"))
def test_stations_lie_between_laid_nodes_by_length_and_never_beyond_them(orientation_sign) -> None:
    # Runs of 1, 2, 1, 1 m; the solve laid only the nodes s1 and s3: s2 is a station, s0 and s4 stay unlaid.
    runs = [_RailRun(i, length, orientation_sign) for i, length in enumerate((1.0, 2.0, 1.0, 1.0))]
    node_by_run_end = {
        (e.id, role): f"n{source[1:]}"
        for e in runs for role, source in (("START", e.start_source_vertex_id), ("END", e.end_source_vertex_id))
    }
    roles = {e.id: "AXIS_A" for e in runs}
    coordinates = {"AXIS_A": {"n1": 10.0, "n3": 14.0}, "AXIS_B": {f"n{i}": 0.5 for i in range(5)}}
    rail = frame_free.MarkedRail("strip", "chain", "line", tuple(e.id for e in runs), 3, "strip (s0..s4)")
    diagnostics: list[str] = []
    placed = frame_free.station_marked_rails((rail,), runs, roles, node_by_run_end, coordinates, diagnostics)
    assert placed["AXIS_A"] == {"n1": 10.0, "n2": pytest.approx(10.0 + 4.0 * 2.0 / 3.0), "n3": 14.0}
    assert placed["AXIS_B"] == coordinates["AXIS_B"] and coordinates["AXIS_A"] == {"n1": 10.0, "n3": 14.0}
    head = f"{frame_free.MARKED_RAIL_PREFIX} from 3 lines, no length equation, 5.0000 m in 3D"
    assert diagnostics == [f"{head}, its ends not both laid: strip (s0..s4)"]
    # Both ends laid: the length it is laid at.
    diagnostics = []
    ends = {"AXIS_A": {"n0": 0.0, "n4": 4.0}, "AXIS_B": coordinates["AXIS_B"]}
    placed = frame_free.station_marked_rails((rail,), runs, roles, node_by_run_end, ends, diagnostics)
    assert placed["AXIS_A"]["n1"] == pytest.approx(0.8) and placed["AXIS_A"]["n3"] == pytest.approx(3.2)
    assert diagnostics == [f"{head} laid at 4.0000 m: strip (s0..s4)"]
    # One laid node: no stations, one diagnostic.
    diagnostics = []
    one_node = {"AXIS_A": {"n1": 10.0}, "AXIS_B": coordinates["AXIS_B"]}
    assert frame_free.station_marked_rails((rail,), runs, roles, node_by_run_end, one_node, diagnostics) == one_node
    assert diagnostics == [f"{head}, no stations: fewer than two of its nodes are laid: strip (s0..s4)"]
    # Paired negative: a rail that already was one line (line_count 1) gets no stations and says nothing.
    diagnostics = []
    one = frame_free.MarkedRail("strip", "chain", "line", rail.run_ids, 1, "strip (s0..s4)")
    assert frame_free.station_marked_rails((one,), runs, roles, node_by_run_end, coordinates, diagnostics) == coordinates
    assert diagnostics == []


def _source_pins(solve, island):
    pins: dict = {}
    for v in solve.vertices:
        if v.island_id == island.id and v.pinned:
            pins.setdefault(str(v.source_vertex_id), v.uv)
    return pins


def test_a_strip_with_both_rails_stitched_is_not_joined_and_says_nothing() -> None:
    context, solve, patch_id = _synthetic(BUMP_A, BUMP_B, joins=("A", "B"), splits=("EB",), beyond_a=FAR_A)
    ladder = _ladder(context, patch_id).ladder
    island, skeleton = _skeleton(solve, patch_id)
    assert all(_stitched(context, island, uses) for uses in (ladder.rail_a_patch_chain_ids, ladder.rail_b_patch_chain_ids))
    assert skeleton.unmeasured_run_ids == frozenset()
    assert len({skeleton.line_by_run[e.id] for e in _rail_runs(context, skeleton, ladder.rail_a_patch_chain_ids)}) == 5
    assert not [d for d in solve.diagnostics if d.startswith((frame_free.MARKED_RAIL_PREFIX, frame_free.MARKED_RAILS_KEPT_PREFIX))]
    # Paired positive: with rail B split off, rail A is joined.
    _c, one, one_id = _synthetic(BUMP_A, BUMP_B, joins=("A",), splits=("B", "EB"), beyond_a=FAR_A)
    assert _skeleton(one, one_id)[1].unmeasured_run_ids


def test_a_run_beside_the_marked_rail_on_its_joined_line_keeps_its_length_and_its_pin(monkeypatch) -> None:
    # The junction at end A turned so that its side off the rail's first node is not the free rail's line:
    # the junction's runs on the joined line are not on the rail's Chain and keep their length equations.
    # Its corner ea0, 1 m beyond p0_0 along the rail, stays pinned as it is without the mark join.
    moved = (("ea1", (-0.6, 0.8, 0.0)),)
    context, solve, patch_id = _synthetic(BUMP_A, BUMP_B, joins=("A",), splits=("B", "EB"), beyond_a=FAR_A, moved=moved)
    ladder = _ladder(context, patch_id).ladder
    island, skeleton = _skeleton(solve, patch_id)
    chains = {str(context.topology_snapshot.patch_chains[use].chain_id) for use in ladder.rail_a_patch_chain_ids}
    evidence = {e.id: e for e in context.relation_snapshot.patch_chain_directional_evidence}
    assert skeleton.unmeasured_run_ids and all(
        str(evidence[run_id].parent_chain_id) in chains for run_id in skeleton.unmeasured_run_ids
    )
    line = skeleton.line_by_run[_rail_runs(context, skeleton, ladder.rail_a_patch_chain_ids)[0].id]
    beside = [run_id for run_id, line_id in skeleton.line_by_run.items()
              if line_id == line and str(evidence[run_id].parent_chain_id) not in chains]
    assert beside and not [run_id for run_id in beside if run_id in skeleton.unmeasured_run_ids]
    pins = _source_pins(solve, island)
    assert math.dist(pins["ea0"], pins["p0_0"]) == pytest.approx(1.0, abs=1e-9)
    assert skeleton.quilt_ladder_by_patch[patch_id] == quilt_ladders.QUILT_LADDER_READ
    # Paired: without the mark joins (HEAD) ea0 is pinned at the same distance.
    _c, head, _p = _without_mark_joins(
        monkeypatch, BUMP_A, BUMP_B, joins=("A",), splits=("B", "EB"), beyond_a=FAR_A, moved=moved
    )
    head_pins = _source_pins(head, _skeleton(head, patch_id)[0])
    assert math.dist(head_pins["ea0"], head_pins["p0_0"]) == pytest.approx(1.0, abs=1e-9)


def test_the_join_keeps_the_parity_of_the_stitched_rails_two_sides() -> None:
    # The two sides of the stitched rail walk the Chain in opposite directions: the joined line lays them
    # on one row with the rail's nodes in order, each at its station; a flipped parity reverses one side.
    context, solve, patch_id = _synthetic(BUMP_A, BUMP_B, joins=("A",), splits=("B", "EB"), beyond_a=FAR_A)
    ladder = _ladder(context, patch_id).ladder
    island, skeleton = _skeleton(solve, patch_id)
    # Every run of the rail's Chain, on either side, points the same way along the joined line walking the
    # Chain forward: its line sign times its orientation sign is one value.
    evidence = context.relation_snapshot.patch_chain_directional_evidence
    chain = str(_rail_runs(context, skeleton, ladder.rail_a_patch_chain_ids)[0].parent_chain_id)
    sides = [e for e in evidence if str(e.parent_chain_id) == chain]
    assert len(sides) == 10
    assert {skeleton.orientation_by_run[e.id] * e.orientation_sign for e in sides} == {1.0} or \
        {skeleton.orientation_by_run[e.id] * e.orientation_sign for e in sides} == {-1.0}
    pins = _source_pins(solve, island)
    rail = [str(line.rail_a.source_vertex_id) for line in ladder.profile_lines]
    beyond = [f"oa{i}" for i in range(len(rail))]
    along = _rail_axis(context, skeleton, ladder.rail_a_patch_chain_ids)
    walked = [0.0]
    for a, b in zip(BUMP_A, BUMP_A[1:]):
        walked.append(walked[-1] + math.dist(a, b))
    start = pins[rail[0]][along]
    direction = math.copysign(1.0, pins[rail[-1]][along] - start)
    for vertex, w in zip(rail, walked):
        assert (pins[vertex][along] - start) * direction == pytest.approx(5.0 * w / walked[-1], abs=1e-9)
    # The row beyond keeps its own lengths (1 m each), in the same direction as the rail.
    for i, vertex in enumerate(beyond):
        assert (pins[vertex][along] - pins[beyond[0]][along]) * direction == pytest.approx(float(i), abs=1e-9)
    assert not [d for d in solve.diagnostics if "contradictory" in d]


def test_a_closed_marked_rail_is_never_joined_across_its_own_cut() -> None:
    # The marked cut ring with its inner and outer rings lifted (no rigid frame): rail A's use is closed, both
    # its ends are r1_0 (the SEAM_SELF cut). Its runs are ordered from the use's start; the stretch runs from
    # r1_0 around to r1_0 and no pair is joined at the cut.
    source = make_marked_cut_ring_source(12)
    source = replace(source, vertices={
        vertex_id: replace(ref, position=(ref.position[0], ref.position[1], 0.5))
        if str(vertex_id).startswith(("r0_", "r3_")) else ref
        for vertex_id, ref in source.vertices.items()
    })
    context = run_pass_2_features(run_pass_1_relations(run_pass_0(source)))
    (strip,) = [r for r in context.feature_snapshot.bevels if r.kind is FeatureKind.BEVEL_STRIP]
    patch_id = str(strip.patch_id)
    neighbour = {"A": str(strip.rail_a_neighbour_patch_ids[0]), "B": str(strip.rail_b_neighbour_patch_ids[0])}
    directives = [
        SeamDirective(adjacency.chain_id, adjacency.first_patch_id, adjacency.second_patch_id, kind, "test")
        for adjacency in context.relation_snapshot.patch_adjacencies.values()
        for name, kind in (("A", SeamDirectiveKind.JOIN), ("B", SeamDirectiveKind.SPLIT))
        if {str(adjacency.first_patch_id), str(adjacency.second_patch_id)} == {patch_id, neighbour[name]}
    ]
    solve = _solve_with(context, directives)
    ladder = _ladder(context, patch_id).ladder
    _island, skeleton = _skeleton(solve, patch_id)
    rail = _rail_runs(context, skeleton, ladder.rail_a_patch_chain_ids)
    assert len(rail) == 12 and len({skeleton.line_by_run[e.id] for e in rail}) == 1
    marked = [d for d in solve.diagnostics if d.startswith(frame_free.MARKED_RAIL_PREFIX)]
    assert marked == [
        f"{frame_free.MARKED_RAIL_PREFIX} from 12 lines, no length equation, {sum(e.length for e in rail):.4f} m in 3D, "
        f"no stations: fewer than two of its nodes are laid: {patch_id} (r1_0..r1_0)"
    ]
    # Paired negative, the join itself: ordered by segment alone, the first two runs meet at the cut r1_0.
    first, second = sorted(rail, key=lambda e: e.segment_indices[0])[:2]
    assert frame_free._forward_end(first) == frame_free._forward_start(second) == "r1_0"


def test_a_mark_join_that_would_make_a_new_longest_line_does_not_move_the_seed(monkeypatch) -> None:
    # d_cyl_s2 with world up +Z: the joined rails of f112 and f114 are longer than any line of their quilt
    # before the join. The bipartition is seeded with the lengths before the mark joins (a joined line counts
    # as its longest part), so every run keeps the axis role it has without the joins.
    path = Path(__file__).resolve().parent / "data" / "bevel_cases" / "d_cyl_s2.capture.json"
    plain = run_pass_2_features(run_pass_1_relations(run_pass_0(load_source_snapshot(path))))
    context = run_pass_3_filters(plain, FilterOptions(world_up=UP))
    solve = run_skeleton_solve(context)
    monkeypatch.setattr(
        skeleton_module, "_join_marked_rails",
        lambda _island, _runs, line_of, signs, length_by_line, *_rest: (line_of, signs, length_by_line, None, ()),
    )
    head = run_skeleton_solve(context)
    evidence = context.relation_snapshot.patch_chain_directional_evidence
    for patch_id in ("patch:seed:f112", "patch:seed:f114"):
        _island, skeleton = _skeleton(solve, patch_id)
        _head_island, before = _skeleton(head, patch_id)
        assert skeleton.unmeasured_run_ids and not before.unmeasured_run_ids
        assert skeleton.axis_role_by_run == before.axis_role_by_run
        runs = [e for e in evidence if e.id in skeleton.line_by_run]
        summed = frame_free.line_lengths(runs, skeleton.line_by_run)
        joined = skeleton.line_by_run[next(iter(sorted(skeleton.unmeasured_run_ids)))]
        assert summed[joined] > max(frame_free.line_lengths(runs, before.line_by_run).values())
