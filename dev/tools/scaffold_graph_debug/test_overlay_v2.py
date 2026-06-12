"""Headless checks for ScaffoldGraph overlay v2 pure assembly."""

from __future__ import annotations

import importlib

from dev.tools.scaffold_graph_debug.geodesic_continuation import GEODESIC_STRAIGHT_TOLERANCE
from dev.tools.scaffold_graph_debug.overlay_v2 import build_overlay_v2_payload
from dev.tools.scaffold_graph_debug.seam_verdicts import ANGLE_DEFECT_TOLERANCE
from scaffold_core.ids import SourceEdgeId, SourceFaceId, SourceMeshId, SourceVertexId
from scaffold_core.layer_0_source.marks import SourceMark, SourceMarkKind
from scaffold_core.layer_0_source.snapshot import (
    MeshEdgeRef,
    MeshFaceRef,
    MeshVertexRef,
    SourceMeshSnapshot,
)
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
from scaffold_core.tests.fixtures.beveled_wall_corner import make_beveled_wall_corner_source
from scaffold_core.tests.fixtures.cylinder_tube import (
    make_cylinder_tube_without_caps_with_two_seams_source,
)
from scaffold_core.tests.fixtures.l_corridor_tunnel import make_l_corridor_tunnel_seamed_folds_source
from scaffold_core.tests.fixtures.non_manifold import make_three_quad_non_manifold_source
from scaffold_core.tests.fixtures.tube_with_cap import make_tube_with_cap_source


def _payload(source_factory):
    return build_overlay_v2_payload(run_pass_1_relations(run_pass_0(source_factory())))


def test_pure_overlay_modules_import_without_blender() -> None:
    importlib.import_module("dev.tools.scaffold_graph_debug")
    importlib.import_module("dev.tools.scaffold_graph_debug.colors")
    importlib.import_module("dev.tools.scaffold_graph_debug.overlay_v2")
    importlib.import_module("dev.tools.scaffold_graph_debug.rail_assembly")
    importlib.import_module("dev.tools.scaffold_graph_debug.seam_verdicts")
    assert ANGLE_DEFECT_TOLERANCE > 0.0
    assert GEODESIC_STRAIGHT_TOLERANCE == 0.1


def test_beveled_corner_has_horizontal_spine_and_vertical_ribs() -> None:
    payload = _payload(make_beveled_wall_corner_source)

    spines = _rails(payload, "SPINE")
    assert len(spines) == 1
    spine = spines[0]
    assert spine["length"] > 1.9
    assert _has_patch_fragments(spine, ("f_wall_a", "f_chamfer", "f_wall_b"))
    assert _has_member_fragments(spine, ("f_wall_a:0:0:2", "f_chamfer:0:0:0", "f_wall_b:0:0:0"))

    parallel_rails = _rails(payload, "PARALLEL")
    assert len(parallel_rails) == 1
    assert parallel_rails[0]["length"] > 1.9

    seam_ribs = [
        rail
        for rail in _rails(payload, "RIB")
        if _has_patch_fragments(rail, ("f_wall_a", "f_chamfer"))
        or _has_patch_fragments(rail, ("f_chamfer", "f_wall_b"))
    ]
    assert len(seam_ribs) >= 2


def test_two_seam_tube_has_top_and_bottom_ring_rails() -> None:
    payload = _payload(make_cylinder_tube_without_caps_with_two_seams_source)

    ring_rails = [
        rail
        for rail in payload["rails"]
        if rail["role"] in {"SPINE", "PARALLEL"} and rail["length"] > 5.0
    ]
    assert len(ring_rails) == 2
    assert {rail["role"] for rail in ring_rails} == {"SPINE", "PARALLEL"}
    assert all(_has_patch_fragments(rail, ("f0", "f2")) for rail in ring_rails)


def test_tube_with_cap_side_rims_win_over_cap_perimeter_view() -> None:
    payload = _payload(make_tube_with_cap_source)

    visible_side_rims = [
        rail
        for rail in payload["rails"]
        if rail["is_default_visible"]
        and rail["role"] in {"SPINE", "PARALLEL"}
        and _has_patch_fragments(rail, ("f0",))
        and len(rail["directional_evidence_ids"]) == 4
    ]
    assert len(visible_side_rims) == 2
    assert all(rail["length"] > 5.0 for rail in visible_side_rims)

    hidden_cap_perimeter = [
        rail
        for rail in payload["rails"]
        if not rail["is_default_visible"] and _has_patch_fragments(rail, ("f_cap",))
    ]
    assert len(hidden_cap_perimeter) == 4
    assert all(len(rail["directional_evidence_ids"]) == 1 for rail in hidden_cap_perimeter)
    assert payload["counts"]["hidden_patch_view_rail_count"] == 4
    assert payload["counts"]["cut_rail_count"] == 2


def test_extruded_cross_side_band_rims_are_geodesic_rails_and_seam_is_cut() -> None:
    payload = _payload(_make_extruded_cross_source)

    visible_long_rails = [
        rail
        for rail in payload["rails"]
        if rail["is_default_visible"]
        and rail["role"] in {"SPINE", "PARALLEL"}
        and len(rail["directional_evidence_ids"]) == 12
        and rail["length"] > 20.0
    ]
    assert len(visible_long_rails) == 2
    assert {rail["role"] for rail in visible_long_rails} == {"SPINE", "PARALLEL"}

    hidden_cap_perimeters = [
        rail
        for rail in payload["rails"]
        if not rail["is_default_visible"] and len(rail["directional_evidence_ids"]) == 1
    ]
    assert len(hidden_cap_perimeters) == 24
    assert payload["counts"]["cut_rail_count"] >= 1
    assert any(verdict["status"] == "CUT" for verdict in payload["seam_verdicts"])


