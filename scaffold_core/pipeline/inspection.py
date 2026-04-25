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
from scaffold_core.layer_1_topology.model import ChainUse, SurfaceModel
from scaffold_core.layer_1_topology.queries import chain_uses_for_chain
from scaffold_core.layer_2_geometry.facts import GeometryFactSnapshot
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
    report["diagnostics"] = _diagnostics_to_list(context)
    return report


def topology_tree_to_dict(
    model: SurfaceModel,
    source: SourceMeshSnapshot | None = None,
) -> InspectionDict:
    """Return nested SurfaceModel -> Shell -> Patch -> Loop -> ChainUse data."""

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
    })
    return summary


def relation_summary_to_dict(relations: RelationSnapshot, detail: str = "compact") -> InspectionDict:
    """Return compact relation snapshot summary."""

    summary: InspectionDict = {
        "patch_adjacency_count": len(relations.patch_adjacencies),
        "chain_continuation_count": len(relations.chain_continuations),
        "chain_directional_run_count": len(relations.chain_directional_runs),
        "chain_directional_run_use_count": len(relations.chain_directional_run_uses),
        "alignment_class_count": len(relations.alignment_classes),
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
                "junction_vertex_id": str(relation.junction_vertex_id),
                "source_chain_use_id": str(relation.source_chain_use_id),
                "target_chain_use_id": (
                    str(relation.target_chain_use_id)
                    if relation.target_chain_use_id is not None
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
                    str(item.junction_vertex_id),
                    str(item.source_chain_use_id),
                    str(item.target_chain_use_id),
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
        "chain_directional_run_uses": [
            {
                "id": run_use.id,
                "directional_run_id": run_use.directional_run_id,
                "parent_chain_id": str(run_use.parent_chain_id),
                "chain_use_id": str(run_use.chain_use_id),
                "patch_id": str(run_use.patch_id),
                "loop_id": str(run_use.loop_id),
                "position_in_loop": run_use.position_in_loop,
                "orientation_sign": run_use.orientation_sign,
                "source_edge_ids": [str(source_edge_id) for source_edge_id in run_use.source_edge_ids],
                "segment_indices": list(run_use.segment_indices),
                "start_source_vertex_id": str(run_use.start_source_vertex_id),
                "end_source_vertex_id": str(run_use.end_source_vertex_id),
                "length": run_use.length,
                "direction": list(run_use.direction),
                "confidence": run_use.confidence,
            }
            for run_use in sorted(
                relations.chain_directional_run_uses,
                key=lambda item: item.id,
            )
        ],
        "alignment_classes": [
            {
                "id": alignment_class.id,
                "kind": str(alignment_class.kind.value),
                "member_run_use_ids": list(alignment_class.member_run_use_ids),
                "patch_ids": [str(patch_id) for patch_id in alignment_class.patch_ids],
                "dominant_direction": list(alignment_class.dominant_direction),
                "confidence": alignment_class.confidence,
            }
            for alignment_class in sorted(
                relations.alignment_classes,
                key=lambda item: item.id,
            )
        ],
    })
    return summary


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
        f"chain uses: {len(model.chain_uses)}",
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
        f"uses {len(chain_uses_for_chain(model, chain.id))}"
        for chain in model.chains.values()
    )
    lines.extend(
        f"chain use {use.id}: chain {use.chain_id} patch {use.patch_id} "
        f"loop {use.loop_id} orientation {use.orientation_sign}"
        for use in model.chain_uses.values()
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
                "chain_uses": [
                    _chain_use_to_dict(model, model.chain_uses[use_id], source)
                    for use_id in sorted(loop.chain_use_ids, key=lambda item: model.chain_uses[item].position_in_loop)
                ],
            }
            for loop in sorted(
                (model.loops[loop_id] for loop_id in patch.loop_ids),
                key=lambda item: item.loop_index,
            )
        ],
    }


def _chain_use_to_dict(
    model: SurfaceModel,
    use: ChainUse,
    source: SourceMeshSnapshot | None,
) -> InspectionDict:
    chain = model.chains[use.chain_id]
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
        "orientation_sign": use.orientation_sign,
        "position_in_loop": use.position_in_loop,
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
