"""
Layer: dev tooling

Rules:
- Tier 3 headless Blender smoke runner, executed inside Blender via --python.
- Consumes scaffold_core like the debug add-on; defines no Scaffold relations.
- Never saves the .blend: selection changes and UV writes stay in memory.
- Prints one compact SMOKE line per object; the full report goes to --out.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
import traceback
from collections import Counter
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import bpy  # noqa: E402 - executed by Blender only

from scaffold_core.layer_0_source.blender_io import read_source_mesh_from_blender  # noqa: E402
from scaffold_core.layer_4_features.model import FeatureOptions  # noqa: E402
from scaffold_core.layer_5_runtime.pins import run_skeleton_solve  # noqa: E402
from scaffold_core.pipeline.passes import (  # noqa: E402
    run_pass_0,
    run_pass_1_relations,
    run_pass_2_features,
    run_pass_3_filters,
)
from scaffold_core.user_filters.model import FilterOptions  # noqa: E402


RESIDUAL_OK_LIMIT = 1.0e-4
SNAPSHOT_IO_PATH = REPO_ROOT / "dev" / "tools" / "scaffold_graph_debug" / "snapshot_io.py"


def main() -> int:
    args = _parse_args()
    objects = _target_objects(args)
    records = []
    for obj in objects:
        record = _run_object(obj, args)
        records.append(record)
        print("SMOKE " + json.dumps(record, sort_keys=True), flush=True)
    report = {
        "format": "scaffold_blender_smoke_v1",
        "blender_version": bpy.app.version_string,
        "blend_file": Path(bpy.data.filepath).name,
        "selection": args.selection,
        "records": records,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=1, sort_keys=True), encoding="utf-8")
    return 0


def _parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(prog="blender_smoke")
    parser.add_argument("--objects", default="", help="comma-separated object names")
    parser.add_argument("--seamed", action="store_true", help="all mesh objects with UV seams")
    parser.add_argument("--selection", choices=("file", "all"), default="file")
    parser.add_argument("--write-uv", action="store_true", help="exercise the UV write boundary")
    parser.add_argument("--capture-dir", default="", help="dump SourceMeshSnapshot JSON per object")
    parser.add_argument("--straighten-strips", action="store_true", help="run Pass 2 with straighten_strips")
    parser.add_argument(
        "--world-up", default="",
        help="run Pass 2 and the Pass 3 user filter with this up axis in world space, turned into each "
        "object's space by its matrix_world (a non-uniform object scale is not handled)",
    )
    parser.add_argument(
        "--unwrap-quilts", action="store_true", help="with --write-uv: lay the quilts (write_quilt_uvs)"
    )
    parser.add_argument("--out", required=True)
    return parser.parse_args(argv)


def _target_objects(args: argparse.Namespace) -> list:
    names = [name for name in args.objects.split(",") if name]
    if names:
        return [bpy.data.objects[name] for name in names]
    meshes = sorted((obj for obj in bpy.data.objects if obj.type == "MESH"), key=lambda obj: obj.name)
    if args.seamed:
        return [obj for obj in meshes if any(edge.use_seam for edge in obj.data.edges)]
    return meshes


def _run_object(obj, args: argparse.Namespace) -> dict:
    started = time.perf_counter()
    record: dict = {"object": obj.name}
    try:
        source = _read_source(obj, args.selection)
        if args.capture_dir:
            _dump_capture(source, Path(args.capture_dir) / f"{obj.name}.json")
        context = run_pass_1_relations(run_pass_0(source))
        if args.straighten_strips:
            context = run_pass_2_features(context, FeatureOptions(straighten_strips=True))
        world_up = tuple(float(value) for value in args.world_up.split(",")) if args.world_up else None
        if world_up is not None:
            # FilterOptions.world_up is a direction in the mesh's own space
            from mathutils import Vector

            world_up = tuple(float(value) for value in obj.matrix_world.to_3x3().inverted_safe() @ Vector(world_up))
            if context.feature_snapshot is None:
                context = run_pass_2_features(context)
            context = run_pass_3_filters(context, FilterOptions(world_up=world_up))
        record.update(_pipeline_metrics(source, context))
        solve = run_skeleton_solve(context)
        if world_up is not None:
            # the user filter (absent without --world-up): its directives and the quilts they make
            for kind in ("SPLIT", "JOIN"):
                record[f"filter_{kind.lower()}"] = sum(
                    1 for directive in context.filter_snapshot.directives if directive.kind.value == kind
                )
        record.update(_solve_metrics(solve))
        record.update(_corner_turn_metrics(context, solve))
        if args.straighten_strips:
            # Layer 4 STRAIGHT_STRIP constraints applied as strip islands (absent without the flag)
            record["strip_islands"] = sum(1 for skeleton in solve.skeletons if skeleton.frame == "STRIP")
            # STRAIGHT_LADDER constraints (marked bevel strips, option on by default) laid as LADDER islands
            record["ladder_islands"] = sum(1 for skeleton in solve.skeletons if skeleton.frame == "LADDER")
            record["bevel_ladder_constraints"] = sum(
                1 for constraint in context.feature_snapshot.constraints if constraint.kind.value == "STRAIGHT_LADDER"
            )
        if args.write_uv:
            record.update(_write_uv_metrics(obj, solve, source, args.selection, args.unwrap_quilts))
    except Exception as error:  # report, never abort the batch
        if obj.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        frame = traceback.extract_tb(error.__traceback__)[-1]
        record["error"] = f"{type(error).__name__}: {error} @ {Path(frame.filename).name}:{frame.lineno}"[:200]
    record["ms"] = round((time.perf_counter() - started) * 1000)
    return record


def _read_source(obj, selection: str):
    """Read like the artist: stored face selection in Edit Mode, else all faces."""

    uses_file_selection = selection == "file" and any(polygon.select for polygon in obj.data.polygons)
    if not uses_file_selection:
        return read_source_mesh_from_blender(SimpleNamespace(object=obj))
    for other in bpy.context.view_layer.objects:
        other.select_set(False)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        return read_source_mesh_from_blender(SimpleNamespace(object=obj))
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")


def _pipeline_metrics(source, context) -> dict:
    topology = context.topology_snapshot
    relations = context.relation_snapshot
    family_sizes = [len(family.member_directional_evidence_ids) for family in relations.connected_direction_families]
    codes = Counter(diagnostic.code for diagnostic in context.diagnostics.diagnostics)
    shapes = Counter(relation.kind.value for relation in relations.patch_chain_shape_relations)
    return {
        # chain shape Stage A: PatchChain pieces per kind on their own side (evidence only)
        "shape_lines": shapes.get("SURFACE_LINE", 0),
        "shape_curves": shapes.get("SURFACE_CURVE", 0),
        "shape_unresolved": shapes.get("UNRESOLVED", 0),
        "shape_law_mismatches": codes.get("PATCH_CHAIN_SHAPE_LAW_MISMATCH", 0),
        "faces": len(source.selected_face_ids) or len(source.faces),
        "shells": len(topology.shells),
        "patches": len(topology.patches),
        "chains": len(topology.chains),
        "families": len(family_sizes),
        "family_max": max(family_sizes, default=0),
        "opposite_side_families": codes.get("FAMILY_SPANS_OPPOSITE_PATCH_SIDES", 0),
        "rails": len(relations.scaffold_rails),
        "rails_consumable": sum(1 for rail in relations.scaffold_rails if rail.is_consumable_by_g5a),
        "pipeline_codes": dict(sorted(codes.items())),
    }


def _solve_metrics(solve) -> dict:
    roles = Counter(role for skeleton in solve.skeletons for role in skeleton.axis_role_by_run.values())
    return {
        "islands": len(solve.assembly.islands),
        "pinned": sum(1 for vertex in solve.vertices if vertex.pinned),
        "residual_max": float(f"{solve.residual_max:.2g}"),
        "residual_ok": solve.residual_max < RESIDUAL_OK_LIMIT,
        "solve_diagnostics": len(solve.diagnostics),
        "axis_violations": len(solve.axis_parallel_violations),
        "seam_mismatches": len(solve.seam_length_mismatches),
        "first_solve_diagnostic": solve.diagnostics[0][:120] if solve.diagnostics else "",
        **_structure_metrics(solve, roles),
    }


def _structure_metrics(solve, roles: Counter) -> dict:
    """Consistency of patch -> line -> island structure (plan Slice N), not UV quality."""

    def count(prefix: str) -> int:
        return sum(1 for diagnostic in solve.diagnostics if diagnostic.startswith(prefix))

    island_rails = [
        segment
        for skeleton in solve.skeletons
        for segment in skeleton.rail_segments
        if len(segment.ordered_member_directional_evidence_ids) > 1
    ]
    return {
        "rigid_islands": sum(1 for skeleton in solve.skeletons if skeleton.frame == "UNFOLDED"),
        "island_lines": sum(len(set(skeleton.line_by_run.values())) for skeleton in solve.skeletons),
        "axis_runs": roles.get("AXIS_A", 0) + roles.get("AXIS_B", 0),
        "oblique_runs": roles.get("OBLIQUE", 0),
        "bipartition_conflicts": count("axis bipartition conflict"),
        "lines_not_straight": count("island line not straight"),
        "patches_outside_frame": count("patch outside the rigid island frame"),
        "node_frame_mismatches": len(solve.node_frame_mismatches),
        # plan Slice O: Layer 3 rails cut by each island, checked against the island lines and frame
        "island_rails": len(island_rails),
        "unordered_island_rails": sum(1 for segment in island_rails if not segment.is_ordered),
        "rail_frame_conflicts": len(solve.rail_frame_conflicts),
    }


def _corner_turn_metrics(context, solve) -> dict:
    """The corner law in the solved layout (convex turns left, reflex right)."""

    from dev.tools.cftuv_parity.parity import corner_turns

    with_law, checked, mirrored = corner_turns(context.relation_snapshot, solve)
    return {"corners_against_law": checked - with_law, "mirrored_islands": mirrored}


def _write_uv_metrics(obj, solve, source, selection: str, unwrap_quilts: bool = False) -> dict:
    """Write pins through the G5 boundary and prove no loop outside the selection changed.

    With unwrap_quilts the quilts are laid (write_quilt_uvs), and the record
    also says how many seam flags differ after the write. A second visible
    mesh object is selected too (in Object Mode beside the target) and its UV
    loops are compared. The run fails (an error record) when a seam flag
    differs, a loop of an unsolved face or of the other object changes, a
    vertex, edge or face selection flag of the target's mesh changes (read
    in the mode the writer was called in), or the object selection or the
    active object is not restored.
    """

    from scaffold_core.layer_5_runtime.uv_transfer import write_pinned_uvs, write_quilt_uvs

    solved_faces = {int(str(face_id)[1:]) for face_id in source.selected_face_ids}
    foreign_before = _foreign_loop_state(obj, solved_faces)
    edit = selection == "file" and len(solved_faces) < len(obj.data.polygons)
    if edit:
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="EDIT")
    seams_before = [edge.use_seam for edge in obj.data.edges]
    other = _other_mesh_object(obj) if unwrap_quilts else None
    if other is not None:
        other.select_set(True)
    other_before = _foreign_loop_state(other, set()) if other is not None else []
    selected_before = {item.name for item in bpy.context.view_layer.objects if item.select_get()}
    active_before = bpy.context.view_layer.objects.active
    flags_before = _selection_flags(obj) if unwrap_quilts else None
    try:
        writer = write_quilt_uvs if unwrap_quilts else write_pinned_uvs
        summary = writer(SimpleNamespace(object=obj), solve)
        flags_after = _selection_flags(obj) if unwrap_quilts else None
    finally:
        if edit:
            bpy.ops.object.mode_set(mode="OBJECT")
    foreign_after = _foreign_loop_state(obj, solved_faces)
    uv_layer = obj.data.uv_layers.active
    pinned_loops = sum(1 for loop_uv in uv_layer.data if loop_uv.pin_uv) if uv_layer else 0
    extra = {}
    if unwrap_quilts:
        extra["seam_flags_changed"] = sum(
            1 for edge, before in zip(obj.data.edges, seams_before) if edge.use_seam != before
        )
        other_after = _foreign_loop_state(other, set()) if other is not None else []
        other_changed = sum(1 for before, after in zip(other_before, other_after) if before != after)
        foreign_changed = sum(1 for before, after in zip(foreign_before, foreign_after) if before != after)
        selection_kept = selected_before == {item.name for item in bpy.context.view_layer.objects if item.select_get()}
        active_kept = bpy.context.view_layer.objects.active == active_before
        flags_changed = sum(
            1 for before, after in zip(flags_before, flags_after) for a, b in zip(before, after) if a != b
        )
        if other is not None:
            other.select_set(False)
        if (
            extra["seam_flags_changed"] or other_changed or foreign_changed or flags_changed
            or not selection_kept or not active_kept
        ):
            raise RuntimeError(
                f"write_quilt_uvs changed state: seam flags {extra['seam_flags_changed']}, unsolved loops "
                f"{foreign_changed}, other object loops {other_changed}, mesh selection flags {flags_changed}, "
                f"selection kept {selection_kept}, active kept {active_kept}"
            )
    return {
        **extra,
        "written_loops": summary["written_loops"],
        "pinned_loops": pinned_loops,
        "foreign_loops_changed": sum(
            1 for before, after in zip(foreign_before, foreign_after) if before != after
        ),
    }


def _selection_flags(obj) -> tuple:
    """The vertex, edge and face select flags of obj's mesh, from the edit mesh in Edit Mode."""

    if obj.mode == "EDIT":
        import bmesh

        bm = bmesh.from_edit_mesh(obj.data)
        return tuple([item.select for item in items] for items in (bm.verts, bm.edges, bm.faces))
    mesh = obj.data
    return tuple([item.select for item in items] for items in (mesh.vertices, mesh.edges, mesh.polygons))


def _other_mesh_object(obj):
    """A visible mesh object other than obj, with its own mesh and an active UV layer, or None."""

    for other in sorted(bpy.context.view_layer.objects, key=lambda item: item.name):
        if other != obj and other.type == "MESH" and other.visible_get() and other.data != obj.data:
            if other.data.uv_layers.active is not None and len(other.data.polygons):
                return other
    return None


def _foreign_loop_state(obj, solved_faces: set[int]) -> list:
    uv_layer = obj.data.uv_layers.active
    if uv_layer is None:
        return []
    state = []
    for polygon in obj.data.polygons:
        if polygon.index in solved_faces:
            continue
        for loop_index in polygon.loop_indices:
            loop_uv = uv_layer.data[loop_index]
            state.append((round(loop_uv.uv[0], 6), round(loop_uv.uv[1], 6), loop_uv.pin_uv))
    return state


def _dump_capture(source, path: Path) -> None:
    spec = importlib.util.spec_from_file_location("scaffold_snapshot_io", SNAPSHOT_IO_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path.parent.mkdir(parents=True, exist_ok=True)
    module.dump_source_snapshot(source, path)


if __name__ == "__main__":
    sys.exit(main())
