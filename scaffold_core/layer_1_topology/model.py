"""
Layer: 1 — Topology

Rules:
- No geometry facts here.
- No H/V, WALL/FLOOR/SLOPE, feature, or runtime roles here.
- PatchChain is the preferred term for the final oriented boundary-use entity.
- This module may import ids and standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Sequence

from scaffold_core.ids import (
    BoundaryLoopId,
    ChainId,
    PatchChainId,
    PatchId,
    ShellId,
    SourceEdgeId,
    SourceFaceId,
    SourceVertexId,
    SurfaceModelId,
    VertexId,
)


class BoundaryLoopKind(str, Enum):
    """Patch boundary loop kind."""

    OUTER = "OUTER"
    INNER = "INNER"
    DEGRADED = "DEGRADED"


@dataclass(frozen=True)
class Vertex:
    id: VertexId
    source_vertex_ids: tuple[SourceVertexId, ...] = ()


@dataclass(frozen=True)
class Chain:
    id: ChainId
    start_vertex_id: VertexId
    end_vertex_id: VertexId
    source_edge_ids: tuple[SourceEdgeId, ...] = ()


@dataclass(frozen=True)
class PatchChain:
    """Final patch-local oriented occurrence of a Chain in a BoundaryLoop."""

    id: PatchChainId
    chain_id: ChainId
    patch_id: PatchId
    loop_id: BoundaryLoopId
    orientation_sign: int
    position_in_loop: int
    start_vertex_id: VertexId | None = None
    end_vertex_id: VertexId | None = None

    def __post_init__(self) -> None:
        if self.orientation_sign not in (-1, 1):
            raise ValueError("PatchChain.orientation_sign must be +1 or -1")


@dataclass(frozen=True)
class BoundaryLoop:
    id: BoundaryLoopId
    patch_id: PatchId
    kind: BoundaryLoopKind
    patch_chain_ids: tuple[PatchChainId, ...]
    loop_index: int


@dataclass(frozen=True)
class Patch:
    id: PatchId
    shell_id: ShellId
    loop_ids: tuple[BoundaryLoopId, ...]
    source_face_ids: tuple[SourceFaceId, ...] = ()


@dataclass(frozen=True)
class Shell:
    id: ShellId
    patch_ids: tuple[PatchId, ...]


@dataclass(frozen=True)
class SurfaceModel:
    id: SurfaceModelId
    shells: Mapping[ShellId, Shell] = field(default_factory=dict)
    patches: Mapping[PatchId, Patch] = field(default_factory=dict)
    loops: Mapping[BoundaryLoopId, BoundaryLoop] = field(default_factory=dict)
    chains: Mapping[ChainId, Chain] = field(default_factory=dict)
    patch_chains: Mapping[PatchChainId, PatchChain] = field(default_factory=dict)
    vertices: Mapping[VertexId, Vertex] = field(default_factory=dict)
