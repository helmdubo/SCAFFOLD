"""
Layer: pipeline

Rules:
- Owns debug/inspection orchestration for G1 pipeline data.
- May import layers.
- Does not contain topology, geometry, relation, feature, or runtime logic.
- Does not import Blender directly; Blender mesh reading stays in Layer 0.
"""

from __future__ import annotations

from typing import Any

from scaffold_core.layer_0_source.blender_io import read_source_mesh_from_blender
from scaffold_core.layer_0_source.snapshot import SourceMeshSnapshot
from scaffold_core.layer_1_topology.build import build_topology_snapshot
from scaffold_core.layer_1_topology.invariants import validate_topology
from scaffold_core.layer_1_topology.model import PatchChain, SurfaceModel
from scaffold_core.layer_1_topology.queries import patch_chain_vertices, patch_chains_for_chain
from scaffold_core.layer_2_geometry.facts import GeometryFactSnapshot, Vector3
from scaffold_core.layer_3_relations.model import RelationSnapshot
from scaffold_core.pipeline.context import PipelineContext


InspectionDict = dict[str, object]
DIRECTION_STABLE_EPSILON = 1.0e-9


def inspect_pipeline_context(context: PipelineContext, detail: str = "compact") -> InspectionDict:
    """Return JSON-serializable inspection data for available pipeline snapshots."""

    report: InspectionDict = {}
    if context.topology_snapshot is not None and detail == "full":
        report.update(topology_tree_to_dict(context.topology_snapshot, context.source_snapshot))
    if context.geometry_facts is not None:
        report["geometry"] = geometry_summary_to_dict(context.geometry_facts, detail=detail)
    if context.relation_snapshot is not None:
        report["relations"] = relation_summary_to_dict(context.relation_snapshot, detail=detail)
    if (
        detail == "full"
        and context.topology_snapshot is not None
        and context.geometry_facts is not None
        and context.relation_snapshot is not None
        and context.relation_snapshot.scaffold_graph is not None
    ):
        report["scaffold_graph_overlay"] = scaffold_graph_overlay_to_dict(
            context.topology_snapshot,
            context.geometry_facts,
            context.relation_snapshot,
        )
    report["diagnostics"] = _diagnostics_to_list(context)
    return report


def topology_tree_to_dict(
    model: SurfaceModel,
    source: SourceMeshSnapshot | None = None,
) -> InspectionDict:
    """Return nested SurfaceModel -> Shell -> Patch -> Loop -> PatchChain data."""

    return {
        "surface_model": {
            "id": str(model.id),
            "shells": [
                {
                    "id": str(shell.id),
                    "patches": [
                        _patch_to_dict(model, patch_id, source)
                        for patch_id in sorted(shell.patch_ids, key=str)
                    ],
                }
                for shell in sorted(model.shells.values(), key=lambda item: str(item.id))
            ],
        }
    }


def geometry_summary_to_dict(geometry: GeometryFactSnapshot, detail: str = "compact") -> InspectionDict:
    """Return compact geometry fact summary."""

    summary: InspectionDict = {
        "patch_count": len(geometry.patch_facts),
        "chain_count": len(geometry.chain_facts),
        "vertex_count": len(geometry.vertex_facts),
        "local_face_fan_count": len(geometry.local_face_fan_facts),
    }
    if detail != "full":
        return summary
    summary.update({
        "patches": [
            {
                "id": str(facts.patch_id),
                "area": facts.area,
                "normal": list(facts.normal),
                "centroid": list(facts.centroid),
            }
            for facts in sorted(geometry.patch_facts.values(), key=lambda item: str(item.patch_id))
        ],
        "chains": [
            {
                "id": str(facts.chain_id),
                "length": facts.length,
                "chord_length": facts.chord_length,
                "shape_hint": str(facts.shape_hint.value),
                "is_closed": facts.chord_length <= DIRECTION_STABLE_EPSILON,
                "is_direction_stable": (
                    facts.shape_hint.value != "UNKNOWN"
                    and facts.chord_length > DIRECTION_STABLE_EPSILON
                ),
                "source_vertex_run": [
                    str(source_vertex_id)
                    for source_vertex_id in facts.source_vertex_run
                ],
                "segments": [
                    {
                        "source_edge_id": str(segment.source_edge_id),
                        "segment_index": segment.segment_index,
                        "start_source_vertex_id": str(segment.start_source_vertex_id),
                        "end_source_vertex_id": str(segment.end_source_vertex_id),
                        "length": segment.length,
                        "direction": list(segment.direction),
                    }
                    for segment in facts.segments
                ],
            }
            for facts in sorted(geometry.chain_facts.values(), key=lambda item: str(item.chain_id))
        ],
        "local_face_fans": [
            _local_face_fan_to_dict(facts)
            for facts in sorted(geometry.local_face_fan_facts.values(), key=lambda item: item.id)
        ],
    })
    return summary


