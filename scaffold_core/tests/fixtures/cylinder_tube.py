"""
Layer: tests fixtures

Rules:
- Synthetic cylinder tube source fixtures only.
- Fixtures build explicit source data.
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


def make_cylinder_tube_without_caps_with_one_seam_source() -> SourceMeshSnapshot:
    """Return a four-sided tube surface with top/bottom borders and one seam cut."""

    v0 = SourceVertexId("v0")
    v1 = SourceVertexId("v1")
    v2 = SourceVertexId("v2")
    v3 = SourceVertexId("v3")
    v4 = SourceVertexId("v4")
    v5 = SourceVertexId("v5")
    v6 = SourceVertexId("v6")
    v7 = SourceVertexId("v7")

    e_t0 = SourceEdgeId("e_t0")
    e_t1 = SourceEdgeId("e_t1")
    e_t2 = SourceEdgeId("e_t2")
    e_t3 = SourceEdgeId("e_t3")
    e_b0 = SourceEdgeId("e_b0")
    e_b1 = SourceEdgeId("e_b1")
    e_b2 = SourceEdgeId("e_b2")
    e_b3 = SourceEdgeId("e_b3")
    e_v0 = SourceEdgeId("e_v0")
    e_v1 = SourceEdgeId("e_v1")
    e_v2 = SourceEdgeId("e_v2")
    e_v3 = SourceEdgeId("e_v3")

    f0 = SourceFaceId("f0")
    f1 = SourceFaceId("f1")
    f2 = SourceFaceId("f2")
    f3 = SourceFaceId("f3")

    return SourceMeshSnapshot(
        id=SourceMeshId("cylinder_tube_without_caps_one_seam"),
        vertices={
            v0: MeshVertexRef(v0, (1.0, 0.0, 1.0)),
            v1: MeshVertexRef(v1, (0.0, 1.0, 1.0)),
            v2: MeshVertexRef(v2, (-1.0, 0.0, 1.0)),
            v3: MeshVertexRef(v3, (0.0, -1.0, 1.0)),
            v4: MeshVertexRef(v4, (1.0, 0.0, 0.0)),
            v5: MeshVertexRef(v5, (0.0, 1.0, 0.0)),
            v6: MeshVertexRef(v6, (-1.0, 0.0, 0.0)),
            v7: MeshVertexRef(v7, (0.0, -1.0, 0.0)),
        },
        edges={
            e_t0: MeshEdgeRef(e_t0, (v0, v1)),
            e_t1: MeshEdgeRef(e_t1, (v1, v2)),
            e_t2: MeshEdgeRef(e_t2, (v2, v3)),
            e_t3: MeshEdgeRef(e_t3, (v3, v0)),
            e_b0: MeshEdgeRef(e_b0, (v4, v5)),
            e_b1: MeshEdgeRef(e_b1, (v5, v6)),
            e_b2: MeshEdgeRef(e_b2, (v6, v7)),
            e_b3: MeshEdgeRef(e_b3, (v7, v4)),
            e_v0: MeshEdgeRef(e_v0, (v0, v4)),
            e_v1: MeshEdgeRef(e_v1, (v1, v5)),
            e_v2: MeshEdgeRef(e_v2, (v2, v6)),
            e_v3: MeshEdgeRef(e_v3, (v3, v7)),
        },
        faces={
            f0: MeshFaceRef(f0, (v0, v4, v5, v1), (e_v0, e_b0, e_v1, e_t0)),
            f1: MeshFaceRef(f1, (v1, v5, v6, v2), (e_v1, e_b1, e_v2, e_t1)),
            f2: MeshFaceRef(f2, (v2, v6, v7, v3), (e_v2, e_b2, e_v3, e_t2)),
            f3: MeshFaceRef(f3, (v3, v7, v4, v0), (e_v3, e_b3, e_v0, e_t3)),
        },
        selected_face_ids=(f0, f1, f2, f3),
        marks=(SourceMark(kind=SourceMarkKind.SEAM, target_id=e_v0),),
    )
