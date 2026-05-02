"""CFTUV Operators — Blender UI, operators, settings.

Thin wrappers only. No geometry logic here (max 5 lines math).
All heavy work delegated to analysis.py, solve.py, debug.py.
"""

import bpy
import bmesh
from bpy.props import (
    BoolProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)

from .analysis import (
    format_patch_graph_snapshot_report,
    validate_solver_input_mesh,
)
from .constants import GP_DEBUG_PREFIX
from .debug import (
    get_gp_layer,
    gp_layer_name,
    is_gp_debug_object,
)
from .operators_pipeline import (
    ADDON_PACKAGE,
    _SolverPreflightSelectionError,
    _build_scaffold_map_with_straighten,
    _build_solve_state,
    _clear_pins_after_phase1_enabled,
    _filter_preflight_issues,
    _format_solver_preflight_breakdown,
    _highlight_solver_preflight_issues,
    _print_console_report,
    _regression_snapshot_path,
    _report_solver_preflight_selection,
    _restore_mode_and_selection,
)
from .operators_session import (
    _enter_debug_mode,
    _exit_debug_mode,
    _force_clear_debug_state,
    _frontier_replay_frame_handler,
    _refresh_debug_layers,
    _stop_animation_playback,
)
from .solve import (
    execute_phase1_preview,
    format_regression_snapshot_report,
    format_root_scaffold_report,
    format_solve_plan_report,
)


class HOTSPOTUV_OT_CleanNonManifoldEdges(bpy.types.Operator):
    bl_idname = "hotspotuv.clean_non_manifold_edges"
    bl_label = "Clean Non-Manifold Edges"
    bl_description = "Find NON_MANIFOLD_EDGE issues and split faces and edges by vertices"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH' and obj.mode in {'EDIT', 'OBJECT'}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            self.report({"ERROR"}, "Select a mesh object")
            return {"CANCELLED"}

        original_mode = obj.mode
        try:
            if obj.mode != 'EDIT':
                bpy.ops.object.mode_set(mode='EDIT')

            bm = bmesh.from_edit_mesh(obj.data)
            bm.faces.ensure_lookup_table()
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()

            preflight = validate_solver_input_mesh(bm, [face.index for face in bm.faces])
            non_manifold_report = _filter_preflight_issues(preflight, "NON_MANIFOLD_EDGE")
            if non_manifold_report.is_valid:
                if original_mode == 'OBJECT':
                    bpy.ops.object.mode_set(mode='OBJECT')
                self.report({"INFO"}, "No NON_MANIFOLD_EDGE issues found")
                return {"FINISHED"}

            edge_indices = sorted(
                {
                    edge_index
                    for issue in non_manifold_report.issues
                    for edge_index in issue.edge_indices
                    if 0 <= edge_index < len(bm.edges)
                }
            )
            selection_message = _highlight_solver_preflight_issues(
                context,
                obj,
                bm,
                non_manifold_report,
            )
            bpy.ops.mesh.edge_split(type='VERT')

            bm = bmesh.from_edit_mesh(obj.data)
            bm.faces.ensure_lookup_table()
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bmesh.update_edit_mesh(obj.data)

            remaining_preflight = validate_solver_input_mesh(bm, [face.index for face in bm.faces])
            remaining_non_manifold = _filter_preflight_issues(remaining_preflight, "NON_MANIFOLD_EDGE")
            remaining_count = len(remaining_non_manifold.issues)
            remaining_breakdown = _format_solver_preflight_breakdown(remaining_non_manifold)
            breakdown_suffix = f" Remaining: {remaining_breakdown}" if remaining_breakdown else ""
            message = (
                f"Edge Split by vertices applied to {len(edge_indices)} non-manifold edges. "
                f"Remaining non-manifold issues: {remaining_count}.{breakdown_suffix}"
            )
            _print_console_report(
                "CFTUV Cleanup",
                [selection_message, message],
                show_lines=True,
            )
            self.report({"WARNING"} if remaining_count > 0 else {"INFO"}, message)
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, f"Clean Non-Manifold Edges failed: {exc}")
            return {"CANCELLED"}


