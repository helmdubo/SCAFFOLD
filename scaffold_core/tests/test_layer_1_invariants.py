"""
Layer: tests

Rules:
- Layer 1 invariant tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

from scaffold_core.core.diagnostics import DiagnosticSeverity
from scaffold_core.layer_1_topology.build import build_topology_snapshot
from scaffold_core.layer_1_topology.invariants import (
    validate_chain_cardinality,
    validate_loop_closure,
    validate_patch_outer_loops,
    validate_topology,
)
from scaffold_core.tests.fixtures.non_manifold import make_non_manifold_chain_model
from scaffold_core.tests.fixtures.single_patch import make_single_quad_source


def test_single_quad_has_no_blocking_topology_diagnostics() -> None:
    model = build_topology_snapshot(make_single_quad_source())

    diagnostics = validate_topology(model)

    assert not [d for d in diagnostics if d.severity is DiagnosticSeverity.BLOCKING]


def test_single_quad_border_chains_are_reported_as_info() -> None:
    model = build_topology_snapshot(make_single_quad_source())

    diagnostics = validate_chain_cardinality(model)
    border_codes = [d.code for d in diagnostics]

    assert border_codes.count("TOPOLOGY_CHAIN_BORDER") == 4


def test_loop_closure_passes_for_single_quad() -> None:
    model = build_topology_snapshot(make_single_quad_source())

    assert validate_loop_closure(model) == ()


def test_patch_outer_loop_count_passes_for_single_quad() -> None:
    model = build_topology_snapshot(make_single_quad_source())

    assert validate_patch_outer_loops(model) == ()


def test_non_manifold_chain_is_represented_as_degraded_diagnostic() -> None:
    model = make_non_manifold_chain_model()

    diagnostics = validate_chain_cardinality(model)

    assert any(d.code == "TOPOLOGY_CHAIN_NON_MANIFOLD" for d in diagnostics)
    assert any(d.severity is DiagnosticSeverity.DEGRADED for d in diagnostics)
