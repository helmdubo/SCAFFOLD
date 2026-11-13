"""
Layer: tests

Rules:
- Quilts as data (plan Slice AH): island assembly under the user filter's
  SeamDirectives, the UV cut set of the solve, and no change without a filter.
- The pure scale helpers of the write boundary (headless; bpy is never loaded).
- No production logic here.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from dev.tools.scaffold_graph_debug.snapshot_io import load_source_snapshot
from scaffold_core.layer_4_features.model import FeatureOptions
from scaffold_core.layer_5_runtime.islands import (
    STITCH_BEVEL_LADDER_REASON,
    STITCH_JOIN_BY_FILTER_PREFIX,
    STITCH_NON_TREE_REASON,
    STITCH_SPLIT_BY_FILTER_PREFIX,
)
from scaffold_core.layer_5_runtime.pins import run_skeleton_solve
from scaffold_core.layer_5_runtime.skeleton import LADDER_LAYOUT
from scaffold_core.layer_5_runtime.uv_transfer import (
    LAYOUT_UV_PER_MESH_UNIT,
    chart_rescale_factor,
    polygon_uv_area,
)
from scaffold_core.pipeline.passes import (
    run_pass_0,
    run_pass_1_relations,
    run_pass_2_features,
    run_pass_3_filters,
)
from scaffold_core.tests.fixtures.cylinder_tube import make_cylinder_tube_without_caps_with_one_seam_source
from scaffold_core.tests.fixtures.quad_ladders import make_quad_grid_with_inner_seam_source
from scaffold_core.user_filters.model import (
    RULE_BEVEL_WITH_ITS_SURFACES,
    RULE_VERTICAL_APART_FROM_HORIZONTAL,
    FilterOptions,
    FilterSnapshot,
    SeamDirectiveKind,
)

DATA = Path(__file__).resolve().parent / "data"
ROUNDED = DATA / "bevel_cases" / "u_rounded_wall_noise_top.capture.json"
UP = (0.0, 0.0, 1.0)
CAPTURES = (
    ROUNDED,
    DATA / "bevel_cases" / "a_cube_s3.capture.json",
    DATA / "bevel_cases" / "c_arch_s2.capture.json",
    DATA / "artist_cyl_multiseam.json",
    DATA / "artist_cross_band.json",
    DATA / "artist_walls_007.json",
)


def _context(capture: Path, world_up=None, strips: bool = False):
    context = run_pass_2_features(
        run_pass_1_relations(run_pass_0(load_source_snapshot(capture))), FeatureOptions(straighten_strips=strips)
    )
    return run_pass_3_filters(context, FilterOptions(world_up=world_up))


def _short(patch_id) -> str:
    return str(patch_id).replace("patch:seed:", "")


@pytest.mark.parametrize("capture", CAPTURES, ids=lambda path: path.stem)
def test_without_a_world_up_the_solve_equals_a_run_without_pass_3(capture: Path) -> None:
    plain = run_pass_2_features(run_pass_1_relations(run_pass_0(load_source_snapshot(capture))))
    filtered = run_pass_3_filters(plain, FilterOptions())
    before, after = run_skeleton_solve(plain), run_skeleton_solve(filtered)

    assert after.assembly == before.assembly
    assert after.vertices == before.vertices
    assert [s.diagnostics for s in after.skeletons] == [s.diagnostics for s in before.skeletons]
    assert after.residual_max == before.residual_max


def test_the_users_mesh_lies_as_the_three_quilts_of_the_reference() -> None:
    solve = run_skeleton_solve(_context(ROUNDED, UP))
    quilts = {frozenset(_short(p) for p in island.patch_ids) for island in solve.assembly.islands}

    assert quilts == {
        frozenset({"f110", "f211", "f112", "f34", "f72", "f94"}),  # the walls with the vertical strips
        frozenset({"f0", "f35", "f71", "f96", "f29", "f32", "f33"}),  # the top with its strips and junctions
        frozenset({"f111", "f36", "f73", "f95", "f28", "f30", "f31"}),  # the bottom with its strips and junctions
    }
    reasons = Counter(decision.reason for decision in solve.assembly.decisions)
    assert reasons == {
        STITCH_SPLIT_BY_FILTER_PREFIX + RULE_VERTICAL_APART_FROM_HORIZONTAL: 12,
        STITCH_JOIN_BY_FILTER_PREFIX + RULE_BEVEL_WITH_ITS_SURFACES: 17,
        STITCH_NON_TREE_REASON: 7,
    }
    # The wall ring is a cycle of six joined seams of two edges each; the last
    # in tree order (the shortest in 3D, 4.1475) stays open: f94|f211.
    ring = {frozenset(("f34", "f110")), frozenset(("f34", "f112")), frozenset(("f72", "f112")),
            frozenset(("f72", "f211")), frozenset(("f94", "f211")), frozenset(("f94", "f110"))}
    open_in_ring = [
        d for d in solve.assembly.decisions
        if frozenset((_short(d.first_patch_id), _short(d.second_patch_id))) in ring and not d.accepted
    ]
    assert [(d.chain_id, d.reason) for d in open_in_ring] == [("chain:e301:e337", STITCH_NON_TREE_REASON)]


def test_a_face_without_width_is_reported_by_layer_2() -> None:
    # g_short's f30 is 0.53 long and 6e-8 wide: the quilt lays it as a line,
    # as its 3D shape is; Layer 2 says so, and no other bevel face is flagged.
    flagged = {
        (capture.name, diagnostic.entity_ids)
        for capture in sorted((DATA / "bevel_cases").glob("*.capture.json"))
        for diagnostic in run_pass_1_relations(run_pass_0(load_source_snapshot(capture))).geometry_facts.diagnostics
        if diagnostic.code == "GEOMETRY_FACE_NEAR_ZERO_AREA"
    }

    assert flagged == {("g_short.capture.json", ("patch:seed:f30", "f30"))}


def test_a_ladder_patch_in_a_quilt_is_laid_by_the_quilt_without_a_diagnostic() -> None:
    solve = run_skeleton_solve(_context(ROUNDED, UP))

    assert not any(skeleton.frame == LADDER_LAYOUT for skeleton in solve.skeletons)
    assert not any("ladder constraint not applied" in line for line in solve.diagnostics)
    wall_quilt = solve.assembly.island_by_patch_id["patch:seed:f34"]
    assert sum(1 for vertex in solve.vertices if vertex.pinned and vertex.island_id == wall_quilt) > 0
    assert solve.axis_parallel_violations == () and solve.node_frame_mismatches == ()


def test_without_the_filter_a_ladder_patch_is_still_laid_by_itself() -> None:
    solve = run_skeleton_solve(_context(ROUNDED))

    assert sum(1 for skeleton in solve.skeletons if skeleton.frame == LADDER_LAYOUT) == 9
    assert len(solve.assembly.islands) == 20


def test_a_split_directive_also_splits_a_seam_the_structure_stitches() -> None:
    # artist_walls_007: walls and the floor slabs between them, stitched today.
    plain = run_skeleton_solve(_context(DATA / "artist_walls_007.json"))
    filtered = run_skeleton_solve(_context(DATA / "artist_walls_007.json", UP))
    stitched_before = {d.chain_id for d in plain.assembly.decisions if d.accepted}
    split = {d.chain_id for d in filtered.assembly.decisions if d.reason.startswith(STITCH_SPLIT_BY_FILTER_PREFIX)}

    assert split & stitched_before
    assert not split & filtered.stitched_chain_ids


@pytest.mark.parametrize("world_up", (None, UP), ids=("no filter", "filter"))
@pytest.mark.parametrize("capture", CAPTURES, ids=lambda path: path.stem)
def test_the_uv_cut_set_is_the_complement_of_the_stitched_seams(capture: Path, world_up) -> None:
    context = _context(capture, world_up)
    solve = run_skeleton_solve(context)
    topology = context.topology_snapshot
    # A Chain is a seam when one of its edges is walked on two sides by the
    # patch uses: two uses, or one use that walks a slit twice.
    sides = Counter(
        (str(patch_chain.chain_id), str(edge_id))
        for patch_chain in topology.patch_chains.values()
        for edge_id in topology.chains[patch_chain.chain_id].source_edge_ids
    )
    shared = {chain_id for (chain_id, _edge_id), count in sides.items() if count >= 2}
    self_seams = {
        str(junction.matched_chain_id)
        for junction in context.relation_snapshot.scaffold_junctions
        if junction.kind.value == "SELF_SEAM" and junction.matched_chain_id is not None
    }

    assert set(solve.uv_cut_chain_ids) == shared - solve.stitched_chain_ids
    assert solve.stitched_chain_ids == {d.chain_id for d in solve.assembly.decisions if d.accepted}
    assert self_seams <= set(solve.uv_cut_chain_ids)
    assert solve.uv_cut_source_edge_ids == {
        str(edge_id) for chain_id in solve.uv_cut_chain_ids for edge_id in topology.chains[chain_id].source_edge_ids
    }
    stitched_edges = {
        str(edge_id) for chain_id in solve.stitched_chain_ids for edge_id in topology.chains[chain_id].source_edge_ids
    }
    assert not stitched_edges & solve.uv_cut_source_edge_ids
    # The user's rule: a user seam between two solved faces that the tree did not stitch is a cut.
    source = context.source_snapshot
    faces_of_edge = Counter(
        str(edge_id) for face_id in source.selected_face_ids for edge_id in source.faces[face_id].edge_ids
    )
    user_seams = {str(mark.target_id) for mark in source.marks if mark.kind.name == "SEAM"}
    interior_seams = {edge_id for edge_id in user_seams if faces_of_edge[edge_id] == 2}
    assert interior_seams - stitched_edges <= solve.uv_cut_source_edge_ids


def _plain_solve(source):
    context = run_pass_3_filters(run_pass_2_features(run_pass_1_relations(run_pass_0(source))), FilterOptions())
    return context, run_skeleton_solve(context)


def test_a_slit_seam_inside_a_patch_is_a_cut() -> None:
    # One interior edge carries a seam from the border into the grid: one
    # patch, and its loop walks the slit twice (a single use, e1 then e1).
    context, solve = _plain_solve(make_quad_grid_with_inner_seam_source())
    slit = [chain for chain in context.topology_snapshot.chains.values() if len(set(chain.source_edge_ids)) == 1]

    assert [str(chain.id) for chain in slit] == ["chain:e1:e1"]
    assert sum(1 for pc in context.topology_snapshot.patch_chains.values() if pc.chain_id == slit[0].id) == 1
    assert solve.uv_cut_chain_ids == ("chain:e1:e1",)
    assert solve.uv_cut_source_edge_ids == {"e1"}


def test_a_seam_self_chain_is_a_cut() -> None:
    # The tube's one seam: a Chain with two uses in the same patch (SEAM_SELF).
    context, solve = _plain_solve(make_cylinder_tube_without_caps_with_one_seam_source())
    self_seams = {
        str(junction.matched_chain_id)
        for junction in context.relation_snapshot.scaffold_junctions
        if junction.kind.value == "SELF_SEAM"
    }

    assert self_seams == {"chain:e_v0"}
    assert solve.uv_cut_chain_ids == ("chain:e_v0",)
    assert solve.uv_cut_source_edge_ids == {"e_v0"}


def test_join_seams_enter_the_tree_after_every_other_seam_longest_first() -> None:
    context = _context(ROUNDED, UP)
    solve = run_skeleton_solve(context)
    joins = {
        (str(d.chain_id), frozenset((str(d.first_patch_id), str(d.second_patch_id))))
        for d in context.filter_snapshot.directives
        if d.kind is SeamDirectiveKind.JOIN
    }
    # Decisions follow the tree order: one per seam.
    is_join = [
        (d.chain_id, frozenset((d.first_patch_id, d.second_patch_id))) in joins for d in solve.assembly.decisions
    ]
    # A joined seam is ordered by its 3D length, not by its edge count: most
    # joined seams are one or two edges, and the id would break those ties.
    length_by_seam = {
        (str(a.chain_id), frozenset((str(a.first_patch_id), str(a.second_patch_id)))): a.shared_length
        for a in context.relation_snapshot.patch_adjacencies.values()
    }
    lengths = [
        length_by_seam[(d.chain_id, frozenset((d.first_patch_id, d.second_patch_id)))]
        for d, join in zip(solve.assembly.decisions, is_join)
        if join
    ]
    edge_counts = [
        len(context.topology_snapshot.chains[d.chain_id].source_edge_ids)
        for d, join in zip(solve.assembly.decisions, is_join)
        if join
    ]

    assert len(lengths) == len(joins) == 24
    assert is_join == sorted(is_join)  # every other seam first, then the joined seams
    assert lengths == sorted(lengths, reverse=True) and lengths[0] > lengths[-1]
    assert edge_counts != sorted(edge_counts, reverse=True)  # the edge count would order them otherwise


@pytest.mark.parametrize("factor", (0.001, 1000.0))
def test_the_join_order_and_the_stitch_decisions_do_not_depend_on_the_mesh_scale(factor: float) -> None:
    # g_short's joined seams order by 3D length; an absolute rounding of the
    # length changed 8 stitched seams at scale 0.001. Pins and the tree order
    # of the other seams still move with the scale (Layer 2's absolute
    # EPSILON drops the 6e-8 wide f30 to a zero normal at 0.001), so only the
    # stitch decisions and the order of the joined seams are compared.
    source = load_source_snapshot(DATA / "bevel_cases" / "g_short.capture.json")
    scaled = replace(source, vertices={
        key: replace(vertex, position=tuple(value * factor for value in vertex.position))
        for key, vertex in source.vertices.items()
    })

    def decisions(src):
        context = run_pass_3_filters(run_pass_2_features(run_pass_1_relations(run_pass_0(src))), FilterOptions(UP))
        joins = {str(d.chain_id) for d in context.filter_snapshot.directives if d.kind is SeamDirectiveKind.JOIN}
        solve = run_skeleton_solve(context)
        return (
            {(d.chain_id, d.first_patch_id, d.second_patch_id, d.accepted) for d in solve.assembly.decisions},
            [d.chain_id for d in solve.assembly.decisions if d.chain_id in joins],
        )

    plain_set, plain_joins = decisions(source)
    scaled_set, scaled_joins = decisions(scaled)

    assert len(plain_joins) > 2
    assert scaled_set == plain_set
    assert scaled_joins == plain_joins


def test_a_ladder_patch_with_a_join_lies_in_its_quilt_and_its_other_seams_are_the_structures() -> None:
    # Only one JOIN, f34|f110: the other ladder patches stay alone, f34 lies
    # with f110 and its seams without a directive go to the structure.
    plain = _context(ROUNDED)
    join = next(
        d for d in _context(ROUNDED, UP).filter_snapshot.directives
        if d.kind is SeamDirectiveKind.JOIN
        and {_short(d.first_patch_id), _short(d.second_patch_id)} == {"f34", "f110"}
    )
    solve = run_skeleton_solve(replace(plain, filter_snapshot=FilterSnapshot(FilterOptions(UP), directives=(join,))))
    island_id = solve.assembly.island_by_patch_id["patch:seed:f34"]
    island = next(island for island in solve.assembly.islands if island.id == island_id)
    f34_decisions = [d for d in solve.assembly.decisions if "patch:seed:f34" in (d.first_patch_id, d.second_patch_id)]

    assert {"f34", "f110"} <= {_short(p) for p in island.patch_ids} and len(island.patch_ids) > 2
    assert next(s for s in solve.skeletons if s.island_id == island_id).frame != LADDER_LAYOUT
    assert sum(1 for skeleton in solve.skeletons if skeleton.frame == LADDER_LAYOUT) == 8
    assert not any(d.reason == STITCH_BEVEL_LADDER_REASON for d in f34_decisions)
    assert sum(1 for d in f34_decisions if d.accepted) >= 2


def test_a_quilt_is_connected_by_its_stitched_seams() -> None:
    context = _context(ROUNDED, UP)
    solve = run_skeleton_solve(context)
    patch_of_use = {str(pc.chain_id): set() for pc in context.topology_snapshot.patch_chains.values()}
    for pc in context.topology_snapshot.patch_chains.values():
        patch_of_use[str(pc.chain_id)].add(str(pc.patch_id))
    for island in solve.assembly.islands:
        members = set(island.patch_ids)
        reached = {island.patch_ids[0]}
        for _ in members:
            for chain_id in island.stitched_chain_ids:
                if patch_of_use[chain_id] & reached:
                    reached |= patch_of_use[chain_id]
        assert reached == members
        assert len(island.stitched_chain_ids) == len(members) - 1  # a tree


def test_the_layout_scale_is_one_uv_unit_per_mesh_unit() -> None:
    assert LAYOUT_UV_PER_MESH_UNIT == 1.0


def test_polygon_uv_area_is_unsigned_shoelace() -> None:
    square = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]
    assert polygon_uv_area(square) == pytest.approx(4.0)
    assert polygon_uv_area(list(reversed(square))) == pytest.approx(4.0)
    assert polygon_uv_area([(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]) == pytest.approx(0.5)
    assert polygon_uv_area([(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)]) == 0.0


def test_chart_rescale_factor_gives_the_uv_area_its_3d_area() -> None:
    # A chart packed into the unit square at linear scale 0.147 of true.
    uv_area, area_3d = 0.147 ** 2 * 4.788, 4.788
    factor = chart_rescale_factor(uv_area, area_3d)
    assert factor == pytest.approx(1.0 / 0.147)
    assert uv_area * factor ** 2 == pytest.approx(area_3d * LAYOUT_UV_PER_MESH_UNIT ** 2)
    assert chart_rescale_factor(area_3d, area_3d) == pytest.approx(1.0)
    assert chart_rescale_factor(1.0, 9.0, layout_scale=0.25) == pytest.approx(0.75)


@pytest.mark.parametrize("uv_area, area_3d", [(0.0, 1.0), (1.0, 0.0), (0.0, 0.0), (-1.0, 1.0)])
def test_a_degenerate_chart_is_left_alone(uv_area: float, area_3d: float) -> None:
    assert chart_rescale_factor(uv_area, area_3d) is None
