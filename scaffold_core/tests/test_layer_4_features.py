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
from math import cos, hypot, pi, sin
from pathlib import Path

import pytest

from scaffold_core.ids import ChainId, PatchChainId, PatchId
from scaffold_core.layer_4_features.build import (
    resolve_strip,
    strip_constraint,
    strip_long_pairs,
    strip_candidates,
    strip_is_rail_pair,
    strip_needs_straightening,
    strip_rail_pair,
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
    make_flat_strip_with_flaps_source,
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
    # The shape is graded first: "option off" marks exactly what the option accepts.
    accepted_on = {i.patch_id for i in _on.feature_snapshot.instances if i.status is FeatureInstanceStatus.ACCEPTED}
    assert accepted_on
    for instance, instance_on in zip(off.feature_snapshot.instances, _on.feature_snapshot.instances, strict=True):
        assert instance.status is FeatureInstanceStatus.SUPPRESSED
        if instance.patch_id in accepted_on:
            assert instance.suppression_reason is FeatureSuppressionReason.OPTION_OFF
        else:
            assert instance.suppression_reason is instance_on.suppression_reason
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


def _side(position, length, line=True, area=None):
    """A strip side; a curved side by default bows the same way as its opposite one.

    Opposite sides walk the loop in opposite directions, so sides bowing the
    same way in space have opposite chord area vectors: +z at positions 0
    and 1, -z at 2 and 3. A straight side closes no area.
    """

    if area is None and not line:
        area = (0.0, 0.0, 1.0 if position < 2 else -1.0)
    return StripSide(
        patch_chain_id=PatchChainId(f"pc{position}"),
        chain_id=ChainId(f"c{position}"),
        position_in_loop=position,
        length=length,
        is_surface_line=line,
        chord_area_vector=area,
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
    assert [side.is_surface_line for side in candidate.sides] == [True, False, True, False]
    assert candidate.sides[0].chain_id == candidate.sides[2].chain_id  # the two SEAM_SELF sides
    assert instance.candidate_id == candidate.id
    assert constraint.kind is FeatureConstraintKind.STRAIGHT_STRIP
    assert constraint.instance_id == instance.id
    assert constraint.patch_chain_ids == tuple(side.patch_chain_id for side in candidate.sides)
    assert constraint.target_lengths == pytest.approx(((lengths[0] + lengths[2]) / 2, (lengths[1] + lengths[3]) / 2))


def test_resolver_reasons() -> None:
    curved_arcs = _candidate(_side(0, 1.0), _side(1, 3.0, False), _side(2, 1.0), _side(3, 2.0, False))
    accepted = resolve_strip(curved_arcs, ON)
    assert accepted.status is FeatureInstanceStatus.ACCEPTED and accepted.suppression_reason is None
    off = resolve_strip(curved_arcs, FeatureOptions())
    assert off.status is FeatureInstanceStatus.SUPPRESSED
    assert off.suppression_reason is FeatureSuppressionReason.OPTION_OFF
    rectangle = _candidate(_side(0, 1.0), _side(1, 3.0), _side(2, 1.0), _side(3, 3.0))
    assert resolve_strip(rectangle, ON).suppression_reason is FeatureSuppressionReason.ALREADY_RECTANGLE
    trapezoid = _candidate(_side(0, 1.0), _side(1, 3.0), _side(2, 1.0), _side(3, 2.0))
    assert resolve_strip(trapezoid, ON).suppression_reason is FeatureSuppressionReason.LONG_SIDES_STRAIGHT
    # The option does not change the grade of a shape it would not accept.
    assert resolve_strip(rectangle, FeatureOptions()).suppression_reason is FeatureSuppressionReason.ALREADY_RECTANGLE
    assert resolve_strip(trapezoid, FeatureOptions()).suppression_reason is FeatureSuppressionReason.LONG_SIDES_STRAIGHT
    one_curved = _candidate(_side(0, 1.0), _side(1, 3.0, False), _side(2, 1.0), _side(3, 2.0))
    assert resolve_strip(one_curved, ON).suppression_reason is FeatureSuppressionReason.LONG_SIDES_STRAIGHT


def test_long_sides_curved_on_the_surface_decide_acceptance() -> None:
    # Long pair curved on the surface -> accepted.
    long_curved = _candidate(_side(0, 1.0), _side(1, 5.0, False), _side(2, 1.2), _side(3, 4.0, False))
    assert strip_long_pairs(long_curved) == ((1, 3),)
    assert resolve_strip(long_curved, ON).suppression_reason is None
    # Long pair lines on the surface, short pair curved -> suppressed: a wall
    # bent in 3D that develops without distortion is not a strip.
    short_curved = _candidate(_side(0, 1.0, False), _side(1, 5.0), _side(2, 1.2, False), _side(3, 4.0))
    assert resolve_strip(short_curved, ON).suppression_reason is FeatureSuppressionReason.LONG_SIDES_STRAIGHT
    # One long side curved is not enough.
    one_long_curved = _candidate(_side(0, 1.0), _side(1, 5.0, False), _side(2, 1.2), _side(3, 4.0))
    assert resolve_strip(one_long_curved, ON).suppression_reason is FeatureSuppressionReason.LONG_SIDES_STRAIGHT
    # Exact tie of the summed lengths: either pair may qualify.
    tie_a = _candidate(_side(0, 2.0, False), _side(1, 3.0), _side(2, 2.0, False), _side(3, 1.0))
    tie_b = _candidate(_side(0, 2.0), _side(1, 3.0, False), _side(2, 2.0), _side(3, 1.0, False))
    assert strip_long_pairs(tie_a) == ((0, 2), (1, 3))
    assert resolve_strip(tie_a, ON).suppression_reason is None
    assert resolve_strip(tie_b, ON).suppression_reason is None
    # The pair is chosen by the summed length, not by the longest single use.
    by_sum = _candidate(_side(0, 4.5), _side(1, 2.0, False), _side(2, 0.4), _side(3, 2.95, False))
    assert strip_long_pairs(by_sum) == ((1, 3),)
    assert resolve_strip(by_sum, ON).suppression_reason is None
    # A trapezoid with straight sides only is already graded by its sides.
    trapezoid = _candidate(_side(0, 1.0), _side(1, 3.0), _side(2, 1.0), _side(3, 2.0))
    assert resolve_strip(trapezoid, ON).suppression_reason is FeatureSuppressionReason.LONG_SIDES_STRAIGHT
    # Bending in 3D is no longer read: the record has no such field.
    assert not hasattr(long_curved.sides[0], "is_bent")


def test_mirrored_long_sides_are_no_rail_pair() -> None:
    # Two profiles bowing away from each other (a flat wall between mirrored
    # curves) have the same chord area vector walked along the loop.
    mirrored = _candidate(_side(0, 1.0), _side(1, 5.0, False, (0.0, 0.0, 1.0)),
                          _side(2, 1.0), _side(3, 5.0, False, (0.0, 0.0, 1.0)))
    assert strip_rail_pair(mirrored) is None
    assert resolve_strip(mirrored, ON).suppression_reason is FeatureSuppressionReason.NO_RAIL_PAIR
    # The option does not change the grade.
    assert resolve_strip(mirrored, FeatureOptions()).suppression_reason is FeatureSuppressionReason.NO_RAIL_PAIR
    # Paired positive: the same sides bending the same way are the rails.
    alike = _candidate(_side(0, 1.0), _side(1, 5.0, False), _side(2, 1.0), _side(3, 5.0, False))
    assert strip_rail_pair(alike) == 1
    assert resolve_strip(alike, ON).status is FeatureInstanceStatus.ACCEPTED
    # A curved side that closes no area with its chord (its bows cancel) cannot be a rail.
    no_area = _candidate(_side(0, 1.0), _side(1, 5.0, False), _side(2, 1.0), replace(_side(3, 5.0, False), chord_area_vector=None))
    assert resolve_strip(no_area, ON).suppression_reason is FeatureSuppressionReason.NO_RAIL_PAIR
    # A side that is one surface line is no rail even when it closes an area.
    line_side = _candidate(_side(0, 1.0), _side(1, 5.0, False), _side(2, 1.0, True, (0.0, 0.0, -1.0)), _side(3, 5.0, False))
    assert strip_is_rail_pair(line_side, (1, 3)) and not strip_is_rail_pair(line_side, (0, 2))


def test_the_single_rail_pair_holds_the_rails_whatever_its_length() -> None:
    # Long pair curved but mirrored, short pair curved and bending alike: the short pair holds the rails.
    short_rails = _candidate(
        _side(0, 6.0, False, (1.0, 0.0, 0.0)), _side(1, 2.8, False),
        _side(2, 6.0, False, (1.0, 0.0, 0.0)), _side(3, 2.9, False),
    )
    assert strip_rail_pair(short_rails) == 1
    instance = resolve_strip(short_rails, ON)
    assert instance.status is FeatureInstanceStatus.ACCEPTED
    constraint = strip_constraint(instance, short_rails)
    assert constraint.rail_pair == 1
    assert constraint.free_end_patch_chain_ids == (PatchChainId("pc0"), PatchChainId("pc2"))
    assert constraint.patch_chain_ids == tuple(side.patch_chain_id for side in short_rails.sides)
    assert constraint.target_lengths == pytest.approx((6.0, 2.85))
    # Both pairs rail pairs: the longer one; an exact tie takes pair 0.
    both = _candidate(_side(0, 6.0, False), _side(1, 2.8, False), _side(2, 6.0, False), _side(3, 2.9, False))
    assert strip_rail_pair(both) == 0
    assert strip_constraint(resolve_strip(both, ON), both).free_end_patch_chain_ids == (PatchChainId("pc1"), PatchChainId("pc3"))
    tie = _candidate(_side(0, 2.0, False), _side(1, 3.0, False), _side(2, 2.0, False), _side(3, 1.0, False))
    assert strip_rail_pair(tie) == 0
    # Ends that are surface lines are not free.
    straight_ends = _candidate(_side(0, 1.0), _side(1, 5.0, False), _side(2, 1.2), _side(3, 4.0, False))
    assert strip_constraint(resolve_strip(straight_ends, ON), straight_ends).free_end_patch_chain_ids == ()


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
    assert report["options"] == {"straighten_strips": True, "straighten_bevel_strips": True}
    assert report["candidate_count"] == 5
    assert report["accepted_count"] == 1
    assert report["suppressed_by_reason"] == {"already a rectangle": 2, "long sides are straight on the surface": 2}
    assert report["constraint_count"] == 1
    assert report["constraints"][0]["patch_id"] == ARCH_FRONT
    assert "features" not in inspect_pipeline_context(base)
    # With the option off the shapes keep their grade; only the strip waits for the option.
    off = inspect_pipeline_context(run_pass_2_features(base))["features"]
    assert off["accepted_count"] == 0 and off["constraint_count"] == 0
    assert off["suppressed_by_reason"] == {
        "already a rectangle": 2, "long sides are straight on the surface": 2, "option off": 1,
    }


# ------------------------------------------------------------------ guard


@pytest.mark.parametrize("name", sorted(path.name for path in DATA.glob("*.json")))
def test_default_pass_2_leaves_the_solve_unchanged(name) -> None:
    base = _pass_1(_load_capture(name))
    assert run_skeleton_solve(run_pass_2_features(base)) == run_skeleton_solve(base)


REFERENCES = Path(__file__).resolve().parents[2] / "dev" / "tools" / "cftuv_parity" / "reference"
UNMARKED = [DATA / path.name for path in sorted(DATA.glob("*.json"))] + sorted(REFERENCES.glob("*.capture.json"))


@pytest.mark.parametrize("path", UNMARKED, ids=lambda path: path.name)
@pytest.mark.parametrize("strips", (False, True), ids=("strips_off", "strips_on"))
def test_a_mesh_without_marks_solves_the_same_with_the_bevel_option_at_its_default(path, strips) -> None:
    from dev.tools.scaffold_graph_debug.snapshot_io import load_source_snapshot

    base = _pass_1(load_source_snapshot(path))
    default = run_pass_2_features(base, FeatureOptions(straighten_strips=strips))
    assert default.feature_snapshot.options.straighten_bevel_strips
    off = run_pass_2_features(base, FeatureOptions(straighten_strips=strips, straighten_bevel_strips=False))
    assert default.feature_snapshot.constraints == off.feature_snapshot.constraints
    assert run_skeleton_solve(default) == run_skeleton_solve(off)


# --------------------------------------------- STRIP acceptance on the captures

BEVEL_CASES = DATA / "bevel_cases"
# Verdicts of the strip rule (option on): A accepted, S suppressed as long sides straight
# on the surface (plan Slice AF), N suppressed as no rail pair (plan Slice AJ).
STRIP_VERDICTS = [
    (DATA / "artist_arch_bevel.json", "f16", "A"),
    (REFERENCES / "Arc.capture.json", "f16", "A"),
    (REFERENCES / "collumn.capture.json", "f1", "A"),
    (REFERENCES / "collumn.capture.json", "f355", "N"),  # the flat back wall: mirrored profiles
    (REFERENCES / "building_walls.capture.json", "f1415", "A"),  # a folded one-face strip
    (BEVEL_CASES / "u_rounded_wall_noise_top.capture.json", "f110", "S"),  # a wall that develops
    (BEVEL_CASES / "u_rounded_wall_noise_top.capture.json", "f211", "S"),
    *[(BEVEL_CASES / "u_rounded_wall_noise_top.capture.json", f"f{i}", "A") for i in (35, 36, 71, 73, 96)],
    *[(BEVEL_CASES / "f_rect_inarc.capture.json", f"f{i}", "S") for i in (20, 22, 24, 26)],
    *[(BEVEL_CASES / "e_arch_s2_n20.capture.json", f"f{i}", "S") for i in (22, 24, 42)],
    *[(BEVEL_CASES / name, f"f{i}", "S") for name in ("b_rect_s2.capture.json", "h_rect_s2_tri.capture.json",
                                                       "m_rect_s2_trimain.capture.json") for i in (8, 10, 12, 14)],
    *[(BEVEL_CASES / "c_arch_s2.capture.json", f"f{i}", "S") for i in (22, 24, 42)],
    *[(BEVEL_CASES / "d_cyl_s2.capture.json", f"f{i}", "S") for i in (124, 154)],
]


@pytest.mark.parametrize(("path", "face", "verdict"), STRIP_VERDICTS, ids=lambda item: getattr(item, "name", item))
def test_strip_acceptance_reads_long_sides_curved_on_the_surface(path, face, verdict) -> None:
    from dev.tools.scaffold_graph_debug.snapshot_io import load_source_snapshot

    context = _pass_1(load_source_snapshot(path))
    candidates = strip_candidates(context.topology_snapshot, context.geometry_facts, context.relation_snapshot)
    (candidate,) = [c for c in candidates if str(c.patch_id) == f"patch:seed:{face}"]
    instance = resolve_strip(candidate, ON)
    assert (instance.status is FeatureInstanceStatus.ACCEPTED) == (verdict == "A")
    if verdict == "S":
        assert instance.suppression_reason is FeatureSuppressionReason.LONG_SIDES_STRAIGHT
    if verdict == "N":
        assert instance.suppression_reason is FeatureSuppressionReason.NO_RAIL_PAIR


# --------------------------------------------- the column (plan Slice AJ)


@pytest.fixture(scope="module")
def column():
    from dev.tools.scaffold_graph_debug.snapshot_io import load_source_snapshot

    base = _pass_1(load_source_snapshot(REFERENCES / "collumn.capture.json"))
    on = run_pass_2_features(base, ON)
    return base, on, run_skeleton_solve(on)


def test_column_back_wall_with_mirrored_profiles_is_not_a_strip(column) -> None:
    base, on, solve = column
    assert _instance(on, "patch:seed:f355").suppression_reason is FeatureSuppressionReason.NO_RAIL_PAIR
    assert not [c for c in on.feature_snapshot.constraints if str(c.patch_id) == "patch:seed:f355"]
    assert _skeleton(solve, "patch:seed:f355") == _skeleton(run_skeleton_solve(base), "patch:seed:f355")
    # Paired positive: the column body next to it is a strip.
    assert _instance(on, "patch:seed:f1").status is FeatureInstanceStatus.ACCEPTED


def test_column_body_rails_are_its_arcs_and_its_profile_seams_are_free(column) -> None:
    _base, on, solve = column
    (constraint,) = [c for c in on.feature_snapshot.constraints if str(c.patch_id) == "patch:seed:f1"]
    candidate = next(c for c in on.feature_snapshot.candidates if str(c.patch_id) == "patch:seed:f1")
    arcs, seams = (1, 3), (0, 2)
    assert constraint.rail_pair == 1
    assert constraint.free_end_patch_chain_ids == tuple(candidate.sides[i].patch_chain_id for i in seams)
    assert constraint.target_lengths == pytest.approx((6.5406, (2.8200 + 2.9312) / 2.0), abs=1e-3)
    skeleton = _skeleton(solve, "patch:seed:f1")
    assert skeleton.frame == STRIP_LAYOUT
    runs = [e for e in on.relation_snapshot.patch_chain_directional_evidence if str(e.patch_id) == "patch:seed:f1"]
    free_uses = set(constraint.free_end_patch_chain_ids)
    assert skeleton.fill_run_ids == frozenset(e.id for e in runs if e.patch_chain_id in free_uses)
    assert all(skeleton.axis_role_by_run[e.id] == "AXIS_A" for e in runs if e.patch_chain_id not in free_uses)
    pins = {v.source_vertex_id: v.uv for v in solve.vertices if v.pinned and v.patch_id == "patch:seed:f1"}
    # The seams' inner vertices are left to the fill; their end points are the rail ends.
    for index in seams:
        run = on.geometry_facts.chain_facts[candidate.sides[index].chain_id].source_vertex_run
        assert not set(map(str, run[1:-1])) & set(pins)
        assert {str(run[0]), str(run[-1])} <= set(pins)
    # Each arc lies straight on one line of the strip, both with one length.
    spans = []
    for index in arcs:
        run = on.geometry_facts.chain_facts[candidate.sides[index].chain_id].source_vertex_run
        uvs = [pins[str(vertex)] for vertex in run]
        assert max(v for _u, v in uvs) - min(v for _u, v in uvs) < 1e-9
        spans.append(max(u for u, _v in uvs) - min(u for u, _v in uvs))
    assert spans == pytest.approx([constraint.target_lengths[1]] * 2, abs=1e-6)
    assert solve.axis_parallel_violations == ()


# ------------------------------------- flat strips with flaps (plan Slice AJ)


def _quarter_annulus(s, t):
    return ((1.0 + 0.3 * t) * cos(0.5 * pi * s), (1.0 + 0.3 * t) * sin(0.5 * pi * s))


def _mirrored_lens(s, t):
    return (3.0 * s, (t - 0.5) * (0.6 + 0.8 * sin(pi * s)))


def _shifted_s(s, t):
    """A sine S of one full wave and the same S shifted by 0.5 across: both point-symmetric."""

    return (4.0 * s, 0.8 * sin(2.0 * pi * s) + 0.5 * t)


def _offset_s(s, t):
    """A sine S of one full wave and its offset curve at the distance 0.3 t (not point-symmetric)."""

    x, y = 4.0 * s, 0.8 * sin(2.0 * pi * s)
    dx, dy = 4.0, 1.6 * pi * cos(2.0 * pi * s)
    norm = hypot(dx, dy)
    return (x - 0.3 * t * dy / norm, y + 0.3 * t * dx / norm)


def _mirrored_long_sides_alike_short_arcs(s, t):
    """Long sides (t = 0, 1) bowing apart, short sides (s = 0, 1) bowing the same way."""

    return ((t - 0.5) * (1.0 + 0.4 * sin(pi * s)), 3.0 * s + 0.15 * (1.0 - (2.0 * t - 1.0) ** 2))


def _flat_strip(outline, columns, rows, **noise):
    context = run_pass_2_features(_pass_1(make_flat_strip_with_flaps_source(outline, columns, rows, **noise)), ON)
    (patch_id,) = [
        patch_id for patch_id, patch in context.topology_snapshot.patches.items()
        if "f0_0" in {str(face_id) for face_id in patch.source_face_ids}
    ]
    return context, str(patch_id)


@pytest.mark.parametrize("seed", range(4))
@pytest.mark.parametrize("noise", (0.05, 0.1))
def test_noise_does_not_turn_a_mirrored_wall_into_a_strip_or_a_strip_into_a_wall(noise, seed) -> None:
    # Out-of-plane noise on the inner vertices of the long sides, as a share of
    # a segment: at 5% the plane-turn reading accepted the lens in 2 of 4 seeds.
    lens, lens_id = _flat_strip(_mirrored_lens, 12, 3, noise=noise * 3.0 / 12, seed=seed)
    assert _instance(lens, lens_id).suppression_reason is FeatureSuppressionReason.NO_RAIL_PAIR
    ring, ring_id = _flat_strip(_quarter_annulus, 12, 3, noise=noise * 0.5 * pi / 12, seed=seed)
    assert _instance(ring, ring_id).status is FeatureInstanceStatus.ACCEPTED
    (constraint,) = ring.feature_snapshot.constraints
    assert constraint.rail_pair == 0  # the two arcs


@pytest.mark.parametrize("columns", (16, 23, 24, 31))
def test_an_exactly_symmetric_s_pair_is_no_rail_pair(columns) -> None:
    # Both long sides are curved on the surface, but each S closes no net area
    # with its chord: no bow to compare, whatever the segment count (before,
    # rounding noise of order 1e-17 decided it and flipped with the count).
    context, patch_id = _flat_strip(_shifted_s, columns, 3)
    candidate = next(c for c in context.feature_snapshot.candidates if str(c.patch_id) == patch_id)
    assert not candidate.sides[0].is_surface_line and not candidate.sides[2].is_surface_line
    assert candidate.sides[0].chord_area_vector is None and candidate.sides[2].chord_area_vector is None
    assert _instance(context, patch_id).suppression_reason is FeatureSuppressionReason.NO_RAIL_PAIR
    # An inflected side is read by its net bow: the offset of the S is not
    # point-symmetric and keeps a real net area; its exact twin keeps none.
    offset, offset_id = _flat_strip(_offset_s, columns, 3)
    sides = next(c for c in offset.feature_snapshot.candidates if str(c.patch_id) == offset_id).sides
    assert sides[0].chord_area_vector is None and sides[2].chord_area_vector is not None


def test_a_free_end_of_one_run_gets_no_inner_pin() -> None:
    context, patch_id = _flat_strip(_mirrored_long_sides_alike_short_arcs, 12, 6)
    (constraint,) = context.feature_snapshot.constraints
    assert constraint.rail_pair == 1  # the short arcs; the mirrored long sides are free
    solve = run_skeleton_solve(context)
    skeleton = _skeleton(solve, patch_id)
    assert skeleton.frame == STRIP_LAYOUT
    runs = context.relation_snapshot.patch_chain_directional_evidence
    for use in constraint.free_end_patch_chain_ids:
        (run,) = [e for e in runs if e.patch_chain_id == use]  # one run: its two ends are the rail ends
        assert run.id in skeleton.fill_run_ids
    pinned = {v.source_vertex_id for v in solve.vertices if v.pinned and v.patch_id == patch_id}
    inner = {f"c{i}_{j}" for i in range(1, 12) for j in (0, 6)}
    corners = {"c0_0", "c12_0", "c0_6", "c12_6"}
    assert not pinned & inner
    assert corners <= pinned
    # Paired positive: the rails carry their stations.
    assert {f"c{i}_{j}" for i in (0, 12) for j in range(7)} <= pinned


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
