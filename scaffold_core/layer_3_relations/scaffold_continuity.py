"""
Layer: 3 - Relations

Rules:
- Build continuity-family evidence over existing ScaffoldEdge records.
- Consume ScaffoldNodeIncidentEdgeRelation records without changing their kinds.
- Do not choose trace paths, circuits, rails, continuation targets, solve or UV data.
"""

from __future__ import annotations

from collections import defaultdict

from scaffold_core.core.evidence import Evidence
from scaffold_core.layer_3_relations.model import (
    ScaffoldContinuityComponent,
    ScaffoldEdge,
    ScaffoldNodeIncidentEdgeRelation,
    ScaffoldNodeIncidentEdgeRelationKind,
)


PROPAGATION_POLICY_NAME = "scaffold_continuity_component_v0"
PROPAGATING_KIND = ScaffoldNodeIncidentEdgeRelationKind.SURFACE_CONTINUATION_CANDIDATE
AMBIGUOUS_KIND = ScaffoldNodeIncidentEdgeRelationKind.SAME_RAY_AMBIGUOUS


def build_scaffold_continuity_components(
    scaffold_edges: tuple[ScaffoldEdge, ...],
    incident_relations: tuple[ScaffoldNodeIncidentEdgeRelation, ...],
) -> tuple[ScaffoldContinuityComponent, ...]:
    """Build one continuity component assignment for every ScaffoldEdge."""

    edge_by_id = {
        edge.id: edge
        for edge in scaffold_edges
    }
    parent = {
        edge.id: edge.id
        for edge in scaffold_edges
    }

    valid_relations = tuple(
        relation
        for relation in incident_relations
        if (
            relation.first_scaffold_edge_id in edge_by_id
            and relation.second_scaffold_edge_id in edge_by_id
        )
    )
    for relation in sorted(valid_relations, key=lambda item: item.id):
        if relation.kind is PROPAGATING_KIND:
            _union(parent, relation.first_scaffold_edge_id, relation.second_scaffold_edge_id)

    component_edge_ids: dict[str, list[str]] = defaultdict(list)
    for edge in sorted(scaffold_edges, key=lambda item: item.id):
        component_edge_ids[_find(parent, edge.id)].append(edge.id)

    component_ids_by_edge_id: dict[str, str] = {}
    for index, edge_ids in enumerate(sorted(
        (tuple(edge_ids) for edge_ids in component_edge_ids.values()),
        key=lambda item: item,
    )):
        component_id = f"scaffold_continuity_component:{index}"
        for edge_id in edge_ids:
            component_ids_by_edge_id[edge_id] = component_id

    relations_by_component_id: dict[str, list[ScaffoldNodeIncidentEdgeRelation]] = defaultdict(list)
    for relation in valid_relations:
        first_component_id = component_ids_by_edge_id[relation.first_scaffold_edge_id]
        second_component_id = component_ids_by_edge_id[relation.second_scaffold_edge_id]
        relations_by_component_id[first_component_id].append(relation)
        if first_component_id != second_component_id:
            relations_by_component_id[second_component_id].append(relation)

    components: list[ScaffoldContinuityComponent] = []
    for edge_ids in sorted((tuple(edge_ids) for edge_ids in component_edge_ids.values()), key=lambda item: item):
        component_id = component_ids_by_edge_id[edge_ids[0]]
        component_relations = tuple(sorted(relations_by_component_id.get(component_id, ()), key=lambda item: item.id))
        propagating_relation_ids = tuple(
            relation.id
            for relation in component_relations
            if relation.kind is PROPAGATING_KIND
        )
        ambiguous_relation_ids = _ambiguous_relation_ids(component_relations)
        blocked_relation_ids = tuple(
            relation.id
            for relation in component_relations
            if relation.kind is not PROPAGATING_KIND
        )
        node_ids = _component_node_ids(edge_ids, edge_by_id)
        confidence = _component_confidence(edge_ids, edge_by_id, component_relations)
        components.append(
            ScaffoldContinuityComponent(
                id=component_id,
                scaffold_edge_ids=edge_ids,
                scaffold_node_ids=node_ids,
                propagating_incident_relation_ids=propagating_relation_ids,
                ambiguous_incident_relation_ids=ambiguous_relation_ids,
                blocked_incident_relation_ids=blocked_relation_ids,
                propagation_policy=PROPAGATION_POLICY_NAME,
                is_ambiguous=bool(ambiguous_relation_ids),
                confidence=confidence,
                evidence=(_evidence(
                    component_id,
                    edge_ids,
                    node_ids,
                    propagating_relation_ids,
                    ambiguous_relation_ids,
                    blocked_relation_ids,
                    confidence,
                ),),
            )
        )
    return tuple(components)


