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
from scaffold_core.layer_1_topology.model import ChainUse, SurfaceModel
from scaffold_core.layer_1_topology.queries import chain_use_vertices


def incident_chain_uses_for_vertex(
    topology: SurfaceModel,
    vertex_id: VertexId,
) -> tuple[ChainUse, ...]:
    """Return incident ChainUses in deterministic order.

    This is deterministic order, not geometric disk-cycle order.
    """

    incident: list[ChainUse] = []
    for use in topology.chain_uses.values():
        start_vertex_id, end_vertex_id = chain_use_vertices(topology, use.id)
        if vertex_id in (start_vertex_id, end_vertex_id):
            incident.append(use)
    return tuple(sorted(incident, key=lambda use: str(use.id)))


def junction_valence(
    topology: SurfaceModel,
    vertex_id: VertexId,
) -> int:
    """Return the deterministic incident ChainUse count for a Vertex."""

    return len(incident_chain_uses_for_vertex(topology, vertex_id))


def is_junction_like(
    topology: SurfaceModel,
    vertex_id: VertexId,
) -> bool:
    """Return whether a Vertex has at least three incident ChainUses."""

    return junction_valence(topology, vertex_id) >= 3
