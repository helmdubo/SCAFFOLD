"""Render ScaffoldGraph inspection overlay into Blender Grease Pencil.

This standalone development script may import Blender APIs because it lives
outside scaffold_core. It consumes the pipeline inspection overlay payload and
does not recompute graph semantics from mesh data.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

import bpy


EDGE_LAYER_NAME = "ScaffoldGraph_Edges"
NODE_LAYER_NAME = "ScaffoldGraph_Nodes"
GP_OBJECT_NAME = "ScaffoldGraph_Overlay"
EDGE_MATERIAL_NAME = "ScaffoldGraph_Edge_Material"
NODE_MATERIAL_NAME = "ScaffoldGraph_Node_Material"
EDGE_COLOR = (0.1, 0.75, 1.0, 1.0)
NODE_COLOR = (1.0, 0.95, 0.2, 1.0)
EDGE_WIDTH = 5
NODE_WIDTH = 9
NODE_MARKER_SIZE = 0.045


def _add_repo_root_to_path() -> None:
    text = getattr(getattr(bpy.context, "space_data", None), "text", None)
    text_path = (
        Path(bpy.path.abspath(text.filepath)).resolve()
        if getattr(text, "filepath", "")
        else None
    )
    text_paths = tuple(
        Path(bpy.path.abspath(blender_text.filepath)).resolve()
        for blender_text in bpy.data.texts
        if getattr(blender_text, "filepath", "")
    )
    env_path = (
        Path(os.environ["SCAFFOLD_REPO_ROOT"]).resolve()
        if os.environ.get("SCAFFOLD_REPO_ROOT")
        else None
    )
    script_path = Path(__file__).resolve()
    for candidate in (
        env_path,
        text_path,
        *text_paths,
        script_path,
        *script_path.parents,
        Path.cwd(),
    ):
        if candidate is None:
            continue
        repo_root = candidate if (candidate / "scaffold_core").is_dir() else candidate.parent
        if (repo_root / "scaffold_core").is_dir():
            repo_root_text = str(repo_root)
            if repo_root_text not in sys.path:
                sys.path.insert(0, repo_root_text)
            return
    raise RuntimeError(
        "Could not locate repository root containing scaffold_core. "
        "Open this script from disk or set SCAFFOLD_REPO_ROOT."
    )


_add_repo_root_to_path()

from scaffold_core.layer_0_source.blender_io import read_source_mesh_from_blender  # noqa: E402
from scaffold_core.pipeline.inspection import inspect_pipeline_context  # noqa: E402
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations  # noqa: E402


def _script_args(argv: Sequence[str]) -> argparse.Namespace:
    args = list(argv)
    if "--" in args:
        args = args[args.index("--") + 1:]
    else:
        args = []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-json", type=Path, default=None)
    return parser.parse_args(args)


def _active_mesh_object() -> Any:
    active_object = getattr(bpy.context, "object", None)
    if active_object is not None and getattr(active_object, "type", None) == "MESH":
        return active_object

    for candidate in bpy.context.scene.objects:
        if getattr(candidate, "type", None) == "MESH":
            bpy.context.view_layer.objects.active = candidate
            candidate.select_set(True)
            return candidate

    raise RuntimeError("No mesh object is available for ScaffoldGraph overlay rendering.")


def _build_overlay_payload() -> dict[str, Any]:
    _active_mesh_object()
    source = read_source_mesh_from_blender(bpy.context)
    context = run_pass_1_relations(run_pass_0(source))
    report = inspect_pipeline_context(context, detail="full")
    overlay = report.get("scaffold_graph_overlay")
    if not isinstance(overlay, dict):
        raise RuntimeError("Pipeline inspection did not emit scaffold_graph_overlay.")
    return overlay


def _grease_pencil_collection() -> Any:
    grease_pencils_v3 = getattr(bpy.data, "grease_pencils_v3", None)
    if grease_pencils_v3 is not None:
        return grease_pencils_v3
    grease_pencils = getattr(bpy.data, "grease_pencils", None)
    if grease_pencils is not None:
        return grease_pencils
    raise RuntimeError("Grease Pencil data-block collection is unavailable.")


def _is_grease_pencil_object(obj: Any) -> bool:
    return getattr(obj, "type", None) in {"GREASEPENCIL", "GPENCIL"}


def _get_or_create_grease_pencil_object(source_object: Any) -> Any:
    existing = bpy.data.objects.get(GP_OBJECT_NAME)
    if existing is not None:
        if _is_grease_pencil_object(existing):
            existing.matrix_world = source_object.matrix_world.copy()
            return existing
        bpy.data.objects.remove(existing, do_unlink=True)

    collection = _grease_pencil_collection()
    gp_data = collection.new(GP_OBJECT_NAME)
    gp_object = bpy.data.objects.new(GP_OBJECT_NAME, gp_data)
    bpy.context.scene.collection.objects.link(gp_object)
    gp_object.matrix_world = source_object.matrix_world.copy()
    if hasattr(gp_data, "stroke_depth_order"):
        gp_data.stroke_depth_order = "3D"
    if hasattr(gp_data, "stroke_thickness_space"):
        gp_data.stroke_thickness_space = "SCREENSPACE"
    return gp_object


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


def _ensure_layer(gp_data: Any, layer_name: str) -> Any:
    layer = _find_layer(gp_data, layer_name)
    if layer is None:
        layer = gp_data.layers.new(layer_name, set_active=False)
    else:
        _clear_layer(layer)
    return layer


def _ensure_frame(layer: Any) -> Any:
    frames = getattr(layer, "frames", None)
    if frames is None:
        raise RuntimeError(f"Grease Pencil layer {_layer_name(layer)!r} has no frames API.")
    if len(frames) > 0:
        return frames[0]
    return frames.new(0)


def _ensure_material(gp_data: Any, material_name: str, color: tuple[float, float, float, float]) -> int:
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


def _add_stroke(frame: Any, points: Sequence[Sequence[float]], material_index: int, line_width: int) -> bool:
    if len(points) < 2:
        return False
    stroke = _new_stroke(frame, len(points))
    _set_stroke_style(stroke, material_index, line_width)
    for index, point in enumerate(points):
        _set_point(stroke.points[index], point, line_width)
    return True


def _node_marker_strokes(position: Sequence[float]) -> tuple[tuple[tuple[float, float, float], ...], ...]:
    x, y, z = (float(position[0]), float(position[1]), float(position[2]))
    size = NODE_MARKER_SIZE
    return (
        ((x - size, y, z), (x + size, y, z)),
        ((x, y - size, z), (x, y + size, z)),
    )


def _draw_edges(frame: Any, material_index: int, edges: Iterable[dict[str, Any]]) -> int:
    stroke_count = 0
    for edge in edges:
        polyline = edge.get("polyline", ())
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


def render_overlay(overlay: dict[str, Any]) -> dict[str, Any]:
    source_object = _active_mesh_object()
    gp_object = _get_or_create_grease_pencil_object(source_object)
    gp_data = gp_object.data

    edge_layer = _ensure_layer(gp_data, EDGE_LAYER_NAME)
    node_layer = _ensure_layer(gp_data, NODE_LAYER_NAME)
    edge_frame = _ensure_frame(edge_layer)
    node_frame = _ensure_frame(node_layer)
    edge_material_index = _ensure_material(gp_data, EDGE_MATERIAL_NAME, EDGE_COLOR)
    node_material_index = _ensure_material(gp_data, NODE_MATERIAL_NAME, NODE_COLOR)

    edges = list(overlay.get("edges", ()))
    nodes = list(overlay.get("nodes", ()))
    edge_stroke_count = _draw_edges(edge_frame, edge_material_index, edges)
    node_marker_count = _draw_nodes(node_frame, node_material_index, nodes)

    return {
        "scaffold_node_count": int(overlay.get("scaffold_node_count", len(nodes))),
        "scaffold_edge_count": int(overlay.get("scaffold_edge_count", len(edges))),
        "grease_pencil_object": gp_object.name,
        "edge_layer": EDGE_LAYER_NAME,
        "node_layer": NODE_LAYER_NAME,
        "edge_stroke_count": edge_stroke_count,
        "node_marker_count": node_marker_count,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _script_args(sys.argv if argv is None else argv)
    overlay = _build_overlay_payload()
    render_report = render_overlay(overlay)
    report_text = json.dumps(render_report, separators=(",", ":"), sort_keys=True)
    print(report_text)
    if args.report_json is not None:
        args.report_json.write_text(report_text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