def relation_summary_to_dict(relations: RelationSnapshot, detail: str = "compact") -> InspectionDict:
    """Return compact relation snapshot summary."""

    summary: InspectionDict = {
        "patch_adjacency_count": len(relations.patch_adjacencies),
        "chain_continuation_count": len(relations.chain_continuations),
        "chain_directional_run_count": len(relations.chain_directional_runs),
        "patch_chain_directional_evidence_count": len(relations.patch_chain_directional_evidence),
        "loop_corner_count": len(relations.loop_corners),
        "patch_chain_endpoint_sample_count": len(relations.patch_chain_endpoint_samples),
        "patch_chain_endpoint_relation_count": len(relations.patch_chain_endpoint_relations),
        "scaffold_node_count": len(relations.scaffold_nodes),
        "scaffold_edge_count": len(relations.scaffold_edges),
        "scaffold_graph_count": 1 if relations.scaffold_graph is not None else 0,
        "scaffold_junction_count": len(relations.scaffold_junctions),
        "side_surface_continuity_evidence_count": len(relations.side_surface_continuity_evidence),
        "scaffold_node_incident_edge_relation_count": len(
            relations.scaffold_node_incident_edge_relations
        ),
        "shared_chain_patch_chain_relation_count": len(relations.shared_chain_patch_chain_relations),
        "scaffold_continuity_component_count": len(relations.scaffold_continuity_components),
        "alignment_class_count": len(relations.alignment_classes),
        "patch_axes_count": len(relations.patch_axes),
    }
    if detail != "full":
        return summary
    summary.update({
        "patch_adjacencies": [
            {
                "id": adjacency.id,
                "first_patch_id": str(adjacency.first_patch_id),
                "second_patch_id": str(adjacency.second_patch_id),
                "chain_id": str(adjacency.chain_id),
                "dihedral_kind": str(adjacency.dihedral_kind.value),
            }
            for adjacency in sorted(relations.patch_adjacencies.values(), key=lambda item: item.id)
        ],
        "chain_continuations": [
            {
                "vertex_id": str(relation.vertex_id),
                "source_patch_chain_id": str(relation.source_patch_chain_id),
                "target_patch_chain_id": (
                    str(relation.target_patch_chain_id)
                    if relation.target_patch_chain_id is not None
                    else None
                ),
                "kind": str(relation.kind.value),
                "confidence": relation.confidence,
                "evidence": [
                    {
                        "source": evidence.source,
                        "summary": evidence.summary,
                        "data": dict(evidence.data),
                    }
                    for evidence in relation.evidence
                ],
            }
            for relation in sorted(
                relations.chain_continuations,
                key=lambda item: (
                    str(item.vertex_id),
                    str(item.source_patch_chain_id),
                    str(item.target_patch_chain_id),
                    str(item.kind.value),
                ),
            )
        ],
        "chain_directional_runs": [
            {
                "id": run.id,
                "parent_chain_id": str(run.parent_chain_id),
                "source_edge_ids": [str(source_edge_id) for source_edge_id in run.source_edge_ids],
                "segment_indices": list(run.segment_indices),
                "start_source_vertex_id": str(run.start_source_vertex_id),
                "end_source_vertex_id": str(run.end_source_vertex_id),
                "length": run.length,
                "direction": list(run.direction),
                "is_closed": run.is_closed,
                "confidence": run.confidence,
            }
            for run in sorted(
                relations.chain_directional_runs,
                key=lambda item: item.id,
            )
        ],
        "patch_chain_directional_evidence": [
            {
                "id": directional_evidence.id,
                "directional_run_id": directional_evidence.directional_run_id,
                "parent_chain_id": str(directional_evidence.parent_chain_id),
                "patch_chain_id": str(directional_evidence.patch_chain_id),
                "patch_id": str(directional_evidence.patch_id),
                "loop_id": str(directional_evidence.loop_id),
                "position_in_loop": directional_evidence.position_in_loop,
                "orientation_sign": directional_evidence.orientation_sign,
                "source_edge_ids": [str(source_edge_id) for source_edge_id in directional_evidence.source_edge_ids],
                "segment_indices": list(directional_evidence.segment_indices),
                "start_source_vertex_id": str(directional_evidence.start_source_vertex_id),
                "end_source_vertex_id": str(directional_evidence.end_source_vertex_id),
                "length": directional_evidence.length,
                "direction": list(directional_evidence.direction),
                "confidence": directional_evidence.confidence,
            }
            for directional_evidence in sorted(
                relations.patch_chain_directional_evidence,
                key=lambda item: item.id,
            )
        ],
        "alignment_classes": [
            {
                "id": alignment_class.id,
                "kind": str(alignment_class.kind.value),
                "member_directional_evidence_ids": list(alignment_class.member_directional_evidence_ids),
                "patch_ids": [str(patch_id) for patch_id in alignment_class.patch_ids],
                "dominant_direction": list(alignment_class.dominant_direction),
                "confidence": alignment_class.confidence,
            }
            for alignment_class in sorted(
                relations.alignment_classes,
                key=lambda item: item.id,
            )
        ],
        "loop_corners": [
            _loop_corner_to_dict(corner)
            for corner in sorted(relations.loop_corners, key=lambda item: item.id)
        ],
        "patch_chain_endpoint_samples": [
            _endpoint_sample_to_dict(sample)
            for sample in sorted(relations.patch_chain_endpoint_samples, key=lambda item: item.id)
        ],
        "patch_chain_endpoint_relations": [
            _endpoint_relation_to_dict(relation)
            for relation in sorted(relations.patch_chain_endpoint_relations, key=lambda item: item.id)
        ],
        "scaffold_nodes": [
            _scaffold_node_to_dict(node)
            for node in sorted(relations.scaffold_nodes, key=lambda item: item.id)
        ],
        "scaffold_edges": [
            _scaffold_edge_to_dict(edge)
            for edge in sorted(relations.scaffold_edges, key=lambda item: item.id)
        ],
        "scaffold_graph": (
            _scaffold_graph_to_dict(relations.scaffold_graph)
            if relations.scaffold_graph is not None
            else None
        ),
        "scaffold_junctions": [
            _scaffold_junction_to_dict(junction)
            for junction in sorted(relations.scaffold_junctions, key=lambda item: item.id)
        ],
        "side_surface_continuity_evidence": [
            _side_surface_continuity_evidence_to_dict(evidence)
            for evidence in sorted(relations.side_surface_continuity_evidence, key=lambda item: item.id)
        ],
        "scaffold_node_incident_edge_relations": [
            _scaffold_node_incident_edge_relation_to_dict(relation)
            for relation in sorted(relations.scaffold_node_incident_edge_relations, key=lambda item: item.id)
        ],
        "shared_chain_patch_chain_relations": [
            _shared_chain_patch_chain_relation_to_dict(relation)
            for relation in sorted(relations.shared_chain_patch_chain_relations, key=lambda item: item.id)
        ],
        "scaffold_continuity_components": [
            _scaffold_continuity_component_to_dict(component)
            for component in sorted(relations.scaffold_continuity_components, key=lambda item: item.id)
        ],
        "patch_axes": [
            {
                "patch_id": str(patch_axes.patch_id),
                "source": str(patch_axes.source.value),
                "primary_alignment_class_id": patch_axes.primary_alignment_class_id,
                "secondary_alignment_class_id": patch_axes.secondary_alignment_class_id,
                "primary_direction": list(patch_axes.primary_direction),
                "secondary_direction": list(patch_axes.secondary_direction),
                "confidence": patch_axes.confidence,
                "candidate_scores": _patch_axes_candidate_scores(patch_axes),
            }
            for patch_axes in sorted(
                relations.patch_axes.values(),
                key=lambda item: str(item.patch_id),
            )
        ],
    })
    return summary


