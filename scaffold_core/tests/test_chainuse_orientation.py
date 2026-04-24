"""
Layer: tests

Rules:
- ChainUse orientation tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

from scaffold_core.layer_1_topology.queries import chain_use_vertices
from scaffold_core.tests.fixtures.seam_self import make_seam_self_model


def test_chain_use_orientation_sign_controls_start_and_end_vertices() -> None:
    model = make_seam_self_model()

    forward_start, forward_end = chain_use_vertices(model, next(iter(model.chain_uses)))
    reverse_use_id = tuple(model.chain_uses.keys())[1]
    reverse_start, reverse_end = chain_use_vertices(model, reverse_use_id)

    assert forward_start == reverse_end
    assert forward_end == reverse_start
