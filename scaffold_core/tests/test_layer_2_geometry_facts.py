"""
Layer: tests

Rules:
- Layer 2 geometry fact tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

from scaffold_core.core.diagnostics import DiagnosticSeverity
from scaffold_core.ids import ChainId, PatchId, VertexId
from scaffold_core.layer_1_topology.build import build_topology_snapshot
from scaffold_core.layer_2_geometry.build import build_geometry_facts
from scaffold_core.tests.fixtures.degenerate_geometry import make_degenerate_triangle_source
from scaffold_core.tests.fixtures.l_shape import make_two_quad_l_source
from scaffold_core.tests.fixtures.single_patch import make_single_quad_source


def test_single_quad_geometry_facts_are_measured() -> None:
    source = make_single_quad_source()
    topology = build_topology_snapshot(source)

    facts = build_geometry_facts(source, topology)

    patch = facts.patch_facts[PatchId("patch:seed:f0")]
    assert patch.area == 1.0
    assert patch.normal == (0.0, 0.0, 1.0)
    assert patch.centroid == (0.5, 0.5, 0.0)
    assert facts.chain_facts[ChainId("chain:e0")].length == 1.0
    assert facts.chain_facts[ChainId("chain:e0")].chord_direction == (1.0, 0.0, 0.0)
    assert facts.vertex_facts[VertexId("vertex:v0")].position == (0.0, 0.0, 0.0)


def test_two_quad_patch_geometry_aggregates_source_faces() -> None:
    source = make_two_quad_l_source()
    topology = build_topology_snapshot(source)

    facts = build_geometry_facts(source, topology)

    patch = facts.patch_facts[PatchId("patch:seed:f0")]
    assert patch.area == 2.0
    assert patch.normal == (0.0, 0.0, 1.0)
    assert patch.centroid == (1.0, 0.5, 0.0)


def test_degenerate_geometry_emits_degraded_diagnostics() -> None:
    source = make_degenerate_triangle_source()
    topology = build_topology_snapshot(source)

    facts = build_geometry_facts(source, topology)

    codes = {diagnostic.code for diagnostic in facts.diagnostics}
    assert "GEOMETRY_PATCH_DEGENERATE_AREA" in codes
    assert "GEOMETRY_CHAIN_ZERO_LENGTH" in codes
    assert all(
        diagnostic.severity is DiagnosticSeverity.DEGRADED
        for diagnostic in facts.diagnostics
    )
