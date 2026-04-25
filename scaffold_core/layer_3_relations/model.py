"""
Layer: 3 - Relations

Rules:
- Frozen derived relation dataclasses only.
- No topology or geometry mutation.
- No feature, runtime, solve, UV, API, UI, or Blender logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from scaffold_core.core.diagnostics import Diagnostic
from scaffold_core.core.evidence import Evidence
from scaffold_core.ids import (
    BoundaryLoopId,
    ChainId,
    ChainUseId,
    PatchId,
    SourceEdgeId,
    SourceVertexId,
    VertexId,
)
from scaffold_core.layer_2_geometry.facts import Vector3


class DihedralKind(str, Enum):
    """Coarse signed dihedral classification for adjacent Patches."""

    UNDEFINED = "UNDEFINED"
    COPLANAR = "COPLANAR"
    CONVEX = "CONVEX"
    CONCAVE = "CONCAVE"


class ContinuationKind(str, Enum):
    """Conservative G3b2 continuation relation kind."""

    TERMINUS = "TERMINUS"
    SPLIT = "SPLIT"
    SMOOTH = "SMOOTH"
    TURN = "TURN"


@dataclass(frozen=True)
class PatchAdjacency:
    id: str
    first_patch_id: PatchId
    second_patch_id: PatchId
    chain_id: ChainId
    first_chain_use_id: ChainUseId
    second_chain_use_id: ChainUseId
    shared_length: float
    signed_angle_radians: float
    dihedral_kind: DihedralKind


@dataclass(frozen=True)
class ChainContinuationRelation:
    junction_vertex_id: VertexId
    source_chain_use_id: ChainUseId
    target_chain_use_id: ChainUseId | None
    kind: ContinuationKind
    confidence: float
    evidence: tuple[Evidence, ...] = ()


@dataclass(frozen=True)
class ChainDirectionalRun:
    id: str
    parent_chain_id: ChainId
    source_edge_ids: tuple[SourceEdgeId, ...]
    segment_indices: tuple[int, ...]
    start_source_vertex_id: SourceVertexId
    end_source_vertex_id: SourceVertexId
    length: float
    direction: Vector3
    is_closed: bool
    confidence: float
    evidence: tuple[Evidence, ...] = ()


@dataclass(frozen=True)
class ChainDirectionalRunUse:
    id: str
    directional_run_id: str
    parent_chain_id: ChainId
    chain_use_id: ChainUseId
    patch_id: PatchId
    loop_id: BoundaryLoopId
    position_in_loop: int
    orientation_sign: int
    source_edge_ids: tuple[SourceEdgeId, ...]
    segment_indices: tuple[int, ...]
    start_source_vertex_id: SourceVertexId
    end_source_vertex_id: SourceVertexId
    length: float
    direction: Vector3
    confidence: float
    evidence: tuple[Evidence, ...] = ()


@dataclass(frozen=True)
class RelationSnapshot:
    patch_adjacencies: Mapping[str, PatchAdjacency] = field(default_factory=dict)
    chain_continuations: tuple[ChainContinuationRelation, ...] = ()
    chain_directional_runs: tuple[ChainDirectionalRun, ...] = ()
    chain_directional_run_uses: tuple[ChainDirectionalRunUse, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()
