"""
Layer: tests fixtures

Rules:
- Synthetic single-patch sheets for run corners (RunCornerRelation), bridged
  right corners (RunBridgedCornerRelation) and the frame-free axis
  bipartition: flat outlines and sheets folded across an edge.
- Fixtures build small explicit source data.
- No production logic here.
"""

from __future__ import annotations

from math import cos, pi, sin, tan

from scaffold_core.ids import SourceEdgeId, SourceFaceId, SourceMeshId, SourceVertexId
from scaffold_core.layer_0_source.snapshot import (
    MeshEdgeRef,
    MeshFaceRef,
    MeshVertexRef,
    SourceMeshSnapshot,
)


def _sheet(name: str, points: dict[str, tuple[float, float, float]], faces: dict[str, tuple[str, ...]]):
    vertices = {SourceVertexId(key): MeshVertexRef(SourceVertexId(key), point) for key, point in points.items()}
    edges: dict[SourceEdgeId, MeshEdgeRef] = {}
    face_refs: dict[SourceFaceId, MeshFaceRef] = {}
    for face_name, corners in faces.items():
        edge_ids = []
        for first, second in zip(corners, corners[1:] + corners[:1]):
            low, high = sorted((first, second))
            edge_id = SourceEdgeId(f"e_{low}_{high}")
            edges[edge_id] = MeshEdgeRef(edge_id, (SourceVertexId(low), SourceVertexId(high)))
            edge_ids.append(edge_id)
        face_id = SourceFaceId(face_name)
        face_refs[face_id] = MeshFaceRef(face_id, tuple(SourceVertexId(c) for c in corners), tuple(edge_ids))
    return SourceMeshSnapshot(
        id=SourceMeshId(name),
        vertices=vertices,
        edges=edges,
        faces=face_refs,
        selected_face_ids=tuple(face_refs),
    )


def make_hexagon_source() -> SourceMeshSnapshot:
    """Return one flat regular hexagon face: six 120-degree corners."""

    points = {f"h{index}": (cos(index * pi / 3.0), sin(index * pi / 3.0), 0.0) for index in range(6)}
    return _sheet("hexagon", points, {"f0": tuple(points)})


def make_flat_l_sheet_source() -> SourceMeshSnapshot:
    """Return a flat L outline of three unit quads: five convex corners, one reflex at (1,1)."""

    points = {
        "a": (0.0, 0.0, 0.0), "b": (1.0, 0.0, 0.0), "c": (2.0, 0.0, 0.0),
        "d": (2.0, 1.0, 0.0), "e": (1.0, 1.0, 0.0), "f": (1.0, 2.0, 0.0),
        "g": (0.0, 2.0, 0.0), "h": (0.0, 1.0, 0.0),
    }
    faces = {"f0": ("a", "b", "e", "h"), "f1": ("b", "c", "d", "e"), "f2": ("h", "e", "f", "g")}
    return _sheet("flat_l_sheet", points, faces)


def make_flat_l_hexagon_source() -> SourceMeshSnapshot:
    """Return one flat L-shaped hexagon face: five 90-degree corners, one 270 at e = (1,1)."""

    points = {
        "a": (0.0, 0.0, 0.0), "b": (2.0, 0.0, 0.0), "d": (2.0, 1.0, 0.0),
        "e": (1.0, 1.0, 0.0), "f": (1.0, 2.0, 0.0), "g": (0.0, 2.0, 0.0),
    }
    return _sheet("flat_l_hexagon", points, {"f0": tuple(points)})


def make_bow_tie_quad_source() -> SourceMeshSnapshot:
    """Return one self-crossing quad: its edges a-b and c-d cross, so its winding says nothing."""

    points = {"a": (0.0, 0.0, 0.0), "b": (2.0, 2.0, 0.0), "c": (2.0, 0.0, 0.0), "d": (0.0, 1.0, 0.0)}
    return _sheet("bow_tie_quad", points, {"f0": tuple(points)})


