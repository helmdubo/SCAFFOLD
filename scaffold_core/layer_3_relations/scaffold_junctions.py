"""
Layer: 3 - Relations

Rules:
- Classify ScaffoldJunction overlays on existing ScaffoldNodes only.
- Use final PatchChain-backed ScaffoldEdges as evidence.
- Do not mutate Layer 1 topology or ScaffoldNode grouping.
- Do not build traces, circuits, rails, feature, runtime, solve or UV data.
"""

from __future__ import annotations

from collections import defaultdict

from scaffold_core.core.evidence import Evidence
from scaffold_core.ids import ChainId, PatchId
from scaffold_core.layer_3_relations.model import (
    ScaffoldEdge,
    ScaffoldJunction,
    ScaffoldJunctionKind,
    ScaffoldNode,
)


POLICY_NAME = "scaffold_junction_self_seam_v0"


def build_scaffold_junctions(
    scaffold_nodes: tuple[ScaffoldNode, ...],
    scaffold_edges: tuple[ScaffoldEdge, ...],
) -> tuple[ScaffoldJunction, ...]:
    """Classify SELF_SEAM overlays for existing ScaffoldNodes."""

    edge_ids_by_node_id = _edge_ids_by_node_id(scaffold_edges)
    edge_by_id = {edge.id: edge for edge in scaffold_edges}
    junctions: list[ScaffoldJunction] = []
    for node in sorted(scaffold_nodes, key=lambda item: item.id):
        grouped_edge_ids = _self_seam_edge_ids_by_chain_and_patch(
            edge_ids_by_node_id.get(node.id, ()),
            edge_by_id,
        )
        for (chain_id, patch_id), edge_ids in sorted(
            grouped_edge_ids.items(),
            key=lambda item: (str(item[0][0]), str(item[0][1])),
        ):
            if len(edge_ids) < 2:
                continue
            edges = tuple(edge_by_id[edge_id] for edge_id in edge_ids)
            junctions.append(_self_seam_junction(node, chain_id, patch_id, edges))
    return tuple(junctions)


def _edge_ids_by_node_id(scaffold_edges: tuple[ScaffoldEdge, ...]) -> dict[str, tuple[str, ...]]:
    edge_ids_by_node_id: dict[str, set[str]] = defaultdict(set)
    for edge in scaffold_edges:
        edge_ids_by_node_id[edge.start_scaffold_node_id].add(edge.id)
        edge_ids_by_node_id[edge.end_scaffold_node_id].add(edge.id)
    return {
        node_id: tuple(sorted(edge_ids))
        for node_id, edge_ids in edge_ids_by_node_id.items()
    }


def _self_seam_edge_ids_by_chain_and_patch(
    edge_ids: tuple[str, ...],
    edge_by_id: dict[str, ScaffoldEdge],
) -> dict[tuple[ChainId, PatchId], tuple[str, ...]]:
    grouped: dict[tuple[ChainId, PatchId], list[str]] = defaultdict(list)
    for edge_id in edge_ids:
        edge = edge_by_id[edge_id]
        grouped[(edge.chain_id, edge.patch_id)].append(edge.id)
    return {
        key: tuple(sorted(value))
        for key, value in grouped.items()
    }


def _self_seam_junction(
    node: ScaffoldNode,
    chain_id: ChainId,
    patch_id: PatchId,
    edges: tuple[ScaffoldEdge, ...],
) -> ScaffoldJunction:
    edge_ids = tuple(edge.id for edge in edges)
    patch_chain_ids = tuple(edge.patch_chain_id for edge in edges)
    return ScaffoldJunction(
        id=_junction_id(node.id, chain_id, patch_id),
        kind=ScaffoldJunctionKind.SELF_SEAM,
        policy=POLICY_NAME,
        scaffold_node_id=node.id,
        matched_chain_id=chain_id,
        patch_id=patch_id,
        scaffold_edge_ids=edge_ids,
        patch_chain_ids=patch_chain_ids,
        confidence=min((node.confidence, *(edge.confidence for edge in edges))),
        evidence=(_self_seam_evidence(node, chain_id, patch_id, edges),),
    )


def _junction_id(node_id: str, chain_id: ChainId, patch_id: PatchId) -> str:
    return f"scaffold_junction:self_seam:{node_id}:{chain_id}:{patch_id}"


def _self_seam_evidence(
    node: ScaffoldNode,
    chain_id: ChainId,
    patch_id: PatchId,
    edges: tuple[ScaffoldEdge, ...],
) -> Evidence:
    return Evidence(
        source="layer_3_relations.scaffold_junctions",
        summary="SELF_SEAM classifies one existing ScaffoldNode by repeated Chain/Patch incidence",
        data={
            "policy": POLICY_NAME,
            "scaffold_node_id": node.id,
            "matched_chain_id": str(chain_id),
            "patch_id": str(patch_id),
            "scaffold_edge_ids": tuple(edge.id for edge in edges),
            "patch_chain_ids": tuple(str(edge.patch_chain_id) for edge in edges),
            "confidence": min((node.confidence, *(edge.confidence for edge in edges))),
        },
    )
