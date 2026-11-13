"""
Layer: tests fixtures

Rules:
- Small synthetic meshes for the Layer 4 bevel rule: an extruded corner
  profile with one bevel strip (convex or concave, marked or not, with or
  without seams), flat patch layouts and a capped prism for the structural
  rule edges.
- Seams are given as vertex pairs; Face Strength marks per face index.
- No production logic here.
"""

from __future__ import annotations

import math

from scaffold_core.ids import SourceEdgeId, SourceFaceId, SourceMeshId, SourceVertexId
from scaffold_core.layer_0_source.marks import SourceFaceStrength, SourceMark, SourceMarkKind
from scaffold_core.layer_0_source.snapshot import (
    MeshEdgeRef,
    MeshFaceRef,
    MeshVertexRef,
    SourceMeshSnapshot,
)

MEDIUM = SourceFaceStrength.MEDIUM
WEAK = SourceFaceStrength.WEAK
STRONG = SourceFaceStrength.STRONG


def _mesh(
    name: str,
    positions: dict[str, tuple[float, float, float]],
    faces: list[tuple[str, ...]],
    seams: tuple[tuple[str, str], ...] = (),
    strengths: dict[int, SourceFaceStrength] | None = None,
) -> SourceMeshSnapshot:
    used = {vertex for cycle in faces for vertex in cycle}
    vertices = {
        SourceVertexId(key): MeshVertexRef(SourceVertexId(key), value) for key, value in positions.items() if key in used
    }
    edges: dict[SourceEdgeId, MeshEdgeRef] = {}
    edge_by_ends: dict[frozenset, SourceEdgeId] = {}
    face_refs: dict[SourceFaceId, MeshFaceRef] = {}
    for index, cycle in enumerate(faces):
        edge_ids = []
        for position, first in enumerate(cycle):
            second = cycle[(position + 1) % len(cycle)]
            key = frozenset((first, second))
            if key not in edge_by_ends:
                edge_id = SourceEdgeId(f"e{len(edges)}")
                edge_by_ends[key] = edge_id
                edges[edge_id] = MeshEdgeRef(edge_id, (SourceVertexId(first), SourceVertexId(second)))
            edge_ids.append(edge_by_ends[key])
        face_id = SourceFaceId(f"f{index}")
        face_refs[face_id] = MeshFaceRef(
            face_id,
            tuple(SourceVertexId(v) for v in cycle),
            tuple(edge_ids),
            face_strength=(strengths or {}).get(index),
        )
    marks = tuple(
        SourceMark(kind=SourceMarkKind.SEAM, target_id=edge_by_ends[frozenset(pair)]) for pair in seams
    )
    return SourceMeshSnapshot(
        id=SourceMeshId(name),
        vertices=vertices,
        edges=edges,
        faces=face_refs,
        selected_face_ids=tuple(face_refs),
        marks=marks,
    )


def make_corner_bevel_source(
    *,
    concave: bool = False,
    marked: bool = True,
    seams: bool = True,
    rows: int = 1,
    strip_strengths: tuple[SourceFaceStrength, ...] | None = None,
) -> SourceMeshSnapshot:
    """A floor and a wall meeting at a 90-degree corner replaced by a one-segment bevel strip.

    The profile (x, z): floor (2, 0) -> (0.2, 0), bevel (0.2, 0) -> (0, 0.2),
    wall (0, 0.2) -> (0, 2), extruded along y over `rows` rows of faces.
    Faces f0..: per row floor, bevel, wall. By default the faces look away
    from the inside of the L (floor normal -z, wall normal -x), so the
    corner is convex; concave reverses every face (floor +z, wall +x), so
    the same corner is seen from inside. Seams on the two profile lines between the bevel and its
    neighbours; marks: bevel MEDIUM (or strip_strengths per row), others STRONG.
    """

    profile = [(2.0, 0.0), (0.2, 0.0), (0.0, 0.2), (0.0, 2.0)]
    positions = {
        f"p{i}_{j}": (x, float(j), z) for i, (x, z) in enumerate(profile) for j in range(rows + 1)
    }
    faces = []
    strengths: dict[int, SourceFaceStrength] = {}
    for j in range(rows):
        for i in range(3):
            cycle = (f"p{i}_{j}", f"p{i}_{j + 1}", f"p{i + 1}_{j + 1}", f"p{i + 1}_{j}")
            if not concave:
                cycle = tuple(reversed(cycle))
            if marked:
                if i == 1:
                    strengths[len(faces)] = strip_strengths[j] if strip_strengths else MEDIUM
                else:
                    strengths[len(faces)] = STRONG
            faces.append(cycle)
    seam_pairs = tuple(
        (f"p{i}_{j}", f"p{i}_{j + 1}") for i in (1, 2) for j in range(rows)
    ) if seams else ()
    name = f"corner_bevel_{'concave' if concave else 'convex'}"
    return _mesh(name, positions, faces, seam_pairs, strengths)


