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
from scaffold_core.layer_0_source.marks import SourceFaceStrength, SourceMark


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
    """One source face; edge_ids[i] joins vertex_ids[i] and vertex_ids[i + 1].

    face_strength is the raw Blender Face Strength mark of the face, None when
    the mesh has no such attribute or the stored value is none of the three.
    """

    id: SourceFaceId
    vertex_ids: tuple[SourceVertexId, ...]
    edge_ids: tuple[SourceEdgeId, ...]
    face_strength: SourceFaceStrength | None = None


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
    marks: Sequence[SourceMark] = field(default_factory=tuple)
    checksum: str | None = None
