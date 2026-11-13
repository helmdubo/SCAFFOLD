"""
Layer: tests

Rules:
- G5a skeleton runtime acceptance on canonical and artist fixtures.
- Invariants are asserted as validation outputs per the phase contract.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import replace
from math import atan2, cos, dist, pi, sin
from pathlib import Path
from types import SimpleNamespace

import pytest

from scaffold_core.ids import SourceEdgeId, SourceFaceId, SourceMeshId, SourceVertexId
from scaffold_core.layer_0_source.marks import SourceMark, SourceMarkKind
from scaffold_core.layer_0_source.snapshot import (
    MeshEdgeRef,
    MeshFaceRef,
    MeshVertexRef,
    SourceMeshSnapshot,
)
from scaffold_core.layer_3_relations.model import PatchChainEndpointRole, RunCornerKind
from scaffold_core.layer_4_features.model import FeatureOptions
from scaffold_core.layer_5_runtime.islands import IslandAssembly
from scaffold_core.layer_5_runtime.pins import PinnedVertex, SolveResult, _station_pins, run_skeleton_solve
from scaffold_core.layer_5_runtime.uv_transfer import write_pinned_uvs
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations, run_pass_2_features
from scaffold_core.tests.fixtures.bent_hinge import make_bent_hinge_panels_source
from scaffold_core.tests.fixtures.capped_prism import (
    make_capped_decagon_prism_odd_strips_source,
    make_capped_square_prism_all_seams_source,
)
from scaffold_core.tests.fixtures.cylinder_tube import (
    make_cylinder_tube_without_caps_with_one_seam_source,
    make_cylinder_tube_without_caps_with_two_seams_source,
    make_segmented_cylinder_tube_without_caps_with_one_seam_source,
)
from scaffold_core.tests.fixtures.detached_parallel_walls import (
    make_detached_parallel_walls_source,
)
from scaffold_core.tests.fixtures.extruded_cross import make_extruded_cross_source
from scaffold_core.tests.fixtures.l_corridor_tunnel import (
    make_l_corridor_tunnel_seamed_folds_source,
)
from scaffold_core.tests.fixtures.reflex_corner import make_reflex_corner_walls_source
from scaffold_core.tests.fixtures.run_corner_sheets import (
    NOTCHED_SHEET_UNFOLDED,
    make_cut_corner_rectangle_source,
    make_folded_cut_corner_source,
    make_folded_l_sheet_source,
    make_folded_sheet_source,
    make_notched_sheet_source,
)
from scaffold_core.tests.fixtures.strip_patches import make_cut_annulus_source
from scaffold_core.tests.fixtures.t_vertex_wall import make_t_vertex_wall_source
from scaffold_core.tests.fixtures.tube_with_cap import make_tube_with_cap_source

DATA = Path(__file__).resolve().parent / "data"


def _solve(source):
    return run_skeleton_solve(run_pass_1_relations(run_pass_0(source)))


def _load_capture(name: str) -> SourceMeshSnapshot:
    data = json.loads((DATA / name).read_text(encoding="utf-8"))
    vertices = {
        SourceVertexId(k): MeshVertexRef(SourceVertexId(k), tuple(v))
        for k, v in data["vertices"].items()
    }
    edges = {
        SourceEdgeId(k): MeshEdgeRef(SourceEdgeId(k), (SourceVertexId(v[0]), SourceVertexId(v[1])))
        for k, v in data["edges"].items()
    }
    faces = {
        SourceFaceId(k): MeshFaceRef(
            SourceFaceId(k),
            tuple(SourceVertexId(v) for v in f["vertex_ids"]),
            tuple(SourceEdgeId(e) for e in f["edge_ids"]),
        )
        for k, f in data["faces"].items()
    }
    return SourceMeshSnapshot(
        id=SourceMeshId(data["id"]),
        vertices=vertices,
        edges=edges,
        faces=faces,
        selected_face_ids=tuple(SourceFaceId(f) for f in data["selected_face_ids"]),
        marks=tuple(
            SourceMark(kind=SourceMarkKind(m["kind"]), target_id=SourceEdgeId(m["target_id"]))
            for m in data["marks"]
        ),
    )


def test_two_seam_tube_unwraps_to_an_exact_rectangle() -> None:
    result = _solve(make_cylinder_tube_without_caps_with_two_seams_source())

    assert len(result.assembly.islands) == 1
    assert result.residual_max < 1e-6
    assert result.axis_parallel_violations == ()
    assert result.seam_length_mismatches == ()
    rows = {round(vertex.uv[1], 6) for vertex in result.vertices}
    assert len(rows) == 2  # top rail and bottom rail are two straight rows
    top = sorted(round(v.uv[0], 4) for v in result.vertices if round(v.uv[1], 6) == min(rows))
    bottom = sorted(round(v.uv[0], 4) for v in result.vertices if round(v.uv[1], 6) == max(rows))
    assert top == bottom  # columns align across the rails


def test_extruded_cross_band_unwraps_with_caps_as_separate_islands() -> None:
    result = _solve(make_extruded_cross_source())

    assert len(result.assembly.islands) == 3
    assert result.residual_max < 1e-6
    assert result.axis_parallel_violations == ()
    band_rows = {
        round(vertex.uv[1], 6)
        for vertex in result.vertices
        if "f_side" in vertex.patch_id
    }
    assert len(band_rows) == 2  # top rim and bottom rim are straight rows


def test_artist_cyl32_band_solves_as_rigid_grid() -> None:
    result = _solve(_load_capture("artist_cyl32.json"))

    assert len(result.assembly.islands) == 3  # stitched side band + two caps
    assert result.residual_max < 1e-6
    assert result.axis_parallel_violations == ()
    assert sum(1 for vertex in result.vertices if vertex.pinned) >= 60


def test_tube_with_cap_keeps_cap_island_separate() -> None:
    result = _solve(make_tube_with_cap_source())

    assert len(result.assembly.islands) == 2
    blocked = [d for d in result.assembly.decisions if not d.accepted and "defect" in d.reason]
    assert blocked  # the cap stitch is rejected by the Level A gate


def test_tunnel_folds_stitch_into_one_island() -> None:
    result = _solve(make_l_corridor_tunnel_seamed_folds_source())

    assert len(result.assembly.islands) == 1
    assert result.residual_max < 1e-6
    assert result.axis_parallel_violations == ()


def test_detached_walls_stay_two_islands() -> None:
    result = _solve(make_detached_parallel_walls_source())

    assert len(result.assembly.islands) == 2


def test_frustum_band_is_developable_and_solves_exactly() -> None:
    # Stretching the top ring turns the tube into a frustum band - still
    # a developable surface. The gate must keep stitching it and the
    # skeleton must stay exact (a wrong "non-developable" rejection here
    # would be over-blocking).
    source = make_cylinder_tube_without_caps_with_two_seams_source()
    stretched = dict(source.vertices)
    for vertex_id, ref in source.vertices.items():
        x, y, z = ref.position
        if z > 0.5:
            stretched[vertex_id] = MeshVertexRef(ref.id, (x * 2.0, y * 2.0, z))
    result = _solve(replace(source, vertices=stretched))

    assert len(result.assembly.islands) == 1
    assert result.residual_max < 1e-6
    assert result.axis_parallel_violations == ()


def test_seam_length_mismatch_is_reported_when_one_seam_side_is_scaled() -> None:
    # Direct unit check of the seam-length invariant: scaling directional
    # evidence on exactly one patch-chain side of one SELF_SEAM chain must
    # surface that chain in seam_length_mismatches.
    from scaffold_core.layer_5_runtime.pins import _seam_length_mismatches

    context = run_pass_1_relations(
        run_pass_0(make_cylinder_tube_without_caps_with_one_seam_source())
    )
    relations = context.relation_snapshot
    evidence_by_id = {e.id: e for e in relations.patch_chain_directional_evidence}

    assert _seam_length_mismatches(context, None, evidence_by_id) == []

    self_seam_chain_ids = sorted(
        str(junction.matched_chain_id)
        for junction in relations.scaffold_junctions
        if junction.kind.value == "SELF_SEAM" and junction.matched_chain_id is not None
    )
    assert self_seam_chain_ids
    target_chain_id = self_seam_chain_ids[0]
    seam_uses = [
        pc
        for pc in context.topology_snapshot.patch_chains.values()
        if str(pc.chain_id) == target_chain_id
    ]
    assert len(seam_uses) == 2
    scaled_side_id = str(seam_uses[0].id)
    perturbed = {
        evidence_id: (
            replace(evidence, length=evidence.length * 2.0)
            if str(evidence.patch_chain_id) == scaled_side_id
            else evidence
        )
        for evidence_id, evidence in evidence_by_id.items()
    }

    mismatches = _seam_length_mismatches(context, None, perturbed)

    assert any(mismatch.startswith(f"{target_chain_id}:") for mismatch in mismatches)


def test_contradictory_equations_are_excluded_with_diagnostics() -> None:
    # Direct unit check of the UNCONSTRAINED path: three nodes, two
    # consistent equations plus one contradicting the loop sum.
    from scaffold_core.layer_5_runtime.axis_solve import _lstsq

    consistent, residuals = _lstsq([("a", "b", 1.0, "e1"), ("b", "c", 1.0, "e2")])
    assert max(abs(r) for r in residuals) < 1e-9
    _coords, residuals = _lstsq(
        [("a", "b", 1.0, "e1"), ("b", "c", 1.0, "e2"), ("a", "c", 5.0, "e3")]
    )
    assert max(abs(r) for r in residuals) > 1e-2  # contradiction is visible, not hidden


def test_artist_multiseam_cylinder_open_band_unwraps_to_an_exact_rectangle() -> None:
    # A 32-segment cylinder cut into 6 vertical strips is an OPEN developable
    # band (one seam stays SPLIT, the rest SEW). It used to collapse because a
    # Layer 3 family leak through curved cap rims welded top and bottom rims
    # (plan Slice L). With the L1 straight-hinge rule the unchanged G5a solve
    # unrolls it; no Layer 5 traversal heuristic is involved.
    result = _solve(_load_capture("artist_cyl_multiseam.json"))

    _assert_band_is_exact_rectangle(result, island_count=3, residual_limit=1e-6)


def test_artist_multiseam_band_rims_open_into_ordered_island_rails() -> None:
    # Each rim closes into a loop rail across the six strips; Layer 3 keeps it
    # a closed, unordered loop. The band island leaves one seam cut, and the
    # Layer 3 cut view opens each rim there into one ordered rail (plan Slice O).
    context = run_pass_1_relations(run_pass_0(_load_capture("artist_cyl_multiseam.json")))
    rims = {
        frozenset(rail.ordered_member_directional_evidence_ids)
        for rail in context.relation_snapshot.scaffold_rails
        if rail.is_closed_loop
    }
    result = run_skeleton_solve(context)
    island_rails = [
        segment
        for skeleton in result.skeletons
        for segment in skeleton.rail_segments
        if len(segment.ordered_member_directional_evidence_ids) > 1
    ]

    assert len(rims) == 2
    assert {frozenset(segment.ordered_member_directional_evidence_ids) for segment in island_rails} == rims
    assert all(segment.is_ordered for segment in island_rails)
    assert result.rail_frame_conflicts == ()


def test_capped_odd_strip_prism_band_unwraps_to_an_exact_rectangle() -> None:
    # Synthetic reproduction of the multiseam case: a capped 10-segment prism
    # cut into two 5-segment strips.
    result = _solve(make_capped_decagon_prism_odd_strips_source())

    _assert_band_is_exact_rectangle(result, island_count=3, residual_limit=1e-9)


def _assert_band_is_exact_rectangle(result, island_count: int, residual_limit: float) -> None:
    band = max(result.assembly.islands, key=lambda island: len(island.patch_ids))
    pinned_in_band = [v for v in result.vertices if v.island_id == band.id and v.pinned]
    assert len(result.assembly.islands) == island_count
    assert result.diagnostics == ()
    assert result.axis_parallel_violations == ()
    assert result.seam_length_mismatches == ()
    assert result.residual_max < residual_limit
    assert pinned_in_band
    rows = sorted({round(vertex.uv[1], 6) for vertex in pinned_in_band})
    assert len(rows) == 2  # top rail and bottom rail are two straight rows
    top = sorted(round(v.uv[0], 4) for v in pinned_in_band if round(v.uv[1], 6) == rows[0])
    bottom = sorted(round(v.uv[0], 4) for v in pinned_in_band if round(v.uv[1], 6) == rows[-1])
    assert top == bottom  # columns align across the rails


def test_artist_walls_captures_keep_g5a_invariants() -> None:
    # Real buildings.blend walls, nearly every edge seamed (one patch per face).
    # G5a invariants are validation outputs: pinned UVs stay axis-parallel and
    # seam sides keep equal length. Island lines in the unfolded island frame
    # leave no axis bipartition conflict (plan Slice N: 156/31/20/8 pins
    # before, when families crossed cut seams and axes came from 3D).
    for name, min_pinned in (
        ("artist_walls_004_selection.json", 180),
        ("artist_walls_005.json", 50),
        ("artist_walls_006.json", 20),
        ("artist_walls_007.json", 190),
    ):
        result = _solve(_load_capture(name))

        assert result.axis_parallel_violations == (), name
        assert result.seam_length_mismatches == (), name
        assert result.node_frame_mismatches == (), name
        # Every island has a rigid frame, so the frame-free bipartition never
        # runs; the frame's own degradations must stay silent here.
        assert all(skeleton.frame == "UNFOLDED" for skeleton in result.skeletons), name
        assert not any(
            diagnostic.startswith(("island line not straight", "patch outside the rigid island frame"))
            for diagnostic in result.diagnostics
        ), name
        assert sum(1 for vertex in result.vertices if vertex.pinned) >= min_pinned, name
        # Plan Slices S and T: drift is absorbed and a run that leaves its axis
        # by more than drift is a jog, so no equation contradicts (walls_004
        # dropped 16 before; its f14 and f15 cross runs are the jogs).
        assert not any("contradictory" in diagnostic for diagnostic in result.diagnostics), name
        # Plan Slice O: Layer 3 orders every island rail of these walls, and
        # each runs one way along its axis in the unfolded frame.
        assert result.rail_frame_conflicts == (), name
        assert all(
            segment.is_ordered
            for skeleton in result.skeletons
            for segment in skeleton.rail_segments
            if len(segment.ordered_member_directional_evidence_ids) > 1
        ), name


def test_fully_seamed_box_unfolds_as_one_consistent_island() -> None:
    # Every edge is a seam, so the whole box is one island: a spanning tree of
    # stitched hinges. Layer 3 families cross the seams the tree leaves cut,
    # and at a box corner three families are mutually perpendicular in 3D, so
    # the frame-free bipartition left the box with no pins at all. Island
    # lines in the rigid unfolded frame give every run an axis (plan Slice N).
    context = run_pass_1_relations(run_pass_0(make_capped_square_prism_all_seams_source()))
    result = run_skeleton_solve(context)

    assert len(result.assembly.islands) == 1
    skeleton = result.skeletons[0]
    assert skeleton.frame == "UNFOLDED"
    assert skeleton.diagnostics == ()
    assert set(skeleton.axis_role_by_run.values()) == {"AXIS_A", "AXIS_B"}
    assert result.node_frame_mismatches == ()
    assert result.axis_parallel_violations == ()
    assert sum(1 for vertex in result.vertices if vertex.pinned) == 24
    # AXIS_B = normal x AXIS_A: every face stays counterclockwise in UV.
    areas = _pinned_face_areas(context, result)
    assert len(areas) == 6
    assert all(area > 0.0 for area in areas)


def test_island_lines_split_families_at_seams_the_island_cuts() -> None:
    context = run_pass_1_relations(run_pass_0(make_capped_square_prism_all_seams_source()))
    result = run_skeleton_solve(context)
    stitched = set(result.assembly.islands[0].stitched_chain_ids)
    line_by_run = result.skeletons[0].line_by_run

    split_families = tuple(
        family
        for family in context.relation_snapshot.connected_direction_families
        if len({line_by_run[member] for member in family.member_directional_evidence_ids}) > 1
    )
    assert split_families
    for family in split_families:
        assert any(
            record.first_patch_id != record.second_patch_id
            and str(record.shared_chain_id) not in stitched
            for record in family.crossing_records
        )


def test_t_vertex_wall_island_has_consistent_lines_and_axes() -> None:
    context = run_pass_1_relations(run_pass_0(make_t_vertex_wall_source()))
    result = run_skeleton_solve(context)

    assert len(result.assembly.islands) == 1
    assert result.skeletons[0].frame == "UNFOLDED"
    assert result.diagnostics == ()  # frame-free co-orientation conflicted here
    assert "OBLIQUE" not in result.skeletons[0].axis_role_by_run.values()
    assert all(area > 0.0 for area in _pinned_face_areas(context, result))


def _t_vertex_wall_with_warped_floor_a() -> SourceMeshSnapshot:
    source = make_t_vertex_wall_source()
    lifted = dict(source.vertices)
    corner = SourceVertexId("a0")
    lifted[corner] = MeshVertexRef(corner, (0.0, -1.0, 0.5))
    return replace(source, vertices=lifted)


def test_warped_face_stays_outside_the_rigid_island_frame() -> None:
    # A single warped n-gon has no rotation axis. It stays OBLIQUE with a
    # diagnostic; the planar wall keeps the rigid frame and its axes.
    result = _solve(_t_vertex_wall_with_warped_floor_a())

    skeleton = result.skeletons[0]
    assert skeleton.frame == "UNFOLDED"
    assert "patch outside the rigid island frame: patch:seed:f_floor_a -> OBLIQUE" in skeleton.diagnostics
    assert all(
        role == "OBLIQUE"
        for run_id, role in skeleton.axis_role_by_run.items()
        if ":f_floor_a:" in run_id
    )
    assert {
        role
        for run_id, role in skeleton.axis_role_by_run.items()
        if ":f_wall:" in run_id
    } == {"AXIS_A", "AXIS_B"}
    assert result.node_frame_mismatches == ()


def _ladder(rung_length: float):
    """Two 10 m AXIS_A rails joined by two AXIS_B rungs; the second rail drifts."""

    def run(run_id, run_length, direction):
        return SimpleNamespace(id=run_id, length=run_length, direction=direction)

    runs = (
        run("a0", 10.0, (1.0, 0.0, 0.0)),
        run("a1", rung_length, (1.0, 0.0, 0.0)),
        run("b0", 2.0, (0.0, 1.0, 0.0)),
        run("b1", 2.0, (0.0, 1.0, 0.0)),
    )
    ends = {"a0": ("n0", "n1"), "a1": ("n2", "n3"), "b0": ("n0", "n2"), "b1": ("n1", "n3")}
    node_by_run_end = {}
    for run_id, (start, end) in ends.items():
        node_by_run_end[(run_id, "START")] = start
        node_by_run_end[(run_id, "END")] = end
    roles = {"a0": "AXIS_A", "a1": "AXIS_A", "b0": "AXIS_B", "b1": "AXIS_B"}
    signs = {run_id: 1.0 for run_id in roles}
    return runs, roles, signs, node_by_run_end


def test_solve_absorbs_modelling_drift_relative_to_the_island_span() -> None:
    from scaffold_core.layer_5_runtime.axis_solve import solve_axis as _solve_axis

    for rung_length, contradictory in ((10.005, False), (10.05, True)):
        runs, roles, signs, node_by_run_end = _ladder(rung_length)
        diagnostics: list[str] = []
        solve = _solve_axis("AXIS_A", runs, roles, signs, node_by_run_end, diagnostics)
        # 5 mm over 10 m is drift (1 mm per metre); 5 cm is a contradiction
        assert bool(diagnostics) is contradictory, (rung_length, diagnostics)
        assert bool(solve.coordinate_by_node) is not contradictory


def test_framed_solve_uses_the_frame_drift_shared_with_the_jog_check() -> None:
    # plan Slice U: a long thin island (buildings walls.010, 8.5 x 0.5 m) lets
    # a 4.6 mm offset pass the jog check; the solve must absorb the same drift
    # instead of its much smaller span along the short axis.
    from scaffold_core.layer_5_runtime.axis_solve import solve_axis as _solve_axis

    runs, roles, signs, node_by_run_end = _ladder(10.05)
    own_span: list[str] = []
    _solve_axis("AXIS_A", runs, roles, signs, node_by_run_end, own_span)
    frame_drift: list[str] = []
    solve = _solve_axis("AXIS_A", runs, roles, signs, node_by_run_end, frame_drift, drift=0.1)

    assert own_span and not frame_drift
    assert solve.coordinate_by_node


def test_rigid_frame_gives_an_axis_only_within_the_planar_tolerance_angle() -> None:
    from math import cos, radians, sin

    from scaffold_core.layer_5_runtime.skeleton import _frame_roles_and_signs

    def run(run_id, degrees, run_length=1.0):
        angle = radians(degrees)
        return SimpleNamespace(id=run_id, length=run_length, direction=(cos(angle), sin(angle), 0.0))

    runs = (run("seed", 0.0, 10.0), run("drift", 3.0), run("slope", 11.25), run("cross", 90.0))
    line_of = {e.id: e.id for e in runs}
    direction_of = {e.id: e.direction for e in runs}
    roles, _signs = _frame_roles_and_signs(runs, runs, line_of, direction_of, (0.0, 0.0, 1.0), [])

    # a 32-gon cap edge 11.25 degrees off no longer snaps to an axis
    assert roles == {"seed": "AXIS_A", "drift": "AXIS_A", "slope": "OBLIQUE", "cross": "AXIS_B"}


def test_a_run_that_leaves_its_axis_by_more_than_drift_is_a_jog_of_its_line() -> None:
    # buildings walls.004/f14: a 1.8 m cross run 1.6 degrees off its axis moves
    # its column by 5 cm, more than the island's drift (1 mm per metre); snapped,
    # it contradicted the whole column. It alone goes OBLIQUE, its line stays.
    from math import cos, radians, sin

    from scaffold_core.layer_5_runtime.skeleton import _frame_roles_and_signs

    def run(run_id, degrees, run_length):
        angle = radians(degrees)
        return SimpleNamespace(id=run_id, length=run_length, direction=(cos(angle), sin(angle), 0.0))

    runs = (run("seed", 0.0, 10.0), run("straight", 0.2, 2.0), run("jog", 1.6, 1.8), run("lone", 3.0, 4.0))
    line_of = {"seed": "line", "straight": "line", "jog": "line", "lone": "lone"}
    direction_of = {e.id: e.direction for e in runs}
    diagnostics: list[str] = []
    roles, _signs = _frame_roles_and_signs(
        runs, runs, line_of, direction_of, (0.0, 0.0, 1.0), diagnostics, drift=0.0087
    )

    assert roles == {"seed": "AXIS_A", "straight": "AXIS_A", "jog": "OBLIQUE", "lone": "OBLIQUE"}
    # a line made only of such runs is simply oblique, with no jog diagnostic
    assert diagnostics == ["island line jogs in the unfolded frame: jog -> OBLIQUE"]


def test_niche_reveals_that_would_overlap_the_wall_stay_cut() -> None:
    # buildings walls.006: a wall with a niche. Unfolded about the opening,
    # the reveals f1 and f2 fall into the same opening and f3 onto the wall
    # (plan Slice U). The gate keeps f2 on the wall and cuts f1 off with f3;
    # every seam that would join the two parts stays cut.
    result = _solve(_load_capture("artist_walls_006.json"))

    assert sorted(island.patch_ids for island in result.assembly.islands) == [
        ("patch:seed:f0", "patch:seed:f2"),
        ("patch:seed:f1", "patch:seed:f3"),
    ]
    refused = [d for d in result.assembly.decisions if d.reason == "would overlap the island"]
    assert sorted(d.chain_id for d in refused) == ["chain:e15", "chain:e16", "chain:e4"]
    assert all(skeleton.frame == "UNFOLDED" for skeleton in result.skeletons)
    assert result.diagnostics == ()


def test_overlap_gate_triangulates_concave_faces_and_ignores_touching_triangles() -> None:
    from scaffold_core.layer_5_runtime.islands import _ear_clip, _triangles_overlap

    # a U-shaped face: its notch (around x=1.5, y=1.5) stays empty
    u_shape = [(0.0, 0.0), (3.0, 0.0), (3.0, 1.0), (1.0, 1.0), (1.0, 2.0), (3.0, 2.0), (3.0, 3.0), (0.0, 3.0)]
    triangles = [tuple(u_shape[i] for i in triangle) for triangle in _ear_clip(u_shape)]
    area = sum(
        abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) / 2.0 for a, b, c in triangles
    )
    assert abs(area - 7.0) < 1e-9
    notch = ((1.4, 1.4), (1.6, 1.4), (1.5, 1.6))
    assert not any(_triangles_overlap(triangle, notch, 1e-9) for triangle in triangles)

    square_a = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0))
    neighbour = ((1.0, 0.0), (2.0, 0.0), (1.0, 1.0))  # shares an edge
    inside = ((0.6, 0.2), (0.9, 0.2), (0.9, 0.5))
    assert not _triangles_overlap(square_a, neighbour, 1e-9)
    assert _triangles_overlap(square_a, inside, 1e-9)


def test_warp_is_measured_at_the_patch_scale_not_by_one_short_edge() -> None:
    # buildings walls/f1352: a 12 x 8 m face with one vertex 1 cm off its plane
    # has a 2 cm edge tilted 63 degrees out of the plane; walls/f1411 is a
    # hexagon folded 90 degrees around a box corner (runs 45 degrees out).
    from scaffold_core.layer_5_runtime.islands import _warped_patch_ids

    up = (0.0, 0.0, 1.0)
    geometry = SimpleNamespace(patch_facts={
        "wall": SimpleNamespace(normal=up, area=100.0),
        "folded": SimpleNamespace(normal=up, area=2.0),
    })

    def run(patch_id, direction, run_length):
        return SimpleNamespace(patch_id=patch_id, direction=direction, length=run_length)

    evidence = (
        run("wall", (1.0, 0.0, 0.0), 12.0),
        run("wall", (0.45, 0.0, 0.89), 0.02),  # 63 degrees out of plane, 1.8 cm climb
        run("folded", (0.71, 0.0, 0.71), 1.2),  # 0.85 m climb on a 1.4 m patch
    )

    assert _warped_patch_ids(geometry, evidence) == {"folded"}


def test_rigid_seams_enter_the_island_tree_first() -> None:
    # Plan Slice P: every seam of the T-vertex wall is one edge long, so the
    # longest-seam-first tree used to reach the planar floor_b only through
    # the warped floor_a, and both fell out of the rigid frame. The straight
    # hinge e_w12 between the wall and floor_b is rigid and enters the tree
    # first; the warped floor_a joins afterwards over one non-rigid seam.
    result = _solve(_t_vertex_wall_with_warped_floor_a())
    decisions = {decision.chain_id: decision for decision in result.assembly.decisions}
    (skeleton,) = result.skeletons

    assert len(result.assembly.islands) == 1
    assert decisions["chain:e_w12"].accepted
    assert [decisions[chain].accepted for chain in ("chain:e_a1", "chain:e_w01")].count(True) == 1
    assert [d for d in skeleton.diagnostics if d.startswith("patch outside the rigid island frame")] == [
        "patch outside the rigid island frame: patch:seed:f_floor_a -> OBLIQUE"
    ]
    floor_b_roles = {role for run_id, role in skeleton.axis_role_by_run.items() if ":f_floor_b:" in run_id}
    assert floor_b_roles == {"AXIS_A", "AXIS_B"}
    assert result.node_frame_mismatches == ()
    assert result.rail_frame_conflicts == ()


def test_rigid_seam_is_a_straight_hinge_or_coplanar_join_of_planar_unwarped_patches() -> None:
    from scaffold_core.layer_5_runtime.islands import SeamRigidity, is_rigid_seam

    rigidity = SeamRigidity(
        planar_patch_ids=frozenset({"a", "b", "c", "warped"}),
        warped_patch_ids=frozenset({"warped"}),
        straight_chain_ids=frozenset({"hinge"}),
        normal_by_patch={
            "a": (0.0, 0.0, 1.0),
            "b": (0.0, 0.0, 0.5),  # patch normals need not be unit length
            "c": (0.0, 1.0, 0.0),
            "warped": (0.0, 0.0, 1.0),
            "curved": (0.0, 0.0, 1.0),
        },
    )

    assert is_rigid_seam(rigidity, "hinge", "a", "c")  # straight hinge at any angle
    assert is_rigid_seam(rigidity, "bent", "a", "b")  # coplanar join over a bent chain
    assert not is_rigid_seam(rigidity, "bent", "a", "c")  # bent hinge, no rotation axis
    assert not is_rigid_seam(rigidity, "hinge", "a", "warped")
    assert not is_rigid_seam(rigidity, "hinge", "curved", "a")  # not planar


def test_tree_edge_priority_takes_rigid_seams_first_then_the_longest_then_by_id() -> None:
    from scaffold_core.layer_5_runtime.islands import SeamRigidity, _tree_edge_priority

    rigidity = SeamRigidity(
        planar_patch_ids=frozenset({"wall", "floor", "lid"}),
        warped_patch_ids=frozenset({"lid"}),
        straight_chain_ids=frozenset({"short", "short_b", "long", "to_lid"}),
        normal_by_patch={"wall": (0.0, -1.0, 0.0), "floor": (0.0, 0.0, 1.0), "lid": (0.0, 0.0, 1.0)},
    )
    topology = SimpleNamespace(chains={
        "short": SimpleNamespace(source_edge_ids=("e1",)),
        "short_b": SimpleNamespace(source_edge_ids=("e5",)),
        "long": SimpleNamespace(source_edge_ids=("e1", "e2", "e3")),
        "to_lid": SimpleNamespace(source_edge_ids=("e1", "e2", "e3", "e4")),
    })
    seams = [
        SimpleNamespace(id="a0", chain_id="to_lid", first_patch_id="wall", second_patch_id="lid"),
        SimpleNamespace(id="a3", chain_id="short_b", first_patch_id="floor", second_patch_id="wall"),
        SimpleNamespace(id="a1", chain_id="short", first_patch_id="wall", second_patch_id="floor"),
        SimpleNamespace(id="a2", chain_id="long", first_patch_id="floor", second_patch_id="wall"),
    ]

    ordered = sorted(seams, key=lambda seam: _tree_edge_priority(seam, rigidity, topology))
    # The longest seam reaches the warped lid, so it comes last; inside the
    # rigid group the longer hinge comes first, and equal lengths go by id.
    assert [seam.id for seam in ordered] == ["a2", "a1", "a3", "a0"]


def test_curved_islands_keep_the_frame_free_derivation() -> None:
    result = _solve(make_cylinder_tube_without_caps_with_two_seams_source())

    assert [skeleton.frame for skeleton in result.skeletons] == ["FRAME_FREE"]


def test_closed_rim_cut_by_self_seam_splits_only_at_the_seam() -> None:
    # The artist_cross_band side band is one patch whose bottom rim is a closed
    # ring cut by a SEAM_SELF at source vertex v4. The Chain's segment order
    # starts at an ordinary ring vertex (v8), so chain ends must be found by
    # the PatchChain end vertices, not by segment index.
    context = run_pass_1_relations(run_pass_0(_load_capture("artist_cross_band.json")))
    result = run_skeleton_solve(context)
    evidence_by_id = {
        evidence.id: evidence for evidence in context.relation_snapshot.patch_chain_directional_evidence
    }
    band = next(
        skeleton
        for island, skeleton in zip(result.assembly.islands, result.skeletons)
        if island.patch_ids == ("patch:seed:f1",)
    )

    nodes_by_source_vertex: dict[str, set[str]] = {}
    for (run_id, role), node in band.node_by_run_end.items():
        if ":f1:0:2:" not in run_id:
            continue
        evidence = evidence_by_id[run_id]
        source_vertex = evidence.start_source_vertex_id if role == "START" else evidence.end_source_vertex_id
        nodes_by_source_vertex.setdefault(str(source_vertex), set()).add(node)
    assert len(nodes_by_source_vertex["v4"]) == 2  # one node per seam side
    assert len(nodes_by_source_vertex["v8"]) == 1  # the ring continues
    # Each rim end sits on its own seam side, so the band's vertical edges
    # stay columns: top and bottom ends share u (a swapped side mirrors the
    # bottom row with zero residual and zero diagnostics).
    band_uv = {vertex.vertex_id: vertex.uv for vertex in result.vertices if vertex.patch_id == "patch:seed:f1"}
    source = context.source_snapshot
    columns = 0
    for face_id in context.topology_snapshot.patches["patch:seed:f1"].source_face_ids:
        for edge_id in source.faces[face_id].edge_ids:
            first, second = source.edges[edge_id].vertex_ids
            delta = [
                end - start
                for start, end in zip(source.vertices[first].position, source.vertices[second].position)
            ]
            vertical = abs(delta[2]) >= 0.9 * sum(value * value for value in delta) ** 0.5
            # Each face corner reads the pin of its own seam side (occurrence).
            first_uv = band_uv.get(result.vertex_by_face_corner[(str(face_id), str(first))])
            second_uv = band_uv.get(result.vertex_by_face_corner[(str(face_id), str(second))])
            if not vertical or first_uv is None or second_uv is None:
                continue
            columns += 1
            assert abs(first_uv[0] - second_uv[0]) < 1e-6, edge_id
    assert columns >= 10


def test_bent_hinge_between_coplanar_patches_joins_the_frame_without_rotation() -> None:
    result = _solve(make_bent_hinge_panels_source(corner_lift=0.0))

    skeleton = result.skeletons[0]
    assert len(result.assembly.islands) == 1
    assert skeleton.frame == "UNFOLDED"
    assert skeleton.diagnostics == ()
    assert "OBLIQUE" not in skeleton.axis_role_by_run.values()
    assert result.node_frame_mismatches == ()


def test_bent_hinge_between_nearly_coplanar_patches_joins_without_rotation() -> None:
    # A 2-degree tilt stays within the planarity tolerance: the quad joins the
    # frame without rotation. Rotating it about the chord of the L would move
    # the shared center vertex away from the panel's copy of it.
    result = _solve(make_bent_hinge_panels_source(corner_lift=0.05))

    skeleton = result.skeletons[0]
    assert skeleton.frame == "UNFOLDED"
    assert not any(
        diagnostic.startswith("patch outside the rigid island frame") for diagnostic in skeleton.diagnostics
    )
    assert result.node_frame_mismatches == ()


def test_bent_hinge_between_tilted_patches_stays_cut_between_two_rigid_islands() -> None:
    # The corner quad tilts 5.7 degrees away from the panel yet stays within
    # the planarity tolerance; an L-shaped hinge has no rotation axis, so the
    # quad must not be rotated about the chord of the L. Since plan Slice U
    # the seam stays cut (the frame cannot cross between two rigid parts), so
    # the quad keeps its own rigid frame instead of hanging outside one.
    result = _solve(make_bent_hinge_panels_source(corner_lift=0.14))

    (decision,) = result.assembly.decisions
    assert not decision.accepted
    assert decision.reason == "frame cannot cross between rigid parts"
    assert sorted(island.patch_ids for island in result.assembly.islands) == [
        ("patch:seed:f_corner",),
        ("patch:seed:f_panel_a",),
    ]
    assert all(skeleton.frame == "UNFOLDED" for skeleton in result.skeletons)
    assert not any(diagnostic.startswith("patch outside") for diagnostic in result.diagnostics)
    assert result.node_frame_mismatches == ()


def test_island_line_whose_members_disagree_degrades_to_oblique() -> None:
    from scaffold_core.layer_5_runtime.skeleton import _frame_roles_and_signs

    runs = (
        SimpleNamespace(id="seed", length=4.0),
        SimpleNamespace(id="rung", length=1.0),
        SimpleNamespace(id="bent_a", length=1.0),
        SimpleNamespace(id="bent_b", length=1.0),
    )
    line_of = {"seed": "line:seed", "rung": "line:rung", "bent_a": "line:bent", "bent_b": "line:bent"}
    direction_of = {
        "seed": (-1.0, 0.0, 0.0),
        "rung": (0.0, 1.0, 0.0),
        "bent_a": (1.0, 0.0, 0.0),
        "bent_b": (0.7071, 0.7071, 0.0),
    }
    diagnostics: list[str] = []

    roles, signs = _frame_roles_and_signs(runs, runs, line_of, direction_of, (0.0, 0.0, 1.0), diagnostics)

    assert roles == {"seed": "AXIS_A", "rung": "AXIS_B", "bent_a": "OBLIQUE", "bent_b": "OBLIQUE"}
    assert diagnostics == ["island line not straight in the unfolded frame: line:bent -> OBLIQUE"]
    assert signs["seed"] == 1.0  # AXIS_A follows the seed run itself
    assert signs["rung"] == -1.0  # AXIS_B = normal x AXIS_A points along -y


def test_island_cut_opens_the_ring_rails_of_a_two_seam_tube() -> None:
    # Layer 3 keeps each rim ring a closed loop rail: it has no start of its
    # own. The island stitches one seam and cuts the other, so Layer 3 cuts
    # the ring there and each rim becomes one ordered rail through both halves.
    context = run_pass_1_relations(run_pass_0(make_cylinder_tube_without_caps_with_two_seams_source()))
    ring_rails = [rail for rail in context.relation_snapshot.scaffold_rails if rail.is_closed_loop]
    ring_members = {frozenset(rail.ordered_member_directional_evidence_ids) for rail in ring_rails}
    result = run_skeleton_solve(context)
    (skeleton,) = result.skeletons
    opened = [
        segment
        for segment in skeleton.rail_segments
        if frozenset(segment.ordered_member_directional_evidence_ids) in ring_members
    ]

    assert len(ring_rails) == 2
    assert not any(rail.is_consumable_by_g5a for rail in ring_rails)
    assert len(opened) == 2
    assert all(segment.is_ordered for segment in opened)
    assert result.rail_frame_conflicts == ()


def test_reflex_corner_island_rails_agree_with_the_unfolded_frame() -> None:
    # Wall A unfolds into the notch of wall B, so A's bottom lies on B's notch
    # bottom pointing back (a fold-back). Layer 3 keeps them on separate lines
    # (plan Slice O1); were they one rail, it would run against the frame.
    source = make_reflex_corner_walls_source()
    context = run_pass_1_relations(run_pass_0(source))
    run_on = {
        str(edge_id): evidence.id
        for evidence in context.relation_snapshot.patch_chain_directional_evidence
        for edge_id in evidence.source_edge_ids
    }
    result = run_skeleton_solve(context)
    (skeleton,) = result.skeletons

    assert skeleton.frame == "UNFOLDED"
    assert result.rail_frame_conflicts == ()
    assert skeleton.line_by_run[run_on["e_a_bottom"]] != skeleton.line_by_run[run_on["e_b_notch_bottom"]]
    assert skeleton.line_by_run[run_on["e_a_top"]] == skeleton.line_by_run[run_on["e_b_top"]]


def test_island_rail_conflicts_name_rails_against_the_frame_and_split_lines() -> None:
    from scaffold_core.layer_3_relations.model import ScaffoldRailSegment
    from scaffold_core.layer_5_runtime.skeleton import _island_rail_conflicts

    def segment(*members, signs=None):
        return ScaffoldRailSegment(
            direction_family_id="family",
            ordered_member_directional_evidence_ids=members,
            ordered_station_member_ids=tuple((member,) for member in members),
            ordered_trace_node_ids=(),
            orientation_sign_by_member=signs or {member: 1 for member in members},
            is_ordered=True,
            diagnostics=(),
        )

    line_of = {"a": "line", "b": "line"}
    roles = {"a": "AXIS_A", "b": "AXIS_A"}
    along = {"a": 1.0, "b": 1.0}
    against = {"a": 1.0, "b": -1.0}

    assert _island_rail_conflicts((segment("a", "b"),), line_of, roles, along, True) == ()
    assert _island_rail_conflicts((segment("a", "b"),), line_of, roles, against, True) == (
        "island rail runs against the unfolded frame: line",
    )
    assert _island_rail_conflicts((segment("a", "b"),), line_of, roles, against, False) == ()
    # A rail sign that flips with the frame sign still runs one way along the axis.
    flipped = segment("a", "b", signs={"a": 1, "b": -1})
    assert _island_rail_conflicts((flipped,), line_of, roles, against, True) == ()
    assert _island_rail_conflicts((segment("a"), segment("b")), line_of, roles, along, True) == (
        "island rail and island line disagree: line",
    )


def test_framed_island_reports_an_island_rail_against_its_frame(monkeypatch) -> None:
    # Wiring of invariant 6: after Slice O1 no real rail runs against the
    # frame, so one sign of every ordered island rail is flipped on its way
    # out of the Layer 3 cut view; a framed island must report it.
    import scaffold_core.layer_5_runtime.skeleton as skeleton_module

    real_cut = skeleton_module.cut_scaffold_rail

    def cut_with_one_sign_flipped(*args):
        segments = []
        for segment in real_cut(*args):
            if segment.is_ordered and len(segment.ordered_member_directional_evidence_ids) > 1:
                first = segment.ordered_member_directional_evidence_ids[0]
                signs = dict(segment.orientation_sign_by_member)
                signs[first] = -signs[first]
                segment = replace(segment, orientation_sign_by_member=signs)
            segments.append(segment)
        return tuple(segments)

    monkeypatch.setattr(skeleton_module, "cut_scaffold_rail", cut_with_one_sign_flipped)
    result = _solve(make_l_corridor_tunnel_seamed_folds_source())

    assert all(skeleton.frame == "UNFOLDED" for skeleton in result.skeletons)
    assert any(
        "island rail runs against the unfolded frame" in conflict for conflict in result.rail_frame_conflicts
    )


def test_frame_free_island_takes_lines_and_in_line_signs_from_its_rails(monkeypatch) -> None:
    # Plan Slice Q: Layer 5 never orders a line itself. One sign of every
    # ordered multi-run island rail is flipped on its way out of the Layer 3
    # cut view; the frame-free island must follow the rail, while a
    # head-to-tail walk of its own would ignore the flip.
    import scaffold_core.layer_5_runtime.skeleton as skeleton_module

    real_cut = skeleton_module.cut_scaffold_rail

    def cut_with_one_sign_flipped(*args):
        segments = []
        for segment in real_cut(*args):
            if segment.is_ordered and len(segment.ordered_member_directional_evidence_ids) > 1:
                first = segment.ordered_member_directional_evidence_ids[0]
                signs = dict(segment.orientation_sign_by_member)
                signs[first] = -signs[first]
                segment = replace(segment, orientation_sign_by_member=signs)
            segments.append(segment)
        return tuple(segments)

    monkeypatch.setattr(skeleton_module, "cut_scaffold_rail", cut_with_one_sign_flipped)
    result = _solve(make_cylinder_tube_without_caps_with_two_seams_source())
    skeleton = result.skeletons[0]

    assert skeleton.frame == "FRAME_FREE"
    multi_run = [s for s in skeleton.rail_segments if len(s.ordered_member_directional_evidence_ids) > 1]
    assert multi_run and all(segment.is_ordered for segment in multi_run)
    for segment in skeleton.rail_segments:
        members = segment.ordered_member_directional_evidence_ids
        assert {skeleton.line_by_run[member] for member in members} == {
            f"{segment.direction_family_id}@{min(members)}"
        }
        # Co-orientation between rails may flip a whole line, never one run.
        assert len({
            skeleton.orientation_by_run[member] * segment.orientation_sign_by_member[member]
            for member in members
        }) == 1


def test_unordered_island_rail_stays_unsigned_in_a_frame_free_island(monkeypatch) -> None:
    import scaffold_core.layer_5_runtime.skeleton as skeleton_module

    baseline = _solve(make_cylinder_tube_without_caps_with_two_seams_source()).skeletons[0]
    real_cut = skeleton_module.cut_scaffold_rail

    def cut_with_multi_run_rails_unordered(*args):
        return tuple(
            replace(segment, is_ordered=False)
            if len(segment.ordered_member_directional_evidence_ids) > 1 else segment
            for segment in real_cut(*args)
        )

    monkeypatch.setattr(skeleton_module, "cut_scaffold_rail", cut_with_multi_run_rails_unordered)
    skeleton = _solve(make_cylinder_tube_without_caps_with_two_seams_source()).skeletons[0]

    unordered = [s for s in skeleton.rail_segments if not s.is_ordered]
    assert unordered
    for segment in unordered:
        members = segment.ordered_member_directional_evidence_ids
        assert f"unordered island rail: {skeleton.line_by_run[members[0]]} -> unsigned" in skeleton.diagnostics
        assert not set(members) & set(skeleton.orientation_by_run)
    equations = skeleton.axis_a.equation_count + skeleton.axis_b.equation_count
    assert equations < baseline.axis_a.equation_count + baseline.axis_b.equation_count


def test_unordered_single_run_rail_stays_unsigned_in_a_frame_free_island(monkeypatch) -> None:
    # Before Slice Q such a run silently took sign +1 and wrote an equation.
    import scaffold_core.layer_5_runtime.skeleton as skeleton_module

    real_cut = skeleton_module.cut_scaffold_rail

    def cut_with_single_run_rails_unordered(*args):
        return tuple(
            replace(segment, is_ordered=False)
            if len(segment.ordered_member_directional_evidence_ids) == 1 else segment
            for segment in real_cut(*args)
        )

    monkeypatch.setattr(skeleton_module, "cut_scaffold_rail", cut_with_single_run_rails_unordered)
    skeleton = _solve(make_cylinder_tube_without_caps_with_two_seams_source()).skeletons[0]

    singles = [s for s in skeleton.rail_segments if len(s.ordered_member_directional_evidence_ids) == 1]
    assert singles
    for segment in singles:
        (member,) = segment.ordered_member_directional_evidence_ids
        assert f"unordered island rail: {skeleton.line_by_run[member]} -> unsigned" in skeleton.diagnostics
        assert member not in skeleton.orientation_by_run


def _frame_free_roles_by_edge(source) -> dict[tuple[str, str], str]:
    """Axis role of every run of a one-island frame-free solve, by its source vertices."""

    context = run_pass_1_relations(run_pass_0(source))
    evidence = {e.id: e for e in context.relation_snapshot.patch_chain_directional_evidence}
    (skeleton,) = run_skeleton_solve(context).skeletons
    assert skeleton.frame == "FRAME_FREE"
    assert not [d for d in skeleton.diagnostics if "bipartition" in d]
    return {
        (str(evidence[run_id].start_source_vertex_id), str(evidence[run_id].end_source_vertex_id)): role
        for run_id, role in skeleton.axis_role_by_run.items()
    }


def test_frame_free_axes_ignore_3d_perpendicular_runs_that_are_no_right_corner() -> None:
    # Folded sheet: b-p (floor) and p-w (wall) are perpendicular in 3D but
    # meet at 135 degrees on the patch; they must not be linked. a-b and b-p
    # meet at a true right corner of the patch and are linked.
    roles = _frame_free_roles_by_edge(make_folded_sheet_source())

    assert roles[("w", "q")] == roles[("q", "a")] == "AXIS_A"  # one straight surface line, the seed
    assert roles[("a", "b")] == "AXIS_B"
    assert roles[("b", "p")] == "AXIS_A"
    assert roles[("p", "w")] == "OBLIQUE"


def test_frame_free_reflex_right_corner_links_like_a_convex_one() -> None:
    # The notch edge e-f is tied to the island only by the 270-degree corner at e.
    roles = _frame_free_roles_by_edge(make_folded_l_sheet_source())

    assert roles[("a", "c")] == roles[("c", "c_up")] == "AXIS_A"
    assert roles[("d_up", "d")] == roles[("d", "e")] == "AXIS_A"
    assert roles[("c_up", "d_up")] == roles[("g", "a")] == "AXIS_B"
    assert roles[("e", "f")] == "AXIS_B"
    assert roles[("f", "g")] == "OBLIQUE"


def _corner(first: str, second: str, kind=RunCornerKind.RIGHT):
    return SimpleNamespace(kind=kind, first_directional_evidence_id=first, second_directional_evidence_id=second)


def test_oblique_line_from_a_bipartition_conflict_passes_no_axis_on() -> None:
    from scaffold_core.layer_5_runtime.frame_free import bipartition_families

    lengths = {"x": 5.0, "y": 2.0, "z": 2.0, "w": 1.0, "v": 1.0}
    runs = tuple(SimpleNamespace(id=f"run_{line}", length=length) for line, length in lengths.items())
    line_of = {f"run_{line}": line for line in lengths}
    # x-y, x-z, y-z is an odd cycle: y becomes OBLIQUE. v hangs on y alone.
    corners = (
        _corner("run_x", "run_y"),
        _corner("run_x", "run_z"),
        _corner("run_y", "run_z"),
        _corner("run_z", "run_w"),
        _corner("run_y", "run_v"),
        _corner("run_x", "run_w", RunCornerKind.STRAIGHT),  # never an edge
    )
    diagnostics: list[str] = []

    axis = bipartition_families(runs, line_of, corners, diagnostics)

    assert axis == {"x": "AXIS_A", "y": "OBLIQUE", "z": "AXIS_B", "w": "AXIS_A"}
    assert diagnostics == ["axis bipartition conflict: y -> OBLIQUE"]


def test_bipartition_links_only_runs_of_this_island() -> None:
    from scaffold_core.layer_5_runtime.frame_free import bipartition_families

    runs = (SimpleNamespace(id="run_x", length=2.0), SimpleNamespace(id="run_y", length=1.0))
    # line_of may name an outside run's line, but its corner is not this island's.
    line_of = {"run_x": "x", "run_y": "y", "outside": "y"}

    axis = bipartition_families(runs, line_of, (_corner("run_x", "outside"),), [])

    assert axis == {"x": "AXIS_A"}


def _corner_law_by_island(context, result) -> dict[str, Counter]:
    """Per island: RIGHT corners that turn by the corner law ("with") or not ("against").

    The run whose endpoint role is END arrives at the corner, the START run
    leaves it; in an unmirrored layout a convex corner turns left and a reflex
    corner right. A bridged right corner is checked the same way between its
    arriving and leaving runs ("bridged" counts those checked). Only corners
    with all four run-end coordinates solved and a clear turn (sine of at
    least 0.5) are counted.
    """

    skeleton_of_run = {run_id: s for s in result.skeletons for run_id in s.axis_role_by_run}
    counts: dict[str, Counter] = {}
    turns = []  # (arriving, leaving, angle, bridged)
    for corner in context.relation_snapshot.run_corner_relations:
        if corner.kind is not RunCornerKind.RIGHT:
            continue
        run_by_role = {
            corner.first_endpoint_role: corner.first_directional_evidence_id,
            corner.second_endpoint_role: corner.second_directional_evidence_id,
        }
        turns.append((
            run_by_role.get(PatchChainEndpointRole.END), run_by_role.get(PatchChainEndpointRole.START),
            corner.interior_angle_sum, False,
        ))
    turns.extend(
        (c.arriving_directional_evidence_id, c.leaving_directional_evidence_id, c.interior_angle_sum, True)
        for c in context.relation_snapshot.run_bridged_corner_relations
    )
    for arriving, leaving, angle, bridged in turns:
        skeleton = skeleton_of_run.get(arriving)
        if leaving is None or skeleton is None or skeleton_of_run.get(leaving) is not skeleton:
            continue
        uv = []
        for run_id, role in ((arriving, "START"), (arriving, "END"), (leaving, "START"), (leaving, "END")):
            node = skeleton.node_by_run_end[(run_id, role)]
            uv.append((skeleton.axis_a.coordinate_by_node.get(node), skeleton.axis_b.coordinate_by_node.get(node)))
        if any(None in point for point in uv):
            continue
        da = (uv[1][0] - uv[0][0], uv[1][1] - uv[0][1])
        dl = (uv[3][0] - uv[2][0], uv[3][1] - uv[2][1])
        turn = da[0] * dl[1] - da[1] * dl[0]
        if turn == 0.0 or abs(turn) < 0.5 * (da[0] ** 2 + da[1] ** 2) ** 0.5 * (dl[0] ** 2 + dl[1] ** 2) ** 0.5:
            continue
        law = (turn > 0.0) == (angle < pi)
        counts.setdefault(skeleton.island_id, Counter())["with" if law else "against"] += 1
        counts[skeleton.island_id]["bridged"] += bridged
    return counts


CORNER_LAW_SOURCES = {
    **{path.name: (lambda name=path.name: _load_capture(name)) for path in sorted(DATA.glob("*.json"))},
    "bent_hinge": make_bent_hinge_panels_source,
    "capped_decagon_prism": make_capped_decagon_prism_odd_strips_source,
    "capped_square_prism": make_capped_square_prism_all_seams_source,
    "tube_one_seam": make_cylinder_tube_without_caps_with_one_seam_source,
    "tube_two_seams": make_cylinder_tube_without_caps_with_two_seams_source,
    "segmented_tube": make_segmented_cylinder_tube_without_caps_with_one_seam_source,
    "detached_walls": make_detached_parallel_walls_source,
    "extruded_cross": make_extruded_cross_source,
    "l_corridor_tunnel": make_l_corridor_tunnel_seamed_folds_source,
    "reflex_corner": make_reflex_corner_walls_source,
    "folded_l_sheet": make_folded_l_sheet_source,
    "folded_sheet": make_folded_sheet_source,
    "notched_sheet": lambda: make_notched_sheet_source(folded=False),
    "notched_sheet_folded": lambda: make_notched_sheet_source(folded=True),
    "cut_corner_folded": lambda: make_cut_corner_rectangle_source(30.0, folded=True),
    "cut_annulus": make_cut_annulus_source,
    "t_vertex_wall": make_t_vertex_wall_source,
    "tube_with_cap": make_tube_with_cap_source,
}


@pytest.mark.parametrize("name", sorted(CORNER_LAW_SOURCES))
def test_right_corners_turn_by_the_corner_law_in_every_island(name) -> None:
    context = run_pass_1_relations(run_pass_0(CORNER_LAW_SOURCES[name]()))
    result = run_skeleton_solve(context)

    counts = _corner_law_by_island(context, result)

    assert {island: c["against"] for island, c in counts.items() if c["against"]} == {}


def test_corner_law_is_checked_in_frame_free_and_framed_islands() -> None:
    checked = Counter()
    for name in sorted(CORNER_LAW_SOURCES):
        context = run_pass_1_relations(run_pass_0(CORNER_LAW_SOURCES[name]()))
        result = run_skeleton_solve(context)
        frame_of = {s.island_id: s.frame for s in result.skeletons}
        for island, c in _corner_law_by_island(context, result).items():
            checked[frame_of[island]] += c["with"] + c["against"]
    assert checked["FRAME_FREE"] > 40
    assert checked["UNFOLDED"] > 500


def test_arch_front_island_is_not_mirrored() -> None:
    # The 3D co-orientation left the arch front's lines unlinked and the island
    # came out mirrored: every right corner turned the wrong way.
    context = run_pass_1_relations(run_pass_0(_load_capture("artist_arch_bevel.json")))
    result = run_skeleton_solve(context)

    island = _corner_law_by_island(context, result)["island:0"]

    assert _skeleton_by_island(result)["island:0"].frame == "FRAME_FREE"
    assert island["with"] >= 4
    assert island["against"] == 0


def _turn_corner(arriving: str, leaving: str, convex: bool):
    return SimpleNamespace(
        kind=RunCornerKind.RIGHT,
        first_directional_evidence_id=arriving,
        first_endpoint_role=PatchChainEndpointRole.END,
        second_directional_evidence_id=leaving,
        second_endpoint_role=PatchChainEndpointRole.START,
        interior_angle_sum=0.5 * pi if convex else 1.5 * pi,
    )


def test_corner_handedness_orients_lines_and_unsigns_a_contradicted_line() -> None:
    from scaffold_core.layer_5_runtime.frame_free import orient_lines_by_corners

    lengths = {"x1": 3.0, "x2": 2.0, "y1": 1.0, "y2": 1.0, "z1": 1.0, "w1": 1.0}
    runs = tuple(SimpleNamespace(id=run_id, length=length) for run_id, length in lengths.items())
    line_of = {run_id: run_id[0] for run_id in lengths}
    axis_by_line = {"x": "AXIS_A", "y": "AXIS_B", "z": "AXIS_B", "w": "AXIS_B"}
    signs = {run_id: 1.0 for run_id in lengths}
    signs["z1"] = -1.0
    corners = (
        # Arriving on AXIS_A at a convex corner: the two signs agree. Line x
        # (longest) keeps its signs; z flips to agree with it.
        _turn_corner("x1", "z1", convex=True),
        # y meets x at a convex and at a reflex corner with the same signs:
        # it cannot satisfy both.
        _turn_corner("x1", "y1", convex=True),
        _turn_corner("x2", "y2", convex=False),
        # Two START ends are no arrive/leave pair; w keeps its rail sign and
        # is reported as not tied to the longest line.
        SimpleNamespace(
            kind=RunCornerKind.RIGHT,
            first_directional_evidence_id="x1",
            first_endpoint_role=PatchChainEndpointRole.START,
            second_directional_evidence_id="w1",
            second_endpoint_role=PatchChainEndpointRole.START,
            interior_angle_sum=0.5 * pi,
        ),
    )
    diagnostics: list[str] = []

    orient_lines_by_corners(runs, line_of, axis_by_line, signs, corners, diagnostics)

    assert diagnostics == [
        "corner handedness conflict on island line: y -> unsigned",
        "island line not tied to the longest line by right corners: w",
    ]
    assert "y1" not in signs and "y2" not in signs
    assert signs["x1"] == signs["x2"] == 1.0  # the seed is not blamed for y's corners
    assert signs["z1"] == 1.0
    assert signs["w1"] == 1.0


def _skeleton_by_island(result):
    return {skeleton.island_id: skeleton for skeleton in result.skeletons}


def _run_name(context):
    evidence = {e.id: e for e in context.relation_snapshot.patch_chain_directional_evidence}
    return lambda run_id: f"{evidence[run_id].start_source_vertex_id}-{evidence[run_id].end_source_vertex_id}"


def _without_bridged_corners(context):
    return replace(context, relation_snapshot=replace(context.relation_snapshot, run_bridged_corner_relations=()))


def test_frame_free_bridged_corners_lay_a_chamfered_outline_exactly() -> None:
    # Folded notched sheet: one non-planar patch, no rigid frame. Its notch
    # corners and its top-left corner are right corners turned over chamfers.
    context = run_pass_1_relations(run_pass_0(make_notched_sheet_source(folded=True)))
    result = run_skeleton_solve(context)
    (skeleton,) = result.skeletons
    name = _run_name(context)
    roles = {name(run_id): role for run_id, role in skeleton.axis_role_by_run.items()}
    bridges = {"j1-j2", "j3-j4", "t1-t2"}

    assert skeleton.frame == "FRAME_FREE"
    assert skeleton.diagnostics == ()
    assert {run for run, role in roles.items() if role == "OBLIQUE"} == bridges
    assert {name(run_id) for run_id in skeleton.bridge_vector_by_run} == bridges
    assert roles["j2-j3"] == roles["a0-a1"] == "AXIS_A"  # the notch top, across two chamfers
    # The notch top is the bridge of the chamfer -> top -> chamfer record, but
    # it has an axis role: it is laid by its length equation, not by a vector.
    (top_bridged,) = [
        c for c in context.relation_snapshot.run_bridged_corner_relations
        if name(c.bridge_directional_evidence_id) == "j2-j3"
    ]
    assert top_bridged.bridge_directional_evidence_id not in skeleton.bridge_vector_by_run
    assert max(skeleton.axis_a.residual_max, skeleton.axis_b.residual_max) < 1e-9
    pins = {vertex.source_vertex_id: vertex.uv for vertex in result.vertices if vertex.pinned}
    run_ends = {
        str(vertex)
        for e in context.relation_snapshot.patch_chain_directional_evidence
        for vertex in (e.start_source_vertex_id, e.end_source_vertex_id)
    }
    assert run_ends <= set(pins)
    # The exact unfolded outline, moved rigidly: a rotation, never a mirror.
    unfolded = {
        str(vertex_id): vertex.position[:2]
        for vertex_id, vertex in context.source_snapshot.vertices.items()
        if vertex.position[2] == 0.0
    }
    unfolded.update(NOTCHED_SHEET_UNFOLDED)
    origin, axis = "a0", "a3"
    angle = atan2(pins[axis][1] - pins[origin][1], pins[axis][0] - pins[origin][0]) - atan2(
        unfolded[axis][1] - unfolded[origin][1], unfolded[axis][0] - unfolded[origin][0]
    )
    for vertex, uv in pins.items():
        x, y = (unfolded[vertex][k] - unfolded[origin][k] for k in range(2))
        moved = (pins[origin][0] + cos(angle) * x - sin(angle) * y, pins[origin][1] + sin(angle) * x + cos(angle) * y)
        assert dist(moved, uv) < 1e-9, vertex
    law = _corner_law_by_island(context, result)[skeleton.island_id]
    assert law["against"] == 0
    assert law["bridged"] == 4  # the three chamfers and the notch top between its chamfers


def test_without_bridged_corners_the_notch_and_its_side_are_unreached_lines() -> None:
    context = _without_bridged_corners(run_pass_1_relations(run_pass_0(make_notched_sheet_source(folded=True))))
    (skeleton,) = run_skeleton_solve(context).skeletons
    name = _run_name(context)
    unreached = {
        name(run_id)
        for run_id, line in skeleton.line_by_run.items()
        if f"island line not reached by right corners: {line} -> OBLIQUE" in skeleton.diagnostics
    }

    assert unreached == {"j1-j2", "j2-j3", "j3-j4", "t1-t2", "t2-a0", "a0-a1", "a1-j1"}
    assert skeleton.bridge_vector_by_run == {}


def test_frame_free_unreached_line_is_reported_once() -> None:
    # Folded sheet: p-w meets its neighbours at 135 and 45 degrees: no right corner.
    context = run_pass_1_relations(run_pass_0(make_folded_sheet_source()))
    (skeleton,) = run_skeleton_solve(context).skeletons
    name = _run_name(context)
    (run_id,) = [run_id for run_id in skeleton.axis_role_by_run if name(run_id) == "p-w"]

    assert skeleton.axis_role_by_run[run_id] == "OBLIQUE"
    assert skeleton.diagnostics == (
        f"island line not reached by right corners: {skeleton.line_by_run[run_id]} -> OBLIQUE",
    )


def _bridged_corner(arriving, bridge, leaving, first_degrees, second_degrees):
    first, second = first_degrees * pi / 180.0, second_degrees * pi / 180.0
    return SimpleNamespace(
        id=f"bridged:{arriving}:{bridge}:{leaving}",
        arriving_directional_evidence_id=arriving,
        bridge_directional_evidence_id=bridge,
        leaving_directional_evidence_id=leaving,
        arriving_interior_angle_sum=first,
        leaving_interior_angle_sum=second,
        interior_angle_sum=first + second - pi,
    )


def test_bridge_vectors_follow_the_corner_turns_and_report_disagreements() -> None:
    from scaffold_core.layer_5_runtime.frame_free import bridge_vectors

    runs = tuple(SimpleNamespace(id=run_id, length=2.0) for run_id in ("a", "b", "c", "d", "e", "f", "g"))
    roles = {"a": "AXIS_A", "b": "AXIS_B", "c": "OBLIQUE", "d": "AXIS_A", "e": "AXIS_B", "f": "OBLIQUE", "g": "AXIS_B"}
    signs = {"a": 1.0, "b": 1.0, "d": 1.0, "e": 1.0, "g": -1.0}
    diagnostics: list[str] = []

    vectors = bridge_vectors(runs, roles, signs, (
        # c bridges a convex right corner split 45 + 45 (a +A, b +B): it points up-right.
        _bridged_corner("a", "c", "b", 135.0, 135.0),
        # f is laid by two corners that disagree: 45 + 45 and 30 + 60.
        _bridged_corner("a", "f", "b", 135.0, 135.0),
        _bridged_corner("d", "f", "e", 150.0, 120.0),
        # A convex corner from +A must leave along +B; g runs along -B.
        _bridged_corner("d", "c", "g", 135.0, 135.0),
    ), diagnostics)

    assert set(vectors) == {"c"}
    assert vectors["c"] == pytest.approx((2.0 ** 0.5, 2.0 ** 0.5))
    assert diagnostics == [
        "bridged corner against its line orientation: bridged:d:c:g",
        "bridge run laid two ways by bridged corners: f",
    ]


def test_bridge_vector_splits_the_tolerance_error_evenly_between_the_two_turns() -> None:
    from scaffold_core.layer_5_runtime.frame_free import bridge_vectors

    runs = tuple(SimpleNamespace(id=run_id, length=1.0) for run_id in ("a", "c", "b"))
    # 136 + 137 degrees: turns 44 and 43, three degrees short of the right angle.
    corner = _bridged_corner("a", "c", "b", 136.0, 137.0)
    vectors = bridge_vectors(
        runs, {"a": "AXIS_A", "c": "OBLIQUE", "b": "AXIS_B"}, {"a": 1.0, "b": 1.0}, (corner,), []
    )

    turn = (44.0 + 1.5) * pi / 180.0
    assert vectors["c"] == pytest.approx((cos(turn), sin(turn)))


@pytest.mark.parametrize("make_source", [
    lambda: make_notched_sheet_source(folded=False),
    lambda: make_cut_corner_rectangle_source(30.0),
])
def test_rigid_frame_island_solves_the_same_with_or_without_bridged_corners(make_source) -> None:
    context = run_pass_1_relations(run_pass_0(make_source()))
    assert context.relation_snapshot.run_bridged_corner_relations

    with_bridged = run_skeleton_solve(context)
    without = run_skeleton_solve(_without_bridged_corners(context))

    assert [s.frame for s in with_bridged.skeletons] == ["UNFOLDED"]
    assert with_bridged.skeletons == without.skeletons
    assert with_bridged.vertices == without.vertices


def test_arch_rim_arcs_share_one_axis_and_end_chains_the_other() -> None:
    # Before right corners, raw 3D perpendicularity across the rim/cap fold
    # made odd cycles and a whole rim arc went OBLIQUE.
    context = run_pass_1_relations(run_pass_0(_load_capture("artist_arch_bevel.json")))
    evidence = {e.id: e for e in context.relation_snapshot.patch_chain_directional_evidence}
    result = run_skeleton_solve(context)
    skeletons = _skeleton_by_island(result)

    for island_id, rim_patch in (("island:0", "patch:seed:f0"), ("island:1", "patch:seed:f85")):
        skeleton = skeletons[island_id]
        assert skeleton.frame == "FRAME_FREE"
        assert not [d for d in skeleton.diagnostics if "bipartition" in d]
        members_by_line: dict[str, int] = Counter(skeleton.line_by_run.values())
        arc_roles, end_roles = set(), set()
        arc_lines = set()
        for run_id, role in skeleton.axis_role_by_run.items():
            if str(evidence[run_id].patch_id) != rim_patch:
                continue
            line = skeleton.line_by_run[run_id]
            if members_by_line[line] > 1:
                arc_roles.add(role)
                arc_lines.add(line)
            else:
                end_roles.add(role)
        assert len(arc_lines) == 2  # the two rim arcs
        assert len(arc_roles) == len(end_roles) == 1
        assert arc_roles | end_roles == {"AXIS_A", "AXIS_B"}
    pins = Counter(vertex.island_id for vertex in result.vertices)
    # 37/27/3 run-end pins plus 3/3/4 station pins on multi-segment axis runs (plan Slice Z)
    assert (pins["island:0"], pins["island:1"], pins["island:2"]) == (40, 30, 7)


@pytest.mark.parametrize(
    ("capture", "island_id", "pin_count"),
    [
        ("artist_cyl32.json", "island:0", 68),
        ("artist_cyl_multiseam.json", "island:0", 76),
        ("artist_cross_band.json", "island:1", 26),  # 22 run-end pins + 4 stations (plan Slice Z)
    ],
)
def test_frame_free_band_islands_keep_every_run_on_an_axis(capture, island_id, pin_count) -> None:
    result = _solve(_load_capture(capture))
    skeleton = _skeleton_by_island(result)[island_id]

    assert skeleton.frame == "FRAME_FREE"
    assert set(skeleton.axis_role_by_run.values()) == {"AXIS_A", "AXIS_B"}
    assert not [d for d in skeleton.diagnostics if "bipartition" in d]
    assert sum(1 for vertex in result.vertices if vertex.island_id == island_id) == pin_count


def test_node_frame_mismatch_names_a_node_whose_occurrences_sit_apart() -> None:
    from scaffold_core.layer_5_runtime.skeleton import (
        _IslandFrame,
        _identity,
        _node_frame_mismatches,
    )

    runs = (
        SimpleNamespace(id="left", patch_id="p1", start_source_vertex_id="a", end_source_vertex_id="v"),
        SimpleNamespace(id="right", patch_id="p2", start_source_vertex_id="v", end_source_vertex_id="b"),
    )
    node_by_run_end = {
        ("left", "START"): "node:a",
        ("left", "END"): "node:v",
        ("right", "START"): "node:v",
        ("right", "END"): "node:b",
    }
    positions = {"a": (0.0, 0.0, 0.0), "v": (1.0, 0.0, 0.0), "b": (2.0, 0.0, 0.0)}

    def frame(shift: float) -> _IslandFrame:
        return _IslandFrame(
            rotation_by_patch={"p1": _identity(), "p2": _identity()},
            offset_by_patch={"p1": (0.0, 0.0, 0.0), "p2": (shift, 0.0, 0.0)},
            normal=(0.0, 0.0, 1.0),
        )

    assert _node_frame_mismatches(frame(0.0), runs, node_by_run_end, positions) == ()
    assert _node_frame_mismatches(frame(0.5), runs, node_by_run_end, positions) == ("node:v",)


def test_self_seam_sides_keep_their_own_pins() -> None:
    # One patch cut by one seam: each seam vertex has one topology occurrence
    # per seam side (DD-37), and the solve places the two sides at the two ends
    # of the unrolled band. Pins keyed by (source vertex, patch) kept only one
    # of them (plan Slice N, deferred unwrap-level finding).
    result = _solve(make_cylinder_tube_without_caps_with_one_seam_source())

    band_length = 4.0 * 2.0 ** 0.5
    for source_vertex in ("v0", "v4"):
        pins = [vertex for vertex in result.vertices if vertex.source_vertex_id == source_vertex]
        assert len(pins) == 2, source_vertex
        assert pins[0].vertex_id != pins[1].vertex_id
        assert abs(abs(pins[0].uv[0] - pins[1].uv[0]) - band_length) < 1e-6
    # f0 and f3 lie on the two sides of the seam edge v0-v4: each side's pins
    # form one straight column of the band.
    pin_by_vertex = {(vertex.vertex_id, vertex.patch_id): vertex for vertex in result.vertices}
    for face_id in ("f0", "f3"):
        patch_id = result.patch_by_source_face[face_id]
        top, bottom = (
            pin_by_vertex[(result.vertex_by_face_corner[(face_id, source_vertex)], patch_id)]
            for source_vertex in ("v0", "v4")
        )
        assert abs(top.uv[0] - bottom.uv[0]) < 1e-6, face_id


@pytest.mark.parametrize("mode", ("OBJECT", "EDIT"))
def test_uv_write_puts_each_seam_side_loop_on_its_own_side(monkeypatch, mode: str) -> None:
    # A loop never takes another occurrence's UV: the band unrolls exactly, so
    # every face keeps its 3D edge lengths in UV. A seam loop at the other
    # side's place would stretch its face across the whole band.
    source = make_cylinder_tube_without_caps_with_one_seam_source()
    written = _write_with_fake_bmesh(monkeypatch, source, _solve(source), mode)

    for face_id, face in source.faces.items():
        corners = face.vertex_ids
        for index, first in enumerate(corners):
            second = corners[(index + 1) % len(corners)]
            first_uv, second_uv = written[(str(face_id), str(first))], written[(str(face_id), str(second))]
            assert first_uv.pin_uv and second_uv.pin_uv
            uv_length = sum((a - b) ** 2 for a, b in zip(first_uv.uv, second_uv.uv)) ** 0.5
            mesh_length = sum(
                (a - b) ** 2 for a, b in zip(source.vertices[first].position, source.vertices[second].position)
            ) ** 0.5
            assert abs(uv_length - mesh_length) < 1e-6, (face_id, first, second)
    assert written[("f0", "v0")].uv != written[("f3", "v0")].uv


@pytest.mark.parametrize("mode", ("OBJECT", "EDIT"))
def test_uv_write_never_borrows_a_pin_from_another_patch(monkeypatch, mode: str) -> None:
    # The 32-gon caps of artist_cyl32 are their own islands. Their loops used
    # to take the band's rim pins (another island), which laid each cap onto
    # the band's rim row. A loop without a pin of its own stays unpinned and
    # untouched for U > Unwrap. Since plan Slice Z each cap pins the ends of
    # its four axis runs (the cross coordinate comes from the cap's frame), so
    # 64 -> 48 rim corners are left without a pin of their own.
    source = _load_capture("artist_cyl32.json")
    result = _solve(source)
    own_pins = {(vertex.source_vertex_id, vertex.patch_id) for vertex in result.vertices}
    written = _write_with_fake_bmesh(monkeypatch, source, result, mode)

    without_own_pin = [
        (face_id, vertex_id)
        for face_id, vertex_id in written
        if (vertex_id, result.patch_by_source_face[face_id]) not in own_pins
    ]
    assert len(without_own_pin) == 48  # the cap rim corners off the cap axis runs
    band = max(result.assembly.islands, key=lambda island: len(island.patch_ids))
    assert Counter(v.island_id for v in result.vertices if v.island_id != band.id) == {
        island.id: 8 for island in result.assembly.islands if island.id != band.id
    }
    for corner in without_own_pin:
        assert written[corner].pin_uv is False and written[corner].uv is None, corner


@pytest.mark.parametrize("mode", ("OBJECT", "EDIT"))
def test_uv_write_never_borrows_a_pin_inside_the_island(monkeypatch, mode: str) -> None:
    # Hand-built solve output: patches P and Q of one island share source
    # vertex v1 (f0 in P, f1 in Q), and only P has a pin there, as when Q's own
    # solve node at v1 lacks an axis coordinate. The solve never glued Q's
    # corner to P's node, so Q's loop stays unpinned (the Tier 3 case of plan
    # Task Card M2).
    pin = PinnedVertex(
        source_vertex_id="v1", island_id="island:0", patch_id="P", uv=(1.0, 2.0), pinned=True, vertex_id="vertex:v1"
    )
    result = SolveResult(
        assembly=IslandAssembly(islands=(), decisions=(), island_by_patch_id={"P": "island:0", "Q": "island:0"}),
        skeletons=(),
        vertices=(pin,),
        residual_max=0.0,
        axis_parallel_violations=(),
        seam_length_mismatches=(),
        diagnostics=(),
        patch_by_source_face={"f0": "P", "f1": "Q"},
        vertex_by_face_corner={("f0", "v1"): "vertex:v1", ("f1", "v1"): "vertex:v1"},
    )
    tube = make_cylinder_tube_without_caps_with_one_seam_source()  # faces f0 and f1 share v1
    written = _write_with_fake_bmesh(monkeypatch, tube, result, mode)

    assert written[("f0", "v1")].pin_uv is True and written[("f0", "v1")].uv == (1.0, 2.0)
    assert written[("f1", "v1")].pin_uv is False and written[("f1", "v1")].uv is None


def test_pinch_vertex_keeps_its_pin_on_both_boundary_passes(monkeypatch) -> None:
    # Without seams the patch touches itself at v5 (f1 and f3 meet only
    # there), so v5 has one occurrence per boundary pass (DD-37). The run's own
    # edges tell the passes apart: both loops keep the pin of their one solve
    # node, and no seam-cut diagnostic fires.
    source = _pinched_grid_source()
    result = _solve(source)
    written = _write_with_fake_bmesh(monkeypatch, source, result, "OBJECT")

    assert not any("seam-cut" in diagnostic for diagnostic in result.diagnostics)
    assert result.vertex_by_face_corner[("f1", "v5")] != result.vertex_by_face_corner[("f3", "v5")]
    assert written[("f1", "v5")].pin_uv and written[("f3", "v5")].pin_uv
    assert written[("f1", "v5")].uv == written[("f3", "v5")].uv


def test_seam_cut_mid_chain_vertex_stays_unpinned_with_diagnostics() -> None:
    # A kinked self-seam splits into two runs at a mid-chain vertex that has
    # one occurrence per seam side, and the two sides solve to different UVs.
    # The run's own seam edge has both sides' faces, so the run end does not
    # name its side: both sides stay unpinned with a diagnostic instead of
    # sharing one pin.
    source = make_segmented_cylinder_tube_without_caps_with_one_seam_source()
    kink = SourceVertexId("v_a_m")
    vertices = dict(source.vertices)
    vertices[kink] = MeshVertexRef(kink, (1.5, 0.0, 1.0))
    result = _solve(replace(source, vertices=vertices))

    unresolved = [
        diagnostic
        for diagnostic in result.diagnostics
        if diagnostic.startswith("run end on a seam-cut mid-chain vertex touches both seam sides")
    ]
    assert len(unresolved) == 4  # two run ends meet at the kink on each seam side
    assert not any(vertex.source_vertex_id == "v_a_m" for vertex in result.vertices)


# ------------------------------------------------ plan Slice Z: gauge, stations


def _grid_wall_source(xs, ys, skip=(), seams=()) -> SourceMeshSnapshot:
    """Planar quad grid at z = 0; cells in `skip` are holes, `seams` are edge ids.

    Blender-style ids (v<i + len(xs) j>, f<i + (len(xs) - 1) j>) so the fake
    BMesh can write it.
    """

    vertices, edges, faces = {}, {}, {}
    n = len(xs)
    for j in range(len(ys) - 1):
        for i in range(n - 1):
            if (i, j) in skip:
                continue
            corners = ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))
            ids = tuple(SourceVertexId(f"v{a + n * b}") for a, b in corners)
            for vertex_id, (a, b) in zip(ids, corners):
                vertices[vertex_id] = MeshVertexRef(vertex_id, (float(xs[a]), float(ys[b]), 0.0))
            edge_ids = []
            for pair in (tuple(sorted(pair)) for pair in zip(ids, ids[1:] + ids[:1])):
                edge_id = SourceEdgeId(f"e_{pair[0]}_{pair[1]}")
                edges.setdefault(edge_id, MeshEdgeRef(edge_id, pair))
                edge_ids.append(edge_id)
            face_id = SourceFaceId(f"f{i + (n - 1) * j}")
            faces[face_id] = MeshFaceRef(face_id, ids, tuple(edge_ids))
    return SourceMeshSnapshot(
        id=SourceMeshId("grid_wall"),
        vertices=vertices,
        edges=edges,
        faces=faces,
        selected_face_ids=tuple(faces),
        marks=tuple(SourceMark(kind=SourceMarkKind.SEAM, target_id=SourceEdgeId(edge)) for edge in seams),
    )


def _window_wall_source() -> SourceMeshSnapshot:
    # A 10 x 4 wall with a 2 x 2 window; the window loop touches nothing else.
    return _grid_wall_source((0.0, 3.0, 5.0, 10.0), (0.0, 1.0, 3.0, 4.0), skip={(1, 1)})


def _distance(p, q) -> float:
    return sum((a - b) ** 2 for a, b in zip(p, q)) ** 0.5


def test_window_loop_of_a_framed_wall_is_pinned_at_its_true_offsets() -> None:
    # No chain joins the window loop to the outer loop, so its nodes form
    # their own equation group on each axis. One gauge for the island left
    # them pinned at arbitrary coordinates; every group is now anchored to the
    # rigid frame, so the window sits at its true offsets (plan Slice Z).
    source = _window_wall_source()
    result = _solve(source)
    uv = {vertex.source_vertex_id: vertex.uv for vertex in result.vertices}
    position = {str(vertex_id): vertex.position for vertex_id, vertex in source.vertices.items()}
    window, outer = ("v5", "v6", "v9", "v10"), ("v0", "v3", "v12", "v15")

    assert result.skeletons[0].frame == "UNFOLDED"
    assert result.diagnostics == ()
    for w in window:
        for o in outer:
            assert _distance(uv[w], uv[o]) == pytest.approx(_distance(position[w], position[o]), abs=1e-9), (w, o)
    # Paired: the outer loop keeps its own exact rectangle.
    for o in outer:
        for p in outer:
            assert _distance(uv[o], uv[p]) == pytest.approx(_distance(position[o], position[p]), abs=1e-9)


def _two_group_axis():
    """AXIS_A runs in two groups (one drifts by 3 mm) plus a node pair with no AXIS_A equation."""

    def run(run_id, run_length):
        return SimpleNamespace(id=run_id, length=run_length, direction=(1.0, 0.0, 0.0))

    runs = (
        run("g1", 10.0),
        run("h1", 2.0), run("h2", 3.0), run("h3", 5.003),
        SimpleNamespace(id="x", length=0.2, direction=(0.0, 1.0, 0.0)),
    )
    ends = {"g1": ("n0", "n1"), "h1": ("n2", "n3"), "h2": ("n3", "n4"), "h3": ("n2", "n4"), "x": ("n5", "n6")}
    node_by_run_end = {}
    for run_id, (start, end) in ends.items():
        node_by_run_end[(run_id, "START")] = start
        node_by_run_end[(run_id, "END")] = end
    roles = {"g1": "AXIS_A", "h1": "AXIS_A", "h2": "AXIS_A", "h3": "AXIS_A", "x": "AXIS_B"}
    signs = {run_id: 1.0 for run_id in roles}
    return runs, roles, signs, node_by_run_end


def test_axis_solve_anchors_every_group_to_the_frame_by_its_mean() -> None:
    from scaffold_core.layer_5_runtime.axis_solve import solve_axis

    runs, roles, signs, node_by_run_end = _two_group_axis()
    frame = {"n0": 100.0, "n1": 110.0, "n2": 103.0, "n3": 105.0, "n4": 108.0, "n5": 50.0, "n6": 50.2}
    diagnostics: list[str] = []
    solve = solve_axis(
        "AXIS_A", runs, roles, signs, node_by_run_end, diagnostics, drift=0.01, frame_coordinate_by_node=frame
    )
    coords = solve.coordinate_by_node

    assert diagnostics == []
    assert (coords["n0"], coords["n1"]) == pytest.approx((100.0, 110.0), abs=1e-9)
    # The drifting group keeps its least-squares lengths, and its mean sits on
    # the mean of its frame coordinates (not on its first node).
    group = ("n2", "n3", "n4")
    assert sum(coords[node] for node in group) / 3 == pytest.approx(sum(frame[node] for node in group) / 3, abs=1e-9)
    assert coords["n3"] - coords["n2"] == pytest.approx(2.001, abs=1e-6)
    assert coords["n4"] - coords["n3"] == pytest.approx(3.001, abs=1e-6)
    assert abs(coords["n2"] - frame["n2"]) > 1e-4
    # A component with no AXIS_A equation takes its nodes' mean frame coordinate.
    assert (coords["n5"], coords["n6"]) == pytest.approx((50.1, 50.1), abs=1e-9)
    assert solve.frame_only_nodes == {"n5", "n6"}


def test_frame_free_axis_solve_keeps_only_the_largest_group() -> None:
    from scaffold_core.layer_5_runtime.axis_solve import solve_axis

    runs, roles, signs, node_by_run_end = _two_group_axis()
    diagnostics: list[str] = []
    solve = solve_axis("AXIS_A", runs, roles, signs, node_by_run_end, diagnostics, drift=0.01)

    assert set(solve.coordinate_by_node) == {"n2", "n3", "n4"}
    assert diagnostics == ["AXIS_A: 2 nodes in 1 equation groups not tied to the gauge -> unpinned"]
    # Paired: the main group solves exactly as it does alone.
    main_only = tuple(e for e in runs if e.id.startswith("h"))
    alone = solve_axis("AXIS_A", main_only, roles, signs, node_by_run_end, [], drift=0.01)
    assert solve.coordinate_by_node == alone.coordinate_by_node
    # A tie in size keeps the group holding the lexically smallest node id.
    tie_runs = (runs[0], SimpleNamespace(id="k", length=4.0, direction=(1.0, 0.0, 0.0)))
    tie_ends = dict(node_by_run_end)
    tie_ends[("k", "START")], tie_ends[("k", "END")] = "m0", "m1"
    tie = solve_axis("AXIS_A", tie_runs, {"g1": "AXIS_A", "k": "AXIS_A"}, {"g1": 1.0, "k": 1.0}, tie_ends, [])
    assert set(tie.coordinate_by_node) == {"m0", "m1"}


def test_stations_pin_inner_vertices_of_a_straight_run_at_arc_length() -> None:
    # The wall's bottom run has three collinear segments of 3, 2 and 5 m: its
    # inner vertices sit at 30 % and 50 % of the way, not at thirds.
    result = _solve(_window_wall_source())
    uv = {vertex.source_vertex_id: vertex.uv for vertex in result.vertices}
    start, end = uv["v0"], uv["v3"]

    for vertex, t in (("v1", 0.3), ("v2", 0.5)):
        expected = tuple(start[i] + t * (end[i] - start[i]) for i in range(2))
        assert uv[vertex] == pytest.approx(expected, abs=1e-9), vertex
    assert len(result.vertices) == 16  # 8 run ends + 8 stations: every boundary vertex
    assert result.axis_parallel_violations == ()


def test_stations_follow_a_zigzag_chord_run_on_its_straight_uv_segment() -> None:
    # The arch front f16 keeps one foot chain as one chord run (plan Slice W);
    # its inner vertices go onto the run's straight UV segment at their arc
    # length, while the OBLIQUE foot run gets no stations.
    context = run_pass_1_relations(run_pass_0(_load_capture("artist_arch_bevel.json")))
    result = run_skeleton_solve(context)
    patch_id = "patch:seed:f16"
    skeleton = _skeleton_by_island(result)[result.assembly.island_by_patch_id[patch_id]]
    feet = [
        e for e in context.relation_snapshot.patch_chain_directional_evidence
        if str(e.patch_id) == patch_id and len(e.segment_indices) > 1
    ]
    pin = {(v.source_vertex_id, v.patch_id): v.uv for v in result.vertices}
    roles = {skeleton.axis_role_by_run[e.id] for e in feet}
    assert roles == {"AXIS_A", "OBLIQUE"}

    for e in feet:
        segments = {s.segment_index: s for s in context.geometry_facts.chain_facts[e.parent_chain_id].segments}
        path = [segments[index] for index in e.segment_indices]
        if str(path[0].start_source_vertex_id) != str(e.start_source_vertex_id) and str(
            path[0].end_source_vertex_id
        ) != str(e.start_source_vertex_id):
            path.reverse()
        current, walked, inner = str(e.start_source_vertex_id), 0.0, []
        for segment in path:
            current = (
                str(segment.end_source_vertex_id)
                if str(segment.start_source_vertex_id) == current
                else str(segment.start_source_vertex_id)
            )
            walked += segment.length
            inner.append((current, walked))
        total = walked
        inner = inner[:-1]
        assert len(inner) == 4
        if skeleton.axis_role_by_run[e.id] == "OBLIQUE":
            assert not any((vertex, patch_id) in pin for vertex, _walked in inner)
            continue
        start, end = pin[(str(e.start_source_vertex_id), patch_id)], pin[(str(e.end_source_vertex_id), patch_id)]
        for vertex, walked in inner:
            t = walked / total
            assert pin[(vertex, patch_id)] == pytest.approx(
                tuple(start[i] + t * (end[i] - start[i]) for i in range(2)), abs=1e-9
            )


def test_station_pins_skip_oblique_runs_unpinned_ends_and_existing_pins() -> None:
    context = run_pass_1_relations(run_pass_0(_window_wall_source()))
    result = run_skeleton_solve(context)
    skeleton = result.skeletons[0]
    evidence = {e.id: e for e in context.relation_snapshot.patch_chain_directional_evidence}
    bottom = next(run_id for run_id, e in evidence.items() if (e.start_source_vertex_id, e.end_source_vertex_id) == ("v0", "v3"))
    a, b = skeleton.axis_a.coordinate_by_node, skeleton.axis_b.coordinate_by_node
    uv_by_node = {node: (a[node], b[node]) for node in a if node in b}
    patch = str(evidence[bottom].patch_id)
    keys = {("vertex:v1", patch), ("vertex:v2", patch)}

    def stations(skeleton_, uv_by_node_, vertices):
        _station_pins(
            skeleton_, evidence, uv_by_node_, context.geometry_facts, result.vertex_by_face_corner, vertices, 0.0
        )
        return vertices

    assert keys <= set(stations(skeleton, uv_by_node, {}))
    oblique = replace(skeleton, axis_role_by_run={**skeleton.axis_role_by_run, bottom: "OBLIQUE"})
    assert not keys & set(stations(oblique, uv_by_node, {}))
    unpinned_end = {node: value for node, value in uv_by_node.items() if node != skeleton.node_by_run_end[(bottom, "END")]}
    assert not keys & set(stations(skeleton, unpinned_end, {}))
    run_end_pin = PinnedVertex("v1", skeleton.island_id, patch, (9.0, 9.0), True, "vertex:v1")
    kept = stations(skeleton, uv_by_node, {("vertex:v1", patch): run_end_pin})
    assert kept[("vertex:v1", patch)] is run_end_pin
    assert ("vertex:v2", patch) in kept


def _contradicted_axis():
    """X-Y 1, Y-Z 1, Z-W 1 and Y-W 5: the Y-Z-W cycle contradicts itself."""

    def run(run_id, run_length):
        return SimpleNamespace(id=run_id, length=run_length, direction=(1.0, 0.0, 0.0))

    runs = (run("xy", 1.0), run("yz", 1.0), run("zw", 1.0), run("yw", 5.0))
    node_by_run_end = {}
    for e in runs:
        node_by_run_end[(e.id, "START")] = e.id[0].upper()
        node_by_run_end[(e.id, "END")] = e.id[1].upper()
    roles = {e.id: "AXIS_A" for e in runs}
    return runs, roles, {run_id: 1.0 for run_id in roles}, node_by_run_end


@pytest.mark.parametrize("framed", (True, False))
def test_unconstrained_components_get_no_coordinate_with_or_without_a_frame(framed) -> None:
    # X's only equation touches the contradicted cycle, so X is left without
    # an equation: a framed island gives it its frame coordinate, a frame-free
    # island drops it. Y, Z, W stay UNCONSTRAINED, frame or not (HEAD left X
    # at -5.0, a leftover of the contradicted solve).
    from scaffold_core.layer_5_runtime.axis_solve import solve_axis

    runs, roles, signs, node_by_run_end = _contradicted_axis()
    frame = {"X": 10.0, "Y": 11.0, "Z": 12.0, "W": 13.0} if framed else None
    diagnostics: list[str] = []
    solve = solve_axis(
        "AXIS_A", runs, roles, signs, node_by_run_end, diagnostics, drift=0.01, frame_coordinate_by_node=frame
    )

    assert any("contradictory" in diagnostic for diagnostic in diagnostics)
    assert solve.unconstrained_components
    assert dict(solve.coordinate_by_node) == ({"X": 10.0} if framed else {})


def test_station_pins_skip_a_ring_run_whose_ends_are_one_node() -> None:
    context = run_pass_1_relations(run_pass_0(_window_wall_source()))
    result = run_skeleton_solve(context)
    skeleton = result.skeletons[0]
    evidence = {e.id: e for e in context.relation_snapshot.patch_chain_directional_evidence}
    bottom = next(run_id for run_id, e in evidence.items() if (e.start_source_vertex_id, e.end_source_vertex_id) == ("v0", "v3"))
    a, b = skeleton.axis_a.coordinate_by_node, skeleton.axis_b.coordinate_by_node
    uv_by_node = {node: (a[node], b[node]) for node in a if node in b}
    ring = replace(skeleton, node_by_run_end={
        **skeleton.node_by_run_end, (bottom, "END"): skeleton.node_by_run_end[(bottom, "START")]
    })
    vertices: dict = {}
    _station_pins(ring, evidence, uv_by_node, context.geometry_facts, result.vertex_by_face_corner, vertices, 0.0)

    patch = str(evidence[bottom].patch_id)
    assert not {("vertex:v1", patch), ("vertex:v2", patch)} & set(vertices)
    assert vertices  # the other runs still get their stations


def test_station_vertex_touching_both_seam_sides_is_skipped_and_counted() -> None:
    # v1's two bottom-run segments name two different occurrences (as when a
    # seam side changes at v1): no single own occurrence, so no guess.
    from scaffold_core.layer_5_runtime.pins import _island_vertices

    context = run_pass_1_relations(run_pass_0(_window_wall_source()))
    result = run_skeleton_solve(context)
    skeleton = result.skeletons[0]
    evidence = {e.id: e for e in context.relation_snapshot.patch_chain_directional_evidence}
    bottom = next(e for e in evidence.values() if (e.start_source_vertex_id, e.end_source_vertex_id) == ("v0", "v3"))
    side_faces = context.geometry_facts.patch_chain_facts[bottom.patch_chain_id].segment_side_face_ids
    faces_at_v1 = {
        str(face) for face in side_faces
        if face is not None and "v1" in {str(v) for v in context.source_snapshot.faces[face].vertex_ids}
    }
    assert len(faces_at_v1) == 2
    split = dict(result.vertex_by_face_corner)
    split[(max(faces_at_v1), "v1")] = "vertex:v1:other_side"
    diagnostics: list[str] = []
    vertices, _violations, _width = _island_vertices(
        skeleton, evidence, 0.0, context.geometry_facts, split, diagnostics
    )

    assert not any(vertex.source_vertex_id == "v1" for vertex in vertices)
    assert any(vertex.source_vertex_id == "v2" for vertex in vertices)
    assert diagnostics == [
        f"{skeleton.island_id}: 1 station vertices without one occurrence on their side -> unpinned"
    ]


@pytest.mark.parametrize("mode", ("OBJECT", "EDIT"))
def test_stitched_seam_gets_station_pins_on_each_side_with_equal_uvs(monkeypatch, mode: str) -> None:
    # Two coplanar patches stitched along a straight seam of two segments
    # (1 and 2 m): the seam's inner vertex v4 is a station on both sides.
    source = _grid_wall_source((0.0, 2.0, 5.0), (0.0, 1.0, 3.0), seams=("e_v1_v4", "e_v4_v7"))
    result = _solve(source)
    assert len(result.assembly.islands) == 1 and len(result.assembly.islands[0].patch_ids) == 2
    stations = [vertex for vertex in result.vertices if vertex.source_vertex_id == "v4"]

    assert {vertex.patch_id for vertex in stations} == set(result.assembly.islands[0].patch_ids)
    assert stations[0].uv == pytest.approx(stations[1].uv, abs=1e-12)
    written = _write_with_fake_bmesh(monkeypatch, source, result, mode)
    corners = [corner for corner in written if corner[1] == "v4"]
    assert len(corners) == 4
    assert all(written[corner].pin_uv is True for corner in corners)
    assert all(written[corner].uv == pytest.approx(stations[0].uv, abs=1e-12) for corner in corners)


def test_self_seam_sides_get_their_own_station_pins() -> None:
    # The straight two-segment SEAM_SELF of the segmented tube: its inner
    # vertex has one occurrence per seam side, and each side's station is
    # read through its own side faces, so each face corner at v_a_m takes the
    # u of its own seam side.
    result = _solve(make_segmented_cylinder_tube_without_caps_with_one_seam_source())
    pin = {(vertex.vertex_id, vertex.patch_id): vertex for vertex in result.vertices}
    patch_of = result.patch_by_source_face
    stations = [vertex for vertex in result.vertices if vertex.source_vertex_id == "v_a_m"]

    assert len({vertex.vertex_id for vertex in stations}) == 2
    for face_id in ("f_ab_top", "f_ab_bot", "f_da_top", "f_da_bot"):
        mid = pin[(result.vertex_by_face_corner[(face_id, "v_a_m")], patch_of[face_id])]
        rim_vertex = "v_a_t" if face_id.endswith("top") else "v_a_b"
        rim = pin[(result.vertex_by_face_corner[(face_id, rim_vertex)], patch_of[face_id])]
        assert mid.uv[0] == pytest.approx(rim.uv[0], abs=1e-9), face_id


def _boundary_corners_pinned(context, result, patch_id):
    """Every face corner of the patch on its boundary chains has its own pin; returns their UVs."""

    topology = context.topology_snapshot
    boundary = {
        str(vertex)
        for pc in topology.patch_chains.values()
        if str(pc.patch_id) == patch_id
        for vertex in context.geometry_facts.chain_facts[pc.chain_id].source_vertex_run
    }
    pin = {(vertex.vertex_id, vertex.patch_id): vertex.uv for vertex in result.vertices if vertex.pinned}
    uvs, missing = [], []
    for face_id in topology.patches[patch_id].source_face_ids:
        for vertex in context.source_snapshot.faces[face_id].vertex_ids:
            if str(vertex) not in boundary:
                continue
            key = (result.vertex_by_face_corner[(str(face_id), str(vertex))], patch_id)
            (uvs.append(pin[key]) if key in pin else missing.append(key))
    return uvs, missing


@pytest.mark.parametrize("which", ("arch_front", "cut_annulus"))
def test_strip_islands_pin_every_boundary_vertex_on_their_rectangle(which) -> None:
    source = _load_capture("artist_arch_bevel.json") if which == "arch_front" else make_cut_annulus_source()
    context = run_pass_2_features(run_pass_1_relations(run_pass_0(source)), FeatureOptions(straighten_strips=True))
    result = run_skeleton_solve(context)
    patch_id = "patch:seed:f16" if which == "arch_front" else str(context.feature_snapshot.constraints[0].patch_id)
    skeleton = _skeleton_by_island(result)[result.assembly.island_by_patch_id[patch_id]]
    assert skeleton.frame == "STRIP"

    uvs, missing = _boundary_corners_pinned(context, result, patch_id)
    assert uvs and not missing
    us, vs = [uv[0] for uv in uvs], [uv[1] for uv in uvs]
    for u, v in uvs:  # every boundary pin lies on a side of the rectangle
        assert min(abs(u - min(us)), abs(u - max(us)), abs(v - min(vs)), abs(v - max(vs))) < 1e-9, (u, v)
    assert result.axis_parallel_violations == ()


def _pinned_face_areas(context, result) -> list[float]:
    uv_by_vertex_patch = {
        (vertex.source_vertex_id, vertex.patch_id): vertex.uv
        for vertex in result.vertices
        if vertex.pinned
    }
    areas = []
    for patch_id, patch in context.topology_snapshot.patches.items():
        for face_id in patch.source_face_ids:
            points = [
                uv_by_vertex_patch.get((str(vertex_id), str(patch_id)))
                for vertex_id in context.source_snapshot.faces[face_id].vertex_ids
            ]
            if any(point is None for point in points):
                continue
            areas.append(0.5 * sum(
                points[index][0] * points[(index + 1) % len(points)][1]
                - points[(index + 1) % len(points)][0] * points[index][1]
                for index in range(len(points))
            ))
    return areas


def _pinched_grid_source() -> SourceMeshSnapshot:
    """Planar 3x3 quad grid without cells f0 and f4: f1 and f3 touch only at v5.

    Blender-style ids (v<i + 4j>, f<i + 3j>) so the fake BMesh can write it.
    """

    vertices, edges, faces = {}, {}, {}
    for j in range(3):
        for i in range(3):
            if i + 3 * j in (0, 4):
                continue
            corners = ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))
            ids = tuple(SourceVertexId(f"v{a + 4 * b}") for a, b in corners)
            for vertex_id, (a, b) in zip(ids, corners):
                vertices[vertex_id] = MeshVertexRef(vertex_id, (float(a), float(b), 0.0))
            edge_ids = []
            for pair in (tuple(sorted(pair)) for pair in zip(ids, ids[1:] + ids[:1])):
                edge_id = SourceEdgeId(f"e_{pair[0]}_{pair[1]}")
                edges.setdefault(edge_id, MeshEdgeRef(edge_id, pair))
                edge_ids.append(edge_id)
            face_id = SourceFaceId(f"f{i + 3 * j}")
            faces[face_id] = MeshFaceRef(face_id, ids, tuple(edge_ids))
    return SourceMeshSnapshot(
        id=SourceMeshId("pinched_grid"),
        vertices=vertices,
        edges=edges,
        faces=faces,
        selected_face_ids=tuple(faces),
        marks=(),
    )


class _FakeLoop:
    """BMesh loop stand-in: loop[uv_layer] is this loop's UV data."""

    def __init__(self, vertex_index: int) -> None:
        self.vert = SimpleNamespace(index=vertex_index)
        self.uv_data = SimpleNamespace(uv=None, pin_uv=None)

    def __getitem__(self, uv_layer):
        return self.uv_data


