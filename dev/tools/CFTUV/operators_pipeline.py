from __future__ import annotations

from pathlib import Path

import bmesh
import bpy

from .analysis import (
    build_patch_graph_derived_topology,
    build_straighten_structural_support,
    build_patch_graph,
    format_solver_input_preflight_report,
    validate_solver_input_mesh,
)
from .model import MeshPreflightReport, UVSettings
from .solve import build_root_scaffold_map, build_solver_graph, plan_solve_phase1
from .solve_skeleton import apply_skeleton_solve_to_scaffold_map


ADDON_PACKAGE = __package__ or Path(__file__).resolve().parent.name


class _SolverPreflightSelectionError(ValueError):
    """Blocking solver preflight error after selecting offending topology."""

    def __init__(self, summary, selection_message=None):
        super().__init__(summary)
        self.summary = summary
        self.selection_message = selection_message or summary


def _clear_pins_after_phase1_enabled(context) -> bool:
    addon = getattr(context.preferences, "addons", {}).get(ADDON_PACKAGE)
    preferences = getattr(addon, "preferences", None)
    return bool(getattr(preferences, "clear_pins_after_phase1", True))


def _build_scaffold_map_with_straighten(graph, solve_plan, settings):
    """Build scaffold map, optionally applying straighten strips from structural analysis."""

    straighten = getattr(settings, "straighten_strips", False)
    derived_topology = build_patch_graph_derived_topology(graph)
    inherited_map, patch_structural_summaries, patch_shape_classes, straighten_chain_refs, band_spine_data = build_straighten_structural_support(graph)
    scaffold_map = build_root_scaffold_map(
        graph,
        solve_plan,
        settings.final_scale,
        straighten_enabled=straighten,
        inherited_role_map=inherited_map if straighten else None,
        patch_structural_summaries=patch_structural_summaries if straighten else None,
        patch_shape_classes=patch_shape_classes,
        straighten_chain_refs=straighten_chain_refs if straighten else None,
        band_spine_data=band_spine_data if straighten else None,
    )
    scaffold_map, _ = apply_skeleton_solve_to_scaffold_map(
        graph,
        derived_topology,
        scaffold_map,
        solve_plan=solve_plan,
        final_scale=settings.final_scale,
    )
    return scaffold_map


def _print_console_report(title, lines, summary=None, show_lines=True):
    """Print report to System Console."""

    print("=" * 60)
    print(title)
    print("=" * 60)
    if show_lines:
        for line in lines:
            print(line)
        if summary:
            print("-" * 60)
            print(summary)
    else:
        if lines and str(lines[0]).startswith("Mesh:"):
            print(lines[0])
            if summary:
                print("-" * 60)
        if summary:
            print(summary)
    print("=" * 60)


def _safe_snapshot_name(label: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in label.strip())
    return safe or "mesh"


def _regression_snapshot_path(obj) -> Path:
    blend_path = bpy.data.filepath
    if blend_path:
        base_dir = Path(bpy.path.abspath("//"))
        blend_stem = Path(blend_path).stem
    else:
        base_dir = Path(__file__).resolve().parents[1]
        blend_stem = "unsaved_blend"

    snapshot_dir = base_dir / "_cftuv_snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{_safe_snapshot_name(blend_stem)}__{_safe_snapshot_name(obj.name)}.md"
    return snapshot_dir / filename


def _capture_face_selection(bm):
    return [face.index for face in bm.faces if face.select]


def _restore_face_selection(bm, selected_indices):
    selected_set = set(selected_indices)
    for face in bm.faces:
        face.select = face.index in selected_set


def _format_solver_preflight_breakdown(preflight):
    issue_counts = {}
    for issue in preflight.issues:
        issue_counts[issue.code] = issue_counts.get(issue.code, 0) + 1
    if not issue_counts:
        return ""
    return ", ".join(f"{code}:{issue_counts[code]}" for code in sorted(issue_counts.keys()))


def _filter_preflight_issues(preflight, code):
    return MeshPreflightReport(
        checked_face_indices=tuple(preflight.checked_face_indices),
        issues=[issue for issue in preflight.issues if issue.code == code],
    )


def _mark_sharp_edges_as_seams(bm):
    changed = 0
    for edge in bm.edges:
        if edge.seam or edge.smooth:
            continue
        edge.seam = True
        changed += 1
    return changed


