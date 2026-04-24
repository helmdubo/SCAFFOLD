"""
Layer: tests fixtures

Rules:
- Synthetic non-manifold topology fixture only.
- Fixtures build explicit test data.
- No production logic here.
"""

from __future__ import annotations

from scaffold_core.ids import BoundaryLoopId, ChainId, ChainUseId, PatchId, ShellId, SurfaceModelId, VertexId
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
