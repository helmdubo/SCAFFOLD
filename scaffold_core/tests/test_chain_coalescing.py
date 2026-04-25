"""
Layer: tests

Rules:
- Layer 1 Chain coalescing tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

from scaffold_core.ids import ChainId, SourceEdgeId
from scaffold_core.layer_1_topology.build import build_topology_snapshot
from scaffold_core.layer_1_topology.invariants import validate_loop_closure
from scaffold_core.layer_1_topology.queries import chain_uses_for_chain
from scaffold_core.tests.fixtures.l_shape import make_two_patch_source_with_two_edge_seam_run


def test_two_edge_shared_boundary_coalesces_to_one_chain() -> None:
    model = build_topology_snapshot(make_two_patch_source_with_two_edge_seam_run())

    shared_chain = model.chains[ChainId("chain:e1:e2")]
    uses = chain_uses_for_chain(model, shared_chain.id)

    assert shared_chain.source_edge_ids == (SourceEdgeId("e1"), SourceEdgeId("e2"))
    assert len(uses) == 2
    assert {use.orientation_sign for use in uses} == {-1, 1}
    assert validate_loop_closure(model) == ()
    assert not any(
        chain.source_edge_ids in ((SourceEdgeId("e1"),), (SourceEdgeId("e2"),))
        for chain in model.chains.values()
    )
