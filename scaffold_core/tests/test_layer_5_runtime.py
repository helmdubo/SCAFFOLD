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
from dataclasses import replace
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
from scaffold_core.layer_5_runtime.islands import IslandAssembly
from scaffold_core.layer_5_runtime.pins import PinnedVertex, SolveResult, run_skeleton_solve
from scaffold_core.layer_5_runtime.uv_transfer import write_pinned_uvs
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
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
    from scaffold_core.layer_5_runtime.skeleton import _lstsq

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


def test_warped_face_stays_outside_the_rigid_island_frame() -> None:
    # A single warped n-gon has no rotation axis. It stays OBLIQUE with a
    # diagnostic; the planar wall keeps the rigid frame and its axes.
    source = make_t_vertex_wall_source()
    lifted = dict(source.vertices)
    corner = SourceVertexId("a0")
    lifted[corner] = MeshVertexRef(corner, (0.0, -1.0, 0.5))
    result = _solve(replace(source, vertices=lifted))

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


def test_bent_hinge_between_tilted_patches_stays_outside_the_frame() -> None:
    # The corner quad tilts 5.7 degrees away from the panel yet stays within
    # the planarity tolerance; an L-shaped hinge has no rotation axis, so the
    # quad must not be rotated about the chord of the L.
    result = _solve(make_bent_hinge_panels_source(corner_lift=0.14))

    skeleton = result.skeletons[0]
    assert skeleton.frame == "UNFOLDED"
    assert skeleton.diagnostics == (
        "patch outside the rigid island frame: patch:seed:f_corner -> OBLIQUE",
    )
    assert all(
        role == "OBLIQUE"
        for run_id, role in skeleton.axis_role_by_run.items()
        if ":f_corner:" in run_id
    )
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
    # The two 32-gon caps of artist_cyl32 are islands without pins of their
    # own. Their loops used to take the band's rim pins (another island), which
    # laid each cap onto the band's rim row. A loop without a pin of its own
    # stays unpinned and untouched for U > Unwrap.
    source = _load_capture("artist_cyl32.json")
    result = _solve(source)
    own_pins = {(vertex.source_vertex_id, vertex.patch_id) for vertex in result.vertices}
    written = _write_with_fake_bmesh(monkeypatch, source, result, mode)

    without_own_pin = [
        (face_id, vertex_id)
        for face_id, vertex_id in written
        if (vertex_id, result.patch_by_source_face[face_id]) not in own_pins
    ]
    assert len(without_own_pin) == 64  # every rim corner of both caps
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
