"""
Layer: tests fixtures

Rules:
- Synthetic detached parallel walls source fixture only.
- Fixtures build small explicit source data.
- No production logic here.
"""

from __future__ import annotations

from scaffold_core.ids import SourceEdgeId, SourceFaceId, SourceMeshId, SourceVertexId
from scaffold_core.layer_0_source.snapshot import (
    MeshEdgeRef,
    MeshFaceRef,
    MeshVertexRef,
    SourceMeshSnapshot,
)


def make_detached_parallel_walls_source() -> SourceMeshSnapshot:
    """Return two disconnected wall quads sharing the same world directions.

    The walls share no vertices, edges or faces, so they form two Shells and
    two Patches with no adjacency path between them. Their boundary chains are
    world-parallel, which makes this the canonical negative fixture for any
    direction-family grouping: a connectivity-aware grouping must keep the two
    walls in separate families even though their world directions coincide.
    """

    a0 = SourceVertexId("a0")
    a1 = SourceVertexId("a1")
    a2 = SourceVertexId("a2")
    a3 = SourceVertexId("a3")
    b0 = SourceVertexId("b0")
    b1 = SourceVertexId("b1")
    b2 = SourceVertexId("b2")
    b3 = SourceVertexId("b3")

    e_a0 = SourceEdgeId("e_a0")
    e_a1 = SourceEdgeId("e_a1")
    e_a2 = SourceEdgeId("e_a2")
    e_a3 = SourceEdgeId("e_a3")
    e_b0 = SourceEdgeId("e_b0")
    e_b1 = SourceEdgeId("e_b1")
    e_b2 = SourceEdgeId("e_b2")
    e_b3 = SourceEdgeId("e_b3")

    f_a = SourceFaceId("f_a")
    f_b = SourceFaceId("f_b")

    return SourceMeshSnapshot(
        id=SourceMeshId("detached_parallel_walls"),
        vertices={
            a0: MeshVertexRef(a0, (0.0, 0.0, 0.0)),
            a1: MeshVertexRef(a1, (1.0, 0.0, 0.0)),
            a2: MeshVertexRef(a2, (1.0, 0.0, 1.0)),
            a3: MeshVertexRef(a3, (0.0, 0.0, 1.0)),
            b0: MeshVertexRef(b0, (4.0, 3.0, 0.0)),
            b1: MeshVertexRef(b1, (5.0, 3.0, 0.0)),
            b2: MeshVertexRef(b2, (5.0, 3.0, 1.0)),
            b3: MeshVertexRef(b3, (4.0, 3.0, 1.0)),
        },
        edges={
            e_a0: MeshEdgeRef(e_a0, (a0, a1)),
            e_a1: MeshEdgeRef(e_a1, (a1, a2)),
            e_a2: MeshEdgeRef(e_a2, (a2, a3)),
            e_a3: MeshEdgeRef(e_a3, (a3, a0)),
            e_b0: MeshEdgeRef(e_b0, (b0, b1)),
            e_b1: MeshEdgeRef(e_b1, (b1, b2)),
            e_b2: MeshEdgeRef(e_b2, (b2, b3)),
            e_b3: MeshEdgeRef(e_b3, (b3, b0)),
        },
        faces={
            f_a: MeshFaceRef(f_a, (a0, a1, a2, a3), (e_a0, e_a1, e_a2, e_a3)),
            f_b: MeshFaceRef(f_b, (b0, b1, b2, b3), (e_b0, e_b1, e_b2, e_b3)),
        },
        selected_face_ids=(f_a, f_b),
    )
