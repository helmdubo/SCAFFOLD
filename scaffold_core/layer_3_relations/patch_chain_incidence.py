"""
Layer: 3 - Relations

Rules:
- Derived vertex-incidence query helpers only.
- Do not mutate lower-layer snapshots.
- Do not create persistent topology entities.
- Do not derive alignment, world, feature, runtime, solve, UV, API, UI, or Blender data.
"""

from __future__ import annotations

from scaffold_core.ids import VertexId
from scaffold_core.layer_1_topology.model import PatchChain, SurfaceModel
from scaffold_core.layer_1_topology.queries import patch_chain_vertices


def incident_patch_chains_for_vertex(
    topology: SurfaceModel,
    vertex_id: VertexId,
) -> tuple[PatchChain, ...]:
    """Return incident PatchChains in deterministic order.

    This is deterministic order, not geometric disk-cycle order.
    """

    incident: list[PatchChain] = []
    for use in topology.patch_chains.values():
        start_vertex_id, end_vertex_id = patch_chain_vertices(topology, use.id)
        if vertex_id in (start_vertex_id, end_vertex_id):
            incident.append(use)
    return tuple(sorted(incident, key=lambda use: str(use.id)))


def patch_chain_incidence_valence(
    topology: SurfaceModel,
    vertex_id: VertexId,
) -> int:
    """Return the deterministic incident PatchChain count for a Vertex."""

    return len(incident_patch_chains_for_vertex(topology, vertex_id))


def has_branching_patch_chain_incidence(
    topology: SurfaceModel,
    vertex_id: VertexId,
) -> bool:
    """Return whether a Vertex has at least three incident PatchChains."""

    return patch_chain_incidence_valence(topology, vertex_id) >= 3
