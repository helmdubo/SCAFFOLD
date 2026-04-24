"""
Layer: tests

Rules:
- Shared Chain / ChainUse tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

from scaffold_core.layer_1_topology.build import build_topology_snapshot
from scaffold_core.layer_1_topology.queries import chain_uses_for_chain
from scaffold_core.tests.fixtures.l_shape import make_two_quad_l_source


def test_two_quads_share_one_chain_with_two_opposite_uses() -> None:
    model = build_topology_snapshot(make_two_quad_l_source())

    shared_chains = [
        chain
        for chain in model.chains.values()
        if len(chain_uses_for_chain(model, chain.id)) == 2
    ]

    assert len(shared_chains) == 1

    uses = chain_uses_for_chain(model, shared_chains[0].id)
    assert {use.orientation_sign for use in uses} == {-1, 1}
    assert uses[0].patch_id != uses[1].patch_id
