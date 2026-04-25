"""
Layer: tests

Rules:
- Layer 3 vertex-incidence query tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

import ast
from pathlib import Path

from scaffold_core.ids import VertexId
from scaffold_core.layer_1_topology.build import build_topology_snapshot
from scaffold_core.layer_1_topology.queries import chain_use_vertices
from scaffold_core.layer_3_relations.junction import (
    incident_chain_uses_for_vertex,
    is_junction_like,
    junction_valence,
)
from scaffold_core.tests.fixtures.closed_shared_loop import make_closed_shared_boundary_loop_source
from scaffold_core.tests.fixtures.l_shape import make_two_quad_l_source_with_seam_on_shared_edge
from scaffold_core.tests.fixtures.non_manifold import make_non_manifold_chain_model
from scaffold_core.tests.fixtures.single_patch import make_single_quad_source


ROOT = Path(__file__).resolve().parents[1]
JUNCTION_MODULE = ROOT / "layer_3_relations" / "junction.py"
FORBIDDEN_TOKENS = frozenset({
    "H_FRAME",
    "V_FRAME",
    "WALL",
    "FLOOR",
    "SLOPE",
    "AlignmentClass",
    "PatchAxes",
    "WorldOrientation",
    "ChainContinuationRelation",
    "Feature",
    "Runtime",
    "UV",
    "Solve",
})


def _assert_deterministic_order(use_ids: list[str]) -> None:
    assert use_ids == sorted(use_ids)


def test_single_quad_corner_vertex_has_deterministic_incident_uses() -> None:
    topology = build_topology_snapshot(make_single_quad_source())
    vertex_id = VertexId("vertex:v0")

    uses = incident_chain_uses_for_vertex(topology, vertex_id)
    use_ids = [str(use.id) for use in uses]

    assert len(uses) == 2
    assert junction_valence(topology, vertex_id) == 2
    assert not is_junction_like(topology, vertex_id)
    _assert_deterministic_order(use_ids)
    assert all(vertex_id in chain_use_vertices(topology, use.id) for use in uses)


def test_two_patch_shared_vertex_returns_all_relevant_uses() -> None:
    topology = build_topology_snapshot(make_two_quad_l_source_with_seam_on_shared_edge())
    vertex_id = VertexId("vertex:v1")

    uses = incident_chain_uses_for_vertex(topology, vertex_id)
    use_ids = [str(use.id) for use in uses]

    assert len(uses) >= 3
    assert junction_valence(topology, vertex_id) == len(uses)
    assert is_junction_like(topology, vertex_id)
    _assert_deterministic_order(use_ids)
    assert all(vertex_id in chain_use_vertices(topology, use.id) for use in uses)


def test_closed_seam_loop_query_does_not_assume_chain_direction_stability() -> None:
    topology = build_topology_snapshot(make_closed_shared_boundary_loop_source())
    closed_chain = next(iter(topology.chains.values()))
    vertex_id = closed_chain.start_vertex_id

    uses = incident_chain_uses_for_vertex(topology, vertex_id)
    use_ids = [str(use.id) for use in uses]

    assert closed_chain.start_vertex_id == closed_chain.end_vertex_id
    assert len(uses) == 2
    assert junction_valence(topology, vertex_id) == 2
    _assert_deterministic_order(use_ids)
    assert all(use.chain_id == closed_chain.id for use in uses)


def test_non_manifold_vertex_incidence_is_represented_without_correction() -> None:
    topology = make_non_manifold_chain_model()
    vertex_id = VertexId("vertex:0")

    uses = incident_chain_uses_for_vertex(topology, vertex_id)
    use_ids = [str(use.id) for use in uses]

    assert len(uses) == 3
    assert junction_valence(topology, vertex_id) == 3
    assert is_junction_like(topology, vertex_id)
    _assert_deterministic_order(use_ids)


def test_junction_queries_do_not_introduce_deferred_semantic_terms() -> None:
    tree = ast.parse(JUNCTION_MODULE.read_text(encoding="utf-8"))
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
