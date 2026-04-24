"""
Layer: tests

Rules:
- Multi-face Patch boundary loop tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

from scaffold_core.layer_1_topology.build import build_topology_snapshot
from scaffold_core.layer_1_topology.invariants import validate_loop_closure
from scaffold_core.tests.fixtures.l_shape import make_two_quad_l_source


def test_unmarked_two_quad_patch_has_closed_outer_boundary_loop() -> None:
    model = build_topology_snapshot(make_two_quad_l_source())

    assert len(model.patches) == 1
    assert validate_loop_closure(model) == ()
