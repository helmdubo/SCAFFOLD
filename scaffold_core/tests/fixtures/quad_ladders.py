"""
Layer: tests fixtures

Rules:
- Small synthetic all-quad (and almost all-quad) source meshes for the quad
  ladder relation: a grid, a single quad, a ring, a patch with a triangle, a
  five-quad pole, a Moebius strip, and a grid and a ring with a seam on one
  edge only.
- Fixtures build explicit source data; one patch each.
- No production logic here.
"""

from __future__ import annotations

import math

from scaffold_core.ids import SourceEdgeId, SourceFaceId, SourceMeshId, SourceVertexId
from scaffold_core.layer_0_source.marks import SourceMark, SourceMarkKind
from scaffold_core.layer_0_source.snapshot import (
    MeshEdgeRef,
    MeshFaceRef,
    MeshVertexRef,
    SourceMeshSnapshot,
)


def _mesh(
    name: str,
    positions: dict[str, tuple[float, float, float]],
    faces: list[tuple[str, ...]],
    seams: tuple[tuple[str, str], ...] = (),
) -> SourceMeshSnapshot:
    vertices = {SourceVertexId(key): MeshVertexRef(SourceVertexId(key), value) for key, value in positions.items()}
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
        face_refs[face_id] = MeshFaceRef(face_id, tuple(SourceVertexId(v) for v in cycle), tuple(edge_ids))
    return SourceMeshSnapshot(
        id=SourceMeshId(name),
        vertices=vertices,
        edges=edges,
        faces=face_refs,
        selected_face_ids=tuple(face_refs),
        marks=tuple(SourceMark(SourceMarkKind.SEAM, edge_by_ends[frozenset(pair)]) for pair in seams),
    )


def make_quad_grid_source(columns: int = 3, rows: int = 2) -> SourceMeshSnapshot:
    """A flat columns x rows grid of quads, faces numbered row by row."""

    positions = {f"v{i}_{j}": (float(i), float(j), 0.0) for i in range(columns + 1) for j in range(rows + 1)}
    faces = [
        (f"v{i}_{j}", f"v{i + 1}_{j}", f"v{i + 1}_{j + 1}", f"v{i}_{j + 1}")
        for j in range(rows)
        for i in range(columns)
    ]
    return _mesh(f"quad_grid_{columns}x{rows}", positions, faces)


def make_quad_ring_source(around: int = 8, across: int = 2) -> SourceMeshSnapshot:
    """A flat annulus: around x across quads between an inner and an outer circle."""

    positions = {}
    for i in range(around):
        angle = 2.0 * math.pi * i / around
        for j in range(across + 1):
            radius = 1.0 + j
            positions[f"v{i}_{j}"] = (radius * math.cos(angle), radius * math.sin(angle), 0.0)
    faces = [
        (f"v{i}_{j}", f"v{(i + 1) % around}_{j}", f"v{(i + 1) % around}_{j + 1}", f"v{i}_{j + 1}")
        for i in range(around)
        for j in range(across)
    ]
    return _mesh(f"quad_ring_{around}x{across}", positions, faces)


def make_quad_grid_with_triangle_source() -> SourceMeshSnapshot:
    """A 2 x 1 grid with a triangle on its right side."""

    positions = {
        "a": (0.0, 0.0, 0.0), "b": (1.0, 0.0, 0.0), "c": (2.0, 0.0, 0.0),
        "d": (0.0, 1.0, 0.0), "e": (1.0, 1.0, 0.0), "f": (2.0, 1.0, 0.0),
        "g": (3.0, 0.5, 0.0),
    }
    faces = [("a", "b", "e", "d"), ("b", "c", "f", "e"), ("c", "g", "f")]
    return _mesh("quad_grid_with_triangle", positions, faces)


def make_five_quad_pole_source() -> SourceMeshSnapshot:
    """Five quads around one interior vertex (a pole of valence five)."""

    positions = {"c": (0.0, 0.0, 0.0)}
    for i in range(5):
        corner = 2.0 * math.pi * i / 5
        middle = corner - math.pi / 5
        positions[f"k{i}"] = (2.0 * math.cos(corner), 2.0 * math.sin(corner), 0.0)
        positions[f"m{i}"] = (1.2 * math.cos(middle), 1.2 * math.sin(middle), 0.0)
    faces = [("c", f"m{i}", f"k{i}", f"m{(i + 1) % 5}") for i in range(5)]
    return _mesh("five_quad_pole", positions, faces)


def make_quad_grid_with_inner_seam_source() -> SourceMeshSnapshot:
    """The 3 x 2 grid with a seam on one interior edge only: v1_0-v1_1, between f0 and f1.

    The patch stays one piece; the seam edge is a boundary edge of it
    (a SEAM_SELF chain) inside the grid.
    """

    grid = make_quad_grid_source(3, 2)
    positions = {str(key): vertex.position for key, vertex in grid.vertices.items()}
    faces = [tuple(str(vertex) for vertex in face.vertex_ids) for face in grid.faces.values()]
    return _mesh("quad_grid_3x2_inner_seam", positions, faces, (("v1_0", "v1_1"),))


def make_quad_ring_with_one_seam_edge_source() -> SourceMeshSnapshot:
    """The 4 x 2 annulus with a seam on one radial edge only (v0_0-v0_1, inner half)."""

    ring = make_quad_ring_source(4, 2)
    positions = {str(key): vertex.position for key, vertex in ring.vertices.items()}
    faces = [tuple(str(vertex) for vertex in face.vertex_ids) for face in ring.faces.values()]
    return _mesh("quad_ring_4x2_one_seam_edge", positions, faces, (("v0_0", "v0_1"),))


def make_mobius_quad_strip_source(around: int = 3) -> SourceMeshSnapshot:
    """A Moebius strip of `around` x 1 quads: the last quad joins the first with a half twist."""

    positions = {}
    for i in range(around):
        angle = 2.0 * math.pi * i / around
        for j in range(2):
            positions[f"v{i}_{j}"] = (math.cos(angle) * (2.0 + j), math.sin(angle) * (2.0 + j), float(i))
    faces = [(f"v{i}_0", f"v{i + 1}_0", f"v{i + 1}_1", f"v{i}_1") for i in range(around - 1)]
    last = around - 1
    faces.append((f"v{last}_0", "v0_1", "v0_0", f"v{last}_1"))
    return _mesh(f"mobius_quad_strip_{around}", positions, faces)