def _find(parent: dict[str, str], edge_id: str) -> str:
    root = edge_id
    while parent[root] != root:
        root = parent[root]
    while parent[edge_id] != edge_id:
        next_edge_id = parent[edge_id]
        parent[edge_id] = root
        edge_id = next_edge_id
    return root


def _union(parent: dict[str, str], first_edge_id: str, second_edge_id: str) -> None:
    first_root = _find(parent, first_edge_id)
    second_root = _find(parent, second_edge_id)
    if first_root == second_root:
        return
    first_parent, second_parent = sorted((first_root, second_root))
    parent[second_parent] = first_parent


def _ambiguous_relation_ids(
    relations: tuple[ScaffoldNodeIncidentEdgeRelation, ...],
) -> tuple[str, ...]:
    ambiguous_ids = {
        relation.id
        for relation in relations
        if relation.kind is AMBIGUOUS_KIND
    }
    propagating_by_node_id: dict[str, list[str]] = defaultdict(list)
    for relation in relations:
        if relation.kind is PROPAGATING_KIND:
            propagating_by_node_id[relation.scaffold_node_id].append(relation.id)
    for relation_ids in propagating_by_node_id.values():
        if len(relation_ids) > 1:
            ambiguous_ids.update(relation_ids)
    return tuple(sorted(ambiguous_ids))


def _component_node_ids(
    edge_ids: tuple[str, ...],
    edge_by_id: dict[str, ScaffoldEdge],
) -> tuple[str, ...]:
    node_ids: set[str] = set()
    for edge_id in edge_ids:
        edge = edge_by_id[edge_id]
        node_ids.add(edge.start_scaffold_node_id)
        node_ids.add(edge.end_scaffold_node_id)
    return tuple(sorted(node_ids))


def _component_confidence(
    edge_ids: tuple[str, ...],
    edge_by_id: dict[str, ScaffoldEdge],
    relations: tuple[ScaffoldNodeIncidentEdgeRelation, ...],
) -> float:
    confidence_values = [
        edge_by_id[edge_id].confidence
        for edge_id in edge_ids
    ]
    confidence_values.extend(relation.confidence for relation in relations)
    return min(confidence_values) if confidence_values else 0.0


def _evidence(
    component_id: str,
    edge_ids: tuple[str, ...],
    node_ids: tuple[str, ...],
    propagating_relation_ids: tuple[str, ...],
    ambiguous_relation_ids: tuple[str, ...],
    blocked_relation_ids: tuple[str, ...],
    confidence: float,
) -> Evidence:
    return Evidence(
        source="layer_3_relations.scaffold_continuity",
        summary="continuity-family component over existing ScaffoldEdges",
        data={
            "policy": PROPAGATION_POLICY_NAME,
            "component_id": component_id,
            "scaffold_edge_ids": list(edge_ids),
            "scaffold_node_ids": list(node_ids),
            "propagating_incident_relation_ids": list(propagating_relation_ids),
            "ambiguous_incident_relation_ids": list(ambiguous_relation_ids),
            "blocked_incident_relation_ids": list(blocked_relation_ids),
            "propagating_kind": PROPAGATING_KIND.value,
            "confidence": confidence,
        },
    )
