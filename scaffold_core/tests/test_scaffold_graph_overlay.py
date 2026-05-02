"""
Layer: tests

Rules:
- Pipeline ScaffoldGraph overlay tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

import json

from scaffold_core.pipeline.inspection import inspect_pipeline_context
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
from scaffold_core.tests.fixtures.closed_shared_loop import make_closed_shared_boundary_loop_source
from scaffold_core.tests.fixtures.cylinder_tube import (
    make_segmented_cylinder_tube_without_caps_with_one_seam_source,
)
from scaffold_core.tests.fixtures.l_shape import make_two_patch_source_with_two_edge_seam_run


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
        "nodes",
        "edges",
        "graph",
    }
    assert set(overlay["nodes"][0]) == {
        "id",
        "source_vertex_ids",
        "vertex_ids",
        "position",
        "confidence",
    }
    assert set(overlay["edges"][0]) == {
        "id",
        "patch_chain_id",
        "chain_id",
        "start_scaffold_node_id",
        "end_scaffold_node_id",
        "polyline",
        "confidence",
        "edge_source",
    }
    assert set(overlay["graph"]) == {"id", "node_ids", "edge_ids"}
    assert all(len(node["position"]) == 3 for node in overlay["nodes"])
    assert all(edge["polyline"] for edge in overlay["edges"])
    assert all(edge["edge_source"] == "FINAL_PATCH_CHAIN" for edge in overlay["edges"])


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