class _FakeFaces(list):
    def ensure_lookup_table(self) -> None:
        pass


def _write_with_fake_bmesh(monkeypatch, source, result, mode: str) -> dict:
    """Run the real uv_transfer write on a fake BMesh; UV data per (face, vertex)."""

    faces = _FakeFaces(
        SimpleNamespace(
            index=int(str(face_id)[1:]),
            loops=[_FakeLoop(int(str(vertex_id)[1:])) for vertex_id in face.vertex_ids],
        )
        for face_id, face in source.faces.items()
    )
    bm = SimpleNamespace(
        faces=faces,
        loops=SimpleNamespace(layers=SimpleNamespace(uv=SimpleNamespace(verify=lambda: "uv"))),
        from_mesh=lambda mesh: None,
        to_mesh=lambda mesh: None,
        free=lambda: None,
    )
    monkeypatch.setitem(sys.modules, "bpy", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "bmesh", SimpleNamespace(
        new=lambda: bm,
        from_edit_mesh=lambda mesh: bm,
        update_edit_mesh=lambda mesh: None,
    ))
    mesh_object = SimpleNamespace(type="MESH", mode=mode, data=SimpleNamespace(update=lambda: None))
    write_pinned_uvs(SimpleNamespace(object=mesh_object), result)
    # uv_transfer names Blender elements like blender_io: f<index>, v<index>.
    return {(f"f{face.index}", f"v{loop.vert.index}"): loop.uv_data for face in faces for loop in face.loops}


