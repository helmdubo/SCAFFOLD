"""
Layer: 3 - Relations

Rules:
- Build patch-local LoopCorner records from final PatchChains / ChainUses.
- Do not mutate Layer 1 topology.
- Do not build ScaffoldGraph, ScaffoldNode, feature, runtime, solve or UV data.
"""

from __future__ import annotations

from scaffold_core.core.evidence import Evidence
from scaffold_core.layer_1_topology.model import SurfaceModel
from scaffold_core.layer_1_topology.queries import chain_use_vertices
from scaffold_core.layer_3_relations.model import LoopCorner


POLICY_NAME = "g3c6_loop_corners"


def build_loop_corners(topology: SurfaceModel) -> tuple[LoopCorner, ...]:
    """Build patch-local transitions between adjacent PatchChains in each loop."""

    corners: list[LoopCorner] = []
    for loop in sorted(topology.loops.values(), key=lambda item: str(item.id)):
        if not loop.chain_use_ids:
            continue
        for position, next_patch_chain_id in enumerate(loop.chain_use_ids):
            previous_patch_chain_id = loop.chain_use_ids[position - 1]
            _previous_start, previous_end = chain_use_vertices(topology, previous_patch_chain_id)
            next_start, _next_end = chain_use_vertices(topology, next_patch_chain_id)
            vertex_id = next_start if next_start == previous_end else next_start
            corners.append(
                LoopCorner(
                    id=f"loop_corner:{loop.id}:{position}",
                    patch_id=loop.patch_id,
                    loop_id=loop.id,
                    vertex_id=vertex_id,
                    previous_patch_chain_id=previous_patch_chain_id,
                    next_patch_chain_id=next_patch_chain_id,
                    position_in_loop=position,
                    evidence=(_evidence(),),
                )
            )
    return tuple(corners)


def _evidence() -> Evidence:
    return Evidence(
        source="layer_3_relations.loop_corners",
        summary="patch-local transition between adjacent PatchChains",
        data={"policy": POLICY_NAME},
    )