def make_single_quad_source(strength: SourceFaceStrength | None = MEDIUM) -> SourceMeshSnapshot:
    """One quad alone: both ladder readings have their rails and ends on the mesh border."""

    positions = {"a": (0.0, 0.0, 0.0), "b": (1.0, 0.0, 0.0), "c": (1.0, 1.0, 0.0), "d": (0.0, 1.0, 0.0)}
    return _mesh("single_quad", positions, [("a", "b", "c", "d")], (), {0: strength} if strength else None)


# Flat layouts for Rule B. The strip candidate is the quad q = (1,1)-(2,2);
# J is a triangle under it, apex (1.5, 0).

_FLAT = {
    f"v{x}{y}": (float(x), float(y), 0.0) for x in range(4) for y in range(5)
}
_FLAT["apex"] = (1.5, 0.0, 0.0)
_Q = ("v11", "v21", "v22", "v12")
_Q_EDGES = (("v11", "v21"), ("v21", "v22"), ("v22", "v12"), ("v12", "v11"))
_J = ("v21", "v11", "apex")


def make_quad_with_triangles_source(*, top: bool = False) -> SourceMeshSnapshot:
    """The quad q with a triangle patch under it, on its left and right, and with top a fourth above.

    The triangles' other edges lie on the border; without top the top side
    of q is on the border (reviewer case F2). Both ladder readings of q are
    end-strict (their ends lie on triangles or the border), so q is
    undecided and nothing anchors a decision.
    """

    faces = [_Q, _J, ("v22", "v21", "right2"), ("v11", "v12", "left2")]
    if top:
        faces.append(("v12", "v22", "top2"))
    positions = dict(_FLAT)
    positions.update({"right2": (3.0, 1.5, 0.0), "top2": (1.5, 3.0, 0.0), "left2": (0.0, 1.5, 0.0)})
    return _mesh("quad_with_triangles" + ("_top" if top else ""), positions, faces, _Q_EDGES)


def make_quad_with_bevel_faces_on_both_readings_rails_source() -> SourceMeshSnapshot:
    """Marked: the MEDIUM quad q between WEAK triangles left and right, a MEDIUM quad above, border below.

    Read with its ends on the triangles, q has a MEDIUM face across its top
    rail; read with its ends top and bottom, it has WEAK faces across both
    rails. Only the rail clause of the mark rule rejects either reading.
    """

    faces = [_Q, ("v22", "v21", "right2"), ("v11", "v12", "left2"), ("v12", "v22", "v23", "v13")]
    positions = dict(_FLAT)
    positions.update({"right2": (3.0, 1.5, 0.0), "left2": (0.0, 1.5, 0.0)})
    strengths = {0: MEDIUM, 1: WEAK, 2: WEAK, 3: MEDIUM}
    edges = _Q_EDGES + (("v12", "v13"), ("v22", "v23"), ("v13", "v23"))
    return _mesh("quad_with_bevel_faces_on_rails", positions, faces, edges, strengths)


def make_open_slab_source() -> SourceMeshSnapshot:
    """A free-standing slab with an open bottom: outer, inner and top quads, two 5-gon end caps.

    Every patch is one face, every edge a seam. Topologically the top is a
    one-segment bevel between outer and inner with the caps as junctions
    (reviewer case F3, a known false positive of the structural rule).
    """

    positions = {f"v{x}{y}{z}": (4.0 * x, 0.3 * y, 2.0 * z) for x in (0, 1) for y in (0, 1) for z in (0, 1)}
    positions.update({"m0": (0.0, 0.15, 0.0), "m1": (4.0, 0.15, 0.0)})
    faces = [
        ("v000", "v100", "v101", "v001"),  # outer, y = 0
        ("v110", "v010", "v011", "v111"),  # inner, y = 0.3
        ("v001", "v101", "v111", "v011"),  # top
        ("v010", "m0", "v000", "v001", "v011"),  # cap, x = 0
        ("m1", "v110", "v111", "v101", "v100"),  # cap, x = 4
    ]
    seams = tuple({tuple(sorted((c[i], c[(i + 1) % len(c)]))) for c in faces for i in range(len(c))})
    return _mesh("open_slab", positions, faces, tuple(sorted(seams)))


def make_quad_between_two_surfaces_source(*, junction_touches_surface: bool, fins_on_top: bool = False) -> SourceMeshSnapshot:
    """The quad q between two quads L and R, with J under it and the top on the border.

    With junction_touches_surface, a triangle of L also borders J across a
    seam, so J touches a main surface and is no junction: nothing is a
    bevel. Without it, J is a junction and q a bevel strip. With
    fins_on_top, two fin triangles stand on q's top edge (a non-manifold
    edge): no reading of q is end-strict and nothing is a bevel.
    """

    faces = [
        _Q,
        _J,
        ("v01", "v11", "v12", "v02"),  # L
        ("v21", "v31", "v32", "v22"),  # R
    ]
    seams = _Q_EDGES
    if junction_touches_surface:
        faces.append(("v01", "apex", "v11"))  # L, under its quad, touching J
        seams = seams + (("v11", "apex"),)
    positions = dict(_FLAT)
    if fins_on_top:
        positions.update({"fin_a": (1.5, 2.0, 1.0), "fin_b": (1.5, 2.0, -1.0)})
        faces.extend((("v22", "v12", "fin_a"), ("v12", "v22", "fin_b")))
    name = "quad_between_two_surfaces" + ("_touching" if junction_touches_surface else "") + ("_fins" if fins_on_top else "")
    return _mesh(name, positions, faces, seams)


