"""
Blender runner for the disposable SCAFFOLD tracer spike v2.

Run from Blender's Text Editor or with:

    blender --python dev/tools/tracer_spike/blender_run.py

This script is intentionally outside scaffold_core. It consumes the existing
Blender read boundary, the Pass 0/Pass 1 pipeline, and the typed tracer spike
layout dump, then writes only UV coordinates and UV pins on the active mesh.
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _candidate_repo_roots() -> list[Path]:
    candidates: list[Path] = []
    env_root = os.environ.get("SCAFFOLD_REPO_ROOT")
    if env_root:
        candidates.append(Path(env_root).expanduser())
    raw_file = globals().get("__file__")
    if raw_file:
        file_path = Path(raw_file)
        if file_path.exists():
            candidates.append(file_path.resolve().parent)
    blender_text_path = _blender_text_filepath()
    if blender_text_path is not None:
        candidates.append(blender_text_path.parent)
    candidates.append(Path.cwd())
    candidates.append(Path.cwd() / "dev" / "tools" / "tracer_spike")
    return candidates


def _blender_text_filepath() -> Path | None:
    try:
        import bpy  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        return None
    space_data = getattr(getattr(bpy, "context", None), "space_data", None)
    text = getattr(space_data, "text", None)
    filepath = getattr(text, "filepath", "")
    if not filepath:
        return None
    path = Path(filepath)
    if not path.exists():
        return None
    return path.resolve()


def _find_repo_root() -> Path:
    checked: list[str] = []
    for start in _candidate_repo_roots():
        for candidate in (start, *start.parents):
            checked.append(str(candidate))
            if (
                (candidate / "scaffold_core").is_dir()
                and (candidate / "dev" / "tools" / "tracer_spike" / "run_tracer_spike.py").is_file()
            ):
                return candidate
    checked_text = "\n".join(f"- {path}" for path in dict.fromkeys(checked))
    raise RuntimeError(
        "Could not locate the SCAFFOLD repo root. Open this script from disk, "
        "run Blender from E:\\GITHUB\\SCAFFOLD, or set SCAFFOLD_REPO_ROOT.\n"
        f"Checked:\n{checked_text}"
    )


REPO_ROOT = _find_repo_root()
SCRIPT_DIR = REPO_ROOT / "dev" / "tools" / "tracer_spike"
REPORT_PATH = SCRIPT_DIR / "blender_run_report.md"
ISLAND_OFFSET_MARGIN = 2.0

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:
    from dev.tools.tracer_spike.run_tracer_spike import build_layout_dump
except ModuleNotFoundError as exc:
    if exc.name != "dev":
        raise
    from run_tracer_spike import build_layout_dump
from scaffold_core.layer_0_source.blender_io import read_source_mesh_from_blender
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations


EXPECTATION_HEADER = """## Expectation Management

v2 diagnoses reality gaps; it does not produce final-quality UVs.
Known limits: crude rail collapse math from spike v0, conservative splits on
asymmetric curved bevels, no scale/texel policy, naive island offsets, interior
quality depends on Blender's solver.
"""

VALIDATION_CHECKLIST = """## User Validation Checklist