def scaffold_graph_overlay_to_dict(
    topology: SurfaceModel,
    geometry: GeometryFactSnapshot,
    relations: RelationSnapshot,
) -> InspectionDict:
    """Return a pure-Python debug overlay payload for existing ScaffoldGraph data."""

    graph = relations.scaffold_graph
    patch_ordinals = {
        patch_id: index
        for index, patch_id in enumerate(sorted(topology.patches, key=str))
    }
    node_ordinals = {
        node.id: index + 1
        for index, node in enumerate(sorted(relations.scaffold_nodes, key=lambda item: item.id))
    }
    node_positions = {
        node.id: list(_scaffold_node_position(geometry, node.vertex_ids))
        for node in relations.scaffold_nodes
    }
    continuity_components = sorted(
        relations.scaffold_continuity_components,
        key=lambda item: item.id,
    )
    continuity_color_by_component_id = {
        component.id: _continuity_color(index)
        for index, component in enumerate(continuity_components)
    }
    continuity_component_id_by_edge_id = {
        edge_id: component.id
        for component in continuity_components
        for edge_id in component.scaffold_edge_ids
    }
    nodes_payload = [
        {
            "id": node.id,
            "display_label": _scaffold_node_display_label(
                topology,
                node,
                patch_ordinals,
                node_ordinals[node.id],
            ),
            "source_vertex_ids": [
                str(source_vertex_id)
                for source_vertex_id in node.source_vertex_ids
            ],
            "vertex_ids": [str(vertex_id) for vertex_id in node.vertex_ids],
            "position": node_positions[node.id],
            "confidence": node.confidence,
        }
        for node in sorted(relations.scaffold_nodes, key=lambda item: item.id)
    ]
    edges_payload = [
        {
            "id": edge.id,
            "display_label": _patch_chain_display_label(
                topology,
                edge.patch_chain_id,
                patch_ordinals,
            ),
            "patch_chain_id": str(edge.patch_chain_id),
            "chain_id": str(edge.chain_id),
            "start_scaffold_node_id": edge.start_scaffold_node_id,
            "end_scaffold_node_id": edge.end_scaffold_node_id,
            "polyline": _scaffold_edge_polyline(topology, geometry, edge.patch_chain_id),
            "continuity_component_id": continuity_component_id_by_edge_id.get(edge.id),
            "color_key": _continuity_color_key(continuity_component_id_by_edge_id.get(edge.id)),
            "continuity_color": _continuity_color_by_edge_id(
                edge.id,
                continuity_component_id_by_edge_id,
                continuity_color_by_component_id,
            ),
            "confidence": edge.confidence,
            "edge_source": _scaffold_edge_source(edge),
        }
        for edge in sorted(relations.scaffold_edges, key=lambda item: item.id)
    ]
    edge_polylines = {
        str(edge["id"]): edge["polyline"]
        for edge in edges_payload
    }
    endpoint_relation_by_id = {
        relation.id: relation
        for relation in relations.patch_chain_endpoint_relations
    }
    incident_relation_by_id = {
        relation.id: relation
        for relation in relations.scaffold_node_incident_edge_relations
    }
    return {
        "scaffold_node_count": len(relations.scaffold_nodes),
        "scaffold_edge_count": len(relations.scaffold_edges),
        "scaffold_junction_count": len(relations.scaffold_junctions),
        "side_surface_continuity_evidence_count": len(relations.side_surface_continuity_evidence),
        "scaffold_node_incident_edge_relation_count": len(
            relations.scaffold_node_incident_edge_relations
        ),
        "shared_chain_patch_chain_relation_count": len(relations.shared_chain_patch_chain_relations),
        "scaffold_continuity_component_count": len(continuity_components),
        "nodes": nodes_payload,
        "edges": edges_payload,
        "continuity_components": [
            _scaffold_continuity_component_overlay_to_dict(
                component,
                continuity_color_by_component_id,
                incident_relation_by_id,
            )
            for component in continuity_components
        ],
        "junctions": [
            _scaffold_junction_overlay_to_dict(junction, node_positions)
            for junction in sorted(relations.scaffold_junctions, key=lambda item: item.id)
        ],
        "side_surface_continuity_evidence": [
            _side_surface_continuity_evidence_overlay_to_dict(evidence, node_positions)
            for evidence in sorted(relations.side_surface_continuity_evidence, key=lambda item: item.id)
        ],
        "incident_relations": [
            _incident_relation_overlay_to_dict(
                relation,
                relations.scaffold_nodes,
                node_positions,
                endpoint_relation_by_id,
                continuity_component_id_by_edge_id,
            )
            for relation in sorted(
                relations.scaffold_node_incident_edge_relations,
                key=lambda item: item.id,
            )
        ],
        "shared_chain_relations": [
            _shared_chain_relation_overlay_to_dict(relation, edge_polylines)
            for relation in sorted(relations.shared_chain_patch_chain_relations, key=lambda item: item.id)
        ],
        "incident_relation_marker_count": len(
            relations.scaffold_node_incident_edge_relations
        ),
        "shared_chain_relation_marker_count": len(relations.shared_chain_patch_chain_relations),
        "side_surface_continuity_evidence_marker_count": len(
            relations.side_surface_continuity_evidence
        ),
        "graph": (
            {
                "id": graph.id,
                "node_ids": list(graph.node_ids),
                "edge_ids": list(graph.edge_ids),
            }
            if graph is not None
            else None
        ),
    }


