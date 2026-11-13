"""
Layer: tests

Rules:
- Quilts as data (plan Slice AH): island assembly under the user filter's
  SeamDirectives, the UV cut set of the solve, and no change without a filter.
- No production logic here.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from dev.tools.scaffold_graph_debug.snapshot_io import load_source_snapshot
from scaffold_core.layer_4_features.model import FeatureOptions
from scaffold_core.layer_5_runtime.islands import (
    STITCH_JOIN_BY_FILTER_PREFIX,
    STITCH_NON_TREE_REASON,
    STITCH_SPLIT_BY_FILTER_PREFIX,
)
from scaffold_core.layer_5_runtime.pins import run_skeleton_solve
from scaffold_core.layer_5_runtime.skeleton import LADDER_LAYOUT
from scaffold_core.pipeline.passes import (
    run_pass_0,
    run_pass_1_relations,
    run_pass_2_features,
    run_pass_3_filters,
)
from scaffold_core.user_filters.model import (
    RULE_BEVEL_WITH_ITS_SURFACES,
    RULE_VERTICAL_APART_FROM_HORIZONTAL,
    FilterOptions,
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
    # The wall ring is a cycle of six joined seams; the last in tree order
    # (all six have two edges, so by adjacency id) stays open: f34|f112.
    ring = {frozenset(("f34", "f110")), frozenset(("f34", "f112")), frozenset(("f72", "f112")),
            frozenset(("f72", "f211")), frozenset(("f94", "f211")), frozenset(("f94", "f110"))}
    open_in_ring = [
        d for d in solve.assembly.decisions
        if frozenset((_short(d.first_patch_id), _short(d.second_patch_id))) in ring and not d.accepted
    ]
    assert [(d.chain_id, d.reason) for d in open_in_ring] == [("chain:e338:e122", STITCH_NON_TREE_REASON)]


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
    uses = Counter(str(patch_chain.chain_id) for patch_chain in topology.patch_chains.values())
    shared = {chain_id for chain_id, count in uses.items() if count >= 2}
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
