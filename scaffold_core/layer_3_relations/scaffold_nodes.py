"""
Layer: 3 - Relations

Rules:
- Build graph-level ScaffoldNode records from LoopCorner and endpoint evidence.
- Group materialized topology Vertex occurrences by source-vertex provenance.
- Do not mutate Layer 1 topology or create downstream graph structures.
- Do not build feature, runtime, solve or UV data.
"""

from __future__ import annotations

from scaffold_core.core.evidence import Evidence
from scaffold_core.ids import PatchChainId, PatchId, SourceVertexId, VertexId
from scaffold_core.layer_1_topology.model import SurfaceModel
from scaffold_core.layer_3_relations.model import (
    LoopCorner,
    PatchChainEndpointRelation,
    PatchChainEndpointSample,
    ScaffoldNode,
)


POLICY_NAME = "scaffold_node_v0"


def build_scaffold_nodes(
    topology: SurfaceModel,
    loop_corners: tuple[LoopCorner, ...],
    endpoint_samples: tuple[PatchChainEndpointSample, ...],
    endpoint_relations: tuple[PatchChainEndpointRelation, ...],
) -> tuple[ScaffoldNode, ...]:
    """Build graph-level nodes from corner and endpoint evidence."""

    vertex_ids = _relevant_vertex_ids(loop_corners, endpoint_samples, endpoint_relations)
    groups: dict[tuple[str, ...], set[VertexId]] = {}
    for vertex_id in vertex_ids:
        groups.setdefault(_group_key(topology, vertex_id), set()).add(vertex_id)

    corners_by_vertex = _indexed_items_by_vertex(loop_corners)
    samples_by_vertex = _indexed_items_by_vertex(endpoint_samples)
    relations_by_vertex = _indexed_items_by_vertex(endpoint_relations)
    nodes = [
        _node_for_vertices(
            topology,
            tuple(sorted(group_vertex_ids, key=str)),
            corners_by_vertex,
            samples_by_vertex,
            relations_by_vertex,
        )
        for group_vertex_ids in groups.values()
    ]
    return tuple(sorted(nodes, key=lambda node: node.id))


def _relevant_vertex_ids(
    loop_corners: tuple[LoopCorner, ...],
    endpoint_samples: tuple[PatchChainEndpointSample, ...],
    endpoint_relations: tuple[PatchChainEndpointRelation, ...],
) -> tuple[VertexId, ...]:
    vertex_ids = {
        corner.vertex_id
        for corner in loop_corners
    }
    return tuple(sorted(vertex_ids, key=str))


def _group_key(topology: SurfaceModel, vertex_id: VertexId) -> tuple[str, ...]:
    source_vertex_ids = _source_vertex_ids_for_vertex(topology, vertex_id)
    if source_vertex_ids:
        return ("source", *(str(source_vertex_id) for source_vertex_id in source_vertex_ids))
    return ("vertex", str(vertex_id))


def _indexed_items_by_vertex(items: tuple) -> dict[VertexId, list[tuple[int, object]]]:
    # (input position, item) per vertex id, so a node's items keep input order.
    by_vertex: dict[VertexId, list[tuple[int, object]]] = {}
    for index, item in enumerate(items):
        by_vertex.setdefault(item.vertex_id, []).append((index, item))
    return by_vertex


def _items_for_vertices(
    items_by_vertex: dict[VertexId, list[tuple[int, object]]],
    vertex_ids: tuple[VertexId, ...],
) -> list:
    indexed = [pair for vertex_id in vertex_ids for pair in items_by_vertex.get(vertex_id, ())]
    return [item for _, item in sorted(indexed, key=lambda pair: pair[0])]


