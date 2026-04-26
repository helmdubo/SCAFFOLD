"""
Layer: tests

Rules:
- Shared Chain / PatchChain tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

from scaffold_core.layer_1_topology.build import build_topology_snapshot
from scaffold_core.ids import SourceEdgeId
from scaffold_core.tests.fixtures.l_shape import make_two_quad_l_source


def test_unmarked_shared_edge_is_internal_to_one_patch() -> None:
    model = build_topology_snapshot(make_two_quad_l_source())

    assert len(model.patches) == 1
    assert not [
        chain
        for chain in model.chains.values()
        if chain.source_edge_ids == (SourceEdgeId("e1"),)
    ]
