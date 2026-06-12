"""Thin Blender drawing layer for ScaffoldGraph overlay v2."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .colors import material_key
from .debug import (
    _add_stroke,
    _ensure_frame,
    _ensure_layer,
    _ensure_material,
    _get_or_create_grease_pencil_object,
    _find_layer,
    is_graph_debug_object,
    overlay_object_name,
)

import bpy


FAMILY_LAYER_NAME = "ScaffoldGraph_FamilyRuns"
SPINE_LAYER_NAME = "ScaffoldGraph_Spines"
RIB_LAYER_NAME = "ScaffoldGraph_Ribs"
SEAM_VERDICT_LAYER_NAME = "ScaffoldGraph_SeamVerdicts"
JUNCTION_V2_LAYER_NAME = "ScaffoldGraph_JunctionsV2"
BRANCH_LAYER_NAME = "ScaffoldGraph_Branches"
FAMILY_MATERIAL_PREFIX = "ScaffoldGraphV2_Family_"
RAIL_MATERIAL_PREFIX = "ScaffoldGraphV2_Rail_"
SEAM_MATERIAL_PREFIX = "ScaffoldGraphV2_Seam_"
JUNCTION_MATERIAL_PREFIX = "ScaffoldGraphV2_Junction_"
BRANCH_MATERIAL_NAME = "ScaffoldGraphV2_Branch_Material"
FAMILY_WIDTH = 9
SPINE_WIDTH = 9
PARALLEL_WIDTH = 5
RIB_WIDTH = 4
SEAM_WIDTH = 6
JUNCTION_WIDTH = 5
BRANCH_WIDTH = 7


def render_overlay_v2(
    source_object: Any,
    payload: dict[str, Any],
    *,
    show_family_colors: bool,
    show_spines: bool,
    show_ribs: bool,
    show_seam_verdicts: bool,
    show_junctions: bool,
    show_branch_points: bool,
) -> dict[str, Any]:
    gp_object = _get_or_create_grease_pencil_object(source_object)
    gp_data = gp_object.data
    family_frame = _ensure_frame(_ensure_layer(gp_data, FAMILY_LAYER_NAME, show_family_colors))
    spine_frame = _ensure_frame(_ensure_layer(gp_data, SPINE_LAYER_NAME, show_spines))
    rib_frame = _ensure_frame(_ensure_layer(gp_data, RIB_LAYER_NAME, show_ribs))
    seam_frame = _ensure_frame(_ensure_layer(gp_data, SEAM_VERDICT_LAYER_NAME, show_seam_verdicts))
    junction_frame = _ensure_frame(_ensure_layer(gp_data, JUNCTION_V2_LAYER_NAME, show_junctions))
    branch_frame = _ensure_frame(_ensure_layer(gp_data, BRANCH_LAYER_NAME, show_branch_points))
    _clear_v2_material_slots(gp_data)

    family_strokes = _draw_family_runs(gp_data, family_frame, payload.get("family_run_segments", ()))
    spine_strokes, rib_strokes = _draw_rails(
        gp_data,
        spine_frame,
        rib_frame,
        payload.get("rails", ()),
    )
    seam_strokes = _draw_seam_verdicts(gp_data, seam_frame, payload.get("seam_verdicts", ()))
    junction_markers = _draw_junctions(gp_data, junction_frame, payload.get("junction_glyphs", ()))
    branch_markers = _draw_branches(gp_data, branch_frame, payload.get("branch_glyphs", ()))
    counts = payload.get("counts", {})
    return {
        "grease_pencil_object": gp_object.name,
        "family_layer": FAMILY_LAYER_NAME,
        "spine_layer": SPINE_LAYER_NAME,
        "rib_layer": RIB_LAYER_NAME,
        "seam_verdict_layer": SEAM_VERDICT_LAYER_NAME,
        "junction_layer": JUNCTION_V2_LAYER_NAME,
        "branch_layer": BRANCH_LAYER_NAME,
        "family_run_segment_count": int(counts.get("family_run_segment_count", 0)),
        "rail_count": int(counts.get("rail_count", 0)),
        "rail_polyline_count": int(counts.get("rail_polyline_count", 0)),
        "offset_polyline_count": int(counts.get("offset_polyline_count", 0)),
        "unoffset_polyline_count": int(counts.get("unoffset_polyline_count", 0)),
        "spine_count": int(counts.get("spine_count", 0)),
        "parallel_rail_count": int(counts.get("parallel_rail_count", 0)),
        "rib_count": int(counts.get("rib_count", 0)),
        "sewable_seam_count": int(counts.get("sewable_seam_count", 0)),
        "cut_seam_count": int(counts.get("cut_seam_count", 0)),
        "junction_glyph_count": int(counts.get("junction_glyph_count", 0)),
        "branch_glyph_count": int(counts.get("branch_glyph_count", 0)),
        "family_stroke_count": family_strokes,
        "spine_stroke_count": spine_strokes,
        "rib_stroke_count": rib_strokes,
        "seam_stroke_count": seam_strokes,
        "junction_marker_count": junction_markers,
        "branch_marker_count": branch_markers,
    }


def _draw_family_runs(gp_data: Any, frame: Any, segments: Sequence[dict[str, Any]]) -> int:
    count = 0
    for segment in segments:
        material_index = _material(gp_data, FAMILY_MATERIAL_PREFIX, segment.get("color_key", ""), segment.get("color"))
        if _add_polyline(frame, segment.get("polyline", ()), material_index, FAMILY_WIDTH):
            count += 1
    return count


def _draw_rails(
    gp_data: Any,
    spine_frame: Any,
    rib_frame: Any,
    rails: Sequence[dict[str, Any]],
) -> tuple[int, int]:
    spine_count = 0
    rib_count = 0
    for rail in rails:
        role = str(rail.get("role") or "RIB")
        # CUT (SEAM_SELF) belongs with the spine view: the artist reads the
        # band as "top rail / bottom rail / the cut between them".
        frame = spine_frame if role in {"SPINE", "PARALLEL", "CUT"} else rib_frame
        width = (
            SPINE_WIDTH
            if role == "SPINE"
            else PARALLEL_WIDTH
            if role == "PARALLEL"
            else SEAM_WIDTH
            if role == "CUT"
            else RIB_WIDTH
        )
        material_index = _material(gp_data, RAIL_MATERIAL_PREFIX, rail.get("color_key", ""), rail.get("color"))
        for polyline in rail.get("segment_polylines", ()):
            if _add_polyline(frame, polyline, material_index, width):
                if role in {"SPINE", "PARALLEL"}:
                    spine_count += 1
                else:
                    rib_count += 1
    return spine_count, rib_count


def _draw_seam_verdicts(gp_data: Any, frame: Any, verdicts: Sequence[dict[str, Any]]) -> int:
    count = 0
    for verdict in verdicts:
        material_index = _material(gp_data, SEAM_MATERIAL_PREFIX, verdict.get("status", ""), verdict.get("color"))
        polylines = _dashed_polyline(verdict.get("polyline", ())) if verdict.get("line_style") == "DASHED" else (verdict.get("polyline", ()),)
        for polyline in polylines:
            if _add_polyline(frame, polyline, material_index, SEAM_WIDTH):
                count += 1
        for position in verdict.get("failing_positions", ()):
            for marker in _x_marker(position, 0.075):
                _add_polyline(frame, marker, material_index, SEAM_WIDTH)
    return count


def _draw_junctions(gp_data: Any, frame: Any, glyphs: Sequence[dict[str, Any]]) -> int:
    count = 0
    for glyph in glyphs:
        material_index = _material(gp_data, JUNCTION_MATERIAL_PREFIX, glyph.get("kind", ""), glyph.get("color"))
        size = 0.045 + 0.018 * int(glyph.get("size_step", 0))
        strokes = (
            _diamond_marker(glyph.get("position", ()), size)
            if glyph.get("kind") == "RUN_ENDPOINT_JUNCTION"
            else _circle_marker(glyph.get("position", ()), size)
        )
        for marker in strokes:
            _add_polyline(frame, marker, material_index, JUNCTION_WIDTH)
        count += 1
    return count


def _draw_branches(gp_data: Any, frame: Any, glyphs: Sequence[dict[str, Any]]) -> int:
    material_index = _ensure_material(gp_data, BRANCH_MATERIAL_NAME, (1.0, 0.9, 0.05, 1.0))
    count = 0
    for glyph in glyphs:
        for marker in _branch_marker(glyph.get("position", ()), 0.11):
            _add_polyline(frame, marker, material_index, BRANCH_WIDTH)
        count += 1
    return count


def _material(gp_data: Any, prefix: str, key: object, color: object) -> int:
    rgba = color if isinstance(color, Sequence) and len(color) == 4 else (0.6, 0.6, 0.6, 1.0)
    return _ensure_material(
        gp_data,
        f"{prefix}{material_key(str(key))}_Material",
        tuple(float(value) for value in rgba),
    )


def _clear_v2_material_slots(gp_data: Any) -> None:
    materials = getattr(gp_data, "materials", None)
    if materials is None:
        return
    pop = getattr(materials, "pop", None)
    if not callable(pop):
        return
    for index in reversed(range(len(materials))):
        material = materials[index]
        if material is None or not _is_v2_material_name(material.name):
            continue
        try:
            pop(index=index)
        except TypeError:
            pop(index)
    for material in list(bpy.data.materials):
        if material.users == 0 and _is_v2_material_name(material.name):
            bpy.data.materials.remove(material)


def _is_v2_material_name(material_name: str) -> bool:
    return material_name == BRANCH_MATERIAL_NAME or material_name.startswith(
        (
            FAMILY_MATERIAL_PREFIX,
            RAIL_MATERIAL_PREFIX,
            SEAM_MATERIAL_PREFIX,
            JUNCTION_MATERIAL_PREFIX,
        )
    )


def _add_polyline(
    frame: Any,
    points: Sequence[Sequence[float]],
    material_index: int,
    line_width: int,
) -> bool:
    if len(points) < 2:
        return False
    if len(points) == 2:
        return _add_stroke(frame, points, material_index, line_width)
    added = False
    for first, second in zip(points, points[1:]):
        if _add_stroke(frame, (first, second), material_index, line_width):
            added = True
    return added


def _dashed_polyline(polyline: Sequence[Sequence[float]]) -> tuple[tuple[Sequence[float], Sequence[float]], ...]:
    return tuple((polyline[index], polyline[index + 1]) for index in range(0, max(0, len(polyline) - 1), 2))


def _circle_marker(position: Sequence[float], size: float) -> tuple[tuple[tuple[float, float, float], ...], ...]:
    x, y, z = _xyz(position)
    return (
        ((x - size, y, z), (x, y + size, z), (x + size, y, z), (x, y - size, z), (x - size, y, z)),
    )


def _diamond_marker(position: Sequence[float], size: float) -> tuple[tuple[tuple[float, float, float], ...], ...]:
    x, y, z = _xyz(position)
    return (
        ((x, y + size, z), (x + size, y, z), (x, y - size, z), (x - size, y, z), (x, y + size, z)),
    )


def _branch_marker(position: Sequence[float], size: float) -> tuple[tuple[tuple[float, float, float], ...], ...]:
    x, y, z = _xyz(position)
    return (
        ((x - size, y, z), (x + size, y, z)),
        ((x, y - size, z), (x, y + size, z)),
        ((x - size * 0.7, y - size * 0.7, z), (x + size * 0.7, y + size * 0.7, z)),
    )


def _x_marker(position: Sequence[float], size: float) -> tuple[tuple[tuple[float, float, float], ...], ...]:
    x, y, z = _xyz(position)
    return (
        ((x - size, y - size, z), (x + size, y + size, z)),
        ((x - size, y + size, z), (x + size, y - size, z)),
    )


def _xyz(position: Sequence[float]) -> tuple[float, float, float]:
    return (float(position[0]), float(position[1]), float(position[2]))


def apply_v2_layer_visibility(
    source_name: str,
    *,
    show_family_colors: bool,
    show_spines: bool,
    show_ribs: bool,
    show_seam_verdicts: bool,
    show_junctions: bool,
    show_branch_points: bool,
) -> None:
    obj = bpy.data.objects.get(overlay_object_name(source_name))
    if not is_graph_debug_object(obj):
        return
    for layer_name, visible in (
        (FAMILY_LAYER_NAME, show_family_colors),
        (SPINE_LAYER_NAME, show_spines),
        (RIB_LAYER_NAME, show_ribs),
        (SEAM_VERDICT_LAYER_NAME, show_seam_verdicts),
        (JUNCTION_V2_LAYER_NAME, show_junctions),
        (BRANCH_LAYER_NAME, show_branch_points),
    ):
        layer = _find_layer(obj.data, layer_name)
        if layer is not None and hasattr(layer, "hide"):
            layer.hide = not visible
