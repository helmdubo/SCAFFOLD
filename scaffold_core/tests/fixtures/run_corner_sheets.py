"""
Layer: tests fixtures

Rules:
- Synthetic single-patch sheets for run corners (RunCornerRelation) and the
  frame-free axis bipartition: flat outlines and sheets folded across an edge.
- Fixtures build small explicit source data.
- No production logic here.
"""

from __future__ import annotations

from math import cos, pi, sin

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
