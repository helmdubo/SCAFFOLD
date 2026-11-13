"""
Layer: dev tooling

Rules:
- Builds the bevel test meshes of scaffold_core/tests/data/bevel_cases/ inside
  Blender (blender -b --python build_bevel_cases.py -- OUT_DIR [case ...]).
- Ground truth comes from Blender's own Face Strength attribute written by a
  Bevel modifier with Face Strength = All; seams follow the ground truth.
- Each mesh is read through the core mesh-read boundary
  (scaffold_core/layer_0_source/blender_io.py) and dumped with the debug
  add-on's capture writer, so the captures carry the face strength mark.
- Consumes scaffold_core like the smoke runner; defines no Scaffold relation.
  Never saves a .blend.
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import random
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import bmesh  # noqa: E402 - executed by Blender only
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from scaffold_core.layer_0_source.blender_io import read_source_mesh_from_blender  # noqa: E402
from scaffold_core.layer_0_source.marks import FACE_STRENGTH_ATTRIBUTE  # noqa: E402

SNAPSHOT_IO_PATH = REPO_ROOT / "dev" / "tools" / "scaffold_graph_debug" / "snapshot_io.py"
WEAK, MEDIUM = -16384, 0
CLASS_NAMES = {0: "OTHER", 1: "STRIP", 2: "JUNCTION"}


# ------------------------------------------------------------------ base meshes


class Base:
    def __init__(self):
        self.bm = bmesh.new()
        self.bev = []  # (vertex, vertex) pairs to bevel
        self.cut = set()  # vertices at which strip runs are cut into separate patches
        self.vcache = {}
        self.keep = self.bm.faces.layers.int.new("keepq")  # faces kept as quads by tri_main

    def v(self, key, co):
        if key not in self.vcache:
            self.vcache[key] = self.bm.verts.new(co)
        return self.vcache[key]

    def f(self, vertices, keep=0):
        face = self.bm.faces.new(vertices)
        if keep:
            face[self.keep] = 1
        return face


def wall(hole2d, center, depth=0.3, scale=2.2):
    """Wall slab in XZ with a hole polygon; front y=0, back y=depth; the front hole rim is bevelled."""

    b = Base()
    n = len(hole2d)
    cx, cz = center
    outer2d = [(cx + (x - cx) * scale, cz + (z - cz) * scale) for x, z in hole2d]
    hf = [b.v(("hf", i), (x, 0.0, z)) for i, (x, z) in enumerate(hole2d)]
    hb = [b.v(("hb", i), (x, depth, z)) for i, (x, z) in enumerate(hole2d)]
    of = [b.v(("of", i), (x, 0.0, z)) for i, (x, z) in enumerate(outer2d)]
    ob = [b.v(("ob", i), (x, depth, z)) for i, (x, z) in enumerate(outer2d)]
    for i in range(n):
        j = (i + 1) % n
        b.f([of[i], of[j], hf[j], hf[i]])
        b.f([ob[j], ob[i], hb[i], hb[j]])
        b.f([hf[i], hf[j], hb[j], hb[i]], keep=1)
        b.f([of[j], of[i], ob[i], ob[j]])
    b.bev = [(hf[i], hf[(i + 1) % n]) for i in range(n)]
    return b, hf


def rect_window():
    b, hf = wall([(-0.5, 0.3), (0.5, 0.3), (0.5, 1.7), (-0.5, 1.7)], (0.0, 1.0))
    b.cut = set(hf)
    return b


def rect_window_ring():
    b = rect_window()
    b.cut = set()
    return b


def arch_window(arc_segments=8):
    r, zs = 0.5, 1.2
    hole = [(-0.5, 0.3), (0.5, 0.3)]
    for k in range(arc_segments + 1):
        a = math.pi * k / arc_segments
        hole.append((r * math.cos(a), zs + r * math.sin(a)))
    b, hf = wall(hole, (0.0, 0.95))
    b.cut = {hf[0], hf[1], hf[2], hf[2 + arc_segments]}
    return b


def cube():
    b = Base()
    bmesh.ops.create_cube(b.bm, size=1.0)
    b.bev = [tuple(e.verts) for e in b.bm.edges]
    return b


def cylinder(N=16, M=4, R=1.0, r=0.85, dz=0.3, hole_i=(0, 2), hole_j=(1, 3)):
    """Thick tube: outer and inner walls, top and bottom rims; a rectangular hole through the wall.

    The outer top rim and the hole's outer rim are bevelled (the top rim ring and the hole ring).
    """

    b = Base()

    def P(rad, i, j):
        a = 2 * math.pi * (i % N) / N
        return (rad * math.cos(a), rad * math.sin(a), j * dz)

    def hole(i, j):
        return hole_i[0] <= i < hole_i[1] and hole_j[0] <= j < hole_j[1]

    O = lambda i, j: b.v(("O", i % N, j), P(R, i, j))  # noqa: E731
    I = lambda i, j: b.v(("I", i % N, j), P(r, i, j))  # noqa: E731
    for i in range(N):
        for j in range(M):
            if hole(i, j):
                continue
            b.f([O(i, j), O(i + 1, j), O(i + 1, j + 1), O(i, j + 1)])
            b.f([I(i, j + 1), I(i + 1, j + 1), I(i + 1, j), I(i, j)])
    for i in range(N):
        b.f([O(i + 1, M), O(i, M), I(i, M), I(i + 1, M)])
        b.f([O(i, 0), O(i + 1, 0), I(i + 1, 0), I(i, 0)])
    i0, i1 = hole_i
    j0, j1 = hole_j
    rim = []
    for i in range(i0, i1):
        rim.append((i, j0, i + 1, j0))
        rim.append((i + 1, j1, i, j1))
    for j in range(j0, j1):
        rim.append((i1, j, i1, j + 1))
        rim.append((i0, j + 1, i0, j))
    for ia, ja, ib, jb in rim:
        b.f([O(ia, ja), O(ib, jb), I(ib, jb), I(ia, ja)], keep=1)
        b.bev.append((O(ia, ja), O(ib, jb)))
    for i in range(N):
        b.bev.append((O(i, M), O(i + 1, M)))
    b.cut = {O(i0, j0), O(i1, j0), O(i1, j1), O(i0, j1)}
    return b


def lsheet(beveled=3):
    """Open L: plane A (z=0) and plane B (x=0) sharing the fold x=z=0; the fold is bevelled to the mesh border."""

    b = Base()
    ys = [0.0, 0.5, 1.0, 1.5]
    xs = [0.0, 0.5, 1.0]
    A = lambda i, k: b.v(("A", i, k), (xs[i], ys[k], 0.0)) if i else b.v(("F", k), (0.0, ys[k], 0.0))  # noqa: E731
    B = lambda i, k: b.v(("B", i, k), (0.0, ys[k], xs[i])) if i else b.v(("F", k), (0.0, ys[k], 0.0))  # noqa: E731
    for i in range(2):
        for k in range(3):
            b.f([A(i, k), A(i + 1, k), A(i + 1, k + 1), A(i, k + 1)])
            b.f([B(i, k + 1), B(i + 1, k + 1), B(i + 1, k), B(i, k)])
    b.bev = [(A(0, k), A(0, k + 1)) for k in range(beveled)]
    return b


def short_prism():
    """A prism with one very short side: its bevel strip is one short quad between two junctions."""

    b = Base()
    pts = [(0, 0), (1, 0), (1, 1), (0.05, 1), (0, 0.95)]
    bot = [b.v(("b", i), (x, y, 0.0)) for i, (x, y) in enumerate(pts)]
    top = [b.v(("t", i), (x, y, 0.6)) for i, (x, y) in enumerate(pts)]
    n = len(pts)
    b.f(list(reversed(bot)))
    b.f(top)
    for i in range(n):
        j = (i + 1) % n
        b.f([bot[i], bot[j], top[j], top[i]])
    b.bev = [tuple(e.verts) for e in b.bm.edges]
    return b


# ------------------------------------------------------------------ bevel, ground truth, capture


def _segment_distance(p, a, b):
    t = (p - a).dot(b - a) / max((b - a).length_squared, 1e-20)
    t = max(0.0, min(1.0, t))
    return (a + (b - a) * t - p).length


def build(out_dir: Path, name, base, width, segments, miter_outer="MITER_SHARP", miter_inner="MITER_SHARP",
          noise=0.0, triangulate=False, tri_main=False, seed=1):
    bm = base.bm
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    weight = bm.edges.layers.float.new("bevel_weight_edge")
    bevelled = {frozenset(pair) for pair in base.bev}
    for edge in bm.edges:
        edge[weight] = 1.0 if frozenset(edge.verts) in bevelled else 0.0
    orig_edges = [(e.index, e.verts[0].co.copy(), e.verts[1].co.copy(), e.verts[0].index, e.verts[1].index)
                  for e in bm.edges if e[weight] > 0]
    bevel_vertices = {v.index for e in bm.edges if e[weight] > 0 for v in e.verts}
    orig_vertices = {v.index: v.co.copy() for v in bm.verts if v.index in bevel_vertices}
    cut = {v.index for v in base.cut}
    mesh = bpy.data.meshes.new(name + "_src")
    bm.to_mesh(mesh)
    obj = bpy.data.objects.new(name + "_src", mesh)
    bpy.context.scene.collection.objects.link(obj)
    modifier = obj.modifiers.new("Bevel", "BEVEL")
    modifier.limit_method = "WEIGHT"
    modifier.width = width
    modifier.segments = segments
    modifier.face_strength_mode = "FSTR_ALL"
    modifier.miter_outer = miter_outer
    modifier.miter_inner = miter_inner
    modifier.harden_normals = False
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph))
    strength = [item.value for item in evaluated.attributes[FACE_STRENGTH_ATTRIBUTE].data]
    keep = [item.value for item in evaluated.attributes["keepq"].data]
    bm2 = bmesh.new()
    bm2.from_mesh(evaluated)
    cls = {f.index: 1 if strength[f.index] == MEDIUM else 2 if strength[f.index] == WEAK else 0 for f in bm2.faces}
    orig = {}
    for face in bm2.faces:
        center = face.calc_center_median()
        if cls[face.index] == 1:
            orig[face.index] = min((_segment_distance(center, a, b), i) for i, a, b, _, _ in orig_edges)[1]
        elif cls[face.index] == 2:
            orig[face.index] = min(((center - co).length, i) for i, co in orig_vertices.items())[1]
    edge_ends = {i: (va, vb) for i, _, _, va, vb in orig_edges}
    junction_vertices = {orig[i] for i in orig if cls[i] == 2}
    parent = {i: i for i in orig if cls[i] == 1}

    def find(item):
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    for edge in bm2.edges:
        faces = edge.link_faces
        if len(faces) != 2 or cls[faces[0].index] != 1 or cls[faces[1].index] != 1:
            continue
        a, b = orig[faces[0].index], orig[faces[1].index]
        join = a == b
        if not join:
            common = set(edge_ends[a]) & set(edge_ends[b])
            join = bool(common) and all(v not in cut and v not in junction_vertices for v in common)
        if join:
            parent[find(faces[0].index)] = find(faces[1].index)
    component = {i: (f"S{find(i)}" if cls[i] == 1 else f"J{orig[i]}") for i in orig}
    for edge in bm2.edges:
        faces = edge.link_faces
        edge.seam = False
        if len(faces) != 2:
            continue
        a, b = faces[0].index, faces[1].index
        if (cls[a] == 0) != (cls[b] == 0):
            edge.seam = True
        elif cls[a] and cls[b]:
            edge.seam = component[a] != component[b]
        else:
            edge.seam = faces[0].normal.angle(faces[1].normal, 0.0) > math.radians(30)
    layer_cls = bm2.faces.layers.int.new("gt_cls")
    layer_orig = bm2.faces.layers.int.new("gt_orig")
    layer_comp = bm2.faces.layers.int.new("gt_comp")
    layer_keep = bm2.faces.layers.int.new("gt_keep")
    component_ids = {}
    for face in bm2.faces:
        face[layer_cls] = cls[face.index]
        face[layer_orig] = orig.get(face.index, -1)
        face[layer_keep] = keep[face.index]
        face[layer_comp] = component_ids.setdefault(component.get(face.index, "O"), len(component_ids))
    component_names = {value: key for key, value in component_ids.items()}
    if noise > 0:
        rnd = random.Random(seed)
        for vertex in bm2.verts:
            direction = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized()
            vertex.co += direction * noise * width * rnd.uniform(0.5, 1.0)
    if tri_main:
        bmesh.ops.triangulate(bm2, faces=[f for f in bm2.faces if f[layer_cls] == 0 and not f[layer_keep]])
    if triangulate:
        bmesh.ops.triangulate(bm2, faces=bm2.faces[:])
    bm2.verts.index_update()
    bm2.edges.index_update()
    bm2.faces.index_update()
    truth = {
        f"f{face.index}": [CLASS_NAMES[face[layer_cls]], component_names[face[layer_comp]] if face[layer_cls] else "O",
                           face[layer_orig]]
        for face in bm2.faces
    }
    result = bpy.data.meshes.new(name)
    bm2.to_mesh(result)
    bm2.free()
    target = bpy.data.objects.new(name, result)
    bpy.context.scene.collection.objects.link(target)
    source = read_source_mesh_from_blender(SimpleNamespace(object=target))
    capture = out_dir / f"{name}.capture.json"
    _snapshot_io().dump_source_snapshot(source, capture)
    capture.write_text(json.dumps(json.loads(capture.read_text(encoding="utf-8")), separators=(",", ":")),
                       encoding="utf-8")
    ground_truth = {
        "case": name, "width": width, "segments": segments, "miter_outer": miter_outer,
        "miter_inner": miter_inner, "noise": noise, "triangulated": triangulate, "tri_main": tri_main,
        "faces": truth,
    }
    (out_dir / f"{name}.gt.json").write_text(json.dumps(ground_truth, separators=(",", ":")), encoding="utf-8")
    marks = {}
    for face in source.faces.values():
        key = face.face_strength.value if face.face_strength is not None else "NONE"
        marks[key] = marks.get(key, 0) + 1
    print(f"CASE {name:20s} faces={len(source.faces):4d} seams={len(source.marks):4d} face_strength={marks}")
    bpy.data.objects.remove(obj)
    bpy.data.objects.remove(target)


def _snapshot_io():
    spec = importlib.util.spec_from_file_location("scaffold_snapshot_io", SNAPSHOT_IO_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CASES = {
    "a_cube_s1": lambda out: build(out, "a_cube_s1", cube(), 0.1, 1),
    "a_cube_s3": lambda out: build(out, "a_cube_s3", cube(), 0.1, 3),
    "b_rect_s2": lambda out: build(out, "b_rect_s2", rect_window(), 0.05, 2),
    "b_ring_s1": lambda out: build(out, "b_ring_s1", rect_window_ring(), 0.05, 1),
    "c_arch_s2": lambda out: build(out, "c_arch_s2", arch_window(), 0.05, 2),
    "d_cyl_s2": lambda out: build(out, "d_cyl_s2", cylinder(), 0.04, 2),
    "e_arch_s2_n20": lambda out: build(out, "e_arch_s2_n20", arch_window(), 0.05, 2, noise=0.20),
    "f_rect_inarc": lambda out: build(out, "f_rect_inarc", rect_window(), 0.05, 2, miter_inner="MITER_ARC"),
    "f_border": lambda out: build(out, "f_border", lsheet(3), 0.08, 2),
    "g_short": lambda out: build(out, "g_short", short_prism(), 0.1, 1),
    "h_rect_s2_tri": lambda out: build(out, "h_rect_s2_tri", rect_window(), 0.05, 2, triangulate=True),
    "m_rect_s2_trimain": lambda out: build(out, "m_rect_s2_trimain", rect_window(), 0.05, 2, tri_main=True),
}


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out_dir = Path(argv[0])
    os.makedirs(out_dir, exist_ok=True)
    for key in argv[1:] or list(CASES):
        CASES[key](out_dir)
