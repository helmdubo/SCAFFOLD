"""
Layer: tests fixtures

Rules:
- Synthetic closed shared boundary loop source fixtures only.
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


def make_closed_shared_boundary_loop_source() -> SourceMeshSnapshot:
    """Return two Patch candidates sharing a closed four-edge boundary loop."""

    v0 = SourceVertexId("v0")
    v1 = SourceVertexId("v1")
    v2 = SourceVertexId("v2")
    v3 = SourceVertexId("v3")
    v4 = SourceVertexId("v4")
    v5 = SourceVertexId("v5")
    v6 = SourceVertexId("v6")
    v7 = SourceVertexId("v7")

    e0 = SourceEdgeId("e0")
    e1 = SourceEdgeId("e1")
    e2 = SourceEdgeId("e2")
    e3 = SourceEdgeId("e3")
    e4 = SourceEdgeId("e4")
    e5 = SourceEdgeId("e5")
    e6 = SourceEdgeId("e6")
    e7 = SourceEdgeId("e7")
    e8 = SourceEdgeId("e8")
    e9 = SourceEdgeId("e9")
    e10 = SourceEdgeId("e10")
    e11 = SourceEdgeId("e11")

    f0 = SourceFaceId("f0")
    f1 = SourceFaceId("f1")
    f2 = SourceFaceId("f2")
    f3 = SourceFaceId("f3")
    f4 = SourceFaceId("f4")
    f5 = SourceFaceId("f5")

    return SourceMeshSnapshot(
        id=SourceMeshId("closed_shared_boundary_loop"),
        vertices={
            v0: MeshVertexRef(v0, (0.0, 0.0, 0.0)),
            v1: MeshVertexRef(v1, (1.0, 0.0, 0.0)),
            v2: MeshVertexRef(v2, (1.0, 1.0, 0.0)),
            v3: MeshVertexRef(v3, (0.0, 1.0, 0.0)),
            v4: MeshVertexRef(v4, (0.0, 0.0, 1.0)),
            v5: MeshVertexRef(v5, (1.0, 0.0, 1.0)),
            v6: MeshVertexRef(v6, (1.0, 1.0, 1.0)),
            v7: MeshVertexRef(v7, (0.0, 1.0, 1.0)),
        },
        edges={
            e0: MeshEdgeRef(e0, (v0, v1)),
            e1: MeshEdgeRef(e1, (v1, v2)),
            e2: MeshEdgeRef(e2, (v2, v3)),
            e3: MeshEdgeRef(e3, (v3, v0)),
            e4: MeshEdgeRef(e4, (v4, v5)),
            e5: MeshEdgeRef(e5, (v5, v6)),
            e6: MeshEdgeRef(e6, (v6, v7)),
            e7: MeshEdgeRef(e7, (v7, v4)),
            e8: MeshEdgeRef(e8, (v0, v4)),
            e9: MeshEdgeRef(e9, (v1, v5)),
            e10: MeshEdgeRef(e10, (v2, v6)),
            e11: MeshEdgeRef(e11, (v3, v7)),
        },
        faces={
            f0: MeshFaceRef(f0, (v0, v1, v2, v3), (e0, e1, e2, e3)),
            f1: MeshFaceRef(f1, (v0, v4, v5, v1), (e8, e4, e9, e0)),
            f2: MeshFaceRef(f2, (v1, v5, v6, v2), (e9, e5, e10, e1)),
            f3: MeshFaceRef(f3, (v2, v6, v7, v3), (e10, e6, e11, e2)),
            f4: MeshFaceRef(f4, (v3, v7, v4, v0), (e11, e7, e8, e3)),
            f5: MeshFaceRef(f5, (v4, v7, v6, v5), (e7, e6, e5, e4)),
        },
        selected_face_ids=(f0, f1, f2, f3, f4, f5),
        marks=(
            SourceMark(kind=SourceMarkKind.SEAM, target_id=e0),
            SourceMark(kind=SourceMarkKind.SEAM, target_id=e1),
            SourceMark(kind=SourceMarkKind.SEAM, target_id=e2),
            SourceMark(kind=SourceMarkKind.SEAM, target_id=e3),
        ),
    )
