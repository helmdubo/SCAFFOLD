"""
Layer: 1 — Topology

Rules:
- Build immutable Layer 1 topology snapshot from Layer 0 source snapshot.
- Build only topology.
- Do not compute Layer 2 geometry facts.
- Do not classify features.
- Do not assign H/V or WorldOrientation roles.
- Do not orchestrate pipeline passes.
"""

from __future__ import annotations

from scaffold_core.ids import (
    BoundaryLoopId,
    ChainId,
    ChainUseId,
    PatchId,
    ShellId,
    SurfaceModelId,
    VertexId,
)
from scaffold_core.layer_0_source.snapshot import SourceMeshSnapshot
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


def build_topology_snapshot(source: SourceMeshSnapshot) -> SurfaceModel:
    """Build a minimal Layer 1 topology snapshot from a source mesh snapshot.

    G1 policy is intentionally simple: all selected faces become patches in one shell.
    Patch segmentation policy remains an open G0 question and must not be hardcoded here
    beyond this G1 fixture-oriented baseline.
    """

    face_ids = tuple(source.selected_face_ids) or tuple(source.faces.keys())
    model_id = SurfaceModelId(f"surface:{source.id}")
    shell_id = ShellId("shell:0")

    vertices = {
        VertexId(f"vertex:{source_vertex_id}"): Vertex(
            id=VertexId(f"vertex:{source_vertex_id}"),
            source_vertex_ids=(source_vertex_id,),
        )
        for source_vertex_id in source.vertices
    }

    chains: dict[ChainId, Chain] = {}
    chain_uses: dict[ChainUseId, ChainUse] = {}
    loops: dict[BoundaryLoopId, BoundaryLoop] = {}
    patches: dict[PatchId, Patch] = {}

    for face_index, face_id in enumerate(face_ids):
        face = source.faces[face_id]
        patch_id = PatchId(f"patch:{face_id}")
        loop_id = BoundaryLoopId(f"loop:{face_id}:0")
        use_ids: list[ChainUseId] = []

        for edge_index, source_edge_id in enumerate(face.edge_ids):
            source_edge = source.edges[source_edge_id]
            chain_id = ChainId(f"chain:{source_edge_id}")
            start_vertex_id = VertexId(f"vertex:{source_edge.vertex_ids[0]}")
            end_vertex_id = VertexId(f"vertex:{source_edge.vertex_ids[1]}")

            if chain_id not in chains:
                chains[chain_id] = Chain(
                    id=chain_id,
                    start_vertex_id=start_vertex_id,
                    end_vertex_id=end_vertex_id,
                    source_edge_ids=(source_edge_id,),
                )

            face_start = face.vertex_ids[edge_index]
            face_end = face.vertex_ids[(edge_index + 1) % len(face.vertex_ids)]
            if (face_start, face_end) == source_edge.vertex_ids:
                orientation_sign = 1
            elif (face_end, face_start) == source_edge.vertex_ids:
                orientation_sign = -1
            else:
                orientation_sign = 1

            use_id = ChainUseId(f"use:{face_id}:{edge_index}")
            chain_uses[use_id] = ChainUse(
                id=use_id,
                chain_id=chain_id,
                patch_id=patch_id,
                loop_id=loop_id,
                orientation_sign=orientation_sign,
                position_in_loop=edge_index,
            )
            use_ids.append(use_id)

        loops[loop_id] = BoundaryLoop(
            id=loop_id,
            patch_id=patch_id,
            kind=BoundaryLoopKind.OUTER,
            chain_use_ids=tuple(use_ids),
            loop_index=0,
        )
        patches[patch_id] = Patch(
            id=patch_id,
            shell_id=shell_id,
            loop_ids=(loop_id,),
            source_face_ids=(face_id,),
        )

    shell = Shell(id=shell_id, patch_ids=tuple(patches.keys()))
    return SurfaceModel(
        id=model_id,
        shells={shell_id: shell},
        patches=patches,
        loops=loops,
        chains=chains,
        chain_uses=chain_uses,
        vertices=vertices,
    )