def test_l_corridor_tunnel_has_length_spine_through_folds() -> None:
    payload = _payload(make_l_corridor_tunnel_seamed_folds_source)

    spines = _rails(payload, "SPINE")
    assert len(spines) == 1
    spine = spines[0]
    assert spine["length"] == 3.0
    assert _has_patch_fragments(spine, ("f_floor", "f_wall", "f_ceiling"))
    assert len(spine["directional_evidence_ids"]) == 3


def test_branch_fixture_emits_branch_glyphs_without_collapsing_choices() -> None:
    payload = _payload(make_three_quad_non_manifold_source)

    assert payload["counts"]["branch_glyph_count"] == 2
    assert {glyph["valence"] for glyph in payload["branch_glyphs"]} == {6}
    assert all(len(rail["directional_evidence_ids"]) == 1 for rail in payload["rails"])


def test_seam_verdicts_match_level_a_expectations() -> None:
    cap_payload = _payload(make_tube_with_cap_source)
    cap_verdicts = cap_payload["seam_verdicts"]
    assert len(cap_verdicts) == 1
    assert cap_verdicts[0]["status"] == "CUT"
    assert len(cap_verdicts[0]["failing_vertex_ids"]) >= 1
    assert cap_verdicts[0]["line_style"] == "SOLID"

    tube_payload = _payload(make_cylinder_tube_without_caps_with_two_seams_source)
    tube_verdicts = tube_payload["seam_verdicts"]
    assert len(tube_verdicts) == 2
    assert {verdict["status"] for verdict in tube_verdicts} == {"SEWABLE"}
    assert all(verdict["line_style"] == "DASHED" for verdict in tube_verdicts)


def _rails(payload, role: str):
    return [rail for rail in payload["rails"] if rail["role"] == role]


def _has_patch_fragments(rail, fragments: tuple[str, ...]) -> bool:
    return all(
        any(fragment in patch_id for patch_id in rail["patch_ids"])
        for fragment in fragments
    )


def _has_member_fragments(rail, fragments: tuple[str, ...]) -> bool:
    return all(
        any(fragment in evidence_id for evidence_id in rail["directional_evidence_ids"])
        for fragment in fragments
    )


def _make_extruded_cross_source() -> SourceMeshSnapshot:
    footprint = (
        (-1.0, 3.0),
        (1.0, 3.0),
        (1.0, 1.0),
        (3.0, 1.0),
        (3.0, -1.0),
        (1.0, -1.0),
        (1.0, -3.0),
        (-1.0, -3.0),
        (-1.0, -1.0),
        (-3.0, -1.0),
        (-3.0, 1.0),
        (-1.0, 1.0),
    )
    top = tuple(SourceVertexId(f"t{index}") for index in range(len(footprint)))
    bottom = tuple(SourceVertexId(f"b{index}") for index in range(len(footprint)))
    top_edges = tuple(SourceEdgeId(f"e_t{index}") for index in range(len(footprint)))
    bottom_edges = tuple(SourceEdgeId(f"e_b{index}") for index in range(len(footprint)))
    vertical_edges = tuple(SourceEdgeId(f"e_v{index}") for index in range(len(footprint)))

    vertices = {
        **{
            top[index]: MeshVertexRef(top[index], (x, y, 1.0))
            for index, (x, y) in enumerate(footprint)
        },
        **{
            bottom[index]: MeshVertexRef(bottom[index], (x, y, 0.0))
            for index, (x, y) in enumerate(footprint)
        },
    }
    edge_count = len(footprint)
    edges = {}
    for index in range(edge_count):
        next_index = (index + 1) % edge_count
        edges[top_edges[index]] = MeshEdgeRef(top_edges[index], (top[index], top[next_index]))
        edges[bottom_edges[index]] = MeshEdgeRef(bottom_edges[index], (bottom[index], bottom[next_index]))
        edges[vertical_edges[index]] = MeshEdgeRef(vertical_edges[index], (top[index], bottom[index]))

    side_faces = {
        SourceFaceId(f"f_side_{index}"): MeshFaceRef(
            SourceFaceId(f"f_side_{index}"),
            (top[index], bottom[index], bottom[(index + 1) % edge_count], top[(index + 1) % edge_count]),
            (vertical_edges[index], bottom_edges[index], vertical_edges[(index + 1) % edge_count], top_edges[index]),
        )
        for index in range(edge_count)
    }
    top_face = SourceFaceId("f_cap_top")
    bottom_face = SourceFaceId("f_cap_bottom")
    faces = {
        **side_faces,
        top_face: MeshFaceRef(top_face, top, top_edges),
        bottom_face: MeshFaceRef(bottom_face, bottom, bottom_edges),
    }
    seam_marks = tuple(
        SourceMark(kind=SourceMarkKind.SEAM, target_id=edge_id)
        for edge_id in (*top_edges, *bottom_edges, vertical_edges[0])
    )
    return SourceMeshSnapshot(
        id=SourceMeshId("extruded_cross_building"),
        vertices=vertices,
        edges=edges,
        faces=faces,
        selected_face_ids=tuple(faces),
        marks=seam_marks,
    )