CONTINUITY_COLOR_PALETTE: tuple[tuple[float, float, float, float], ...] = (
    (0.12, 0.62, 1.0, 1.0),
    (0.95, 0.45, 0.18, 1.0),
    (0.18, 0.78, 0.38, 1.0),
    (0.82, 0.35, 0.95, 1.0),
    (0.96, 0.82, 0.18, 1.0),
    (0.1, 0.78, 0.72, 1.0),
    (0.92, 0.28, 0.42, 1.0),
    (0.52, 0.7, 0.18, 1.0),
)
CONTINUITY_UNASSIGNED_COLOR = (0.55, 0.55, 0.55, 1.0)


def _continuity_color(index: int) -> list[float]:
    return list(CONTINUITY_COLOR_PALETTE[index % len(CONTINUITY_COLOR_PALETTE)])


def _continuity_color_key(component_id: str | None) -> str:
    if component_id is None:
        return "continuity:unassigned"
    return f"continuity:{component_id}"


def _continuity_color_by_edge_id(
    edge_id: str,
    continuity_component_id_by_edge_id: dict[str, str],
    continuity_color_by_component_id: dict[str, list[float]],
) -> list[float]:
    component_id = continuity_component_id_by_edge_id.get(edge_id)
    if component_id is None:
        return list(CONTINUITY_UNASSIGNED_COLOR)
    return list(continuity_color_by_component_id[component_id])


def _patch_chain_display_label(
    topology: SurfaceModel,
    patch_chain_id,
    patch_ordinals: dict[object, int],
) -> str:
    patch_chain = topology.patch_chains[patch_chain_id]
    return f"P{patch_ordinals[patch_chain.patch_id]}C{patch_chain.position_in_loop}"


def _scaffold_node_display_label(
    topology: SurfaceModel,
    node,
    patch_ordinals: dict[object, int],
    node_ordinal: int,
) -> str:
    incident_patch_chain_ids = sorted(
        node.incident_patch_chain_ids,
        key=lambda item: (
            patch_ordinals[topology.patch_chains[item].patch_id],
            topology.patch_chains[item].position_in_loop,
            str(item),
        ),
    )
    incident_labels = [
        _patch_chain_display_label(topology, patch_chain_id, patch_ordinals)
        for patch_chain_id in incident_patch_chain_ids
    ]
    if not incident_labels:
        return f"N{node_ordinal}"
    return f"N{node_ordinal} {'/'.join(incident_labels)}"


def _scaffold_node_position(
    geometry: GeometryFactSnapshot,
    vertex_ids,
) -> Vector3:
    positions = [
        geometry.vertex_facts[vertex_id].position
        for vertex_id in sorted(vertex_ids, key=str)
        if vertex_id in geometry.vertex_facts
    ]
    if not positions:
        return (0.0, 0.0, 0.0)
    count = float(len(positions))
    return (
        sum(position[0] for position in positions) / count,
        sum(position[1] for position in positions) / count,
        sum(position[2] for position in positions) / count,
    )


def _scaffold_edge_polyline(
    topology: SurfaceModel,
    geometry: GeometryFactSnapshot,
    patch_chain_id,
) -> list[list[float]]:
    patch_chain = topology.patch_chains[patch_chain_id]
    chain_facts = geometry.chain_facts.get(patch_chain.chain_id)
    if chain_facts is not None and chain_facts.segments:
        segments = chain_facts.segments
        if patch_chain.orientation_sign < 0:
            segments = tuple(reversed(segments))
            points = [segments[0].end_position]
            points.extend(segment.start_position for segment in segments)
        else:
            points = [segments[0].start_position]
            points.extend(segment.end_position for segment in segments)
        return [list(point) for point in points]

    start_vertex_id, end_vertex_id = patch_chain_vertices(topology, patch_chain_id)
    return [
        list(geometry.vertex_facts[start_vertex_id].position),
        list(geometry.vertex_facts[end_vertex_id].position),
    ]


def _scaffold_edge_source(edge) -> str:
    for evidence in edge.evidence:
        edge_source = evidence.data.get("edge_source")
        if edge_source is not None:
            return str(edge_source)
    return "FINAL_PATCH_CHAIN"


def _scaffold_junction_overlay_to_dict(junction, node_positions: dict[str, list[float]]) -> dict[str, object]:
    return {
        "id": junction.id,
        "scaffold_node_id": junction.scaffold_node_id,
        "kind": str(junction.kind.value),
        "position": list(node_positions.get(junction.scaffold_node_id, (0.0, 0.0, 0.0))),
        "confidence": junction.confidence,
        "evidence": [
            {
                "source": evidence.source,
                "summary": evidence.summary,
                "data": dict(evidence.data),
            }
            for evidence in junction.evidence
        ],
    }