def _bridge_on_one_component(offset):
    """Axis A solve: c bridges two nodes that the AXIS_B run b joins into one component."""

    from scaffold_core.layer_5_runtime.axis_solve import solve_axis

    runs = (
        SimpleNamespace(id="a", length=1.0, direction=(1.0, 0.0, 0.0)),
        SimpleNamespace(id="b", length=1.0, direction=(0.0, 1.0, 0.0)),
        SimpleNamespace(id="c", length=1.0, direction=(0.7, 0.7, 0.0)),
    )
    node_by_run_end = {
        ("a", "START"): "n0", ("a", "END"): "n2",
        ("b", "START"): "n0", ("b", "END"): "n1",
        ("c", "START"): "n0", ("c", "END"): "n1",
    }
    roles = {"a": "AXIS_A", "b": "AXIS_B", "c": "OBLIQUE"}
    diagnostics: list[str] = []
    solve = solve_axis(
        "AXIS_A", runs, roles, {"a": 1.0, "b": 1.0}, node_by_run_end, diagnostics,
        bridge_offset_by_run={"c": offset},
    )
    return solve, diagnostics


def test_bridge_whose_ends_share_a_cross_component_is_judged_by_the_residual() -> None:
    # A non-zero offset between two nodes of one component cannot hold: its
    # residual is the offset, so the component goes UNCONSTRAINED, reported.
    solve, diagnostics = _bridge_on_one_component(0.5)

    assert solve.equation_count == 2
    assert diagnostics == ["AXIS_A: 1 contradictory equations -> UNCONSTRAINED components"]
    assert "n0" not in solve.coordinate_by_node and "n1" not in solve.coordinate_by_node


