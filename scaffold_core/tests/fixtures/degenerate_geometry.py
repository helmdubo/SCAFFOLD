"""
Layer: tests fixtures

Rules:
- Synthetic degenerate geometry source fixture only.
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


def make_degenerate_triangle_source() -> SourceMeshSnapshot:
    """Return one triangle with zero area and one zero-length source edge."""

    v0 = SourceVertexId("v0")
    v1 = SourceVertexId("v1")
    v2 = SourceVertexId("v2")
    e0 = SourceEdgeId("e0")
    e1 = SourceEdgeId("e1")
    e2 = SourceEdgeId("e2")
    f0 = SourceFaceId("f0")

    return SourceMeshSnapshot(
        id=SourceMeshId("degenerate_triangle"),
        vertices={
            v0: MeshVertexRef(v0, (0.0, 0.0, 0.0)),
            v1: MeshVertexRef(v1, (0.0, 0.0, 0.0)),
            v2: MeshVertexRef(v2, (1.0, 0.0, 0.0)),
        },
        edges={
            e0: MeshEdgeRef(e0, (v0, v1)),
            e1: MeshEdgeRef(e1, (v1, v2)),
            e2: MeshEdgeRef(e2, (v2, v0)),
        },
        faces={
            f0: MeshFaceRef(f0, (v0, v1, v2), (e0, e1, e2)),
        },
        selected_face_ids=(f0,),
    )