def _incident_relation_overlay_to_dict(
    relation,
    scaffold_nodes,
    node_positions: dict[str, list[float]],
    endpoint_relation_by_id,
    continuity_component_id_by_edge_id: dict[str, str],
) -> dict[str, object]:
    node_by_id = {
        node.id: node
        for node in scaffold_nodes
    }
    node = node_by_id.get(relation.scaffold_node_id)
    endpoint_relation = endpoint_relation_by_id.get(relation.patch_chain_endpoint_relation_id)
    vertex_id = (
        str(endpoint_relation.vertex_id)
        if endpoint_relation is not None
        else (
            str(sorted(node.vertex_ids, key=str)[0])
            if node is not None and node.vertex_ids
            else None
        )
    )
    return {
        "id": relation.id,
        "kind": str(relation.kind.value),
        "scaffold_node_id": relation.scaffold_node_id,
        "first_scaffold_edge_id": relation.first_scaffold_edge_id,
        "second_scaffold_edge_id": relation.second_scaffold_edge_id,
        "first_continuity_component_id": continuity_component_id_by_edge_id.get(
            relation.first_scaffold_edge_id
        ),
        "second_continuity_component_id": continuity_component_id_by_edge_id.get(
            relation.second_scaffold_edge_id
        ),
        "first_patch_chain_id": str(relation.first_patch_chain_id),
        "second_patch_chain_id": str(relation.second_patch_chain_id),
        "first_endpoint_role": str(relation.first_endpoint_role.value),
        "second_endpoint_role": str(relation.second_endpoint_role.value),
        "first_endpoint_sample_id": relation.first_endpoint_sample_id,
        "second_endpoint_sample_id": relation.second_endpoint_sample_id,
        "endpoint_relation_id": relation.patch_chain_endpoint_relation_id,
        "vertex_id": vertex_id,
        "direction_dot": relation.direction_dot,
        "normal_dot": relation.normal_dot,
        "confidence": relation.confidence,
        "position": list(node_positions.get(relation.scaffold_node_id, (0.0, 0.0, 0.0))),
        "evidence": [
            {
                "source": evidence.source,
                "summary": evidence.summary,
                "data": dict(evidence.data),
            }
            for evidence in relation.evidence
        ],
    }


def _side_surface_continuity_evidence_overlay_to_dict(
    evidence,
    node_positions: dict[str, list[float]],
) -> dict[str, object]:
    return {
        "id": evidence.id,
        "scaffold_node_id": evidence.scaffold_node_id,
        "first_scaffold_edge_id": evidence.first_scaffold_edge_id,
        "second_scaffold_edge_id": evidence.second_scaffold_edge_id,
        "first_patch_chain_id": str(evidence.first_patch_chain_id),
        "second_patch_chain_id": str(evidence.second_patch_chain_id),
        "first_endpoint_role": str(evidence.first_endpoint_role.value),
        "second_endpoint_role": str(evidence.second_endpoint_role.value),
        "patch_id": str(evidence.patch_id),
        "loop_id": str(evidence.loop_id),
        "first_chain_id": str(evidence.first_chain_id),
        "second_chain_id": str(evidence.second_chain_id),
        "vertex_id": str(evidence.vertex_id),
        "source_vertex_ids": [
            str(source_vertex_id)
            for source_vertex_id in evidence.source_vertex_ids
        ],
        "first_endpoint_sample_id": evidence.first_endpoint_sample_id,
        "second_endpoint_sample_id": evidence.second_endpoint_sample_id,
        "normal_dot": evidence.normal_dot,
        "normal_evidence_source": evidence.normal_evidence_source,
        "confidence": evidence.confidence,
        "position": list(node_positions.get(evidence.scaffold_node_id, (0.0, 0.0, 0.0))),
        "evidence": [
            {
                "source": item.source,
                "summary": item.summary,
                "data": dict(item.data),
            }
            for item in evidence.evidence
        ],
    }


def _scaffold_continuity_component_overlay_to_dict(
    component,
    continuity_color_by_component_id: dict[str, list[float]],
    incident_relation_by_id: dict[str, object],
) -> dict[str, object]:
    degraded_relation_ids = tuple(
        relation_id
        for relation_id in component.blocked_incident_relation_ids
        if _relation_kind_value(incident_relation_by_id.get(relation_id)) == "DEGRADED"
    )
    warning_relation_ids = tuple(sorted((
        *component.ambiguous_incident_relation_ids,
        *degraded_relation_ids,
    )))
    return {
        "id": component.id,
        "color_key": _continuity_color_key(component.id),
        "continuity_color": list(continuity_color_by_component_id[component.id]),
        "scaffold_edge_ids": list(component.scaffold_edge_ids),
        "scaffold_node_ids": list(component.scaffold_node_ids),
        "propagating_incident_relation_ids": list(component.propagating_incident_relation_ids),
        "ambiguous_incident_relation_ids": list(component.ambiguous_incident_relation_ids),
        "blocked_incident_relation_ids": list(component.blocked_incident_relation_ids),
        "degraded_incident_relation_ids": list(degraded_relation_ids),
        "warning_relation_ids": list(warning_relation_ids),
        "warning_count": len(warning_relation_ids),
        "is_ambiguous": component.is_ambiguous,
        "confidence": component.confidence,
    }


def _relation_kind_value(relation) -> str:
    kind = getattr(relation, "kind", None)
    return str(getattr(kind, "value", kind or ""))


