"""
Layer: tests fixtures

Rules:
- Synthetic non-manifold topology fixture only.
- Fixtures build explicit test data.
- No production logic here.
"""

from __future__ import annotations

from scaffold_core.ids import (
    BoundaryLoopId,
    ChainId,
    ChainUseId,
    PatchId,
    ShellId,
    SourceEdgeId,
    SourceFaceId,
    SourceMeshId,
    SourceVertexId,
    SurfaceModelId,
    VertexId,
)
from scaffold_core.layer_0_source.snapshot import (
    MeshEdgeRef,
    MeshFaceRef,
    MeshVertexRef,
    SourceMeshSnapshot,
)
from scaffold_core.layer_1_topology.model import (
    BoundaryLoop,
    BoundaryLoopKind,
    Chain,
    ChainUse,
    Patch,
    Shell,
    SurfaceModel,
    Vertex,
)


def make_three_quad_non_manifold_source() -> SourceMeshSnapshot:
    """Return three selected quads sharing one source edge."""

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

    f0 = SourceFaceId("f0")
    f1 = SourceFaceId("f1")
    f2 = SourceFaceId("f2")

    return SourceMeshSnapshot(
        id=SourceMeshId("three_quad_non_manifold"),
        vertices={
            v0: MeshVertexRef(v0, (0.0, 0.0, 0.0)),
            v1: MeshVertexRef(v1, (1.0, 0.0, 0.0)),
            v2: MeshVertexRef(v2, (1.0, 1.0, 0.0)),
            v3: MeshVertexRef(v3, (0.0, 1.0, 0.0)),
            v4: MeshVertexRef(v4, (0.0, -1.0, 0.0)),
            v5: MeshVertexRef(v5, (1.0, -1.0, 0.0)),
            v6: MeshVertexRef(v6, (1.0, 0.0, 1.0)),
            v7: MeshVertexRef(v7, (0.0, 0.0, 1.0)),
        },
        edges={
            e0: MeshEdgeRef(e0, (v0, v1)),
            e1: MeshEdgeRef(e1, (v1, v2)),
            e2: MeshEdgeRef(e2, (v2, v3)),
            e3: MeshEdgeRef(e3, (v3, v0)),
            e4: MeshEdgeRef(e4, (v0, v4)),
            e5: MeshEdgeRef(e5, (v4, v5)),
            e6: MeshEdgeRef(e6, (v5, v1)),
            e7: MeshEdgeRef(e7, (v1, v6)),
            e8: MeshEdgeRef(e8, (v6, v7)),
            e9: MeshEdgeRef(e9, (v7, v0)),
        },
        faces={
            f0: MeshFaceRef(f0, (v0, v1, v2, v3), (e0, e1, e2, e3)),
            f1: MeshFaceRef(f1, (v1, v0, v4, v5), (e0, e4, e5, e6)),
            f2: MeshFaceRef(f2, (v0, v1, v6, v7), (e0, e7, e8, e9)),
        },
        selected_face_ids=(f0, f1, f2),
    )


def make_non_manifold_chain_model() -> SurfaceModel:
    """Return a model where one Chain has three ChainUses."""

    shell_id = ShellId("shell:0")
    chain_id = ChainId("chain:shared")
    v0 = VertexId("vertex:0")
    v1 = VertexId("vertex:1")

    patches = {}
    loops = {}
    chain_uses = {}
    patch_ids: list[PatchId] = []

    for index in range(3):
        patch_id = PatchId(f"patch:{index}")
        loop_id = BoundaryLoopId(f"loop:{index}:0")
        use_id = ChainUseId(f"use:{index}:0")
        patch_ids.append(patch_id)
        patches[patch_id] = Patch(id=patch_id, shell_id=shell_id, loop_ids=(loop_id,))
        loops[loop_id] = BoundaryLoop(
            id=loop_id,
            patch_id=patch_id,
            kind=BoundaryLoopKind.OUTER,
            chain_use_ids=(use_id,),
            loop_index=0,
        )
        chain_uses[use_id] = ChainUse(
            id=use_id,
            chain_id=chain_id,
            patch_id=patch_id,
            loop_id=loop_id,
            orientation_sign=1 if index % 2 == 0 else -1,
            position_in_loop=0,
        )

    return SurfaceModel(
        id=SurfaceModelId("surface:non_manifold"),
        shells={shell_id: Shell(id=shell_id, patch_ids=tuple(patch_ids))},
        patches=patches,
        loops=loops,
        chains={chain_id: Chain(id=chain_id, start_vertex_id=v0, end_vertex_id=v1)},
        chain_uses=chain_uses,
        vertices={v0: Vertex(id=v0), v1: Vertex(id=v1)},
    )
