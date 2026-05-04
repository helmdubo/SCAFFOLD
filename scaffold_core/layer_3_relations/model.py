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
    PatchChainId,
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


class PatchChainEndpointRole(str, Enum):
    """Endpoint role for a patch-local directional evidence sample."""

    START = "START"
    END = "END"


class OwnerNormalSource(str, Enum):
    """Source for a PatchChain endpoint sample owner normal."""

    LOCAL_FACE_FAN_NORMAL = "LOCAL_FACE_FAN_NORMAL"
    PATCH_AGGREGATE_NORMAL = "PATCH_AGGREGATE_NORMAL"
    LOCAL_FACE_NORMAL_AVERAGE = "LOCAL_FACE_NORMAL_AVERAGE"
    UNKNOWN = "UNKNOWN"


class EndpointDirectionRelationKind(str, Enum):
    """Directional relation between two endpoint samples at one Vertex."""

    OPPOSITE_COLLINEAR = "OPPOSITE_COLLINEAR"
    SAME_RAY_COLLINEAR = "SAME_RAY_COLLINEAR"
    ORTHOGONAL = "ORTHOGONAL"
    OBLIQUE = "OBLIQUE"
    DEGENERATE = "DEGENERATE"


class PatchChainEndpointRelationKind(str, Enum):
    """Structural relation between two endpoint samples at one Vertex."""

    CONTINUATION_CANDIDATE = "CONTINUATION_CANDIDATE"
    CORNER_CONNECTOR = "CORNER_CONNECTOR"
    OBLIQUE_CONNECTOR = "OBLIQUE_CONNECTOR"
    AMBIGUOUS = "AMBIGUOUS"
    DEGENERATE = "DEGENERATE"


class ScaffoldJunctionKind(str, Enum):
    """Implemented ScaffoldJunction classification kinds."""

    SELF_SEAM = "SELF_SEAM"
    CROSS_PATCH = "CROSS_PATCH"


class ScaffoldNodeIncidentEdgeRelationKind(str, Enum):
    """Node-local relation kinds between incident ScaffoldEdges."""

    STRAIGHT_CONTINUATION_CANDIDATE = "STRAIGHT_CONTINUATION_CANDIDATE"
    SURFACE_CONTINUATION_CANDIDATE = "SURFACE_CONTINUATION_CANDIDATE"
    SURFACE_SLIDING_CONTINUATION_CANDIDATE = "SURFACE_SLIDING_CONTINUATION_CANDIDATE"
    CROSS_SURFACE_CONNECTOR = "CROSS_SURFACE_CONNECTOR"
    ORTHOGONAL_CORNER = "ORTHOGONAL_CORNER"
    OBLIQUE_CONNECTOR = "OBLIQUE_CONNECTOR"
    SAME_RAY_AMBIGUOUS = "SAME_RAY_AMBIGUOUS"
    MISSING_ENDPOINT_EVIDENCE = "MISSING_ENDPOINT_EVIDENCE"
    DEGRADED = "DEGRADED"


class SharedChainPatchChainRelationKind(str, Enum):
    """Graph-level relation kinds for ScaffoldEdges sharing one Chain."""

    CROSS_PATCH_SHARED_CHAIN = "CROSS_PATCH_SHARED_CHAIN"


@dataclass(frozen=True)
class PatchAdjacency:
    id: str
    first_patch_id: PatchId
    second_patch_id: PatchId
    chain_id: ChainId
    first_patch_chain_id: PatchChainId
    second_patch_chain_id: PatchChainId
    shared_length: float
    signed_angle_radians: float
    dihedral_kind: DihedralKind


@dataclass(frozen=True)
class ChainContinuationRelation:
    vertex_id: VertexId
    source_patch_chain_id: PatchChainId
    target_patch_chain_id: PatchChainId | None
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
class PatchChainDirectionalEvidence:
    """Derived directional evidence for a PatchChain; not PatchChain identity."""

    id: str
    directional_run_id: str
    parent_chain_id: ChainId
    patch_chain_id: PatchChainId
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
    member_directional_evidence_ids: tuple[str, ...]
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
    directional_evidence_id: str
    patch_chain_id: PatchChainId
    patch_id: PatchId
    endpoint_role: PatchChainEndpointRole
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
    first_directional_evidence_id: str
    second_directional_evidence_id: str
    direction_dot: float
    normal_dot: float
    direction_relation: EndpointDirectionRelationKind
    kind: PatchChainEndpointRelationKind
    confidence: float
    evidence: tuple[Evidence, ...] = ()


@dataclass(frozen=True)
class LoopCorner:
    id: str
    patch_id: PatchId
    loop_id: BoundaryLoopId
    vertex_id: VertexId
    previous_patch_chain_id: PatchChainId
    next_patch_chain_id: PatchChainId
    position_in_loop: int
    evidence: tuple[Evidence, ...] = ()


@dataclass(frozen=True)
class ScaffoldNode:
    """Graph-level node assembled from patch-local corner and endpoint evidence."""

    id: str
    vertex_ids: tuple[VertexId, ...]
    source_vertex_ids: tuple[SourceVertexId, ...]
    loop_corner_ids: tuple[str, ...]
    patch_chain_endpoint_sample_ids: tuple[str, ...]
    patch_chain_endpoint_relation_ids: tuple[str, ...]
    incident_patch_chain_ids: tuple[PatchChainId, ...]
    patch_ids: tuple[PatchId, ...]
    confidence: float
    evidence: tuple[Evidence, ...] = ()


@dataclass(frozen=True)
class ScaffoldEdge:
    """Graph-level edge view of one final PatchChain."""

    id: str
    patch_chain_id: PatchChainId
    chain_id: ChainId
    patch_id: PatchId
    loop_id: BoundaryLoopId
    start_scaffold_node_id: str
    end_scaffold_node_id: str
    confidence: float
    evidence: tuple[Evidence, ...] = ()