def _shared_chain_relation_overlay_to_dict(
    relation,
    edge_polylines: dict[str, list[list[float]]],
) -> dict[str, object]:
    first_polyline = edge_polylines.get(relation.first_scaffold_edge_id, [])
    second_polyline = edge_polylines.get(relation.second_scaffold_edge_id, [])
    label_position = _average_positions((
        _polyline_midpoint(first_polyline),
        _polyline_midpoint(second_polyline),
    ))
    return {
        "id": relation.id,
        "kind": str(relation.kind.value),
        "chain_id": str(relation.chain_id),
        "first_scaffold_edge_id": relation.first_scaffold_edge_id,
        "second_scaffold_edge_id": relation.second_scaffold_edge_id,
        "first_patch_chain_id": str(relation.first_patch_chain_id),
        "second_patch_chain_id": str(relation.second_patch_chain_id),
        "patch_ids": [
            str(patch_id)
            for patch_id in sorted((relation.first_patch_id, relation.second_patch_id), key=str)
        ],
        "confidence": relation.confidence,
        "label_position": label_position,
        "midpoint": label_position,
        "evidence": [
            {
                "source": evidence.source,
                "summary": evidence.summary,
                "data": dict(evidence.data),
            }
            for evidence in relation.evidence
        ],
    }


def _polyline_midpoint(polyline: list[list[float]]) -> list[float]:
    if not polyline:
        return [0.0, 0.0, 0.0]
    middle_index = len(polyline) // 2
    if len(polyline) % 2 == 1:
        return list(polyline[middle_index])
    return _average_positions((polyline[middle_index - 1], polyline[middle_index]))


def _average_positions(positions) -> list[float]:
    concrete_positions = [
        position
        for position in positions
        if len(position) == 3
    ]
    if not concrete_positions:
        return [0.0, 0.0, 0.0]
    count = float(len(concrete_positions))
    return [
        sum(float(position[index]) for position in concrete_positions) / count
        for index in range(3)
    ]


def _patch_axes_candidate_scores(patch_axes) -> list[dict[str, object]]:
    if not patch_axes.evidence:
        return []
    return list(patch_axes.evidence[0].data.get("candidate_scores", ()))


def _local_face_fan_to_dict(facts) -> dict[str, object]:
    return {
        "id": facts.id,
        "patch_id": str(facts.patch_id),
        "vertex_id": str(facts.vertex_id),
        "source_vertex_id": str(facts.source_vertex_id),
        "source_face_ids": [str(source_face_id) for source_face_id in facts.source_face_ids],
        "area": facts.area,
        "normal": list(facts.normal),
    }


def _loop_corner_to_dict(corner) -> dict[str, object]:
    return {
        "id": corner.id,
        "patch_id": str(corner.patch_id),
        "loop_id": str(corner.loop_id),
        "vertex_id": str(corner.vertex_id),
        "previous_patch_chain_id": str(corner.previous_patch_chain_id),
        "next_patch_chain_id": str(corner.next_patch_chain_id),
        "position_in_loop": corner.position_in_loop,
    }


def _endpoint_sample_to_dict(sample) -> dict[str, object]:
    return {
        "id": sample.id,
        "vertex_id": str(sample.vertex_id),
        "directional_evidence_id": sample.directional_evidence_id,
        "patch_chain_id": str(sample.patch_chain_id),
        "patch_id": str(sample.patch_id),
        "endpoint_role": str(sample.endpoint_role.value),
        "tangent_away_from_vertex": list(sample.tangent_away_from_vertex),
        "owner_normal": list(sample.owner_normal),
        "owner_normal_source": str(sample.owner_normal_source.value),
        "confidence": sample.confidence,
    }


def _endpoint_relation_to_dict(relation) -> dict[str, object]:
    return {
        "id": relation.id,
        "vertex_id": str(relation.vertex_id),
        "first_sample_id": relation.first_sample_id,
        "second_sample_id": relation.second_sample_id,
        "first_directional_evidence_id": relation.first_directional_evidence_id,
        "second_directional_evidence_id": relation.second_directional_evidence_id,
        "direction_dot": relation.direction_dot,
        "normal_dot": relation.normal_dot,
        "direction_relation": str(relation.direction_relation.value),
        "kind": str(relation.kind.value),
        "confidence": relation.confidence,
    }


def _scaffold_node_to_dict(node) -> dict[str, object]:
    return {
        "id": node.id,
        "vertex_ids": [str(vertex_id) for vertex_id in node.vertex_ids],
        "source_vertex_ids": [str(source_vertex_id) for source_vertex_id in node.source_vertex_ids],
        "loop_corner_ids": list(node.loop_corner_ids),
        "patch_chain_endpoint_sample_ids": list(node.patch_chain_endpoint_sample_ids),
        "patch_chain_endpoint_relation_ids": list(node.patch_chain_endpoint_relation_ids),
        "incident_patch_chain_ids": [
            str(patch_chain_id)
            for patch_chain_id in node.incident_patch_chain_ids
        ],
        "patch_ids": [str(patch_id) for patch_id in node.patch_ids],
        "confidence": node.confidence,
    }


def _scaffold_edge_to_dict(edge) -> dict[str, object]:
    return {
        "id": edge.id,
        "patch_chain_id": str(edge.patch_chain_id),
        "chain_id": str(edge.chain_id),
        "patch_id": str(edge.patch_id),
        "loop_id": str(edge.loop_id),
        "start_scaffold_node_id": edge.start_scaffold_node_id,
        "end_scaffold_node_id": edge.end_scaffold_node_id,
        "confidence": edge.confidence,
        "evidence": [
            {
                "source": evidence.source,
                "summary": evidence.summary,
                "data": dict(evidence.data),
            }
            for evidence in edge.evidence
        ],
    }


