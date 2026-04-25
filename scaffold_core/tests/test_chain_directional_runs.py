"""
Layer: tests

Rules:
- Layer 3 ChainDirectionalRun tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from scaffold_core.ids import ChainId, SourceEdgeId, SourceVertexId, SurfaceModelId, VertexId
from scaffold_core.layer_1_topology.build import build_topology_snapshot
from scaffold_core.layer_1_topology.model import Chain, SurfaceModel, Vertex
from scaffold_core.layer_2_geometry.build import build_geometry_facts
from scaffold_core.layer_2_geometry.facts import (
    ChainGeometryFacts,
    ChainSegmentGeometryFacts,
    ChainShapeHint,
    GeometryFactSnapshot,
)
from scaffold_core.layer_3_relations.build import build_relation_snapshot
from scaffold_core.layer_3_relations.chain_refinement import build_chain_directional_runs
from scaffold_core.pipeline.inspection import inspect_pipeline_context
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
from scaffold_core.tests.fixtures.chain_shape_geometry import make_chain_shape_source_and_topology
from scaffold_core.tests.fixtures.closed_shared_loop import make_closed_shared_boundary_loop_source


ROOT = Path(__file__).resolve().parents[1]
CHAIN_REFINEMENT_MODULE = ROOT / "layer_3_relations" / "chain_refinement.py"
FORBIDDEN_TOKENS = frozenset({
    "H_FRAME",
    "V_FRAME",
    "WALL",
    "FLOOR",
    "SLOPE",
    "AlignmentClass",
    "PatchAxes",
    "WorldOrientation",
    "Feature",
    "Runtime",
    "Solve",
    "UV",
})


def test_straight_multi_segment_chain_produces_one_directional_run() -> None:
    source, topology = make_chain_shape_source_and_topology()
    geometry = build_geometry_facts(source, topology)

    runs = build_chain_directional_runs(topology, geometry)
    straight_run = next(run for run in runs if run.parent_chain_id == ChainId("chain:straight"))

    assert straight_run.source_edge_ids == (SourceEdgeId("e0"), SourceEdgeId("e1"))
    assert straight_run.segment_indices == (0, 1)
    assert straight_run.start_source_vertex_id == SourceVertexId("v0")
    assert straight_run.end_source_vertex_id == SourceVertexId("v2")
    assert straight_run.length == 2.0
    assert straight_run.direction == (1.0, 0.0, 0.0)
    assert not straight_run.is_closed


def test_closed_square_chain_produces_four_directional_runs_without_chain_identity_change() -> None:
    source = make_closed_shared_boundary_loop_source()
    topology = build_topology_snapshot(source)
    geometry = build_geometry_facts(source, topology)
    original_chain = topology.chains[ChainId("chain:e10:e9:e6:e7")]

    snapshot = build_relation_snapshot(topology, geometry)

    assert topology.chains[original_chain.id] == original_chain
    runs = tuple(
        run
        for run in snapshot.chain_directional_runs
        if run.parent_chain_id == original_chain.id
    )
    assert len(runs) == 4
    assert [run.source_edge_ids for run in runs] == [
        (SourceEdgeId("e10"),),
        (SourceEdgeId("e9"),),
        (SourceEdgeId("e6"),),
        (SourceEdgeId("e7"),),
    ]
    assert [run.segment_indices for run in runs] == [(0,), (1,), (2,), (3,)]
    assert [run.direction for run in runs] == [
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (-1.0, 0.0, 0.0),
        (0.0, -1.0, 0.0),
    ]
    assert all(run.is_closed for run in runs)


def test_perpendicular_segments_split_into_two_directional_runs() -> None:
    topology, geometry = _make_geometry_snapshot(
        (
            ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
            ((1.0, 0.0, 0.0), (1.0, 1.0, 0.0)),
        )
    )

    runs = build_chain_directional_runs(topology, geometry)

    assert len(runs) == 2
    assert [run.source_edge_ids for run in runs] == [
        (SourceEdgeId("e0"),),
        (SourceEdgeId("e1"),),
    ]
    assert [run.direction for run in runs] == [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]


def test_collinear_unknown_segments_merge_into_one_directional_run() -> None:
    topology, geometry = _make_geometry_snapshot(
        (
            ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
            ((1.0, 0.0, 0.0), (2.0, 0.0, 0.0)),
        )
    )

    runs = build_chain_directional_runs(topology, geometry)

    assert len(runs) == 1
    assert runs[0].source_edge_ids == (SourceEdgeId("e0"), SourceEdgeId("e1"))
    assert runs[0].segment_indices == (0, 1)
    assert runs[0].direction == (1.0, 0.0, 0.0)


def test_inspection_json_includes_chain_directional_runs() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_closed_shared_boundary_loop_source())
    )

    report = inspect_pipeline_context(context)

    json.dumps(report)
    relations = report["relations"]
    assert relations["chain_directional_run_count"] == 4
    assert relations["chain_directional_runs"][0] == {
        "id": "directional_run:chain:e10:e9:e6:e7:0",
        "parent_chain_id": "chain:e10:e9:e6:e7",
        "source_edge_ids": ["e10"],
        "segment_indices": [0],
        "start_source_vertex_id": "v0",
        "end_source_vertex_id": "v1",
        "length": 1.0,
        "direction": [1.0, 0.0, 0.0],
        "is_closed": True,
        "confidence": 1.0,
    }


def test_chain_refinement_code_does_not_introduce_deferred_semantic_terms() -> None:
    tree = ast.parse(CHAIN_REFINEMENT_MODULE.read_text(encoding="utf-8"))
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


def _make_geometry_snapshot(
    segment_positions: tuple[tuple[tuple[float, float, float], tuple[float, float, float]], ...],
) -> tuple[SurfaceModel, GeometryFactSnapshot]:
    chain_id = ChainId("chain:directional")
    start_vertex_id = VertexId("vertex:start")
    end_vertex_id = VertexId("vertex:end")
    topology = SurfaceModel(
        id=SurfaceModelId("surface:directional"),
        chains={
            chain_id: Chain(
                id=chain_id,
                start_vertex_id=start_vertex_id,
                end_vertex_id=end_vertex_id,
            ),
        },
        vertices={
            start_vertex_id: Vertex(id=start_vertex_id),
            end_vertex_id: Vertex(id=end_vertex_id),
        },
    )
    segments = tuple(
        _segment(chain_id, index, start, end)
        for index, (start, end) in enumerate(segment_positions)
    )
    return topology, GeometryFactSnapshot(
        chain_facts={
            chain_id: ChainGeometryFacts(
                chain_id=chain_id,
                length=sum(segment.length for segment in segments),
                chord_length=1.0,
                chord_direction=(0.0, 0.0, 0.0),
                straightness=0.0,
                detour_ratio=0.0,
                shape_hint=ChainShapeHint.UNKNOWN,
                segments=segments,
            )
        }
    )


def _segment(
    chain_id: ChainId,
    index: int,
    start: tuple[float, float, float],
    end: tuple[float, float, float],
) -> ChainSegmentGeometryFacts:
    vector = (end[0] - start[0], end[1] - start[1], end[2] - start[2])
    length = (vector[0] * vector[0] + vector[1] * vector[1] + vector[2] * vector[2]) ** 0.5
    direction = (
        vector[0] / length,
        vector[1] / length,
        vector[2] / length,
    )
    return ChainSegmentGeometryFacts(
        chain_id=chain_id,
        source_edge_id=SourceEdgeId(f"e{index}"),
        segment_index=index,
        start_source_vertex_id=SourceVertexId(f"v{index}"),
        end_source_vertex_id=SourceVertexId(f"v{index + 1}"),
        start_position=start,
        end_position=end,
        vector=vector,
        length=length,
        direction=direction,
    )
