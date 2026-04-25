"""
Layer: tests

Rules:
- Layer 3 ChainDirectionalRunUse tests only.
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
    build_chain_directional_run_uses,
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


def test_shared_closed_loop_builds_patch_local_directional_run_uses() -> None:
    source = make_closed_shared_boundary_loop_source()
    topology = build_topology_snapshot(source)
    geometry = build_geometry_facts(source, topology)
    directional_runs = build_chain_directional_runs(topology, geometry)

    run_uses = build_chain_directional_run_uses(topology, directional_runs)

    assert len(directional_runs) == 4
    assert len(topology.chain_uses) == 2
    assert len(run_uses) == 8
    assert {run_use.parent_chain_id for run_use in run_uses} == {
        ChainId("chain:e10:e9:e6:e7")
    }
    assert {
        run_use.directional_run_id
        for run_use in run_uses
    } == {run.id for run in directional_runs}


def test_opposite_chain_use_orientation_reverses_direction_and_endpoints() -> None:
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
        run_use
        for run_use in snapshot.chain_directional_run_uses
        if run_use.directional_run_id == parent_run.id
    )

    assert len(uses) == 2
    plus_use = next(run_use for run_use in uses if run_use.orientation_sign == 1)
    minus_use = next(run_use for run_use in uses if run_use.orientation_sign == -1)
    assert plus_use.direction == parent_run.direction
    assert minus_use.direction == (-parent_run.direction[0], -parent_run.direction[1], -parent_run.direction[2])
    assert plus_use.start_source_vertex_id == SourceVertexId("v0")
    assert plus_use.end_source_vertex_id == SourceVertexId("v1")
    assert minus_use.start_source_vertex_id == SourceVertexId("v1")
    assert minus_use.end_source_vertex_id == SourceVertexId("v0")


def test_directional_run_use_keeps_patch_local_fields() -> None:
    source = make_closed_shared_boundary_loop_source()
    topology = build_topology_snapshot(source)
    geometry = build_geometry_facts(source, topology)
    snapshot = build_relation_snapshot(topology, geometry)

    for run_use in snapshot.chain_directional_run_uses:
        chain_use = topology.chain_uses[run_use.chain_use_id]
        assert run_use.patch_id == chain_use.patch_id
        assert run_use.loop_id == chain_use.loop_id
        assert run_use.position_in_loop == chain_use.position_in_loop
        assert run_use.orientation_sign == chain_use.orientation_sign
        assert run_use.source_edge_ids
        assert run_use.segment_indices


def test_directional_run_uses_do_not_change_layer_1_identity() -> None:
    source = make_closed_shared_boundary_loop_source()
    topology = build_topology_snapshot(source)
    original_chains = dict(topology.chains)
    original_chain_uses = dict(topology.chain_uses)
    original_loops = dict(topology.loops)
    original_patches = dict(topology.patches)
    geometry = build_geometry_facts(source, topology)

    build_relation_snapshot(topology, geometry)

    assert dict(topology.chains) == original_chains
    assert dict(topology.chain_uses) == original_chain_uses
    assert dict(topology.loops) == original_loops
    assert dict(topology.patches) == original_patches


def test_inspection_json_includes_chain_directional_run_uses() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_closed_shared_boundary_loop_source())
    )

    report = inspect_pipeline_context(context)

    json.dumps(report)
    relations = report["relations"]
    assert relations["chain_directional_run_count"] == 4
    assert relations["chain_directional_run_use_count"] == 8
    first_run_use = relations["chain_directional_run_uses"][0]
    assert first_run_use["id"].startswith("directional_run_use:")
    assert first_run_use["directional_run_id"].startswith("directional_run:chain:e10:e9:e6:e7:")
    assert first_run_use["parent_chain_id"] == "chain:e10:e9:e6:e7"
    assert first_run_use["source_edge_ids"] == ["e10"]
    assert first_run_use["segment_indices"] == [0]
    assert first_run_use["length"] == 1.0
    assert first_run_use["orientation_sign"] in (-1, 1)
    assert "patch_id" in first_run_use
    assert "loop_id" in first_run_use


def test_chain_refinement_code_does_not_introduce_deferred_semantic_terms_for_run_uses() -> None:
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
