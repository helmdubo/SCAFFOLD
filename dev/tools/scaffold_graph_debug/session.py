"""Session helpers for the Scaffold structure debugger."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

import bpy

from .debug import clear_overlay, is_graph_debug_object, overlay_object_name
from .draw_v2 import apply_layer_visibility, apply_line_thickness, render_debug_overlay

REPORT_TEXT_PREFIX = "Scaffold_Debug_Report__"


def _add_repo_root_to_path() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    repo_root_text = str(repo_root)
    if repo_root_text not in sys.path:
        sys.path.insert(0, repo_root_text)


def active_mesh_object(context: Any, *, fallback_source_name: str = "") -> Any:
    obj = getattr(context, "active_object", None)
    if obj is not None and getattr(obj, "type", None) == "MESH":
        return obj
    if fallback_source_name:
        source_obj = bpy.data.objects.get(fallback_source_name)
        if source_obj is not None and getattr(source_obj, "type", None) == "MESH":
            return source_obj
    raise RuntimeError("Select a mesh object.")


def build_payload(
    reader_context: Any,
    *,
    straighten_strips: bool,
    object_name: str,
    capture: bool = True,
    straighten_bevel_strips: bool = True,
    world_up: tuple[float, float, float] | None = None,
    horizontal_angle_degrees: float = 45.0,
) -> dict[str, Any]:
    """Pass 0, 1, 2, 3 (the user filter), the skeleton solve (quilts + skeletons + pins) once, then the payload.

    capture writes the read mesh to reports/last_mesh_snapshot.json (panel use).
    world_up None runs no filter (the pipeline default).
    """

    _add_repo_root_to_path()
    from scaffold_core.layer_0_source.blender_io import read_source_mesh_from_blender
    from scaffold_core.layer_4_features.model import FeatureOptions
    from scaffold_core.layer_5_runtime.pins import run_skeleton_solve
    from scaffold_core.pipeline.passes import (
        run_pass_0,
        run_pass_1_relations,
        run_pass_2_features,
        run_pass_3_filters,
    )
    from scaffold_core.user_filters.model import FilterOptions
    from .overlay_v2 import build_debug_payload

    source = read_source_mesh_from_blender(reader_context)
    if capture:
        try:
            from .snapshot_io import dump_source_snapshot

            dump_source_snapshot(source, Path(__file__).resolve().parent / "reports" / "last_mesh_snapshot.json")
        except Exception as exc:  # capture must never break the overlay
            print(f"[scaffold debug] snapshot capture failed: {exc}")
    if not source.selected_face_ids:
        raise RuntimeError("select faces before analyzing")
    context = run_pass_2_features(
        run_pass_1_relations(run_pass_0(source)),
        FeatureOptions(
            straighten_strips=bool(straighten_strips),
            straighten_bevel_strips=bool(straighten_bevel_strips),
        ),
    )
    context = run_pass_3_filters(context, FilterOptions(world_up, horizontal_angle_degrees))
    solve = run_skeleton_solve(context)
    return build_debug_payload(context, solve, object_name=object_name)


WORLD_UP_BY_AXIS = {
    "+X": (1.0, 0.0, 0.0), "-X": (-1.0, 0.0, 0.0),
    "+Y": (0.0, 1.0, 0.0), "-Y": (0.0, -1.0, 0.0),
    "+Z": (0.0, 0.0, 1.0), "-Z": (0.0, 0.0, -1.0),
}


def filter_from_settings(settings: Any) -> tuple[tuple[float, float, float] | None, float]:
    """(world_up, horizontal angle) of the panel's filter options; world_up None when the filter is off."""

    angle = float(getattr(settings, "horizontal_angle", 45.0))
    if not bool(getattr(settings, "split_vertical_from_horizontal", True)):
        return None, angle
    return WORLD_UP_BY_AXIS[str(getattr(settings, "world_up_axis", "+Z"))], angle


def object_space_up(obj: Any, world_up: tuple[float, float, float] | None) -> tuple[float, float, float] | None:
    """The world axis world_up in obj's own space (FilterOptions.world_up is a mesh-space direction).

    Turned by the inverse of the 3x3 part of matrix_world, which under a
    rotation and a uniform scale (mirroring included) keeps every angle
    between a normal and the up line. A non-uniform scale changes those
    angles in world space; that is a stated limit, not handled here.
    """

    if world_up is None or obj is None:
        return world_up
    from mathutils import Vector

    return tuple(float(value) for value in obj.matrix_world.to_3x3().inverted_safe() @ Vector(world_up))


def visibility_from_settings(settings: Any) -> dict[str, bool]:
    from .overlay_v2 import LAYER_SPECS

    return {spec.layer: bool(getattr(settings, spec.prop, spec.default)) for spec in LAYER_SPECS}


def write_report_text(source_name: str, report: str) -> None:
    name = f"{REPORT_TEXT_PREFIX}{source_name}"
    text = bpy.data.texts.get(name) or bpy.data.texts.new(name)
    text.clear()
    text.write(report + "\n")