def make_folded_sheet_source() -> SourceMeshSnapshot:
    """Return one patch folded 90 degrees along the edge y = 1, z = 0.

    A unit floor quad (z = 0) and a wall triangle in the plane y = 1. The
    boundary loop is a-b-p-w-q: at q = (0,1,0) floor and wall add to 180
    degrees (the side q-a and the wall edge w-q are one straight line of the
    surface although they are perpendicular in 3D); at p = (1,1,0) the floor
    gives 90 and the wall 45 degrees, so the floor edge b-p and the wall edge
    p-w are perpendicular in 3D but meet at 135 degrees on the surface.
    """

    points = {
        "a": (0.0, 0.0, 0.0), "b": (1.0, 0.0, 0.0), "p": (1.0, 1.0, 0.0),
        "q": (0.0, 1.0, 0.0), "w": (0.0, 1.0, 1.0),
    }
    faces = {"f_floor": ("a", "b", "p", "q"), "f_wall": ("q", "p", "w")}
    return _sheet("folded_sheet", points, faces)


def make_folded_l_sheet_source() -> SourceMeshSnapshot:
    """Return an L-shaped floor with a flap folded up 90 degrees on its right side.

    One patch, not planar. Floor: (0,0)-(2,0)-(2,1)-(1,1)-(1,2)-(0,1.5); the
    corner at e = (1,1) is a reflex right corner (270 degrees). The flap
    stands on c-d at x = 2 up to z = 1, so the floor bottom and the flap's
    near edge form one straight surface line, and so do the flap's far edge
    and the floor edge d-e. The slanted top f-g has no right corner, so the
    notch edge e-f is tied to the rest only through the reflex corner.
    """

    points = {
        "a": (0.0, 0.0, 0.0), "b": (1.0, 0.0, 0.0), "c": (2.0, 0.0, 0.0),
        "d": (2.0, 1.0, 0.0), "e": (1.0, 1.0, 0.0), "f": (1.0, 2.0, 0.0),
        "g": (0.0, 1.5, 0.0), "h": (0.0, 1.0, 0.0),
        "c_up": (2.0, 0.0, 1.0), "d_up": (2.0, 1.0, 1.0),
    }
    faces = {
        "f0": ("a", "b", "e", "h"),
        "f1": ("b", "c", "d", "e"),
        "f2": ("h", "e", "f", "g"),
        "f_flap": ("c", "c_up", "d_up", "d"),
    }
    return _sheet("folded_l_sheet", points, faces)


def make_outline_face_source(name: str, outline: tuple[tuple[float, float], ...]) -> SourceMeshSnapshot:
    """Return one flat convex n-gon face in z = 0 with the given counter-clockwise outline."""

    points = {f"o{index}": (x, y, 0.0) for index, (x, y) in enumerate(outline)}
    return _sheet(name, points, {"f0": tuple(points)})


def make_cut_corner_rectangle_source(first_turn_degrees: float = 45.0, folded: bool = False) -> SourceMeshSnapshot:
    """Return a 4 x 2 rectangle whose corner (4, 2) is cut by one straight run.

    Loop a(0,0) - b(4,0) - c(4,1) - d - g(0,2): the cut c-d leaves the right
    side b-c turned left by first_turn_degrees, and the top side d-g turns
    left by the rest of 90 degrees, so b-c and d-g meet at a convex right
    corner bridged by c-d. folded=True stands a 1 m flap on the left side a-g
    (one patch, not planar); the outline seen from the patch surface is the
    same: at g and at a floor and flap add up to a straight line.
    """

    run = tan(first_turn_degrees * pi / 180.0)
    points = {
        "a": (0.0, 0.0, 0.0), "b": (4.0, 0.0, 0.0), "c": (4.0, 1.0, 0.0),
        "d": (4.0 - run, 2.0, 0.0), "g": (0.0, 2.0, 0.0),
    }
    faces = {"f0": ("a", "b", "c", "d", "g")}
    if folded:
        points.update({"a_up": (0.0, 0.0, 1.0), "g_up": (0.0, 2.0, 1.0)})
        faces["f_flap"] = ("a", "g", "g_up", "a_up")
    return _sheet(f"cut_corner_rectangle_{first_turn_degrees:g}{'_folded' if folded else ''}", points, faces)


