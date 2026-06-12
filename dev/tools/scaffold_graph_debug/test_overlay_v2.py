"""Headless checks for ScaffoldGraph overlay v2 pure assembly."""

from __future__ import annotations

import importlib
import json

from dev.tools.scaffold_graph_debug.overlay_v2 import build_overlay_v2_payload
from dev.tools.scaffold_graph_debug.rail_offsets import (
    RAIL_NORMAL_HOVER_FACTOR,
    RAIL_OFFSET_FACTOR,
    coalesce_polylines,
)
from dev.tools.scaffold_graph_debug.seam_verdicts import ANGLE_DEFECT_TOLERANCE
from dev.tools.scaffold_graph_debug.snapshot_io import dump_source_snapshot, load_source_snapshot
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
from scaffold_core.tests.fixtures.beveled_wall_corner import make_beveled_wall_corner_source
from scaffold_core.tests.fixtures.cylinder_tube import (
    make_cylinder_tube_without_caps_with_two_seams_source,
)
from scaffold_core.tests.fixtures.extruded_cross import make_extruded_cross_source
from scaffold_core.tests.fixtures.l_corridor_tunnel import make_l_corridor_tunnel_seamed_folds_source
from scaffold_core.tests.fixtures.non_manifold import make_three_quad_non_manifold_source
from scaffold_core.tests.fixtures.tube_with_cap import make_tube_with_cap_source


def _payload(source_factory):
    return build_overlay_v2_payload(run_pass_1_relations(run_pass_0(source_factory())))


def _context_payload(source):
    context = run_pass_1_relations(run_pass_0(source))
    return context, build_overlay_v2_payload(context)


def test_pure_overlay_modules_import_without_blender() -> None:
    importlib.import_module("dev.tools.scaffold_graph_debug")
    build_stamp = importlib.import_module("dev.tools.scaffold_graph_debug.build_stamp")
    importlib.import_module("dev.tools.scaffold_graph_debug.colors")
    importlib.import_module("dev.tools.scaffold_graph_debug.overlay_v2")
    importlib.import_module("dev.tools.scaffold_graph_debug.rail_assembly")
    importlib.import_module("dev.tools.scaffold_graph_debug.rail_offsets")
    importlib.import_module("dev.tools.scaffold_graph_debug.seam_verdicts")
    assert ANGLE_DEFECT_TOLERANCE > 0.0
    assert _payload(make_tube_with_cap_source)["geodesic_straight_tolerance"] == 0.1
    assert RAIL_OFFSET_FACTOR > 0.0
    assert RAIL_NORMAL_HOVER_FACTOR > 0.0
    assert build_stamp.OVERLAY_VERSION == "overlay-v3"


def test_coalesced_visual_polylines_do_not_add_vertex_connector_segments() -> None:
    base_polylines = (
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        ((1.0, 0.0, 0.0), (1.0, 1.0, 0.0)),
    )
    visual_polylines = (
        ((0.0, 0.0, 0.1), (1.0, 0.0, 0.1)),
        ((1.0, 0.1, 0.0), (1.0, 1.1, 0.0)),
    )

    coalesced = coalesce_polylines(visual_polylines, base_polylines=base_polylines)

    assert len(coalesced) == 1
    assert len(coalesced[0]) == 3
    assert coalesced[0][1] == (1.0, 0.05, 0.05)


def test_beveled_corner_has_horizontal_spine_and_vertical_ribs() -> None:
    payload = _payload(make_beveled_wall_corner_source)
    assert _has_no_hidden_fields(payload)
    assert payload["counts"]["unoffset_polyline_count"] == 0

    horizontal_rails = [
        rail
        for rail in payload["rails"]
        if _has_member_fragments(rail, ("f_wall_a:0:0:2", "f_chamfer:0:0:0", "f_wall_b:0:0:0"))
    ]
    assert len(horizontal_rails) == 1
    assert horizontal_rails[0]["length"] > 1.9
    assert _has_patch_fragments(horizontal_rails[0], ("f_wall_a", "f_chamfer", "f_wall_b"))

    spines = _rails(payload, "SPINE")
    assert len(spines) == 1
    spine = spines[0]
    assert spine["length"] > 1.9
    assert _has_patch_fragments(spine, ("f_wall_a", "f_chamfer", "f_wall_b"))

    parallel_rails = _rails(payload, "PARALLEL")
    assert len(parallel_rails) == 2
    assert all(rail["length"] > 0.9 for rail in parallel_rails)

    seam_ribs = [
        rail
        for rail in _rails(payload, "RIB")
        if _has_patch_fragments(rail, ("f_wall_a", "f_chamfer"))
        or _has_patch_fragments(rail, ("f_chamfer", "f_wall_b"))
    ]
    assert len(seam_ribs) >= 2


