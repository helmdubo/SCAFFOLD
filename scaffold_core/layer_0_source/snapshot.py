"""
Layer: 0 — Source

Rules:
- Source snapshot data models only.
- No topology entities, geometry facts, relations, features, or runtime solve here.
- No direct Blender access here; Blender conversion lives in blender_io.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from scaffold_core.ids import (
    SourceEdgeId,
    SourceFaceId,
    SourceMeshId,
    SourceVertexId,
)


@dataclass(frozen=True)
class MeshVertexRef:
    id: SourceVertexId
    position: tuple[float, float, float]


@dataclass(frozen=True)
class MeshEdgeRef:
    id: SourceEdgeId
    vertex_ids: tuple[SourceVertexId, SourceVertexId]


@dataclass(frozen=True)
class MeshFaceRef:
    id: SourceFaceId
    vertex_ids: tuple[SourceVertexId, ...]
    edge_ids: tuple[SourceEdgeId, ...]


@dataclass(frozen=True)
class SourceMeshSnapshot:
    """Immutable source mesh snapshot.

    checksum is optional source provenance for future rebuild detection.
    G1 fixtures may leave it None.
    """

    id: SourceMeshId
    vertices: Mapping[SourceVertexId, MeshVertexRef]
    edges: Mapping[SourceEdgeId, MeshEdgeRef]
    faces: Mapping[SourceFaceId, MeshFaceRef]
    selected_face_ids: Sequence[SourceFaceId] = field(default_factory=tuple)
    checksum: str | None = None
