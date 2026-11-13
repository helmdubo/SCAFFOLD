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


def make_quad_with_four_junctions_source() -> SourceMeshSnapshot:
    """The quad q with a triangle patch on each side, the triangles' other edges on the border.

    Both ladder readings of q are end-strict, end on a pure junction and
    have their rails on two different patches: two readings qualify.
    """

    faces = [
        _Q,
        _J,
        ("v22", "v21", "right2"),
        ("v12", "v22", "top2"),
        ("v11", "v12", "left2"),
    ]
    positions = dict(_FLAT)
    positions.update({"right2": (3.0, 1.5, 0.0), "top2": (1.5, 3.0, 0.0), "left2": (0.0, 1.5, 0.0)})
    return _mesh("quad_with_four_junctions", positions, faces, _Q_EDGES)


def make_quad_between_junction_and_one_surface_source() -> SourceMeshSnapshot:
    """The quad q with J under it and one patch M wrapped round its other three sides.

    M has a triangle (no ladder relation) and a neighbour N, a triangle across
    a seam (no ladder relation either), so M is no junction. Read with rails left and right, q has an end on the pure
    junction J but both rails on M: not a strip. Read the other way its ends
    lie on M, which is no junction. J stays a pure junction.
    """

    faces = [
        _Q,
        _J,
        ("v01", "v11", "v12", "v02"),  # M, left of q
        ("v02", "v12", "v13", "v03"),  # M, top left
        ("v12", "v22", "v23"),  # M, top middle, two triangles
        ("v12", "v23", "v13"),
        ("v22", "v32", "v33", "v23"),  # M, top right
        ("v21", "v31", "v32", "v22"),  # M, right of q
        ("v03", "v13", "v04"),  # N, a triangle above M
    ]
    return _mesh("quad_between_junction_and_one_surface", dict(_FLAT), faces, _Q_EDGES + (("v03", "v13"),))


def make_quad_between_two_surfaces_source(*, junction_touches_surface: bool) -> SourceMeshSnapshot:
    """The quad q between two quads L and R, with J under it and the top on the border.

    With junction_touches_surface, a triangle of L also borders J across a
    seam, so J touches a main surface and is no pure junction: nothing is a
    bevel. Without it, J is a pure junction and q a bevel strip.
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
    name = "quad_between_two_surfaces" + ("_touching" if junction_touches_surface else "")
    return _mesh(name, dict(_FLAT), faces, seams)


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
