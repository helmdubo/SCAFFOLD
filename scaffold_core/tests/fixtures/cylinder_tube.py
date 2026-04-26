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


def make_segmented_cylinder_tube_without_caps_with_one_seam_source() -> SourceMeshSnapshot:
    """Return a tube whose seam cut is represented by two source edges."""

    vertex_ids = {
        name: SourceVertexId(name)
        for name in (
            "v_a_t", "v_b_t", "v_c_t", "v_d_t",
            "v_a_m", "v_b_m", "v_c_m", "v_d_m",
            "v_a_b", "v_b_b", "v_c_b", "v_d_b",
        )
    }

    edge_ids = {
        name: SourceEdgeId(name)
        for name in (
            "e_top_ab", "e_top_bc", "e_top_cd", "e_top_da",
            "e_mid_ab", "e_mid_bc", "e_mid_cd", "e_mid_da",
            "e_bot_ab", "e_bot_bc", "e_bot_cd", "e_bot_da",
            "e_va_top", "e_va_bot",
            "e_vb_top", "e_vb_bot",
            "e_vc_top", "e_vc_bot",
            "e_vd_top", "e_vd_bot",
        )
    }

    face_ids = {
        name: SourceFaceId(name)
        for name in (
            "f_ab_top", "f_ab_bot",
            "f_bc_top", "f_bc_bot",
            "f_cd_top", "f_cd_bot",
            "f_da_top", "f_da_bot",
        )
    }

    def edge(name: str, first: str, second: str) -> MeshEdgeRef:
        return MeshEdgeRef(edge_ids[name], (vertex_ids[first], vertex_ids[second]))

    def face(name: str, vertices: tuple[str, ...], edges: tuple[str, ...]) -> MeshFaceRef:
        return MeshFaceRef(
            face_ids[name],
            tuple(vertex_ids[vertex_name] for vertex_name in vertices),
            tuple(edge_ids[edge_name] for edge_name in edges),
        )

    return SourceMeshSnapshot(
        id=SourceMeshId("segmented_cylinder_tube_without_caps_one_seam"),
        vertices={
            vertex_ids["v_a_t"]: MeshVertexRef(vertex_ids["v_a_t"], (1.0, 0.0, 2.0)),
            vertex_ids["v_b_t"]: MeshVertexRef(vertex_ids["v_b_t"], (0.0, 1.0, 2.0)),
            vertex_ids["v_c_t"]: MeshVertexRef(vertex_ids["v_c_t"], (-1.0, 0.0, 2.0)),
            vertex_ids["v_d_t"]: MeshVertexRef(vertex_ids["v_d_t"], (0.0, -1.0, 2.0)),
            vertex_ids["v_a_m"]: MeshVertexRef(vertex_ids["v_a_m"], (1.0, 0.0, 1.0)),
            vertex_ids["v_b_m"]: MeshVertexRef(vertex_ids["v_b_m"], (0.0, 1.0, 1.0)),
            vertex_ids["v_c_m"]: MeshVertexRef(vertex_ids["v_c_m"], (-1.0, 0.0, 1.0)),
            vertex_ids["v_d_m"]: MeshVertexRef(vertex_ids["v_d_m"], (0.0, -1.0, 1.0)),
            vertex_ids["v_a_b"]: MeshVertexRef(vertex_ids["v_a_b"], (1.0, 0.0, 0.0)),
            vertex_ids["v_b_b"]: MeshVertexRef(vertex_ids["v_b_b"], (0.0, 1.0, 0.0)),
            vertex_ids["v_c_b"]: MeshVertexRef(vertex_ids["v_c_b"], (-1.0, 0.0, 0.0)),
            vertex_ids["v_d_b"]: MeshVertexRef(vertex_ids["v_d_b"], (0.0, -1.0, 0.0)),
        },
        edges={
            edge_ids["e_top_ab"]: edge("e_top_ab", "v_a_t", "v_b_t"),
            edge_ids["e_top_bc"]: edge("e_top_bc", "v_b_t", "v_c_t"),
            edge_ids["e_top_cd"]: edge("e_top_cd", "v_c_t", "v_d_t"),
            edge_ids["e_top_da"]: edge("e_top_da", "v_d_t", "v_a_t"),
            edge_ids["e_mid_ab"]: edge("e_mid_ab", "v_a_m", "v_b_m"),
            edge_ids["e_mid_bc"]: edge("e_mid_bc", "v_b_m", "v_c_m"),
            edge_ids["e_mid_cd"]: edge("e_mid_cd", "v_c_m", "v_d_m"),
            edge_ids["e_mid_da"]: edge("e_mid_da", "v_d_m", "v_a_m"),
            edge_ids["e_bot_ab"]: edge("e_bot_ab", "v_a_b", "v_b_b"),
            edge_ids["e_bot_bc"]: edge("e_bot_bc", "v_b_b", "v_c_b"),
            edge_ids["e_bot_cd"]: edge("e_bot_cd", "v_c_b", "v_d_b"),
            edge_ids["e_bot_da"]: edge("e_bot_da", "v_d_b", "v_a_b"),
            edge_ids["e_va_top"]: edge("e_va_top", "v_a_t", "v_a_m"),
            edge_ids["e_va_bot"]: edge("e_va_bot", "v_a_m", "v_a_b"),
            edge_ids["e_vb_top"]: edge("e_vb_top", "v_b_t", "v_b_m"),
            edge_ids["e_vb_bot"]: edge("e_vb_bot", "v_b_m", "v_b_b"),
            edge_ids["e_vc_top"]: edge("e_vc_top", "v_c_t", "v_c_m"),
            edge_ids["e_vc_bot"]: edge("e_vc_bot", "v_c_m", "v_c_b"),
            edge_ids["e_vd_top"]: edge("e_vd_top", "v_d_t", "v_d_m"),
            edge_ids["e_vd_bot"]: edge("e_vd_bot", "v_d_m", "v_d_b"),
        },
        faces={
            face_ids["f_ab_top"]: face(
                "f_ab_top",
                ("v_a_t", "v_a_m", "v_b_m", "v_b_t"),
                ("e_va_top", "e_mid_ab", "e_vb_top", "e_top_ab"),
            ),
            face_ids["f_ab_bot"]: face(
                "f_ab_bot",
                ("v_a_m", "v_a_b", "v_b_b", "v_b_m"),
                ("e_va_bot", "e_bot_ab", "e_vb_bot", "e_mid_ab"),
            ),
            face_ids["f_bc_top"]: face(
                "f_bc_top",
                ("v_b_t", "v_b_m", "v_c_m", "v_c_t"),
                ("e_vb_top", "e_mid_bc", "e_vc_top", "e_top_bc"),
            ),
            face_ids["f_bc_bot"]: face(
                "f_bc_bot",
                ("v_b_m", "v_b_b", "v_c_b", "v_c_m"),
                ("e_vb_bot", "e_bot_bc", "e_vc_bot", "e_mid_bc"),
            ),
            face_ids["f_cd_top"]: face(
                "f_cd_top",
                ("v_c_t", "v_c_m", "v_d_m", "v_d_t"),
                ("e_vc_top", "e_mid_cd", "e_vd_top", "e_top_cd"),
            ),
            face_ids["f_cd_bot"]: face(
                "f_cd_bot",
                ("v_c_m", "v_c_b", "v_d_b", "v_d_m"),
                ("e_vc_bot", "e_bot_cd", "e_vd_bot", "e_mid_cd"),
            ),
            face_ids["f_da_top"]: face(
                "f_da_top",
                ("v_d_t", "v_d_m", "v_a_m", "v_a_t"),
                ("e_vd_top", "e_mid_da", "e_va_top", "e_top_da"),
            ),
            face_ids["f_da_bot"]: face(
                "f_da_bot",
                ("v_d_m", "v_d_b", "v_a_b", "v_a_m"),
                ("e_vd_bot", "e_bot_da", "e_va_bot", "e_mid_da"),
            ),
        },
        selected_face_ids=tuple(face_ids.values()),
        marks=(
            SourceMark(kind=SourceMarkKind.SEAM, target_id=edge_ids["e_va_top"]),
            SourceMark(kind=SourceMarkKind.SEAM, target_id=edge_ids["e_va_bot"]),
        ),
    )
