"""Session helpers for the ScaffoldGraph Blender dev overlay."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

import bpy

from .debug import apply_layer_visibility, clear_overlay, render_overlay


def _add_repo_root_to_path() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    repo_root_text = str(repo_root)
    if repo_root_text not in sys.path:
        sys.path.insert(0, repo_root_text)


def active_mesh_object(context: Any) -> Any:
    obj = getattr(context, "active_object", None)
    if obj is not None and getattr(obj, "type", None) == "MESH":
        return obj
    raise RuntimeError("Select a mesh object.")


def _build_overlay_payload(context: Any) -> dict[str, Any]:
    _add_repo_root_to_path()
    from scaffold_core.layer_0_source.blender_io import read_source_mesh_from_blender
    from scaffold_core.pipeline.inspection import inspect_pipeline_context
    from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations

    source = read_source_mesh_from_blender(context)
    pipeline_context = run_pass_1_relations(run_pass_0(source))
    report = inspect_pipeline_context(pipeline_context, detail="full")
    overlay = report.get("scaffold_graph_overlay")
    if not isinstance(overlay, dict):
        raise RuntimeError("Pipeline inspection did not emit scaffold_graph_overlay.")
    return overlay


def _format_summary(report: dict[str, Any]) -> str:
    return (
        f"nodes:{report['scaffold_node_count']} "
        f"edges:{report['scaffold_edge_count']} "
        f"strokes:{report['edge_stroke_count']} "
        f"markers:{report['node_marker_count']}"
    )


def show_or_refresh(context: Any) -> tuple[dict[str, Any], str]:
    settings = context.scene.scaffold_graph_debug_settings
    source_object = active_mesh_object(context)
    overlay = _build_overlay_payload(context)
    render_report = render_overlay(
        source_object,
        overlay,
        show_edges=bool(settings.show_edges),
        show_nodes=bool(settings.show_nodes),
    )

    settings.active = True
    settings.source_object = source_object.name
    settings.last_report = _format_summary(render_report)
    print(json.dumps(render_report, separators=(",", ":"), sort_keys=True))
    return render_report, settings.last_report


def close(context: Any) -> str:
    settings = context.scene.scaffold_graph_debug_settings
    source_name = settings.source_object or None
    clear_overlay(source_name)
    settings.active = False
    settings.source_object = ""
    settings.last_report = "closed"
    return settings.last_report


def refresh_visibility(context: Any) -> None:
    settings = context.scene.scaffold_graph_debug_settings
    if settings.source_object:
        apply_layer_visibility(
            settings.source_object,
            show_edges=bool(settings.show_edges),
            show_nodes=bool(settings.show_nodes),
        )


def clear_all() -> None:
    clear_overlay()
