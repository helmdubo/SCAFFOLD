"""
Layer: tests

Rules:
- Layer 3 junction sample tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from scaffold_core.ids import PatchId, SourceVertexId, VertexId
from scaffold_core.layer_1_topology.build import build_topology_snapshot
from scaffold_core.layer_2_geometry.build import build_geometry_facts
from scaffold_core.layer_3_relations.build import build_relation_snapshot
from scaffold_core.layer_3_relations.junction_samples import build_junction_samples
from scaffold_core.layer_3_relations.model import OwnerNormalSource, RunUseEndpointRole
from scaffold_core.pipeline.inspection import inspect_pipeline_context
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
from scaffold_core.tests.fixtures.closed_shared_loop import make_closed_shared_boundary_loop_source


ROOT = Path(__file__).resolve().parents[1]
JUNCTION_SAMPLES_MODULE = ROOT / "layer_3_relations" / "junction_samples.py"
FORBIDDEN_TOKENS = frozenset({
    "H_FRAME",
    "V_FRAME",
    "WALL",
    "FLOOR",
    "SLOPE",
    "WorldOrientation",
    "WORLD_UP",
    "Feature",
    "Runtime",
    "Solve",
    "UV",
    "ScaffoldMap",
    "ScaffoldGraph",
})


def test_junction_samples_are_built_for_each_run_use_endpoint() -> None:
    source = make_closed_shared_boundary_loop_source()
    topology = build_topology_snapshot(source)
    geometry = build_geometry_facts(source, topology)
    snapshot = build_relation_snapshot(topology, geometry)

    samples = snapshot.junction_samples

    assert len(snapshot.chain_directional_run_uses) == 8
    assert len(samples) == 16
    assert {sample.endpoint_role for sample in samples} == {
        RunUseEndpointRole.START,
        RunUseEndpointRole.END,
    }
    assert {sample.run_use_id for sample in samples} == {
        run_use.id for run_use in snapshot.chain_directional_run_uses
    }


def test_junction_sample_tangent_points_away_from_endpoint() -> None:
    source = make_closed_shared_boundary_loop_source()
    topology = build_topology_snapshot(source)
    geometry = build_geometry_facts(source, topology)
    snapshot = build_relation_snapshot(topology, geometry)
    run_use = next(
        item
        for item in snapshot.chain_directional_run_uses
        if item.patch_id == PatchId("patch:seed:f0")
        and item.start_source_vertex_id == SourceVertexId("v0")
        and item.end_source_vertex_id == SourceVertexId("v1")
    )

    start_sample = _sample(snapshot.junction_samples, run_use.id, RunUseEndpointRole.START)
    end_sample = _sample(snapshot.junction_samples, run_use.id, RunUseEndpointRole.END)

    assert start_sample.vertex_id == VertexId("vertex:v0")
    assert end_sample.vertex_id == VertexId("vertex:v1")
    assert start_sample.tangent_away_from_vertex == run_use.direction
    assert end_sample.tangent_away_from_vertex == (
        -run_use.direction[0],
        -run_use.direction[1],
        -run_use.direction[2],
    )


def test_junction_sample_owner_normal_uses_patch_aggregate_normal() -> None:
    source = make_closed_shared_boundary_loop_source()
    topology = build_topology_snapshot(source)
    geometry = build_geometry_facts(source, topology)
    snapshot = build_relation_snapshot(topology, geometry)

    for sample in snapshot.junction_samples:
        assert sample.owner_normal == geometry.patch_facts[sample.patch_id].normal
        assert sample.owner_normal_source is OwnerNormalSource.PATCH_AGGREGATE_NORMAL
        assert sample.confidence == 1.0


def test_junction_samples_do_not_change_layer_1_identity() -> None:
    source = make_closed_shared_boundary_loop_source()
    topology = build_topology_snapshot(source)
    original_chains = dict(topology.chains)
    original_chain_uses = dict(topology.chain_uses)
    original_vertices = dict(topology.vertices)
    geometry = build_geometry_facts(source, topology)
    snapshot = build_relation_snapshot(topology, geometry)

    build_junction_samples(topology, geometry, snapshot.chain_directional_run_uses)

    assert dict(topology.chains) == original_chains
    assert dict(topology.chain_uses) == original_chain_uses
    assert dict(topology.vertices) == original_vertices


def test_inspection_json_includes_junction_samples() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_closed_shared_boundary_loop_source())
    )

    report = inspect_pipeline_context(context, detail="full")

    json.dumps(report)
    relations = report["relations"]
    assert relations["junction_sample_count"] == 16
    first_sample = relations["junction_samples"][0]
    assert first_sample["id"].startswith("junction_sample:")
    assert first_sample["vertex_id"].startswith("vertex:")
    assert first_sample["run_use_id"].startswith("directional_run_use:")
    assert first_sample["endpoint_role"] in ("START", "END")
    assert first_sample["owner_normal_source"] == "PATCH_AGGREGATE_NORMAL"
    assert "tangent_away_from_vertex" in first_sample
    assert "owner_normal" in first_sample


def test_junction_samples_code_does_not_introduce_deferred_semantic_terms() -> None:
    tree = ast.parse(JUNCTION_SAMPLES_MODULE.read_text(encoding="utf-8"))
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


def _sample(samples, run_use_id: str, role: RunUseEndpointRole):
    return next(
        sample
        for sample in samples
        if sample.run_use_id == run_use_id and sample.endpoint_role is role
    )