- Select wall faces with seams marked, run script.
- UV editor: rails are straight lines, pins visible on rails.
- Seams the gate stitched are interior straight stitches.
- Cap-like patches are separate islands.
- Report any crash/wrong island with the console dump.
"""


@dataclass(frozen=True)
class WriteResult:
    object_name: str
    mesh_name: str
    uv_layer_name: str
    selected_face_count: int
    layout_vertex_count: int
    pinned_layout_vertex_count: int
    written_loop_count: int
    pinned_loop_count: int
    cleared_pin_count: int
    unsupported_pin_loop_count: int
    ambiguous_loop_count: int
    missing_loop_count: int
    island_offsets: dict[str, tuple[float, float]]
    loops_written_by_island: dict[str, int]
    pins_written_by_island: dict[str, int]
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class UnwrapResult:
    ok: bool
    blender_version: str
    call: str
    result: str | None = None
    error: str | None = None
    fallback_used: bool = False


@dataclass
class LoopWriteStats:
    written_loop_count: int = 0
    pinned_loop_count: int = 0
    cleared_pin_count: int = 0
    unsupported_pin_loop_count: int = 0
    ambiguous_loop_count: int = 0
    missing_loop_count: int = 0
    loops_written_by_island: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    pins_written_by_island: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    notes: list[str] = field(default_factory=list)


def main() -> None:
    bpy = _load_bpy()
    active_object = getattr(bpy.context, "object", None)
    if active_object is None or getattr(active_object, "type", None) != "MESH":
        raise ValueError("Select an active mesh object before running the tracer spike.")

    original_mode = getattr(active_object, "mode", "OBJECT")
    source_snapshot = read_source_mesh_from_blender(bpy.context)
    pipeline_context = run_pass_1_relations(run_pass_0(source_snapshot))
    layout = build_layout_dump(str(source_snapshot.id), pipeline_context)

    try:
        _set_object_mode(bpy, active_object, "OBJECT")
        write_result = write_skeleton_uvs(bpy, active_object, pipeline_context, layout)
        unwrap_result = call_conformal_unwrap(bpy, active_object)
    finally:
        _restore_mode(bpy, active_object, original_mode)

    report = build_blender_report(
        layout=layout,
        source_id=str(source_snapshot.id),
        write_result=write_result,
        unwrap_result=unwrap_result,
    )
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(report)
    print(f"Scaffold tracer spike v2 report saved to: {REPORT_PATH}")


def _load_bpy() -> Any:
    try:
        import bpy  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        raise RuntimeError("This script must be run inside Blender so bpy is available.") from exc
    return bpy


def write_skeleton_uvs(bpy: Any, active_object: Any, pipeline_context: Any, layout: dict[str, Any]) -> WriteResult:
    mesh = active_object.data
    selected_polygons = [polygon for polygon in mesh.polygons if getattr(polygon, "select", False)]
    if not selected_polygons:
        raise ValueError("No selected faces. Select the wall/floor/cap faces to trace before running the script.")

    uv_layer = _ensure_uv_layer(mesh)
    island_offsets = _build_island_offsets(layout)
    vertex_entries = _build_vertex_entry_index(layout)
    source_to_topology_vertices = _build_source_to_topology_vertices(pipeline_context.topology_snapshot)
    face_to_island = _build_face_to_island(pipeline_context.topology_snapshot, layout)
    stats = LoopWriteStats()

    _clear_selected_loop_pins(uv_layer, selected_polygons, stats)

    for polygon in selected_polygons:
        face_island_id = face_to_island.get(f"f{polygon.index}")
        for loop_index, vertex_index in zip(polygon.loop_indices, polygon.vertices):
            entry = _choose_layout_entry(
                source_vertex_id=f"v{vertex_index}",
                island_id=face_island_id,
                source_to_topology_vertices=source_to_topology_vertices,
                vertex_entries=vertex_entries,
                stats=stats,
            )
            if entry is None:
                continue
            island_id = str(entry["island_id"])
            uv = entry["uv"]
            offset_u, offset_v = island_offsets.get(island_id, (0.0, 0.0))
            loop_data = uv_layer.data[loop_index]
            loop_data.uv = (float(uv[0]) + offset_u, float(uv[1]) + offset_v)
            stats.written_loop_count += 1
            stats.loops_written_by_island[island_id] += 1
            if bool(entry.get("pinned")):
                if _set_loop_pin(loop_data, True):
                    stats.pinned_loop_count += 1
                    stats.pins_written_by_island[island_id] += 1
                else:
                    stats.unsupported_pin_loop_count += 1

    mesh.update()
    layout_vertices = list(layout.get("vertices", {}).values())
    return WriteResult(
        object_name=str(getattr(active_object, "name", "<object>")),
        mesh_name=str(getattr(mesh, "name", "<mesh>")),
        uv_layer_name=str(getattr(uv_layer, "name", "<active UV layer>")),
        selected_face_count=len(selected_polygons),
        layout_vertex_count=len(layout_vertices),
        pinned_layout_vertex_count=sum(1 for entry in layout_vertices if bool(entry.get("pinned"))),
        written_loop_count=stats.written_loop_count,
        pinned_loop_count=stats.pinned_loop_count,
        cleared_pin_count=stats.cleared_pin_count,
        unsupported_pin_loop_count=stats.unsupported_pin_loop_count,
        ambiguous_loop_count=stats.ambiguous_loop_count,
        missing_loop_count=stats.missing_loop_count,
        island_offsets=island_offsets,
        loops_written_by_island=dict(stats.loops_written_by_island),
        pins_written_by_island=dict(stats.pins_written_by_island),
        notes=tuple(stats.notes),
    )


def call_conformal_unwrap(bpy: Any, active_object: Any) -> UnwrapResult:
    version = ".".join(str(part) for part in getattr(bpy.app, "version", ()))
    _set_object_mode(bpy, active_object, "EDIT")
    try:
        result = bpy.ops.uv.unwrap(method="CONFORMAL")
        return UnwrapResult(
            ok=True,
            blender_version=version,
            call='bpy.ops.uv.unwrap(method="CONFORMAL")',
            result=repr(result),
        )
    except TypeError as conformal_error:
        try:
            result = bpy.ops.uv.unwrap()
            return UnwrapResult(
                ok=True,
                blender_version=version,
                call="bpy.ops.uv.unwrap()",
                result=repr(result),
                error=f'CONFORMAL call rejected: {type(conformal_error).__name__}: {conformal_error}',
                fallback_used=True,
            )
        except Exception as fallback_error:  # pragma: no cover - Blender-only branch.
            return UnwrapResult(
                ok=False,
                blender_version=version,
                call='bpy.ops.uv.unwrap(method="CONFORMAL") then bpy.ops.uv.unwrap()',
                error=(
                    f'CONFORMAL error: {type(conformal_error).__name__}: {conformal_error}; '
                    f'fallback error: {type(fallback_error).__name__}: {fallback_error}'
                ),
            )
    except Exception as exc:  # pragma: no cover - Blender-only branch.
        return UnwrapResult(
            ok=False,
            blender_version=version,
            call='bpy.ops.uv.unwrap(method="CONFORMAL")',
            error=f"{type(exc).__name__}: {exc}",
        )


def build_blender_report(
    layout: dict[str, Any],
    source_id: str,
    write_result: WriteResult,
    unwrap_result: UnwrapResult,
) -> str:
    island_sections = "\n\n".join(
        _format_island_report(island, layout, write_result)
        for island in layout.get("islands", ())
    )
    notes = "\n".join(f"- {note}" for note in write_result.notes) or "- None."
    ambiguities = "\n".join(f"- {item}" for item in layout.get("ambiguities", ())) or "- None."
    improvisations = "\n".join(f"- {item}" for item in layout.get("improvisations", ())) or "- None."
    return f"""# Scaffold Tracer Spike v2 Blender Report

