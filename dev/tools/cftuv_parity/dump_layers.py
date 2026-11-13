"""Dump the UV polygons and pin flags of every UV layer of named objects, read-only.

Run inside Blender; the scene is never saved:

    blender -b result.blend --python dev/tools/cftuv_parity/dump_layers.py -- \
        OUT.json Arc building_walls collumn Main_wall

Writes one compact JSON for render_layers.py:

    {"format": "cftuv_parity_layers_v1", "blend": path,
     "objects": {name: {"faces": [[vertex_index, ...], ...],
                        "layers": {layer_name: [[u0, v0, pin0, u1, v1, pin1, ...], ...]}}}}

Faces are in Blender polygon order; each layer face lists its corners in the
same order as "faces". UVs are rounded to 6 digits; pin is 0 or 1.
"""

import json
import sys

import bpy


def dump_object(obj) -> dict:
    mesh = obj.data
    loop_vertex = [0] * len(mesh.loops)
    mesh.loops.foreach_get("vertex_index", loop_vertex)
    polygons = [(poly.loop_start, poly.loop_total) for poly in mesh.polygons]
    layers = {}
    for layer in mesh.uv_layers:
        uv = [0.0] * (2 * len(mesh.loops))
        layer.uv.foreach_get("vector", uv)
        pin = [False] * len(mesh.loops)
        if len(layer.pin):
            layer.pin.foreach_get("value", pin)
        faces = []
        for start, total in polygons:
            corners = []
            for loop in range(start, start + total):
                corners += [round(uv[2 * loop], 6), round(uv[2 * loop + 1], 6), 1 if pin[loop] else 0]
            faces.append(corners)
        layers[layer.name] = faces
    return {
        "faces": [loop_vertex[start:start + total] for start, total in polygons],
        "layers": layers,
    }


def main() -> None:
    args = sys.argv[sys.argv.index("--") + 1:]
    out = {"format": "cftuv_parity_layers_v1", "blend": bpy.data.filepath, "objects": {}}
    for name in args[1:]:
        obj = bpy.data.objects.get(name)
        if obj is None or obj.type != "MESH":
            print(f"DUMP {name}: not a mesh object, skipped")
            continue
        out["objects"][name] = dump_object(obj)
        data = out["objects"][name]
        pinned = {layer: sum(face[2::3].count(1) for face in faces) for layer, faces in data["layers"].items()}
        print(f"DUMP {name}: faces={len(data['faces'])} pinned corners per layer={pinned}")
    with open(args[0], "w") as handle:
        json.dump(out, handle, separators=(",", ":"))


main()
