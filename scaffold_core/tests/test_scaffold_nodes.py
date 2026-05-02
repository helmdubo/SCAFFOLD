"""
Layer: tests

Rules:
- Layer 3 ScaffoldNode tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from scaffold_core.layer_1_topology.build import build_topology_snapshot
from scaffold_core.layer_2_geometry.build import build_geometry_facts
from scaffold_core.layer_3_relations.build import build_relation_snapshot
from scaffold_core.layer_3_relations.scaffold_nodes import build_scaffold_nodes
from scaffold_core.pipeline.inspection import inspect_pipeline_context
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
from scaffold_core.tests.fixtures.closed_shared_loop import make_closed_shared_boundary_loop_source
from scaffold_core.tests.fixtures.cylinder_tube import (
    make_segmented_cylinder_tube_without_caps_with_one_seam_source,
)


ROOT = Path(__file__).resolve().parents[1]
SCAFFOLD_NODES_MODULE = ROOT / "layer_3_relations" / "scaffold_nodes.py"
FORBIDDEN_TOKENS = frozenset({
    "H_FRAME",
    "V_FRAME",
    "WALL",
    "FLOOR",
    "SLOPE",
    "WorldOrientation",
    "WORLD_UP",
    "ScaffoldJunction",
    "ScaffoldEdge",
    "ScaffoldTrace",
    "FeatureCandidate",
    "Runtime",
    "Solve",
    "UV",
})


def test_closed_shared_loop_builds_scaffold_nodes_from_endpoint_evidence() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_closed_shared_boundary_loop_source())
    )

    snapshot = context.relation_snapshot

    assert snapshot is not None
    assert len(snapshot.scaffold_nodes) == 2
    assert {
        tuple(str(source_vertex_id) for source_vertex_id in node.source_vertex_ids)
        for node in snapshot.scaffold_nodes
    } == {("v0",), ("v1",)}
    assert all(node.loop_corner_ids for node in snapshot.scaffold_nodes)
    assert all(node.patch_chain_endpoint_sample_ids for node in snapshot.scaffold_nodes)
    assert all(node.incident_patch_chain_ids for node in snapshot.scaffold_nodes)


def test_cylinder_scaffold_nodes_group_materialized_seam_vertices_by_source_vertex() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_segmented_cylinder_tube_without_caps_with_one_seam_source())
    )

    snapshot = context.relation_snapshot

    assert snapshot is not None
    assert len(context.topology_snapshot.patch_chains) == 4
    assert len(snapshot.loop_corners) == 4
    assert len(snapshot.scaffold_nodes) == 2
    node_source_ids = {
        tuple(str(source_vertex_id) for source_vertex_id in node.source_vertex_ids)
        for node in snapshot.scaffold_nodes
    }
    assert node_source_ids == {("v_a_t",), ("v_a_b",)}
    top_seam_node = _node_for_source(snapshot.scaffold_nodes, "v_a_t")
    bottom_seam_node = _node_for_source(snapshot.scaffold_nodes, "v_a_b")
    assert len(top_seam_node.vertex_ids) == 2
    assert len(bottom_seam_node.vertex_ids) == 2
    assert len(top_seam_node.loop_corner_ids) == 2
    assert len(bottom_seam_node.loop_corner_ids) == 2
    assert len(top_seam_node.incident_patch_chain_ids) == 3
    assert len(bottom_seam_node.incident_patch_chain_ids) == 3
    assert not {
        ("v_b_t",),
        ("v_b_b",),
        ("v_c_t",),
        ("v_c_b",),
        ("v_d_t",),
        ("v_d_b",),
    } & node_source_ids

    samples_by_id = {
        sample.id: sample
        for sample in snapshot.patch_chain_endpoint_samples
    }
    relations_by_id = {
        relation.id: relation
        for relation in snapshot.patch_chain_endpoint_relations
    }
    for node in snapshot.scaffold_nodes:
        node_vertex_ids = set(node.vertex_ids)
        assert all(
            samples_by_id[sample_id].vertex_id in node_vertex_ids
            for sample_id in node.patch_chain_endpoint_sample_ids
        )
        assert all(
            relations_by_id[relation_id].vertex_id in node_vertex_ids
            for relation_id in node.patch_chain_endpoint_relation_ids
        )


def test_scaffold_node_builder_does_not_change_layer_1_identity() -> None:
    source = make_closed_shared_boundary_loop_source()
    topology = build_topology_snapshot(source)
    geometry = build_geometry_facts(source, topology)
    snapshot = build_relation_snapshot(topology, geometry)
    original_chains = dict(topology.chains)
    original_patch_chains = dict(topology.patch_chains)
    original_vertices = dict(topology.vertices)

    build_scaffold_nodes(
        topology,
        snapshot.loop_corners,
        snapshot.patch_chain_endpoint_samples,
        snapshot.patch_chain_endpoint_relations,
    )

    assert dict(topology.chains) == original_chains
    assert dict(topology.patch_chains) == original_patch_chains
    assert dict(topology.vertices) == original_vertices


def test_inspection_json_includes_scaffold_nodes() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_segmented_cylinder_tube_without_caps_with_one_seam_source())
    )

    report = inspect_pipeline_context(context, detail="full")

    json.dumps(report)
    relations = report["relations"]
    assert relations["loop_corner_count"] == 4
    assert relations["scaffold_node_count"] == 2
    top_seam_node = next(
        node
        for node in relations["scaffold_nodes"]
        if node["source_vertex_ids"] == ["v_a_t"]
    )
    assert top_seam_node["id"] == "scaffold_node:source:v_a_t"
    assert len(top_seam_node["vertex_ids"]) == 2
    assert top_seam_node["loop_corner_ids"]
    assert top_seam_node["patch_chain_endpoint_sample_ids"]
    assert top_seam_node["patch_chain_endpoint_relation_ids"]


def test_scaffold_node_code_does_not_introduce_deferred_terms() -> None:
    tree = ast.parse(SCAFFOLD_NODES_MODULE.read_text(encoding="utf-8"))
    identifiers: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            identifiers.add(node.id)
        elif isinstance(node, ast.Attribute):
            identifiers.add(node.attr)
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            identifiers.add(node.name)
        elif isinstance(node, ast.arg):
            identifiers.add(node.arg)
        elif isinstance(node, ast.alias):
            identifiers.add(node.name.split(".")[-1])
            if node.asname:
                identifiers.add(node.asname)

    assert not identifiers & FORBIDDEN_TOKENS


def _node_for_source(nodes, source_vertex_id: str):
    return next(
        node
        for node in nodes
        if tuple(str(item) for item in node.source_vertex_ids) == (source_vertex_id,)
    )
