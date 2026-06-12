"""Session helpers for the ScaffoldGraph Blender dev overlay."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

import bpy

from .debug import (
    clear_overlay,
    is_graph_debug_object,
    overlay_object_name,
)
from .draw_v2 import apply_v2_layer_visibility, render_overlay_v2
from .pair_checks import format_continuity_pair_check


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


def _build_overlay_payloads(context: Any) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    _add_repo_root_to_path()
    from scaffold_core.layer_0_source.blender_io import read_source_mesh_from_blender
    from scaffold_core.pipeline.inspection import inspect_pipeline_context
    from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
    from .overlay_v2 import build_overlay_v2_payload

    source = read_source_mesh_from_blender(context)
    pipeline_context = run_pass_1_relations(run_pass_0(source))
    report = inspect_pipeline_context(pipeline_context, detail="full")
    overlay = report.get("scaffold_graph_overlay")
    legacy_overlay = overlay if isinstance(overlay, dict) else None
    return legacy_overlay, build_overlay_v2_payload(pipeline_context)


def _format_summary(report: dict[str, Any]) -> str:
    return (
        f"runs:{report['family_run_segment_count']} "
        f"rails:{report['rail_count']} "
        f"spines:{report['spine_count']} "
        f"parallel:{report['parallel_rail_count']} "
        f"ribs:{report['rib_count']} "
        f"sew:{report['sewable_seam_count']} "
        f"cut:{report['cut_seam_count']} "
        f"junctions:{report['junction_glyph_count']} "
        f"branches:{report['branch_glyph_count']}"
    )


def _write_pair_check_text_block(source_object_name: str, report: str) -> None:
    datablock_name = f"ScaffoldGraph_ContinuityPairCheck__{source_object_name}"
    text = bpy.data.texts.get(datablock_name)
    if text is None:
        text = bpy.data.texts.new(datablock_name)
    else:
        text.clear()
    text.write(report)


def show_or_refresh(context: Any) -> tuple[dict[str, Any], str]:
    settings = context.scene.scaffold_graph_debug_settings
    source_object = active_mesh_object(
        context,
        fallback_source_name=settings.source_object if settings.active else "",
    )
    starting_new_session = (not settings.active) or settings.source_object != source_object.name
    if starting_new_session:
        settings.source_hide_viewport = bool(getattr(source_object, "hide_viewport", False))
        hide_get = getattr(source_object, "hide_get", None)
        settings.source_hide_set = bool(hide_get()) if callable(hide_get) else False

    if context.active_object and context.active_object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    source_object.hide_viewport = False
    source_object.hide_set(False)
    bpy.ops.object.select_all(action="DESELECT")
    source_object.select_set(True)
    context.view_layer.objects.active = source_object

    legacy_overlay, overlay = _build_overlay_payloads(context)
    render_report = render_overlay_v2(
        source_object,
        overlay,
        show_family_colors=bool(settings.show_family_colors),
        show_spines=bool(settings.show_spines),
        show_ribs=bool(settings.show_ribs),
        show_seam_verdicts=bool(settings.show_seam_verdicts),
        show_junctions=bool(settings.show_junctions),
        show_branch_points=bool(settings.show_branch_points),
    )

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
    settings.last_report = _format_summary(render_report)
    print(json.dumps(render_report, separators=(",", ":"), sort_keys=True))
    if legacy_overlay is not None:
        pair_check_report = format_continuity_pair_check(source_object.name, legacy_overlay)
        print(pair_check_report)
        _write_pair_check_text_block(source_object.name, pair_check_report)
    return render_report, settings.last_report


def close(context: Any) -> str:
    settings = context.scene.scaffold_graph_debug_settings
    source_name = settings.source_object or None
    clear_overlay(source_name)
    if source_name and source_name in bpy.data.objects:
        source_object = bpy.data.objects[source_name]
        source_object.hide_viewport = bool(settings.source_hide_viewport)
        source_object.hide_set(bool(settings.source_hide_set))
        if not source_object.hide_viewport and not source_object.hide_get():
            bpy.ops.object.select_all(action="DESELECT")
            source_object.select_set(True)
            context.view_layer.objects.active = source_object
    settings.active = False
    settings.source_object = ""
    settings.source_hide_viewport = False
    settings.source_hide_set = False
    settings.last_report = "closed"
    return settings.last_report


def refresh_visibility(context: Any) -> None:
    settings = context.scene.scaffold_graph_debug_settings
    if settings.source_object:
        apply_v2_layer_visibility(
            settings.source_object,
            show_family_colors=bool(settings.show_family_colors),
            show_spines=bool(settings.show_spines),
            show_ribs=bool(settings.show_ribs),
            show_seam_verdicts=bool(settings.show_seam_verdicts),
            show_junctions=bool(settings.show_junctions),
            show_branch_points=bool(settings.show_branch_points),
        )


def clear_all() -> None:
    clear_overlay()
