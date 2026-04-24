"""
Layer: tests fixtures

Rules:
- Synthetic L-shape source fixture only.
- Fixtures build small explicit source data.
- No production logic here.
"""

from __future__ import annotations

from dataclasses import replace

from scaffold_core.ids import SourceEdgeId, SourceFaceId, SourceMeshId, SourceVertexId
from scaffold_core.layer_0_source.marks import SourceMark, SourceMarkKind
from scaffold_core.layer_0_source.snapshot import (
    MeshEdgeRef,
    MeshFaceRef,
    MeshVertexRef,
    SourceMeshSnapshot,
)


def make_two_quad_l_source() -> SourceMeshSnapshot:
    """Return two quads sharing one edge, enough to exercise shared ChainUses."""

    v0 = SourceVertexId("v0")
    v1 = SourceVertexId("v1")
    v2 = SourceVertexId("v2")
    v3 = SourceVertexId("v3")
    v4 = SourceVertexId("v4")
    v5 = SourceVertexId("v5")

    e0 = SourceEdgeId("e0")
    e1 = SourceEdgeId("e1")
    e2 = SourceEdgeId("e2")
    e3 = SourceEdgeId("e3")
    e4 = SourceEdgeId("e4")
    e5 = SourceEdgeId("e5")
    e6 = SourceEdgeId("e6")

    f0 = SourceFaceId("f0")
    f1 = SourceFaceId("f1")

    return SourceMeshSnapshot(
        id=SourceMeshId("two_quad_l"),
        vertices={
            v0: MeshVertexRef(v0, (0.0, 0.0, 0.0)),
            v1: MeshVertexRef(v1, (1.0, 0.0, 0.0)),
            v2: MeshVertexRef(v2, (1.0, 1.0, 0.0)),
            v3: MeshVertexRef(v3, (0.0, 1.0, 0.0)),
            v4: MeshVertexRef(v4, (2.0, 0.0, 0.0)),
            v5: MeshVertexRef(v5, (2.0, 1.0, 0.0)),
        },
        edges={
            e0: MeshEdgeRef(e0, (v0, v1)),
            e1: MeshEdgeRef(e1, (v1, v2)),
            e2: MeshEdgeRef(e2, (v2, v3)),
            e3: MeshEdgeRef(e3, (v3, v0)),
            e4: MeshEdgeRef(e4, (v1, v4)),
            e5: MeshEdgeRef(e5, (v4, v5)),
            e6: MeshEdgeRef(e6, (v5, v2)),
        },
        faces={
            f0: MeshFaceRef(f0, (v0, v1, v2, v3), (e0, e1, e2, e3)),
            f1: MeshFaceRef(f1, (v1, v4, v5, v2), (e4, e5, e6, e1)),
        },
        selected_face_ids=(f0, f1),
    )


def make_two_quad_l_source_with_seam_on_shared_edge() -> SourceMeshSnapshot:
    """Return the L fixture with the shared source edge marked as a UV seam."""

    source = make_two_quad_l_source()
    shared_edge_id = SourceEdgeId("e1")
    return replace(
        source,
        marks=(SourceMark(kind=SourceMarkKind.SEAM, target_id=shared_edge_id),),
    )


def make_two_quad_l_source_with_user_boundary_on_shared_edge() -> SourceMeshSnapshot:
    """Return the L fixture with the shared source edge marked as Scaffold boundary."""

    source = make_two_quad_l_source()
    shared_edge_id = SourceEdgeId("e1")
    return replace(
        source,
        marks=(SourceMark(kind=SourceMarkKind.USER, target_id=shared_edge_id),),
    )


def make_two_quad_l_source_with_sharp_on_shared_edge() -> SourceMeshSnapshot:
    """Return the L fixture with the shared source edge marked as Blender Sharp."""

    source = make_two_quad_l_source()
    shared_edge_id = SourceEdgeId("e1")
    return replace(
        source,
        marks=(SourceMark(kind=SourceMarkKind.SHARP, target_id=shared_edge_id),),
    )


def make_two_quad_folded_source_with_seam_on_shared_edge() -> SourceMeshSnapshot:
    """Return the L fixture folded 90 degrees around the shared edge with a seam on it.

    The second quad is rotated up around edge e1 so adjacent patch normals are
    perpendicular, producing a non-coplanar signed dihedral.
    """

    source = make_two_quad_l_source_with_seam_on_shared_edge()
    return replace(
        source,
        vertices={
            **source.vertices,
            SourceVertexId("v4"): MeshVertexRef(SourceVertexId("v4"), (1.0, 0.0, 1.0)),
            SourceVertexId("v5"): MeshVertexRef(SourceVertexId("v5"), (1.0, 1.0, 1.0)),
        },
    )
