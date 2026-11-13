"""Blender operators and panel for the Scaffold structure debugger."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, PointerProperty, StringProperty
from bpy_extras.io_utils import ExportHelper

from .build_stamp import get_build_stamp, resolve_build_stamp, set_build_stamp
from .overlay_v2 import GROUPS, LAYER_SPECS, LEGENDS
from .session import (
    active_mesh_object,
    clear_all,
    close,
    refresh_line_thickness,
    refresh_visibility,
    show_or_refresh,
)

GROUP_EXPAND_PROPS = {
    "Structure": "expand_structure",
    "Skeleton": "expand_skeleton",
    "Patches: sides and types": "expand_patches",
    "Layer 3 (detail)": "expand_layer3",
    "Ladders": "expand_ladders",
    "Bevels": "expand_bevels",
}
GROUP_EXPAND_DEFAULTS = {
    "expand_structure": True,
    "expand_skeleton": True,
    "expand_patches": True,
    "expand_layer3": False,
    "expand_ladders": False,
    "expand_bevels": False,
}


def _add_dev_tools_to_path() -> None:
    tools_root = Path(__file__).resolve().parents[1]
    tools_root_text = str(tools_root)
    if tools_root_text not in sys.path:
        sys.path.insert(0, tools_root_text)


def _safe_filename(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in name)


def _on_visibility_changed(_settings, context) -> None:
    try:
        refresh_visibility(context)
    except Exception as exc:  # noqa: BLE001 - a toggle must never raise into the UI
        print(f"[scaffold debug] visibility update failed: {exc}")


def _on_line_thickness_changed(_settings, context) -> None:
    try:
        refresh_line_thickness(context)
    except Exception as exc:  # noqa: BLE001 - a slider must never raise into the UI
        print(f"[scaffold debug] line thickness update failed: {exc}")


class SCAFFOLDGRAPH_Settings(bpy.types.PropertyGroup):
    active: BoolProperty(name="Analyze Active", default=False)
    source_object: StringProperty(name="Source Object", default="")
    source_ref: PointerProperty(name="Source Object Ref", type=bpy.types.Object)  # survives a rename
    last_report: StringProperty(name="Last Report", default="")
    build_stamp: StringProperty(name="Build Stamp", default="")
    straighten_strips: BoolProperty(
        name="Straighten Strips",
        description="Pass 2 option: lay accepted strip patches as rectangles (applies on Rebuild and Write UV)",
        default=False,
    )
    straighten_bevel_strips: BoolProperty(
        name="Straighten Bevel Strips",
        description=(
            "Pass 2 option: lay every bevel strip marked by Face Strength from its ladder as a straight "
            "island of its own (applies on Rebuild and Write UV)"
        ),
        default=True,
    )
    split_vertical_from_horizontal: BoolProperty(
        name="Split vertical from horizontal",
        description=(
            "User filter (Pass 3): patches facing the up axis within the angle are horizontal, the rest "
            "vertical; seams between the two are split, bevels lie with their surfaces (applies on Rebuild "
            "and Write UV)"
        ),
        default=True,
    )
    world_up_axis: EnumProperty(
        name="Up axis",
        description="The world vertical of the user filter",
        items=[(axis, axis, f"{axis} is up") for axis in ("+Z", "-Z", "+Y", "-Y", "+X", "-X")],
        default="+Z",
    )
    horizontal_angle: FloatProperty(
        name="Angle",
        description="A patch is horizontal when its normal lies within this many degrees of the up axis",
        default=45.0,
        min=0.0,
        max=90.0,
    )
    show_labels: BoolProperty(name="Labels", default=False, update=_on_visibility_changed)
    line_thickness: FloatProperty(
        name="Line thickness",
        description="Multiplier for every stroke of the overlay (1.0 = as built); fills are unaffected; acts at once",
        default=1.0,
        min=0.1,
        max=20.0,
        soft_max=8.0,
        step=10,
        update=_on_line_thickness_changed,
    )
    source_hide_viewport: BoolProperty(name="Stored Viewport Hidden", default=False)
    source_hide_set: BoolProperty(name="Stored Object Hidden", default=False)


for _spec in LAYER_SPECS:
    SCAFFOLDGRAPH_Settings.__annotations__[_spec.prop] = BoolProperty(
        name=_spec.label,
        default=_spec.default,
        update=_on_visibility_changed,
    )
for _prop, _default in GROUP_EXPAND_DEFAULTS.items():
    SCAFFOLDGRAPH_Settings.__annotations__[_prop] = BoolProperty(name="Expand", default=_default)


def _mesh_or_session_poll(context) -> bool:
    """A live session's stored mesh, else the active mesh (a deleted or renamed source falls through)."""

    settings = getattr(context.scene, "scaffold_graph_debug_settings", None)
    if settings is not None and settings.active and settings.source_object in bpy.data.objects:
        return True
    obj = context.active_object
    return obj is not None and obj.type == "MESH" and obj.mode in {"OBJECT", "EDIT"}


