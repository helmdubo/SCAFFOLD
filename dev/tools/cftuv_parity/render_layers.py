"""Draw the reference UV layer and the Scaffold UV layer side by side, per object.

Pure Python with Pillow (no Blender). Input is the JSON of dump_layers.py:

    python dev/tools/cftuv_parity/render_layers.py LAYERS.json --out-dir DIR \
        [--panel 900] [--left UVMap] [--right Scaffold] [--object NAME ...]

Writes DIR/<object>.png: left panel = reference layer, right panel = Scaffold
layer. Each panel fits its own content with one scale for u and v (no
distortion). Faces are filled light and outlined thin; pinned corners are red.
For an object whose Scaffold layer has more than --many-charts UV charts
(faces connected by edges with coinciding UVs), DIR/<object>.charts.png also
shows the --top-charts largest charts of that layer (by UV area) in a grid,
each fitted to its own cell, so damage inside big islands can be seen.
A viewing aid only: it reads UVs and defines no Scaffold relation.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover - depends on the environment
    Image = ImageDraw = None

UV_MATCH_EPS = 1e-5
TITLE_HEIGHT = 24
MARGIN = 16
FILL = (226, 233, 242)
OUTLINE = (120, 130, 148)
PIN = (215, 40, 40)
TEXT = (20, 20, 20)
BACKGROUND = (255, 255, 255)
GRID_COLUMNS = 3


def corners_of(face):
    """[(u, v, pinned)] of a dumped layer face (flat u, v, pin triples)."""

    return [(face[i], face[i + 1], face[i + 2]) for i in range(0, len(face), 3)]


def uv_area(corners) -> float:
    return abs(sum(
        corners[k][0] * corners[(k + 1) % len(corners)][1] - corners[(k + 1) % len(corners)][0] * corners[k][1]
        for k in range(len(corners))
    )) / 2.0


def uv_charts(vertex_faces, layer_faces):
    """Face index lists of the layer's UV charts, largest UV area first (ties by first face)."""

    parent = list(range(len(layer_faces)))

    def find(item):
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    seen = {}
    for index, (vertices, face) in enumerate(zip(vertex_faces, layer_faces)):
        corners = corners_of(face)
        for k, vertex in enumerate(vertices):
            nxt = (k + 1) % len(vertices)
            edge = (min(vertex, vertices[nxt]), max(vertex, vertices[nxt]))
            uv = {vertex: corners[k][:2], vertices[nxt]: corners[nxt][:2]}
            other = seen.get(edge)
            if other is None:
                seen[edge] = (index, uv)
                continue
            other_index, other_uv = other
            if all(math.dist(uv[v], other_uv[v]) <= UV_MATCH_EPS for v in edge):
                parent[find(index)] = find(other_index)
    groups = {}
    for index in range(len(layer_faces)):
        groups.setdefault(find(index), []).append(index)
    area = {root: sum(uv_area(corners_of(layer_faces[i])) for i in faces) for root, faces in groups.items()}
    return [groups[root] for root in sorted(groups, key=lambda root: (-area[root], groups[root][0]))], area


def draw_panel(draw, faces, box, title):
    """Draw faces (lists of (u, v, pin)) fitted into box = (x, y, width, height) under a title line."""

    x0, y0, width, height = box
    pinned = sum(1 for face in faces for _u, _v, pin in face if pin)
    draw.text((x0 + MARGIN, y0 + 6), f"{title}   pinned corners {pinned}", fill=TEXT)
    points = [(u, v) for face in faces for u, v, _pin in face]
    if not points:
        return
    min_u, max_u = min(p[0] for p in points), max(p[0] for p in points)
    min_v, max_v = min(p[1] for p in points), max(p[1] for p in points)
    inner_w, inner_h = width - 2 * MARGIN, height - TITLE_HEIGHT - 2 * MARGIN
    span_u, span_v = max(max_u - min_u, 1e-12), max(max_v - min_v, 1e-12)
    scale = min(inner_w / span_u, inner_h / span_v)
    left = x0 + MARGIN + (inner_w - span_u * scale) / 2
    bottom = y0 + TITLE_HEIGHT + MARGIN + inner_h - (inner_h - span_v * scale) / 2

    def to_px(u, v):
        return (left + (u - min_u) * scale, bottom - (v - min_v) * scale)

    for face in faces:
        polygon = [to_px(u, v) for u, v, _pin in face]
        if len(polygon) >= 3:
            draw.polygon(polygon, fill=FILL, outline=OUTLINE)
    radius = max(1.5, min(width, height) / 400)
    for face in faces:
        for u, v, pin in face:
            if pin:
                x, y = to_px(u, v)
                draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=PIN)


def render_object(name, data, left, right, panel, out_dir, many_charts, top_charts):
    written = []
    image = Image.new("RGB", (2 * panel, panel), BACKGROUND)
    draw = ImageDraw.Draw(image)
    for column, layer in enumerate((left, right)):
        faces = [corners_of(face) for face in data["layers"].get(layer, [])]
        label = f"{name}  {layer}" if layer in data["layers"] else f"{name}  {layer} (missing)"
        draw_panel(draw, faces, (column * panel, 0, panel, panel), label)
    draw.line((panel, 0, panel, panel), fill=(170, 170, 170))
    path = out_dir / f"{name}.png"
    image.save(path)
    written.append(path)

    layer_faces = data["layers"].get(right)
    if not layer_faces:
        return written
    charts, area = uv_charts(data["faces"], layer_faces)
    if len(charts) <= many_charts:
        return written
    chosen = charts[:top_charts]
    rows = math.ceil(len(chosen) / GRID_COLUMNS)
    cell = (2 * panel) // GRID_COLUMNS
    image = Image.new("RGB", (GRID_COLUMNS * cell, rows * cell + TITLE_HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.text((MARGIN, 6), f"{name}  {right}: the {len(chosen)} largest of {len(charts)} UV charts", fill=TEXT)
    for rank, faces in enumerate(chosen):
        box = ((rank % GRID_COLUMNS) * cell, TITLE_HEIGHT + (rank // GRID_COLUMNS) * cell, cell, cell)
        title = f"#{rank + 1}: {len(faces)} faces, first f{faces[0]}"
        draw_panel(draw, [corners_of(layer_faces[i]) for i in faces], box, title)
        draw.rectangle((box[0], box[1], box[0] + cell - 1, box[1] + cell - 1), outline=(190, 190, 190))
    path = out_dir / f"{name}.charts.png"
    image.save(path)
    written.append(path)
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Render reference and Scaffold UV layers side by side")
    parser.add_argument("dump", help="JSON written by dump_layers.py")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--panel", type=int, default=900, help="panel size in pixels")
    parser.add_argument("--left", default="UVMap", help="reference UV layer")
    parser.add_argument("--right", default="Scaffold", help="Scaffold UV layer")
    parser.add_argument("--object", action="append", help="only these objects")
    parser.add_argument("--many-charts", type=int, default=30)
    parser.add_argument("--top-charts", type=int, default=6)
    args = parser.parse_args(argv)
    if Image is None:
        print("render_layers.py needs Pillow: python -m pip install Pillow", file=sys.stderr)
        return 1
    dump = json.loads(Path(args.dump).read_text())
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, data in dump["objects"].items():
        if args.object and name not in args.object:
            continue
        for path in render_object(name, data, args.left, args.right, args.panel, out_dir,
                                  args.many_charts, args.top_charts):
            print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
