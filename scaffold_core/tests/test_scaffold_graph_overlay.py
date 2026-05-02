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
    return {
        "scaffold_node_count": relations["scaffold_node_count"],
        "scaffold_edge_count": relations["scaffold_edge_count"],
        "scaffold_junction_count": relations["scaffold_junction_count"],
        "overlay_node_count": overlay["scaffold_node_count"],
        "overlay_edge_count": overlay["scaffold_edge_count"],
        "overlay_junction_count": overlay["scaffold_junction_count"],
        "edge_stroke_count": len(overlay["edges"]),
        "node_marker_count": len(overlay["nodes"]),
        "junction_marker_count": len(overlay["junctions"]),
    }


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
        "nodes",
        "edges",
        "junctions",
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
        "confidence",
        "edge_source",
    }
    assert overlay["scaffold_junction_count"] == len(overlay["junctions"])
    assert len(overlay["junctions"]) == 2
    assert {junction["kind"] for junction in overlay["junctions"]} == {"CROSS_PATCH"}
    assert all(len(junction["position"]) == 3 for junction in overlay["junctions"])
    assert set(overlay["graph"]) == {"id", "node_ids", "edge_ids"}
    assert all(len(node["position"]) == 3 for node in overlay["nodes"])
    assert all(edge["polyline"] for edge in overlay["edges"])
    assert all(edge["edge_source"] == "FINAL_PATCH_CHAIN" for edge in overlay["edges"])


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
        "overlay_node_count": 1,
        "overlay_edge_count": 1,
        "overlay_junction_count": 0,
        "edge_stroke_count": 1,
        "node_marker_count": 1,
        "junction_marker_count": 0,
    }


def test_scaffold_graph_overlay_compact_report_expectations_for_cylinder() -> None:
    assert _compact_graph_report(
        make_segmented_cylinder_tube_without_caps_with_one_seam_source
    ) == {
        "scaffold_node_count": 2,
        "scaffold_edge_count": 4,
        "scaffold_junction_count": 2,
        "overlay_node_count": 2,
        "overlay_edge_count": 4,
        "overlay_junction_count": 2,
        "edge_stroke_count": 4,
        "node_marker_count": 2,
        "junction_marker_count": 2,
    }


def test_scaffold_graph_overlay_compact_report_expectations_for_closed_shared_loop() -> None:
    assert _compact_graph_report(make_closed_shared_boundary_loop_source) == {
        "scaffold_node_count": 2,
        "scaffold_edge_count": 2,
        "scaffold_junction_count": 2,
        "overlay_node_count": 2,
        "overlay_edge_count": 2,
        "overlay_junction_count": 2,
        "edge_stroke_count": 2,
        "node_marker_count": 2,
        "junction_marker_count": 2,
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
