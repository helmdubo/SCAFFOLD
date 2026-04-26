"""
Layer: tests

Rules:
- Layer 3 PatchAxes tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

import ast
import json
from dataclasses import fields
from pathlib import Path

from scaffold_core.ids import (
    BoundaryLoopId,
    ChainId,
    PatchChainId,
    PatchId,
    ShellId,
    SourceVertexId,
    SurfaceModelId,
)
from scaffold_core.layer_1_topology.model import Patch, SurfaceModel
from scaffold_core.layer_2_geometry.facts import Vector3
from scaffold_core.layer_3_relations.alignment import build_patch_axes
from scaffold_core.layer_3_relations.model import (
    AlignmentClass,
    AlignmentClassKind,
    PatchChainDirectionalEvidence,
    PatchAxes,
    PatchAxisSource,
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
    "WorldOrientation",
    "WORLD_UP",
    "Feature",
    "Runtime",
    "Solve",
    "UV",
})


def test_closed_square_patch_axes_use_dual_alignment() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_closed_shared_boundary_loop_source())
    )

    snapshot = context.relation_snapshot
    assert snapshot is not None
    assert len(snapshot.patch_axes) == 2
    assert {patch_axes.source for patch_axes in snapshot.patch_axes.values()} == {
        PatchAxisSource.DUAL_ALIGNMENT
    }
    for patch_axes in snapshot.patch_axes.values():
        assert patch_axes.primary_alignment_class_id is not None
        assert patch_axes.secondary_alignment_class_id is not None
        assert patch_axes.primary_direction in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
        assert patch_axes.secondary_direction in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0))


def test_patch_axes_model_has_no_coordinate_label_fields() -> None:
    field_names = {field.name for field in fields(PatchAxes)}

    assert not field_names & {
        "u_alignment_class",
        "v_alignment_class",
        "u_direction",
        "v_direction",
        "H",
        "V",
    }


def test_single_alignment_patch_axes() -> None:
    patch_id = PatchId("patch:single")
    directional_evidence = _directional_evidence("directional_evidence:single", patch_id, (1.0, 0.0, 0.0), 2.0)
    alignment_class = _alignment_class("alignment:single", (directional_evidence.id,), (patch_id,), (1.0, 0.0, 0.0))

    patch_axes = build_patch_axes(
        _topology_with_patch(patch_id),
        (directional_evidence,),
        (alignment_class,),
    )[patch_id]

    assert patch_axes.source is PatchAxisSource.SINGLE_ALIGNMENT
    assert patch_axes.primary_alignment_class_id == "alignment:single"
    assert patch_axes.secondary_alignment_class_id is None
    assert patch_axes.primary_direction == (1.0, 0.0, 0.0)
    assert patch_axes.secondary_direction == (0.0, 0.0, 0.0)
    assert _candidate_scores(patch_axes) == [
        {
            "alignment_class_id": "alignment:single",
            "patch_length_score": 2.0,
            "dot_with_primary": None,
            "selected_as": "PRIMARY",
        }
    ]


def test_no_alignment_patch_axes() -> None:
    patch_id = PatchId("patch:none")

    patch_axes = build_patch_axes(_topology_with_patch(patch_id), (), ())[patch_id]

    assert patch_axes.source is PatchAxisSource.NO_ALIGNMENT
    assert patch_axes.primary_alignment_class_id is None
    assert patch_axes.secondary_alignment_class_id is None
    assert patch_axes.primary_direction == (0.0, 0.0, 0.0)
    assert patch_axes.secondary_direction == (0.0, 0.0, 0.0)
    assert patch_axes.confidence == 0.0
    assert _candidate_scores(patch_axes) == []


def test_patch_axes_evidence_marks_candidate_rejection_reasons() -> None:
    patch_id = PatchId("patch:candidates")
    primary_directional_evidence = _directional_evidence("directional_evidence:primary", patch_id, (1.0, 0.0, 0.0), 2.0)
    secondary_directional_evidence = _directional_evidence("directional_evidence:secondary", patch_id, (0.0, 1.0, 0.0), 1.5)
    parallel_directional_evidence = _directional_evidence("directional_evidence:parallel", patch_id, (1.0, 0.0, 0.0), 1.0)
    zero_patch_directional_evidence = _directional_evidence("directional_evidence:zero", PatchId("patch:other"), (0.0, 0.0, 1.0), 3.0)
    alignment_classes = (
        _alignment_class("alignment:primary", (primary_directional_evidence.id,), (patch_id,), (1.0, 0.0, 0.0)),
        _alignment_class("alignment:secondary", (secondary_directional_evidence.id,), (patch_id,), (0.0, 1.0, 0.0)),
        _alignment_class("alignment:parallel", (parallel_directional_evidence.id,), (patch_id,), (1.0, 0.0, 0.0)),
        _alignment_class("alignment:zero", (zero_patch_directional_evidence.id,), (PatchId("patch:other"),), (0.0, 0.0, 1.0)),
    )

    patch_axes = build_patch_axes(
        _topology_with_patch(patch_id),
        (primary_directional_evidence, secondary_directional_evidence, parallel_directional_evidence, zero_patch_directional_evidence),
        alignment_classes,
    )[patch_id]

    assert _candidate_scores(patch_axes) == [
        {
            "alignment_class_id": "alignment:primary",
            "patch_length_score": 2.0,
            "dot_with_primary": None,
            "selected_as": "PRIMARY",
        },
        {
            "alignment_class_id": "alignment:secondary",
            "patch_length_score": 1.5,
            "dot_with_primary": 0.0,
            "selected_as": "SECONDARY",
        },
        {
            "alignment_class_id": "alignment:parallel",
            "patch_length_score": 1.0,
            "dot_with_primary": 1.0,
            "selected_as": "REJECTED_PARALLEL",
        },
        {
            "alignment_class_id": "alignment:zero",
            "patch_length_score": 0,
            "dot_with_primary": 0.0,
            "selected_as": "REJECTED_ZERO_PATCH_LENGTH",
        },
    ]


def test_inspection_json_includes_patch_axes() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_closed_shared_boundary_loop_source())
    )

    report = inspect_pipeline_context(context, detail="full")

    json.dumps(report)
    relations = report["relations"]
    assert relations["patch_axes_count"] == 2
    first_axes = relations["patch_axes"][0]
    assert first_axes["source"] == "DUAL_ALIGNMENT"
    assert first_axes["primary_alignment_class_id"] is not None
    assert first_axes["secondary_alignment_class_id"] is not None
    assert first_axes["primary_direction"] in ([1.0, 0.0, 0.0], [0.0, 1.0, 0.0])
    assert first_axes["secondary_direction"] in ([1.0, 0.0, 0.0], [0.0, 1.0, 0.0])
    assert first_axes["candidate_scores"]
    assert {candidate["selected_as"] for candidate in first_axes["candidate_scores"]} == {
        "PRIMARY",
        "SECONDARY",
    }


def test_alignment_code_does_not_introduce_deferred_semantic_terms_for_patch_axes() -> None:
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


def _topology_with_patch(patch_id: PatchId) -> SurfaceModel:
    return SurfaceModel(
        id=SurfaceModelId("surface:patch_axes"),
        patches={
            patch_id: Patch(
                id=patch_id,
                shell_id=ShellId("shell:0"),
                loop_ids=(),
            )
        },
    )


def _candidate_scores(patch_axes: PatchAxes) -> list[dict[str, object]]:
    assert patch_axes.evidence
    return list(patch_axes.evidence[0].data["candidate_scores"])


def _directional_evidence(
    directional_evidence_id: str,
    patch_id: PatchId,
    direction: Vector3,
    length: float,
) -> PatchChainDirectionalEvidence:
    return PatchChainDirectionalEvidence(
        id=directional_evidence_id,
        directional_run_id=f"directional:{directional_evidence_id}",
        parent_chain_id=ChainId("chain:test"),
        patch_chain_id=PatchChainId(f"patch_chain:{directional_evidence_id}"),
        patch_id=patch_id,
        loop_id=BoundaryLoopId(f"loop:{patch_id}"),
        position_in_loop=0,
        orientation_sign=1,
        source_edge_ids=(),
        segment_indices=(),
        start_source_vertex_id=SourceVertexId("v0"),
        end_source_vertex_id=SourceVertexId("v1"),
        length=length,
        direction=direction,
        confidence=1.0,
    )


def _alignment_class(
    alignment_class_id: str,
    member_directional_evidence_ids: tuple[str, ...],
    patch_ids: tuple[PatchId, ...],
    dominant_direction: Vector3,
) -> AlignmentClass:
    return AlignmentClass(
        id=alignment_class_id,
        member_directional_evidence_ids=member_directional_evidence_ids,
        patch_ids=patch_ids,
        dominant_direction=dominant_direction,
        kind=AlignmentClassKind.LINEAR,
        confidence=1.0,
    )
