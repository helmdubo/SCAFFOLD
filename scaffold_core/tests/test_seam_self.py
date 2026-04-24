"""
Layer: tests

Rules:
- SEAM_SELF topology tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

from scaffold_core.core.diagnostics import DiagnosticSeverity
from scaffold_core.layer_1_topology.invariants import validate_chain_cardinality, validate_loop_closure
from scaffold_core.tests.fixtures.seam_self import make_seam_self_model


def test_seam_self_is_first_class_cardinality_case() -> None:
    model = make_seam_self_model()

    diagnostics = validate_chain_cardinality(model)

    seam_self = [d for d in diagnostics if d.code == "TOPOLOGY_CHAIN_SEAM_SELF"]
    assert len(seam_self) == 1
    assert seam_self[0].severity is DiagnosticSeverity.INFO


def test_seam_self_loop_can_still_close() -> None:
    model = make_seam_self_model()

    assert validate_loop_closure(model) == ()
