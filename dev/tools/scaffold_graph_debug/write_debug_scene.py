"""
Layer: dev tooling

Rules:
- Runs inside Blender (--python). Builds the structure-debugger overlay for
  named mesh objects and saves the scene as a COPY to --out; the opened .blend
  is never written.
- Consumes scaffold_core like the debug add-on (same payload, same drawing);
  defines no Scaffold relations.

Usage:
  blender -b scene.blend --python write_debug_scene.py -- \
      --objects Arc,collumn --straighten Arc --out debug.blend \
      [--render-dir pngs --render Arc,collumn --facade Main_wall --line-thickness 4]
      [--sets patches_chains,bevels_ladders,face_mark] [--no-bevel-strips]
      [--world-up 0,0,1 | --no-filter] [--angle 45]

Per object: Pass 0, 1, 2 (Straighten Strips on for --straighten; Straighten
Bevel Strips on unless --no-bevel-strips), Pass 3 (the user filter, on with
+Z like the panel's default; --world-up picks another up axis, --no-filter
turns it off), the skeleton solve, the overlay with the panel's default layer visibility and line
thickness 1.0, then the source mesh is hidden like Analyze does, so the saved
file opens on the overlay. After the copy is saved, --render writes Workbench
PNGs of layer sets per named object from an oblique view (by default three:
patches_chains, islands_lines_seams, types; --sets picks others, e.g.
bevels_ladders, face_mark), and --facade
one Patches+Chains PNG per named object looking at its longest side. Renders
use --line-thickness (the panel's Line thickness multiplier); the saved file
keeps 1.0.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_ROOT = REPO_ROOT / "dev" / "tools"
for _path in (REPO_ROOT, TOOLS_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import bpy  # noqa: E402 - executed by Blender only
from mathutils import Vector  # noqa: E402

from scaffold_graph_debug.debug import overlay_object_name  # noqa: E402
from scaffold_graph_debug.draw_v2 import (  # noqa: E402
    apply_layer_visibility,
    apply_line_thickness,
    render_debug_overlay,
)
from scaffold_graph_debug.overlay_v2 import LAYER_SPECS  # noqa: E402
from scaffold_graph_debug.session import build_payload, object_space_up, write_report_text  # noqa: E402

RENDER_SETS = {
    "patches_chains": ("Scaffold_Patches", "Scaffold_Chains"),
    "islands_lines_seams": (
        "Scaffold_Islands_UNFOLDED",
        "Scaffold_Islands_FRAME_FREE",
        "Scaffold_Islands_STRIP",
        "Scaffold_Islands_LADDER",
        "Scaffold_Skeleton_Lines",
        "Scaffold_Seams",
    ),
    "types": (
        "Scaffold_Types_Strip",
        "Scaffold_Types_StripOff",
        "Scaffold_Types_Rectangle",
        "Scaffold_Types_FourSided",
        "Scaffold_Types_Other",
        "Scaffold_Loops_Boundary",
    ),
    "bevels_ladders": (
        "Scaffold_Bevel_Strip",
        "Scaffold_Bevel_Junction",
        "Scaffold_Bevel_Strip_Structure",
        "Scaffold_Bevel_Junction_Structure",
        "Scaffold_Bevel_Not_Isolated",
        "Scaffold_Ladder_Rails",
        "Scaffold_Ladder_Ends",
        "Scaffold_Ladder_Columns",
    ),
    "face_mark": ("Scaffold_Source_Face_Strength", "Scaffold_Loops_Boundary"),
}
DEFAULT_RENDER_SETS = ("patches_chains", "islands_lines_seams", "types")
OBLIQUE_VIEW = Vector((1.0, -1.3, 0.8))


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--objects", required=True)
    parser.add_argument("--straighten", default="")
    parser.add_argument("--out", required=True)
    parser.add_argument("--render-dir", default="")
    parser.add_argument("--render", default="")
    parser.add_argument("--facade", default="")
    parser.add_argument("--line-thickness", type=float, default=1.0)
    parser.add_argument("--width", type=int, default=1200)
    parser.add_argument("--sets", default=",".join(DEFAULT_RENDER_SETS))
    parser.add_argument("--no-bevel-strips", action="store_true", help="Pass 2 with straighten_bevel_strips off")
    parser.add_argument(
        "--world-up", default="0,0,1",
        help="Pass 3 user filter up axis in world space (the panel's default +Z), turned into each object's "
        "space by its matrix_world; a non-uniform object scale is not handled",
    )
    parser.add_argument("--no-filter", action="store_true", help="Pass 3 without the user filter")
    parser.add_argument("--angle", type=float, default=45.0, help="Pass 3 horizontal angle in degrees")
    args = parser.parse_args(argv)
    world_up = None if args.no_filter else tuple(float(value) for value in args.world_up.split(","))
    straighten = {name for name in args.straighten.split(",") if name}
    default_visibility = {spec.layer: spec.default for spec in LAYER_SPECS}

    built = []
    for name in [item for item in args.objects.split(",") if item]:
        obj = bpy.data.objects.get(name)
        if obj is None or obj.type != "MESH":
            print(f"DEBUG {name} not a mesh object, skipped", flush=True)
            continue
        if obj.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        payload = build_payload(
            SimpleNamespace(object=obj), straighten_strips=name in straighten, object_name=name, capture=False,
            straighten_bevel_strips=not args.no_bevel_strips,
            world_up=object_space_up(obj, world_up), horizontal_angle_degrees=args.angle,
        )
        counts = render_debug_overlay(obj, payload, default_visibility, show_labels=False)
        write_report_text(name, payload["report"])
        obj.hide_set(True)
        built.append(name)
        print(f"DEBUG {name} strips={'on' if name in straighten else 'off'}", flush=True)
        for spec in LAYER_SPECS:
            print(f"DEBUG   {spec.layer}: {counts.get(spec.layer, 0)}", flush=True)
        print("\n".join("DEBUG   | " + line for line in payload["report"].splitlines()), flush=True)

    bpy.ops.wm.save_as_mainfile(filepath=str(Path(args.out)), copy=True, check_existing=False)
    print(f"DEBUG saved copy {args.out}", flush=True)

    jobs = [
        (name, set_name, layers, None)
        for name in args.render.split(",")
        if name in built
        for set_name, layers in RENDER_SETS.items()
        if set_name in args.sets.split(",")
    ] + [
        (name, "facade_patches_chains", RENDER_SETS["patches_chains"], "facade")
        for name in args.facade.split(",")
        if name in built
    ]
    if args.render_dir and jobs:
        _render(jobs, Path(args.render_dir), args.width, args.line_thickness)
    return 0


def _render(jobs, out_dir: Path, width: int, line_thickness: float) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = width
    scene.render.resolution_y = int(width * 0.75)
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.display.shading.light = "FLAT"
    scene.display.shading.color_type = "MATERIAL"
    scene.view_settings.view_transform = "Standard"
    if scene.world is None:
        scene.world = bpy.data.worlds.new("ScaffoldDebugWorld")
    scene.world.color = (0.08, 0.08, 0.09)
    camera_data = bpy.data.cameras.new("ScaffoldDebugCamera")
    camera_data.type = "ORTHO"
    camera = bpy.data.objects.new("ScaffoldDebugCamera", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    for name, set_name, layers, view in jobs:
        source = bpy.data.objects[name]
        overlay_name = overlay_object_name(name)
        for obj in scene.objects:
            obj.hide_render = obj.name != overlay_name and obj is not camera
        if view == "facade":
            _aim_camera(camera, source, _facade_view(source), frame_factor=2.0)
        else:
            _aim_camera(camera, source, OBLIQUE_VIEW)
        apply_line_thickness(name, line_thickness)
        visibility = {spec.layer: spec.layer in layers for spec in LAYER_SPECS}
        apply_layer_visibility(name, visibility, show_labels=False)
        scene.render.filepath = str(out_dir / f"{name}_{set_name}.png")
        bpy.ops.render.render(write_still=True)
        print(f"DEBUG render {scene.render.filepath} (line thickness {line_thickness})", flush=True)


def _facade_view(source) -> Vector:
    """Look at the longest horizontal side of the bounding box, a little from above and the side."""

    dimensions = source.dimensions
    if dimensions.x >= dimensions.y:
        return Vector((0.3, -1.0, 0.25))
    return Vector((1.0, -0.3, 0.25))


def _aim_camera(camera, source, view: Vector, *, frame_factor: float = 2.9) -> None:
    corners = [source.matrix_world @ Vector(corner) for corner in source.bound_box]
    center = sum(corners, Vector()) / len(corners)
    extent = max((corner - center).length for corner in corners)
    direction = view.normalized()
    camera.location = center + direction * extent * 4.0
    camera.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
    camera.data.ortho_scale = extent * frame_factor  # the frame is 4:3, the scale spans its width
    camera.data.clip_end = extent * 10.0


if __name__ == "__main__":
    raise SystemExit(main())
