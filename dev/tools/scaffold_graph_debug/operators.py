"""Blender operators and panel for the ScaffoldGraph dev overlay."""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, PointerProperty, StringProperty

from .build_stamp import get_build_stamp, resolve_build_stamp, set_build_stamp
from .session import clear_all, close, refresh_visibility, show_or_refresh


class SCAFFOLDGRAPH_Settings(bpy.types.PropertyGroup):
    active: BoolProperty(name="Graph Debug Active", default=False)
    source_object: StringProperty(name="Source Object", default="")
    last_report: StringProperty(name="Last Report", default="")
    build_stamp: StringProperty(name="Build Stamp", default="")
    show_family_colors: BoolProperty(name="Family Colors", default=True)
    show_spines: BoolProperty(name="Spines", default=True)
    show_ribs: BoolProperty(name="Ribs", default=True)
    show_seam_verdicts: BoolProperty(name="Seam Verdicts", default=True)
    show_junctions: BoolProperty(name="Junctions", default=True)
    show_branch_points: BoolProperty(name="Branches", default=True)
    source_hide_viewport: BoolProperty(name="Stored Viewport Hidden", default=False)
    source_hide_set: BoolProperty(name="Stored Object Hidden", default=False)


class SCAFFOLDGRAPH_OT_Show(bpy.types.Operator):
    bl_idname = "scaffold_graph_debug.show"
    bl_label = "Rebuild Overlay"
    bl_description = "Rebuild the ScaffoldGraph v2 Grease Pencil overlay"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == "MESH" and obj.mode in {"OBJECT", "EDIT"}

    def execute(self, context):
        try:
            _report, summary = show_or_refresh(context)
        except Exception as exc:
            self.report({"ERROR"}, f"ScaffoldGraph debug failed: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, summary)
        print(summary)
        return {"FINISHED"}


class SCAFFOLDGRAPH_OT_Refresh(bpy.types.Operator):
    bl_idname = "scaffold_graph_debug.refresh"
    bl_label = "Rebuild Overlay"
    bl_description = "Rebuild the ScaffoldGraph v2 Grease Pencil overlay"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        settings = getattr(context.scene, "scaffold_graph_debug_settings", None)
        if settings is not None and settings.active and settings.source_object:
            return settings.source_object in bpy.data.objects
        obj = context.active_object
        return obj is not None and obj.type == "MESH" and obj.mode in {"OBJECT", "EDIT"}

    def execute(self, context):
        try:
            _report, summary = show_or_refresh(context)
        except Exception as exc:
            self.report({"ERROR"}, f"ScaffoldGraph refresh failed: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, summary)
        print(summary)
        return {"FINISHED"}


class SCAFFOLDGRAPH_OT_Close(bpy.types.Operator):
    bl_idname = "scaffold_graph_debug.close"
    bl_label = "Close Graph"
    bl_description = "Remove the ScaffoldGraph Grease Pencil overlay"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            summary = close(context)
        except Exception as exc:
            self.report({"ERROR"}, f"ScaffoldGraph close failed: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, summary)
        return {"FINISHED"}


class SCAFFOLDGRAPH_OT_UpdateVisibility(bpy.types.Operator):
    bl_idname = "scaffold_graph_debug.update_visibility"
    bl_label = "Update Visibility"
    bl_description = "Apply ScaffoldGraph overlay layer visibility"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            refresh_visibility(context)
            summary = "visibility updated"
        except Exception as exc:
            self.report({"ERROR"}, f"ScaffoldGraph visibility update failed: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, summary)
        return {"FINISHED"}


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
        stamp = settings.build_stamp or get_build_stamp()
        col.label(text=f"Build: {stamp}")
        col.operator("scaffold_graph_debug.refresh", text="Rebuild Overlay", icon="FILE_REFRESH")
        if settings.active:
            col.operator("scaffold_graph_debug.close", text="Close Graph", icon="X")

        col.separator()
        row = col.row(align=True)
        row.prop(settings, "show_family_colors", toggle=True)
        row.prop(settings, "show_spines", toggle=True)
        row.prop(settings, "show_ribs", toggle=True)
        row = col.row(align=True)
        row.prop(settings, "show_seam_verdicts", toggle=True)
        row.prop(settings, "show_junctions", toggle=True)
        row.prop(settings, "show_branch_points", toggle=True)

        if settings.source_object:
            col.label(text=f"Source: {settings.source_object}")
        if settings.last_report:
            col.label(text=settings.last_report)


classes = (
    SCAFFOLDGRAPH_Settings,
    SCAFFOLDGRAPH_OT_Show,
    SCAFFOLDGRAPH_OT_Refresh,
    SCAFFOLDGRAPH_OT_Close,
    SCAFFOLDGRAPH_OT_UpdateVisibility,
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
