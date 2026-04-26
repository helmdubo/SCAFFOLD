"""
Layer: tests

Rules:
- PatchChain orientation tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

from scaffold_core.layer_1_topology.queries import patch_chain_vertices
from scaffold_core.tests.fixtures.seam_self import make_seam_self_model


def test_patch_chain_orientation_sign_controls_start_and_end_vertices() -> None:
    model = make_seam_self_model()

    forward_start, forward_end = patch_chain_vertices(model, next(iter(model.patch_chains)))
    reverse_use_id = tuple(model.patch_chains.keys())[1]
    reverse_start, reverse_end = patch_chain_vertices(model, reverse_use_id)

    assert forward_start == reverse_end
    assert forward_end == reverse_start
