"""
Layer: tests

Rules:
- Layer 3 ScaffoldGraph tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from scaffold_core.layer_1_topology.build import build_topology_snapshot
from scaffold_core.layer_2_geometry.build import build_geometry_facts
from scaffold_core.layer_3_relations.build import build_relation_snapshot
from scaffold_core.layer_3_relations.model import ContinuationKind
from scaffold_core.layer_3_relations.scaffold_graph import build_scaffold_graph
from scaffold_core.pipeline.inspection import inspect_pipeline_context
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
from scaffold_core.tests.fixtures.closed_shared_loop import make_closed_shared_boundary_loop_source
from scaffold_core.tests.fixtures.cylinder_tube import (
    make_segmented_cylinder_tube_without_caps_with_one_seam_source,
)
from scaffold_core.tests.fixtures.l_shape import make_two_patch_source_with_two_edge_seam_run
from scaffold_core.tests.fixtures.non_manifold import make_three_quad_non_manifold_source


ROOT = Path(__file__).resolve().parents[1]
SCAFFOLD_GRAPH_MODULE = ROOT / "layer_3_relations" / "scaffold_graph.py"
FORBIDDEN_TOKENS = frozenset({
    "H_FRAME",
    "V_FRAME",
    "WALL",
    "FLOOR",
    "SLOPE",
    "WorldOrientation",
    "WORLD_UP",
    "ScaffoldJunction",
    "ScaffoldTrace",
    "ScaffoldCircuit",
    "ScaffoldRail",
    "FeatureCandidate",
    "Runtime",
    "Solve",
    "UV",
})
FORBIDDEN_IMPORTS = (
    "scaffold_core.layer_4_features",
    "scaffold_core.layer_5_runtime",
    "scaffold_core.api",
    "scaffold_core.ui",
    "scaffold_core.pipeline",
)


def test_cylinder_scaffold_edges_follow_final_patch_chains_and_node_grouping() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_segmented_cylinder_tube_without_caps_with_one_seam_source())
    )

    topology = context.topology_snapshot
    snapshot = context.relation_snapshot

    assert topology is not None
    assert snapshot is not None
    assert len(snapshot.scaffold_edges) == 4
    assert len(snapshot.scaffold_edges) == len(topology.patch_chains)
    assert {edge.patch_chain_id for edge in snapshot.scaffold_edges} == set(topology.patch_chains)
    node_ids = {node.id for node in snapshot.scaffold_nodes}
    assert all(edge.start_scaffold_node_id in node_ids for edge in snapshot.scaffold_edges)
    assert all(edge.end_scaffold_node_id in node_ids for edge in snapshot.scaffold_edges)
    assert all(edge.evidence[0].data["edge_source"] == "FINAL_PATCH_CHAIN" for edge in snapshot.scaffold_edges)
    assert _node_for_source(snapshot.scaffold_nodes, "v_a_t").id in _edge_endpoint_node_ids(snapshot.scaffold_edges)
    assert _node_for_source(snapshot.scaffold_nodes, "v_a_b").id in _edge_endpoint_node_ids(snapshot.scaffold_edges)


def test_closed_shared_loop_builds_graph_edge_per_patch_chain_occurrence() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_closed_shared_boundary_loop_source())
    )

    topology = context.topology_snapshot
    snapshot = context.relation_snapshot

    assert topology is not None
    assert snapshot is not None
    assert len(topology.chains) == 1
    assert len(topology.patch_chains) == 2
    assert len(snapshot.scaffold_edges) == 2
    assert {edge.patch_chain_id for edge in snapshot.scaffold_edges} == set(topology.patch_chains)
    assert len({edge.chain_id for edge in snapshot.scaffold_edges}) == 1


def test_simple_fixture_graph_counts_and_endpoint_nodes_resolve() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_two_patch_source_with_two_edge_seam_run())
    )

    topology = context.topology_snapshot
    snapshot = context.relation_snapshot

    assert topology is not None
    assert snapshot is not None
    assert snapshot.scaffold_graph is not None
    assert len(snapshot.scaffold_edges) == len(topology.patch_chains)
    assert snapshot.scaffold_graph.edge_ids == tuple(edge.id for edge in snapshot.scaffold_edges)
    assert snapshot.scaffold_graph.node_ids == tuple(node.id for node in snapshot.scaffold_nodes)
    node_ids = set(snapshot.scaffold_graph.node_ids)
    for edge in snapshot.scaffold_edges:
        assert edge.start_scaffold_node_id in node_ids
        assert edge.end_scaffold_node_id in node_ids


def test_degraded_non_manifold_graph_preserves_ambiguity_without_path_choices() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_three_quad_non_manifold_source())
    )

    topology = context.topology_snapshot
    snapshot = context.relation_snapshot

    assert topology is not None
    assert snapshot is not None
    assert any(diagnostic.code == "TOPOLOGY_CHAIN_NON_MANIFOLD" for diagnostic in context.diagnostics.diagnostics)
    assert len(snapshot.scaffold_edges) == len(topology.patch_chains)
    assert snapshot.scaffold_graph is not None
    assert snapshot.scaffold_graph.evidence[0].data["edge_count"] == len(topology.patch_chains)
    assert all(
        relation.kind in (ContinuationKind.TERMINUS, ContinuationKind.SPLIT)
        for relation in snapshot.chain_continuations
    )
    assert not hasattr(snapshot, "scaffold_traces")
    assert not hasattr(snapshot, "scaffold_circuits")
    assert not hasattr(snapshot, "scaffold_rails")


def test_scaffold_graph_builder_does_not_change_layer_1_identity() -> None:
    source = make_closed_shared_boundary_loop_source()
    topology = build_topology_snapshot(source)
    geometry = build_geometry_facts(source, topology)
    snapshot = build_relation_snapshot(topology, geometry)
    original_vertices = dict(topology.vertices)
    original_chains = dict(topology.chains)
    original_patch_chains = dict(topology.patch_chains)
    original_loops = dict(topology.loops)
    original_patches = dict(topology.patches)

    build_scaffold_graph(topology, snapshot.scaffold_nodes)

    assert dict(topology.vertices) == original_vertices
    assert dict(topology.chains) == original_chains
    assert dict(topology.patch_chains) == original_patch_chains
    assert dict(topology.loops) == original_loops
    assert dict(topology.patches) == original_patches


def test_inspection_json_includes_scaffold_graph() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_two_patch_source_with_two_edge_seam_run())
    )

    report = inspect_pipeline_context(context, detail="full")

    json.dumps(report)
    relations = report["relations"]
    assert relations["scaffold_edge_count"] == 4
    assert relations["scaffold_graph_count"] == 1
    assert len(relations["scaffold_edges"]) == 4
    assert relations["scaffold_graph"]["edge_ids"] == [
        edge["id"]
        for edge in relations["scaffold_edges"]
    ]
    assert relations["scaffold_edges"][0]["evidence"][0]["data"]["edge_source"] == "FINAL_PATCH_CHAIN"


def test_scaffold_graph_code_does_not_introduce_deferred_terms_or_imports() -> None:
    tree = ast.parse(SCAFFOLD_GRAPH_MODULE.read_text(encoding="utf-8"))
    identifiers: set[str] = set()
    imports: list[str] = []
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
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)

    assert not identifiers & FORBIDDEN_TOKENS
    assert not any(imported.startswith(FORBIDDEN_IMPORTS) for imported in imports)


def _node_for_source(nodes, source_vertex_id: str):
    return next(
        node
        for node in nodes
        if tuple(str(item) for item in node.source_vertex_ids) == (source_vertex_id,)
    )


def _edge_endpoint_node_ids(edges) -> set[str]:
    node_ids: set[str] = set()
    for edge in edges:
        node_ids.add(edge.start_scaffold_node_id)
        node_ids.add(edge.end_scaffold_node_id)
    return node_ids
