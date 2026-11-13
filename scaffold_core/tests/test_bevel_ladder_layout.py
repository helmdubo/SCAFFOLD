"""
Layer: tests

Rules:
- A marked bevel strip laid from its ladder (plan Slice AF): the Layer 4
  STRAIGHT_LADDER constraint (which strips get one, u_i, width, fractions)
  and its Layer 5 layout (own island, frame LADDER, every boundary vertex
  pinned where the constraint says, unmirrored).
- Synthetic marked strips with hand-computed numbers, and the bevel cases
  of tests/data/bevel_cases (the user's rounded wall, a cube with three
  segments, the arch window).
- Every negative case is paired with a positive one. No production logic.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import replace
from pathlib import Path

import pytest

from dev.tools.cftuv_parity.parity import corner_turns
from dev.tools.scaffold_graph_debug.snapshot_io import load_source_snapshot
from scaffold_core.layer_4_features import bevels as feature_bevels
from scaffold_core.layer_4_features.model import (
    FeatureConstraintKind,
    FeatureInstanceStatus,
    FeatureKind,
    FeatureOptions,
    FeatureSuppressionReason,
)
from scaffold_core.layer_5_runtime import skeleton as runtime_skeleton
from scaffold_core.layer_5_runtime.islands import STITCH_BEVEL_LADDER_REASON
from scaffold_core.layer_5_runtime.pins import run_skeleton_solve
from scaffold_core.layer_5_runtime.skeleton import LADDER_LAYOUT, UNFOLDED_FRAME
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations, run_pass_2_features
from scaffold_core.tests.fixtures.bevel_patches import (
    make_marked_cut_ring_source,
    make_marked_ladder_strip_source,
)

BEVEL_CASES = Path(__file__).with_name("data") / "bevel_cases"
CASE_NAMES = sorted(path.name[: -len(".capture.json")] for path in BEVEL_CASES.glob("*.capture.json"))
OFF = FeatureOptions(straighten_bevel_strips=False)
EXACT = 1e-9

_ARC = [math.radians(30.0 * i) for i in range(4)]
SYNTHETIC = {
    # rail A, rail B, inner points of each profile line (offsets from rail A)
    "straight_3x1": ([(float(i), 0.0, 0.0) for i in range(4)], [(float(i), 0.2, 0.0) for i in range(4)], None),
    "curved_rails": (
        [(math.cos(t), math.sin(t), 0.0) for t in _ARC],
        [(1.2 * math.cos(t), 1.2 * math.sin(t), 0.0) for t in _ARC],
        None,
    ),
    "two_segments": (
        [(float(i), 0.0, 0.0) for i in range(4)], [(float(i), 0.2, 0.0) for i in range(4)], [(0.0, 0.05, 0.05)],
    ),
    "l_shaped": (
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 1.0, 0.0), (2.0, 2.0, 0.0)],
        [(0.0, 0.2, 0.0), (1.0, 0.2, 0.0), (1.8, 0.2, 0.0), (1.8, 1.0, 0.0), (1.8, 2.0, 0.0)],
        None,
    ),
}
_CHORD_30 = 2.0 * math.sin(math.radians(15.0))
_FIRST, _SECOND = math.hypot(0.05, 0.05), math.hypot(0.15, 0.05)
# u of every profile line, width, fraction across of the end lines' inner vertex.
HAND = {
    "straight_3x1": ([0.0, 1.0, 2.0, 3.0], 0.2, None),
    "curved_rails": ([i * _CHORD_30 * 1.1 for i in range(4)], 0.2, None),  # mean of radius 1 and 1.2
    "two_segments": ([0.0, 1.0, 2.0, 3.0], _FIRST + _SECOND, _FIRST / (_FIRST + _SECOND)),
    "l_shaped": ([0.0, 1.0, 1.9, 2.8, 3.8], (4 * 0.2 + math.hypot(0.2, 0.2)) / 5.0, None),
}
_CACHE: dict = {}


def _synthetic(name: str, options: FeatureOptions = FeatureOptions()):
    key = ("synthetic", name, options)
    if key not in _CACHE:
        rail_a, rail_b, across = SYNTHETIC[name]
        base = run_pass_1_relations(run_pass_0(make_marked_ladder_strip_source(rail_a, rail_b, across)))
        context = run_pass_2_features(base, options)
        _CACHE[key] = (base, context, run_skeleton_solve(context))
    return _CACHE[key]


def _case(name: str, options: FeatureOptions = FeatureOptions(), *, marks: bool = True):
    key = ("case", name, options, marks)
    if key not in _CACHE:
        source = load_source_snapshot(BEVEL_CASES / f"{name}.capture.json")
        if not marks:
            source = replace(source, faces={k: replace(f, face_strength=None) for k, f in source.faces.items()})
        base = run_pass_1_relations(run_pass_0(source))
        context = run_pass_2_features(base, options)
        _CACHE[key] = (base, context, run_skeleton_solve(context))
    return _CACHE[key]


def _ladders(context):
    return [c for c in context.feature_snapshot.constraints if c.kind is FeatureConstraintKind.STRAIGHT_LADDER]


def _skeleton(solve, patch_id):
    island_id = solve.assembly.island_by_patch_id[patch_id]
    return next(s for s in solve.skeletons if s.island_id == island_id)


def _placed(constraint, flip: bool) -> dict[str, tuple[float, float]]:
    ladder = constraint.ladder
    out = {}
    for line in ladder.profile_lines:
        u = ladder.length - line.u if flip else line.u
        out[str(line.rail_a.vertex_id)] = (u, 0.0)
        out[str(line.rail_b.vertex_id)] = (u, ladder.width)
        for vertex, fraction in line.across:
            out[str(vertex.vertex_id)] = (u, fraction * ladder.width)
    return out


def _check_ladder_island(context, solve, constraint) -> None:
    """Own island of frame LADDER; every boundary occurrence pinned exactly at its place; straight; unmirrored."""

    patch_id = str(constraint.patch_id)
    island_id = solve.assembly.island_by_patch_id[patch_id]
    (island,) = [i for i in solve.assembly.islands if i.id == island_id]
    assert island.patch_ids == (patch_id,) and island.stitched_chain_ids == ()
    skeleton = _skeleton(solve, patch_id)
    assert skeleton.frame == LADDER_LAYOUT
    # No solve: no length equation, zero residual, and no rail/line check (invariant 6 does not apply).
    assert skeleton.axis_a.equation_count == skeleton.axis_b.equation_count == 0
    assert skeleton.axis_a.residual_max == skeleton.axis_b.residual_max == 0.0
    assert skeleton.rail_frame_conflicts == ()
    assert not [c for c in solve.rail_frame_conflicts if island_id in c]
    pins = {v.vertex_id: v.uv for v in solve.vertices if v.patch_id == patch_id and v.pinned}
    shift = min(uv[0] for uv in pins.values())
    flips = [flip for flip in (False, True) if all(
        key in pins and abs(pins[key][0] - shift - u) <= EXACT and abs(pins[key][1] - v) <= EXACT
        for key, (u, v) in _placed(constraint, flip).items()
    )]
    assert len(flips) == 1, patch_id  # one orientation places every boundary vertex
    assert set(pins) == set(_placed(constraint, flips[0]))  # nothing else is pinned (no stations)
    ladder = constraint.ladder
    for line in ladder.profile_lines:  # both rail vertices of a line share u; rails straight and parallel
        a, b = pins[str(line.rail_a.vertex_id)], pins[str(line.rail_b.vertex_id)]
        assert a[0] == pytest.approx(b[0], abs=EXACT)
        assert a[1] == pytest.approx(0.0, abs=EXACT) and b[1] == pytest.approx(ladder.width, abs=EXACT)
    assert max(uv[0] for uv in pins.values()) - shift == pytest.approx(ladder.length, abs=EXACT)
    # Unmirrored: the boundary loop, walked along its runs (they follow the face winding), is counterclockwise.
    a_coords, b_coords = skeleton.axis_a.coordinate_by_node, skeleton.axis_b.coordinate_by_node
    area = 0.0
    for e in context.relation_snapshot.patch_chain_directional_evidence:
        if str(e.patch_id) != patch_id:
            continue
        start, end = skeleton.node_by_run_end[(e.id, "START")], skeleton.node_by_run_end[(e.id, "END")]
        area += a_coords[start] * b_coords[end] - a_coords[end] * b_coords[start]
    assert area > 0.0
    for e in context.relation_snapshot.patch_chain_directional_evidence:
        if str(e.patch_id) != patch_id:
            continue
        on_rail = e.patch_chain_id in ladder.rail_a_patch_chain_ids + ladder.rail_b_patch_chain_ids
        assert skeleton.axis_role_by_run[e.id] == ("AXIS_A" if on_rail else "AXIS_B")
    for decision in solve.assembly.decisions:
        if patch_id in (decision.first_patch_id, decision.second_patch_id):
            assert not decision.accepted
            assert decision.reason in (STITCH_BEVEL_LADDER_REASON, "SEAM_SELF always splits")


def _rail_length(context, uses) -> float:
    return sum(context.geometry_facts.chain_facts[context.topology_snapshot.patch_chains[use].chain_id].length
               for use in uses)


# --------------------------------------------------------------------------- Layer 4: the constraint


@pytest.mark.parametrize("name", sorted(SYNTHETIC))
def test_ladder_constraint_numbers_match_hand_computed_values(name) -> None:
    _base, context, _solve = _synthetic(name)
    (constraint,) = _ladders(context)
    us, width, fraction = HAND[name]
    ladder = constraint.ladder
    assert [line.u for line in ladder.profile_lines] == pytest.approx(us, abs=1e-12)
    assert ladder.width == pytest.approx(width, abs=1e-12)
    assert constraint.target_lengths == pytest.approx((us[-1], width), abs=1e-12)
    assert ladder.length == ladder.profile_lines[-1].u
    inner = [line.across for line in ladder.profile_lines]
    assert all(not across for across in inner[1:-1])  # only the end lines carry their inner vertices
    if fraction is None:
        assert not inner[0] and not inner[-1]
    else:
        assert [f for _v, f in inner[0]] == pytest.approx([fraction], abs=1e-12)
        assert [f for _v, f in inner[-1]] == pytest.approx([fraction], abs=1e-12)
    # The strip's length is the mean of its rails' 3D lengths.
    rails = (_rail_length(context, ladder.rail_a_patch_chain_ids), _rail_length(context, ladder.rail_b_patch_chain_ids))
    assert ladder.length == pytest.approx(sum(rails) / 2.0, abs=1e-12)
    assert constraint.patch_chain_ids == (
        ladder.rail_a_patch_chain_ids + ladder.rail_b_patch_chain_ids
        + ladder.end_a_patch_chain_ids + ladder.end_b_patch_chain_ids
    )


# Marked strips without a constraint, and why (patch -> reason).
NOT_LAID = {
    "b_ring_s1": {"patch:seed:f8": feature_bevels.NOT_LAID_CLOSED},
    "d_cyl_s2": {"patch:seed:f116": feature_bevels.NOT_LAID_CLOSED},
    "h_rect_s2_tri": {f"patch:seed:f{i}": feature_bevels.NOT_LAID_NO_READING for i in (8, 10, 12, 14)},
}


@pytest.mark.parametrize("name", CASE_NAMES)
def test_every_marked_strip_with_an_open_unshared_reading_gets_a_ladder_constraint(name) -> None:
    _base, context, _solve = _case(name)
    features = context.feature_snapshot
    strips = {
        str(r.patch_id) for r in features.bevels
        if r.kind is FeatureKind.BEVEL_STRIP and r.status is FeatureInstanceStatus.ACCEPTED
    }
    assert strips
    laid = {str(c.patch_id) for c in _ladders(context)}
    not_laid = {
        str(d.entity_ids[0]): d.evidence["reason"]
        for d in features.diagnostics if d.code == feature_bevels.LADDER_NOT_LAID_CODE
    }
    assert not_laid == NOT_LAID.get(name, {})
    assert laid | set(not_laid) == strips and not laid & set(not_laid)
    assert all(c.instance_id == f"feature_instance:bevel_strip:{c.patch_id}" for c in _ladders(context))


@pytest.mark.parametrize("name", ("a_cube_s1", "a_cube_s3", "g_short", "u_rounded_wall_noise_top"))
def test_strips_by_structure_never_emit_a_ladder_constraint(name) -> None:
    _base, context, _solve = _case(name, marks=False)
    strips = [r for r in context.feature_snapshot.bevels if r.kind is FeatureKind.BEVEL_STRIP]
    assert strips and all(r.source.value == "STRUCTURE" for r in strips)
    assert _ladders(context) == []
    assert not [d for d in context.feature_snapshot.diagnostics if d.code == feature_bevels.LADDER_NOT_LAID_CODE]
    # Paired positive: the same mesh with its marks.
    assert _ladders(_case(name)[1])


def test_a_reading_with_a_shared_use_gets_no_constraint_and_a_diagnostic() -> None:
    _base, context, _solve = _synthetic("straight_3x1")
    relations = context.relation_snapshot
    (record,) = [r for r in context.feature_snapshot.bevels if r.kind is FeatureKind.BEVEL_STRIP]
    relation = next(r for r in relations.patch_quad_ladder_relations if r.patch_id == record.patch_id)
    reading = relation.readings[record.reading_index]
    shared = replace(reading, shared_patch_chain_ids=reading.rail_a_patch_chain_ids[:1])
    readings = tuple(shared if i == record.reading_index else r for i, r in enumerate(relation.readings))
    tampered = replace(relations, patch_quad_ladder_relations=tuple(
        replace(r, readings=readings) if r is relation else r for r in relations.patch_quad_ladder_relations
    ))
    args = (context.feature_snapshot.bevels, tampered, context.geometry_facts, FeatureOptions())
    constraints, diagnostics = feature_bevels.ladder_constraints(*args)
    assert constraints == ()
    (diagnostic,) = diagnostics
    assert diagnostic.entity_ids == (str(record.patch_id),)
    assert diagnostic.evidence["reason"] == feature_bevels.NOT_LAID_SHARED_USE
    # Paired positive: the untouched reading is laid.
    constraints, diagnostics = feature_bevels.ladder_constraints(*((args[0], relations) + args[2:]))
    assert len(constraints) == 1 and diagnostics == ()


def test_triangulated_bevel_strips_get_no_layout_with_strips_on() -> None:
    """Known regression, pinned: h_rect_s2_tri's four marked strips are triangulated.

    They have no ladder reading (no STRAIGHT_LADDER) and their long sides are
    straight on the surface (no STRAIGHT_STRIP), so with straighten_strips
    they stay stitched into the main island of 10 patches, which has no
    rigid frame: 36 pinned vertices and 3 FRAME_FREE islands. Before Slice AF
    (564e07a) the same run laid them as 4 STRAIGHT_STRIP islands with 72
    pinned vertices; with straighten_strips off it is 36 both then and now.
    """

    on = FeatureOptions(straighten_strips=True)
    base, context, solve = _case("h_rect_s2_tri", on)
    strips = {f"patch:seed:f{i}" for i in (8, 10, 12, 14)}
    reasons = {str(i.patch_id): i.suppression_reason for i in context.feature_snapshot.instances}
    assert all(reasons[p] is FeatureSuppressionReason.LONG_SIDES_STRAIGHT for p in strips)
    assert context.feature_snapshot.constraints == ()
    assert sum(1 for v in solve.vertices if v.pinned) == 36
    assert [s.frame for s in solve.skeletons] == ["FRAME_FREE"] * 3
    assert sorted(len(i.patch_ids) for i in solve.assembly.islands) == [2, 2, 10]
    assert solve == _case("h_rect_s2_tri", FeatureOptions())[2]  # the same as strips off


@pytest.mark.parametrize("name", ("u_rounded_wall_noise_top", "a_cube_s3", "c_arch_s2", "d_cyl_s2"))
def test_with_the_bevel_option_off_no_ladder_constraint_and_the_solve_is_todays(name) -> None:
    base, off, solve_off = _case(name, OFF)
    assert _ladders(off) == []
    assert not [d for d in off.feature_snapshot.diagnostics if d.code == feature_bevels.LADDER_NOT_LAID_CODE]
    assert solve_off == run_skeleton_solve(base)  # strips off: as without Pass 2
    assert _ladders(_case(name)[1])


def test_a_strip_the_ladder_lays_emits_no_straight_strip() -> None:
    on = FeatureOptions(straighten_strips=True)
    _base, context, _solve = _case("u_rounded_wall_noise_top", on)
    taken = {"patch:seed:f35", "patch:seed:f36", "patch:seed:f71", "patch:seed:f73", "patch:seed:f96"}
    instances = {str(i.patch_id): i for i in context.feature_snapshot.instances}
    for patch_id in taken:
        assert instances[patch_id].suppression_reason is FeatureSuppressionReason.LAID_AS_BEVEL_STRIP
        kinds = [c.kind for c in context.feature_snapshot.constraints if str(c.patch_id) == patch_id]
        assert kinds == [FeatureConstraintKind.STRAIGHT_LADDER]
    # The strips the strip rule suppresses keep their own grade.
    assert instances["patch:seed:f34"].suppression_reason is FeatureSuppressionReason.ALREADY_RECTANGLE
    assert instances["patch:seed:f110"].suppression_reason is FeatureSuppressionReason.LONG_SIDES_STRAIGHT
    # Paired positive: with the bevel option off the strip rule accepts them.
    _base, plain, _solve = _case("u_rounded_wall_noise_top", replace(on, straighten_bevel_strips=False))
    accepted = {str(i.patch_id) for i in plain.feature_snapshot.instances if i.status is FeatureInstanceStatus.ACCEPTED}
    assert accepted == taken
    assert {str(c.patch_id) for c in plain.feature_snapshot.constraints} == taken


# --------------------------------------------------------------------------- Layer 5: the layout


@pytest.mark.parametrize("name", sorted(SYNTHETIC))
def test_a_synthetic_marked_strip_is_its_own_straight_island(name) -> None:
    _base, context, solve = _synthetic(name)
    (constraint,) = _ladders(context)
    _check_ladder_island(context, solve, constraint)
    _with_law, _checked, mirrored = corner_turns(context.relation_snapshot, solve)
    assert mirrored == 0
    assert solve.axis_parallel_violations == ()
    assert not [d for d in solve.diagnostics if "contradictory" in d]


@pytest.mark.parametrize("name", ("u_rounded_wall_noise_top", "a_cube_s3", "c_arch_s2"))
@pytest.mark.parametrize("strips", (False, True), ids=("strips_off", "strips_on"))
def test_marked_strips_of_the_bevel_cases_are_laid_from_their_ladder(name, strips) -> None:
    _base, context, solve = _case(name, FeatureOptions(straighten_strips=strips))
    ladders = _ladders(context)
    assert ladders
    for constraint in ladders:
        _check_ladder_island(context, solve, constraint)
    assert sum(1 for s in solve.skeletons if s.frame == LADDER_LAYOUT) == len(ladders)
    with_law, checked, mirrored = corner_turns(context.relation_snapshot, solve)
    assert with_law == checked and mirrored == 0
    assert solve.axis_parallel_violations == () and solve.seam_length_mismatches == ()
    assert not [d for d in solve.diagnostics if "contradictory" in d]  # nothing UNCONSTRAINED


def test_the_users_junctions_and_walls_keep_their_exact_shape() -> None:
    base, context, solve = _case("u_rounded_wall_noise_top")
    _base, _off, solve_off = _case("u_rounded_wall_noise_top", OFF)
    position = {str(k): v.position for k, v in base.source_snapshot.vertices.items()}
    junctions = [str(r.patch_id) for r in context.feature_snapshot.bevels if r.kind is FeatureKind.BEVEL_JUNCTION]
    assert len(junctions) == 6
    for patch_id in junctions:
        pins = [v for v in solve.vertices if v.patch_id == patch_id and v.pinned]
        assert len({v.uv for v in pins}) >= 2
        for a, b in itertools.combinations(pins, 2):  # planar triangles: pins at their true distances
            truth = math.dist(position[a.source_vertex_id], position[b.source_vertex_id])
            assert math.dist(a.uv, b.uv) == pytest.approx(truth, rel=1e-9)
    # The wall pieces leave the strips' island. f211 develops as before; f110
    # and f112 lose the 1.3 mm drift their 15-patch island spread (measured
    # 3.1e-4 and 6.1e-4 relative), and the planar f112 now sits at its true
    # distances.
    for patch_id, rel in (("patch:seed:f211", 1e-6), ("patch:seed:f110", 1e-3), ("patch:seed:f112", 1e-3)):
        now = {v.vertex_id: v.uv for v in solve.vertices if v.patch_id == patch_id and v.pinned}
        before = {v.vertex_id: v.uv for v in solve_off.vertices if v.patch_id == patch_id and v.pinned}
        assert set(now) == set(before) and len(now) > 2
        for k1, k2 in itertools.combinations(sorted(now), 2):
            assert math.dist(now[k1], now[k2]) == pytest.approx(math.dist(before[k1], before[k2]), rel=rel)
        skeleton = _skeleton(solve, patch_id)
        assert max(skeleton.axis_a.residual_max, skeleton.axis_b.residual_max) < 1e-9
    planar = {v.vertex_id: v for v in solve.vertices if v.patch_id == "patch:seed:f112" and v.pinned}
    for a, b in itertools.combinations(planar.values(), 2):
        truth = math.dist(position[a.source_vertex_id], position[b.source_vertex_id])
        assert math.dist(a.uv, b.uv) == pytest.approx(truth, rel=1e-9)
    patches_with_few_pins = {
        str(p) for p in context.topology_snapshot.patches
        if len({v.uv for v in solve.vertices if v.patch_id == str(p) and v.pinned}) < 2
    }
    assert patches_with_few_pins == {"patch:seed:f0"}  # the flat curved bottom waits for a band kind


def test_a_degenerate_end_line_gets_no_constraint_and_a_diagnostic() -> None:
    """Rail B starts on rail A's first vertex: profile line 0 has no length."""

    rail_a = [(float(i), 0.0, 0.0) for i in range(4)]
    rail_b = [(0.0, 0.0, 0.0)] + [(float(i), 0.2, 0.0) for i in range(1, 4)]
    context = run_pass_2_features(run_pass_1_relations(run_pass_0(make_marked_ladder_strip_source(rail_a, rail_b))))
    (record,) = [r for r in context.feature_snapshot.bevels if r.kind is FeatureKind.BEVEL_STRIP]
    assert record.status is FeatureInstanceStatus.ACCEPTED and record.reading_index is not None
    assert _ladders(context) == []
    (diagnostic,) = [d for d in context.feature_snapshot.diagnostics if d.code == feature_bevels.LADDER_NOT_LAID_CODE]
    assert diagnostic.entity_ids == (str(record.patch_id),)
    assert diagnostic.evidence["reason"] == feature_bevels.NOT_LAID_DEGENERATE
    assert LADDER_LAYOUT not in {s.frame for s in run_skeleton_solve(context).skeletons}
    # Paired positive: the same strip with a proper end is laid.
    assert len(_ladders(_synthetic("straight_3x1")[1])) == 1


