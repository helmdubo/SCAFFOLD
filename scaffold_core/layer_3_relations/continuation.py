"""
Layer: 3 - Relations

Rules:
- Build conservative ChainContinuationRelation data only.
- Use Layer 1 topology and G3b1 deterministic incidence queries.
- Do not mutate lower-layer snapshots.
- Do not derive alignment, world, feature, runtime, solve, UV, API, UI, or Blender data.
"""

from __future__ import annotations

from scaffold_core.core.evidence import Evidence
from scaffold_core.ids import PatchChainId, VertexId
from scaffold_core.layer_1_topology.model import PatchChain, SurfaceModel
from scaffold_core.layer_3_relations.patch_chain_incidence import incident_patch_chains_for_vertex
from scaffold_core.layer_3_relations.model import (
    ChainContinuationRelation,
    ContinuationKind,
    RelationSnapshot,
)


POLICY_NAME = "conservative_g3b2"


def build_chain_continuations(
    topology: SurfaceModel,
) -> tuple[ChainContinuationRelation, ...]:
    """Build conservative TERMINUS/SPLIT relations for Layer 1 PatchChains."""

    relations: list[ChainContinuationRelation] = []
    for vertex_id in sorted(topology.vertices, key=str):
        incident_uses = incident_patch_chains_for_vertex(topology, vertex_id)
        for source_use in incident_uses:
            candidates = tuple(use for use in incident_uses if use.id != source_use.id)
            if len(candidates) >= 2:
                relations.append(_split_relation(vertex_id, source_use, incident_uses, candidates))
                continue
            relations.append(_terminus_relation(vertex_id, source_use, incident_uses, candidates))
    return tuple(relations)


def continuations_for_source_use(
    snapshot: RelationSnapshot,
    patch_chain_id: PatchChainId,
) -> tuple[ChainContinuationRelation, ...]:
    """Return continuation relations for one source PatchChain."""

    return tuple(
        relation
        for relation in snapshot.chain_continuations
        if relation.source_patch_chain_id == patch_chain_id
    )


def _terminus_relation(
    vertex_id: VertexId,
    source_use: PatchChain,
    incident_uses: tuple[PatchChain, ...],
    candidates: tuple[PatchChain, ...],
) -> ChainContinuationRelation:
    return ChainContinuationRelation(
        vertex_id=vertex_id,
        source_patch_chain_id=source_use.id,
        target_patch_chain_id=None,
        kind=ContinuationKind.TERMINUS,
        confidence=1.0,
        evidence=(_evidence(incident_uses, candidates),),
    )


def _split_relation(
    vertex_id: VertexId,
    source_use: PatchChain,
    incident_uses: tuple[PatchChain, ...],
    candidates: tuple[PatchChain, ...],
) -> ChainContinuationRelation:
    return ChainContinuationRelation(
        vertex_id=vertex_id,
        source_patch_chain_id=source_use.id,
        target_patch_chain_id=None,
        kind=ContinuationKind.SPLIT,
        confidence=1.0,
        evidence=(_evidence(incident_uses, candidates),),
    )


def _evidence(
    incident_uses: tuple[PatchChain, ...],
    candidates: tuple[PatchChain, ...],
) -> Evidence:
    return Evidence(
        source="layer_3_relations.continuation",
        summary="conservative PatchChain continuation policy",
        data={
            "incident_count": len(incident_uses),
            "candidate_count": len(candidates),
            "policy": POLICY_NAME,
        },
    )