def _highlight_solver_preflight_issues(context, obj, bm, preflight):
    """Leave the blocking topology selected for quick manual inspection."""

    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    edge_indices = sorted(
        {
            edge_index
            for issue in preflight.issues
            for edge_index in issue.edge_indices
            if 0 <= edge_index < len(bm.edges)
        }
    )
    face_indices = sorted(
        {
            face_index
            for issue in preflight.issues
            for face_index in issue.face_indices
            if 0 <= face_index < len(bm.faces)
        }
    )
    vert_indices = sorted(
        {
            vert_index
            for issue in preflight.issues
            for vert_index in issue.vert_indices
            if 0 <= vert_index < len(bm.verts)
        }
    )

    for face in bm.faces:
        face.select = False
    for edge in bm.edges:
        edge.select = False
    for vert in bm.verts:
        vert.select = False
    issue_breakdown = _format_solver_preflight_breakdown(preflight)
    breakdown_suffix = f" ({issue_breakdown})" if issue_breakdown else ""

    if edge_indices:
        context.tool_settings.mesh_select_mode = (False, True, False)
        for edge_index in edge_indices:
            bm.edges[edge_index].select = True
        selection_message = f"Solver preflight failed - selected {len(edge_indices)} offending edges in Edit Mode"
    elif face_indices:
        context.tool_settings.mesh_select_mode = (False, False, True)
        for face_index in face_indices:
            bm.faces[face_index].select = True
        selection_message = f"Solver preflight failed - selected {len(face_indices)} offending faces in Edit Mode"
    elif vert_indices:
        context.tool_settings.mesh_select_mode = (True, False, False)
        for vert_index in vert_indices:
            bm.verts[vert_index].select = True
        selection_message = f"Solver preflight failed - selected {len(vert_indices)} offending verts in Edit Mode"
    else:
        selection_message = "Solver preflight failed - offending topology could not be selected"

    if breakdown_suffix:
        selection_message = f"{selection_message}{breakdown_suffix}"

    bm.select_flush_mode()
    bmesh.update_edit_mesh(obj.data)
    return selection_message


def _report_solver_preflight_selection(operator, exc):
    message = getattr(exc, "selection_message", str(exc))
    operator.report({"WARNING"}, message)


def _prepare_patch_graph(
    context,
    require_selection=True,
    validate_for_solver=False,
    make_seams_by_sharp=False,
):
    """Prepare PatchGraph from the current context."""

    obj = context.active_object
    if obj is None or obj.type != "MESH":
        raise ValueError("Select a mesh object")

    original_mode = obj.mode
    if obj.mode != "EDIT":
        bpy.ops.object.mode_set(mode="EDIT")

    bm = bmesh.from_edit_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    if make_seams_by_sharp:
        seam_count = _mark_sharp_edges_as_seams(bm)
        if seam_count > 0:
            bmesh.update_edit_mesh(obj.data)
            _print_console_report(
                "CFTUV Phase1",
                [],
                f"Make Seams by Sharp: marked {seam_count} sharp edges",
                show_lines=False,
            )

    selected_face_indices = _capture_face_selection(bm)

    try:
        if original_mode == "OBJECT":
            face_indices = [face.index for face in bm.faces]
        else:
            face_indices = list(selected_face_indices)
            if require_selection and not face_indices:
                raise ValueError("No faces selected in Edit Mode")
            if not face_indices:
                face_indices = [face.index for face in bm.faces]

        if validate_for_solver:
            preflight = validate_solver_input_mesh(bm, face_indices)
            if not preflight.is_valid:
                report = format_solver_input_preflight_report(preflight, mesh_name=obj.name)
                _print_console_report("CFTUV Solver Preflight", report.lines, report.summary)
                selection_message = _highlight_solver_preflight_issues(context, obj, bm, preflight)
                raise _SolverPreflightSelectionError(report.summary, selection_message)

        patch_graph = build_patch_graph(bm, face_indices, obj)
        return obj, bm, patch_graph, original_mode, selected_face_indices
    except _SolverPreflightSelectionError:
        raise
    except Exception:
        _restore_mode_and_selection(obj, original_mode, selected_face_indices)
        raise


def _restore_mode_and_selection(obj, original_mode, selected_face_indices):
    if obj is None or obj.name not in bpy.data.objects:
        return

    if obj.mode == "EDIT":
        bm = bmesh.from_edit_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        _restore_face_selection(bm, selected_face_indices)
        bmesh.update_edit_mesh(obj.data)

    if original_mode == "OBJECT" and obj.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def _build_solve_state(context, make_seams_by_sharp=False):
    obj, bm, patch_graph, original_mode, selected_faces = _prepare_patch_graph(
        context,
        require_selection=True,
        validate_for_solver=True,
        make_seams_by_sharp=make_seams_by_sharp,
    )
    settings = UVSettings.from_blender_settings(context.scene.hotspotuv_settings)
    solver_graph = build_solver_graph(
        patch_graph,
        straighten_enabled=settings.straighten_strips,
    )
    solve_plan = plan_solve_phase1(patch_graph, solver_graph)
    return obj, bm, patch_graph, solver_graph, solve_plan, settings, original_mode, selected_faces


__all__ = [
    "ADDON_PACKAGE",
    "_SolverPreflightSelectionError",
    "_clear_pins_after_phase1_enabled",
    "_build_scaffold_map_with_straighten",
    "_print_console_report",
    "_regression_snapshot_path",
    "_filter_preflight_issues",
    "_report_solver_preflight_selection",
    "_prepare_patch_graph",
    "_restore_mode_and_selection",
    "_build_solve_state",
]