class SCAFFOLDGRAPH_OT_Analyze(bpy.types.Operator):
    bl_idname = "scaffold_graph_debug.analyze"
    bl_label = "Analyze"
    bl_description = "Build the debug overlay and hide the mesh, or remove it and restore the mesh"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        settings = getattr(context.scene, "scaffold_graph_debug_settings", None)
        if settings is not None and settings.active:
            return True  # always able to end a session, even one whose mesh is gone
        return _mesh_or_session_poll(context)

    def execute(self, context):
        settings = context.scene.scaffold_graph_debug_settings
        try:
            if settings.active:
                summary = close(context)
            else:
                _payload, summary = show_or_refresh(context)
        except Exception as exc:  # noqa: BLE001 - surface errors to the artist
            self.report({"ERROR"}, f"Scaffold debug failed: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, summary)
        return {"FINISHED"}


class SCAFFOLDGRAPH_OT_Refresh(bpy.types.Operator):
    bl_idname = "scaffold_graph_debug.refresh"
    bl_label = "Rebuild"
    bl_description = "Rerun the pipeline and redraw every debug layer"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _mesh_or_session_poll(context)

    def execute(self, context):
        try:
            _payload, summary = show_or_refresh(context)
        except Exception as exc:  # noqa: BLE001 - surface errors to the artist
            self.report({"ERROR"}, f"Scaffold debug rebuild failed: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, summary)
        return {"FINISHED"}


class SCAFFOLDGRAPH_OT_ExportJson(bpy.types.Operator, ExportHelper):
    bl_idname = "scaffold_graph_debug.export_json"
    bl_label = "SCAFFOLD JSON"
    bl_description = "Export the active Scaffold Pass 0/1 graph payload for the external viewer"
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    @classmethod
    def poll(cls, context):
        return _mesh_or_session_poll(context)

    def invoke(self, context, event):
        settings = getattr(context.scene, "scaffold_graph_debug_settings", None)
        source_object = active_mesh_object(
            context,
            fallback_source_name=settings.source_object if settings and settings.active else "",
        )
        default_dir = Path(__file__).resolve().parents[1] / "scaffold_graph_viewer" / "reports"
        self.filepath = str(default_dir / f"{_safe_filename(source_object.name)}.graph.json")
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        settings = getattr(context.scene, "scaffold_graph_debug_settings", None)
        source_object = active_mesh_object(
            context,
            fallback_source_name=settings.source_object if settings and settings.active else "",
        )
        previous_active = context.view_layer.objects.active
        previous_hide_viewport = bool(getattr(source_object, "hide_viewport", False))
        hide_get = getattr(source_object, "hide_get", None)
        previous_hide_set = bool(hide_get()) if callable(hide_get) else False
        try:
            _add_dev_tools_to_path()
            from scaffold_graph_viewer.export_selected_graph import write_payload

            source_object.hide_viewport = False
            source_object.hide_set(False)
            context.view_layer.objects.active = source_object
            source_object.select_set(True)
            out = write_payload(context, self.filepath)
        except Exception as exc:  # noqa: BLE001 - report Blender operator failures
            self.report({"ERROR"}, f"SCAFFOLD JSON export failed: {exc}")
            return {"CANCELLED"}
        finally:
            source_object.hide_viewport = previous_hide_viewport
            source_object.hide_set(previous_hide_set)
            if previous_active is not None and previous_active.name in bpy.data.objects:
                context.view_layer.objects.active = previous_active

        summary = f"SCAFFOLD JSON wrote {out}"
        print(f"[scaffold graph viewer] {summary}")
        self.report({"INFO"}, summary)
        return {"FINISHED"}


class SCAFFOLDGRAPH_OT_WriteUV(bpy.types.Operator):
    bl_idname = "scaffold_graph_debug.write_uv_g5a"
    bl_label = "Write UV (G5a)"
    bl_description = "Run the G5a skeleton solve and write pinned UVs (U > Unwrap fills the rest)"

    unwrap_quilts = False

    def execute(self, context):
        try:
            from .session import _add_repo_root_to_path, filter_from_settings

            _add_repo_root_to_path()
            from scaffold_core.layer_0_source.blender_io import read_source_mesh_from_blender
            from scaffold_core.layer_4_features.model import FeatureOptions
            from scaffold_core.layer_5_runtime.pins import run_skeleton_solve
            from scaffold_core.layer_5_runtime.uv_transfer import write_pinned_uvs, write_quilt_uvs
            from scaffold_core.pipeline.passes import (
                run_pass_0,
                run_pass_1_relations,
                run_pass_2_features,
                run_pass_3_filters,
            )
            from scaffold_core.user_filters.model import FilterOptions

            source = read_source_mesh_from_blender(context)
            if not source.selected_face_ids:
                self.report({"ERROR"}, "Select faces before writing UVs")
                return {"CANCELLED"}
            settings = context.scene.scaffold_graph_debug_settings
            options = FeatureOptions(
                straighten_strips=bool(settings.straighten_strips),
                straighten_bevel_strips=bool(settings.straighten_bevel_strips),
            )
            world_up, angle = filter_from_settings(settings)
            pipeline = run_pass_3_filters(
                run_pass_2_features(run_pass_1_relations(run_pass_0(source)), options),
                FilterOptions(world_up=world_up, horizontal_angle_degrees=angle),
            )
            result = run_skeleton_solve(pipeline)
            writer = write_quilt_uvs if self.unwrap_quilts else write_pinned_uvs
            report = writer(context, result)
            directives = Counter(d.kind.value for d in pipeline.filter_snapshot.directives)
            summary = (
                f"quilts:{len(result.assembly.islands)} "
                f"filter:{'off' if world_up is None else settings.world_up_axis} "
                f"split:{directives.get('SPLIT', 0)} join:{directives.get('JOIN', 0)} "
                f"pinned:{report['pinned_vertices']} loops:{report['written_loops']} "
                f"residual:{result.residual_max:.1e} "
                f"axis_violations:{len(result.axis_parallel_violations)} "
                f"diags:{len(result.diagnostics)}"
            )
            print(f"[scaffold G5a] {summary}")
            print(f"[scaffold G5a] {report['next_step']}")
            for line in result.diagnostics:
                print(f"[scaffold G5a] diag: {line}")
            self.report({"INFO"}, summary + (" | quilts unwrapped" if self.unwrap_quilts else " | U > Unwrap to fill"))
        except Exception as exc:  # noqa: BLE001 - surface errors to the artist
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class SCAFFOLDGRAPH_OT_WriteUVQuilts(SCAFFOLDGRAPH_OT_WriteUV):
    bl_idname = "scaffold_graph_debug.write_uv_quilts"
    bl_label = "Write UV and unwrap quilts"
    bl_description = (
        "Run the solve, write pinned UVs and lay each quilt as one chart by Blender's conformal unwrap; "
        "the mesh's seams are restored afterwards"
    )
    bl_options = {"REGISTER", "UNDO"}

    unwrap_quilts = True


class SCAFFOLDGRAPH_PT_Panel(bpy.types.Panel):
    bl_label = "Scaffold Graph"
    bl_idname = "SCAFFOLDGRAPH_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Scaffold"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.scaffold_graph_debug_settings

        col = layout.column(align=True)
        col.label(text=f"Build: {settings.build_stamp or get_build_stamp()}")
        row = col.row(align=True)
        row.scale_y = 1.4
        row.operator(
            "scaffold_graph_debug.analyze",
            text="Analyze",
            icon="VIEWZOOM",
            depress=bool(settings.active),
        )
        col.operator("scaffold_graph_debug.refresh", text="Rebuild", icon="FILE_REFRESH")
        col.prop(settings, "straighten_strips", toggle=True)
        col.prop(settings, "straighten_bevel_strips", toggle=True)
        col.prop(settings, "split_vertical_from_horizontal", toggle=True)
        row = col.row(align=True)
        row.enabled = bool(settings.split_vertical_from_horizontal)
        row.prop(settings, "world_up_axis", text="Up")
        row.prop(settings, "horizontal_angle")
        col.label(text="Straighten and filter options apply on Rebuild")
        col.prop(settings, "line_thickness", slider=True)
        if settings.source_object:
            col.label(text=f"Source: {settings.source_object}")
        if settings.last_report:
            col.label(text=settings.last_report)

        for group in GROUPS:
            self._draw_group(layout, settings, group)

        row = layout.row(align=True)
        row.operator("scaffold_graph_debug.write_uv_g5a", icon="UV")
        layout.operator("scaffold_graph_debug.write_uv_quilts", icon="UV_DATA")
        layout.operator("scaffold_graph_debug.export_json", text="SCAFFOLD JSON", icon="EXPORT")

    def _draw_group(self, layout, settings, group: str) -> None:
        expand_prop = GROUP_EXPAND_PROPS[group]
        expanded = bool(getattr(settings, expand_prop))
        box = layout.box()
        header = box.row()
        header.prop(
            settings,
            expand_prop,
            text=group,
            icon="TRIA_DOWN" if expanded else "TRIA_RIGHT",
            emboss=False,
        )
        if not expanded:
            return
        column = box.column(align=True)
        for spec in LAYER_SPECS:
            if spec.group != group:
                continue
            visible = bool(getattr(settings, spec.prop))
            column.prop(settings, spec.prop, text=spec.label, icon="HIDE_OFF" if visible else "HIDE_ON")
        if group == "Structure":
            visible = bool(settings.show_labels)
            column.prop(settings, "show_labels", text="Labels", icon="HIDE_OFF" if visible else "HIDE_ON")
        legend = box.column(align=True)
        legend.scale_y = 0.7
        for line in LEGENDS.get(group, ()):
            legend.label(text=line)


classes = (
    SCAFFOLDGRAPH_OT_ExportJson,
    SCAFFOLDGRAPH_OT_WriteUV,
    SCAFFOLDGRAPH_OT_WriteUVQuilts,
    SCAFFOLDGRAPH_Settings,
    SCAFFOLDGRAPH_OT_Analyze,
    SCAFFOLDGRAPH_OT_Refresh,
    SCAFFOLDGRAPH_PT_Panel,
)


def register():
    set_build_stamp(resolve_build_stamp())
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.scaffold_graph_debug_settings = PointerProperty(
        type=SCAFFOLDGRAPH_Settings
    )
    for scene in bpy.data.scenes:
        scene.scaffold_graph_debug_settings.build_stamp = get_build_stamp()


def unregister():
    clear_all()
    if hasattr(bpy.types.Scene, "scaffold_graph_debug_settings"):
        del bpy.types.Scene.scaffold_graph_debug_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
