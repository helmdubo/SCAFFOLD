"""
Layer: 1 — Topology

Rules:
- Read-only topology query helpers only.
- No mutation, no builders, no geometry facts, no relations, no features, no runtime solve.
- This module imports only Layer 1 model and ids.
"""

from __future__ import annotations

from scaffold_core.ids import BoundaryLoopId, ChainId, ChainUseId, PatchId, VertexId
from scaffold_core.layer_1_topology.model import ChainUse, SurfaceModel


def chain_uses_for_chain(model: SurfaceModel, chain_id: ChainId) -> tuple[ChainUse, ...]:
    """Return all ChainUses referencing a Chain."""

    return tuple(use for use in model.chain_uses.values() if use.chain_id == chain_id)


def loops_for_patch(model: SurfaceModel, patch_id: PatchId) -> tuple[BoundaryLoopId, ...]:
    """Return loop ids owned by a Patch."""

    return model.patches[patch_id].loop_ids


def chain_uses_in_loop(model: SurfaceModel, loop_id: BoundaryLoopId) -> tuple[ChainUse, ...]:
    """Return ChainUses in loop order."""

    loop = model.loops[loop_id]
    return tuple(model.chain_uses[use_id] for use_id in loop.chain_use_ids)


def chain_use_vertices(model: SurfaceModel, chain_use_id: ChainUseId) -> tuple[VertexId, VertexId]:
    """Return materialized start/end vertices for a ChainUse."""

    use = model.chain_uses[chain_use_id]
    if use.start_vertex_id is not None and use.end_vertex_id is not None:
        return use.start_vertex_id, use.end_vertex_id

    chain = model.chains[use.chain_id]
    if use.orientation_sign == 1:
        return chain.start_vertex_id, chain.end_vertex_id
    return chain.end_vertex_id, chain.start_vertex_id


def incident_uses_for_vertex(model: SurfaceModel, vertex_id: VertexId) -> tuple[ChainUse, ...]:
    """Return ChainUses whose oriented start or end touches a Vertex."""

    incident: list[ChainUse] = []
    for use in model.chain_uses.values():
        start, end = chain_use_vertices(model, use.id)
        if vertex_id in (start, end):
            incident.append(use)
    return tuple(incident)