# ============================================================
# UI SETTINGS
# ============================================================


class HOTSPOTUV_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = ADDON_PACKAGE

    clear_pins_after_phase1: BoolProperty(
        name="Clear Pins After Solve Phase 1",
        default=True,
        description="Remove UV pins after Solve Phase 1 Preview. Disable to keep pins visible for debug inspection",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "clear_pins_after_phase1")


class HOTSPOTUV_Settings(bpy.types.PropertyGroup):
    target_texel_density: IntProperty(
        name="Target Texel Density (px/m)", default=512, min=1
    )
    texture_size: IntProperty(name="Texture Size", default=2048, min=1)
    uv_scale: FloatProperty(name="Custom Scale Multiplier", default=1.0, min=0.0001)
    uv_range_limit: IntProperty(name="UV Range Limit (Tiles)", default=16, min=0)

    # Debug state
    dbg_active: BoolProperty(
        name="Analyze", default=False, description="Debug analysis mode"
    )
    dbg_source_object: StringProperty(name="Debug Source", default="")
    dbg_replay_active: BoolProperty(name="Replay Active", default=False)
    dbg_replay_source_object: StringProperty(name="Replay Source", default="")
    dbg_replay_cleanup_pending: BoolProperty(name="Replay Cleanup Pending", default=False)
    dbg_verbose_console: BoolProperty(
        name="Verbose Console",
        default=False,
        description="Print full reports and trace diagnostics to System Console",
    )
    dbg_show_advanced_debug: BoolProperty(
        name="Advanced Debug",
        default=False,
        description="Show rarely used developer debug tools",
    )
    phase1_make_seams_by_sharp: BoolProperty(
        name="Make Seams by Sharp",
        default=False,
        description="Before Phase 1 preview, mark sharp edges as seam",
    )
    straighten_strips: BoolProperty(
        name="Straighten Strips",
        default=False,
        description="Place structurally strong FREE chains as straight frame lines (inherited from neighbor)",
    )

    # Group toggles
    dbg_grp_patches: BoolProperty(name="Patches", default=True)
    dbg_grp_loops: BoolProperty(name="Loop Types", default=True)
    dbg_grp_overlay: BoolProperty(name="Overlay", default=True)

    # Patches group
    dbg_patches_wall: BoolProperty(name="Wall", default=True)
    dbg_patches_floor: BoolProperty(name="Floor", default=True)
    dbg_patches_slope: BoolProperty(name="Slope", default=True)

    # Loop Types group
    dbg_loops_chains: BoolProperty(name="Chains", default=True)
    dbg_loops_holes: BoolProperty(name="Holes", default=True)

    # Overlay group
    dbg_overlay_labels: BoolProperty(name="Chain Labels", default=True)


class HOTSPOTUV_OT_DebugAnalysis(bpy.types.Operator):
    bl_idname = "hotspotuv.debug_analysis"
    bl_label = "Debug: Toggle Analysis"
    bl_description = "Toggle debug analysis mode ON/OFF"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        s = context.scene.hotspotuv_settings
        if s.dbg_active:
            return True
        obj = context.active_object
        return obj is not None and obj.type == 'MESH' and obj.mode in {'EDIT', 'OBJECT'}

    def execute(self, context):
        s = context.scene.hotspotuv_settings

        if s.dbg_active:
            _exit_debug_mode(context)
            self.report({"INFO"}, "Debug analysis OFF")
        else:
            obj = context.active_object
            if not obj or obj.type != 'MESH':
                self.report({"WARNING"}, "Select a mesh object")
                return {"CANCELLED"}
            try:
                report = _enter_debug_mode(context, obj)
            except Exception as exc:
                self.report({"ERROR"}, f"Debug analysis failed: {exc}")
                return {"CANCELLED"}
            if report is None:
                self.report({"WARNING"}, "No faces selected in Edit Mode")
                return {"CANCELLED"}
            self.report({"INFO"}, report)

        return {"FINISHED"}


