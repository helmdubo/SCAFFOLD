"""
Layer: dev tooling

Rules:
- Runs inside Blender (--python). Writes Scaffold's result into a second UV
  layer next to the reference layer, so the two can be flipped in the UV editor.
- Never touches the opened .blend: the result is saved as a COPY to --out.
- Consumes scaffold_core like the debug add-on; defines no Scaffold relations.

Usage:
  blender -b reference.blend --python write_scaffold_layer.py -- \
      --objects Arc,collumn --straighten Arc,collumn --out result.blend

Per object: Pass 0, Pass 1, Pass 2 (Straighten Strips on for --straighten;
Straighten Bevel Strips on unless --no-bevel-strips),
the skeleton solve, pins written to a new UV layer "Scaffold", then Blender's
conformal unwrap fills the rest (pins are respected). The layer is scaled by
--scale (default 0.25, the reference's UV units per metre) so both layers have
the same density. Charts are packed in rows so the layer can be read; a patch
without pins comes out of the unwrap at an arbitrary scale and is rescaled to
its 3D area first. This is a viewing aid, not Scaffold packing.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import bpy  # noqa: E402 - executed by Blender only

from scaffold_core.layer_0_source.blender_io import read_source_mesh_from_blender  # noqa: E402
from scaffold_core.layer_4_features.model import FeatureOptions  # noqa: E402
from scaffold_core.layer_5_runtime.pins import run_skeleton_solve  # noqa: E402
from scaffold_core.layer_5_runtime.uv_transfer import write_pinned_uvs  # noqa: E402
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations, run_pass_2_features  # noqa: E402

LAYER_NAME = "Scaffold"


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--objects", required=True)
    parser.add_argument("--straighten", default="")
    parser.add_argument("--out", required=True)
    parser.add_argument("--scale", type=float, default=0.25)
    parser.add_argument("--no-unwrap", action="store_true")
    parser.add_argument("--no-bevel-strips", action="store_true", help="Pass 2 with straighten_bevel_strips off")
    args = parser.parse_args(argv)
    straighten = {name for name in args.straighten.split(",") if name}

    for name in [item for item in args.objects.split(",") if item]:
        obj = bpy.data.objects.get(name)
        if obj is None or obj.type != "MESH":
            print(f"LAYER {name} not a mesh object, skipped", flush=True)
            continue
        print("LAYER " + _write_object(obj, name in straighten, args), flush=True)

    bpy.ops.wm.save_as_mainfile(filepath=str(Path(args.out)), copy=True, check_existing=False)
    print(f"LAYER saved copy {args.out}", flush=True)
    return 0


def _write_object(obj, straighten_strips: bool, args) -> str:
    for other in bpy.context.view_layer.objects:
        other.select_set(False)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    if obj.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    source = read_source_mesh_from_blender(SimpleNamespace(object=obj))
    context = run_pass_1_relations(run_pass_0(source))
    context = run_pass_2_features(context, FeatureOptions(
        straighten_strips=straighten_strips, straighten_bevel_strips=not args.no_bevel_strips,
    ))
    solve = run_skeleton_solve(context)

    mesh = obj.data
    existing = mesh.uv_layers.get(LAYER_NAME)
    if existing is not None:
        mesh.uv_layers.remove(existing)
    layer = mesh.uv_layers.new(name=LAYER_NAME)
    mesh.uv_layers.active = layer
    summary = write_pinned_uvs(SimpleNamespace(object=obj), solve)

    unwrapped = "skipped"
    if not args.no_unwrap:
        try:
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.uv.select_all(action="SELECT")
            bpy.ops.uv.unwrap(method="CONFORMAL", fill_holes=False, margin=0.0)
            unwrapped = "conformal"
        except Exception as error:  # report, keep the pins
            unwrapped = f"failed: {error}"
        finally:
            if obj.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")

    layer = mesh.uv_layers[LAYER_NAME]
    free_charts = _lay_out_charts(mesh, layer, solve)
    for item in layer.data:
        item.uv = (item.uv[0] * args.scale, item.uv[1] * args.scale)
    pinned = sum(1 for item in layer.data if item.pin_uv)
    layouts = {}
    for skeleton in solve.skeletons:
        layouts[skeleton.frame] = layouts.get(skeleton.frame, 0) + 1
    return (
        f"{obj.name} strips={'on' if straighten_strips else 'off'} islands={len(solve.skeletons)} {layouts} "
        f"written_loops={summary['written_loops']} pinned_loops={pinned} of {len(layer.data)} "
        f"unwrap={unwrapped} charts_without_pins={free_charts} diagnostics={len(solve.diagnostics)}"
    )


def _lay_out_charts(mesh, layer, solve) -> int:
    """Make the layer readable: restore the density of charts without pins and pack all charts.

    A chart is one Scaffold island, except that a patch without any pinned
    corner is a chart of its own: Blender's unwrap leaves it at an arbitrary
    scale and place. Only whole charts move or scale; no structure changes.
    """

    patch_of_face = solve.patch_by_source_face
    island_of_patch = solve.assembly.island_by_patch_id
    loops_of_patch: dict[str, list[int]] = {}
    faces_of_patch: dict[str, list] = {}
    for polygon in mesh.polygons:
        patch_id = patch_of_face.get(f"f{polygon.index}")
        if patch_id is None:
            continue
        loops_of_patch.setdefault(patch_id, []).extend(polygon.loop_indices)
        faces_of_patch.setdefault(patch_id, []).append(polygon)

    charts: dict[str, list[int]] = {}
    free_charts = 0
    for patch_id, loop_indices in loops_of_patch.items():
        if any(layer.data[i].pin_uv for i in loop_indices):
            charts.setdefault(island_of_patch.get(patch_id, patch_id), []).extend(loop_indices)
            continue
        free_charts += 1
        area_3d = sum(polygon.area for polygon in faces_of_patch[patch_id])
        area_uv = sum(_uv_area(layer, polygon) for polygon in faces_of_patch[patch_id])
        if area_3d > 0.0 and area_uv > 0.0:
            factor = (area_3d / area_uv) ** 0.5
            for i in loop_indices:
                layer.data[i].uv = (layer.data[i].uv[0] * factor, layer.data[i].uv[1] * factor)
        charts[f"free:{patch_id}"] = list(loop_indices)

    boxes = []
    for key, loop_indices in charts.items():
        us = [layer.data[i].uv[0] for i in loop_indices]
        vs = [layer.data[i].uv[1] for i in loop_indices]
        boxes.append((max(vs) - min(vs), max(us) - min(us), min(us), min(vs), key))
    if not boxes:
        return free_charts
    total_area = sum(height * width for height, width, _u, _v, _key in boxes)
    row_limit = max(max(width for _h, width, _u, _v, _k in boxes), 1.3 * total_area ** 0.5)
    margin = 0.02 * row_limit
    cursor_u, cursor_v, row_height = 0.0, 0.0, 0.0
    for height, width, min_u, min_v, key in sorted(boxes, key=lambda box: (-box[0], box[4])):
        if cursor_u > 0.0 and cursor_u + width > row_limit:
            cursor_u, cursor_v, row_height = 0.0, cursor_v + row_height + margin, 0.0
        shift_u, shift_v = cursor_u - min_u, cursor_v - min_v
        for i in charts[key]:
            layer.data[i].uv = (layer.data[i].uv[0] + shift_u, layer.data[i].uv[1] + shift_v)
        cursor_u += width + margin
        row_height = max(row_height, height)
    return free_charts


def _uv_area(layer, polygon) -> float:
    points = [layer.data[i].uv for i in polygon.loop_indices]
    return abs(sum(
        points[k][0] * points[(k + 1) % len(points)][1] - points[(k + 1) % len(points)][0] * points[k][1]
        for k in range(len(points))
    )) / 2.0


if __name__ == "__main__":
    raise SystemExit(main())
