"""Extract reference UVs (and CFTUV pin flags) from a Blender scene, read-only.

Run inside Blender; the scene is never saved:

    blender -b reference_scene.blend --python dev/tools/cftuv_parity/extract_reference.py -- \
        OUT_DIR Arc building_walls collumn Main_wall

Writes OUT_DIR/<object>.uv.json per object (compact JSON):

    {"format": "cftuv_parity_reference_v1", "object": name, "uv_layer": name,
     "faces": {"f12": [[vertex_index, u, v, pinned], ...corners in face order]},
     "islands": [["f0", "f1", ...], ...]}

Indices are Blender's own, the same as SourceMeshSnapshot ids ("f12", "v5").
Reference islands are connected components of faces whose shared edge has
coinciding UVs (both end points within UV_MATCH_EPS) on both faces.
"""

import json
import sys
from pathlib import Path

import bpy

UV_MATCH_EPS = 1e-5


def extract(obj) -> dict:
    mesh = obj.data
    layer = mesh.uv_layers.active
    uv = layer.uv
    pin = layer.pin
    faces = {}
    corner_uv = {}  # (face index, vertex index) -> (u, v)
    for poly in mesh.polygons:
        corners = []
        for loop_index in poly.loop_indices:
            vertex = mesh.loops[loop_index].vertex_index
            u, v = uv[loop_index].vector
            pinned = bool(pin[loop_index].value) if len(pin) else False
            corners.append([vertex, round(u, 7), round(v, 7), 1 if pinned else 0])
            corner_uv[(poly.index, vertex)] = (u, v)
        faces[f"f{poly.index}"] = corners
    faces_of_edge = {}
    for poly in mesh.polygons:
        for key in poly.edge_keys:
            faces_of_edge.setdefault(key, []).append(poly.index)
    parent = {poly.index: poly.index for poly in mesh.polygons}

    def find(item):
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    for (a, b), polys in faces_of_edge.items():
        if len(polys) != 2:
            continue
        f, g = polys
        same = all(
            abs(corner_uv[(f, vertex)][axis] - corner_uv[(g, vertex)][axis]) <= UV_MATCH_EPS
            for vertex in (a, b)
            for axis in (0, 1)
        )
        if same:
            parent[find(f)] = find(g)
    groups = {}
    for poly in mesh.polygons:
        groups.setdefault(find(poly.index), []).append(f"f{poly.index}")
    return {
        "format": "cftuv_parity_reference_v1",
        "object": obj.name,
        "uv_layer": layer.name,
        "faces": faces,
        "islands": sorted(groups.values(), key=lambda group: int(group[0][1:])),
    }


def main() -> None:
    args = sys.argv[sys.argv.index("--") + 1:]
    out_dir = Path(args[0])
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in args[1:]:
        data = extract(bpy.data.objects[name])
        pinned = sum(corner[3] for corners in data["faces"].values() for corner in corners)
        (out_dir / f"{name}.uv.json").write_text(json.dumps(data, separators=(",", ":")))
        print(f"{name}: faces={len(data['faces'])} islands={len(data['islands'])} pinned_loops={pinned}")


main()
