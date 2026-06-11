"""
Layer: tests fixtures

Rules:
- Synthetic L-corridor tunnel strip source fixtures only.
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


def make_l_corridor_tunnel_single_patch_source() -> SourceMeshSnapshot:
    """Return a three-quad strip folding 90 degrees twice (floor, wall, ceiling).

    The strip runs along +X on the floor, folds up along +Z at x=1, then folds
    again and returns along -X as a ceiling. No seams: one Patch whose long
    border chains turn through three world directions. A length-preserving
    unwrap lays this strip out straight, so the long rails are one continuous
    flow despite the world-direction turns. This is the canonical positive
    fixture for connectivity-aware direction transport.
    """

    g0 = SourceVertexId("g0")
    g1 = SourceVertexId("g1")
    g2 = SourceVertexId("g2")
    g3 = SourceVertexId("g3")
    w0 = SourceVertexId("w0")
    w1 = SourceVertexId("w1")
    t0 = SourceVertexId("t0")
    t1 = SourceVertexId("t1")

    e_floor_y0 = SourceEdgeId("e_floor_y0")
    e_fold_bottom = SourceEdgeId("e_fold_bottom")
    e_floor_y1 = SourceEdgeId("e_floor_y1")
    e_floor_x0 = SourceEdgeId("e_floor_x0")
    e_wall_y0 = SourceEdgeId("e_wall_y0")
    e_wall_y1 = SourceEdgeId("e_wall_y1")
    e_fold_top = SourceEdgeId("e_fold_top")
    e_ceil_y0 = SourceEdgeId("e_ceil_y0")
    e_ceil_y1 = SourceEdgeId("e_ceil_y1")
    e_ceil_x0 = SourceEdgeId("e_ceil_x0")

    f_floor = SourceFaceId("f_floor")
    f_wall = SourceFaceId("f_wall")
    f_ceiling = SourceFaceId("f_ceiling")

    return SourceMeshSnapshot(
        id=SourceMeshId("l_corridor_tunnel_single_patch"),
        vertices={
            g0: MeshVertexRef(g0, (0.0, 0.0, 0.0)),
            g1: MeshVertexRef(g1, (1.0, 0.0, 0.0)),
            g2: MeshVertexRef(g2, (1.0, 1.0, 0.0)),
            g3: MeshVertexRef(g3, (0.0, 1.0, 0.0)),
            w0: MeshVertexRef(w0, (1.0, 0.0, 1.0)),
            w1: MeshVertexRef(w1, (1.0, 1.0, 1.0)),
            t0: MeshVertexRef(t0, (0.0, 0.0, 1.0)),
            t1: MeshVertexRef(t1, (0.0, 1.0, 1.0)),
        },
        edges={
            e_floor_y0: MeshEdgeRef(e_floor_y0, (g0, g1)),
            e_fold_bottom: MeshEdgeRef(e_fold_bottom, (g1, g2)),
            e_floor_y1: MeshEdgeRef(e_floor_y1, (g2, g3)),
            e_floor_x0: MeshEdgeRef(e_floor_x0, (g3, g0)),
            e_wall_y0: MeshEdgeRef(e_wall_y0, (g1, w0)),
            e_wall_y1: MeshEdgeRef(e_wall_y1, (g2, w1)),
            e_fold_top: MeshEdgeRef(e_fold_top, (w0, w1)),
            e_ceil_y0: MeshEdgeRef(e_ceil_y0, (w0, t0)),
            e_ceil_y1: MeshEdgeRef(e_ceil_y1, (w1, t1)),
            e_ceil_x0: MeshEdgeRef(e_ceil_x0, (t0, t1)),
        },
        faces={
            f_floor: MeshFaceRef(
                f_floor,
                (g0, g1, g2, g3),
                (e_floor_y0, e_fold_bottom, e_floor_y1, e_floor_x0),
            ),
            f_wall: MeshFaceRef(
                f_wall,
                (g1, w0, w1, g2),
                (e_wall_y0, e_fold_top, e_wall_y1, e_fold_bottom),
            ),
            f_ceiling: MeshFaceRef(
                f_ceiling,
                (w0, t0, t1, w1),
                (e_ceil_y0, e_ceil_x0, e_ceil_y1, e_fold_top),
            ),
        },
        selected_face_ids=(f_floor, f_wall, f_ceiling),
    )


def make_l_corridor_tunnel_seamed_folds_source() -> SourceMeshSnapshot:
    """Return the tunnel strip with seams on both fold edges.

    Three Patches (floor, wall, ceiling) connected through two seamed folds.
    The width chains of all three patches stay world-parallel along Y, while
    the length chains span X, Z and X world directions across the patches.
    """

    source = make_l_corridor_tunnel_single_patch_source()
    return replace(
        source,
        id=SourceMeshId("l_corridor_tunnel_seamed_folds"),
        marks=(
            SourceMark(kind=SourceMarkKind.SEAM, target_id=SourceEdgeId("e_fold_bottom")),
            SourceMark(kind=SourceMarkKind.SEAM, target_id=SourceEdgeId("e_fold_top")),
        ),
    )
