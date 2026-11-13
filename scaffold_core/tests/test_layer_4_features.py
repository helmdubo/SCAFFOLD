"""
Layer: tests

Rules:
- Layer 4 v0 strip feature: candidates, resolver, constraint, Pass 2, and
  the STRAIGHT_STRIP constraint in the Layer 5 skeleton solve.
- Every negative case is paired with a positive one.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from scaffold_core.ids import ChainId, PatchChainId, PatchId
from scaffold_core.layer_4_features.build import (
    chain_is_bent,
    resolve_strip,
    strip_candidates,
    strip_needs_straightening,
)
from scaffold_core.layer_4_features.model import (
    FeatureCandidate,
    FeatureConstraint,
    FeatureInstance,
    FeatureSnapshot,
    FeatureConstraintKind,
    FeatureInstanceStatus,
    FeatureKind,
    FeatureOptions,
    FeatureSuppressionReason,
    StripSide,
)
from scaffold_core.layer_5_runtime.islands import STITCH_LEAVING_STRIP_REASON
from scaffold_core.layer_5_runtime.pins import run_skeleton_solve
from scaffold_core.layer_5_runtime.skeleton import STRIP_LAYOUT
from scaffold_core.pipeline.inspection import inspect_pipeline_context
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations, run_pass_2_features
from scaffold_core.tests.fixtures.cylinder_tube import make_cylinder_tube_without_caps_with_one_seam_source
from scaffold_core.tests.fixtures.strip_patches import (
    make_annulus_with_tab_source,
    make_cut_annulus_source,
    make_cut_three_row_annulus_source,
    make_ring_sector_between_quads_source,
    make_ring_sector_between_quads_with_band_source,
    make_square_with_hole_source,
)
from scaffold_core.tests.test_layer_5_runtime import _load_capture

DATA = Path(__file__).resolve().parent / "data"
ON = FeatureOptions(straighten_strips=True)
ARCH_FRONT = "patch:seed:f16"
ARCH_RIMS = ("patch:seed:f0", "patch:seed:f85")


def _pass_1(source):
    return run_pass_1_relations(run_pass_0(source))


def _instance(context, patch_id):
    return next(i for i in context.feature_snapshot.instances if str(i.patch_id) == patch_id)


def _skeleton(solve, patch_id):
    island_id = solve.assembly.island_by_patch_id[patch_id]
    return next(s for s in solve.skeletons if s.island_id == island_id)


def _side_extents(context, solve, constraint):
    """Per use in loop order: (axis role, UV length along the axis, cross coordinate spread)."""

    skeleton = _skeleton(solve, str(constraint.patch_id))
    coords = {"AXIS_A": skeleton.axis_a.coordinate_by_node, "AXIS_B": skeleton.axis_b.coordinate_by_node}
    runs = context.relation_snapshot.patch_chain_directional_evidence
    sides = []
    for pc_id in constraint.patch_chain_ids:
        use_runs = [e for e in runs if e.patch_chain_id == pc_id]
        roles = {skeleton.axis_role_by_run[e.id] for e in use_runs}
        assert len(roles) == 1
        role = next(iter(roles))
        cross = "AXIS_B" if role == "AXIS_A" else "AXIS_A"
        along = sum(
            coords[role][skeleton.node_by_run_end[(e.id, "END")]] - coords[role][skeleton.node_by_run_end[(e.id, "START")]]
            for e in use_runs
        )
        cross_values = [
            coords[cross][skeleton.node_by_run_end[(e.id, end)]] for e in use_runs for end in ("START", "END")
        ]
        sides.append((role, along, max(cross_values) - min(cross_values)))
    return sides


def _loop_signed_area(context, solve, constraint):
    """Shoelace area of the solved loop, summed over the runs (they follow the loop)."""

    skeleton = _skeleton(solve, str(constraint.patch_id))
    a, b = skeleton.axis_a.coordinate_by_node, skeleton.axis_b.coordinate_by_node
    area = 0.0
    for e in context.relation_snapshot.patch_chain_directional_evidence:
        if e.patch_chain_id not in constraint.patch_chain_ids:
            continue
        start = skeleton.node_by_run_end[(e.id, "START")]
        end = skeleton.node_by_run_end[(e.id, "END")]
        area += a[start] * b[end] - a[end] * b[start]
    return area / 2.0


def _patch_run_ends_pinned(context, solve, patch_id):
    skeleton = _skeleton(solve, patch_id)
    pinned = {(v.vertex_id, v.patch_id) for v in solve.vertices if v.pinned}
    keys = [
        (vertex_id, patch_id)
        for (run_id, _role), vertex_id in skeleton.vertex_by_run_end.items()
        if run_id.startswith(f"patch_chain_directional_evidence:patch_chain:{patch_id}:")
    ]
    return keys, [key for key in keys if key not in pinned]


# ------------------------------------------------------------ arch capture


@pytest.fixture(scope="module")
def arch():
    base = _pass_1(_load_capture("artist_arch_bevel.json"))
    on = run_pass_2_features(base, ON)
    return base, on, run_skeleton_solve(base), run_skeleton_solve(on)


def test_arch_front_is_an_accepted_strip_laid_as_a_rectangle(arch) -> None:
    _base, on, _solve_off, solve = arch
    assert _instance(on, ARCH_FRONT).status is FeatureInstanceStatus.ACCEPTED
    (constraint,) = [c for c in on.feature_snapshot.constraints if str(c.patch_id) == ARCH_FRONT]
    assert _skeleton(solve, ARCH_FRONT).frame == STRIP_LAYOUT
    feet = (0.4416, 0.4416)
    arcs = ((3.5573 + 2.2464) / 2.0,)
    assert constraint.target_lengths == pytest.approx(feet[:1] + arcs, abs=1e-4)
    sides = _side_extents(on, solve, constraint)
    # Both arcs (loop positions 1 and 3) on AXIS_A with one UV length, the
    # mean of 3.557 and 2.246; both feet on AXIS_B with one length.
    assert [role for role, _along, _cross in sides] == ["AXIS_B", "AXIS_A", "AXIS_B", "AXIS_A"]
    assert sides[1][1] == pytest.approx(arcs[0], abs=1e-4)
    assert sides[3][1] == pytest.approx(-arcs[0], abs=1e-4)
    # The loop from the first AXIS_A use runs +A, +B, -A, -B.
    assert sides[2][1] == pytest.approx(feet[0], abs=1e-4)
    assert sides[0][1] == pytest.approx(-feet[0], abs=1e-4)
    assert all(cross < 1e-9 for _role, _along, cross in sides)
    keys, unpinned = _patch_run_ends_pinned(on, solve, ARCH_FRONT)
    assert keys and not unpinned
    assert solve.axis_parallel_violations == ()
    assert _loop_signed_area(on, solve, constraint) > 0.0  # unmirrored


def test_arch_rims_are_suppressed_rectangles_and_keep_their_islands(arch) -> None:
    _base, on, solve_off, solve = arch
    for rim in ARCH_RIMS:
        instance = _instance(on, rim)
        assert instance.status is FeatureInstanceStatus.SUPPRESSED
        assert instance.suppression_reason is FeatureSuppressionReason.ALREADY_RECTANGLE
        assert _skeleton(solve, rim) == _skeleton(solve_off, rim)
    # The paired positive: the front island did change.
    assert _skeleton(solve, ARCH_FRONT) != _skeleton(solve_off, ARCH_FRONT)


def test_arch_with_the_option_off_solves_as_without_pass_2(arch) -> None:
    base, _on, solve_off, _solve = arch
    off = run_pass_2_features(base)
    assert not off.feature_snapshot.constraints
    assert {i.suppression_reason for i in off.feature_snapshot.instances} == {FeatureSuppressionReason.OPTION_OFF}
    assert run_skeleton_solve(off) == solve_off
    assert off.relation_snapshot is base.relation_snapshot  # Pass 2 never writes Layer 3


def test_layer_5_reads_constraints_not_candidates(arch) -> None:
    _base, on, solve_off, solve = arch
    without_constraints = replace(on, feature_snapshot=replace(on.feature_snapshot, constraints=()))
    assert run_skeleton_solve(without_constraints) == solve_off
    assert solve != solve_off


# ------------------------------------------------------- synthetic fixtures


def test_cut_annulus_is_an_accepted_strip_rectangle() -> None:
    context = run_pass_2_features(_pass_1(make_cut_annulus_source()), ON)
    (constraint,) = context.feature_snapshot.constraints
    solve = run_skeleton_solve(context)
    assert _skeleton(solve, str(constraint.patch_id)).frame == STRIP_LAYOUT
    ends, circles = constraint.target_lengths
    assert ends == pytest.approx(1.0)
    sides = _side_extents(context, solve, constraint)
    assert [role for role, _along, _cross in sides] == ["AXIS_B", "AXIS_A", "AXIS_B", "AXIS_A"]
    assert [along for _role, along, _cross in sides] == pytest.approx([-ends, circles, ends, -circles])
    assert _loop_signed_area(context, solve, constraint) == pytest.approx(ends * circles)  # unmirrored
    assert solve.axis_parallel_violations == ()
    assert solve.residual_max < 1e-9
    _keys, unpinned = _patch_run_ends_pinned(context, solve, str(constraint.patch_id))
    assert not unpinned


def test_plain_rectangle_is_a_suppressed_candidate() -> None:
    base = _pass_1(make_cylinder_tube_without_caps_with_one_seam_source())
    context = run_pass_2_features(base, ON)
    (instance,) = context.feature_snapshot.instances
    assert len(context.feature_snapshot.candidates) == 1
    assert instance.suppression_reason is FeatureSuppressionReason.ALREADY_RECTANGLE
    assert context.feature_snapshot.constraints == ()
    assert run_skeleton_solve(context) == run_skeleton_solve(base)


@pytest.mark.parametrize("make", [make_annulus_with_tab_source, make_square_with_hole_source])
def test_five_uses_or_a_hole_is_no_candidate(make) -> None:
    context = run_pass_2_features(_pass_1(make()), ON)
    assert context.feature_snapshot.candidates == ()
    assert context.feature_snapshot.instances == ()
    # Paired positive: the cut annulus, the same ring without the tab, is one.
    annulus = run_pass_2_features(_pass_1(make_cut_annulus_source()), ON)
    assert len(annulus.feature_snapshot.candidates) == 1


def test_strip_stitched_only_across_straight_sides_leaves_its_island() -> None:
    base = _pass_1(make_ring_sector_between_quads_source())
    context = run_pass_2_features(base, ON)
    (constraint,) = context.feature_snapshot.constraints
    patch_id = str(constraint.patch_id)
    solve = run_skeleton_solve(context)
    # With the option off the sector stays stitched to both quads.
    (island_off,) = run_skeleton_solve(base).assembly.islands
    assert len(island_off.patch_ids) == 3
    decisions = [d for d in solve.assembly.decisions if patch_id in (d.first_patch_id, d.second_patch_id)]
    assert len(decisions) == 2
    assert all(not d.accepted and d.reason == STITCH_LEAVING_STRIP_REASON for d in decisions)
    assert len(solve.assembly.islands) == 3
    assert _skeleton(solve, patch_id).frame == STRIP_LAYOUT
    # A rectangle: opposite sides equal, every side straight, every corner turns left.
    sides = _side_extents(context, solve, constraint)
    assert [abs(along) for _role, along, _cross in sides[:2]] == pytest.approx(
        [abs(along) for _role, along, _cross in sides[2:]]
    )
    assert all(cross < 1e-9 for _role, _along, cross in sides)
    vectors = [(along, 0.0) if role == "AXIS_A" else (0.0, along) for role, along, _cross in sides]
    for (ax, ay), (bx, by) in zip(vectors, vectors[1:] + vectors[:1]):
        assert ax * by - ay * bx > 0.0
    assert _loop_signed_area(context, solve, constraint) > 0.0
    # The former neighbours are islands of one patch with their own layout.
    for decision in decisions:
        neighbour = decision.second_patch_id if decision.first_patch_id == patch_id else decision.first_patch_id
        island_id = solve.assembly.island_by_patch_id[neighbour]
        (island,) = [i for i in solve.assembly.islands if i.id == island_id]
        assert island.patch_ids == (neighbour,)
        assert _skeleton(solve, neighbour).frame != STRIP_LAYOUT
        assert any(v.pinned and v.patch_id == neighbour for v in solve.vertices)


def test_strip_stitched_across_a_bent_side_is_not_applied_with_a_diagnostic() -> None:
    base = _pass_1(make_ring_sector_between_quads_with_band_source())
    context = run_pass_2_features(base, ON)
    (constraint,) = context.feature_snapshot.constraints
    patch_id = str(constraint.patch_id)
    solve = run_skeleton_solve(context)
    solve_off = run_skeleton_solve(base)
    skeleton = _skeleton(solve, patch_id)
    (island,) = solve.assembly.islands
    assert len(island.patch_ids) == 4
    assert all(d.reason != STITCH_LEAVING_STRIP_REASON for d in solve.assembly.decisions)
    assert solve.assembly == solve_off.assembly
    assert skeleton.frame != STRIP_LAYOUT
    assert f"strip constraint not applied, patch shares its island: {patch_id}" in skeleton.diagnostics
    assert solve.vertices == solve_off.vertices
    assert replace(skeleton, diagnostics=()) == replace(_skeleton(solve_off, patch_id), diagnostics=())


# ------------------------------------------------------------ Layer 4 units


def _side(position, length, bent=False, line=True):
    return StripSide(
        patch_chain_id=PatchChainId(f"pc{position}"),
        chain_id=ChainId(f"c{position}"),
        position_in_loop=position,
        length=length,
        is_bent=bent,
        is_surface_line=line,
    )


def _candidate(*sides):
    return FeatureCandidate(
        id="feature_candidate:strip:p", kind=FeatureKind.STRIP, patch_id=PatchId("p"),
        loop_id="loop", sides=tuple(sides),
    )


def test_cut_annulus_candidate_and_constraint_fields() -> None:
    context = run_pass_2_features(_pass_1(make_cut_annulus_source()), ON)
    (candidate,) = context.feature_snapshot.candidates
    (instance,) = context.feature_snapshot.instances
    (constraint,) = context.feature_snapshot.constraints
    topology = context.topology_snapshot
    loop = topology.loops[candidate.loop_id]
    assert [side.position_in_loop for side in candidate.sides] == [0, 1, 2, 3]
    assert [side.patch_chain_id for side in candidate.sides] == sorted(
        loop.patch_chain_ids, key=lambda pc_id: topology.patch_chains[pc_id].position_in_loop
    )
    lengths = [side.length for side in candidate.sides]
    assert lengths == pytest.approx([1.0, 12.4233, 1.0, 6.2117], abs=1e-4)
    assert [side.is_bent for side in candidate.sides] == [False, True, False, True]
    assert [side.is_surface_line for side in candidate.sides] == [True, False, True, False]
    assert candidate.sides[0].chain_id == candidate.sides[2].chain_id  # the two SEAM_SELF sides
    assert instance.candidate_id == candidate.id
    assert constraint.kind is FeatureConstraintKind.STRAIGHT_STRIP
    assert constraint.instance_id == instance.id
    assert constraint.patch_chain_ids == tuple(side.patch_chain_id for side in candidate.sides)
    assert constraint.target_lengths == pytest.approx(((lengths[0] + lengths[2]) / 2, (lengths[1] + lengths[3]) / 2))


def test_resolver_reasons() -> None:
    bent_arcs = _candidate(_side(0, 1.0), _side(1, 3.0, True, False), _side(2, 1.0), _side(3, 2.0, True, False))
    accepted = resolve_strip(bent_arcs, ON)
    assert accepted.status is FeatureInstanceStatus.ACCEPTED and accepted.suppression_reason is None
    off = resolve_strip(bent_arcs, FeatureOptions())
    assert off.status is FeatureInstanceStatus.SUPPRESSED
    assert off.suppression_reason is FeatureSuppressionReason.OPTION_OFF
    rectangle = _candidate(_side(0, 1.0), _side(1, 3.0, True), _side(2, 1.0), _side(3, 3.0, True))
    assert resolve_strip(rectangle, ON).suppression_reason is FeatureSuppressionReason.ALREADY_RECTANGLE
    trapezoid = _candidate(_side(0, 1.0), _side(1, 3.0), _side(2, 1.0), _side(3, 2.0))
    assert resolve_strip(trapezoid, ON).suppression_reason is FeatureSuppressionReason.NO_BENT_OPPOSITE_PAIR
    one_bent = _candidate(_side(0, 1.0, True), _side(1, 3.0, True), _side(2, 1.0), _side(3, 2.0))
    assert resolve_strip(one_bent, ON).suppression_reason is FeatureSuppressionReason.NO_BENT_OPPOSITE_PAIR


def test_needs_straightening_threshold_is_one_percent() -> None:
    near = _candidate(_side(0, 1.0), _side(1, 3.0), _side(2, 1.0), _side(3, 3.0 * 0.995))
    far = _candidate(_side(0, 1.0), _side(1, 3.0), _side(2, 1.0), _side(3, 3.0 * 0.98))
    curved = _candidate(_side(0, 1.0), _side(1, 3.0, line=False), _side(2, 1.0), _side(3, 3.0))
    assert not strip_needs_straightening(near)
    assert strip_needs_straightening(far)
    assert strip_needs_straightening(curved)


def test_inspection_lists_feature_counts() -> None:
    base = _pass_1(_load_capture("artist_arch_bevel.json"))
    report = inspect_pipeline_context(run_pass_2_features(base, ON))["features"]
    assert report["options"] == {"straighten_strips": True}
    assert report["candidate_count"] == 5
    assert report["accepted_count"] == 1
    assert report["suppressed_by_reason"] == {"already a rectangle": 2, "no bent opposite pair": 2}
    assert report["constraint_count"] == 1
    assert report["constraints"][0]["patch_id"] == ARCH_FRONT
    assert "features" not in inspect_pipeline_context(base)


# ------------------------------------------------------------------ guard


@pytest.mark.parametrize("name", sorted(path.name for path in DATA.glob("*.json")))
def test_default_pass_2_leaves_the_solve_unchanged(name) -> None:
    base = _pass_1(_load_capture(name))
    assert run_skeleton_solve(run_pass_2_features(base)) == run_skeleton_solve(base)


# ------------------------------------------------- reviewer gate additions


def _with_constraint_uses(context, order):
    (constraint,) = context.feature_snapshot.constraints
    uses = tuple(constraint.patch_chain_ids[i] for i in order)
    return replace(context, feature_snapshot=replace(
        context.feature_snapshot, constraints=(replace(constraint, patch_chain_ids=uses),),
    ))


@pytest.mark.parametrize("order", [(3, 2, 1, 0), (0, 2, 1, 3)], ids=["reversed", "swapped"])
def test_strip_uses_that_do_not_close_the_loop_are_not_applied(order) -> None:
    base = _pass_1(make_cut_annulus_source())
    context = run_pass_2_features(base, ON)
    patch_id = str(context.feature_snapshot.constraints[0].patch_id)
    solve = run_skeleton_solve(_with_constraint_uses(context, order))
    skeleton = _skeleton(solve, patch_id)
    assert skeleton.frame != STRIP_LAYOUT
    assert f"strip constraint not applied, its uses do not close the loop: {patch_id}" in skeleton.diagnostics
    assert solve.vertices == run_skeleton_solve(base).vertices
    # Paired positive: the stated loop order still applies.
    assert _skeleton(run_skeleton_solve(_with_constraint_uses(context, (0, 1, 2, 3))), patch_id).frame == STRIP_LAYOUT


def test_strip_side_without_runs_falls_back_with_a_diagnostic() -> None:
    base = _pass_1(make_cut_annulus_source())
    context = run_pass_2_features(base, ON)
    (constraint,) = context.feature_snapshot.constraints
    broken = replace(constraint, patch_chain_ids=constraint.patch_chain_ids[:3] + (PatchChainId("no_such_use"),))
    solve = run_skeleton_solve(replace(context, feature_snapshot=replace(
        context.feature_snapshot, constraints=(broken,),
    )))
    skeleton = _skeleton(solve, str(constraint.patch_id))
    assert skeleton.frame != STRIP_LAYOUT
    assert f"strip constraint not applied, a side has no runs: {constraint.patch_id}" in skeleton.diagnostics
    assert solve.vertices == run_skeleton_solve(base).vertices
    assert _skeleton(run_skeleton_solve(context), str(constraint.patch_id)).frame == STRIP_LAYOUT


def test_strip_with_a_hole_is_no_candidate() -> None:
    holed = run_pass_2_features(_pass_1(make_cut_three_row_annulus_source(with_hole=True)), ON)
    (patch,) = holed.topology_snapshot.patches.values()
    assert len(patch.loop_ids) == 2
    assert len(holed.topology_snapshot.loops[patch.loop_ids[0]].patch_chain_ids) == 4
    assert holed.feature_snapshot.candidates == ()
    whole = run_pass_2_features(_pass_1(make_cut_three_row_annulus_source(with_hole=False)), ON)
    assert len(whole.feature_snapshot.candidates) == 1


def test_a_use_of_several_surface_line_pieces_is_not_one_line() -> None:
    context = _pass_1(make_cut_annulus_source())
    relations = context.relation_snapshot
    (candidate,) = strip_candidates(context.topology_snapshot, context.geometry_facts, relations)
    line_use = candidate.sides[0]
    assert line_use.is_surface_line
    piece = next(p for p in relations.patch_chain_shape_relations if p.patch_chain_id == line_use.patch_chain_id)
    doubled = replace(relations, patch_chain_shape_relations=relations.patch_chain_shape_relations + (
        replace(piece, id=piece.id + ":second"),
    ))
    (split,) = strip_candidates(context.topology_snapshot, context.geometry_facts, doubled)
    assert not split.sides[0].is_surface_line
    assert [side.is_surface_line for side in split.sides[1:]] == [side.is_surface_line for side in candidate.sides[1:]]


def test_bent_means_longer_than_the_chord() -> None:
    from types import SimpleNamespace

    assert not chain_is_bent(SimpleNamespace(length=15.259, chord_length=15.259))  # arched but chord-long
    assert not chain_is_bent(SimpleNamespace(length=1.005, chord_length=1.0))
    assert chain_is_bent(SimpleNamespace(length=1.02, chord_length=1.0))
    assert chain_is_bent(SimpleNamespace(length=6.28, chord_length=0.0))  # closed


def test_layer_4_records_are_frozen() -> None:
    context = run_pass_2_features(_pass_1(make_cut_annulus_source()), ON)
    features = context.feature_snapshot
    records = (
        features, features.options, features.candidates[0], features.candidates[0].sides[0],
        features.instances[0], features.constraints[0],
    )
    assert {type(r) for r in records} >= {FeatureSnapshot, FeatureCandidate, FeatureInstance, FeatureConstraint}
    for record in records:
        with pytest.raises(FrozenInstanceError):
            record.id = "changed"


def test_a_chord_long_chain_off_its_line_is_not_bent() -> None:
    context = _pass_1(make_cut_annulus_source())
    geometry = context.geometry_facts
    (candidate,) = strip_candidates(context.topology_snapshot, geometry, context.relation_snapshot)
    straight = candidate.sides[0]
    assert not straight.is_bent and candidate.sides[1].is_bent
    # A vertex off the chord line gives a plane, yet the length equals the chord.
    facts = geometry.chain_facts[straight.chain_id]
    planed = replace(geometry, chain_facts={
        **geometry.chain_facts, straight.chain_id: replace(facts, plane_normal=(0.0, 0.0, 1.0)),
    })
    (same,) = strip_candidates(context.topology_snapshot, planed, context.relation_snapshot)
    assert not same.sides[0].is_bent
