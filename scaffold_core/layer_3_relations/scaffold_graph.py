"""
Layer: 3 - Relations

Rules:
- Build connectivity-only graph records from final PatchChains and ScaffoldNodes.
- Use existing ScaffoldNode grouping for endpoint node ids.
- Do not mutate Layer 1 topology or choose path continuations.
- Do not build feature, runtime, solve or UV data.
"""

from __future__ import annotations

from scaffold_core.core.evidence import Evidence
from scaffold_core.ids import PatchChainId, VertexId
from scaffold_core.layer_1_topology.model import PatchChain, SurfaceModel
from scaffold_core.layer_1_topology.queries import patch_chain_vertices
from scaffold_core.layer_3_relations.model import ScaffoldEdge, ScaffoldGraph, ScaffoldNode


POLICY_NAME = "scaffold_graph_v0"


def build_scaffold_graph(
    topology: SurfaceModel,
    scaffold_nodes: tuple[ScaffoldNode, ...],
) -> tuple[tuple[ScaffoldEdge, ...], ScaffoldGraph]:
    """Build graph edges for final PatchChains and one connectivity graph."""

    node_id_by_vertex_id = _node_id_by_vertex_id(scaffold_nodes)
    edges = tuple(
        _edge_for_patch_chain(topology, patch_chain, node_id_by_vertex_id, scaffold_nodes)
        for patch_chain in sorted(topology.patch_chains.values(), key=lambda item: str(item.id))
    )
    graph = ScaffoldGraph(
        id=f"scaffold_graph:{topology.id}",
        node_ids=tuple(node.id for node in sorted(scaffold_nodes, key=lambda item: item.id)),
        edge_ids=tuple(edge.id for edge in edges),
        confidence=_graph_confidence(scaffold_nodes, edges),
        evidence=(_graph_evidence(topology, scaffold_nodes, edges),),
    )
    return edges, graph


def _node_id_by_vertex_id(scaffold_nodes: tuple[ScaffoldNode, ...]) -> dict[VertexId, str]:
    node_id_by_vertex_id: dict[VertexId, str] = {}
    for node in sorted(scaffold_nodes, key=lambda item: item.id):
        for vertex_id in node.vertex_ids:
            node_id_by_vertex_id[vertex_id] = node.id
    return node_id_by_vertex_id


def _edge_for_patch_chain(
    topology: SurfaceModel,
    patch_chain: PatchChain,
    node_id_by_vertex_id: dict[VertexId, str],
    scaffold_nodes: tuple[ScaffoldNode, ...],
) -> ScaffoldEdge:
    start_vertex_id, end_vertex_id = patch_chain_vertices(topology, patch_chain.id)
    start_node_id = node_id_by_vertex_id[start_vertex_id]
    end_node_id = node_id_by_vertex_id[end_vertex_id]
    node_confidence = _endpoint_node_confidence(scaffold_nodes, start_node_id, end_node_id)
    return ScaffoldEdge(
        id=_edge_id(patch_chain.id),
        patch_chain_id=patch_chain.id,
        chain_id=patch_chain.chain_id,
        patch_id=patch_chain.patch_id,
        loop_id=patch_chain.loop_id,
        start_scaffold_node_id=start_node_id,
        end_scaffold_node_id=end_node_id,
        confidence=node_confidence,
        evidence=(_edge_evidence(patch_chain, start_vertex_id, end_vertex_id),),
    )


def _endpoint_node_confidence(
    scaffold_nodes: tuple[ScaffoldNode, ...],
    start_node_id: str,
    end_node_id: str,
) -> float:
    confidence_by_node_id = {
        node.id: node.confidence
        for node in scaffold_nodes
    }
    return min(confidence_by_node_id[start_node_id], confidence_by_node_id[end_node_id])


def _graph_confidence(
    scaffold_nodes: tuple[ScaffoldNode, ...],
    scaffold_edges: tuple[ScaffoldEdge, ...],
) -> float:
    confidence_values = [node.confidence for node in scaffold_nodes]
    confidence_values.extend(edge.confidence for edge in scaffold_edges)
    if not confidence_values:
        return 0.0
    return min(confidence_values)


def _edge_id(patch_chain_id: PatchChainId) -> str:
    return f"scaffold_edge:{patch_chain_id}"


def _edge_evidence(
    patch_chain: PatchChain,
    start_vertex_id: VertexId,
    end_vertex_id: VertexId,
) -> Evidence:
    return Evidence(
        source="layer_3_relations.scaffold_graph",
        summary="ScaffoldEdge is a graph-level view of one final PatchChain",
        data={
            "policy": POLICY_NAME,
            "edge_source": "FINAL_PATCH_CHAIN",
            "patch_chain_id": str(patch_chain.id),
            "chain_id": str(patch_chain.chain_id),
            "patch_id": str(patch_chain.patch_id),
            "loop_id": str(patch_chain.loop_id),
            "start_vertex_id": str(start_vertex_id),
            "end_vertex_id": str(end_vertex_id),
            "endpoint_node_policy": "SCAFFOLD_NODE_GROUPING",
        },
    )


def _graph_evidence(
    topology: SurfaceModel,
    scaffold_nodes: tuple[ScaffoldNode, ...],
    scaffold_edges: tuple[ScaffoldEdge, ...],
) -> Evidence:
    return Evidence(
        source="layer_3_relations.scaffold_graph",
        summary="ScaffoldGraph is connectivity-only over existing nodes and edges",
        data={
            "policy": POLICY_NAME,
            "node_count": len(scaffold_nodes),
            "edge_count": len(scaffold_edges),
            "patch_chain_count": len(topology.patch_chains),
            "edge_source": "FINAL_PATCH_CHAIN",
        },
    )
