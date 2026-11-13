"""Grease Pencil and text-label primitives for the Scaffold debug overlay.

This module may import Blender APIs because it lives outside scaffold_core.
It draws what it is given and computes no Scaffold semantics. Both Grease
Pencil generations are handled: legacy GPENCIL (Blender <= 4.2, frame.strokes)
and GP v3 (Blender >= 4.3, frame.drawing).
"""

from __future__ import annotations

from typing import Any, Sequence

import bpy
from mathutils import Vector


GP_OBJECT_PREFIX = "ScaffoldGraph_Overlay__"
LABEL_COLLECTION_PREFIX = "Scaffold_Debug_Labels__"
LABEL_OBJECT_PREFIX = "Scaffold_Label__"
LABEL_MATERIAL_PREFIX = "ScaffoldDebug_Label_"
MATERIAL_PREFIX = "ScaffoldDebug_"
LEGACY_MATERIAL_PREFIXES = ("ScaffoldGraphV2_", "ScaffoldGraph_")
LABEL_SIZE = 0.12
GP_OBJECT_TYPES = {"GREASEPENCIL", "GPENCIL"}
V3_RADIUS_PER_WIDTH = 0.00075


def _safe_object_suffix(name: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"_", "-", "."} else "_" for ch in name)
    return safe or "mesh"


def color_hex(color: Sequence[float]) -> str:
    """RGBA as 8 hex digits: materials shared by several overlays are named by their colour."""

    return "".join(f"{max(0, min(255, round(float(value) * 255))):02x}" for value in tuple(color)[:4])


def overlay_object_name(source_name: str) -> str:
    return GP_OBJECT_PREFIX + _safe_object_suffix(source_name)


def label_collection_name(source_name: str) -> str:
    return LABEL_COLLECTION_PREFIX + _safe_object_suffix(source_name)


def is_graph_debug_object(obj: Any) -> bool:
    return (
        obj is not None
        and getattr(obj, "type", None) in GP_OBJECT_TYPES
        and getattr(obj, "name", "").startswith(GP_OBJECT_PREFIX)
    )


def _grease_pencil_collection() -> Any:
    grease_pencils_v3 = getattr(bpy.data, "grease_pencils_v3", None)
    if grease_pencils_v3 is not None:
        return grease_pencils_v3
    grease_pencils = getattr(bpy.data, "grease_pencils", None)
    if grease_pencils is not None:
        return grease_pencils
    raise RuntimeError("Grease Pencil data-block collection is unavailable.")


def _layer_name(layer: Any) -> str:
    return str(getattr(layer, "name", getattr(layer, "info", "")))


def _find_layer(gp_data: Any, layer_name: str) -> Any | None:
    for layer in getattr(gp_data, "layers", ()):
        if _layer_name(layer) == layer_name:
            return layer
    return None


def _clear_layer(layer: Any) -> None:
    if hasattr(layer, "clear"):
        layer.clear()
        return
    frames = getattr(layer, "frames", None)
    if frames is None:
        return
    for frame in list(frames):
        frame_number = getattr(frame, "frame_number", None)
        if frame_number is not None:
            frames.remove(frame_number)


def _ensure_layer(gp_data: Any, layer_name: str, visible: bool) -> Any:
    layer = _find_layer(gp_data, layer_name)
    if layer is None:
        layer = gp_data.layers.new(layer_name, set_active=False)
    else:
        _clear_layer(layer)
    if hasattr(layer, "hide"):
        layer.hide = not visible
    if hasattr(layer, "use_lights"):
        layer.use_lights = False  # flat debug colours, independent of scene lights
    return layer


def _ensure_frame(layer: Any) -> Any:
    frames = getattr(layer, "frames", None)
    if frames is None:
        raise RuntimeError(f"Grease Pencil layer {_layer_name(layer)!r} has no frames API.")
    if len(frames) > 0:
        return frames[0]
    return frames.new(0)


def _ensure_material(
    gp_data: Any,
    material_name: str,
    color: tuple[float, float, float, float],
    *,
    fill: bool = False,
) -> int:
    material = bpy.data.materials.get(material_name)
    if material is None:
        material = bpy.data.materials.new(material_name)
    if not getattr(material, "grease_pencil", None):
        bpy.data.materials.create_gpencil_data(material)
    material.grease_pencil.color = color
    material.grease_pencil.show_fill = fill
    material.grease_pencil.show_stroke = not fill
    if fill:
        material.grease_pencil.fill_color = color

    for index, slot in enumerate(gp_data.materials):
        if slot is not None and slot.name == material_name:
            return index
    gp_data.materials.append(material)
    return len(gp_data.materials) - 1