@dataclass(frozen=True)
class ScaffoldGraph:
    """Connectivity-only graph over ScaffoldNode and ScaffoldEdge records."""

    id: str
    node_ids: tuple[str, ...]
    edge_ids: tuple[str, ...]
    confidence: float
    evidence: tuple[Evidence, ...] = ()


@dataclass(frozen=True)
class ScaffoldJunction:
    """Graph-level classification overlay on one existing ScaffoldNode."""

    id: str
    kind: ScaffoldJunctionKind
    policy: str
    scaffold_node_id: str
    matched_chain_id: ChainId | None
    patch_id: PatchId | None
    chain_ids: tuple[ChainId, ...]
    patch_ids: tuple[PatchId, ...]
    loop_ids: tuple[BoundaryLoopId, ...]
    scaffold_edge_ids: tuple[str, ...]
    patch_chain_ids: tuple[PatchChainId, ...]
    confidence: float
    evidence: tuple[Evidence, ...] = ()


@dataclass(frozen=True)
class ScaffoldNodeIncidentEdgeRelation:
    """Node-local relation between two existing incident ScaffoldEdges."""

    id: str
    kind: ScaffoldNodeIncidentEdgeRelationKind
    policy: str
    scaffold_node_id: str
    first_scaffold_edge_id: str
    second_scaffold_edge_id: str
    first_patch_chain_id: PatchChainId
    second_patch_chain_id: PatchChainId
    first_endpoint_role: PatchChainEndpointRole
    second_endpoint_role: PatchChainEndpointRole
    first_endpoint_sample_id: str | None
    second_endpoint_sample_id: str | None
    patch_chain_endpoint_relation_id: str | None
    direction_dot: float | None
    normal_dot: float | None
    confidence: float
    evidence: tuple[Evidence, ...] = ()


@dataclass(frozen=True)
class SideSurfaceContinuityEvidence:
    """Evidence-only same-side surface flow between two edge-end occurrences."""

    id: str
    scaffold_node_id: str
    first_scaffold_edge_id: str
    second_scaffold_edge_id: str
    first_patch_chain_id: PatchChainId
    second_patch_chain_id: PatchChainId
    first_endpoint_role: PatchChainEndpointRole
    second_endpoint_role: PatchChainEndpointRole
    patch_id: PatchId
    loop_id: BoundaryLoopId
    first_chain_id: ChainId
    second_chain_id: ChainId
    vertex_id: VertexId
    source_vertex_ids: tuple[SourceVertexId, ...]
    first_endpoint_sample_id: str
    second_endpoint_sample_id: str
    first_direction_family_id: str | None
    second_direction_family_id: str | None
    direction_family_compatible: bool
    blocked_by_direction_family: bool
    normal_dot: float
    normal_evidence_source: str
    confidence: float
    evidence: tuple[Evidence, ...] = ()


@dataclass(frozen=True)
class SharedChainPatchChainRelation:
    """Graph-level relation between final PatchChains sharing one Chain."""

    id: str
    kind: SharedChainPatchChainRelationKind
    policy: str
    chain_id: ChainId
    first_scaffold_edge_id: str
    second_scaffold_edge_id: str
    first_patch_chain_id: PatchChainId
    second_patch_chain_id: PatchChainId
    first_patch_id: PatchId
    second_patch_id: PatchId
    patch_adjacency_id: str | None
    confidence: float
    evidence: tuple[Evidence, ...] = ()


@dataclass(frozen=True)
class ScaffoldContinuityComponent:
    """Evidence-only continuity-family view over existing ScaffoldEdges."""

    id: str
    scaffold_edge_ids: tuple[str, ...]
    scaffold_node_ids: tuple[str, ...]
    propagating_incident_relation_ids: tuple[str, ...]
    ambiguous_incident_relation_ids: tuple[str, ...]
    blocked_incident_relation_ids: tuple[str, ...]
    propagation_policy: str
    is_ambiguous: bool
    confidence: float
    evidence: tuple[Evidence, ...] = ()


@dataclass(frozen=True)
class RelationSnapshot:
    patch_adjacencies: Mapping[str, PatchAdjacency] = field(default_factory=dict)
    chain_continuations: tuple[ChainContinuationRelation, ...] = ()
    chain_directional_runs: tuple[ChainDirectionalRun, ...] = ()
    patch_chain_directional_evidence: tuple[PatchChainDirectionalEvidence, ...] = ()
    loop_corners: tuple[LoopCorner, ...] = ()
    patch_chain_endpoint_samples: tuple[PatchChainEndpointSample, ...] = ()
    patch_chain_endpoint_relations: tuple[PatchChainEndpointRelation, ...] = ()
    scaffold_nodes: tuple[ScaffoldNode, ...] = ()
    scaffold_edges: tuple[ScaffoldEdge, ...] = ()
    scaffold_graph: ScaffoldGraph | None = None
    scaffold_junctions: tuple[ScaffoldJunction, ...] = ()
    side_surface_continuity_evidence: tuple[SideSurfaceContinuityEvidence, ...] = ()
    scaffold_node_incident_edge_relations: tuple[ScaffoldNodeIncidentEdgeRelation, ...] = ()
    shared_chain_patch_chain_relations: tuple[SharedChainPatchChainRelation, ...] = ()
    scaffold_continuity_components: tuple[ScaffoldContinuityComponent, ...] = ()
    alignment_classes: tuple[AlignmentClass, ...] = ()
    patch_axes: Mapping[PatchId, PatchAxes] = field(default_factory=dict)
    diagnostics: tuple[Diagnostic, ...] = ()
