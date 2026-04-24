"""
Layer: tests fixtures

Rules:
- Synthetic SEAM_SELF topology fixture only.
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


def make_seam_self_model() -> SurfaceModel:
    """Return a minimal model where one Chain has two uses in the same Patch."""

    shell_id = ShellId("shell:0")
    patch_id = PatchId("patch:self")
    loop_id = BoundaryLoopId("loop:self:0")
    chain_id = ChainId("chain:self")
    v0 = VertexId("vertex:0")
    v1 = VertexId("vertex:1")
    use_a = ChainUseId("use:self:0")
    use_b = ChainUseId("use:self:1")

    return SurfaceModel(
        id=SurfaceModelId("surface:seam_self"),
        shells={shell_id: Shell(id=shell_id, patch_ids=(patch_id,))},
        patches={patch_id: Patch(id=patch_id, shell_id=shell_id, loop_ids=(loop_id,))},
        loops={
            loop_id: BoundaryLoop(
                id=loop_id,
                patch_id=patch_id,
                kind=BoundaryLoopKind.OUTER,
                chain_use_ids=(use_a, use_b),
                loop_index=0,
            )
        },
        chains={chain_id: Chain(id=chain_id, start_vertex_id=v0, end_vertex_id=v1)},
        chain_uses={
            use_a: ChainUse(
                id=use_a,
                chain_id=chain_id,
                patch_id=patch_id,
                loop_id=loop_id,
                orientation_sign=1,
                position_in_loop=0,
            ),
            use_b: ChainUse(
                id=use_b,
                chain_id=chain_id,
                patch_id=patch_id,
                loop_id=loop_id,
                orientation_sign=-1,
                position_in_loop=1,
            ),
        },
        vertices={v0: Vertex(id=v0), v1: Vertex(id=v1)},
    )