def test_a_ring_cut_by_one_seam_is_laid_as_a_ladder() -> None:
    """A MEDIUM ring whose two ends are one SEAM_SELF Chain: each end vertex has two occurrences."""

    sides = 12
    context = run_pass_2_features(run_pass_1_relations(run_pass_0(make_marked_cut_ring_source(sides))))
    solve = run_skeleton_solve(context)
    (constraint,) = _ladders(context)
    ladder = constraint.ladder
    first, last = ladder.profile_lines[0], ladder.profile_lines[-1]
    assert first.rail_a.source_vertex_id == last.rail_a.source_vertex_id == "r1_0"
    assert first.rail_a.vertex_id != last.rail_a.vertex_id  # the two sides of the cut
    # Length: the mean of the two polygon perimeters (radius 1.0 and 1.1); width 0.1.
    perimeter = sides * 2.0 * math.sin(math.pi / sides)
    assert ladder.length == pytest.approx(perimeter * 1.05, abs=1e-12)
    assert ladder.width == pytest.approx(0.1, abs=1e-12)
    _check_ladder_island(context, solve, constraint)
    patch_id = str(constraint.patch_id)
    pins = {v.vertex_id: v.uv for v in solve.vertices if v.patch_id == patch_id and v.pinned}
    assert len(pins) == 2 * (sides + 1)  # every boundary occurrence, both ends of the cut included
    for face_id in context.topology_snapshot.patches[constraint.patch_id].source_face_ids:
        face = context.source_snapshot.faces[face_id]
        uv = [pins[solve.vertex_by_face_corner[(str(face_id), str(v))]] for v in face.vertex_ids]
        area = 0.5 * sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(uv, uv[1:] + uv[:1]))
        assert area > 0.0, face_id
    # Paired negative: the ring without its cut is a closed reading and is not laid.
    _base, closed, _solve = _case("b_ring_s1")
    assert "patch:seed:f8" not in {str(c.patch_id) for c in _ladders(closed)}


