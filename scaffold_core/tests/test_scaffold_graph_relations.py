"""
Layer: tests

Rules:
- Layer 3 ScaffoldGraph evidence relation tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from scaffold_core.ids import BoundaryLoopId, ChainId, PatchChainId, PatchId, VertexId
from scaffold_core.layer_3_relations.model import (
    DihedralKind,
    PatchAdjacency,
    PatchChainEndpointRole,
    PatchChainEndpointSample,
    OwnerNormalSource,
    ScaffoldEdge,
    ScaffoldJunctionKind,
    ScaffoldNode,
    ScaffoldNodeIncidentEdgeRelationKind,
    SharedChainPatchChainRelationKind,
)
from scaffold_core.layer_3_relations.patch_chain_endpoint_relations import (
    build_patch_chain_endpoint_relations,
)
from scaffold_core.layer_3_relations.scaffold_graph_relations import (
    build_scaffold_graph_relations,
)
from scaffold_core.pipeline.inspection import inspect_pipeline_context
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
from scaffold_core.tests.fixtures.closed_shared_loop import make_closed_shared_boundary_loop_source
from scaffold_core.tests.fixtures.l_shape import make_two_patch_source_with_two_edge_seam_run


ROOT = Path(__file__).resolve().parents[1]
SCAFFOLD_GRAPH_RELATIONS_MODULE = ROOT / "layer_3_relations" / "scaffold_graph_relations.py"
FORBIDDEN_TOKENS = frozenset({
    "H_FRAME",
    "V_FRAME",
    "WALL",
    "FLOOR",
    "SLOPE",
    "WorldOrientation",
    "WORLD_UP",
    "ScaffoldTrace",
    "ScaffoldCircuit",
    "ScaffoldRail",
    "FeatureCandidate",
    "Runtime",
    "Solve",
    "UV",
})
FORBIDDEN_IMPORTS = (
    "scaffold_core.layer_4_features",
    "scaffold_core.layer_5_runtime",
    "scaffold_core.api",
    "scaffold_core.ui",
    "scaffold_core.pipeline",
)


def test_same_patch_orthogonal_endpoint_relation_becomes_node_corner_relation() -> None:
    relation = _single_incident_relation(
        _sample("a", (1.0, 0.0, 0.0), PatchId("patch:one")),
        _sample("b", (0.0, 1.0, 0.0), PatchId("patch:one")),
    )

    assert relation.kind is ScaffoldNodeIncidentEdgeRelationKind.ORTHOGONAL_CORNER
    assert relation.patch_chain_endpoint_relation_id is not None
    assert relation.confidence == 1.0


def test_opposite_collinear_endpoint_relation_becomes_continuation_candidate() -> None:
    relation = _single_incident_relation(
        _sample("a", (1.0, 0.0, 0.0), PatchId("patch:one")),
        _sample("b", (-1.0, 0.0, 0.0), PatchId("patch:one")),
    )

    assert relation.kind is ScaffoldNodeIncidentEdgeRelationKind.CONTINUATION_CANDIDATE
    assert relation.evidence[0].data["endpoint_relation_kind"] == "CONTINUATION_CANDIDATE"


def test_same_ray_endpoint_relation_becomes_ambiguous_pair_without_reversed_duplicate() -> None:
    relation = _single_incident_relation(
        _sample("b", (1.0, 0.0, 0.0), PatchId("patch:one")),
        _sample("a", (1.0, 0.0, 0.0), PatchId("patch:one")),
    )

    assert relation.kind is ScaffoldNodeIncidentEdgeRelationKind.SAME_RAY_AMBIGUOUS
    assert relation.first_scaffold_edge_id < relation.second_scaffold_edge_id


def test_degraded_endpoint_evidence_becomes_degraded_incident_edge_relation() -> None:
    relation = _single_incident_relation(
        _sample("a", (1.0, 0.0, 0.0), PatchId("patch:one")),
        _sample("b", (0.0, 0.0, 0.0), PatchId("patch:one"), confidence=0.0),
    )

    assert relation.kind is ScaffoldNodeIncidentEdgeRelationKind.DEGRADED
    assert relation.confidence == 0.0


def test_cross_patch_shared_chain_relation_links_patch_adjacency_when_available() -> None:
    first_edge = _edge("a", ChainId("chain:shared"), PatchId("patch:left"))
    second_edge = _edge("b", ChainId("chain:shared"), PatchId("patch:right"))
    adjacency = PatchAdjacency(
        id="adjacency:shared:left:right",
        first_patch_id=first_edge.patch_id,
        second_patch_id=second_edge.patch_id,
        chain_id=first_edge.chain_id,
        first_patch_chain_id=first_edge.patch_chain_id,
        second_patch_chain_id=second_edge.patch_chain_id,
        shared_length=1.0,
        signed_angle_radians=0.0,
        dihedral_kind=DihedralKind.COPLANAR,
    )

    incident_relations, shared_relations = build_scaffold_graph_relations(
        scaffold_nodes=(),
        scaffold_edges=(first_edge, second_edge),
        endpoint_samples=(),
        endpoint_relations=(),
        patch_adjacencies={adjacency.id: adjacency},
    )

    assert incident_relations == ()
    assert len(shared_relations) == 1
    assert shared_relations[0].kind is SharedChainPatchChainRelationKind.CROSS_PATCH_SHARED_CHAIN
    assert shared_relations[0].chain_id == ChainId("chain:shared")
    assert shared_relations[0].patch_adjacency_id == adjacency.id


def test_cross_patch_node_has_incident_edge_pair_evidence_in_snapshot_and_inspection() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_two_patch_source_with_two_edge_seam_run())
    )

    snapshot = context.relation_snapshot
    assert snapshot is not None
    cross_patch_node_ids = {
        junction.scaffold_node_id
        for junction in snapshot.scaffold_junctions
        if junction.kind is ScaffoldJunctionKind.CROSS_PATCH
    }
    relation_node_ids = {
        relation.scaffold_node_id
        for relation in snapshot.scaffold_node_incident_edge_relations
    }

    assert cross_patch_node_ids
    assert cross_patch_node_ids <= relation_node_ids
    assert all(
        relation.patch_chain_endpoint_relation_id in {
            endpoint_relation.id
            for endpoint_relation in snapshot.patch_chain_endpoint_relations
        }
        for relation in snapshot.scaffold_node_incident_edge_relations
    )
    assert snapshot.shared_chain_patch_chain_relations

    report = inspect_pipeline_context(context, detail="full")
    json.dumps(report)
    relations = report["relations"]
    assert relations["scaffold_node_incident_edge_relation_count"] == len(
        snapshot.scaffold_node_incident_edge_relations
    )
    assert relations["shared_chain_patch_chain_relation_count"] == len(
        snapshot.shared_chain_patch_chain_relations
    )
    assert relations["scaffold_node_incident_edge_relations"]
    assert relations["shared_chain_patch_chain_relations"]


def test_closed_shared_loop_preserves_multiple_endpoint_relations_for_same_edge_pair() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_closed_shared_boundary_loop_source())
    )

    snapshot = context.relation_snapshot
    assert snapshot is not None
    assert len(snapshot.scaffold_node_incident_edge_relations) == 8
    assert {
        relation.kind
        for relation in snapshot.scaffold_node_incident_edge_relations
    } == {
        ScaffoldNodeIncidentEdgeRelationKind.ORTHOGONAL_CORNER,
        ScaffoldNodeIncidentEdgeRelationKind.SAME_RAY_AMBIGUOUS,
    }
    assert len({
        relation.patch_chain_endpoint_relation_id
        for relation in snapshot.scaffold_node_incident_edge_relations
    }) == 8
    assert len({
        relation.id
        for relation in snapshot.scaffold_node_incident_edge_relations
    }) == 8


def test_scaffold_graph_relations_code_does_not_introduce_deferred_terms_or_imports() -> None:
    tree = ast.parse(SCAFFOLD_GRAPH_RELATIONS_MODULE.read_text(encoding="utf-8"))
    identifiers: set[str] = set()
    imports: list[str] = []
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
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)

    assert not identifiers & FORBIDDEN_TOKENS
    assert not any(imported.startswith(FORBIDDEN_IMPORTS) for imported in imports)


def _single_incident_relation(
    first_sample: PatchChainEndpointSample,
    second_sample: PatchChainEndpointSample,
):
    endpoint_relations = build_patch_chain_endpoint_relations((first_sample, second_sample))
    assert len(endpoint_relations) == 1
    edges = (
        _edge("a", ChainId("chain:a"), first_sample.patch_id),
        _edge("b", ChainId("chain:b"), second_sample.patch_id),
    )
    node = _node(first_sample.patch_chain_id, second_sample.patch_chain_id)

    incident_relations, shared_relations = build_scaffold_graph_relations(
        scaffold_nodes=(node,),
        scaffold_edges=edges,
        endpoint_samples=(first_sample, second_sample),
        endpoint_relations=endpoint_relations,
        patch_adjacencies={},
    )

    assert shared_relations == ()
    assert len(incident_relations) == 1
    return incident_relations[0]


def _sample(
    suffix: str,
    tangent,
    patch_id: PatchId,
    confidence: float = 1.0,
) -> PatchChainEndpointSample:
    return PatchChainEndpointSample(
        id=f"sample:{suffix}",
        vertex_id=VertexId("vertex:one"),
        directional_evidence_id=f"directional_evidence:{suffix}",
        patch_chain_id=PatchChainId(f"patch_chain:{suffix}"),
        patch_id=patch_id,
        endpoint_role=PatchChainEndpointRole.START,
        tangent_away_from_vertex=tangent,
        owner_normal=(0.0, 0.0, 1.0),
        owner_normal_source=OwnerNormalSource.PATCH_AGGREGATE_NORMAL,
        confidence=confidence,
    )


def _edge(
    suffix: str,
    chain_id: ChainId,
    patch_id: PatchId,
) -> ScaffoldEdge:
    return ScaffoldEdge(
        id=f"scaffold_edge:patch_chain:{suffix}",
        patch_chain_id=PatchChainId(f"patch_chain:{suffix}"),
        chain_id=chain_id,
        patch_id=patch_id,
        loop_id=BoundaryLoopId(f"loop:{suffix}"),
        start_scaffold_node_id="scaffold_node:one",
        end_scaffold_node_id="scaffold_node:two",
        confidence=1.0,
    )


def _node(
    first_patch_chain_id: PatchChainId,
    second_patch_chain_id: PatchChainId,
) -> ScaffoldNode:
    return ScaffoldNode(
        id="scaffold_node:one",
        vertex_ids=(VertexId("vertex:one"),),
        source_vertex_ids=(),
        loop_corner_ids=(),
        patch_chain_endpoint_sample_ids=("sample:a", "sample:b"),
        patch_chain_endpoint_relation_ids=(),
        incident_patch_chain_ids=tuple(sorted((first_patch_chain_id, second_patch_chain_id), key=str)),
        patch_ids=(PatchId("patch:one"),),
        confidence=1.0,
    )
