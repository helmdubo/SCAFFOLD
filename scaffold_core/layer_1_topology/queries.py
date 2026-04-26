"""
Layer: 1 — Topology

Rules:
- Read-only topology query helpers only.
- No mutation, no builders, no geometry facts, no relations, no features, no runtime solve.
- This module imports only Layer 1 model and ids.
"""

from __future__ import annotations

from scaffold_core.ids import BoundaryLoopId, ChainId, PatchChainId, PatchId, VertexId
from scaffold_core.layer_1_topology.model import PatchChain, SurfaceModel


def patch_chains_for_chain(model: SurfaceModel, chain_id: ChainId) -> tuple[PatchChain, ...]:
    """Return all PatchChains referencing a Chain."""

    return tuple(use for use in model.patch_chains.values() if use.chain_id == chain_id)


def loops_for_patch(model: SurfaceModel, patch_id: PatchId) -> tuple[BoundaryLoopId, ...]:
    """Return loop ids owned by a Patch."""

    return model.patches[patch_id].loop_ids


def patch_chains_in_loop(model: SurfaceModel, loop_id: BoundaryLoopId) -> tuple[PatchChain, ...]:
    """Return PatchChains in loop order."""

    loop = model.loops[loop_id]
    return tuple(model.patch_chains[use_id] for use_id in loop.patch_chain_ids)


def patch_chain_vertices(model: SurfaceModel, patch_chain_id: PatchChainId) -> tuple[VertexId, VertexId]:
    """Return materialized start/end vertices for a PatchChain."""

    use = model.patch_chains[patch_chain_id]
    if use.start_vertex_id is not None and use.end_vertex_id is not None:
        return use.start_vertex_id, use.end_vertex_id

    chain = model.chains[use.chain_id]
    if use.orientation_sign == 1:
        return chain.start_vertex_id, chain.end_vertex_id
    return chain.end_vertex_id, chain.start_vertex_id


def incident_patch_chains_for_vertex(model: SurfaceModel, vertex_id: VertexId) -> tuple[PatchChain, ...]:
    """Return PatchChains whose oriented start or end touches a Vertex."""

    incident: list[PatchChain] = []
    for use in model.patch_chains.values():
        start, end = patch_chain_vertices(model, use.id)
        if vertex_id in (start, end):
            incident.append(use)
    return tuple(incident)
