"""
Layer: tests

Rules:
- Layer 3 ScaffoldJunction tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

import json

from scaffold_core.layer_1_topology.build import build_topology_snapshot
from scaffold_core.layer_2_geometry.build import build_geometry_facts
from scaffold_core.layer_3_relations.build import build_relation_snapshot
from scaffold_core.layer_3_relations.model import ScaffoldJunctionKind
from scaffold_core.layer_3_relations.scaffold_junctions import build_scaffold_junctions
from scaffold_core.pipeline.inspection import inspect_pipeline_context
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
from scaffold_core.tests.fixtures.closed_shared_loop import make_closed_shared_boundary_loop_source
from scaffold_core.tests.fixtures.cylinder_tube import (
    make_segmented_cylinder_tube_without_caps_with_one_seam_source,
)
from scaffold_core.tests.fixtures.single_patch import make_single_quad_source


def test_cylinder_builds_two_self_seam_scaffold_junctions() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_segmented_cylinder_tube_without_caps_with_one_seam_source())
    )

    snapshot = context.relation_snapshot

    assert snapshot is not None
    assert len(snapshot.loop_corners) == 4
    assert len(snapshot.scaffold_nodes) == 2
    assert len(snapshot.scaffold_edges) == 4
    assert len(snapshot.scaffold_junctions) == 2
    assert {junction.kind for junction in snapshot.scaffold_junctions} == {
        ScaffoldJunctionKind.SELF_SEAM,
    }
    assert {
        junction.scaffold_node_id
        for junction in snapshot.scaffold_junctions
    } == {node.id for node in snapshot.scaffold_nodes}
    assert all(len(junction.scaffold_edge_ids) == 2 for junction in snapshot.scaffold_junctions)
    assert all(len(junction.patch_chain_ids) == 2 for junction in snapshot.scaffold_junctions)
    assert all(junction.evidence[0].data["policy"] == junction.policy for junction in snapshot.scaffold_junctions)


def test_closed_shared_two_patch_boundary_does_not_build_self_seam_junctions() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_closed_shared_boundary_loop_source())
    )

    snapshot = context.relation_snapshot

    assert snapshot is not None
    assert len(snapshot.scaffold_nodes) == 2
    assert len(snapshot.scaffold_edges) == 2
    assert snapshot.scaffold_junctions == ()


def test_ordinary_single_patch_node_remains_unclassified() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_single_quad_source())
    )

    snapshot = context.relation_snapshot

    assert snapshot is not None
    assert len(snapshot.scaffold_nodes) == 1
    assert len(snapshot.scaffold_edges) == 1
    assert snapshot.scaffold_junctions == ()


def test_scaffold_junction_builder_does_not_change_layer_1_or_graph_identity() -> None:
    source = make_segmented_cylinder_tube_without_caps_with_one_seam_source()
    topology = build_topology_snapshot(source)
    geometry = build_geometry_facts(source, topology)
    snapshot = build_relation_snapshot(topology, geometry)
    original_vertices = dict(topology.vertices)
    original_chains = dict(topology.chains)
    original_patch_chains = dict(topology.patch_chains)
    original_nodes = tuple(snapshot.scaffold_nodes)
    original_edges = tuple(snapshot.scaffold_edges)
    original_graph = snapshot.scaffold_graph

    build_scaffold_junctions(snapshot.scaffold_nodes, snapshot.scaffold_edges)

    assert dict(topology.vertices) == original_vertices
    assert dict(topology.chains) == original_chains
    assert dict(topology.patch_chains) == original_patch_chains
    assert snapshot.scaffold_nodes == original_nodes
    assert snapshot.scaffold_edges == original_edges
    assert snapshot.scaffold_graph == original_graph


def test_inspection_json_includes_scaffold_junctions() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_segmented_cylinder_tube_without_caps_with_one_seam_source())
    )

    report = inspect_pipeline_context(context, detail="full")

    json.dumps(report)
    relations = report["relations"]
    assert relations["scaffold_junction_count"] == 2
    assert len(relations["scaffold_junctions"]) == 2
    assert {junction["kind"] for junction in relations["scaffold_junctions"]} == {"SELF_SEAM"}
    assert all(junction["policy"] for junction in relations["scaffold_junctions"])
    assert all(junction["scaffold_node_id"] for junction in relations["scaffold_junctions"])
    assert all(junction["matched_chain_id"] for junction in relations["scaffold_junctions"])
    assert all(junction["patch_id"] for junction in relations["scaffold_junctions"])
    assert all(len(junction["scaffold_edge_ids"]) == 2 for junction in relations["scaffold_junctions"])
    assert all(len(junction["patch_chain_ids"]) == 2 for junction in relations["scaffold_junctions"])
