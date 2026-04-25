"""
Layer: tests

Rules:
- Layer 3 conservative continuation relation tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

import ast
from pathlib import Path

from scaffold_core.ids import (
    BoundaryLoopId,
    ChainId,
    ChainUseId,
    PatchId,
    ShellId,
    SurfaceModelId,
    VertexId,
)
from scaffold_core.layer_1_topology.build import build_topology_snapshot
from scaffold_core.layer_1_topology.model import (
    BoundaryLoop,
    BoundaryLoopKind,
    Chain,
    ChainUse,
    Patch,
    Shell,
    SurfaceModel,
    Vertex,
)
from scaffold_core.layer_2_geometry.build import build_geometry_facts
from scaffold_core.layer_3_relations.build import build_relation_snapshot
from scaffold_core.layer_3_relations.continuation import (
    build_chain_continuations,
    continuations_for_source_use,
)
from scaffold_core.layer_3_relations.model import ContinuationKind
from scaffold_core.tests.fixtures.l_shape import make_two_quad_l_source_with_seam_on_shared_edge
from scaffold_core.tests.fixtures.non_manifold import make_non_manifold_chain_model
from scaffold_core.tests.fixtures.single_patch import make_single_quad_source


ROOT = Path(__file__).resolve().parents[1]
CONTINUATION_MODULE = ROOT / "layer_3_relations" / "continuation.py"
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
    "UV",
    "Solve",
})


def test_single_quad_corner_uses_conservative_terminus_for_one_candidate() -> None:
    source = make_single_quad_source()
    topology = build_topology_snapshot(source)
    geometry = build_geometry_facts(source, topology)

    snapshot = build_relation_snapshot(topology, geometry)

    corner_relations = tuple(
        relation
        for relation in snapshot.chain_continuations
        if relation.junction_vertex_id == VertexId("vertex:v0")
    )
    assert len(corner_relations) == 2
    assert {relation.kind for relation in corner_relations} == {ContinuationKind.TERMINUS}
    assert all(relation.target_chain_use_id is None for relation in corner_relations)
    assert _evidence_values(corner_relations[0]) == {
        "incident_count": 2,
        "candidate_count": 1,
        "policy": "conservative_g3b2",
    }


def test_isolated_chain_use_without_candidate_produces_terminus() -> None:
    topology = _make_single_use_model()

    continuations = build_chain_continuations(topology)

    assert len(continuations) == 2
    assert {relation.junction_vertex_id for relation in continuations} == {
        VertexId("vertex:0"),
        VertexId("vertex:1"),
    }
    assert {relation.kind for relation in continuations} == {ContinuationKind.TERMINUS}
    assert all(relation.target_chain_use_id is None for relation in continuations)
    assert all(_evidence_values(relation)["candidate_count"] == 0 for relation in continuations)


def test_ambiguous_junction_produces_split_relations_to_each_candidate() -> None:
    source = make_two_quad_l_source_with_seam_on_shared_edge()
    topology = build_topology_snapshot(source)
    geometry = build_geometry_facts(source, topology)

    snapshot = build_relation_snapshot(topology, geometry)
    split_relations = tuple(
        relation
        for relation in snapshot.chain_continuations
        if relation.junction_vertex_id == VertexId("vertex:v1")
    )

    assert split_relations
    assert {relation.kind for relation in split_relations} == {ContinuationKind.SPLIT}
    assert all(relation.target_chain_use_id is not None for relation in split_relations)
    assert all(_evidence_values(relation)["candidate_count"] >= 2 for relation in split_relations)


def test_non_manifold_incidence_becomes_split_not_false_smooth_or_turn() -> None:
    topology = make_non_manifold_chain_model()

    continuations = build_chain_continuations(topology)

    assert continuations
    assert {relation.kind for relation in continuations} == {ContinuationKind.SPLIT}
    assert all(relation.target_chain_use_id is not None for relation in continuations)


def test_continuations_for_source_use_filters_snapshot_relations() -> None:
    source = make_single_quad_source()
    topology = build_topology_snapshot(source)
    geometry = build_geometry_facts(source, topology)
    snapshot = build_relation_snapshot(topology, geometry)
    source_use_id = next(iter(topology.chain_uses))

    relations = continuations_for_source_use(snapshot, source_use_id)

    assert relations
    assert all(relation.source_chain_use_id == source_use_id for relation in relations)


def test_conservative_continuation_does_not_emit_smooth_or_turn() -> None:
    source = make_two_quad_l_source_with_seam_on_shared_edge()
    topology = build_topology_snapshot(source)
    geometry = build_geometry_facts(source, topology)

    snapshot = build_relation_snapshot(topology, geometry)

    assert ContinuationKind.SMOOTH not in {relation.kind for relation in snapshot.chain_continuations}
    assert ContinuationKind.TURN not in {relation.kind for relation in snapshot.chain_continuations}


def test_continuation_code_does_not_introduce_deferred_semantic_terms() -> None:
    tree = ast.parse(CONTINUATION_MODULE.read_text(encoding="utf-8"))
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


def _evidence_values(relation) -> dict[str, object]:
    assert len(relation.evidence) == 1
    return dict(relation.evidence[0].data)


def _make_single_use_model() -> SurfaceModel:
    shell_id = ShellId("shell:0")
    patch_id = PatchId("patch:0")
    loop_id = BoundaryLoopId("loop:0")
    chain_id = ChainId("chain:0")
    use_id = ChainUseId("use:0")
    v0 = VertexId("vertex:0")
    v1 = VertexId("vertex:1")

    return SurfaceModel(
        id=SurfaceModelId("surface:single_use"),
        shells={shell_id: Shell(id=shell_id, patch_ids=(patch_id,))},
        patches={patch_id: Patch(id=patch_id, shell_id=shell_id, loop_ids=(loop_id,))},
        loops={
            loop_id: BoundaryLoop(
                id=loop_id,
                patch_id=patch_id,
                kind=BoundaryLoopKind.DEGRADED,
                chain_use_ids=(use_id,),
                loop_index=0,
            )
        },
        chains={chain_id: Chain(id=chain_id, start_vertex_id=v0, end_vertex_id=v1)},
        chain_uses={
            use_id: ChainUse(
                id=use_id,
                chain_id=chain_id,
                patch_id=patch_id,
                loop_id=loop_id,
                orientation_sign=1,
                position_in_loop=0,
            )
        },
        vertices={v0: Vertex(id=v0), v1: Vertex(id=v1)},
    )
