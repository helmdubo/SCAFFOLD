from __future__ import annotations

import bpy

from .constants import GP_DEBUG_PREFIX
from .debug import (
    clear_visualization,
    create_frontier_visualization,
    create_visualization,
)
from .analysis import format_patch_graph_report
from .model import UVSettings
from .operators_pipeline import (
    _build_scaffold_map_with_straighten,
    _prepare_patch_graph,
    _print_console_report,
)
from .solve import build_solver_graph, format_root_scaffold_report, plan_solve_phase1


def _build_debug_settings(settings) -> dict:
    loops_visible = bool(settings.dbg_grp_loops)
    overlay_visible = bool(settings.dbg_grp_overlay)
    return {
        "patches_wall": bool(settings.dbg_grp_patches and settings.dbg_patches_wall),
        "patches_floor": bool(settings.dbg_grp_patches and settings.dbg_patches_floor),
        "patches_slope": bool(settings.dbg_grp_patches and settings.dbg_patches_slope),
        "loops_chains": bool(loops_visible and settings.dbg_loops_chains),
        "loops_boundary": loops_visible,
        "loops_holes": bool(loops_visible and settings.dbg_loops_holes),
        "overlay_basis": overlay_visible,
        "overlay_centers": overlay_visible,
        "overlay_labels": bool(overlay_visible and settings.dbg_overlay_labels),
        "frontier_path": True,
    }


def _refresh_debug_layers(context, patch_graph, source_obj, scaffold_map=None):
    dbg_settings = _build_debug_settings(context.scene.hotspotuv_settings)
    create_visualization(patch_graph, source_obj, dbg_settings)
    if scaffold_map is not None:
        create_frontier_visualization(patch_graph, scaffold_map, source_obj, dbg_settings)


def _find_screen_override():
    for window in bpy.context.window_manager.windows:
        screen = window.screen
        for area in screen.areas:
            if area.type not in {"VIEW_3D", "DOPESHEET_EDITOR", "TIMELINE"}:
                continue
            region = next((reg for reg in area.regions if reg.type == "WINDOW"), None)
            if region is None:
                continue
            return {
                "window": window,
                "screen": screen,
                "area": area,
                "region": region,
            }
    return None


def _stop_animation_playback():
    override = _find_screen_override()
    if override is not None:
        with bpy.context.temp_override(**override):
            try:
                bpy.ops.screen.animation_cancel(restore_frame=False)
                return
            except Exception:
                try:
                    bpy.ops.screen.animation_play()
                    return
                except Exception:
                    pass
    try:
        bpy.ops.screen.animation_cancel(restore_frame=False)
    except Exception:
        try:
            bpy.ops.screen.animation_play()
        except Exception:
            pass


def _force_clear_debug_state(context, source_obj=None, reset_timeline=False):
    settings = context.scene.hotspotuv_settings

    if context.active_object and context.active_object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    resolved_source = source_obj
    if resolved_source is None:
        source_name = settings.dbg_replay_source_object or settings.dbg_source_object
        if source_name and source_name in bpy.data.objects:
            resolved_source = bpy.data.objects[source_name]
        else:
            obj = context.active_object
            if obj:
                if obj.name.startswith(GP_DEBUG_PREFIX):
                    src_name = obj.name[len(GP_DEBUG_PREFIX) :]
                    resolved_source = bpy.data.objects.get(src_name)
                elif obj.type == "MESH":
                    resolved_source = obj

    if resolved_source is not None and resolved_source.name in bpy.data.objects:
        resolved_source.hide_viewport = False
        resolved_source.hide_set(False)
        clear_visualization(resolved_source)
        bpy.ops.object.select_all(action="DESELECT")
        resolved_source.select_set(True)
        context.view_layer.objects.active = resolved_source

    if reset_timeline:
        context.scene.frame_current = context.scene.frame_start

    settings.dbg_active = False
    settings.dbg_source_object = ""
    settings.dbg_replay_active = False
    settings.dbg_replay_source_object = ""
    settings.dbg_replay_cleanup_pending = False


