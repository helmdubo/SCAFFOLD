"""
Layer: tests fixtures

Rules:
- Synthetic T-vertex wall source fixture only.
- Fixtures build small explicit source data.
- No production logic here.
"""

from __future__ import annotations

from scaffold_core.ids import SourceEdgeId, SourceFaceId, SourceMeshId, SourceVertexId
from scaffold_core.layer_0_source.marks import SourceMark, SourceMarkKind
from scaffold_core.layer_0_source.snapshot import (
    MeshEdgeRef,
    MeshFaceRef,
    MeshVertexRef,
    SourceMeshSnapshot,
)


def make_t_vertex_wall_source(
    flip_left_bottom_edge: bool = False,
    flip_right_bottom_edge: bool = False,
) -> SourceMeshSnapshot:
    """Return a pentagon wall whose straight bottom side is split by a T-vertex.

    Two floor quads meet the wall bottom, one on each side of the T-vertex, and
    every edge is a seam, so the wall bottom is two Chains that continue in a
    straight line (in-patch angle pi). The flip flags reverse the vertex order
    of the two bottom edges: the family result must not depend on it (DD-45).
    """

    positions = {
        "w0": (0.0, 0.0, 0.0),
        "w1": (1.0, 0.0, 0.0),
        "w2": (2.0, 0.0, 0.0),
        "w3": (2.0, 0.0, 1.0),
        "w4": (0.0, 0.0, 1.0),
        "a0": (0.0, -1.0, 0.0),
        "a1": (1.0, -1.0, 0.0),
        "a2": (2.0, -1.0, 0.0),
    }
    vertices = {
        SourceVertexId(name): MeshVertexRef(SourceVertexId(name), position)
        for name, position in positions.items()
    }
    edge_vertices = {
        "e_w01": ("w1", "w0") if flip_left_bottom_edge else ("w0", "w1"),
        "e_w12": ("w2", "w1") if flip_right_bottom_edge else ("w1", "w2"),
        "e_w23": ("w2", "w3"),
        "e_w34": ("w3", "w4"),
        "e_w40": ("w4", "w0"),
        "e_a0": ("w0", "a0"),
        "e_a01": ("a0", "a1"),
        "e_a1": ("a1", "w1"),
        "e_a12": ("a1", "a2"),
        "e_a2": ("a2", "w2"),
    }
    edges = {
        SourceEdgeId(name): MeshEdgeRef(
            SourceEdgeId(name),
            (SourceVertexId(first), SourceVertexId(second)),
        )
        for name, (first, second) in edge_vertices.items()
    }
    face_loops = {
        "f_wall": (("w0", "w4", "w3", "w2", "w1"), ("e_w40", "e_w34", "e_w23", "e_w12", "e_w01")),
        "f_floor_a": (("w0", "w1", "a1", "a0"), ("e_w01", "e_a1", "e_a01", "e_a0")),
        "f_floor_b": (("w1", "w2", "a2", "a1"), ("e_w12", "e_a2", "e_a12", "e_a1")),
    }
    faces = {
        SourceFaceId(name): MeshFaceRef(
            SourceFaceId(name),
            tuple(SourceVertexId(vertex) for vertex in loop),
            tuple(SourceEdgeId(edge) for edge in loop_edges),
        )
        for name, (loop, loop_edges) in face_loops.items()
    }
    return SourceMeshSnapshot(
        id=SourceMeshId("t_vertex_wall"),
        vertices=vertices,
        edges=edges,
        faces=faces,
        selected_face_ids=tuple(faces),
        marks=tuple(SourceMark(kind=SourceMarkKind.SEAM, target_id=edge_id) for edge_id in edges),
    )
