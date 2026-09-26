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
from scaffold_core.layer_5_runtime.pins import run_skeleton_solve  # noqa: E402
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations  # noqa: E402


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
        record.update(_pipeline_metrics(source, context))
        solve = run_skeleton_solve(context)
        record.update(_solve_metrics(solve))
        if args.write_uv:
            record.update(_write_uv_metrics(obj, solve, source, args.selection))
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
    return {
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

    return {
        "rigid_islands": sum(1 for skeleton in solve.skeletons if skeleton.frame == "UNFOLDED"),
        "island_lines": sum(len(set(skeleton.line_by_run.values())) for skeleton in solve.skeletons),
        "axis_runs": roles.get("AXIS_A", 0) + roles.get("AXIS_B", 0),
        "oblique_runs": roles.get("OBLIQUE", 0),
        "bipartition_conflicts": count("axis bipartition conflict"),
        "lines_not_straight": count("island line not straight"),
        "patches_outside_frame": count("patch outside the rigid island frame"),
        "node_frame_mismatches": len(solve.node_frame_mismatches),
    }


def _write_uv_metrics(obj, solve, source, selection: str) -> dict:
    """Write pins through the G5 boundary and prove no loop outside the selection changed."""

    from scaffold_core.layer_5_runtime.uv_transfer import write_pinned_uvs

    solved_faces = {int(str(face_id)[1:]) for face_id in source.selected_face_ids}
    foreign_before = _foreign_loop_state(obj, solved_faces)
    edit = selection == "file" and len(solved_faces) < len(obj.data.polygons)
    if edit:
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="EDIT")
    try:
        summary = write_pinned_uvs(SimpleNamespace(object=obj), solve)
    finally:
        if edit:
            bpy.ops.object.mode_set(mode="OBJECT")
    foreign_after = _foreign_loop_state(obj, solved_faces)
    uv_layer = obj.data.uv_layers.active
    pinned_loops = sum(1 for loop_uv in uv_layer.data if loop_uv.pin_uv) if uv_layer else 0
    return {
        "written_loops": summary["written_loops"],
        "pinned_loops": pinned_loops,
        "foreign_loops_changed": sum(
            1 for before, after in zip(foreign_before, foreign_after) if before != after
        ),
    }


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