def _finish_frontier_replay(scene_name):
    scene = bpy.data.scenes.get(scene_name)
    if scene is None:
        return None
    settings = scene.hotspotuv_settings
    if not settings.dbg_replay_cleanup_pending:
        return None

    _stop_animation_playback()
    scene.frame_current = scene.frame_start
    source_obj = None
    source_name = settings.dbg_replay_source_object or settings.dbg_source_object
    if source_name and source_name in bpy.data.objects:
        source_obj = bpy.data.objects[source_name]
    _force_clear_debug_state(bpy.context, source_obj=source_obj, reset_timeline=False)
    return None


def _frontier_replay_frame_handler(scene, _depsgraph=None):
    settings = getattr(scene, "hotspotuv_settings", None)
    if settings is None or not settings.dbg_replay_active or settings.dbg_replay_cleanup_pending:
        return
    if scene.frame_current < scene.frame_end:
        return
    settings.dbg_replay_cleanup_pending = True
    bpy.app.timers.register(lambda: _finish_frontier_replay(scene.name), first_interval=0.0)


def _enter_debug_mode(context, obj):
    settings = context.scene.hotspotuv_settings

    try:
        obj, bm, patch_graph, _om, _sel = _prepare_patch_graph(
            context,
            require_selection=not (obj.mode == "OBJECT"),
        )
    except ValueError:
        if obj.mode != "EDIT":
            bpy.ops.object.mode_set(mode="EDIT")
        return None

    bpy.ops.object.mode_set(mode="OBJECT")

    dbg_settings = _build_debug_settings(settings)
    gp_obj = create_visualization(patch_graph, obj, dbg_settings)

    obj.hide_viewport = True
    bpy.ops.object.select_all(action="DESELECT")
    gp_obj.select_set(True)
    context.view_layer.objects.active = gp_obj

    settings.dbg_active = True
    settings.dbg_source_object = obj.name

    report = format_patch_graph_report(patch_graph, mesh_name=obj.name)
    _print_console_report(
        "CFTUV PatchGraph Analyze",
        report.lines,
        report.summary,
        show_lines=bool(settings.dbg_verbose_console),
    )

    try:
        solver_graph = build_solver_graph(
            patch_graph,
            straighten_enabled=bool(getattr(settings, "straighten_strips", False)),
        )
        solve_plan = plan_solve_phase1(patch_graph, solver_graph)
        solve_settings = UVSettings.from_blender_settings(settings)
        scaffold_map = _build_scaffold_map_with_straighten(patch_graph, solve_plan, solve_settings)
        scaffold_report = format_root_scaffold_report(patch_graph, scaffold_map, mesh_name=obj.name)
        _print_console_report(
            "CFTUV Scaffold (Analyze)",
            scaffold_report.lines,
            scaffold_report.summary,
            show_lines=bool(settings.dbg_verbose_console),
        )
        create_frontier_visualization(patch_graph, scaffold_map, obj, dbg_settings)
    except Exception as exc:
        _print_console_report("CFTUV Analyze", [], f"Scaffold failed: {exc}", show_lines=False)

    return report.summary


def _exit_debug_mode(context):
    settings = context.scene.hotspotuv_settings
    source_name = settings.dbg_source_object

    if context.active_object and context.active_object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    if source_name and source_name in bpy.data.objects:
        source_obj = bpy.data.objects[source_name]
        clear_visualization(source_obj)
        source_obj.hide_viewport = False
        bpy.ops.object.select_all(action="DESELECT")
        source_obj.select_set(True)
        context.view_layer.objects.active = source_obj

    settings.dbg_active = False
    settings.dbg_source_object = ""


__all__ = [
    "_refresh_debug_layers",
    "_stop_animation_playback",
    "_force_clear_debug_state",
    "_frontier_replay_frame_handler",
    "_enter_debug_mode",
    "_exit_debug_mode",
]