class HOTSPOTUV_OT_DebugClear(bpy.types.Operator):
    bl_idname = "hotspotuv.debug_clear"
    bl_label = "Debug: Force Clear"
    bl_description = "Force remove all debug visualization"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        _stop_animation_playback()
        _force_clear_debug_state(context, reset_timeline=True)
        self.report({"INFO"}, "Debug cleared")
        return {"FINISHED"}


class HOTSPOTUV_OT_DebugToggleLayer(bpy.types.Operator):
    """Toggle visibility of a GP debug layer."""
    bl_idname = "hotspotuv.debug_toggle_layer"
    bl_label = "Toggle Layer"
    bl_options = {"REGISTER", "UNDO"}

    layer_name: StringProperty()

    def execute(self, context):
        s = context.scene.hotspotuv_settings
        source_name = s.dbg_source_object
        if not source_name:
            return {"CANCELLED"}

        gp_name = GP_DEBUG_PREFIX + source_name
        gp_obj = bpy.data.objects.get(gp_name)
        if not is_gp_debug_object(gp_obj):
            return {"CANCELLED"}

        gp_data = gp_obj.data

        # Chain Labels — управляем коллекцией, а не GP layer
        if self.layer_name == 'Overlay_Labels':
            from .debug import _LABEL_COLLECTION_NAME
            if _LABEL_COLLECTION_NAME in bpy.data.collections:
                col = bpy.data.collections[_LABEL_COLLECTION_NAME]
                col.hide_viewport = not col.hide_viewport
                s.dbg_overlay_labels = not col.hide_viewport
            return {"FINISHED"}

        layer = get_gp_layer(gp_data, self.layer_name)
        if layer is not None:
            layer.hide = not layer.hide
            visible = not layer.hide
            layer_setting_map = {
                'Patches_WALL': 'dbg_patches_wall',
                'Patches_FLOOR': 'dbg_patches_floor',
                'Patches_SLOPE': 'dbg_patches_slope',
                'Loops_Chains': 'dbg_loops_chains',
                'Loops_Holes': 'dbg_loops_holes',
            }
            prop_name = layer_setting_map.get(self.layer_name)
            if prop_name and hasattr(s, prop_name):
                setattr(s, prop_name, visible)

        return {"FINISHED"}


class HOTSPOTUV_OT_DebugToggleGroup(bpy.types.Operator):
    """Toggle visibility of a debug layer group."""
    bl_idname = "hotspotuv.debug_toggle_group"
    bl_label = "Toggle Group"
    bl_options = {"REGISTER", "UNDO"}

    group_name: StringProperty()

    _GROUP_LAYERS = {
        'patches': ['Patches_WALL', 'Patches_FLOOR', 'Patches_SLOPE'],
        'loops': ['Loops_Chains', 'Loops_Boundary', 'Loops_Holes'],
        'overlay': ['Overlay_Basis', 'Overlay_Centers'],
    }

    def execute(self, context):
        s = context.scene.hotspotuv_settings
        source_name = s.dbg_source_object
        if not source_name:
            return {"CANCELLED"}

        prop_name = f"dbg_grp_{self.group_name}"
        new_val = not getattr(s, prop_name, True)
        setattr(s, prop_name, new_val)

        gp_name = GP_DEBUG_PREFIX + source_name
        gp_obj = bpy.data.objects.get(gp_name)
        if not is_gp_debug_object(gp_obj):
            return {"FINISHED"}

        gp_data = gp_obj.data
        for layer_name in self._GROUP_LAYERS.get(self.group_name, []):
            layer = get_gp_layer(gp_data, layer_name)
            if layer is not None:
                layer.hide = not new_val

        # Overlay group также управляет коллекцией labels
        if self.group_name == 'overlay':
            from .debug import _LABEL_COLLECTION_NAME
            if _LABEL_COLLECTION_NAME in bpy.data.collections:
                bpy.data.collections[_LABEL_COLLECTION_NAME].hide_viewport = not new_val

        return {"FINISHED"}