def test_two_seam_tube_has_top_and_bottom_ring_rails() -> None:
    payload = _payload(make_cylinder_tube_without_caps_with_two_seams_source)
    assert _has_no_hidden_fields(payload)
    assert payload["counts"]["unoffset_polyline_count"] == 0

    ring_rails = [
        rail
        for rail in payload["rails"]
        if rail["role"] in {"SPINE", "PARALLEL"} and rail["length"] > 5.0
    ]
    assert len(ring_rails) == 2
    assert {rail["role"] for rail in ring_rails} == {"SPINE", "PARALLEL"}
    assert all(_has_patch_fragments(rail, ("f0", "f2")) for rail in ring_rails)
    assert all(len(rail["segment_polylines"]) == 1 for rail in ring_rails)
    assert all(len(rail["segment_polylines"][0]) > len(rail["directional_evidence_ids"]) for rail in ring_rails)
    _assert_records_have_normal_hover(ring_rails)


def test_snapshot_capture_records_empty_selection_fallback(tmp_path) -> None:
    source = load_source_snapshot("scaffold_core/tests/data/artist_cyl32.json")
    path = dump_source_snapshot(source, tmp_path / "snapshot.json")
    payload = json.loads(path.read_text())

    assert payload["selected_face_ids"] == []
    assert payload["selection_fallback_used"] is True
    assert "empty selected_face_ids" in payload["selection_fallback_reason"]


def test_artist_cyl32_overlay_semantics_v3() -> None:
    context, payload = _context_payload(load_source_snapshot("scaffold_core/tests/data/artist_cyl32.json"))
    relations = context.relation_snapshot
    assert _has_no_hidden_fields(payload)
    assert payload["counts"]["family_run_segment_count"] == len(relations.patch_chain_directional_evidence)
    assert payload["counts"]["junction_glyph_count"] == (
        len(relations.scaffold_nodes) + len(relations.run_endpoint_junctions)
    )

    ring_rails = [
        rail
        for rail in payload["rails"]
        if rail["role"] in {"SPINE", "PARALLEL"}
        and rail["length"] > 6.0
        and _has_patch_fragments(rail, ("f0", "f6"))
    ]
    assert len(ring_rails) == 2
    # I5 deterministic curved-run policy: f0 rim arcs split per segment
    # like f6 (8 + 24 run atoms per ring, was 1 + 24); each atom is a
    # polyline of the closed inter-patch ring rail; contiguous atoms
    # coalesce into one closed polyline for drawing.
    assert all(len(rail["directional_evidence_ids"]) == 32 for rail in ring_rails)
    assert all(rail.get("is_closed") for rail in ring_rails)
    assert all(len(rail["segment_polylines"]) == 1 for rail in ring_rails)
    assert any(segment["patch_id"] == "patch:seed:f30" for segment in payload["family_run_segments"])
    assert any(segment["patch_id"] == "patch:seed:f33" for segment in payload["family_run_segments"])
    assert all("related_rail_ids" in rail for rail in payload["rails"])
    assert payload["counts"]["dual_membership_rib_count"] >= 1
    assert any(
        rail["role"] == "RIB" and len(rail["related_rail_ids"]) >= 2
        for rail in payload["rails"]
    )


