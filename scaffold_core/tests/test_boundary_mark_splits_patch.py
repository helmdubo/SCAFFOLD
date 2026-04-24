"""
Layer: tests

Rules:
- G1 explicit Scaffold boundary Patch segmentation test only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

from scaffold_core.layer_1_topology.build import build_topology_snapshot
from scaffold_core.tests.fixtures.l_shape import make_two_quad_l_source_with_user_boundary_on_shared_edge


def test_explicit_scaffold_boundary_between_two_quads_produces_two_patches() -> None:
    model = build_topology_snapshot(make_two_quad_l_source_with_user_boundary_on_shared_edge())

    assert len(model.shells) == 1
    assert len(model.patches) == 2