def _summary(payload: dict[str, Any]) -> str:
    layers = payload["layers"]
    seams = layers["Scaffold_Seams"]
    islands = sum(
        len(layers[name])
        for name in (
            "Scaffold_Islands_UNFOLDED", "Scaffold_Islands_FRAME_FREE", "Scaffold_Islands_STRIP", "Scaffold_Islands_LADDER",
        )
    )
    return (
        f"patches:{len(layers['Scaffold_Patches'])} islands:{islands} "
        f"lines:{len(layers['Scaffold_Skeleton_Lines'])} pins:{len(layers['Scaffold_Pins'])} "
        f"seams stitched:{sum(item['accepted'] for item in seams)} cut:{sum(not item['accepted'] for item in seams)}"
    )


def show_or_refresh(context: Any) -> tuple[dict[str, Any], str]:
    settings = context.scene.scaffold_graph_debug_settings
    source_object = active_mesh_object(
        context,
        fallback_source_name=settings.source_object if settings.active else "",
    )
    starting_new_session = (not settings.active) or settings.source_object != source_object.name
    if starting_new_session:
        if settings.active and settings.source_object:
            close(context)
        settings.source_hide_viewport = bool(getattr(source_object, "hide_viewport", False))
        hide_get = getattr(source_object, "hide_get", None)
        settings.source_hide_set = bool(hide_get()) if callable(hide_get) else False

    source_object.hide_viewport = False
    source_object.hide_set(False)
    source_was_edit = getattr(source_object, "mode", None) == "EDIT"
    if not source_was_edit:
        if context.active_object and context.active_object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="DESELECT")
        source_object.select_set(True)
        context.view_layer.objects.active = source_object

    world_up, horizontal_angle = filter_from_settings(settings)
    world_up = object_space_up(source_object, world_up)
    payload = build_payload(
        context,
        straighten_strips=bool(settings.straighten_strips),
        straighten_bevel_strips=bool(getattr(settings, "straighten_bevel_strips", True)),
        object_name=source_object.name,
        world_up=world_up,
        horizontal_angle_degrees=horizontal_angle,
    )
    if context.active_object and context.active_object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    render_debug_overlay(
        source_object,
        payload,
        visibility_from_settings(settings),
        show_labels=bool(settings.show_labels),
        line_thickness=float(settings.line_thickness),
    )
    print(payload["report"])
    write_report_text(source_object.name, payload["report"])

    gp_object = bpy.data.objects.get(overlay_object_name(source_object.name))
    if is_graph_debug_object(gp_object):
        bpy.ops.object.select_all(action="DESELECT")
        source_object.hide_viewport = True
        source_object.hide_set(True)
        gp_object.hide_viewport = False
        gp_object.hide_set(False)
        gp_object.select_set(True)
        context.view_layer.objects.active = gp_object

    settings.active = True
    settings.source_object = source_object.name
    settings.source_ref = source_object
    settings.last_report = _summary(payload)
    return payload, settings.last_report


def close(context: Any) -> str:
    settings = context.scene.scaffold_graph_debug_settings
    source_name = settings.source_object or None
    clear_overlay(source_name)
    source_object = _stored_source(settings)
    if source_object is not None:
        source_object.hide_viewport = bool(settings.source_hide_viewport)
        source_object.hide_set(bool(settings.source_hide_set))
        if not source_object.hide_viewport and not source_object.hide_get():
            if context.active_object and context.active_object.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            bpy.ops.object.select_all(action="DESELECT")
            source_object.select_set(True)
            context.view_layer.objects.active = source_object
    settings.active = False
    settings.source_object = ""
    settings.source_ref = None
    settings.source_hide_viewport = False
    settings.source_hide_set = False
    settings.last_report = "closed"
    return settings.last_report


def _stored_source(settings: Any) -> Any:
    """The analysed mesh by its stored name, else by reference (it was renamed); None when deleted."""

    source_object = bpy.data.objects.get(settings.source_object) if settings.source_object else None
    if source_object is None:
        source_object = getattr(settings, "source_ref", None)
    return source_object


def refresh_visibility(context: Any) -> None:
    settings = context.scene.scaffold_graph_debug_settings
    if settings.source_object:
        apply_layer_visibility(
            settings.source_object,
            visibility_from_settings(settings),
            show_labels=bool(settings.show_labels),
        )


def refresh_line_thickness(context: Any) -> None:
    settings = context.scene.scaffold_graph_debug_settings
    if settings.source_object:
        apply_line_thickness(settings.source_object, float(settings.line_thickness))


def clear_all() -> None:
    """Unregister: end every scene's session (restoring its mesh), then drop every overlay."""

    for scene in bpy.data.scenes:
        settings = getattr(scene, "scaffold_graph_debug_settings", None)
        if settings is None or not settings.active:
            continue
        source_object = _stored_source(settings)
        if source_object is not None:
            source_object.hide_viewport = bool(settings.source_hide_viewport)
            try:
                source_object.hide_set(bool(settings.source_hide_set))
            except RuntimeError:  # not in the current view layer
                pass
        settings.active = False
        settings.source_object = ""
        settings.source_ref = None
    clear_overlay()
