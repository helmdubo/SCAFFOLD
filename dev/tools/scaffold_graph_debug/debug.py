"""Grease Pencil drawing helpers for the ScaffoldGraph dev overlay.

This module may import Blender APIs because it lives outside scaffold_core. It
only consumes the pipeline inspection overlay payload and does not recompute
ScaffoldGraph semantics.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

import bpy
from mathutils import Vector


EDGE_LAYER_NAME = "ScaffoldGraph_Edges"
NODE_LAYER_NAME = "ScaffoldGraph_Nodes"
GP_OBJECT_PREFIX = "ScaffoldGraph_Overlay__"
LABEL_COLLECTION_PREFIX = "ScaffoldGraph_Labels__"
LABEL_OBJECT_PREFIX = "ScaffoldGraph_Label__"
EDGE_MATERIAL_NAME = "ScaffoldGraph_Edge_Material"
NODE_MATERIAL_NAME = "ScaffoldGraph_Node_Material"
LABEL_MATERIAL_NAME = "ScaffoldGraph_Label_Material"
EDGE_COLOR = (0.1, 0.75, 1.0, 1.0)
NODE_COLOR = (1.0, 0.95, 0.2, 1.0)
LABEL_COLOR = (1.0, 1.0, 1.0, 1.0)
EDGE_WIDTH = 5
NODE_WIDTH = 9
NODE_MARKER_SIZE = 0.045
LABEL_SIZE = 0.12
LABEL_LIFT = 0.06
EDGE_LANE_SPACING = 0.035
EDGE_LANE_ROUND_DIGITS = 6
GP_OBJECT_TYPES = {"GREASEPENCIL", "GPENCIL"}


def _safe_object_suffix(name: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"_", "-", "."} else "_" for ch in name)
    return safe or "mesh"


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
) -> int:
    material = bpy.data.materials.get(material_name)
    if material is None:
        material = bpy.data.materials.new(material_name)
    if not getattr(material, "grease_pencil", None):
        bpy.data.materials.create_gpencil_data(material)
    material.grease_pencil.color = color
    material.grease_pencil.show_fill = False

    for index, slot in enumerate(gp_data.materials):
        if slot is not None and slot.name == material_name:
            return index
    gp_data.materials.append(material)
    return len(gp_data.materials) - 1


def _new_stroke(frame: Any, point_count: int) -> Any:
    strokes = getattr(frame, "strokes", None)
    if strokes is not None and hasattr(strokes, "new"):
        stroke = strokes.new()
        stroke.points.add(point_count - 1)
        return stroke

    drawing = getattr(frame, "drawing", None)
    if drawing is None:
        raise RuntimeError("Grease Pencil frame has neither strokes nor drawing API.")
    drawing.add_strokes(sizes=[point_count])
    return drawing.strokes[-1]


def _set_stroke_style(stroke: Any, material_index: int, line_width: int) -> None:
    stroke.material_index = material_index
    if hasattr(stroke, "line_width"):
        stroke.line_width = line_width
    if hasattr(stroke, "radius"):
        stroke.radius = float(line_width)
    if hasattr(stroke, "use_cyclic"):
        stroke.use_cyclic = False
    elif hasattr(stroke, "cyclic"):
        stroke.cyclic = False


def _set_point(point: Any, coords: Sequence[float], line_width: int) -> None:
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
        point.radius = max(0.001, float(line_width) * 0.00075)


def _add_stroke(
    frame: Any,
    points: Sequence[Sequence[float]],
    material_index: int,
    line_width: int,
) -> bool:
    if len(points) < 2:
        return False
    stroke = _new_stroke(frame, len(points))
    _set_stroke_style(stroke, material_index, line_width)
    for index, point in enumerate(points):
        _set_point(stroke.points[index], point, line_width)
    return True


def _node_marker_strokes(
    position: Sequence[float],
) -> tuple[tuple[tuple[float, float, float], ...], ...]:
    x, y, z = (float(position[0]), float(position[1]), float(position[2]))
    size = NODE_MARKER_SIZE
    return (
        ((x - size, y, z), (x + size, y, z)),
        ((x, y - size, z), (x, y + size, z)),
    )


def _edge_label(edge: dict[str, Any]) -> str:
    return str(edge.get("display_label") or edge.get("id") or edge.get("patch_chain_id") or "")


def _node_label(node: dict[str, Any]) -> str:
    return str(node.get("display_label") or node.get("id") or "")


def _rounded_polyline_point(point: Sequence[float]) -> tuple[float, float, float]:
    return (
        round(float(point[0]), EDGE_LANE_ROUND_DIGITS),
        round(float(point[1]), EDGE_LANE_ROUND_DIGITS),
        round(float(point[2]), EDGE_LANE_ROUND_DIGITS),
    )


def _coincident_polyline_key(polyline: Sequence[Sequence[float]]) -> tuple[tuple[float, float, float], ...]:
    rounded = tuple(_rounded_polyline_point(point) for point in polyline if len(point) == 3)
    reversed_rounded = tuple(reversed(rounded))
    return min(rounded, reversed_rounded)


def _lane_perpendicular(
    key: tuple[tuple[float, float, float], ...],
) -> Vector:
    points = [Vector(point) for point in key]
    for first, second in zip(points, points[1:]):
        direction = second - first
        if direction.length > 1.0e-8:
            direction.normalize()
            axis = min(
                (Vector((0.0, 0.0, 1.0)), Vector((0.0, 1.0, 0.0)), Vector((1.0, 0.0, 0.0))),
                key=lambda candidate: abs(direction.dot(candidate)),
            )
            perpendicular = direction.cross(axis)
            if perpendicular.length > 1.0e-8:
                perpendicular.normalize()
                return perpendicular
    return Vector((0.0, 0.0, 1.0))


def _offset_polyline(
    polyline: Sequence[Sequence[float]],
    offset: Vector,
) -> list[tuple[float, float, float]]:
    return [
        (
            float(point[0]) + offset.x,
            float(point[1]) + offset.y,
            float(point[2]) + offset.z,
        )
        for point in polyline
        if len(point) == 3
    ]


def _display_edges(edges: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[tuple[float, float, float], ...], list[tuple[int, dict[str, Any]]]] = {}
    display_edges = [dict(edge) for edge in edges]
    for index, edge in enumerate(display_edges):
        polyline = edge.get("polyline", ())
        if len(polyline) < 2:
            edge["display_polyline"] = polyline
            continue
        groups.setdefault(_coincident_polyline_key(polyline), []).append((index, edge))

    for key, group in groups.items():
        ordered_group = sorted(
            group,
            key=lambda item: (
                _edge_label(item[1]),
                str(item[1].get("id", "")),
                str(item[1].get("patch_chain_id", "")),
            ),
        )
        perpendicular = _lane_perpendicular(key)
        midpoint = (len(ordered_group) - 1) * 0.5
        for lane_index, (edge_index, edge) in enumerate(ordered_group):
            amount = (lane_index - midpoint) * EDGE_LANE_SPACING
            offset = perpendicular * amount if len(ordered_group) > 1 else Vector((0.0, 0.0, 0.0))
            display_edges[edge_index]["display_polyline"] = _offset_polyline(
                edge.get("polyline", ()),
                offset,
            )
    return display_edges


def _draw_edges(frame: Any, material_index: int, edges: Iterable[dict[str, Any]]) -> int:
    stroke_count = 0
    for edge in edges:
        polyline = edge.get("display_polyline", edge.get("polyline", ()))
        if _add_stroke(frame, polyline, material_index, EDGE_WIDTH):
            stroke_count += 1
    return stroke_count


def _draw_nodes(frame: Any, material_index: int, nodes: Iterable[dict[str, Any]]) -> int:
    marker_count = 0
    for node in nodes:
        position = node.get("position", ())
        if len(position) != 3:
            continue
        for stroke_points in _node_marker_strokes(position):
            _add_stroke(frame, stroke_points, material_index, NODE_WIDTH)
        marker_count += 1
    return marker_count


def _edge_label_position(polyline: Sequence[Sequence[float]]) -> Vector | None:
    points = [Vector((float(point[0]), float(point[1]), float(point[2]))) for point in polyline]
    if not points:
        return None
    if len(points) == 1:
        return points[0]

    lengths: list[float] = []
    total = 0.0
    for first, second in zip(points, points[1:]):
        length = (second - first).length
        lengths.append(length)
        total += length
    if total <= 1e-8:
        return points[0]

    halfway = total * 0.5
    accumulated = 0.0
    for index, length in enumerate(lengths):
        if accumulated + length >= halfway:
            ratio = (halfway - accumulated) / length if length > 1e-8 else 0.0
            return points[index].lerp(points[index + 1], ratio)
        accumulated += length
    return points[-1]


def _ensure_label_collection(source_name: str) -> Any:
    collection_name = label_collection_name(source_name)
    collection = bpy.data.collections.get(collection_name)
    if collection is None:
        collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(collection)
    else:
        for obj in list(collection.objects):
            data = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if data and getattr(data, "users", 0) == 0:
                bpy.data.curves.remove(data)
    return collection


def _ensure_label_material() -> Any:
    material = bpy.data.materials.get(LABEL_MATERIAL_NAME)
    if material is None:
        material = bpy.data.materials.new(LABEL_MATERIAL_NAME)
    material.diffuse_color = LABEL_COLOR
    return material


def _add_label(
    collection: Any,
    source_object: Any,
    kind: str,
    label: str,
    local_position: Vector,
    material: Any,
) -> None:
    safe_label = _safe_object_suffix(label)
    curve_name = f"{LABEL_OBJECT_PREFIX}{kind}__{safe_label}"
    curve_data = bpy.data.curves.new(curve_name, type="FONT")
    curve_data.body = label
    curve_data.size = LABEL_SIZE
    curve_data.align_x = "CENTER"
    curve_data.align_y = "CENTER"
    curve_data.materials.append(material)

    label_object = bpy.data.objects.new(curve_name, curve_data)
    label_object.location = source_object.matrix_world @ (
        local_position + Vector((0.0, 0.0, LABEL_LIFT))
    )
    collection.objects.link(label_object)


def _draw_labels(
    source_object: Any,
    nodes: Sequence[dict[str, Any]],
    edges: Sequence[dict[str, Any]],
    *,
    visible: bool,
) -> int:
    collection = _ensure_label_collection(source_object.name)
    collection.hide_viewport = not visible
    material = _ensure_label_material()
    label_count = 0

    for node in nodes:
        label = _node_label(node)
        position = node.get("position", ())
        if label and len(position) == 3:
            _add_label(
                collection,
                source_object,
                "node",
                label,
                Vector((float(position[0]), float(position[1]), float(position[2]))),
                material,
            )
            label_count += 1

    for edge in edges:
        label = _edge_label(edge)
        label_position = _edge_label_position(edge.get("display_polyline", edge.get("polyline", ())))
        if label and label_position is not None:
            _add_label(collection, source_object, "edge", label, label_position, material)
            label_count += 1

    return label_count


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


def render_overlay(
    source_object: Any,
    overlay: dict[str, Any],
    *,
    show_edges: bool = True,
    show_nodes: bool = True,
    show_labels: bool = True,
) -> dict[str, Any]:
    gp_object = _get_or_create_grease_pencil_object(source_object)
    gp_data = gp_object.data

    edge_layer = _ensure_layer(gp_data, EDGE_LAYER_NAME, show_edges)
    node_layer = _ensure_layer(gp_data, NODE_LAYER_NAME, show_nodes)
    edge_frame = _ensure_frame(edge_layer)
    node_frame = _ensure_frame(node_layer)
    edge_material_index = _ensure_material(gp_data, EDGE_MATERIAL_NAME, EDGE_COLOR)
    node_material_index = _ensure_material(gp_data, NODE_MATERIAL_NAME, NODE_COLOR)

    edges = list(overlay.get("edges", ()))
    nodes = list(overlay.get("nodes", ()))
    display_edges = _display_edges(edges)
    edge_stroke_count = _draw_edges(edge_frame, edge_material_index, display_edges)
    node_marker_count = _draw_nodes(node_frame, node_material_index, nodes)
    label_count = _draw_labels(
        source_object,
        nodes,
        display_edges,
        visible=show_labels,
    )

    return {
        "scaffold_node_count": int(overlay.get("scaffold_node_count", len(nodes))),
        "scaffold_edge_count": int(overlay.get("scaffold_edge_count", len(edges))),
        "grease_pencil_object": gp_object.name,
        "edge_layer": EDGE_LAYER_NAME,
        "node_layer": NODE_LAYER_NAME,
        "edge_stroke_count": edge_stroke_count,
        "node_marker_count": node_marker_count,
        "label_count": label_count,
    }


def clear_overlay(source_name: str | None = None) -> None:
    prefix = overlay_object_name(source_name) if source_name else GP_OBJECT_PREFIX
    for obj in list(bpy.data.objects):
        if obj.name.startswith(prefix):
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

    label_prefix = label_collection_name(source_name) if source_name else LABEL_COLLECTION_PREFIX
    for collection in list(bpy.data.collections):
        if collection.name.startswith(label_prefix):
            for obj in list(collection.objects):
                data = obj.data
                bpy.data.objects.remove(obj, do_unlink=True)
                if data and getattr(data, "users", 0) == 0:
                    bpy.data.curves.remove(data)
            bpy.data.collections.remove(collection)

    for material in list(bpy.data.materials):
        if (
            material.name in {EDGE_MATERIAL_NAME, NODE_MATERIAL_NAME, LABEL_MATERIAL_NAME}
            and material.users == 0
        ):
            bpy.data.materials.remove(material)


def apply_layer_visibility(
    source_name: str,
    *,
    show_edges: bool,
    show_nodes: bool,
    show_labels: bool,
) -> None:
    obj = bpy.data.objects.get(overlay_object_name(source_name))
    if is_graph_debug_object(obj):
        edge_layer = _find_layer(obj.data, EDGE_LAYER_NAME)
        node_layer = _find_layer(obj.data, NODE_LAYER_NAME)
        if edge_layer is not None and hasattr(edge_layer, "hide"):
            edge_layer.hide = not show_edges
        if node_layer is not None and hasattr(node_layer, "hide"):
            node_layer.hide = not show_nodes

    collection = bpy.data.collections.get(label_collection_name(source_name))
    if collection is not None:
        collection.hide_viewport = not show_labels
