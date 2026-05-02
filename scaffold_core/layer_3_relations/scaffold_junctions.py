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
from scaffold_core.ids import ChainId, PatchChainId, PatchId
from scaffold_core.layer_3_relations.model import (
    ScaffoldEdge,
    ScaffoldJunction,
    ScaffoldJunctionKind,
    ScaffoldNode,
)


SELF_SEAM_POLICY_NAME = "scaffold_junction_self_seam_v0"
CROSS_PATCH_POLICY_NAME = "scaffold_junction_cross_patch_v0"


def build_scaffold_junctions(
    scaffold_nodes: tuple[ScaffoldNode, ...],
    scaffold_edges: tuple[ScaffoldEdge, ...],
) -> tuple[ScaffoldJunction, ...]:
    """Classify implemented junction overlays for existing ScaffoldNodes."""

    edge_by_id = {edge.id: edge for edge in scaffold_edges}
    edge_by_patch_chain_id = {
        edge.patch_chain_id: edge
        for edge in scaffold_edges
    }
    junctions: list[ScaffoldJunction] = []
    for node in sorted(scaffold_nodes, key=lambda item: item.id):
        incident_edges = _incident_edges(node, edge_by_patch_chain_id)
        grouped_edge_ids = _self_seam_edge_ids_by_chain_and_patch(
            tuple(edge.id for edge in incident_edges),
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
        if _is_cross_patch(incident_edges):
            junctions.append(_cross_patch_junction(node, incident_edges))
    return tuple(junctions)


def _incident_edges(
    node: ScaffoldNode,
    edge_by_patch_chain_id: dict[PatchChainId, ScaffoldEdge],
) -> tuple[ScaffoldEdge, ...]:
    edges = [
        edge_by_patch_chain_id[patch_chain_id]
        for patch_chain_id in node.incident_patch_chain_ids
        if patch_chain_id in edge_by_patch_chain_id
    ]
    return tuple(sorted(edges, key=lambda edge: edge.id))


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
        policy=SELF_SEAM_POLICY_NAME,
        scaffold_node_id=node.id,
        matched_chain_id=chain_id,
        patch_id=patch_id,
        chain_ids=(chain_id,),
        patch_ids=(patch_id,),
        loop_ids=_loop_ids(edges),
        scaffold_edge_ids=edge_ids,
        patch_chain_ids=patch_chain_ids,
        confidence=min((node.confidence, *(edge.confidence for edge in edges))),
        evidence=(_self_seam_evidence(node, chain_id, patch_id, edges),),
    )


def _junction_id(node_id: str, chain_id: ChainId, patch_id: PatchId) -> str:
    return f"scaffold_junction:self_seam:{node_id}:{chain_id}:{patch_id}"


def _is_cross_patch(edges: tuple[ScaffoldEdge, ...]) -> bool:
    return len({edge.patch_id for edge in edges}) > 1


def _cross_patch_junction(
    node: ScaffoldNode,
    edges: tuple[ScaffoldEdge, ...],
) -> ScaffoldJunction:
    edge_ids = tuple(edge.id for edge in edges)
    patch_chain_ids = tuple(edge.patch_chain_id for edge in edges)
    chain_ids = _chain_ids(edges)
    patch_ids = _patch_ids(edges)
    loop_ids = _loop_ids(edges)
    return ScaffoldJunction(
        id=f"scaffold_junction:cross_patch:{node.id}",
        kind=ScaffoldJunctionKind.CROSS_PATCH,
        policy=CROSS_PATCH_POLICY_NAME,
        scaffold_node_id=node.id,
        matched_chain_id=None,
        patch_id=None,
        chain_ids=chain_ids,
        patch_ids=patch_ids,
        loop_ids=loop_ids,
        scaffold_edge_ids=edge_ids,
        patch_chain_ids=patch_chain_ids,
        confidence=min((node.confidence, *(edge.confidence for edge in edges))),
        evidence=(_cross_patch_evidence(node, edges),),
    )


def _chain_ids(edges: tuple[ScaffoldEdge, ...]) -> tuple[ChainId, ...]:
    return tuple(sorted({edge.chain_id for edge in edges}, key=str))


def _patch_ids(edges: tuple[ScaffoldEdge, ...]) -> tuple[PatchId, ...]:
    return tuple(sorted({edge.patch_id for edge in edges}, key=str))


def _loop_ids(edges: tuple[ScaffoldEdge, ...]):
    return tuple(sorted({edge.loop_id for edge in edges}, key=str))


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
            "policy": SELF_SEAM_POLICY_NAME,
            "scaffold_node_id": node.id,
            "matched_chain_id": str(chain_id),
            "patch_id": str(patch_id),
            "chain_ids": (str(chain_id),),
            "patch_ids": (str(patch_id),),
            "loop_ids": tuple(str(loop_id) for loop_id in _loop_ids(edges)),
            "scaffold_edge_ids": tuple(edge.id for edge in edges),
            "patch_chain_ids": tuple(str(edge.patch_chain_id) for edge in edges),
            "confidence": min((node.confidence, *(edge.confidence for edge in edges))),
        },
    )


def _cross_patch_evidence(
    node: ScaffoldNode,
    edges: tuple[ScaffoldEdge, ...],
) -> Evidence:
    return Evidence(
        source="layer_3_relations.scaffold_junctions",
        summary="CROSS_PATCH classifies one existing ScaffoldNode by multi-Patch ScaffoldEdge incidence",
        data={
            "policy": CROSS_PATCH_POLICY_NAME,
            "classification_policy": CROSS_PATCH_POLICY_NAME,
            "scaffold_node_id": node.id,
            "incident_scaffold_edge_ids": tuple(edge.id for edge in edges),
            "scaffold_edge_ids": tuple(edge.id for edge in edges),
            "patch_chain_ids": tuple(str(edge.patch_chain_id) for edge in edges),
            "chain_ids": tuple(str(chain_id) for chain_id in _chain_ids(edges)),
            "patch_ids": tuple(str(patch_id) for patch_id in _patch_ids(edges)),
            "loop_ids": tuple(str(loop_id) for loop_id in _loop_ids(edges)),
            "confidence": min((node.confidence, *(edge.confidence for edge in edges))),
        },
    )
