"""
Layer: tests

Rules:
- G1 Shell detection ignores seam Patch boundaries.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

from scaffold_core.layer_1_topology.build import build_topology_snapshot
from scaffold_core.tests.fixtures.l_shape import make_two_quad_l_source_with_seam_on_shared_edge


def test_two_quads_with_seam_between_them_produce_one_shell() -> None:
    model = build_topology_snapshot(make_two_quad_l_source_with_seam_on_shared_edge())

    assert len(model.shells) == 1