def _ensure_stroke_point_count(stroke: Any, point_count: int) -> None:
    points = getattr(stroke, "points", None)
    if points is None:
        raise RuntimeError("Grease Pencil stroke has no points API.")
    if len(points) >= point_count:
        return
    add_points = getattr(points, "add", None)
    if not callable(add_points):
        raise RuntimeError(
            f"Grease Pencil stroke has {len(points)} points; expected {point_count}."
        )
    while len(points) < point_count:
        before = len(points)
        add_points(point_count - before)
        if len(points) == before:
            raise RuntimeError(
                f"Grease Pencil stroke has {len(points)} points; expected {point_count}."
            )


def _set_stroke_style(stroke: Any, material_index: int, line_width: int, cyclic: bool = False) -> None:
    try:
        stroke.material_index = material_index
    except (IndexError, RuntimeError):
        stroke.material_index = 0
    if hasattr(stroke, "line_width"):
        stroke.line_width = line_width
    if hasattr(stroke, "use_cyclic"):
        stroke.use_cyclic = cyclic
    elif hasattr(stroke, "cyclic"):
        stroke.cyclic = cyclic


def _set_point(point: Any, coords: Sequence[float], line_width: int, radius_scale: float = 1.0) -> None:
    location = (float(coords[0]), float(coords[1]), float(coords[2]))
    if hasattr(point, "co"):
        point.co = location
    elif hasattr(point, "position"):
        point.position = location
    else:
        raise RuntimeError("Grease Pencil point has no writable coordinate field.")

    if hasattr(point, "strength"):
        point.strength = 1.0
    if hasattr(point, "opacity"):
        point.opacity = 1.0
    if hasattr(point, "pressure"):
        point.pressure = 1.0
    if hasattr(point, "radius"):
        point.radius = max(0.001, float(line_width) * V3_RADIUS_PER_WIDTH * radius_scale)


def set_layer_thickness(layer: Any, base_width: int, multiplier: float, radius_scale: float) -> bool:
    """Scale a layer's strokes live through its layer-level thickness property.

    GP v3: radius_offset (world units) is added to every point radius, so
    offset = (multiplier - 1) x the radius the layer's thinnest stroke was
    built with (base_width x V3_RADIUS_PER_WIDTH x radius_scale).
    Legacy GPENCIL: line_change (pixels) is added to every line_width, so
    change = round((multiplier - 1) x base_width), never below 1 px.
    """

    multiplier = max(0.0, float(multiplier))
    if hasattr(layer, "radius_offset"):
        base_radius = max(0.001, float(base_width) * V3_RADIUS_PER_WIDTH * float(radius_scale))
        layer.radius_offset = (multiplier - 1.0) * base_radius
        return True
    if hasattr(layer, "line_change"):
        layer.line_change = max(1 - int(base_width), int(round((multiplier - 1.0) * float(base_width))))
        return True
    return False


def write_strokes(
    frame: Any,
    rows: Sequence[tuple[Sequence[Sequence[float]], int, int, bool]],
    *,
    radius_scale: float = 1.0,
) -> int:
    """Write (points, material_index, line_width, cyclic) rows into one frame.

    GP v3 gets one add_strokes call per frame (fast for thousands of fill
    triangles); legacy GPENCIL gets one strokes.new() per row.
    """

    rows = [row for row in rows if len(row[0]) >= 2]
    if not rows:
        return 0
    legacy_strokes = getattr(frame, "strokes", None)
    if legacy_strokes is not None and hasattr(legacy_strokes, "new"):
        for points, material_index, line_width, cyclic in rows:
            stroke = legacy_strokes.new()
            _ensure_stroke_point_count(stroke, len(points))
            _set_stroke_style(stroke, material_index, line_width, cyclic)
            for index, point in enumerate(points):
                _set_point(stroke.points[index], point, line_width, radius_scale)
        return len(rows)

    drawing = getattr(frame, "drawing", None)
    if drawing is None:
        raise RuntimeError("Grease Pencil frame has neither strokes nor drawing API.")
    start = len(drawing.strokes)
    drawing.add_strokes(sizes=[len(points) for points, _m, _w, _c in rows])
    strokes = drawing.strokes
    for offset, (points, material_index, line_width, cyclic) in enumerate(rows):
        stroke = strokes[start + offset]
        _set_stroke_style(stroke, material_index, line_width, cyclic)
        stroke_points = stroke.points
        for index, point in enumerate(points):
            _set_point(stroke_points[index], point, line_width, radius_scale)
    return len(rows)