def test_bridge_with_zero_offset_inside_one_component_adds_no_equation() -> None:
    solve, diagnostics = _bridge_on_one_component(1e-7)

    assert solve.equation_count == 1  # the AXIS_A run alone
    assert diagnostics == []
    assert solve.coordinate_by_node["n2"] - solve.coordinate_by_node["n0"] == pytest.approx(1.0)


def test_bridged_corner_off_a_right_angle_within_tolerance_is_reported_not_silent() -> None:
    # Pinned behaviour (Slice AD review): turns of 44 and 43 degrees make a
    # 93-degree corner, inside the DD-45 tolerance, so the record exists and
    # the bridge is laid for an exact right angle. The true top side is 3
    # degrees off the bottom, so the island cannot close: the solve reports
    # contradictory equations and pins nothing; it never places wrong pins.
    context = run_pass_1_relations(run_pass_0(make_folded_cut_corner_source(44.0, 43.0)))
    (record,) = context.relation_snapshot.run_bridged_corner_relations
    result = run_skeleton_solve(context)
    (skeleton,) = result.skeletons

    assert round(record.interior_angle_sum * 180.0 / pi, 6) == 93.0
    assert skeleton.frame == "FRAME_FREE"
    assert record.bridge_directional_evidence_id in skeleton.bridge_vector_by_run
    assert "AXIS_A: 5 contradictory equations -> UNCONSTRAINED components" in skeleton.diagnostics
    assert "AXIS_B: 3 contradictory equations -> UNCONSTRAINED components" in skeleton.diagnostics
    assert skeleton.axis_a.unconstrained_components and skeleton.axis_b.unconstrained_components
    assert not [vertex for vertex in result.vertices if vertex.pinned]
    # The same sheet with turns that add up to 90 degrees solves exactly.
    exact = run_skeleton_solve(run_pass_1_relations(run_pass_0(make_folded_cut_corner_source(45.0, 45.0))))
    assert exact.skeletons[0].diagnostics == ()
    assert len([vertex for vertex in exact.vertices if vertex.pinned]) == 7