Generated by `dev/tools/tracer_spike/blender_run.py`.

{EXPECTATION_HEADER}
{VALIDATION_CHECKLIST}
## Run

- Source: `{source_id}`
- Object: `{write_result.object_name}`
- Mesh: `{write_result.mesh_name}`
- Blender version: `{unwrap_result.blender_version}`
- Active UV layer: `{write_result.uv_layer_name}`
- Selected faces: {write_result.selected_face_count}
- Layout vertices: {write_result.layout_vertex_count}
- Pinned layout vertices: {write_result.pinned_layout_vertex_count}
- Written skeleton loops: {write_result.written_loop_count}
- Pinned loops: {write_result.pinned_loop_count}
- Cleared selected-loop pins before write: {write_result.cleared_pin_count}
- Unsupported pin loop writes: {write_result.unsupported_pin_loop_count}
- Ambiguous loop choices: {write_result.ambiguous_loop_count}
- Missing layout loop choices: {write_result.missing_loop_count}
- Unwrap call: `{unwrap_result.call}`
- Unwrap status: {_format_unwrap_status(unwrap_result)}

## Islands

{island_sections}

## Runner Notes

{notes}

## Frontier Ambiguities

{ambiguities}

## Frontier Improvisations

{improvisations}
"""


def _ensure_uv_layer(mesh: Any) -> Any:
    uv_layer = getattr(mesh.uv_layers, "active", None)
    if uv_layer is None:
        uv_layer = mesh.uv_layers.new(name="Scaffold Spike v2")
        mesh.uv_layers.active = uv_layer
    return uv_layer


def _clear_selected_loop_pins(uv_layer: Any, selected_polygons: list[Any], stats: LoopWriteStats) -> None:
    for polygon in selected_polygons:
        for loop_index in polygon.loop_indices:
            loop_data = uv_layer.data[loop_index]
            if _set_loop_pin(loop_data, False):
                stats.cleared_pin_count += 1
            else:
                stats.unsupported_pin_loop_count += 1


def _set_loop_pin(loop_data: Any, pinned: bool) -> bool:
    for attribute in ("pin_uv", "pin"):
        if hasattr(loop_data, attribute):
            setattr(loop_data, attribute, bool(pinned))
            return True
    return False


def _build_island_offsets(layout: dict[str, Any]) -> dict[str, tuple[float, float]]:
    entries_by_island: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in layout.get("vertices", {}).values():
        entries_by_island[str(entry["island_id"])].append(entry)

    offsets: dict[str, tuple[float, float]] = {}
    cursor_u = 0.0
    island_ids = sorted(str(island["id"]) for island in layout.get("islands", ()))
    for island_id in island_ids:
        entries = entries_by_island.get(island_id, ())
        if not entries:
            offsets[island_id] = (cursor_u, 0.0)
            cursor_u += ISLAND_OFFSET_MARGIN
            continue
        min_u = min(float(entry["uv"][0]) for entry in entries)
        max_u = max(float(entry["uv"][0]) for entry in entries)
        min_v = min(float(entry["uv"][1]) for entry in entries)
        offsets[island_id] = (cursor_u - min_u, -min_v)
        cursor_u += max(max_u - min_u, 1.0) + ISLAND_OFFSET_MARGIN
    return offsets


def _build_vertex_entry_index(layout: dict[str, Any]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    vertex_entries: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for layout_key, entry in layout.get("vertices", {}).items():
        row = dict(entry)
        row["_layout_key"] = layout_key
        vertex_entries[(str(row["vertex_id"]), str(row["island_id"]))].append(row)
    for entries in vertex_entries.values():
        entries.sort(key=lambda item: str(item["_layout_key"]))
    return vertex_entries


def _build_source_to_topology_vertices(topology: Any) -> dict[str, list[str]]:
    source_to_topology_vertices: dict[str, list[str]] = defaultdict(list)
    for vertex in topology.vertices.values():
        for source_vertex_id in vertex.source_vertex_ids:
            source_to_topology_vertices[str(source_vertex_id)].append(str(vertex.id))
    for vertex_ids in source_to_topology_vertices.values():
        vertex_ids.sort()
    return source_to_topology_vertices


def _build_face_to_island(topology: Any, layout: dict[str, Any]) -> dict[str, str]:
    island_by_patch_id = {
        str(patch_id): str(island["id"])
        for island in layout.get("islands", ())
        for patch_id in island.get("patch_ids", ())
    }
    face_to_island: dict[str, str] = {}
    for patch in topology.patches.values():
        island_id = island_by_patch_id.get(str(patch.id))
        if island_id is None:
            continue
        for source_face_id in patch.source_face_ids:
            face_to_island[str(source_face_id)] = island_id
    return face_to_island


def _choose_layout_entry(
    source_vertex_id: str,
    island_id: str | None,
    source_to_topology_vertices: dict[str, list[str]],
    vertex_entries: dict[tuple[str, str], list[dict[str, Any]]],
    stats: LoopWriteStats,
) -> dict[str, Any] | None:
    topology_vertex_ids = source_to_topology_vertices.get(source_vertex_id, ())
    candidates: list[dict[str, Any]] = []
    if island_id is not None:
        for vertex_id in topology_vertex_ids:
            candidates.extend(vertex_entries.get((vertex_id, island_id), ()))
    if not candidates:
        for vertex_id in topology_vertex_ids:
            for (entry_vertex_id, _entry_island_id), entries in vertex_entries.items():
                if entry_vertex_id == vertex_id:
                    candidates.extend(entries)
    if not candidates:
        stats.missing_loop_count += 1
        return None
    candidates = [entry for entry in candidates if bool(entry.get("pinned"))]
    if not candidates:
        return None
    candidates.sort(key=lambda item: (str(item["island_id"]), str(item["_layout_key"])))
    if len(candidates) > 1:
        stats.ambiguous_loop_count += 1
        if stats.ambiguous_loop_count <= 12:
            stats.notes.append(
                f"{source_vertex_id}: chose {candidates[0]['_layout_key']} among "
                f"{len(candidates)} pinned layout candidates"
            )
    return candidates[0]


def _format_island_report(
    island: dict[str, Any],
    layout: dict[str, Any],
    write_result: WriteResult,
) -> str:
    island_id = str(island["id"])
    rails = [
        rail for rail in layout.get("rails", ())
        if str(rail.get("island_id")) == island_id
    ]
    accepted_stitches = [
        decision for decision in layout.get("stitch_decisions", ())
        if bool(decision.get("accepted"))
        and decision.get("from_patch_id") in island.get("patch_ids", ())
        and decision.get("to_patch_id") in island.get("patch_ids", ())
    ]
    blocked_stitches = [
        decision for decision in layout.get("stitch_decisions", ())
        if not bool(decision.get("accepted"))
        and (
            decision.get("from_patch_id") in island.get("patch_ids", ())
            or decision.get("to_patch_id") in island.get("patch_ids", ())
        )
    ]
    rail_lines = "\n".join(_format_rail(rail) for rail in rails) or "- None."
    accepted_lines = "\n".join(_format_stitch(decision) for decision in accepted_stitches) or "- None."
    blocked_lines = "\n".join(_format_stitch(decision) for decision in blocked_stitches) or "- None."
    offset = write_result.island_offsets.get(island_id, (0.0, 0.0))
    return f"""### {island_id}

