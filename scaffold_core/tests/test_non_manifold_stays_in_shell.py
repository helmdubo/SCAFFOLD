"""
Layer: tests

Rules:
- G1 non-manifold Shell and Chain cardinality tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

from scaffold_core.core.diagnostics import DiagnosticSeverity
from scaffold_core.layer_1_topology.build import build_topology_snapshot
from scaffold_core.layer_1_topology.invariants import validate_chain_cardinality
from scaffold_core.tests.fixtures.non_manifold import make_three_quad_non_manifold_source


def test_three_quads_sharing_one_edge_stay_in_one_degraded_shell_candidate() -> None:
    model = build_topology_snapshot(make_three_quad_non_manifold_source())

    diagnostics = validate_chain_cardinality(model)

    assert len(model.shells) == 1
    assert any(
        diagnostic.code == "TOPOLOGY_CHAIN_NON_MANIFOLD"
        and diagnostic.severity is DiagnosticSeverity.DEGRADED
        for diagnostic in diagnostics
    )
