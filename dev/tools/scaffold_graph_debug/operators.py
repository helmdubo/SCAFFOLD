"""Blender operators and panel for the ScaffoldGraph dev overlay."""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, PointerProperty, StringProperty

from .session import clear_all, close, refresh_visibility, show_or_refresh


class SCAFFOLDGRAPH_Settings(bpy.types.PropertyGroup):
    active: BoolProperty(name="Graph Debug Active", default=False)
    source_object: StringProperty(name="Source Object", default="")
    last_report: StringProperty(name="Last Report", default="")
    show_edges: BoolProperty(name="Edges", default=True)
    show_nodes: BoolProperty(name="Nodes", default=True)
    show_junctions: BoolProperty(name="Junctions", default=True)
    show_incident_relations: BoolProperty(name="Incident", default=True)
    show_shared_chain_relations: BoolProperty(name="Shared", default=True)
    show_labels: BoolProperty(name="Labels", default=True)
    source_hide_viewport: BoolProperty(name="Stored Viewport Hidden", default=False)
    source_hide_set: BoolProperty(name="Stored Object Hidden", default=False)


class SCAFFOLDGRAPH_OT_Show(bpy.types.Operator):
    bl_idname = "scaffold_graph_debug.show"
    bl_label = "Show Graph"
    bl_description = "Build or refresh the ScaffoldGraph Grease Pencil overlay"
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
        return {"FINISHED"}


class SCAFFOLDGRAPH_OT_Refresh(bpy.types.Operator):
    bl_idname = "scaffold_graph_debug.refresh"
    bl_label = "Refresh Graph"
    bl_description = "Refresh the ScaffoldGraph Grease Pencil overlay"
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
        refresh_visibility(context)
        self.report({"INFO"}, "ScaffoldGraph visibility updated")
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
        if settings.active:
            col.operator("scaffold_graph_debug.refresh", text="Refresh Graph", icon="FILE_REFRESH")
            col.operator("scaffold_graph_debug.close", text="Close Graph", icon="X")
        else:
            col.operator("scaffold_graph_debug.show", text="Show Graph", icon="OUTLINER_OB_GREASEPENCIL")

        col.separator()
        row = col.row(align=True)
        row.prop(settings, "show_edges", toggle=True)
        row.prop(settings, "show_nodes", toggle=True)
        row.prop(settings, "show_junctions", toggle=True)
        row = col.row(align=True)
        row.prop(settings, "show_incident_relations", toggle=True)
        row.prop(settings, "show_shared_chain_relations", toggle=True)
        row.prop(settings, "show_labels", toggle=True)
        col.operator("scaffold_graph_debug.update_visibility", text="Apply Visibility", icon="HIDE_OFF")

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
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.scaffold_graph_debug_settings = PointerProperty(
        type=SCAFFOLDGRAPH_Settings
    )


def unregister():
    clear_all()
    if hasattr(bpy.types.Scene, "scaffold_graph_debug_settings"):
        del bpy.types.Scene.scaffold_graph_debug_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