def _get_or_create_grease_pencil_object(source_object: Any) -> Any:
    gp_name = overlay_object_name(source_object.name)
    existing = bpy.data.objects.get(gp_name)
    if existing is not None:
        if is_graph_debug_object(existing):
            existing.matrix_world = source_object.matrix_world.copy()
            return existing
        bpy.data.objects.remove(existing, do_unlink=True)

    collection = _grease_pencil_collection()
    gp_data = collection.new(gp_name)
    gp_object = bpy.data.objects.new(gp_name, gp_data)
    bpy.context.scene.collection.objects.link(gp_object)
    gp_object.matrix_world = source_object.matrix_world.copy()
    if hasattr(gp_data, "stroke_depth_order"):
        gp_data.stroke_depth_order = "3D"
    if hasattr(gp_data, "stroke_thickness_space"):
        gp_data.stroke_thickness_space = "SCREENSPACE"
    return gp_object


def _matches(name: str, exact: str | None, prefix: str) -> bool:
    """One source: its exact name only (Arc never clears ArcX); no source: every debug item."""

    return name == exact if exact is not None else name.startswith(prefix)


def remove_labels(source_name: str | None = None) -> None:
    exact = label_collection_name(source_name) if source_name else None
    for collection in list(bpy.data.collections):
        if _matches(collection.name, exact, LABEL_COLLECTION_PREFIX):
            for obj in list(collection.objects):
                data = obj.data
                bpy.data.objects.remove(obj, do_unlink=True)
                if data and getattr(data, "users", 0) == 0:
                    bpy.data.curves.remove(data)
            bpy.data.collections.remove(collection)


def draw_labels(source_object: Any, labels: Sequence[dict[str, Any]]) -> int:
    """Create one text object per label; positions are mesh-local."""

    remove_labels(source_object.name)
    collection = bpy.data.collections.new(label_collection_name(source_object.name))
    bpy.context.scene.collection.children.link(collection)
    materials: dict[tuple[float, ...], Any] = {}
    count = 0
    for label in labels:
        text = str(label.get("text") or "")
        position = label.get("position") or ()
        if not text or len(position) != 3:
            continue
        color = tuple(float(value) for value in label.get("color", (1.0, 1.0, 1.0, 1.0)))
        material = materials.get(color)
        if material is None:
            name = f"{LABEL_MATERIAL_PREFIX}{color_hex(color)}"  # the name fixes the colour
            material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
            material.diffuse_color = color
            materials[color] = material
        curve_name = f"{LABEL_OBJECT_PREFIX}{_safe_object_suffix(text)}"
        curve_data = bpy.data.curves.new(curve_name, type="FONT")
        curve_data.body = text
        curve_data.size = float(label.get("size", LABEL_SIZE))
        curve_data.align_x = "CENTER"
        curve_data.align_y = "CENTER"
        curve_data.materials.append(material)
        label_object = bpy.data.objects.new(curve_name, curve_data)
        label_object.location = source_object.matrix_world @ Vector(tuple(float(value) for value in position))
        label_object.hide_select = True
        collection.objects.link(label_object)
        count += 1
    return count


def clear_overlay(source_name: str | None = None) -> None:
    exact = overlay_object_name(source_name) if source_name else None
    for obj in list(bpy.data.objects):
        if _matches(obj.name, exact, GP_OBJECT_PREFIX):
            data_name = getattr(obj.data, "name", "")
            bpy.data.objects.remove(obj, do_unlink=True)
            for collection in (
                getattr(bpy.data, "grease_pencils_v3", None),
                getattr(bpy.data, "grease_pencils", None),
            ):
                if collection is not None and data_name in collection:
                    data = collection[data_name]
                    if getattr(data, "users", 0) == 0:
                        collection.remove(data)

    remove_labels(source_name)

    for material in list(bpy.data.materials):
        if material.users != 0:
            continue
        if material.name.startswith((MATERIAL_PREFIX,) + LEGACY_MATERIAL_PREFIXES):
            bpy.data.materials.remove(material)
