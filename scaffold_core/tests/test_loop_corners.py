"""
Layer: tests

Rules:
- Layer 3 LoopCorner tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

import json

from scaffold_core.pipeline.inspection import inspect_pipeline_context
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
from scaffold_core.tests.fixtures.cylinder_tube import (
    make_segmented_cylinder_tube_without_caps_with_one_seam_source,
)


def test_cylinder_loop_corners_follow_final_patch_chains() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_segmented_cylinder_tube_without_caps_with_one_seam_source())
    )

    snapshot = context.relation_snapshot
    assert snapshot is not None
    assert len(snapshot.loop_corners) == 4
    assert {
        corner.position_in_loop
        for corner in snapshot.loop_corners
    } == {0, 1, 2, 3}
    assert all(corner.previous_patch_chain_id != corner.next_patch_chain_id for corner in snapshot.loop_corners)


def test_inspection_json_includes_loop_corners() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_segmented_cylinder_tube_without_caps_with_one_seam_source())
    )

    report = inspect_pipeline_context(context, detail="full")

    json.dumps(report)
    relations = report["relations"]
    assert relations["loop_corner_count"] == 4
    first_corner = relations["loop_corners"][0]
    assert first_corner["id"].startswith("loop_corner:")
    assert first_corner["previous_patch_chain_id"].startswith("use:")
    assert first_corner["next_patch_chain_id"].startswith("use:")
