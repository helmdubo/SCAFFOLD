"""
Layer: tests fixtures

Rules:
- Synthetic source fixtures for per-side chain shape (cone ring, stepped seam, warped face).
- Fixtures build small explicit source data.
- No production logic here.
"""

from __future__ import annotations

from math import cos, pi, sin

from scaffold_core.ids import SourceEdgeId, SourceFaceId, SourceMeshId, SourceVertexId
from scaffold_core.layer_0_source.marks import SourceMark, SourceMarkKind
from scaffold_core.layer_0_source.snapshot import (
    MeshEdgeRef,
    MeshFaceRef,
    MeshVertexRef,
    SourceMeshSnapshot,
)


def make_cone_frustum_band_source(
    sides: int = 16,
    bottom_radius: float = 2.0,
    top_radius: float = 1.0,
    height: float = 1.0,
    capped: bool = False,
) -> SourceMeshSnapshot:
    """Return an open cone frustum band of quads with one vertical seam.

    The top and bottom rings are planar arcs on the band border. With the
    default radii the band leans 45 degrees, so each ring meets the surface at
    a tilt strictly between 0 and 90 degrees. Equal radii give a cylinder band
    (tilt 0). capped=True adds one ngon cap across the top ring behind a fully
    seamed rim; the rim then turns by 360/sides degrees per vertex on the cap.
    """

    vertices: dict[SourceVertexId, MeshVertexRef] = {}
    edges: dict[SourceEdgeId, MeshEdgeRef] = {}
    faces: dict[SourceFaceId, MeshFaceRef] = {}
    top = [SourceVertexId(f"t{index}") for index in range(sides)]
    bottom = [SourceVertexId(f"b{index}") for index in range(sides)]
    for index in range(sides):
        angle = 2.0 * pi * index / sides
        vertices[bottom[index]] = MeshVertexRef(
            bottom[index], (bottom_radius * cos(angle), bottom_radius * sin(angle), 0.0)
        )
        vertices[top[index]] = MeshVertexRef(
            top[index], (top_radius * cos(angle), top_radius * sin(angle), height)
        )
    for index in range(sides):
        following = (index + 1) % sides
        for edge_id, pair in (
            (f"e_b{index}", (bottom[index], bottom[following])),
            (f"e_t{index}", (top[index], top[following])),
            (f"e_v{index}", (bottom[index], top[index])),
        ):
            edges[SourceEdgeId(edge_id)] = MeshEdgeRef(SourceEdgeId(edge_id), pair)
    for index in range(sides):
        following = (index + 1) % sides
        face_id = SourceFaceId(f"f{index}")
        faces[face_id] = MeshFaceRef(
            face_id,
            (bottom[index], bottom[following], top[following], top[index]),
            (
                SourceEdgeId(f"e_b{index}"),
                SourceEdgeId(f"e_v{following}"),
                SourceEdgeId(f"e_t{index}"),
                SourceEdgeId(f"e_v{index}"),
            ),
        )
    marks = [SourceMark(kind=SourceMarkKind.SEAM, target_id=SourceEdgeId("e_v0"))]
    if capped:
        cap_id = SourceFaceId("f_cap")
        faces[cap_id] = MeshFaceRef(
            cap_id,
            tuple(top),
            tuple(SourceEdgeId(f"e_t{index}") for index in range(sides)),
        )
        marks.extend(
            SourceMark(kind=SourceMarkKind.SEAM, target_id=SourceEdgeId(f"e_t{index}"))
            for index in range(sides)
        )
    return SourceMeshSnapshot(
        id=SourceMeshId("cone_frustum_band"),
        vertices=vertices,
        edges=edges,
        faces=faces,
        selected_face_ids=tuple(faces),
        marks=tuple(marks),
    )


def make_stepped_seam_source(stepped: bool = True) -> SourceMeshSnapshot:
    """Return two coplanar patches split by a seam of three unit segments.

    stepped=True: on a 2 x 3 grid the seam runs (0,1)-(1,1)-(1,2)-(2,2), two
    90-degree steps in the plane (the buildings jog case). stepped=False: on a
    3 x 2 grid the seam runs straight along y = 1. Both patches lie in z = 0.
    """

    columns, rows = (2, 3) if stepped else (3, 2)
    vertices: dict[SourceVertexId, MeshVertexRef] = {}
    edges: dict[SourceEdgeId, MeshEdgeRef] = {}
    faces: dict[SourceFaceId, MeshFaceRef] = {}

    def vertex(x: int, y: int) -> SourceVertexId:
        return SourceVertexId(f"v{x}_{y}")

    def edge(first: tuple[int, int], second: tuple[int, int]) -> SourceEdgeId:
        low, high = sorted((first, second))
        return SourceEdgeId(f"e{low[0]}_{low[1]}_{high[0]}_{high[1]}")

    for x in range(columns + 1):
        for y in range(rows + 1):
            vertices[vertex(x, y)] = MeshVertexRef(vertex(x, y), (float(x), float(y), 0.0))
    for x in range(columns):
        for y in range(rows):
            corners = ((x, y), (x + 1, y), (x + 1, y + 1), (x, y + 1))
            edge_ids = []
            for first, second in zip(corners, corners[1:] + corners[:1]):
                edge_id = edge(first, second)
                low, high = sorted((first, second))
                edges[edge_id] = MeshEdgeRef(edge_id, (vertex(*low), vertex(*high)))
                edge_ids.append(edge_id)
            face_id = SourceFaceId(f"f{x}_{y}")
            faces[face_id] = MeshFaceRef(face_id, tuple(vertex(*corner) for corner in corners), tuple(edge_ids))
    path = ((0, 1), (1, 1), (1, 2), (2, 2)) if stepped else ((0, 1), (1, 1), (2, 1), (3, 1))
    seam_edges = tuple(edge(first, second) for first, second in zip(path, path[1:]))
    return SourceMeshSnapshot(
        id=SourceMeshId("stepped_seam" if stepped else "straight_seam"),
        vertices=vertices,
        edges=edges,
        faces=faces,
        selected_face_ids=tuple(faces),
        marks=tuple(SourceMark(kind=SourceMarkKind.SEAM, target_id=edge_id) for edge_id in seam_edges),
    )


