"""
Layer: tests fixtures

Rules:
- Synthetic beveled/rounded wall corner source fixtures only.
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


def make_beveled_wall_corner_source() -> SourceMeshSnapshot:
    """Return two walls meeting at a 90-degree corner with one chamfer strip.

    Wall A faces -Y, wall B faces +X, and a single 45-degree chamfer quad
    replaces the corner edge. Both vertical chamfer boundary edges carry UV
    seams, so the chamfer becomes its own narrow Patch between the two wall
    Patches. This is the minimal middle-poly bevel case: the vertical chains
    of all three patches share one direction family, while the horizontal
    chains of wall A, chamfer and wall B point in three different world
    directions despite forming one continuous surface flow around the corner.
    """

    a0 = SourceVertexId("a0")
    a1 = SourceVertexId("a1")
    a2 = SourceVertexId("a2")
    a3 = SourceVertexId("a3")
    c0 = SourceVertexId("c0")
    c1 = SourceVertexId("c1")
    b0 = SourceVertexId("b0")
    b1 = SourceVertexId("b1")

    e_a_bottom = SourceEdgeId("e_a_bottom")
    e_a_inner = SourceEdgeId("e_a_inner")
    e_a_top = SourceEdgeId("e_a_top")
    e_a_outer = SourceEdgeId("e_a_outer")
    e_ch_bottom = SourceEdgeId("e_ch_bottom")
    e_ch_far = SourceEdgeId("e_ch_far")
    e_ch_top = SourceEdgeId("e_ch_top")
    e_b_bottom = SourceEdgeId("e_b_bottom")
    e_b_far = SourceEdgeId("e_b_far")
    e_b_top = SourceEdgeId("e_b_top")

    f_wall_a = SourceFaceId("f_wall_a")
    f_chamfer = SourceFaceId("f_chamfer")
    f_wall_b = SourceFaceId("f_wall_b")

    return SourceMeshSnapshot(
        id=SourceMeshId("beveled_wall_corner"),
        vertices={
            a0: MeshVertexRef(a0, (0.0, 0.0, 0.0)),
            a1: MeshVertexRef(a1, (0.9, 0.0, 0.0)),
            a2: MeshVertexRef(a2, (0.9, 0.0, 1.0)),
            a3: MeshVertexRef(a3, (0.0, 0.0, 1.0)),
            c0: MeshVertexRef(c0, (1.0, -0.1, 0.0)),
            c1: MeshVertexRef(c1, (1.0, -0.1, 1.0)),
            b0: MeshVertexRef(b0, (1.0, -1.0, 0.0)),
            b1: MeshVertexRef(b1, (1.0, -1.0, 1.0)),
        },
        edges={
            e_a_bottom: MeshEdgeRef(e_a_bottom, (a0, a1)),
            e_a_inner: MeshEdgeRef(e_a_inner, (a1, a2)),
            e_a_top: MeshEdgeRef(e_a_top, (a2, a3)),
            e_a_outer: MeshEdgeRef(e_a_outer, (a3, a0)),
            e_ch_bottom: MeshEdgeRef(e_ch_bottom, (a1, c0)),
            e_ch_far: MeshEdgeRef(e_ch_far, (c0, c1)),
            e_ch_top: MeshEdgeRef(e_ch_top, (c1, a2)),
            e_b_bottom: MeshEdgeRef(e_b_bottom, (c0, b0)),
            e_b_far: MeshEdgeRef(e_b_far, (b0, b1)),
            e_b_top: MeshEdgeRef(e_b_top, (b1, c1)),
        },
        faces={
            f_wall_a: MeshFaceRef(
                f_wall_a,
                (a0, a1, a2, a3),
                (e_a_bottom, e_a_inner, e_a_top, e_a_outer),
            ),
            f_chamfer: MeshFaceRef(
                f_chamfer,
                (a1, c0, c1, a2),
                (e_ch_bottom, e_ch_far, e_ch_top, e_a_inner),
            ),
            f_wall_b: MeshFaceRef(
                f_wall_b,
                (c0, b0, b1, c1),
                (e_b_bottom, e_b_far, e_b_top, e_ch_far),
            ),
        },
        selected_face_ids=(f_wall_a, f_chamfer, f_wall_b),
        marks=(
            SourceMark(kind=SourceMarkKind.SEAM, target_id=e_a_inner),
            SourceMark(kind=SourceMarkKind.SEAM, target_id=e_ch_far),
        ),
    )


def make_rounded_wall_corner_two_segment_source() -> SourceMeshSnapshot:
    """Return two walls joined by a two-segment rounded corner strip.

    Same layout as the single-chamfer fixture, but the corner is approximated
    by two quads. Seams sit only on the wall/strip boundaries, so the rounded
    strip is one curved Patch of two faces. The strip's horizontal chains turn
    inside one Patch, exercising turning-chain directional evidence.
    """

    a0 = SourceVertexId("a0")
    a1 = SourceVertexId("a1")
    a2 = SourceVertexId("a2")
    a3 = SourceVertexId("a3")
    m0 = SourceVertexId("m0")
    m1 = SourceVertexId("m1")
    c0 = SourceVertexId("c0")
    c1 = SourceVertexId("c1")
    b0 = SourceVertexId("b0")
    b1 = SourceVertexId("b1")

    e_a_bottom = SourceEdgeId("e_a_bottom")
    e_a_inner = SourceEdgeId("e_a_inner")
    e_a_top = SourceEdgeId("e_a_top")
    e_a_outer = SourceEdgeId("e_a_outer")
    e_s1_bottom = SourceEdgeId("e_s1_bottom")
    e_mid = SourceEdgeId("e_mid")
    e_s1_top = SourceEdgeId("e_s1_top")
    e_s2_bottom = SourceEdgeId("e_s2_bottom")
    e_ch_far = SourceEdgeId("e_ch_far")
    e_s2_top = SourceEdgeId("e_s2_top")
    e_b_bottom = SourceEdgeId("e_b_bottom")
    e_b_far = SourceEdgeId("e_b_far")
    e_b_top = SourceEdgeId("e_b_top")

    f_wall_a = SourceFaceId("f_wall_a")
    f_round_1 = SourceFaceId("f_round_1")
    f_round_2 = SourceFaceId("f_round_2")
    f_wall_b = SourceFaceId("f_wall_b")

    return SourceMeshSnapshot(
        id=SourceMeshId("rounded_wall_corner_two_segment"),
        vertices={
            a0: MeshVertexRef(a0, (0.0, 0.0, 0.0)),
            a1: MeshVertexRef(a1, (0.8, 0.0, 0.0)),
            a2: MeshVertexRef(a2, (0.8, 0.0, 1.0)),
            a3: MeshVertexRef(a3, (0.0, 0.0, 1.0)),
            m0: MeshVertexRef(m0, (0.941, -0.059, 0.0)),
            m1: MeshVertexRef(m1, (0.941, -0.059, 1.0)),
            c0: MeshVertexRef(c0, (1.0, -0.2, 0.0)),
            c1: MeshVertexRef(c1, (1.0, -0.2, 1.0)),
            b0: MeshVertexRef(b0, (1.0, -1.0, 0.0)),
            b1: MeshVertexRef(b1, (1.0, -1.0, 1.0)),
        },
        edges={
            e_a_bottom: MeshEdgeRef(e_a_bottom, (a0, a1)),
            e_a_inner: MeshEdgeRef(e_a_inner, (a1, a2)),
            e_a_top: MeshEdgeRef(e_a_top, (a2, a3)),
            e_a_outer: MeshEdgeRef(e_a_outer, (a3, a0)),
            e_s1_bottom: MeshEdgeRef(e_s1_bottom, (a1, m0)),
            e_mid: MeshEdgeRef(e_mid, (m0, m1)),
            e_s1_top: MeshEdgeRef(e_s1_top, (m1, a2)),
            e_s2_bottom: MeshEdgeRef(e_s2_bottom, (m0, c0)),
            e_ch_far: MeshEdgeRef(e_ch_far, (c0, c1)),
            e_s2_top: MeshEdgeRef(e_s2_top, (c1, m1)),
            e_b_bottom: MeshEdgeRef(e_b_bottom, (c0, b0)),
            e_b_far: MeshEdgeRef(e_b_far, (b0, b1)),
            e_b_top: MeshEdgeRef(e_b_top, (b1, c1)),
        },
        faces={
            f_wall_a: MeshFaceRef(
                f_wall_a,
                (a0, a1, a2, a3),
                (e_a_bottom, e_a_inner, e_a_top, e_a_outer),
            ),
            f_round_1: MeshFaceRef(
                f_round_1,
                (a1, m0, m1, a2),
                (e_s1_bottom, e_mid, e_s1_top, e_a_inner),
            ),
            f_round_2: MeshFaceRef(
                f_round_2,
                (m0, c0, c1, m1),
                (e_s2_bottom, e_ch_far, e_s2_top, e_mid),
            ),
            f_wall_b: MeshFaceRef(
                f_wall_b,
                (c0, b0, b1, c1),
                (e_b_bottom, e_b_far, e_b_top, e_ch_far),
            ),
        },
        selected_face_ids=(f_wall_a, f_round_1, f_round_2, f_wall_b),
        marks=(
            SourceMark(kind=SourceMarkKind.SEAM, target_id=e_a_inner),
            SourceMark(kind=SourceMarkKind.SEAM, target_id=e_ch_far),
        ),
    )