def make_capped_prism_source(sides: int = 6) -> SourceMeshSnapshot:
    """A prism: two n-gon caps and one quad side patch per side, every edge a seam.

    Each side patch is one column from cap to cap whose rails lie on the two
    neighbouring side patches: topologically a chamfered prism.
    """

    positions = {}
    for i in range(sides):
        angle = 2.0 * math.pi * i / sides
        positions[f"b{i}"] = (math.cos(angle), math.sin(angle), 0.0)
        positions[f"t{i}"] = (math.cos(angle), math.sin(angle), 1.0)
    faces = [(f"b{i}", f"b{(i + 1) % sides}", f"t{(i + 1) % sides}", f"t{i}") for i in range(sides)]
    faces.append(tuple(f"b{i}" for i in reversed(range(sides))))
    faces.append(tuple(f"t{i}" for i in range(sides)))
    seams = tuple((f"b{i}", f"t{i}") for i in range(sides)) + tuple(
        (f"{ring}{i}", f"{ring}{(i + 1) % sides}") for ring in "bt" for i in range(sides)
    )
    return _mesh(f"capped_prism_{sides}", positions, faces, seams)


def make_tube_with_one_quad_column_source(sides: int = 6) -> SourceMeshSnapshot:
    """An open-bottom tube under an n-gon cap: one side quad q and one wall patch W of the other sides.

    Seams on the two vertical edges between q and W and around the cap. Both
    q and W have exactly one end-strict reading (ends on the cap and the
    border), and the cap is a junction of them, but q has W on both rails
    and W has q on both rails: no strip, so the cap joins none.
    """

    positions = {}
    for i in range(sides):
        angle = 2.0 * math.pi * i / sides
        positions[f"b{i}"] = (math.cos(angle), math.sin(angle), 0.0)
        positions[f"t{i}"] = (math.cos(angle), math.sin(angle), 1.0)
    faces = [(f"b{i}", f"b{(i + 1) % sides}", f"t{(i + 1) % sides}", f"t{i}") for i in range(sides)]
    faces.append(tuple(f"t{i}" for i in range(sides)))
    seams = (("b0", "t0"), (f"b{sides - 1}", f"t{sides - 1}")) + tuple(
        (f"t{i}", f"t{(i + 1) % sides}") for i in range(sides)
    )
    return _mesh(f"tube_with_one_quad_column_{sides}", positions, faces, seams)


def make_quad_pointed_both_ways_source() -> SourceMeshSnapshot:
    """A quad q with a triangle on each side; the bottom and left triangles are anchored by strips.

    Topology only (the positions are a plain spread, not a real surface).
    Both readings of q end on triangles, so q is undecided. Below and left
    of q, a one-quad strip D1 / D2 has one end on the triangle, the other on
    the border, and single-quad ladders L on both rails: D1 and D2 are
    decided, so the bottom and left triangles are junctions. Their edges
    on q are ends of different readings of q: q is blocked and stays
    undecided; D1 and D2 are bevel strips with those two junctions.
    """

    faces = [
        ("a", "b", "c", "d"),  # f0: q
        ("b", "a", "x1"),  # f1: bottom triangle
        ("c", "b", "x2"),  # f2: right triangle
        ("d", "c", "x3"),  # f3: top triangle
        ("a", "d", "x4"),  # f4: left triangle
        ("b", "x1", "y1", "y2"),  # f5: D1 on the bottom triangle
        ("y1", "x1", "z1", "z2"),  # f6: L on a rail of D1
        ("b", "y2", "z3", "z4"),  # f7: L on the other rail of D1
        ("a", "x4", "w1", "w2"),  # f8: D2 on the left triangle
        ("w1", "x4", "u1", "u2"),  # f9: L on a rail of D2
        ("a", "w2", "u3", "u4"),  # f10: L on the other rail of D2
    ]
    names = sorted({vertex for face in faces for vertex in face})
    positions = {
        name: (math.cos(index * 2.4), math.sin(index * 2.4), 0.1 * index) for index, name in enumerate(names)
    }
    seams = tuple({tuple(sorted((c[i], c[(i + 1) % len(c)]))) for c in faces for i in range(len(c))})
    return _mesh("quad_pointed_both_ways", positions, faces, tuple(sorted(seams)))
