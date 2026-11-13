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
from scaffold_core.ids import ChainId, PatchChainId, PatchId, SourceEdgeId, SourceFaceId, SourceVertexId, VertexId


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
    # Length of the sum of the patch's triangle area vectors (the unnormalised
    # normal): the area for a planar patch, about 0 when they cancel.
    area_vector_length: float


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
    # Plane the chain's vertices lie in; None when they are collinear.
    plane_normal: Vector3 | None = None
    # Largest vertex distance from that plane through the vertex mean.
    plane_deviation: float = 0.0
    # Largest vertex distance from the chord line.
    chord_deviation: float = 0.0


@dataclass(frozen=True)
class PatchChainGeometryFacts:
    """Per-side measurement of a Chain on one PatchChain's own patch faces."""

    patch_chain_id: PatchChainId
    chain_id: ChainId
    patch_id: PatchId
    # asin(|dot(chain plane normal, side face normal)|) over the chain edges;
    # None when the chain has no plane or no side face is known.
    tilt_min: float | None = None
    tilt_max: float | None = None
    # Per chain segment, in segment order: the source face of this patch on
    # this side of the edge, and its unit normal; None when not determinable.
    segment_side_face_ids: tuple[SourceFaceId | None, ...] = ()
    segment_side_normals: tuple[Vector3 | None, ...] = ()


@dataclass(frozen=True)
class VertexGeometryFacts:
    vertex_id: VertexId
    position: Vector3
    interior_angle_sum: float = 0.0
    angle_defect: float = 0.0
    is_boundary: bool = False


@dataclass(frozen=True)
class LocalFaceFanGeometryFacts:
    """Patch-local face-fan measurement for endpoint normal evidence."""

    id: str
    patch_id: PatchId
    vertex_id: VertexId
    source_vertex_id: SourceVertexId
    source_face_ids: tuple[SourceFaceId, ...]
    area: float
    normal: Vector3
    interior_angle_sum: float


@dataclass(frozen=True)
class GeometryFactSnapshot:
    patch_facts: Mapping[PatchId, PatchGeometryFacts] = field(default_factory=dict)
    chain_facts: Mapping[ChainId, ChainGeometryFacts] = field(default_factory=dict)
    vertex_facts: Mapping[VertexId, VertexGeometryFacts] = field(default_factory=dict)
    local_face_fan_facts: Mapping[str, LocalFaceFanGeometryFacts] = field(default_factory=dict)
    patch_chain_facts: Mapping[PatchChainId, PatchChainGeometryFacts] = field(default_factory=dict)
    # 3D length of every source edge of the model's faces (chain or interior edge alike).
    edge_length_by_source_edge: Mapping[SourceEdgeId, float] = field(default_factory=dict)
    diagnostics: tuple[Diagnostic, ...] = ()
