"""Tests for the ScaffoldGraph debug continuity pair-check formatter."""

from __future__ import annotations

from dev.tools.scaffold_graph_debug.pair_checks import format_continuity_pair_check


def test_cube_pair_check_report_uses_component_membership() -> None:
    overlay = {
        "scaffold_edge_count": 12,
        "scaffold_continuity_component_count": 9,
        "edges": [
            _edge("e_p0c0", "P0C0", "cc_p0c0"),
            _edge("e_p0c1", "P0C1", "cc_p0c1"),
            _edge("e_p1c0", "P1C0", "cc_p1c0"),
            _edge("e_p1c1", "P1C1", "cc_top_a"),
            _edge("e_p1c2", "P1C2", "cc_top_b"),
            _edge("e_p1c3", "P1C3", "cc_top_c"),
            _edge("e_p2c0", "P2C0", "cc_top_a"),
            _edge("e_p2c1", "P2C1", "cc_p2c1"),
            _edge("e_p2c2", "P2C2", "cc_top_c"),
            _edge("e_p2c3", "P2C3", "cc_top_b"),
        ],
        "continuity_components": [
            _component("cc_top_a", "e_p1c1", "e_p2c0"),
            _component("cc_top_b", "e_p1c2", "e_p2c3"),
            _component("cc_top_c", "e_p1c3", "e_p2c2"),
            _component("cc_p0c0", "e_p0c0"),
            _component("cc_p0c1", "e_p0c1"),
            _component("cc_p1c0", "e_p1c0"),
            _component("cc_p2c1", "e_p2c1"),
        ],
    }

    report = format_continuity_pair_check("cube_1hole_2seams_tube", overlay)

    assert "CONTINUITY PAIR CHECK" in report
    assert "object: cube_1hole_2seams_tube" in report
    assert "scaffold_edges: 12" in report
    assert "continuity_components: 9" in report
    assert "COMPONENTS\ncc_top_a: P1C1, P2C0" in report
    assert "FALSE MERGE CHECKS (expected false)" in report
    assert "P0C1 / P1C1: false component=cc_p0c1/cc_top_a" in report
    assert "P1C2 / P1C3: false component=cc_top_b/cc_top_c" in report
    assert "EXPECTED CONNECTED (expected true)" in report
    assert "P1C1 / P2C0: true component=cc_top_a/cc_top_a" in report
    assert "P1C3 / P2C2: true component=cc_top_c/cc_top_c" in report
    assert "P1C2 / P2C3: true component=cc_top_b/cc_top_b" in report
    assert "STILL UNRESOLVED (expected false)" in report
    assert "P1C0 / P2C1: false component=cc_p1c0/cc_p2c1" in report
    assert "RESULT" in report
    assert "false_merge_checks_passed: true" in report
    assert "expected_connected_passed: true" in report
    assert "unresolved_check_passed: true" in report


def test_pair_check_report_marks_missing_expected_labels() -> None:
    overlay = {
        "edges": [_edge("e_p1c1", "P1C1", "cc_top_a")],
        "continuity_components": [_component("cc_top_a", "e_p1c1")],
    }

    report = format_continuity_pair_check("cube_1hole_2seams_tube", overlay)

    assert "P0C1 / P1C1: MISSING_LABEL component=MISSING_LABEL/cc_top_a" in report
    assert "P1C1 / P2C0: MISSING_LABEL component=cc_top_a/MISSING_LABEL" in report
    assert "false_merge_checks_passed: false" in report
    assert "expected_connected_passed: false" in report


def test_cylinder_pair_check_report_does_not_guess_pairs() -> None:
    overlay = {
        "edges": [_edge("e_p0c0", "P0C0", "cc_0")],
        "continuity_components": [_component("cc_0", "e_p0c0")],
    }

    report = format_continuity_pair_check("cylinder_1cap_all_seams", overlay)

    assert "COMPONENTS\ncc_0: P0C0" in report
    assert "pair expectations unavailable for this object; labels need mapping" in report
    assert "FALSE MERGE CHECKS (expected false)" not in report


def _edge(edge_id: str, label: str, component_id: str) -> dict[str, str]:
    return {
        "id": edge_id,
        "display_label": label,
        "continuity_component_id": component_id,
    }


def _component(component_id: str, *edge_ids: str) -> dict[str, object]:
    return {
        "id": component_id,
        "scaffold_edge_ids": list(edge_ids),
    }
