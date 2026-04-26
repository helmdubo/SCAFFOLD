"""
Layer: tests

Rules:
- Layer 1 materialized boundary run coalescing tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

from scaffold_core.ids import ChainId, SourceEdgeId
from scaffold_core.layer_1_topology.build import build_topology_snapshot
from scaffold_core.layer_1_topology.invariants import validate_loop_closure
from scaffold_core.layer_1_topology.model import ChainUse
from scaffold_core.layer_1_topology.queries import chain_uses_for_chain
from scaffold_core.layer_2_geometry.build import build_geometry_facts
from scaffold_core.layer_3_relations.chain_refinement import build_chain_directional_runs
from scaffold_core.tests.fixtures.cylinder_tube import make_cylinder_tube_without_caps_with_one_seam_source


ROOT = Path(__file__).resolve().parents[1]
LAYER_1_ROOT = ROOT / "layer_1_topology"
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
})


def test_cylinder_tube_one_seam_materializes_one_loop_with_four_chain_uses() -> None:
    model = build_topology_snapshot(make_cylinder_tube_without_caps_with_one_seam_source())

    assert len(model.patches) == 1
    assert len(model.loops) == 1
    assert len(model.chains) == 3
    assert len(model.chain_uses) == 4
    assert validate_loop_closure(model) == ()
    loop = next(iter(model.loops.values()))
    assert len(loop.chain_use_ids) == 4


def test_cylinder_tube_coalesces_top_bottom_and_seam_runs() -> None:
    model = build_topology_snapshot(make_cylinder_tube_without_caps_with_one_seam_source())

    seam_chain = model.chains[ChainId("chain:e_v0")]
    bottom_chain = model.chains[ChainId("chain:e_b0:e_b1:e_b2:e_b3")]
    top_chain = model.chains[ChainId("chain:e_t3:e_t2:e_t1:e_t0")]

    assert seam_chain.source_edge_ids == (SourceEdgeId("e_v0"),)
    assert bottom_chain.source_edge_ids == (
        SourceEdgeId("e_b0"),
        SourceEdgeId("e_b1"),
        SourceEdgeId("e_b2"),
        SourceEdgeId("e_b3"),
    )
    assert top_chain.source_edge_ids == (
        SourceEdgeId("e_t3"),
        SourceEdgeId("e_t2"),
        SourceEdgeId("e_t1"),
        SourceEdgeId("e_t0"),
    )
    assert {chain.source_edge_ids for chain in model.chains.values()} == {
        seam_chain.source_edge_ids,
        bottom_chain.source_edge_ids,
        top_chain.source_edge_ids,
    }


def test_cylinder_tube_seam_chain_has_two_uses_in_same_patch() -> None:
    model = build_topology_snapshot(make_cylinder_tube_without_caps_with_one_seam_source())

    seam_uses = chain_uses_for_chain(model, ChainId("chain:e_v0"))

    assert len(seam_uses) == 2
    assert {use.patch_id for use in seam_uses} == {next(iter(model.patches))}
    assert {use.orientation_sign for use in seam_uses} == {-1, 1}
    assert seam_uses[0].loop_id == seam_uses[1].loop_id


def test_cylinder_tube_border_rings_are_not_one_edge_chains() -> None:
    model = build_topology_snapshot(make_cylinder_tube_without_caps_with_one_seam_source())

    one_edge_cap_chains = {
        (SourceEdgeId("e_t0"),),
        (SourceEdgeId("e_t1"),),
        (SourceEdgeId("e_t2"),),
        (SourceEdgeId("e_t3"),),
        (SourceEdgeId("e_b0"),),
        (SourceEdgeId("e_b1"),),
        (SourceEdgeId("e_b2"),),
        (SourceEdgeId("e_b3"),),
    }

    assert not any(chain.source_edge_ids in one_edge_cap_chains for chain in model.chains.values())


def test_chain_directional_runs_still_split_turning_border_rings_downstream() -> None:
    source = make_cylinder_tube_without_caps_with_one_seam_source()
    topology = build_topology_snapshot(source)
    geometry = build_geometry_facts(source, topology)

    runs = build_chain_directional_runs(topology, geometry)
    bottom_runs = tuple(
        run
        for run in runs
        if run.parent_chain_id == ChainId("chain:e_b0:e_b1:e_b2:e_b3")
    )
    top_runs = tuple(
        run
        for run in runs
        if run.parent_chain_id == ChainId("chain:e_t3:e_t2:e_t1:e_t0")
    )

    assert len(bottom_runs) == 4
    assert len(top_runs) == 4
    assert all(len(run.source_edge_ids) == 1 for run in bottom_runs + top_runs)


def test_layer_1_chain_use_has_no_geometry_normal_fields() -> None:
    field_names = {field.name for field in fields(ChainUse)}

    assert "normal" not in field_names
    assert "owner_normal" not in field_names
    assert "face_normal" not in field_names


def test_layer_1_materialized_run_code_has_no_deferred_semantic_terms() -> None:
    violations: list[str] = []
    for path in LAYER_1_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
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
        violations.extend(
            f"{path.relative_to(ROOT)} uses {token}"
            for token in sorted(identifiers & FORBIDDEN_TOKENS)
        )

    assert not violations
