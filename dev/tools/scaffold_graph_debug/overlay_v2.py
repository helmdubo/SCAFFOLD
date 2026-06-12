"""Build JSON-like ScaffoldGraph overlay v2 payloads without Blender."""

from __future__ import annotations

from typing import Any

from .colors import (
    BRANCH_COLOR,
    CUT_SEAM_COLOR,
    NEUTRAL_GRAY,
    PARALLEL_RAIL_COLOR,
    RIB_COLOR,
    RUN_ENDPOINT_JUNCTION_COLOR,
    SCAFFOLD_NODE_COLOR,
    SEWABLE_SEAM_COLOR,
    SPINE_COLOR,
    stable_color,
)
from .geodesic_continuation import GEODESIC_STRAIGHT_TOLERANCE
from .rail_assembly import RailAssembly, RailView, RunSegmentView, build_rail_assembly
from .seam_verdicts import ANGLE_DEFECT_TOLERANCE, SeamVerdict, build_seam_verdicts


def build_overlay_v2_payload(context: Any) -> dict[str, Any]:
    """Return a serializable v2 overlay payload from a Pass 1 context."""

    topology = context.topology_snapshot
    geometry = context.geometry_facts
    relations = context.relation_snapshot
    if topology is None or geometry is None or relations is None:
        raise RuntimeError("Overlay v2 requires topology, geometry and relation snapshots.")
    assembly = build_rail_assembly(topology, geometry, relations, context.source_snapshot)
    seam_verdicts = build_seam_verdicts(topology, geometry, relations)
    return {
        "version": 2,
        "family_run_segments": [_run_segment_to_dict(segment) for segment in assembly.run_segments],
        "rails": [_rail_to_dict(rail) for rail in assembly.rails],
        "seam_verdicts": [_seam_verdict_to_dict(verdict) for verdict in seam_verdicts],
        "junction_glyphs": [_junction_glyph_to_dict(glyph) for glyph in assembly.junction_glyphs],
        "branch_glyphs": [_junction_glyph_to_dict(glyph) for glyph in assembly.branch_glyphs],
        "counts": _counts(assembly, seam_verdicts),
        "rail_contract_inputs": list(assembly.rail_contract_inputs),
        "angle_defect_tolerance": ANGLE_DEFECT_TOLERANCE,
        "geodesic_straight_tolerance": GEODESIC_STRAIGHT_TOLERANCE,
    }


def _run_segment_to_dict(segment: RunSegmentView) -> dict[str, Any]:
    family_id = segment.family_id
    color = stable_color(family_id) if family_id is not None else NEUTRAL_GRAY
    return {
        "id": segment.id,
        "directional_evidence_id": segment.directional_evidence_id,
        "family_id": family_id,
        "patch_id": segment.patch_id,
        "patch_chain_id": segment.patch_chain_id,
        "loop_id": segment.loop_id,
        "start_junction_id": segment.start_junction_id,
        "end_junction_id": segment.end_junction_id,
        "length": segment.length,
        "direction": list(segment.direction),
        "polyline": [list(point) for point in segment.polyline],
        "color": list(color),
        "color_key": family_id or "unfamilied",
    }


def _rail_to_dict(rail: RailView) -> dict[str, Any]:
    color = _rail_color(rail)
    return {
        "id": rail.id,
        "family_id": rail.family_id,
        "role": rail.role,
        "directional_evidence_ids": list(rail.directional_evidence_ids),
        "patch_ids": list(rail.patch_ids),
        "junction_ids": list(rail.junction_ids),
        "segment_polylines": [
            [list(point) for point in polyline]
            for polyline in rail.segment_polylines
        ],
        "length": rail.length,
        "branch_junction_ids": list(rail.branch_junction_ids),
        "is_ambiguous": rail.is_ambiguous,
        "is_default_visible": rail.is_default_visible,
        "color": list(color),
        "color_key": f"{rail.role.lower()}:{rail.family_id}",
    }


def _rail_color(rail: RailView) -> tuple[float, float, float, float]:
    if rail.role == "CUT":
        return CUT_SEAM_COLOR
    if rail.role == "SPINE":
        return SPINE_COLOR
    if rail.role == "PARALLEL":
        return PARALLEL_RAIL_COLOR
    return RIB_COLOR


def _seam_verdict_to_dict(verdict: SeamVerdict) -> dict[str, Any]:
    return {
        "id": verdict.id,
        "chain_id": verdict.chain_id,
        "patch_ids": list(verdict.patch_ids),
        "status": verdict.status,
        "polyline": [list(point) for point in verdict.polyline],
        "failing_vertex_ids": list(verdict.failing_vertex_ids),
        "failing_positions": [list(point) for point in verdict.failing_positions],
        "would_be_interior_vertex_ids": list(verdict.would_be_interior_vertex_ids),
        "excluded_endpoint_vertex_ids": list(verdict.excluded_endpoint_vertex_ids),
        "vertex_angle_defects": [
            {"vertex_id": vertex_id, "angle_defect": defect}
            for vertex_id, defect in verdict.vertex_angle_defects
        ],
        "reason": verdict.reason,
        "color": list(SEWABLE_SEAM_COLOR if verdict.status == "SEWABLE" else CUT_SEAM_COLOR),
        "line_style": "DASHED" if verdict.status == "SEWABLE" else "SOLID",
    }


def _junction_glyph_to_dict(glyph) -> dict[str, Any]:
    color = (
        SCAFFOLD_NODE_COLOR
        if glyph.kind == "SCAFFOLD_NODE"
        else RUN_ENDPOINT_JUNCTION_COLOR
    )
    if glyph.valence > 2:
        color = BRANCH_COLOR
    return {
        "id": glyph.id,
        "kind": glyph.kind,
        "position": list(glyph.position),
        "valence": glyph.valence,
        "size_step": glyph.size_step,
        "color": list(color),
    }


def _counts(assembly: RailAssembly, seam_verdicts: tuple[SeamVerdict, ...]) -> dict[str, int]:
    visible_rails = tuple(rail for rail in assembly.rails if rail.is_default_visible)
    return {
        "family_run_segment_count": len(assembly.run_segments),
        "rail_count": len(visible_rails),
        "hidden_patch_view_rail_count": sum(not rail.is_default_visible for rail in assembly.rails),
        "spine_count": sum(rail.role == "SPINE" for rail in visible_rails),
        "parallel_rail_count": sum(rail.role == "PARALLEL" for rail in visible_rails),
        "rib_count": sum(rail.role == "RIB" for rail in visible_rails),
        "cut_rail_count": sum(rail.role == "CUT" for rail in visible_rails),
        "sewable_seam_count": sum(verdict.status == "SEWABLE" for verdict in seam_verdicts),
        "cut_seam_count": sum(verdict.status == "CUT" for verdict in seam_verdicts),
        "junction_glyph_count": len(assembly.junction_glyphs),
        "branch_glyph_count": len(assembly.branch_glyphs),
    }