- Patches: {", ".join(str(patch_id) for patch_id in island.get("patch_ids", ()))}
- Seed patch: `{island.get("seed_patch_id")}`
- Offset: ({offset[0]:.6g}, {offset[1]:.6g})
- Layout vertices: {len(island.get("vertex_ids", ()))}
- Written loops: {write_result.loops_written_by_island.get(island_id, 0)}
- Pinned loops: {write_result.pins_written_by_island.get(island_id, 0)}

Rails:

{rail_lines}

Stitched seams:

{accepted_lines}

Blocked seams:

{blocked_lines}
"""


def _format_rail(rail: dict[str, Any]) -> str:
    branch_count = len(rail.get("branch_records", {}))
    return (
        f"- `{rail.get('id')}` source={rail.get('source')} "
        f"members={len(rail.get('member_directional_evidence_ids', ()))}, "
        f"assigned_vertices={len(rail.get('assigned_vertex_ids', ()))}, "
        f"branches={branch_count}"
    )


def _format_stitch(decision: dict[str, Any]) -> str:
    defects = decision.get("vertex_angle_defects", {})
    defect_text = ", ".join(
        f"{vertex_id}={_format_float_or_none(value)}"
        for vertex_id, value in sorted(defects.items())
    ) or "none"
    return (
        f"- `{decision.get('from_patch_id')}` -> `{decision.get('to_patch_id')}` "
        f"chain=`{decision.get('chain_id')}` accepted={decision.get('accepted')} "
        f"reason={decision.get('reason')} defects=[{defect_text}]"
    )


def _format_float_or_none(value: Any) -> str:
    if value is None:
        return "None"
    return f"{float(value):.6g}"


def _format_unwrap_status(unwrap_result: UnwrapResult) -> str:
    status = "ok" if unwrap_result.ok else "failed"
    details = []
    if unwrap_result.result is not None:
        details.append(f"result={unwrap_result.result}")
    if unwrap_result.fallback_used:
        details.append("fallback_used=True")
    if unwrap_result.error is not None:
        details.append(f"error={unwrap_result.error}")
    if not details:
        return status
    return f"{status} ({'; '.join(details)})"


def _set_object_mode(bpy: Any, active_object: Any, mode: str) -> None:
    if getattr(active_object, "mode", None) == mode:
        return
    bpy.context.view_layer.objects.active = active_object
    active_object.select_set(True)
    bpy.ops.object.mode_set(mode=mode)


def _restore_mode(bpy: Any, active_object: Any, mode: str) -> None:
    try:
        _set_object_mode(bpy, active_object, mode)
    except Exception as exc:  # pragma: no cover - Blender-only branch.
        print(f"Could not restore Blender mode {mode}: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
