"""
Layer: tests

Rules:
- Pipeline ScaffoldGraph overlay tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

import json
import re

from scaffold_core.pipeline.inspection import inspect_pipeline_context
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
from scaffold_core.tests.fixtures.closed_shared_loop import make_closed_shared_boundary_loop_source
from scaffold_core.tests.fixtures.cylinder_tube import (
    make_segmented_cylinder_tube_without_caps_with_one_seam_source,
)
from scaffold_core.tests.fixtures.l_shape import make_two_patch_source_with_two_edge_seam_run
from scaffold_core.tests.fixtures.single_patch import make_single_quad_source


def _compact_graph_report(source_factory) -> dict[str, int]:
    context = run_pass_1_relations(run_pass_0(source_factory()))
    compact_report = inspect_pipeline_context(context, detail="compact")
    full_report = inspect_pipeline_context(context, detail="full")
    relations = compact_report["relations"]
    overlay = full_report["scaffold_graph_overlay"]
    assert all(edge["polyline"] for edge in overlay["edges"])
    assert all(len(node["position"]) == 3 for node in overlay["nodes"])
    assert all(len(junction["position"]) == 3 for junction in overlay["junctions"])
    assert all(len(relation["position"]) == 3 for relation in overlay["incident_relations"])
    assert all(len(relation["label_position"]) == 3 for relation in overlay["shared_chain_relations"])
    return {
        "scaffold_node_count": relations["scaffold_node_count"],
        "scaffold_edge_count": relations["scaffold_edge_count"],
        "scaffold_junction_count": relations["scaffold_junction_count"],
        "scaffold_node_incident_edge_relation_count": relations[
            "scaffold_node_incident_edge_relation_count"
        ],
        "shared_chain_patch_chain_relation_count": relations[
            "shared_chain_patch_chain_relation_count"
        ],
        "scaffold_continuity_component_count": relations[
            "scaffold_continuity_component_count"
        ],
        "overlay_node_count": overlay["scaffold_node_count"],
        "overlay_edge_count": overlay["scaffold_edge_count"],
        "overlay_junction_count": overlay["scaffold_junction_count"],
        "overlay_continuity_component_count": overlay["scaffold_continuity_component_count"],
        "overlay_incident_relation_count": overlay["scaffold_node_incident_edge_relation_count"],
        "overlay_shared_chain_relation_count": overlay["shared_chain_patch_chain_relation_count"],
        "edge_stroke_count": len(overlay["edges"]),
        "node_marker_count": len(overlay["nodes"]),
        "junction_marker_count": len(overlay["junctions"]),
        "incident_relation_marker_count": overlay["incident_relation_marker_count"],
        "shared_chain_relation_marker_count": overlay["shared_chain_relation_marker_count"],
    }


def _polyline_midpoint_for_assertion(polyline: list[list[float]]) -> list[float]:
    middle_index = len(polyline) // 2
    if len(polyline) % 2 == 1:
        return list(polyline[middle_index])
    return [
        (float(polyline[middle_index - 1][index]) + float(polyline[middle_index][index])) / 2.0
        for index in range(3)
    ]


def _average_positions_for_assertion(first_position: list[float], second_position: list[float]) -> list[float]:
    return [
        (float(first_position[index]) + float(second_position[index])) / 2.0
        for index in range(3)
    ]


def test_scaffold_graph_overlay_has_required_debug_payload_shape() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_two_patch_source_with_two_edge_seam_run())
    )

    report = inspect_pipeline_context(context, detail="full")

    json.dumps(report)
    overlay = report["scaffold_graph_overlay"]
    assert overlay["scaffold_node_count"] == len(overlay["nodes"])
    assert overlay["scaffold_edge_count"] == len(overlay["edges"])
    assert set(overlay) == {
        "scaffold_node_count",
        "scaffold_edge_count",
        "scaffold_junction_count",
        "scaffold_node_incident_edge_relation_count",
        "shared_chain_patch_chain_relation_count",
        "scaffold_continuity_component_count",
        "nodes",
        "edges",
        "continuity_components",
        "junctions",
        "incident_relations",
        "shared_chain_relations",
        "incident_relation_marker_count",
        "shared_chain_relation_marker_count",
        "graph",
    }
    assert set(overlay["nodes"][0]) == {
        "id",
        "display_label",
        "source_vertex_ids",
        "vertex_ids",
        "position",
        "confidence",
    }
    assert set(overlay["edges"][0]) == {
        "id",
        "display_label",
        "patch_chain_id",
        "chain_id",
        "start_scaffold_node_id",
        "end_scaffold_node_id",
        "polyline",
        "continuity_component_id",
        "color_key",
        "continuity_color",
        "confidence",
        "edge_source",
    }
    assert set(overlay["continuity_components"][0]) == {
        "id",
        "color_key",
        "continuity_color",
        "scaffold_edge_ids",
        "scaffold_node_ids",
        "propagating_incident_relation_ids",
        "ambiguous_incident_relation_ids",
        "blocked_incident_relation_ids",
        "degraded_incident_relation_ids",
        "warning_relation_ids",
        "warning_count",
        "is_ambiguous",
        "confidence",
    }
    assert overlay["scaffold_junction_count"] == len(overlay["junctions"])
    assert overlay["scaffold_continuity_component_count"] == len(overlay["continuity_components"])
    assert overlay["scaffold_node_incident_edge_relation_count"] == len(overlay["incident_relations"])
    assert overlay["shared_chain_patch_chain_relation_count"] == len(overlay["shared_chain_relations"])
    assert overlay["incident_relation_marker_count"] == len(overlay["incident_relations"])
    assert overlay["shared_chain_relation_marker_count"] == len(overlay["shared_chain_relations"])
    assert len(overlay["junctions"]) == 2
    assert {junction["kind"] for junction in overlay["junctions"]} == {"CROSS_PATCH"}
    assert all(len(junction["position"]) == 3 for junction in overlay["junctions"])
    assert set(overlay["graph"]) == {"id", "node_ids", "edge_ids"}
    assert all(len(node["position"]) == 3 for node in overlay["nodes"])
    assert all(edge["polyline"] for edge in overlay["edges"])
    assert all(edge["edge_source"] == "FINAL_PATCH_CHAIN" for edge in overlay["edges"])
    assert set(overlay["incident_relations"][0]) == {
        "id",
        "kind",
        "scaffold_node_id",
        "first_scaffold_edge_id",
        "second_scaffold_edge_id",
        "first_continuity_component_id",
        "second_continuity_component_id",
        "first_patch_chain_id",
        "second_patch_chain_id",
        "first_endpoint_role",
        "second_endpoint_role",
        "first_endpoint_sample_id",
        "second_endpoint_sample_id",
        "endpoint_relation_id",
        "vertex_id",
        "direction_dot",
        "normal_dot",
        "confidence",
        "position",
        "evidence",
    }
    assert set(overlay["shared_chain_relations"][0]) == {
        "id",
        "kind",
        "chain_id",
        "first_scaffold_edge_id",
        "second_scaffold_edge_id",
        "first_patch_chain_id",
        "second_patch_chain_id",
        "patch_ids",
        "confidence",
        "label_position",
        "midpoint",
        "evidence",
    }


def test_scaffold_graph_overlay_display_labels_are_compact_and_deterministic() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_segmented_cylinder_tube_without_caps_with_one_seam_source())
    )

    first_report = inspect_pipeline_context(context, detail="full")
    second_report = inspect_pipeline_context(context, detail="full")
    first_overlay = first_report["scaffold_graph_overlay"]
    second_overlay = second_report["scaffold_graph_overlay"]

    edge_labels = [edge["display_label"] for edge in first_overlay["edges"]]
    node_labels = [node["display_label"] for node in first_overlay["nodes"]]
    all_labels = edge_labels + node_labels

    assert edge_labels == [edge["display_label"] for edge in second_overlay["edges"]]
    assert node_labels == [node["display_label"] for node in second_overlay["nodes"]]
    assert all(re.fullmatch(r"P\d+C\d+", label) for label in edge_labels)
    assert all(re.fullmatch(r"N\d+( P\d+C\d+(?:/P\d+C\d+)*)?", label) for label in node_labels)
    assert not any(
        raw in label
        for label in all_labels
        for raw in ("scaffold_edge", "scaffold_node", "patch_chain", "patch:seed")
    )


def test_scaffold_graph_overlay_uses_existing_graph_records() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_segmented_cylinder_tube_without_caps_with_one_seam_source())
    )

    snapshot = context.relation_snapshot
    report = inspect_pipeline_context(context, detail="full")

    assert snapshot is not None
    overlay = report["scaffold_graph_overlay"]
    assert overlay["scaffold_node_count"] == len(snapshot.scaffold_nodes)
    assert overlay["scaffold_edge_count"] == len(snapshot.scaffold_edges)
    assert overlay["scaffold_junction_count"] == len(snapshot.scaffold_junctions)
    assert overlay["scaffold_node_incident_edge_relation_count"] == len(
        snapshot.scaffold_node_incident_edge_relations
    )
    assert overlay["shared_chain_patch_chain_relation_count"] == len(
        snapshot.shared_chain_patch_chain_relations
    )
    assert overlay["scaffold_continuity_component_count"] == len(
        snapshot.scaffold_continuity_components
    )
    assert overlay["graph"]["id"] == snapshot.scaffold_graph.id
    assert overlay["graph"]["node_ids"] == [node.id for node in snapshot.scaffold_nodes]
    assert overlay["graph"]["edge_ids"] == [edge.id for edge in snapshot.scaffold_edges]
    assert {
        edge["patch_chain_id"]
        for edge in overlay["edges"]
    } == {
        str(edge.patch_chain_id)
        for edge in snapshot.scaffold_edges
    }
    assert {
        relation["id"]
        for relation in overlay["incident_relations"]
    } == {
        relation.id
        for relation in snapshot.scaffold_node_incident_edge_relations
    }
    assert {
        relation["id"]
        for relation in overlay["shared_chain_relations"]
    } == {
        relation.id
        for relation in snapshot.shared_chain_patch_chain_relations
    }


def test_scaffold_graph_overlay_relation_records_reference_renderable_graph_payload() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_two_patch_source_with_two_edge_seam_run())
    )

    report = inspect_pipeline_context(context, detail="full")

    json.dumps(report)
    overlay = report["scaffold_graph_overlay"]
    node_ids = {node["id"] for node in overlay["nodes"]}
    edge_ids = {edge["id"] for edge in overlay["edges"]}
    component_ids = {component["id"] for component in overlay["continuity_components"]}
    patch_chain_ids = {edge["patch_chain_id"] for edge in overlay["edges"]}
    edge_polylines = {
        edge["id"]: edge["polyline"]
        for edge in overlay["edges"]
    }
    node_positions = {
        node["id"]: node["position"]
        for node in overlay["nodes"]
    }

    assert overlay["incident_relations"]
    assert overlay["shared_chain_relations"]
    assert all(
        relation["scaffold_node_id"] in node_ids
        and relation["first_scaffold_edge_id"] in edge_ids
        and relation["second_scaffold_edge_id"] in edge_ids
        and relation["first_continuity_component_id"] in component_ids
        and relation["second_continuity_component_id"] in component_ids
        and relation["first_patch_chain_id"] in patch_chain_ids
        and relation["second_patch_chain_id"] in patch_chain_ids
        and relation["position"] == node_positions[relation["scaffold_node_id"]]
        and relation["vertex_id"]
        and relation["evidence"]
        for relation in overlay["incident_relations"]
    )
    assert all(
        relation["first_scaffold_edge_id"] in edge_ids
        and relation["second_scaffold_edge_id"] in edge_ids
        and relation["first_patch_chain_id"] in patch_chain_ids
        and relation["second_patch_chain_id"] in patch_chain_ids
        and len(relation["patch_ids"]) == 2
        and len(relation["label_position"]) == 3
        and len(relation["midpoint"]) == 3
        and relation["evidence"]
        for relation in overlay["shared_chain_relations"]
    )
    for relation in overlay["shared_chain_relations"]:
        expected_label_position = _average_positions_for_assertion(
            _polyline_midpoint_for_assertion(edge_polylines[relation["first_scaffold_edge_id"]]),
            _polyline_midpoint_for_assertion(edge_polylines[relation["second_scaffold_edge_id"]]),
        )
        assert relation["label_position"] == expected_label_position


def test_scaffold_graph_overlay_exposes_self_seam_junction_markers_for_cylinder() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_segmented_cylinder_tube_without_caps_with_one_seam_source())
    )

    report = inspect_pipeline_context(context, detail="full")

    json.dumps(report)
    overlay = report["scaffold_graph_overlay"]
    node_ids = {node["id"] for node in overlay["nodes"]}
    node_positions = {
        node["id"]: node["position"]
        for node in overlay["nodes"]
    }
    assert overlay["scaffold_node_count"] == 2
    assert overlay["scaffold_edge_count"] == 4
    assert overlay["scaffold_continuity_component_count"] == 4
    assert overlay["scaffold_junction_count"] == 2
    assert len(overlay["junctions"]) == 2
    assert {junction["kind"] for junction in overlay["junctions"]} == {"SELF_SEAM"}
    assert all(junction["scaffold_node_id"] in node_ids for junction in overlay["junctions"])
    assert all(
        junction["position"] == node_positions[junction["scaffold_node_id"]]
        for junction in overlay["junctions"]
    )
    assert all(len(junction["position"]) == 3 for junction in overlay["junctions"])
    assert all(junction["evidence"] for junction in overlay["junctions"])
    assert set(overlay["junctions"][0]) == {
        "id",
        "scaffold_node_id",
        "kind",
        "position",
        "confidence",
        "evidence",
    }


def test_scaffold_graph_overlay_exposes_cross_patch_junction_markers() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_two_patch_source_with_two_edge_seam_run())
    )

    report = inspect_pipeline_context(context, detail="full")

    json.dumps(report)
    overlay = report["scaffold_graph_overlay"]
    node_ids = {node["id"] for node in overlay["nodes"]}
    node_positions = {
        node["id"]: node["position"]
        for node in overlay["nodes"]
    }
    assert overlay["scaffold_node_count"] == 2
    assert overlay["scaffold_edge_count"] == 4
    assert overlay["scaffold_junction_count"] == 2
    assert len(overlay["junctions"]) == 2
    assert {junction["kind"] for junction in overlay["junctions"]} == {"CROSS_PATCH"}
    assert all(junction["scaffold_node_id"] in node_ids for junction in overlay["junctions"])
    assert all(
        junction["position"] == node_positions[junction["scaffold_node_id"]]
        for junction in overlay["junctions"]
    )
    assert all(junction["evidence"] for junction in overlay["junctions"])


def test_scaffold_graph_overlay_node_anchor_groups_materialized_vertices() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_segmented_cylinder_tube_without_caps_with_one_seam_source())
    )

    report = inspect_pipeline_context(context, detail="full")
    overlay = report["scaffold_graph_overlay"]

    top_node = next(
        node
        for node in overlay["nodes"]
        if node["source_vertex_ids"] == ["v_a_t"]
    )
    bottom_node = next(
        node
        for node in overlay["nodes"]
        if node["source_vertex_ids"] == ["v_a_b"]
    )
    assert len(top_node["vertex_ids"]) == 2
    assert len(bottom_node["vertex_ids"]) == 2
    assert top_node["position"] == [1.0, 0.0, 2.0]
    assert bottom_node["position"] == [1.0, 0.0, 0.0]


def test_scaffold_graph_overlay_polyline_follows_patch_chain_orientation() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_closed_shared_boundary_loop_source())
    )

    report = inspect_pipeline_context(context, detail="full")
    overlay = report["scaffold_graph_overlay"]

    assert len(overlay["edges"]) == 2
    first_polyline = overlay["edges"][0]["polyline"]
    second_polyline = overlay["edges"][1]["polyline"]
    assert first_polyline == list(reversed(second_polyline))


def test_scaffold_graph_overlay_compact_report_expectations_for_single_patch() -> None:
    assert _compact_graph_report(make_single_quad_source) == {
        "scaffold_node_count": 1,
        "scaffold_edge_count": 1,
        "scaffold_junction_count": 0,
        "scaffold_node_incident_edge_relation_count": 1,
        "shared_chain_patch_chain_relation_count": 0,
        "scaffold_continuity_component_count": 1,
        "overlay_node_count": 1,
        "overlay_edge_count": 1,
        "overlay_junction_count": 0,
        "overlay_continuity_component_count": 1,
        "overlay_incident_relation_count": 1,
        "overlay_shared_chain_relation_count": 0,
        "edge_stroke_count": 1,
        "node_marker_count": 1,
        "junction_marker_count": 0,
        "incident_relation_marker_count": 1,
        "shared_chain_relation_marker_count": 0,
    }


def test_scaffold_graph_overlay_compact_report_expectations_for_cylinder() -> None:
    assert _compact_graph_report(
        make_segmented_cylinder_tube_without_caps_with_one_seam_source
    ) == {
        "scaffold_node_count": 2,
        "scaffold_edge_count": 4,
        "scaffold_junction_count": 2,
        "scaffold_node_incident_edge_relation_count": 12,
        "shared_chain_patch_chain_relation_count": 0,
        "scaffold_continuity_component_count": 4,
        "overlay_node_count": 2,
        "overlay_edge_count": 4,
        "overlay_junction_count": 2,
        "overlay_continuity_component_count": 4,
        "overlay_incident_relation_count": 12,
        "overlay_shared_chain_relation_count": 0,
        "edge_stroke_count": 4,
        "node_marker_count": 2,
        "junction_marker_count": 2,
        "incident_relation_marker_count": 12,
        "shared_chain_relation_marker_count": 0,
    }


def test_scaffold_graph_overlay_compact_report_expectations_for_closed_shared_loop() -> None:
    assert _compact_graph_report(make_closed_shared_boundary_loop_source) == {
        "scaffold_node_count": 2,
        "scaffold_edge_count": 2,
        "scaffold_junction_count": 2,
        "scaffold_node_incident_edge_relation_count": 2,
        "shared_chain_patch_chain_relation_count": 1,
        "scaffold_continuity_component_count": 2,
        "overlay_node_count": 2,
        "overlay_edge_count": 2,
        "overlay_junction_count": 2,
        "overlay_continuity_component_count": 2,
        "overlay_incident_relation_count": 2,
        "overlay_shared_chain_relation_count": 1,
        "edge_stroke_count": 2,
        "node_marker_count": 2,
        "junction_marker_count": 2,
        "incident_relation_marker_count": 2,
        "shared_chain_relation_marker_count": 1,
    }


def test_scaffold_graph_overlay_report_edges_are_final_patch_chains() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_segmented_cylinder_tube_without_caps_with_one_seam_source())
    )

    report = inspect_pipeline_context(context, detail="full")
    overlay = report["scaffold_graph_overlay"]

    assert overlay["scaffold_node_count"] != len(context.source_snapshot.vertices)
    assert overlay["scaffold_edge_count"] == len(context.topology_snapshot.patch_chains)
    assert all(edge["edge_source"] == "FINAL_PATCH_CHAIN" for edge in overlay["edges"])
    assert all(edge["continuity_component_id"] for edge in overlay["edges"])
    assert all(edge["color_key"].startswith("continuity:") for edge in overlay["edges"])
    assert all(len(edge["continuity_color"]) == 4 for edge in overlay["edges"])


def test_scaffold_graph_overlay_continuity_colors_are_deterministic() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_two_patch_source_with_two_edge_seam_run())
    )

    first_overlay = inspect_pipeline_context(context, detail="full")["scaffold_graph_overlay"]
    second_overlay = inspect_pipeline_context(context, detail="full")["scaffold_graph_overlay"]

    first_components = {
        component["id"]: (component["color_key"], component["continuity_color"])
        for component in first_overlay["continuity_components"]
    }
    second_components = {
        component["id"]: (component["color_key"], component["continuity_color"])
        for component in second_overlay["continuity_components"]
    }
    first_edges = {
        edge["id"]: (
            edge["continuity_component_id"],
            edge["color_key"],
            edge["continuity_color"],
        )
        for edge in first_overlay["edges"]
    }
    second_edges = {
        edge["id"]: (
            edge["continuity_component_id"],
            edge["color_key"],
            edge["continuity_color"],
        )
        for edge in second_overlay["edges"]
    }

    assert first_components == second_components
    assert first_edges == second_edges


def test_scaffold_graph_overlay_continuity_edge_colors_do_not_use_relation_kind() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_two_patch_source_with_two_edge_seam_run())
    )

    overlay = inspect_pipeline_context(context, detail="full")["scaffold_graph_overlay"]
    relation_kinds = {relation["kind"] for relation in overlay["incident_relations"]}
    colors_by_component = {
        component["id"]: component["continuity_color"]
        for component in overlay["continuity_components"]
    }

    assert relation_kinds
    assert not any(edge["color_key"] in relation_kinds for edge in overlay["edges"])
    assert all(
        edge["continuity_color"] == colors_by_component[edge["continuity_component_id"]]
        for edge in overlay["edges"]
    )
