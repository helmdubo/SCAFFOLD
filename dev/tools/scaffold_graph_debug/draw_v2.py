"""Thin Blender drawing layer for the Scaffold structure debugger.

Draws the payload of overlay_v2.build_debug_payload into one Grease Pencil
object per source mesh, one GP layer per LayerSpec. Visibility is the GP
layer flag only, so the panel toggles act without a rebuild.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

import bpy

from .colors import material_key
from .debug import (
    MATERIAL_PREFIX,
    color_hex,
    _ensure_frame,
    _ensure_layer,
    _ensure_material,
    _find_layer,
    _get_or_create_grease_pencil_object,
    clear_overlay,
    draw_labels,
    is_graph_debug_object,
    label_collection_name,
    overlay_object_name,
    remove_labels,
    set_layer_thickness,
    write_strokes,
)
from .overlay_v2 import LAYER_SPECS

LABELS_PROPERTY = "scaffold_debug_labels"
BASE_WIDTHS_PROPERTY = "scaffold_debug_base_widths"
RADIUS_SCALE_PROPERTY = "scaffold_debug_radius_scale"
# GP v3 widths are world-space radii: thicken them on large meshes.
RADIUS_REFERENCE_UNIT = 0.2


def render_debug_overlay(
    source_object: Any,
    payload: dict[str, Any],
    visibility: Mapping[str, bool],
    *,
    show_labels: bool = False,
    line_thickness: float = 1.0,
) -> dict[str, int]:
    """Rebuild the overlay object of source_object; returns strokes per layer."""

    clear_overlay(source_object.name)
    gp_object = _get_or_create_grease_pencil_object(source_object)
    gp_data = gp_object.data
    radius_scale = max(1.0, float(payload.get("marker_unit", RADIUS_REFERENCE_UNIT)) / RADIUS_REFERENCE_UNIT)
    material_indexes: dict[tuple[str, str, bool], int] = {}
    stroke_counts: dict[str, int] = {}
    base_widths: dict[str, int] = {}
    for spec in LAYER_SPECS:
        frame = _ensure_frame(_ensure_layer(gp_data, spec.layer, bool(visibility.get(spec.layer, spec.default))))
        rows = []
        for item in payload["layers"].get(spec.layer, ()):
            for stroke in item["strokes"]:
                key = (stroke["material"], color_hex(stroke["color"]), bool(stroke["fill"]))
                index = material_indexes.get(key)
                if index is None:
                    index = _ensure_material(
                        gp_data,
                        # shared across overlays, so the name carries everything that sets the colour
                        f"{MATERIAL_PREFIX}{material_key(stroke['material'])}_{key[1]}{'_Fill' if stroke['fill'] else ''}",
                        tuple(float(value) for value in stroke["color"]),
                        fill=bool(stroke["fill"]),
                    )
                    material_indexes[key] = index
                rows.append((stroke["points"], index, stroke["width"], bool(stroke["fill"])))
                if not stroke["fill"]:
                    base_widths[spec.layer] = min(base_widths.get(spec.layer, stroke["width"]), stroke["width"])
        stroke_counts[spec.layer] = write_strokes(frame, rows, radius_scale=radius_scale)
    gp_object[BASE_WIDTHS_PROPERTY] = json.dumps(base_widths, separators=(",", ":"), sort_keys=True)
    gp_object[RADIUS_SCALE_PROPERTY] = radius_scale
    apply_line_thickness(source_object.name, line_thickness)
    gp_object[LABELS_PROPERTY] = json.dumps(payload.get("labels", []), separators=(",", ":"))
    stroke_counts["labels"] = draw_labels(source_object, payload.get("labels", [])) if show_labels else 0
    return stroke_counts


def apply_line_thickness(source_name: str, multiplier: float) -> int:
    """Set the live thickness of every stroke layer (fill-only layers untouched); returns layers set."""

    obj = bpy.data.objects.get(overlay_object_name(source_name))
    if not is_graph_debug_object(obj):
        return 0
    try:
        base_widths = json.loads(obj.get(BASE_WIDTHS_PROPERTY, "{}"))
    except (TypeError, ValueError):
        base_widths = {}
    radius_scale = float(obj.get(RADIUS_SCALE_PROPERTY, 1.0))
    count = 0
    for layer_name, base_width in base_widths.items():
        layer = _find_layer(obj.data, layer_name)
        if layer is not None and set_layer_thickness(layer, int(base_width), multiplier, radius_scale):
            count += 1
    return count


def apply_layer_visibility(source_name: str, visibility: Mapping[str, bool], *, show_labels: bool) -> None:
    """Show or hide the overlay layers of one source mesh; labels are created or removed."""

    obj = bpy.data.objects.get(overlay_object_name(source_name))
    if not is_graph_debug_object(obj):
        return
    for spec in LAYER_SPECS:
        layer = _find_layer(obj.data, spec.layer)
        if layer is not None and hasattr(layer, "hide"):
            layer.hide = not bool(visibility.get(spec.layer, spec.default))
    if not show_labels:
        remove_labels(source_name)
        return
    source_object = bpy.data.objects.get(source_name)
    if source_object is None or bpy.data.collections.get(label_collection_name(source_name)) is not None:
        return
    try:
        labels = json.loads(obj.get(LABELS_PROPERTY, "[]"))
    except (TypeError, ValueError):
        labels = []
    draw_labels(source_object, labels)
