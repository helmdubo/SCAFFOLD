"""
Layer: tests

Rules:
- Layer 3 junction run-use relation tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from scaffold_core.ids import ChainUseId, PatchId, VertexId
from scaffold_core.layer_3_relations.junction_relations import build_junction_run_use_relations
from scaffold_core.layer_3_relations.model import (
    ChainDirectionalRunUseJunctionSample,
    JunctionDirectionRelationKind,
    JunctionRunUseRelationKind,
    OwnerNormalSource,
    RunUseEndpointRole,
)
from scaffold_core.pipeline.inspection import inspect_pipeline_context
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
from scaffold_core.tests.fixtures.closed_shared_loop import make_closed_shared_boundary_loop_source
from scaffold_core.tests.fixtures.cylinder_tube import (
    make_segmented_cylinder_tube_without_caps_with_one_seam_source,
)


ROOT = Path(__file__).resolve().parents[1]
JUNCTION_RELATIONS_MODULE = ROOT / "layer_3_relations" / "junction_relations.py"
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
    "ScaffoldMap",
    "ScaffoldGraph",
    "JunctionDiskCycle",
})


def test_opposite_collinear_samples_are_continuation_candidates() -> None:
    relation = _single_relation(
        _sample("a", (1.0, 0.0, 0.0)),
        _sample("b", (-1.0, 0.0, 0.0)),
    )

    assert relation.direction_dot == -1.0
    assert relation.direction_relation is JunctionDirectionRelationKind.OPPOSITE_COLLINEAR
    assert relation.kind is JunctionRunUseRelationKind.CONTINUATION_CANDIDATE
    assert relation.confidence == 1.0


def test_same_ray_collinear_samples_are_ambiguous() -> None:
    relation = _single_relation(
        _sample("a", (1.0, 0.0, 0.0)),
        _sample("b", (1.0, 0.0, 0.0)),
    )

    assert relation.direction_dot == 1.0
    assert relation.direction_relation is JunctionDirectionRelationKind.SAME_RAY_COLLINEAR
    assert relation.kind is JunctionRunUseRelationKind.AMBIGUOUS


def test_orthogonal_samples_are_corner_connectors() -> None:
    relation = _single_relation(
        _sample("a", (1.0, 0.0, 0.0)),
        _sample("b", (0.0, 1.0, 0.0)),
    )

    assert relation.direction_dot == 0.0
    assert relation.direction_relation is JunctionDirectionRelationKind.ORTHOGONAL
    assert relation.kind is JunctionRunUseRelationKind.CORNER_CONNECTOR


def test_oblique_samples_are_oblique_connectors() -> None:
    relation = _single_relation(
        _sample("a", (1.0, 0.0, 0.0)),
        _sample("b", (0.5, 0.5, 0.0)),
    )

    assert 0.2 < relation.direction_dot < 0.996
    assert relation.direction_relation is JunctionDirectionRelationKind.OBLIQUE
    assert relation.kind is JunctionRunUseRelationKind.OBLIQUE_CONNECTOR


def test_degenerate_sample_produces_degenerate_relation() -> None:
    relation = _single_relation(
        _sample("a", (1.0, 0.0, 0.0)),
        _sample("b", (0.0, 0.0, 0.0), confidence=0.0),
    )

    assert relation.direction_relation is JunctionDirectionRelationKind.DEGENERATE
    assert relation.kind is JunctionRunUseRelationKind.DEGENERATE
    assert relation.confidence == 0.0


def test_relations_are_unordered_pairs_without_reversed_duplicates() -> None:
    samples = (
        _sample("a", (1.0, 0.0, 0.0)),
        _sample("b", (-1.0, 0.0, 0.0)),
        _sample("c", (0.0, 1.0, 0.0)),
    )

    relations = build_junction_run_use_relations(samples)

    assert len(relations) == 3
    pairs = {(relation.first_sample_id, relation.second_sample_id) for relation in relations}
    assert all((second, first) not in pairs for first, second in pairs)


def test_pipeline_builds_closed_loop_junction_run_use_relations() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_closed_shared_boundary_loop_source())
    )

    snapshot = context.relation_snapshot
    assert snapshot is not None
    assert len(snapshot.junction_samples) == 16
    assert len(snapshot.junction_run_use_relations) == 24
    assert {
        relation.kind
        for relation in snapshot.junction_run_use_relations
    } >= {
        JunctionRunUseRelationKind.CORNER_CONNECTOR,
        JunctionRunUseRelationKind.AMBIGUOUS,
    }


def test_cylinder_endpoint_relations_use_local_face_fan_normals() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_segmented_cylinder_tube_without_caps_with_one_seam_source())
    )

    snapshot = context.relation_snapshot
    assert snapshot is not None
    assert snapshot.junction_run_use_relations
    assert all(
        relation.kind is not JunctionRunUseRelationKind.DEGENERATE
        for relation in snapshot.junction_run_use_relations
    )


def test_inspection_json_includes_junction_run_use_relations() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_closed_shared_boundary_loop_source())
    )

    report = inspect_pipeline_context(context, detail="full")

    json.dumps(report)
    relations = report["relations"]
    assert relations["junction_run_use_relation_count"] == 24
    assert relations["patch_chain_endpoint_relation_count"] == 24
    first_relation = relations["patch_chain_endpoint_relations"][0]
    assert first_relation["id"].startswith("patch_chain_endpoint_relation:")
    assert first_relation["vertex_id"].startswith("vertex:")
    assert first_relation["first_run_use_id"].startswith("directional_run_use:")
    assert first_relation["second_run_use_id"].startswith("directional_run_use:")
    assert "direction_dot" in first_relation
    assert "normal_dot" in first_relation
    assert first_relation["direction_relation"] in {
        "OPPOSITE_COLLINEAR",
        "SAME_RAY_COLLINEAR",
        "ORTHOGONAL",
        "OBLIQUE",
        "DEGENERATE",
    }


def test_junction_relation_code_does_not_introduce_deferred_semantic_terms() -> None:
    tree = ast.parse(JUNCTION_RELATIONS_MODULE.read_text(encoding="utf-8"))
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


def _single_relation(
    first: ChainDirectionalRunUseJunctionSample,
    second: ChainDirectionalRunUseJunctionSample,
):
    relations = build_junction_run_use_relations((first, second))
    assert len(relations) == 1
    return relations[0]


def _sample(
    sample_id: str,
    tangent,
    confidence: float = 1.0,
) -> ChainDirectionalRunUseJunctionSample:
    return ChainDirectionalRunUseJunctionSample(
        id=f"sample:{sample_id}",
        vertex_id=VertexId("vertex:test"),
        run_use_id=f"run_use:{sample_id}",
        chain_use_id=ChainUseId(f"use:{sample_id}"),
        patch_id=PatchId("patch:test"),
        endpoint_role=RunUseEndpointRole.START,
        tangent_away_from_vertex=tangent,
        owner_normal=(0.0, 0.0, 1.0),
        owner_normal_source=OwnerNormalSource.PATCH_AGGREGATE_NORMAL,
        confidence=confidence,
    )
