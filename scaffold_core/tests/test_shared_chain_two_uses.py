"""
Layer: tests

Rules:
- Shared Chain / ChainUse tests for explicit Patch boundaries only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

from scaffold_core.layer_1_topology.build import build_topology_snapshot
from scaffold_core.layer_1_topology.queries import chain_uses_for_chain
from scaffold_core.tests.fixtures.l_shape import make_two_quad_l_source_with_seam_on_shared_edge


def test_seamed_l_shape_shared_chain_has_two_opposite_uses() -> None:
    model = build_topology_snapshot(make_two_quad_l_source_with_seam_on_shared_edge())

    shared_chains = [
        chain
        for chain in model.chains.values()
        if len(chain_uses_for_chain(model, chain.id)) == 2
    ]

    assert len(shared_chains) == 1

    uses = chain_uses_for_chain(model, shared_chains[0].id)
    assert {use.orientation_sign for use in uses} == {-1, 1}
    assert uses[0].patch_id != uses[1].patch_id