def _scaffold_graph_to_dict(graph) -> dict[str, object]:
    return {
        "id": graph.id,
        "node_ids": list(graph.node_ids),
        "edge_ids": list(graph.edge_ids),
        "confidence": graph.confidence,
        "evidence": [
            {
                "source": evidence.source,
                "summary": evidence.summary,
                "data": dict(evidence.data),
            }
            for evidence in graph.evidence
        ],
    }


def _scaffold_junction_to_dict(junction) -> dict[str, object]:
    return {
        "id": junction.id,
        "kind": str(junction.kind.value),
        "policy": junction.policy,
        "scaffold_node_id": junction.scaffold_node_id,
        "matched_chain_id": (
            str(junction.matched_chain_id)
            if junction.matched_chain_id is not None
            else None
        ),
        "patch_id": (
            str(junction.patch_id)
            if junction.patch_id is not None
            else None
        ),
        "chain_ids": [str(chain_id) for chain_id in junction.chain_ids],
        "patch_ids": [str(patch_id) for patch_id in junction.patch_ids],
        "loop_ids": [str(loop_id) for loop_id in junction.loop_ids],
        "scaffold_edge_ids": list(junction.scaffold_edge_ids),
        "patch_chain_ids": [
            str(patch_chain_id)
            for patch_chain_id in junction.patch_chain_ids
        ],
        "confidence": junction.confidence,
        "evidence": [
            {
                "source": evidence.source,
                "summary": evidence.summary,
                "data": dict(evidence.data),
            }
            for evidence in junction.evidence
        ],
    }


def _scaffold_node_incident_edge_relation_to_dict(relation) -> dict[str, object]:
    return {
        "id": relation.id,
        "kind": str(relation.kind.value),
        "policy": relation.policy,
        "scaffold_node_id": relation.scaffold_node_id,
        "first_scaffold_edge_id": relation.first_scaffold_edge_id,
        "second_scaffold_edge_id": relation.second_scaffold_edge_id,
        "first_patch_chain_id": str(relation.first_patch_chain_id),
        "second_patch_chain_id": str(relation.second_patch_chain_id),
        "first_endpoint_role": str(relation.first_endpoint_role.value),
        "second_endpoint_role": str(relation.second_endpoint_role.value),
        "first_endpoint_sample_id": relation.first_endpoint_sample_id,
        "second_endpoint_sample_id": relation.second_endpoint_sample_id,
        "patch_chain_endpoint_relation_id": relation.patch_chain_endpoint_relation_id,
        "direction_dot": relation.direction_dot,
        "normal_dot": relation.normal_dot,
        "confidence": relation.confidence,
        "evidence": [
            {
                "source": evidence.source,
                "summary": evidence.summary,
                "data": dict(evidence.data),
            }
            for evidence in relation.evidence
        ],
    }


def _side_surface_continuity_evidence_to_dict(evidence) -> dict[str, object]:
    return {
        "id": evidence.id,
        "scaffold_node_id": evidence.scaffold_node_id,
        "first_scaffold_edge_id": evidence.first_scaffold_edge_id,
        "second_scaffold_edge_id": evidence.second_scaffold_edge_id,
        "first_patch_chain_id": str(evidence.first_patch_chain_id),
        "second_patch_chain_id": str(evidence.second_patch_chain_id),
        "first_endpoint_role": str(evidence.first_endpoint_role.value),
        "second_endpoint_role": str(evidence.second_endpoint_role.value),
        "patch_id": str(evidence.patch_id),
        "loop_id": str(evidence.loop_id),
        "first_chain_id": str(evidence.first_chain_id),
        "second_chain_id": str(evidence.second_chain_id),
        "vertex_id": str(evidence.vertex_id),
        "source_vertex_ids": [
            str(source_vertex_id)
            for source_vertex_id in evidence.source_vertex_ids
        ],
        "first_endpoint_sample_id": evidence.first_endpoint_sample_id,
        "second_endpoint_sample_id": evidence.second_endpoint_sample_id,
        "normal_dot": evidence.normal_dot,
        "normal_evidence_source": evidence.normal_evidence_source,
        "confidence": evidence.confidence,
        "evidence": [
            {
                "source": item.source,
                "summary": item.summary,
                "data": dict(item.data),
            }
            for item in evidence.evidence
        ],
    }


def _shared_chain_patch_chain_relation_to_dict(relation) -> dict[str, object]:
    return {
        "id": relation.id,
        "kind": str(relation.kind.value),
        "policy": relation.policy,
        "chain_id": str(relation.chain_id),
        "first_scaffold_edge_id": relation.first_scaffold_edge_id,
        "second_scaffold_edge_id": relation.second_scaffold_edge_id,
        "first_patch_chain_id": str(relation.first_patch_chain_id),
        "second_patch_chain_id": str(relation.second_patch_chain_id),
        "first_patch_id": str(relation.first_patch_id),
        "second_patch_id": str(relation.second_patch_id),
        "patch_adjacency_id": relation.patch_adjacency_id,
        "confidence": relation.confidence,
        "evidence": [
            {
                "source": evidence.source,
                "summary": evidence.summary,
                "data": dict(evidence.data),
            }
            for evidence in relation.evidence
        ],
    }


def _scaffold_continuity_component_to_dict(component) -> dict[str, object]:
    return {
        "id": component.id,
        "scaffold_edge_ids": list(component.scaffold_edge_ids),
        "scaffold_node_ids": list(component.scaffold_node_ids),
        "propagating_incident_relation_ids": list(component.propagating_incident_relation_ids),
        "ambiguous_incident_relation_ids": list(component.ambiguous_incident_relation_ids),
        "blocked_incident_relation_ids": list(component.blocked_incident_relation_ids),
        "propagation_policy": component.propagation_policy,
        "is_ambiguous": component.is_ambiguous,
        "confidence": component.confidence,
        "evidence": [
            {
                "source": evidence.source,
                "summary": evidence.summary,
                "data": dict(evidence.data),
            }
            for evidence in component.evidence
        ],
    }


