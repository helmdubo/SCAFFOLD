"""Build JSON-like ScaffoldGraph overlay v2 payloads without Blender."""

from __future__ import annotations

import math
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from .colors import (
    BRANCH_COLOR,
    CHAIN_SHAPE_COLORS,
    CUT_SEAM_COLOR,
    NEUTRAL_GRAY,
    RUN_ENDPOINT_JUNCTION_COLOR,
    SCAFFOLD_NODE_COLOR,
    SEWABLE_SEAM_COLOR,
    stable_color,
)
from .rail_assembly import (
    RailAssembly,
    RailView,
    RunSegmentView,
    _self_seam_chain_ids,
    build_rail_assembly,
)
from .rail_offsets import offset_segment_polyline, self_seam_flip_keys
from .seam_verdicts import ANGLE_DEFECT_TOLERANCE, SeamVerdict, build_seam_verdicts

GEODESIC_STRAIGHT_TOLERANCE_FALLBACK = 0.1
CHAIN_SHAPE_KINDS = ("SURFACE_LINE", "SURFACE_CURVE", "UNRESOLVED")


@dataclass(frozen=True)
class ChainShapePieceView:
    """One PatchChainShapeRelation piece in the shape the rail offset rule reads."""

    id: str
    directional_evidence_id: str
    patch_id: str
    patch_chain_id: str
    parent_chain_id: str
    source_edge_ids: tuple[str, ...]
    polyline: tuple[tuple[float, float, float], ...]


def build_overlay_v2_payload(context: Any) -> dict[str, Any]:
    """Return a serializable v2 overlay payload from a Pass 1 context."""

    topology = context.topology_snapshot
    geometry = context.geometry_facts
    relations = context.relation_snapshot
    if topology is None or geometry is None or relations is None:
        raise RuntimeError("Overlay v2 requires topology, geometry and relation snapshots.")
    assembly = build_rail_assembly(topology, geometry, relations, context.source_snapshot)
    seam_verdicts = build_seam_verdicts(topology, geometry, relations)
    chain_shape_pieces = _chain_shape_pieces(topology, geometry, relations, context.source_snapshot)
    counts = _counts(assembly, seam_verdicts)
    counts.update(_chain_shape_counts(chain_shape_pieces))
    counts["chain_shape_undrawn_count"] = (
        len(getattr(relations, "patch_chain_shape_relations", ())) - len(chain_shape_pieces)
    )
    return {
        "version": 2,
        "family_run_segments": [_run_segment_to_dict(segment) for segment in assembly.run_segments],
        "rails": [_rail_to_dict(rail) for rail in assembly.rails],
        "seam_verdicts": [_seam_verdict_to_dict(verdict) for verdict in seam_verdicts],
        "junction_glyphs": [_junction_glyph_to_dict(glyph) for glyph in assembly.junction_glyphs],
        "branch_glyphs": [_junction_glyph_to_dict(glyph) for glyph in assembly.branch_glyphs],
        "chain_shape_pieces": chain_shape_pieces,
        "counts": counts,
        "rail_contract_inputs": list(assembly.rail_contract_inputs),
        "angle_defect_tolerance": ANGLE_DEFECT_TOLERANCE,
        "geodesic_straight_tolerance": _geodesic_straight_tolerance(),
    }


def _geodesic_straight_tolerance() -> float:
    try:
        from scaffold_core.layer_3_relations import direction_families
    except ImportError:
        return GEODESIC_STRAIGHT_TOLERANCE_FALLBACK
    return float(
        getattr(
            direction_families,
            "GEODESIC_STRAIGHT_TOLERANCE",
            GEODESIC_STRAIGHT_TOLERANCE_FALLBACK,
        )
    )


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
        "is_closed": rail.is_closed,
        "directional_evidence_ids": list(rail.directional_evidence_ids),
        "patch_ids": list(rail.patch_ids),
        "junction_ids": list(rail.junction_ids),
        "segment_polylines": [
            [list(point) for point in polyline]
            for polyline in rail.segment_polylines
        ],
        "segment_offset_records": list(rail.segment_offset_records),
        "length": rail.length,
        "branch_junction_ids": list(rail.branch_junction_ids),
        "related_rail_ids": list(rail.related_rail_ids),
        "is_ambiguous": rail.is_ambiguous,
        "color": list(color),
        "color_key": f"{rail.role.lower()}:{rail.family_id}",
    }


def _rail_color(rail: RailView) -> tuple[float, float, float, float]:
    if rail.role == "OTHER":
        return NEUTRAL_GRAY
    if rail.role == "CUT":
        return CUT_SEAM_COLOR
    return stable_color(rail.family_id)


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