def _node_for_vertices(
    topology: SurfaceModel,
    vertex_ids: tuple[VertexId, ...],
    corners_by_vertex: dict[VertexId, list[tuple[int, LoopCorner]]],
    samples_by_vertex: dict[VertexId, list[tuple[int, PatchChainEndpointSample]]],
    relations_by_vertex: dict[VertexId, list[tuple[int, PatchChainEndpointRelation]]],
) -> ScaffoldNode:
    node_corners = tuple(
        sorted(
            _items_for_vertices(corners_by_vertex, vertex_ids),
            key=lambda corner: corner.id,
        )
    )
    node_samples = tuple(
        sorted(
            _items_for_vertices(samples_by_vertex, vertex_ids),
            key=lambda sample: sample.id,
        )
    )
    node_relations = tuple(
        sorted(
            _items_for_vertices(relations_by_vertex, vertex_ids),
            key=lambda relation: relation.id,
        )
    )
    source_vertex_ids = _source_vertex_ids_for_vertices(topology, vertex_ids)
    incident_patch_chain_ids = _incident_patch_chain_ids(node_corners, node_samples)
    patch_ids = _patch_ids(node_corners, node_samples)

    return ScaffoldNode(
        id=_node_id(vertex_ids, source_vertex_ids),
        vertex_ids=vertex_ids,
        source_vertex_ids=source_vertex_ids,
        loop_corner_ids=tuple(corner.id for corner in node_corners),
        patch_chain_endpoint_sample_ids=tuple(sample.id for sample in node_samples),
        patch_chain_endpoint_relation_ids=tuple(relation.id for relation in node_relations),
        incident_patch_chain_ids=incident_patch_chain_ids,
        patch_ids=patch_ids,
        confidence=_confidence(node_corners, node_samples, node_relations),
        evidence=(
            _evidence(
                vertex_ids,
                source_vertex_ids,
                len(node_corners),
                len(node_samples),
                len(node_relations),
            ),
        ),
    )


def _source_vertex_ids_for_vertices(
    topology: SurfaceModel,
    vertex_ids: tuple[VertexId, ...],
) -> tuple[SourceVertexId, ...]:
    source_vertex_ids: set[SourceVertexId] = set()
    for vertex_id in vertex_ids:
        source_vertex_ids.update(_source_vertex_ids_for_vertex(topology, vertex_id))
    return tuple(sorted(source_vertex_ids, key=str))


def _source_vertex_ids_for_vertex(
    topology: SurfaceModel,
    vertex_id: VertexId,
) -> tuple[SourceVertexId, ...]:
    vertex = topology.vertices.get(vertex_id)
    if vertex is None:
        return ()
    return tuple(sorted(vertex.source_vertex_ids, key=str))


def _incident_patch_chain_ids(
    loop_corners: tuple[LoopCorner, ...],
    endpoint_samples: tuple[PatchChainEndpointSample, ...],
) -> tuple[PatchChainId, ...]:
    patch_chain_ids: set[PatchChainId] = set()
    for corner in loop_corners:
        patch_chain_ids.add(corner.previous_patch_chain_id)
        patch_chain_ids.add(corner.next_patch_chain_id)
    patch_chain_ids.update(sample.patch_chain_id for sample in endpoint_samples)
    return tuple(sorted(patch_chain_ids, key=str))


def _patch_ids(
    loop_corners: tuple[LoopCorner, ...],
    endpoint_samples: tuple[PatchChainEndpointSample, ...],
) -> tuple[PatchId, ...]:
    patch_ids = {
        corner.patch_id
        for corner in loop_corners
    }
    patch_ids.update(sample.patch_id for sample in endpoint_samples)
    return tuple(sorted(patch_ids, key=str))


def _confidence(
    loop_corners: tuple[LoopCorner, ...],
    endpoint_samples: tuple[PatchChainEndpointSample, ...],
    endpoint_relations: tuple[PatchChainEndpointRelation, ...],
) -> float:
    confidence_values = [
        sample.confidence
        for sample in endpoint_samples
    ]
    confidence_values.extend(relation.confidence for relation in endpoint_relations)
    if confidence_values:
        return min(confidence_values)
    if loop_corners:
        return 1.0
    return 0.0


def _node_id(
    vertex_ids: tuple[VertexId, ...],
    source_vertex_ids: tuple[SourceVertexId, ...],
) -> str:
    if source_vertex_ids:
        return "scaffold_node:source:" + "+".join(str(source_vertex_id) for source_vertex_id in source_vertex_ids)
    return "scaffold_node:vertex:" + "+".join(str(vertex_id) for vertex_id in vertex_ids)


def _evidence(
    vertex_ids: tuple[VertexId, ...],
    source_vertex_ids: tuple[SourceVertexId, ...],
    loop_corner_count: int,
    endpoint_sample_count: int,
    endpoint_relation_count: int,
) -> Evidence:
    return Evidence(
        source="layer_3_relations.scaffold_nodes",
        summary="ScaffoldNode assembled from LoopCorner and endpoint evidence",
        data={
            "policy": POLICY_NAME,
            "grouping": "SOURCE_VERTEX" if source_vertex_ids else "TOPOLOGY_VERTEX",
            "vertex_ids": [str(vertex_id) for vertex_id in vertex_ids],
            "source_vertex_ids": [str(source_vertex_id) for source_vertex_id in source_vertex_ids],
            "loop_corner_count": loop_corner_count,
            "endpoint_sample_count": endpoint_sample_count,
            "endpoint_relation_count": endpoint_relation_count,
        },
    )
