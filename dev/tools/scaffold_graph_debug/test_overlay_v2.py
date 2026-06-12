"""Headless checks for ScaffoldGraph overlay v2 pure assembly."""

from __future__ import annotations

import importlib

from dev.tools.scaffold_graph_debug.overlay_v2 import build_overlay_v2_payload
from dev.tools.scaffold_graph_debug.seam_verdicts import ANGLE_DEFECT_TOLERANCE
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
