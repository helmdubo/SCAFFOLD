"""
Layer: tests

Rules:
- Layer 3 PatchChainDirectionalEvidence tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from scaffold_core.ids import ChainId, SourceEdgeId, SourceVertexId
from scaffold_core.layer_1_topology.build import build_topology_snapshot
from scaffold_core.layer_2_geometry.build import build_geometry_facts
from scaffold_core.layer_3_relations.build import build_relation_snapshot
from scaffold_core.layer_3_relations.chain_refinement import (
    build_patch_chain_directional_evidence,
    build_chain_directional_runs,
)
from scaffold_core.pipeline.inspection import inspect_pipeline_context
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
from scaffold_core.tests.fixtures.closed_shared_loop import make_closed_shared_boundary_loop_source


ROOT = Path(__file__).resolve().parents[1]
CHAIN_REFINEMENT_MODULE = ROOT / "layer_3_relations" / "chain_refinement.py"
FORBIDDEN_TOKENS = frozenset({
    "H_FRAME",
    "V_FRAME",
    "WALL",
    "FLOOR",
    "SLOPE",
    "AlignmentClass",
    "PatchAxes",
    "WorldOrientation",
    "WORLD_UP",
    "Feature",
    "Runtime",
    "Solve",
    "UV",
})


def test_shared_closed_loop_builds_patch_local_patch_chain_directional_evidences() -> None:
    source = make_closed_shared_boundary_loop_source()
    topology = build_topology_snapshot(source)
    geometry = build_geometry_facts(source, topology)
    directional_runs = build_chain_directional_runs(topology, geometry)

    directional_evidence_items = build_patch_chain_directional_evidence(topology, directional_runs)

    assert len(directional_runs) == 4
    assert len(topology.patch_chains) == 2
    assert len(directional_evidence_items) == 8
    assert {directional_evidence.parent_chain_id for directional_evidence in directional_evidence_items} == {
        ChainId("chain:e10:e9:e6:e7")
    }
    assert {
        directional_evidence.directional_run_id
        for directional_evidence in directional_evidence_items
    } == {run.id for run in directional_runs}


def test_opposite_patch_chain_orientation_reverses_direction_and_endpoints() -> None:
    source = make_closed_shared_boundary_loop_source()
    topology = build_topology_snapshot(source)
    geometry = build_geometry_facts(source, topology)
    snapshot = build_relation_snapshot(topology, geometry)
    parent_run = next(
        run
        for run in snapshot.chain_directional_runs
        if run.source_edge_ids == (SourceEdgeId("e10"),)
    )

    uses = tuple(
        directional_evidence
        for directional_evidence in snapshot.patch_chain_directional_evidence
        if directional_evidence.directional_run_id == parent_run.id
    )

    assert len(uses) == 2
    plus_use = next(directional_evidence for directional_evidence in uses if directional_evidence.orientation_sign == 1)
    minus_use = next(directional_evidence for directional_evidence in uses if directional_evidence.orientation_sign == -1)
    assert plus_use.direction == parent_run.direction
    assert minus_use.direction == (-parent_run.direction[0], -parent_run.direction[1], -parent_run.direction[2])
    assert plus_use.start_source_vertex_id == SourceVertexId("v0")
    assert plus_use.end_source_vertex_id == SourceVertexId("v1")
    assert minus_use.start_source_vertex_id == SourceVertexId("v1")
    assert minus_use.end_source_vertex_id == SourceVertexId("v0")


def test_patch_chain_directional_evidence_keeps_patch_local_fields() -> None:
    source = make_closed_shared_boundary_loop_source()
    topology = build_topology_snapshot(source)
    geometry = build_geometry_facts(source, topology)
    snapshot = build_relation_snapshot(topology, geometry)

    for directional_evidence in snapshot.patch_chain_directional_evidence:
        patch_chain = topology.patch_chains[directional_evidence.patch_chain_id]
        assert directional_evidence.patch_id == patch_chain.patch_id
        assert directional_evidence.loop_id == patch_chain.loop_id
        assert directional_evidence.position_in_loop == patch_chain.position_in_loop
        assert directional_evidence.orientation_sign == patch_chain.orientation_sign
        assert directional_evidence.source_edge_ids
        assert directional_evidence.segment_indices


def test_patch_chain_directional_evidences_do_not_change_layer_1_identity() -> None:
    source = make_closed_shared_boundary_loop_source()
    topology = build_topology_snapshot(source)
    original_chains = dict(topology.chains)
    original_patch_chains = dict(topology.patch_chains)
    original_loops = dict(topology.loops)
    original_patches = dict(topology.patches)
    geometry = build_geometry_facts(source, topology)

    build_relation_snapshot(topology, geometry)

    assert dict(topology.chains) == original_chains
    assert dict(topology.patch_chains) == original_patch_chains
    assert dict(topology.loops) == original_loops
    assert dict(topology.patches) == original_patches


def test_inspection_json_includes_patch_chain_directional_evidence() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_closed_shared_boundary_loop_source())
    )

    report = inspect_pipeline_context(context, detail="full")

    json.dumps(report)
    relations = report["relations"]
    assert relations["chain_directional_run_count"] == 4
    assert relations["patch_chain_directional_evidence_count"] == 8
    first_directional_evidence = relations["patch_chain_directional_evidence"][0]
    assert first_directional_evidence["id"].startswith("patch_chain_directional_evidence:")
    assert first_directional_evidence["directional_run_id"].startswith("directional_run:chain:e10:e9:e6:e7:")
    assert first_directional_evidence["parent_chain_id"] == "chain:e10:e9:e6:e7"
    assert first_directional_evidence["source_edge_ids"] == ["e10"]
    assert first_directional_evidence["segment_indices"] == [0]
    assert first_directional_evidence["length"] == 1.0
    assert first_directional_evidence["orientation_sign"] in (-1, 1)
    assert "patch_id" in first_directional_evidence
    assert "loop_id" in first_directional_evidence


def test_chain_refinement_code_does_not_introduce_deferred_semantic_terms_for_directional_evidence_items() -> None:
    tree = ast.parse(CHAIN_REFINEMENT_MODULE.read_text(encoding="utf-8"))
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
