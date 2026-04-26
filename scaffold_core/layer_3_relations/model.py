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


class AlignmentClassKind(str, Enum):
    """Conservative G3c2 alignment grouping kind."""

    LINEAR = "LINEAR"
    UNKNOWN = "UNKNOWN"


class PatchAxisSource(str, Enum):
    """Conservative G3c3 patch-axis selection source."""

    DUAL_ALIGNMENT = "DUAL_ALIGNMENT"
    SINGLE_ALIGNMENT = "SINGLE_ALIGNMENT"
    NO_ALIGNMENT = "NO_ALIGNMENT"


class RunUseEndpointRole(str, Enum):
    """Endpoint role for a patch-local directional run-use sample."""

    START = "START"
    END = "END"


class OwnerNormalSource(str, Enum):
    """Source for a junction sample owner normal."""

    LOCAL_FACE_FAN_NORMAL = "LOCAL_FACE_FAN_NORMAL"
    PATCH_AGGREGATE_NORMAL = "PATCH_AGGREGATE_NORMAL"
    LOCAL_FACE_NORMAL_AVERAGE = "LOCAL_FACE_NORMAL_AVERAGE"
    UNKNOWN = "UNKNOWN"


class JunctionDirectionRelationKind(str, Enum):
    """Directional relation between two endpoint samples at one Vertex."""

    OPPOSITE_COLLINEAR = "OPPOSITE_COLLINEAR"
    SAME_RAY_COLLINEAR = "SAME_RAY_COLLINEAR"
    ORTHOGONAL = "ORTHOGONAL"
    OBLIQUE = "OBLIQUE"
    DEGENERATE = "DEGENERATE"


class JunctionRunUseRelationKind(str, Enum):
    """Structural relation between two endpoint samples at one Vertex."""

    CONTINUATION_CANDIDATE = "CONTINUATION_CANDIDATE"
    CORNER_CONNECTOR = "CORNER_CONNECTOR"
    OBLIQUE_CONNECTOR = "OBLIQUE_CONNECTOR"
    AMBIGUOUS = "AMBIGUOUS"
    DEGENERATE = "DEGENERATE"


PatchChainEndpointRelationKind = JunctionRunUseRelationKind


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
    """Derived directional evidence for a PatchChain; not PatchChain identity."""

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
class AlignmentClass:
    id: str
    member_run_use_ids: tuple[str, ...]
    patch_ids: tuple[PatchId, ...]
    dominant_direction: Vector3
    kind: AlignmentClassKind
    confidence: float
    evidence: tuple[Evidence, ...] = ()


@dataclass(frozen=True)
class PatchAxes:
    patch_id: PatchId
    primary_alignment_class_id: str | None
    secondary_alignment_class_id: str | None
    primary_direction: Vector3
    secondary_direction: Vector3
    source: PatchAxisSource
    confidence: float
    evidence: tuple[Evidence, ...] = ()


@dataclass(frozen=True)
class PatchChainEndpointSample:
    id: str
    vertex_id: VertexId
    run_use_id: str
    chain_use_id: ChainUseId
    patch_id: PatchId
    endpoint_role: RunUseEndpointRole
    tangent_away_from_vertex: Vector3
    owner_normal: Vector3
    owner_normal_source: OwnerNormalSource
    confidence: float
    evidence: tuple[Evidence, ...] = ()


@dataclass(frozen=True)
class PatchChainEndpointRelation:
    id: str
    vertex_id: VertexId
    first_sample_id: str
    second_sample_id: str
    first_run_use_id: str
    second_run_use_id: str
    direction_dot: float
    normal_dot: float
    direction_relation: JunctionDirectionRelationKind
    kind: JunctionRunUseRelationKind
    confidence: float
    evidence: tuple[Evidence, ...] = ()


@dataclass(frozen=True)
class LoopCorner:
    id: str
    patch_id: PatchId
    loop_id: BoundaryLoopId
    vertex_id: VertexId
    previous_patch_chain_id: ChainUseId
    next_patch_chain_id: ChainUseId
    position_in_loop: int
    evidence: tuple[Evidence, ...] = ()


ChainDirectionalRunUseJunctionSample = PatchChainEndpointSample
JunctionRunUseRelation = PatchChainEndpointRelation


@dataclass(frozen=True)
class RelationSnapshot:
    patch_adjacencies: Mapping[str, PatchAdjacency] = field(default_factory=dict)
    chain_continuations: tuple[ChainContinuationRelation, ...] = ()
    chain_directional_runs: tuple[ChainDirectionalRun, ...] = ()
    chain_directional_run_uses: tuple[ChainDirectionalRunUse, ...] = ()
    loop_corners: tuple[LoopCorner, ...] = ()
    patch_chain_endpoint_samples: tuple[PatchChainEndpointSample, ...] = ()
    patch_chain_endpoint_relations: tuple[PatchChainEndpointRelation, ...] = ()
    alignment_classes: tuple[AlignmentClass, ...] = ()
    patch_axes: Mapping[PatchId, PatchAxes] = field(default_factory=dict)
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def junction_samples(self) -> tuple[PatchChainEndpointSample, ...]:
        """Legacy name for patch_chain_endpoint_samples."""

        return self.patch_chain_endpoint_samples

    @property
    def junction_run_use_relations(self) -> tuple[PatchChainEndpointRelation, ...]:
        """Legacy name for patch_chain_endpoint_relations."""

        return self.patch_chain_endpoint_relations