def test_tube_with_cap_side_rims_win_over_cap_perimeter_view() -> None:
    payload = _payload(make_tube_with_cap_source)

    side_rims = [
        rail
        for rail in payload["rails"]
        if rail["role"] in {"SPINE", "PARALLEL"}
        and _has_patch_fragments(rail, ("f0",))
        and len(rail["directional_evidence_ids"]) == 4
    ]
    assert len(side_rims) == 2
    assert all(rail["length"] > 5.0 for rail in side_rims)
    assert all(len(rail["segment_polylines"]) == 1 for rail in side_rims)
    assert all(len(rail["segment_polylines"][0]) > len(rail["directional_evidence_ids"]) for rail in side_rims)
    _assert_records_have_normal_hover(side_rims)

    cap_perimeter = [
        rail
        for rail in payload["rails"]
        if _has_patch_fragments(rail, ("f_cap",))
    ]
    assert len(cap_perimeter) == 4
    assert all(len(rail["directional_evidence_ids"]) == 1 for rail in cap_perimeter)
    assert {rail["role"] for rail in cap_perimeter} == {"RIB"}
    assert _has_no_hidden_fields(payload)
    assert payload["counts"]["cut_rail_count"] == 2
    assert payload["counts"]["rail_polyline_count"] == 8
    assert payload["counts"]["unoffset_polyline_count"] == 0
    _assert_cut_lines_are_oppositely_offset(payload)


def test_extruded_cross_side_band_rims_are_geodesic_rails_and_seam_is_cut() -> None:
    payload = _payload(make_extruded_cross_source)

    long_rails = [
        rail
        for rail in payload["rails"]
        if rail["role"] in {"SPINE", "PARALLEL"}
        and len(rail["directional_evidence_ids"]) == 12
        and rail["length"] > 20.0
    ]
    assert len(long_rails) == 2
    assert {rail["role"] for rail in long_rails} == {"SPINE", "PARALLEL"}
    assert len({tuple(rail["color"]) for rail in long_rails}) == 2
    assert all(len(rail["segment_polylines"]) == 1 for rail in long_rails)
    assert all(len(rail["segment_polylines"][0]) > len(rail["directional_evidence_ids"]) for rail in long_rails)
    _assert_records_have_normal_hover(long_rails)

    cap_perimeters = [
        rail
        for rail in payload["rails"]
        if _has_patch_fragments(rail, ("f_cap_top",)) or _has_patch_fragments(rail, ("f_cap_bottom",))
    ]
    assert len(cap_perimeters) == 24
    assert all(len(rail["directional_evidence_ids"]) == 1 for rail in cap_perimeters)
    assert {rail["role"] for rail in cap_perimeters} == {"RIB"}
    assert len({tuple(rail["color"]) for rail in cap_perimeters}) == 24
    assert _has_no_hidden_fields(payload)
    assert payload["counts"]["rail_polyline_count"] == 28
    assert payload["counts"]["unoffset_polyline_count"] == 0
    assert payload["counts"]["cut_rail_count"] >= 1
    assert any(verdict["status"] == "CUT" for verdict in payload["seam_verdicts"])
    _assert_cut_lines_are_oppositely_offset(payload)


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


def _has_no_hidden_fields(payload) -> bool:
    if any("hidden" in key for key in payload["counts"]):
        return False
    return all("is_default_visible" not in rail for rail in payload["rails"])


def _assert_cut_lines_are_oppositely_offset(payload) -> None:
    cut_records = [
        record
        for rail in payload["rails"]
        if rail["role"] == "CUT"
        for record in rail["segment_offset_records"]
    ]
    assert len(cut_records) == 2
    assert all(not record["unoffset"] for record in cut_records)
    assert all(record["offset_magnitude"] > 0.0 for record in cut_records)
    assert cut_records[0]["parent_chain_id"] == cut_records[1]["parent_chain_id"]
    first = cut_records[0]["offset_direction"]
    second = cut_records[1]["offset_direction"]
    assert _dot(first, second) < -0.99


def _assert_records_have_normal_hover(rails) -> None:
    records = [
        record
        for rail in rails
        for record in rail["segment_offset_records"]
    ]
    assert records
    assert all(record["normal_hover_magnitude"] > 0.0 for record in records)


def _dot(first, second) -> float:
    return sum(float(first[index]) * float(second[index]) for index in range(3))
