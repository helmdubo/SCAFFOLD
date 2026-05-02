"""
Layer: 3 - Relations

Rules:
- Build evidence relations over existing ScaffoldNode and ScaffoldEdge records.
- Use final PatchChains and implemented endpoint/adjacency evidence only.
- Do not mutate Layer 1 topology or graph identity.
- Do not build traces, circuits, rails, feature, runtime, solve or UV data.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import Mapping

from scaffold_core.core.evidence import Evidence
from scaffold_core.ids import ChainId, PatchChainId, PatchId, VertexId
from scaffold_core.layer_3_relations.model import (
    PatchAdjacency,
    PatchChainEndpointRelation,
    PatchChainEndpointRelationKind,
    PatchChainEndpointSample,
    ScaffoldEdge,
    ScaffoldNode,
    ScaffoldNodeIncidentEdgeRelation,
    ScaffoldNodeIncidentEdgeRelationKind,
    SharedChainPatchChainRelation,
    SharedChainPatchChainRelationKind,
)


NODE_INCIDENT_EDGE_POLICY_NAME = "scaffold_node_incident_edge_relation_v0"
SHARED_CHAIN_POLICY_NAME = "shared_chain_patch_chain_relation_v0"


def build_scaffold_graph_relations(
    scaffold_nodes: tuple[ScaffoldNode, ...],
    scaffold_edges: tuple[ScaffoldEdge, ...],
    endpoint_samples: tuple[PatchChainEndpointSample, ...],
    endpoint_relations: tuple[PatchChainEndpointRelation, ...],
    patch_adjacencies: Mapping[str, PatchAdjacency],
) -> tuple[
    tuple[ScaffoldNodeIncidentEdgeRelation, ...],
    tuple[SharedChainPatchChainRelation, ...],
]:
    """Build node-local edge-pair and cross-patch shared Chain relations."""

    edge_by_patch_chain_id = {
        edge.patch_chain_id: edge
        for edge in scaffold_edges
    }
    incident_edge_relations = build_scaffold_node_incident_edge_relations(
        scaffold_nodes,
        endpoint_samples,
        endpoint_relations,
        edge_by_patch_chain_id,
    )
    shared_chain_relations = build_shared_chain_patch_chain_relations(
        scaffold_edges,
        patch_adjacencies,
    )
    return incident_edge_relations, shared_chain_relations


def build_scaffold_node_incident_edge_relations(
    scaffold_nodes: tuple[ScaffoldNode, ...],
    endpoint_samples: tuple[PatchChainEndpointSample, ...],
    endpoint_relations: tuple[PatchChainEndpointRelation, ...],
    edge_by_patch_chain_id: Mapping[PatchChainId, ScaffoldEdge],
) -> tuple[ScaffoldNodeIncidentEdgeRelation, ...]:
    """Build node-local pair relations backed by endpoint relation evidence."""

    sample_by_id = {
        sample.id: sample
        for sample in endpoint_samples
    }
    node_by_vertex_id = _node_by_vertex_id(scaffold_nodes)
    relations: list[ScaffoldNodeIncidentEdgeRelation] = []
    seen_keys: set[tuple[str, str, str, str]] = set()
    for endpoint_relation in sorted(endpoint_relations, key=lambda item: item.id):
        first_sample = sample_by_id.get(endpoint_relation.first_sample_id)
        second_sample = sample_by_id.get(endpoint_relation.second_sample_id)
        if first_sample is None or second_sample is None:
            continue
        if first_sample.patch_chain_id == second_sample.patch_chain_id:
            continue
        first_edge = edge_by_patch_chain_id.get(first_sample.patch_chain_id)
        second_edge = edge_by_patch_chain_id.get(second_sample.patch_chain_id)
        if first_edge is None or second_edge is None:
            continue
        edge_pair = tuple(sorted((first_edge, second_edge), key=lambda edge: edge.id))
        node = node_by_vertex_id.get(endpoint_relation.vertex_id)
        if node is None or not _node_has_patch_chain_pair(
            node,
            first_sample.patch_chain_id,
            second_sample.patch_chain_id,
        ):
            continue
        seen_key = (node.id, edge_pair[0].id, edge_pair[1].id, endpoint_relation.id)
        if seen_key in seen_keys:
            continue
        seen_keys.add(seen_key)
        relations.append(_incident_edge_relation(node, edge_pair, endpoint_relation))
    return tuple(relations)


def build_shared_chain_patch_chain_relations(
    scaffold_edges: tuple[ScaffoldEdge, ...],
    patch_adjacencies: Mapping[str, PatchAdjacency],
) -> tuple[SharedChainPatchChainRelation, ...]:
    """Build cross-patch relation records for ScaffoldEdges sharing one Chain."""

    edges_by_chain_id: dict[ChainId, list[ScaffoldEdge]] = defaultdict(list)
    for edge in scaffold_edges:
        edges_by_chain_id[edge.chain_id].append(edge)

    adjacency_id_by_chain_and_patch_pair = _adjacency_id_by_chain_and_patch_pair(patch_adjacencies)
    relations: list[SharedChainPatchChainRelation] = []
    for chain_id in sorted(edges_by_chain_id, key=str):
        chain_edges = tuple(sorted(edges_by_chain_id[chain_id], key=lambda edge: edge.id))
        if len(chain_edges) != 2:
            continue
        for first_edge, second_edge in combinations(chain_edges, 2):
            if first_edge.patch_id == second_edge.patch_id:
                continue
            patch_pair = _patch_pair(first_edge.patch_id, second_edge.patch_id)
            relations.append(
                _shared_chain_relation(
                    first_edge,
                    second_edge,
                    adjacency_id_by_chain_and_patch_pair.get((chain_id, patch_pair)),
                )
            )
    return tuple(relations)


def _node_by_vertex_id(
    scaffold_nodes: tuple[ScaffoldNode, ...],
) -> dict[VertexId, ScaffoldNode]:
    node_by_vertex_id: dict[VertexId, ScaffoldNode] = {}
    for node in sorted(scaffold_nodes, key=lambda item: item.id):
        for vertex_id in node.vertex_ids:
            node_by_vertex_id[vertex_id] = node
    return node_by_vertex_id


def _node_has_patch_chain_pair(
    node: ScaffoldNode,
    first_patch_chain_id: PatchChainId,
    second_patch_chain_id: PatchChainId,
) -> bool:
    incident_patch_chain_ids = set(node.incident_patch_chain_ids)
    return first_patch_chain_id in incident_patch_chain_ids and second_patch_chain_id in incident_patch_chain_ids


def _incident_edge_relation(
    node: ScaffoldNode,
    edge_pair: tuple[ScaffoldEdge, ScaffoldEdge],
    endpoint_relation: PatchChainEndpointRelation,
) -> ScaffoldNodeIncidentEdgeRelation:
    first_edge, second_edge = edge_pair
    kind = _incident_edge_kind(endpoint_relation.kind)
    confidence = min(node.confidence, first_edge.confidence, second_edge.confidence, endpoint_relation.confidence)
    return ScaffoldNodeIncidentEdgeRelation(
        id=(
            "scaffold_node_incident_edge_relation:"
            f"{node.id}:{first_edge.id}:{second_edge.id}:{endpoint_relation.id}"
        ),
        kind=kind,
        policy=NODE_INCIDENT_EDGE_POLICY_NAME,
        scaffold_node_id=node.id,
        first_scaffold_edge_id=first_edge.id,
        second_scaffold_edge_id=second_edge.id,
        first_patch_chain_id=first_edge.patch_chain_id,
        second_patch_chain_id=second_edge.patch_chain_id,
        patch_chain_endpoint_relation_id=endpoint_relation.id,
        confidence=confidence,
        evidence=(_incident_edge_evidence(node, first_edge, second_edge, endpoint_relation, kind, confidence),),
    )


def _incident_edge_kind(
    endpoint_relation_kind: PatchChainEndpointRelationKind,
) -> ScaffoldNodeIncidentEdgeRelationKind:
    if endpoint_relation_kind is PatchChainEndpointRelationKind.CONTINUATION_CANDIDATE:
        return ScaffoldNodeIncidentEdgeRelationKind.CONTINUATION_CANDIDATE
    if endpoint_relation_kind is PatchChainEndpointRelationKind.CORNER_CONNECTOR:
        return ScaffoldNodeIncidentEdgeRelationKind.ORTHOGONAL_CORNER
    if endpoint_relation_kind is PatchChainEndpointRelationKind.OBLIQUE_CONNECTOR:
        return ScaffoldNodeIncidentEdgeRelationKind.OBLIQUE_CONNECTOR
    if endpoint_relation_kind is PatchChainEndpointRelationKind.AMBIGUOUS:
        return ScaffoldNodeIncidentEdgeRelationKind.SAME_RAY_AMBIGUOUS
    return ScaffoldNodeIncidentEdgeRelationKind.DEGRADED


def _incident_edge_evidence(
    node: ScaffoldNode,
    first_edge: ScaffoldEdge,
    second_edge: ScaffoldEdge,
    endpoint_relation: PatchChainEndpointRelation,
    kind: ScaffoldNodeIncidentEdgeRelationKind,
    confidence: float,
) -> Evidence:
    return Evidence(
        source="layer_3_relations.scaffold_graph_relations",
        summary="node-local ScaffoldEdge pair relation backed by PatchChainEndpointRelation",
        data={
            "policy": NODE_INCIDENT_EDGE_POLICY_NAME,
            "scaffold_node_id": node.id,
            "first_scaffold_edge_id": first_edge.id,
            "second_scaffold_edge_id": second_edge.id,
            "first_patch_chain_id": str(first_edge.patch_chain_id),
            "second_patch_chain_id": str(second_edge.patch_chain_id),
            "patch_chain_endpoint_relation_id": endpoint_relation.id,
            "endpoint_relation_kind": endpoint_relation.kind.value,
            "kind": kind.value,
            "confidence": confidence,
        },
    )


def _adjacency_id_by_chain_and_patch_pair(
    patch_adjacencies: Mapping[str, PatchAdjacency],
) -> dict[tuple[ChainId, tuple[PatchId, PatchId]], str]:
    return {
        (adjacency.chain_id, _patch_pair(adjacency.first_patch_id, adjacency.second_patch_id)): adjacency.id
        for adjacency in patch_adjacencies.values()
    }


def _shared_chain_relation(
    first_edge: ScaffoldEdge,
    second_edge: ScaffoldEdge,
    patch_adjacency_id: str | None,
) -> SharedChainPatchChainRelation:
    confidence = min(first_edge.confidence, second_edge.confidence)
    return SharedChainPatchChainRelation(
        id=f"shared_chain_patch_chain_relation:{first_edge.chain_id}:{first_edge.id}:{second_edge.id}",
        kind=SharedChainPatchChainRelationKind.CROSS_PATCH_SHARED_CHAIN,
        policy=SHARED_CHAIN_POLICY_NAME,
        chain_id=first_edge.chain_id,
        first_scaffold_edge_id=first_edge.id,
        second_scaffold_edge_id=second_edge.id,
        first_patch_chain_id=first_edge.patch_chain_id,
        second_patch_chain_id=second_edge.patch_chain_id,
        first_patch_id=first_edge.patch_id,
        second_patch_id=second_edge.patch_id,
        patch_adjacency_id=patch_adjacency_id,
        confidence=confidence,
        evidence=(_shared_chain_evidence(first_edge, second_edge, patch_adjacency_id, confidence),),
    )


def _shared_chain_evidence(
    first_edge: ScaffoldEdge,
    second_edge: ScaffoldEdge,
    patch_adjacency_id: str | None,
    confidence: float,
) -> Evidence:
    return Evidence(
        source="layer_3_relations.scaffold_graph_relations",
        summary="cross-patch ScaffoldEdges share one final Chain",
        data={
            "policy": SHARED_CHAIN_POLICY_NAME,
            "chain_id": str(first_edge.chain_id),
            "first_scaffold_edge_id": first_edge.id,
            "second_scaffold_edge_id": second_edge.id,
            "first_patch_chain_id": str(first_edge.patch_chain_id),
            "second_patch_chain_id": str(second_edge.patch_chain_id),
            "first_patch_id": str(first_edge.patch_id),
            "second_patch_id": str(second_edge.patch_id),
            "patch_adjacency_id": patch_adjacency_id,
            "confidence": confidence,
        },
    )


def _patch_pair(first_patch_id: PatchId, second_patch_id: PatchId) -> tuple[PatchId, PatchId]:
    return tuple(sorted((first_patch_id, second_patch_id), key=str))