class HOTSPOTUV_OT_FlowDebug(bpy.types.Operator):
    bl_idname = "hotspotuv.flow_debug"
    bl_label = "Flow Debug"
    bl_description = "Build SolverGraph + SolvePlan, print to System Console"
    bl_options = {"REGISTER", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH' and obj.mode in {'EDIT', 'OBJECT'}

    def execute(self, context):
        try:
            obj, _bm, pg, sg, sp, _s, om, sel = _build_solve_state(context)
            report = format_solve_plan_report(pg, sg, sp, mesh_name=obj.name)
            _print_console_report('CFTUV Flow Debug', report.lines, report.summary)
            self.report({"INFO"}, report.summary)
            return {"FINISHED"}
        except _SolverPreflightSelectionError as exc:
            _report_solver_preflight_selection(self, exc)
            return {"CANCELLED"}
        except Exception as exc:
            self.report({"ERROR"}, f"Flow Debug failed: {exc}")
            return {"CANCELLED"}
        finally:
            if 'obj' in locals() and 'om' in locals() and 'sel' in locals():
                _restore_mode_and_selection(obj, om, sel)


class HOTSPOTUV_OT_ScaffoldDebug(bpy.types.Operator):
    bl_idname = "hotspotuv.scaffold_debug"
    bl_label = "Scaffold Debug"
    bl_description = "Build ScaffoldMap, print to System Console"
    bl_options = {"REGISTER", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH' and obj.mode in {'EDIT', 'OBJECT'}

    def execute(self, context):
        try:
            obj, _bm, pg, _sg, sp, settings, om, sel = _build_solve_state(context)
            scaffold_map = _build_scaffold_map_with_straighten(pg, sp, settings)
            report = format_root_scaffold_report(pg, scaffold_map, mesh_name=obj.name)
            _print_console_report('CFTUV Scaffold Debug', report.lines, report.summary)

            # Frontier path visualization поверх существующего GP
            s = context.scene.hotspotuv_settings
            source_name = s.dbg_source_object
            if source_name and source_name in bpy.data.objects:
                _refresh_debug_layers(context, pg, bpy.data.objects[source_name], scaffold_map)

            self.report({"INFO"}, report.summary)
            return {"FINISHED"}
        except _SolverPreflightSelectionError as exc:
            _report_solver_preflight_selection(self, exc)
            return {"CANCELLED"}
        except Exception as exc:
            self.report({"ERROR"}, f"Scaffold Debug failed: {exc}")
            return {"CANCELLED"}
        finally:
            if 'obj' in locals() and 'om' in locals() and 'sel' in locals():
                _restore_mode_and_selection(obj, om, sel)


class HOTSPOTUV_OT_SaveRegressionSnapshot(bpy.types.Operator):
    bl_idname = "hotspotuv.save_regression_snapshot"
    bl_label = "Save Regression Snapshot"
    bl_description = "Serialize a stable scaffold baseline report to a markdown file"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH' and obj.mode in {'EDIT', 'OBJECT'}

    def execute(self, context):
        try:
            obj, bm, pg, _sg, sp, settings, om, sel = _build_solve_state(context)
            scaffold_map = _build_scaffold_map_with_straighten(pg, sp, settings)
            patch_graph_report = format_patch_graph_snapshot_report(
                pg,
                mesh_name=obj.name,
            )
            report = format_regression_snapshot_report(
                bm,
                pg,
                sp,
                scaffold_map,
                mesh_name=obj.name,
            )
            output_path = _regression_snapshot_path(obj)
            content = "\n".join([
                "# CFTUV Regression Snapshot",
                "",
                "## PatchGraph Snapshot",
                "",
                *patch_graph_report.lines,
                "",
                patch_graph_report.summary,
                "",
                "## Scaffold Snapshot",
                "",
                *report.lines,
                "",
                "---",
                report.summary,
                "",
            ])
            output_path.write_text(content, encoding="utf-8")
            _print_console_report(
                'CFTUV Regression Snapshot',
                report.lines,
                report.summary,
                show_lines=bool(context.scene.hotspotuv_settings.dbg_verbose_console),
            )
            self.report({"INFO"}, f"Snapshot saved: {output_path}")
            return {"FINISHED"}
        except _SolverPreflightSelectionError as exc:
            _report_solver_preflight_selection(self, exc)
            return {"CANCELLED"}
        except Exception as exc:
            self.report({"ERROR"}, f"Save Regression Snapshot failed: {exc}")
            return {"CANCELLED"}
        finally:
            if 'obj' in locals() and 'om' in locals() and 'sel' in locals():
                _restore_mode_and_selection(obj, om, sel)


class HOTSPOTUV_OT_FrontierReplay(bpy.types.Operator):
    bl_idname = "hotspotuv.frontier_replay"
    bl_label = "Frontier Replay"
    bl_description = "Animate scaffold build step-by-step. Hides mesh, shows only frontier path"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        s = context.scene.hotspotuv_settings
        if s.dbg_replay_active:
            return True
        if s.dbg_active and s.dbg_source_object:
            return True
        obj = context.active_object
        return obj is not None and obj.type == 'MESH' and obj.mode in {'EDIT', 'OBJECT'}

    def execute(self, context):
        s = context.scene.hotspotuv_settings

        if s.dbg_replay_active:
            _stop_animation_playback()
            _force_clear_debug_state(context, reset_timeline=True)
            self.report({"INFO"}, "Frontier Replay stopped")
            return {"FINISHED"}

        # В debug mode mesh скрыт, активен GP — нужно переключиться
        source_name = s.dbg_source_object if s.dbg_active else ""
        need_restore_debug = False

        try:
            if source_name and source_name in bpy.data.objects:
                source_obj = bpy.data.objects[source_name]
                # Временно показываем mesh и делаем активным
                source_obj.hide_viewport = False
                source_obj.hide_set(False)
                if context.active_object and context.active_object.mode != 'OBJECT':
                    bpy.ops.object.mode_set(mode='OBJECT')
                bpy.ops.object.select_all(action='DESELECT')
                source_obj.select_set(True)
                context.view_layer.objects.active = source_obj
                need_restore_debug = True

            obj, _bm, pg, _sg, sp, settings, om, sel = _build_solve_state(context)
            scaffold_map = _build_scaffold_map_with_straighten(pg, sp, settings)
            _restore_mode_and_selection(obj, om, sel)

            # Frontier visualization
            target_name = source_name or obj.name
            if target_name in bpy.data.objects:
                target_obj = bpy.data.objects[target_name]
                _refresh_debug_layers(context, pg, target_obj, scaffold_map)

                # Прячем mesh
                target_obj.hide_viewport = True

                # Показываем только Frontier_Path
                gp_name = GP_DEBUG_PREFIX + target_name
                gp_obj = bpy.data.objects.get(gp_name)
                if is_gp_debug_object(gp_obj):
                    for layer in gp_obj.data.layers:
                        layer.hide = (gp_layer_name(layer) != 'Frontier_Path')
                    # Активируем GP
                    if context.active_object and context.active_object.mode != 'OBJECT':
                        bpy.ops.object.mode_set(mode='OBJECT')
                    bpy.ops.object.select_all(action='DESELECT')
                    gp_obj.select_set(True)
                    context.view_layer.objects.active = gp_obj

                # Запускаем playback
                s.dbg_replay_active = True
                s.dbg_replay_source_object = target_name
                s.dbg_replay_cleanup_pending = False
                context.scene.frame_current = 0
                bpy.ops.screen.animation_play()

            self.report({"INFO"}, "Frontier Replay started — click again to stop")
            return {"FINISHED"}
        except _SolverPreflightSelectionError as exc:
            s.dbg_replay_active = False
            s.dbg_replay_source_object = ""
            s.dbg_replay_cleanup_pending = False
            _report_solver_preflight_selection(self, exc)
            return {"CANCELLED"}
        except Exception as exc:
            s.dbg_replay_active = False
            s.dbg_replay_source_object = ""
            s.dbg_replay_cleanup_pending = False
            self.report({"ERROR"}, f"Frontier Replay failed: {exc}")
            return {"CANCELLED"}


class HOTSPOTUV_OT_SolvePhase1Preview(bpy.types.Operator):
    bl_idname = "hotspotuv.solve_phase1_preview"
    bl_label = "Solve Phase 1 Preview"
    bl_description = "Write ScaffoldMap-driven preview UVs"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH' and obj.mode in {'EDIT', 'OBJECT'}

    def _execute_single(self, context):
        """Запускает Phase 1 для active object. Возвращает (stats, obj_name)."""
        scene_settings = context.scene.hotspotuv_settings
        obj, bm, pg, _sg, sp, settings, om, sel = _build_solve_state(
            context,
            make_seams_by_sharp=bool(scene_settings.phase1_make_seams_by_sharp),
        )
        try:
            stats = execute_phase1_preview(
                context,
                obj,
                bm,
                pg,
                settings,
                sp,
                keep_pins=not _clear_pins_after_phase1_enabled(context),
            )
            s = context.scene.hotspotuv_settings
            source_name = s.dbg_source_object
            if source_name and source_name in bpy.data.objects:
                scaffold_map = _build_scaffold_map_with_straighten(pg, sp, settings)
                _refresh_debug_layers(context, pg, bpy.data.objects[source_name], scaffold_map)
            return stats, obj.name
        finally:
            _restore_mode_and_selection(obj, om, sel)

    def execute(self, context):
        active_obj = context.active_object
        if active_obj is None:
            self.report({"ERROR"}, "No active object")
            return {"CANCELLED"}

        if active_obj.mode == "EDIT":
            return self._execute_edit_mode(context)
        return self._execute_object_mode(context)

    def _execute_edit_mode(self, context):
        """EDIT mode: только active object, selected faces."""
        try:
            stats, obj_name = self._execute_single(context)
            summary = self._format_summary(stats, obj_name)
            _print_console_report("CFTUV Phase1", [], summary, show_lines=False)
            self.report({"INFO"}, summary)
            return {"FINISHED"}
        except _SolverPreflightSelectionError as exc:
            _report_solver_preflight_selection(self, exc)
            return {"CANCELLED"}
        except Exception as exc:
            self.report({"ERROR"}, f"Solve Phase 1 Preview failed: {exc}")
            return {"CANCELLED"}

    def _execute_object_mode(self, context):
        """OBJECT mode: все выбранные mesh объекты."""
        mesh_objects = [
            obj for obj in context.selected_objects
            if obj.type == 'MESH'
        ]
        if not mesh_objects:
            self.report({"WARNING"}, "No mesh objects selected")
            return {"CANCELLED"}

        original_active = context.active_object
        original_selection = [obj for obj in context.selected_objects]
        total_stats = {}
        processed = 0
        errors = []

        for obj in mesh_objects:
            # Снимаем selection со всех, чтобы bpy.ops.uv.unwrap()
            # не затронул другие объекты при входе в EDIT mode.
            for other in context.selected_objects:
                other.select_set(False)
            obj.select_set(True)
            context.view_layer.objects.active = obj
            try:
                stats, obj_name = self._execute_single(context)
                processed += 1
                for key, value in stats.items():
                    if isinstance(value, (int, float)):
                        total_stats[key] = total_stats.get(key, 0) + value
                summary = self._format_summary(stats, obj_name)
                _print_console_report("CFTUV Phase1", [], summary, show_lines=False)
            except _SolverPreflightSelectionError as exc:
                errors.append(f"{obj.name}: preflight failed")
            except Exception as exc:
                errors.append(f"{obj.name}: {exc}")

        # Восстанавливаем исходный selection и active object.
        for other in context.selected_objects:
            other.select_set(False)
        for obj in original_selection:
            if obj.name in bpy.data.objects:
                obj.select_set(True)
        if original_active and original_active.name in bpy.data.objects:
            context.view_layer.objects.active = original_active

        if processed == 0:
            self.report({"ERROR"}, f"Phase1 failed for all objects: {'; '.join(errors)}")
            return {"CANCELLED"}

        if len(mesh_objects) == 1:
            summary = self._format_summary(total_stats)
        else:
            summary = self._format_summary(total_stats, count=processed)
        if errors:
            summary += f" errors:{len(errors)}"
        self.report({"INFO"}, summary)
        return {"FINISHED"}

    @staticmethod
    def _format_summary(stats, obj_name=None, count=None):
        prefix = ""
        if count is not None:
            prefix = f"[{count} objects] "
        elif obj_name is not None:
            prefix = f"[{obj_name}] "
        return (
            f"{prefix}Phase1 quilts:{stats.get('quilts', 0)} "
            f"roots:{stats.get('supported_roots', 0)} "
            f"children:{stats.get('attached_children', 0)} "
            f"invalid:{stats.get('invalid_scaffold_patches', 0)} "
            f"unresolved:{stats.get('unresolved_scaffold_points', 0)} "
            f"missing:{stats.get('missing_uv_targets', 0)} "
            f"conflicts:{stats.get('conflicting_uv_targets', 0)}"
        )


# ============================================================
# LEGACY OPERATORS — DISABLED
# Будут пересобраны на ScaffoldMap в Phase 5.
# ============================================================

# ============================================================
# PANEL
# ============================================================

class HOTSPOTUV_PT_Panel(bpy.types.Panel):
    bl_label = "Hotspot UV"
    bl_idname = "HOTSPOTUV_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Hotspot UV"

    def draw(self, context):
        layout = self.layout
        s = context.scene.hotspotuv_settings

        # --- Settings ---
        col = layout.column(align=True)
        col.prop(s, "target_texel_density")
        col.prop(s, "texture_size")
        col.prop(s, "uv_scale")
        col.prop(s, "uv_range_limit")

        # --- Preview ---
        layout.separator()
        col = layout.column(align=True)
        col.label(text="Preview:")
        row = col.row(align=True)
        row.prop(s, "phase1_make_seams_by_sharp", text="")
        row.prop(s, "straighten_strips", text="", icon="SNAP_EDGE")
        row.operator(
            "hotspotuv.solve_phase1_preview", text="Solve Phase 1 Preview", icon="UV"
        )
        col.operator(
            "hotspotuv.clean_non_manifold_edges",
            text="Clean Non-Manifold Edges",
            icon="MESH_DATA",
        )

        # --- Debug ---
        layout.separator()
        col = layout.column(align=True)
        col.label(text="Debug:")
        row = col.row(align=True)
        row.prop(s, "dbg_verbose_console", text="Verbose Console", toggle=True)
        row.prop(s, "dbg_show_advanced_debug", text="Advanced Tools", toggle=True)
        col.operator(
            "hotspotuv.save_regression_snapshot",
            text="Save Regression Snapshot",
            icon="TEXT",
        )
        if s.dbg_replay_active:
            col.operator(
                "hotspotuv.frontier_replay",
                text="Frontier Replay: ON",
                icon="PAUSE",
                depress=True,
            )
        else:
            col.operator("hotspotuv.frontier_replay", text="Frontier Replay: OFF", icon="PLAY")
        if s.dbg_show_advanced_debug:
            col.operator("hotspotuv.flow_debug", text="Flow Debug", icon="SORTSIZE")

        # --- Analyze toggle ---
        if s.dbg_active:
            col.operator(
                "hotspotuv.debug_analysis",
                text="Analyze: ON",
                icon="PAUSE",
                depress=True,
            )
        else:
            col.operator(
                "hotspotuv.debug_analysis", text="Analyze: OFF", icon="VIEWZOOM"
            )

        # --- Layer controls (only when debug active) ---
        if s.dbg_active and s.dbg_source_object:
            gp_name = GP_DEBUG_PREFIX + s.dbg_source_object
            gp_obj = bpy.data.objects.get(gp_name)
            has_gp = is_gp_debug_object(gp_obj)

            if has_gp:
                gp_data = gp_obj.data
                _draw_debug_group(
                    col, s, gp_data, "patches", "Patches", "MESH_GRID",
                    [('Patches_WALL', 'Wall'), ('Patches_FLOOR', 'Floor'),
                     ('Patches_SLOPE', 'Slope')],
                )
                _draw_debug_group(
                    col, s, gp_data, "loops", "Loop Types", "CURVE_BEZCIRCLE",
                    [('Loops_Chains', 'Chains'), ('Loops_Boundary', 'Boundary'),
                     ('Loops_Holes', 'Holes')],
                )
                _draw_debug_group(
                    col, s, gp_data, "overlay", "Overlay", "ORIENTATION_LOCAL",
                    [('Overlay_Basis', 'Basis (U/V/N)'),
                     ('Overlay_Centers', 'Centers'),
                     ('Overlay_Labels', 'Chain Labels')],
                )

            col.separator()
            col.operator("hotspotuv.debug_clear", text="Force Clear", icon="X")


def _draw_debug_group(col, settings, gp_data, group_name, label, icon, layers):
    """Рисует collapsible debug group в panel."""
    grp_prop = f"dbg_grp_{group_name}"
    is_expanded = getattr(settings, grp_prop, True)

    box = col.box()
    row = box.row(align=True)
    arrow_icon = 'TRIA_DOWN' if is_expanded else 'TRIA_RIGHT'
    op = row.operator("hotspotuv.debug_toggle_group", text="", icon=arrow_icon, emboss=False)
    op.group_name = group_name
    row.label(text=label, icon=icon)

    if is_expanded:
        for layer_name, layer_label in layers:
            # Chain Labels — коллекция, а не GP layer
            if layer_name == 'Overlay_Labels':
                from .debug import _LABEL_COLLECTION_NAME
                if _LABEL_COLLECTION_NAME in bpy.data.collections:
                    label_col = bpy.data.collections[_LABEL_COLLECTION_NAME]
                    row = box.row(align=True)
                    row.separator(factor=2.0)
                    vis_icon = 'HIDE_OFF' if not label_col.hide_viewport else 'HIDE_ON'
                    op = row.operator(
                        "hotspotuv.debug_toggle_layer", text="", icon=vis_icon
                    )
                    op.layer_name = layer_name
                    row.label(text=layer_label)
                continue

            layer = get_gp_layer(gp_data, layer_name)
            if layer is not None:
                row = box.row(align=True)
                row.separator(factor=2.0)
                vis_icon = 'HIDE_OFF' if not layer.hide else 'HIDE_ON'
                op = row.operator(
                    "hotspotuv.debug_toggle_layer", text="", icon=vis_icon
                )
                op.layer_name = layer_name
                row.label(text=layer_label)


# ============================================================
# REGISTRATION
# ============================================================

classes = (
    HOTSPOTUV_AddonPreferences,
    HOTSPOTUV_Settings,
    HOTSPOTUV_OT_DebugAnalysis,
    HOTSPOTUV_OT_DebugClear,
    HOTSPOTUV_OT_DebugToggleLayer,
    HOTSPOTUV_OT_DebugToggleGroup,
    HOTSPOTUV_OT_FlowDebug,
    HOTSPOTUV_OT_ScaffoldDebug,
    HOTSPOTUV_OT_SaveRegressionSnapshot,
    HOTSPOTUV_OT_FrontierReplay,
    HOTSPOTUV_OT_SolvePhase1Preview,
    HOTSPOTUV_OT_CleanNonManifoldEdges,
    HOTSPOTUV_PT_Panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.hotspotuv_settings = PointerProperty(type=HOTSPOTUV_Settings)
    if _frontier_replay_frame_handler not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(_frontier_replay_frame_handler)


def unregister():
    if _frontier_replay_frame_handler in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(_frontier_replay_frame_handler)
    # Cleanup GP debug objects
    for obj in list(bpy.data.objects):
        if obj.name.startswith(GP_DEBUG_PREFIX):
            bpy.data.objects.remove(obj, do_unlink=True)
    if hasattr(bpy.types.Scene, "hotspotuv_settings"):
        del bpy.types.Scene.hotspotuv_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