def test_a_ladder_island_never_runs_the_rail_line_check(monkeypatch) -> None:
    seen: list[set] = []
    check = runtime_skeleton._island_rail_conflicts

    def recording(segments, line_of, roles, signs, framed):
        seen.append(set(line_of))
        return check(segments, line_of, roles, signs, framed)

    monkeypatch.setattr(runtime_skeleton, "_island_rail_conflicts", recording)
    _base, context, _cached = _synthetic("curved_rails")
    solve = run_skeleton_solve(context)
    (constraint,) = _ladders(context)
    ladder_runs = {
        e.id for e in context.relation_snapshot.patch_chain_directional_evidence if e.patch_id == constraint.patch_id
    }
    assert seen  # paired positive: the other islands run it
    assert all(not runs & ladder_runs for runs in seen)
    assert _skeleton(solve, str(constraint.patch_id)).rail_frame_conflicts == ()


def test_a_ladder_constraint_whose_vertex_is_missing_falls_back_with_a_diagnostic() -> None:
    # A curved strip: with straighten_strips its strip instance is suppressed as laid from the ladder.
    base, context, solve = _synthetic("curved_rails", FeatureOptions(straighten_strips=True))
    (constraint,) = _ladders(context)
    lines = constraint.ladder.profile_lines
    broken_line = replace(lines[0], rail_a=replace(lines[0].rail_a, vertex_id="no_such_vertex"))  # a corner
    broken = replace(constraint, ladder=replace(constraint.ladder, profile_lines=(broken_line,) + lines[1:]))
    others = tuple(c for c in context.feature_snapshot.constraints if c is not constraint)
    tampered = run_skeleton_solve(replace(context, feature_snapshot=replace(
        context.feature_snapshot, constraints=others + (broken,),
    )))
    patch_id = str(constraint.patch_id)
    skeleton = _skeleton(tampered, patch_id)
    assert skeleton.frame == UNFOLDED_FRAME  # its normal layout: a flat strip unfolds
    assert f"ladder constraint not applied, a run end is not on the ladder: {patch_id}" in skeleton.diagnostics
    # It stays an island by itself (island assembly reads the constraint).
    assert tampered.assembly == solve.assembly
    island_id = tampered.assembly.island_by_patch_id[patch_id]
    (island,) = [i for i in tampered.assembly.islands if i.id == island_id]
    assert island.patch_ids == (patch_id,) and island.stitched_chain_ids == ()
    # Its strip instance stays suppressed as laid from the ladder, and no STRAIGHT_STRIP stands in.
    (instance,) = [i for i in context.feature_snapshot.instances if str(i.patch_id) == patch_id]
    assert instance.status is FeatureInstanceStatus.SUPPRESSED
    assert instance.suppression_reason is FeatureSuppressionReason.LAID_AS_BEVEL_STRIP
    assert [c.kind for c in context.feature_snapshot.constraints if str(c.patch_id) == patch_id] == [
        FeatureConstraintKind.STRAIGHT_LADDER
    ]
    # Paired positive: the untouched constraint lays it.
    assert _skeleton(solve, patch_id).frame == LADDER_LAYOUT