def make_folded_cut_corner_source(first_turn_degrees: float, second_turn_degrees: float) -> SourceMeshSnapshot:
    """Return the folded cut-corner sheet with any two turns at the cut.

    a(0,0) - b(4,0) - c(4,1), then the cut c-d (length 1 / cos(first turn))
    turned left by first_turn_degrees, then the top side d-g turned left by
    second_turn_degrees up to g on x = 0, and the left side g-a. With turns
    that do not add up to 90 degrees the top side is not parallel to the
    bottom. A 1 m flap stands on a-g (one patch, not planar).
    """

    first, second = first_turn_degrees * pi / 180.0, second_turn_degrees * pi / 180.0
    cut = 1.0 / cos(first)
    d = (4.0 + cut * cos(pi / 2.0 + first), 1.0 + cut * sin(pi / 2.0 + first))
    heading = pi / 2.0 + first + second
    g_y = d[1] + (-d[0] / cos(heading)) * sin(heading)
    points = {
        "a": (0.0, 0.0, 0.0), "b": (4.0, 0.0, 0.0), "c": (4.0, 1.0, 0.0),
        "d": (d[0], d[1], 0.0), "g": (0.0, g_y, 0.0),
        "a_up": (0.0, 0.0, 1.0), "g_up": (0.0, g_y, 1.0),
    }
    faces = {"f0": ("a", "b", "c", "d", "g"), "f_flap": ("a", "g", "g_up", "a_up")}
    return _sheet(f"folded_cut_corner_{first_turn_degrees:g}_{second_turn_degrees:g}", points, faces)


def make_notched_sheet_source(folded: bool) -> SourceMeshSnapshot:
    """Return a 6 x 3 sheet with a chamfered door notch and one chamfered corner.

    Loop (counter-clockwise in z = 0): bottom a0(0,0) - a1(2,0); notch: jamb
    a1 - j1(2,1.3), chamfer j1 - j2(2.2,1.5), top j2 - j3(3.8,1.5), chamfer
    j3 - j4(4,1.3), jamb j4 - a2(4,0); bottom a2 - a3(6,0); right side a3 -
    h4(6,1.3) - a4(6,3); top a4 - u4 - u3 - u2 - u1 - t1(0.3,3); chamfer t1 -
    t2(0,2.7); left t2 - h1(0,1.3) - a0. Every chamfer corner is 225 degrees
    on the patch (the notch: a reflex right corner turned over the chamfer)
    or 135 degrees (top left: a convex one). folded=True stands a 1 m flap on
    the right side a3 - a4 (one patch, not planar): the loop then runs a3 -
    f0 - g0 - f1 - a4 over the flap, and the bottom and top sides continue
    straight onto it.
    """

    flat = {
        "a0": (0.0, 0.0), "a1": (2.0, 0.0), "j1": (2.0, 1.3), "j2": (2.2, 1.5), "j3": (3.8, 1.5),
        "j4": (4.0, 1.3), "a2": (4.0, 0.0), "a3": (6.0, 0.0), "h4": (6.0, 1.3), "a4": (6.0, 3.0),
        "u4": (4.0, 3.0), "u3": (3.8, 3.0), "u2": (2.2, 3.0), "u1": (2.0, 3.0), "t1": (0.3, 3.0),
        "t2": (0.0, 2.7), "h1": (0.0, 1.3),
    }
    points = {key: (x, y, 0.0) for key, (x, y) in flat.items()}
    faces = {
        "L1": ("a0", "a1", "j1", "h1"),
        "L2": ("h1", "j1", "u1", "t1", "t2"),
        "C1": ("j1", "j2", "u2", "u1"),
        "M1": ("j2", "j3", "u3", "u2"),
        "C2": ("j3", "j4", "u4", "u3"),
        "R1": ("a2", "a3", "h4", "j4"),
        "R2": ("j4", "h4", "a4", "u4"),
    }
    if folded:
        points.update({"f0": (6.0, 0.0, 1.0), "g0": (6.0, 1.3, 1.0), "f1": (6.0, 3.0, 1.0)})
        faces["F1"] = ("h4", "a3", "f0", "g0")
        faces["F2"] = ("a4", "h4", "g0", "f1")
    return _sheet(f"notched_sheet{'_folded' if folded else ''}", points, faces)


# The folded notched sheet unfolded about its fold x = 6: the flap lands at x > 6.
NOTCHED_SHEET_UNFOLDED = {
    "f0": (7.0, 0.0), "g0": (7.0, 1.3), "f1": (7.0, 3.0),
}
