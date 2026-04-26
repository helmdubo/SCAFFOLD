"""
Layer: 2 - Geometry

Rules:
- Frozen geometry fact dataclasses only.
- No topology building, relation derivation, feature interpretation, or solve logic.
- Store measured data only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from scaffold_core.core.diagnostics import Diagnostic
from scaffold_core.ids import ChainId, PatchId, SourceEdgeId, SourceFaceId, SourceVertexId, VertexId


Vector3 = tuple[float, float, float]


class ChainShapeHint(str, Enum):
    """Raw geometric shape hint for a Chain."""

    UNKNOWN = "UNKNOWN"
    STRAIGHT = "STRAIGHT"
    SAWTOOTH_STRAIGHT = "SAWTOOTH_STRAIGHT"


@dataclass(frozen=True)
class PatchGeometryFacts:
    patch_id: PatchId
    area: float
    normal: Vector3
    centroid: Vector3


@dataclass(frozen=True)
class ChainSegmentGeometryFacts:
    chain_id: ChainId
    source_edge_id: SourceEdgeId
    segment_index: int
    start_source_vertex_id: SourceVertexId
    end_source_vertex_id: SourceVertexId
    start_position: Vector3
    end_position: Vector3
    vector: Vector3
    length: float
    direction: Vector3


@dataclass(frozen=True)
class ChainGeometryFacts:
    chain_id: ChainId
    length: float
    chord_length: float
    chord_direction: Vector3
    straightness: float
    detour_ratio: float
    shape_hint: ChainShapeHint = ChainShapeHint.UNKNOWN
    source_vertex_run: tuple[SourceVertexId, ...] = ()
    segments: tuple[ChainSegmentGeometryFacts, ...] = ()


@dataclass(frozen=True)
class VertexGeometryFacts:
    vertex_id: VertexId
    position: Vector3


@dataclass(frozen=True)
class VertexFanGeometryFacts:
    id: str
    patch_id: PatchId
    vertex_id: VertexId
    source_vertex_id: SourceVertexId
    source_face_ids: tuple[SourceFaceId, ...]
    area: float
    normal: Vector3


@dataclass(frozen=True)
class GeometryFactSnapshot:
    patch_facts: Mapping[PatchId, PatchGeometryFacts] = field(default_factory=dict)
    chain_facts: Mapping[ChainId, ChainGeometryFacts] = field(default_factory=dict)
    vertex_facts: Mapping[VertexId, VertexGeometryFacts] = field(default_factory=dict)
    vertex_fan_facts: Mapping[str, VertexFanGeometryFacts] = field(default_factory=dict)
    diagnostics: tuple[Diagnostic, ...] = ()
