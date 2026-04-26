"""
Layer: tests

Rules:
- Pipeline Pass 0 tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

from scaffold_core.core.diagnostics import DiagnosticSeverity
from scaffold_core.pipeline.passes import run_pass_0
from scaffold_core.tests.fixtures.single_patch import make_single_quad_source


def test_pass_0_builds_topology_snapshot() -> None:
    context = run_pass_0(make_single_quad_source())

    assert context.source_snapshot is not None
    assert context.topology_snapshot is not None
    assert context.geometry_facts is not None
    assert len(context.topology_snapshot.patches) == 1
    assert len(context.topology_snapshot.chains) == 1
    assert len(context.topology_snapshot.patch_chains) == 1
    assert len(context.geometry_facts.patch_facts) == 1
    assert len(context.geometry_facts.chain_facts) == 1


def test_pass_0_single_quad_has_no_blocking_diagnostics() -> None:
    context = run_pass_0(make_single_quad_source())

    assert not [
        diagnostic
        for diagnostic in context.diagnostics.diagnostics
        if diagnostic.severity is DiagnosticSeverity.BLOCKING
    ]
