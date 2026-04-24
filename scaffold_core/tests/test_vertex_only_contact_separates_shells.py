"""
Layer: tests

Rules:
- G1 Shell detection uses edge connectivity only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

from scaffold_core.layer_1_topology.build import build_topology_snapshot
from scaffold_core.tests.fixtures.corner_touch import make_vertex_only_contact_source


def test_two_quads_meeting_at_one_corner_produce_two_shells() -> None:
    model = build_topology_snapshot(make_vertex_only_contact_source())

    assert len(model.shells) == 2