def make_folded_strip_with_cap_source() -> SourceMeshSnapshot:
    """Return a strip folded like a bevel profile, with a flat cap on its end.

    The profile (0,0,0)-(1,0,0)-(1,0,1)-(2,0,1) is swept along +y to y = 2:
    three strip faces, one patch. At y = 0 a flat hexagonal cap closes the
    profile down to z = -1. The profile edges at y = 0 are seams, so the cross
    chain is shared by the strip (it bends in depth there) and the cap (it
    steps by right angles in the cap plane).
    """

    profile = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (2.0, 1.0))
    vertices: dict[SourceVertexId, MeshVertexRef] = {}
    edges: dict[SourceEdgeId, MeshEdgeRef] = {}
    faces: dict[SourceFaceId, MeshFaceRef] = {}

    def add_vertex(name: str, position: tuple[float, float, float]) -> SourceVertexId:
        vertex_id = SourceVertexId(name)
        vertices[vertex_id] = MeshVertexRef(vertex_id, position)
        return vertex_id

    def add_face(name: str, corners: tuple[SourceVertexId, ...]) -> None:
        edge_ids = []
        for first, second in zip(corners, corners[1:] + corners[:1]):
            low, high = sorted((first, second))
            edge_id = SourceEdgeId(f"e_{low}_{high}")
            edges[edge_id] = MeshEdgeRef(edge_id, (low, high))
            edge_ids.append(edge_id)
        face_id = SourceFaceId(name)
        faces[face_id] = MeshFaceRef(face_id, corners, tuple(edge_ids))

    near = tuple(add_vertex(f"p{index}_0", (x, 0.0, z)) for index, (x, z) in enumerate(profile))
    far = tuple(add_vertex(f"p{index}_2", (x, 2.0, z)) for index, (x, z) in enumerate(profile))
    cap_low_right = add_vertex("c_low_right", (2.0, 0.0, -1.0))
    cap_low_left = add_vertex("c_low_left", (0.0, 0.0, -1.0))
    for index in range(len(profile) - 1):
        add_face(f"f_strip{index}", (near[index], near[index + 1], far[index + 1], far[index]))
    add_face("f_cap", (cap_low_left, cap_low_right) + tuple(reversed(near)))
    seam_edges = tuple(
        SourceEdgeId(f"e_{min(first, second)}_{max(first, second)}") for first, second in zip(near, near[1:])
    )
    return SourceMeshSnapshot(
        id=SourceMeshId("folded_strip_with_cap"),
        vertices=vertices,
        edges=edges,
        faces=faces,
        selected_face_ids=tuple(faces),
        marks=tuple(SourceMark(kind=SourceMarkKind.SEAM, target_id=edge_id) for edge_id in seam_edges),
    )


def make_single_pentagon_source(lift: float = 0.5) -> SourceMeshSnapshot:
    """Return one pentagon face whose border chain passes (0,0)-(1,0)-(2,0,lift).

    lift > 0 warps the single face: at (1,0) the border turns in depth while
    the face angle there says it turns in the surface (law mismatch). lift = 0
    gives the same pentagon flat, straight through (1,0).
    """

    points = (
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (2.0, 0.0, lift),
        (2.0, 2.0, lift),
        (0.0, 2.0, 0.0),
    )
    vertex_ids = tuple(SourceVertexId(f"v{index}") for index in range(len(points)))
    edge_ids = tuple(SourceEdgeId(f"e{index}") for index in range(len(points)))
    face_id = SourceFaceId("f0")
    return SourceMeshSnapshot(
        id=SourceMeshId("single_pentagon"),
        vertices={vertex_id: MeshVertexRef(vertex_id, point) for vertex_id, point in zip(vertex_ids, points)},
        edges={
            edge_id: MeshEdgeRef(edge_id, (vertex_ids[index], vertex_ids[(index + 1) % len(points)]))
            for index, edge_id in enumerate(edge_ids)
        },
        faces={face_id: MeshFaceRef(face_id, vertex_ids, edge_ids)},
        selected_face_ids=(face_id,),
    )