def _chain_shape_pieces(topology: Any, geometry: Any, relations: Any, source: Any) -> list[dict[str, Any]]:
    """One payload item per core PatchChainShapeRelation, offset to its own patch side."""

    records = sorted(getattr(relations, "patch_chain_shape_relations", ()), key=lambda item: item.id)
    views = {
        record.id: view
        for record in records
        for view in (_chain_shape_piece_view(geometry, record),)
        if view is not None
    }
    self_seam_chain_ids = _self_seam_chain_ids(relations)
    flip_keys = self_seam_flip_keys(
        (SimpleNamespace(directional_evidence_ids=tuple(views)),),
        views,
        self_seam_chain_ids,
    )
    messages_by_record_id: dict[str, list[str]] = {}
    for diagnostic in getattr(relations, "diagnostics", ()):
        for entity_id in diagnostic.entity_ids:
            if entity_id in views:
                messages_by_record_id.setdefault(entity_id, []).append(diagnostic.message)
    pieces = []
    for record in records:
        view = views.get(record.id)
        if view is None:
            continue
        polyline, offset_record = offset_segment_polyline(
            topology,
            source,
            view,
            flip=(view.parent_chain_id, view.patch_id, view.patch_chain_id) in flip_keys,
            self_seam_chain_ids=self_seam_chain_ids,
        )
        kind = record.kind.value
        pieces.append({
            "id": record.id,
            "kind": kind,
            "patch_id": view.patch_id,
            "patch_chain_id": view.patch_chain_id,
            "chain_id": view.parent_chain_id,
            "polyline": [list(point) for point in polyline],
            "color": list(CHAIN_SHAPE_COLORS.get(kind, NEUTRAL_GRAY)),
            "length": float(record.length),
            "segment_count": len(record.segment_indices),
            "surface_turn_max_deg": math.degrees(record.surface_turn_max),
            "tilt_range_deg": (
                [math.degrees(record.tilt_min), math.degrees(record.tilt_max)]
                if record.tilt_min is not None and record.tilt_max is not None
                else None
            ),
            "unoffset": bool(offset_record["unoffset"]),
            "diagnostics": messages_by_record_id.get(record.id, []),
        })
    return pieces


def _chain_shape_piece_view(geometry: Any, record: Any) -> ChainShapePieceView | None:
    chain_facts = geometry.chain_facts.get(record.chain_id)
    if chain_facts is None:
        return None
    segments_by_index = {segment.segment_index: segment for segment in chain_facts.segments}
    segments = [segments_by_index[index] for index in record.segment_indices if index in segments_by_index]
    if not segments or len(segments) != len(record.segment_indices):
        return None
    points = [segments[0].start_position]
    points.extend(segment.end_position for segment in segments)
    return ChainShapePieceView(
        id=record.id,
        directional_evidence_id=record.id,
        patch_id=str(record.patch_id),
        patch_chain_id=str(record.patch_chain_id),
        parent_chain_id=str(record.chain_id),
        source_edge_ids=tuple(str(segment.source_edge_id) for segment in segments),
        polyline=tuple(tuple(float(value) for value in point) for point in points),
    )


def _chain_shape_counts(pieces: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        f"chain_shape_{kind.lower()}_count": sum(piece["kind"] == kind for piece in pieces)
        for kind in CHAIN_SHAPE_KINDS
    }
    counts["chain_shape_piece_count"] = len(pieces)
    return counts


def _counts(assembly: RailAssembly, seam_verdicts: tuple[SeamVerdict, ...]) -> dict[str, int]:
    return {
        "family_run_segment_count": len(assembly.run_segments),
        "rail_count": len(assembly.rails),
        "rail_polyline_count": sum(len(rail.segment_polylines) for rail in assembly.rails),
        "offset_polyline_count": sum(
            not record.get("unoffset", False)
            for rail in assembly.rails
            for record in rail.segment_offset_records
        ),
        "unoffset_polyline_count": sum(
            record.get("unoffset", False)
            for rail in assembly.rails
            for record in rail.segment_offset_records
        ),
        "spine_count": sum(rail.role == "SPINE" for rail in assembly.rails),
        "parallel_rail_count": sum(rail.role == "PARALLEL" for rail in assembly.rails),
        "rib_count": sum(rail.role == "RIB" for rail in assembly.rails),
        "other_rail_count": sum(rail.role == "OTHER" for rail in assembly.rails),
        "closed_rail_count": sum(rail.is_closed for rail in assembly.rails),
        "cut_rail_count": sum(rail.role == "CUT" for rail in assembly.rails),
        "dual_membership_rib_count": sum(
            rail.role == "RIB" and len(rail.related_rail_ids) >= 2
            for rail in assembly.rails
        ),
        "sewable_seam_count": sum(verdict.status == "SEWABLE" for verdict in seam_verdicts),
        "cut_seam_count": sum(verdict.status == "CUT" for verdict in seam_verdicts),
        "junction_glyph_count": len(assembly.junction_glyphs),
        "branch_glyph_count": len(assembly.branch_glyphs),
    }
