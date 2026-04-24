"""
Layer: tests fixtures

Rules:
- Synthetic vertex-only contact source fixture only.
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


def make_vertex_only_contact_source() -> SourceMeshSnapshot:
    """Return two selected quads that share one vertex and no edge."""

    v0 = SourceVertexId("v0")
    v1 = SourceVertexId("v1")
    v2 = SourceVertexId("v2")
    v3 = SourceVertexId("v3")
    v4 = SourceVertexId("v4")
    v5 = SourceVertexId("v5")
    v6 = SourceVertexId("v6")

    e0 = SourceEdgeId("e0")
    e1 = SourceEdgeId("e1")
    e2 = SourceEdgeId("e2")
    e3 = SourceEdgeId("e3")
    e4 = SourceEdgeId("e4")
    e5 = SourceEdgeId("e5")
    e6 = SourceEdgeId("e6")
    e7 = SourceEdgeId("e7")

    f0 = SourceFaceId("f0")
    f1 = SourceFaceId("f1")

    return SourceMeshSnapshot(
        id=SourceMeshId("vertex_only_contact"),
        vertices={
            v0: MeshVertexRef(v0, (0.0, 0.0, 0.0)),
            v1: MeshVertexRef(v1, (1.0, 0.0, 0.0)),
            v2: MeshVertexRef(v2, (1.0, 1.0, 0.0)),
            v3: MeshVertexRef(v3, (0.0, 1.0, 0.0)),
            v4: MeshVertexRef(v4, (2.0, 1.0, 0.0)),
            v5: MeshVertexRef(v5, (2.0, 2.0, 0.0)),
            v6: MeshVertexRef(v6, (1.0, 2.0, 0.0)),
        },
        edges={
            e0: MeshEdgeRef(e0, (v0, v1)),
            e1: MeshEdgeRef(e1, (v1, v2)),
            e2: MeshEdgeRef(e2, (v2, v3)),
            e3: MeshEdgeRef(e3, (v3, v0)),
            e4: MeshEdgeRef(e4, (v2, v4)),
            e5: MeshEdgeRef(e5, (v4, v5)),
            e6: MeshEdgeRef(e6, (v5, v6)),
            e7: MeshEdgeRef(e7, (v6, v2)),
        },
        faces={
            f0: MeshFaceRef(f0, (v0, v1, v2, v3), (e0, e1, e2, e3)),
            f1: MeshFaceRef(f1, (v2, v4, v5, v6), (e4, e5, e6, e7)),
        },
        selected_face_ids=(f0, f1),
    )
