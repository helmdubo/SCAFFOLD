"""
Layer: tests

Rules:
- Pipeline Pass 1 tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

import pytest

from scaffold_core.pipeline.context import PipelineContext
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
from scaffold_core.tests.fixtures.l_shape import (
    make_two_quad_l_source_with_seam_on_shared_edge,
)


def test_pass_1_builds_relation_snapshot_after_pass_0() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_two_quad_l_source_with_seam_on_shared_edge())
    )

    assert context.relation_snapshot is not None
    assert len(context.relation_snapshot.patch_adjacencies) == 1
    assert context.source_snapshot is not None
    assert context.topology_snapshot is not None
    assert context.geometry_facts is not None


def test_pass_1_requires_topology_and_geometry() -> None:
    with pytest.raises(ValueError):
        run_pass_1_relations(PipelineContext())