def describe_active_blender_mesh_topology(context: object) -> str:
    """Return a text report for the active Blender mesh topology snapshot."""

    source = read_source_mesh_from_blender(context)
    model = build_topology_snapshot(source)
    diagnostics = validate_topology(model)

    lines = [
        f"source faces: {len(source.faces)}",
        f"selected faces: {len(source.selected_face_ids)}",
        f"marks: {[(str(mark.kind), str(mark.target_id)) for mark in source.marks]}",
        f"shells: {len(model.shells)}",
        f"patches: {len(model.patches)}",
        f"chains: {len(model.chains)}",
        f"patch chains: {len(model.patch_chains)}",
    ]
    lines.extend(
        f"shell {shell.id}: patches {tuple(str(patch_id) for patch_id in shell.patch_ids)}"
        for shell in model.shells.values()
    )
    lines.extend(
        f"patch {patch.id}: shell {patch.shell_id} faces "
        f"{tuple(str(face_id) for face_id in patch.source_face_ids)} loops "
        f"{tuple(str(loop_id) for loop_id in patch.loop_ids)}"
        for patch in model.patches.values()
    )
    lines.extend(
        f"chain {chain.id}: edges {tuple(str(edge_id) for edge_id in chain.source_edge_ids)} "
        f"uses {len(patch_chains_for_chain(model, chain.id))}"
        for chain in model.chains.values()
    )
    lines.extend(
        f"patch chain {use.id}: chain {use.chain_id} patch {use.patch_id} "
        f"loop {use.loop_id} orientation {use.orientation_sign}"
        for use in model.patch_chains.values()
    )
    lines.extend(
        f"{diagnostic.severity} {diagnostic.code} "
        f"{tuple(diagnostic.entity_ids)} {dict(diagnostic.evidence)}"
        for diagnostic in diagnostics
    )
    return "\n".join(lines)


def _patch_to_dict(
    model: SurfaceModel,
    patch_id,
    source: SourceMeshSnapshot | None,
) -> InspectionDict:
    patch = model.patches[patch_id]
    return {
        "id": str(patch.id),
        "source_face_ids": [str(face_id) for face_id in patch.source_face_ids],
        "loops": [
            {
                "id": str(loop.id),
                "kind": str(loop.kind.value),
                "loop_index": loop.loop_index,
                "patch_chains": [
                    _patch_chain_to_dict(model, model.patch_chains[use_id], source)
                    for use_id in sorted(loop.patch_chain_ids, key=lambda item: model.patch_chains[item].position_in_loop)
                ],
            }
            for loop in sorted(
                (model.loops[loop_id] for loop_id in patch.loop_ids),
                key=lambda item: item.loop_index,
            )
        ],
    }


def _patch_chain_to_dict(
    model: SurfaceModel,
    use: PatchChain,
    source: SourceMeshSnapshot | None,
) -> InspectionDict:
    chain = model.chains[use.chain_id]
    use_start_vertex_id, use_end_vertex_id = patch_chain_vertices(model, use.id)
    start_vertex = model.vertices[chain.start_vertex_id]
    end_vertex = model.vertices[chain.end_vertex_id]
    chain_data: InspectionDict = {
        "id": str(chain.id),
        "source_edge_ids": [str(edge_id) for edge_id in chain.source_edge_ids],
        "source_edge_count": len(chain.source_edge_ids),
        "is_closed": chain.start_vertex_id == chain.end_vertex_id,
        "start_vertex_id": str(chain.start_vertex_id),
        "end_vertex_id": str(chain.end_vertex_id),
        "start_source_vertex_ids": [
            str(source_vertex_id)
            for source_vertex_id in start_vertex.source_vertex_ids
        ],
        "end_source_vertex_ids": [
            str(source_vertex_id)
            for source_vertex_id in end_vertex.source_vertex_ids
        ],
    }
    source_vertex_run = _source_vertex_run(source, chain.source_edge_ids)
    if source_vertex_run:
        chain_data["source_vertex_run"] = source_vertex_run
    return {
        "id": str(use.id),
        "patch_chain_id": str(use.id),
        "orientation_sign": use.orientation_sign,
        "position_in_loop": use.position_in_loop,
        "start_vertex_id": str(use_start_vertex_id),
        "end_vertex_id": str(use_end_vertex_id),
        "chain": chain_data,
    }


def _source_vertex_run(
    source: SourceMeshSnapshot | None,
    source_edge_ids,
) -> list[str]:
    if source is None or not source_edge_ids:
        return []

    first_edge = source.edges[source_edge_ids[0]]
    run = [first_edge.vertex_ids[0], first_edge.vertex_ids[1]]
    for edge_id in source_edge_ids[1:]:
        edge = source.edges[edge_id]
        if edge.vertex_ids[0] == run[-1]:
            run.append(edge.vertex_ids[1])
        elif edge.vertex_ids[1] == run[-1]:
            run.append(edge.vertex_ids[0])
        else:
            return []
    return [str(vertex_id) for vertex_id in run]


def _diagnostics_to_list(context: PipelineContext) -> list[dict[str, Any]]:
    diagnostics = list(context.diagnostics.diagnostics)
    return [
        {
            "code": diagnostic.code,
            "severity": str(diagnostic.severity.value),
            "message": diagnostic.message,
            "entity_ids": [str(entity_id) for entity_id in diagnostic.entity_ids],
        }
        for diagnostic in diagnostics
    ]
