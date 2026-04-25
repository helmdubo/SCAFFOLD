"""
Layer: tests

Rules:
- Layer 3 AlignmentClass tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from scaffold_core.ids import BoundaryLoopId, ChainId, ChainUseId, PatchId, SourceVertexId
from scaffold_core.layer_2_geometry.facts import Vector3
from scaffold_core.layer_3_relations.alignment import build_alignment_classes
from scaffold_core.layer_3_relations.model import (
    AlignmentClassKind,
    ChainDirectionalRunUse,
)
from scaffold_core.pipeline.inspection import inspect_pipeline_context
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
from scaffold_core.tests.fixtures.closed_shared_loop import make_closed_shared_boundary_loop_source


ROOT = Path(__file__).resolve().parents[1]
ALIGNMENT_MODULE = ROOT / "layer_3_relations" / "alignment.py"
FORBIDDEN_TOKENS = frozenset({
    "H_FRAME",
    "V_FRAME",
    "WALL",
    "FLOOR",
    "SLOPE",
    "PatchAxes",
    "WorldOrientation",
    "WORLD_UP",
    "Feature",
    "Runtime",
    "Solve",
    "UV",
})


def test_closed_square_seam_produces_two_alignment_direction_families() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_closed_shared_boundary_loop_source())
    )

    snapshot = context.relation_snapshot
    assert snapshot is not None
    assert len(snapshot.chain_directional_run_uses) == 8
    assert len(snapshot.alignment_classes) == 2
    assert {alignment.kind for alignment in snapshot.alignment_classes} == {
        AlignmentClassKind.LINEAR
    }
    assert {alignment.dominant_direction for alignment in snapshot.alignment_classes} == {
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
    }


def test_opposite_directions_group_into_one_alignment_class() -> None:
    run_uses = (
        _run_use("run_use:a", (1.0, 0.0, 0.0), PatchId("patch:a")),
        _run_use("run_use:b", (-1.0, 0.0, 0.0), PatchId("patch:b")),
    )

    alignment_classes = build_alignment_classes(run_uses)

    assert len(alignment_classes) == 1
    alignment_class = alignment_classes[0]
    assert alignment_class.kind is AlignmentClassKind.LINEAR
    assert alignment_class.member_run_use_ids == ("run_use:a", "run_use:b")
    assert alignment_class.patch_ids == (PatchId("patch:a"), PatchId("patch:b"))
    assert alignment_class.dominant_direction == (1.0, 0.0, 0.0)


def test_alignment_members_are_directional_run_use_ids() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_closed_shared_boundary_loop_source())
    )

    snapshot = context.relation_snapshot
    assert snapshot is not None
    run_use_ids = {run_use.id for run_use in snapshot.chain_directional_run_uses}
    chain_ids = {str(run_use.parent_chain_id) for run_use in snapshot.chain_directional_run_uses}
    directional_run_ids = {run_use.directional_run_id for run_use in snapshot.chain_directional_run_uses}

    for alignment_class in snapshot.alignment_classes:
        assert set(alignment_class.member_run_use_ids) <= run_use_ids
        assert not set(alignment_class.member_run_use_ids) & chain_ids
        assert not set(alignment_class.member_run_use_ids) & directional_run_ids


def test_relation_snapshot_does_not_expose_patch_axes() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_closed_shared_boundary_loop_source())
    )

    snapshot = context.relation_snapshot
    assert snapshot is not None
    assert not hasattr(snapshot, "patch_axes")


def test_inspection_json_includes_alignment_classes() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_closed_shared_boundary_loop_source())
    )

    report = inspect_pipeline_context(context)

    json.dumps(report)
    relations = report["relations"]
    assert relations["alignment_class_count"] == 2
    first_alignment = relations["alignment_classes"][0]
    assert first_alignment == {
        "id": "alignment:0",
        "kind": "LINEAR",
        "member_run_use_ids": [
            "directional_run_use:use:patch:seed:f0:0:0:0",
            "directional_run_use:use:patch:seed:f0:0:0:2",
            "directional_run_use:use:patch:seed:f1:0:0:0",
            "directional_run_use:use:patch:seed:f1:0:0:2",
        ],
        "patch_ids": ["patch:seed:f0", "patch:seed:f1"],
        "dominant_direction": [1.0, 0.0, 0.0],
        "confidence": 1.0,
    }


def test_alignment_code_does_not_introduce_deferred_semantic_terms() -> None:
    tree = ast.parse(ALIGNMENT_MODULE.read_text(encoding="utf-8"))
    identifiers: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            identifiers.add(node.id)
        elif isinstance(node, ast.Attribute):
            identifiers.add(node.attr)
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            identifiers.add(node.name)
        elif isinstance(node, ast.arg):
            identifiers.add(node.arg)
        elif isinstance(node, ast.alias):
            identifiers.add(node.name.split(".")[-1])
            if node.asname:
                identifiers.add(node.asname)

    assert not identifiers & FORBIDDEN_TOKENS


def _run_use(
    run_use_id: str,
    direction: Vector3,
    patch_id: PatchId,
) -> ChainDirectionalRunUse:
    return ChainDirectionalRunUse(
        id=run_use_id,
        directional_run_id=f"directional:{run_use_id}",
        parent_chain_id=ChainId("chain:test"),
        chain_use_id=ChainUseId(f"use:{run_use_id}"),
        patch_id=patch_id,
        loop_id=BoundaryLoopId(f"loop:{patch_id}"),
        position_in_loop=0,
        orientation_sign=1,
        source_edge_ids=(),
        segment_indices=(),
        start_source_vertex_id=SourceVertexId("v0"),
        end_source_vertex_id=SourceVertexId("v1"),
        length=1.0,
        direction=direction,
        confidence=1.0,
    )
