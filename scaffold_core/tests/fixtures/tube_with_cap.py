"""
Layer: tests fixtures

Rules:
- Synthetic tube-with-cap source fixture only.
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


def make_tube_with_cap_source() -> SourceMeshSnapshot:
    """Return the four-sided tube with a top cap patch behind a seamed rim.

    Same tube as the cylinder fixture (one vertical seam), plus one planar cap
    face across the top ring. All four rim edges carry UV seams, so the cap is
    its own Patch. The cap rim chains and the tube top chains are co-directional
    in world space, but their owner normals diverge: the cap must never join the
    side surface flow. This is the canonical negative fixture for sliding /
    cross-surface continuation.
    """

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
    f_cap = SourceFaceId("f_cap")

    return SourceMeshSnapshot(
        id=SourceMeshId("tube_with_cap"),
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
            f_cap: MeshFaceRef(f_cap, (v0, v1, v2, v3), (e_t0, e_t1, e_t2, e_t3)),
        },
        selected_face_ids=(f0, f1, f2, f3, f_cap),
        marks=(
            SourceMark(kind=SourceMarkKind.SEAM, target_id=e_v0),
            SourceMark(kind=SourceMarkKind.SEAM, target_id=e_t0),
            SourceMark(kind=SourceMarkKind.SEAM, target_id=e_t1),
            SourceMark(kind=SourceMarkKind.SEAM, target_id=e_t2),
            SourceMark(kind=SourceMarkKind.SEAM, target_id=e_t3),
        ),
    )
