"""
Layer: 3 - Relations

Rules:
- Derived vertex-incidence query helpers only.
- Do not mutate lower-layer snapshots.
- Do not create persistent topology entities.
- Do not derive alignment, world, feature, runtime, solve, UV, API, UI, or Blender data.
"""

from __future__ import annotations

from typing import Mapping

from scaffold_core.ids import VertexId
from scaffold_core.layer_1_topology.model import PatchChain, SurfaceModel
from scaffold_core.layer_1_topology.queries import patch_chain_vertices


PatchChainVertexIncidenceIndex = Mapping[VertexId, tuple[PatchChain, ...]]


def build_patch_chain_vertex_incidence_index(
    topology: SurfaceModel,
) -> dict[VertexId, tuple[PatchChain, ...]]:
    """Return one deterministic Vertex -> incident PatchChains index."""

    incident: dict[VertexId, list[PatchChain]] = {
        vertex_id: []
        for vertex_id in topology.vertices
    }
    for use in topology.patch_chains.values():
        start_vertex_id, end_vertex_id = patch_chain_vertices(topology, use.id)
        incident.setdefault(start_vertex_id, []).append(use)
        if end_vertex_id != start_vertex_id:
            incident.setdefault(end_vertex_id, []).append(use)
    return {
        vertex_id: tuple(sorted(uses, key=lambda use: str(use.id)))
        for vertex_id, uses in incident.items()
    }


def incident_patch_chains_for_vertex(
    topology: SurfaceModel,
    vertex_id: VertexId,
    incidence_index: PatchChainVertexIncidenceIndex | None = None,
) -> tuple[PatchChain, ...]:
    """Return incident PatchChains in deterministic order.

    This is deterministic order, not geometric disk-cycle order.
    """

    if incidence_index is not None:
        return incidence_index.get(vertex_id, ())

    incident: list[PatchChain] = []
    for use in topology.patch_chains.values():
        start_vertex_id, end_vertex_id = patch_chain_vertices(topology, use.id)
        if vertex_id in (start_vertex_id, end_vertex_id):
            incident.append(use)
    return tuple(sorted(incident, key=lambda use: str(use.id)))


def patch_chain_incidence_valence(
    topology: SurfaceModel,
    vertex_id: VertexId,
    incidence_index: PatchChainVertexIncidenceIndex | None = None,
) -> int:
    """Return the deterministic incident PatchChain count for a Vertex."""

    return len(incident_patch_chains_for_vertex(topology, vertex_id, incidence_index))


def has_branching_patch_chain_incidence(
    topology: SurfaceModel,
    vertex_id: VertexId,
    incidence_index: PatchChainVertexIncidenceIndex | None = None,
) -> bool:
    """Return whether a Vertex has at least three incident PatchChains."""

    return patch_chain_incidence_valence(topology, vertex_id, incidence_index) >= 3
