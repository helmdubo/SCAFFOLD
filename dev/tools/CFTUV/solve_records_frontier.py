from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from mathutils import Vector

from .model import (
    AnchorAdjustment,
    BoundaryChain,
    ChainGapReport,
    ChainRef,
    FrameRole,
    PatchNode,
    PlacementSourceKind,
    ScaffoldChainPlacement,
    ScaffoldQuiltPlacement,
)
from .solve_records_common import CHAIN_FRONTIER_THRESHOLD
from .solve_records_domain import AttachmentNeighborRef, SeamRelationProfile, SolveView


PointRegistryKey = tuple[int, int, int, int]
VertexPlacementRef = tuple[ChainRef, int]
PointRegistry = dict[PointRegistryKey, Vector]
VertexPlacementMap = dict[int, list[VertexPlacementRef]]
AnchorRefPair = tuple[Optional[ChainRef], Optional[ChainRef]]


def _point_registry_key(chain_ref: ChainRef, source_point_index: int) -> PointRegistryKey:
    return (chain_ref[0], chain_ref[1], chain_ref[2], source_point_index)


@dataclass(frozen=True)
class ChainPoolEntry:
    chain_ref: ChainRef
    chain: BoundaryChain
    node: PatchNode


@dataclass(frozen=True, order=True)
class ClosureFollowCandidateRank:
    anchor_count: int
    shared_vert_count: int
    length_bias: float


@dataclass(frozen=True, order=True)
class FreeIngressCandidateRank:
    downstream_cross_patch: int
    downstream_count: int
    placed_in_patch: int
    downstream_max_length: float


@dataclass(frozen=True, order=True)
class TreeIngressCandidateRank:
    role_priority: int
    downstream_hv_count: int
    downstream_max_length: float
    chain_length: float


@dataclass(frozen=True)
class FrontierTopologyFacts:
    is_hv: bool = False
    is_bridge: bool = False
    same_patch_anchor_count: int = 0
    cross_patch_anchor_count: int = 0
    hv_adjacency: int = 0
    would_be_connected: bool = True
    is_secondary_closure: bool = False


@dataclass(frozen=True, order=True)
class FrontierRank:
    """Lexicographic rank for main-frontier candidate selection."""

    viability_tier: int
    role_tier: int
    ingress_tier: int
    patch_fit_tier: int
    anchor_tier: int
    closure_risk_tier: int
    local_score: float
    tie_length: float


@dataclass(frozen=True)
class FrontierRankBreakdown:
    viability_label: str = ""
    role_label: str = ""
    ingress_label: str = ""
    patch_fit_label: str = ""
    anchor_label: str = ""
    closure_label: str = ""
    seam_label: str = ""
    shape_label: str = ""
    summary: str = ""


@dataclass(frozen=True)
class PatchShapeProfile:
    """Coarse patch prior kept for scoring context and diagnostics."""

    elongation: float = 0.0
    rectilinearity: float = 0.0
    hole_ratio: float = 0.0
    frame_dominance: float = 0.0
    seam_multiplicity_hint: float = 0.0


@dataclass(frozen=True)
class PatchScoringContext:
    patch_id: int
    placed_chain_count: int = 0
    placed_h_count: int = 0
    placed_v_count: int = 0
    placed_free_count: int = 0
    placed_ratio: float = 0.0
    hv_coverage_ratio: float = 0.0
    same_patch_backbone_strength: float = 0.0
    closure_pressure: float = 0.0
    is_untouched: bool = True
    has_secondary_seam_pairs: bool = False
    shape_profile: Optional[PatchShapeProfile] = None


@dataclass(frozen=True)
class CornerScoringHints:
    start_turn_strength: float = 0.0
    end_turn_strength: float = 0.0
    orthogonal_turn_count: int = 0
    same_role_continuation_strength: float = 0.0
    has_geometric_corner: bool = False
    has_junction_corner: bool = False


@dataclass(frozen=True)
class FrontierLocalScoreDetails:
    length_factor: float = 0.0
    downstream_count: int = 0
    downstream_bonus: float = 0.0
    isolation_penalty: float = 0.0
    structural_free_bonus: float = 0.0
    seam_bonus: float = 0.0
    corner_bonus: float = 0.0
    shape_bonus: float = 0.0


@dataclass(frozen=True)
class FrontierRescueGap:
    candidate_class: str = ""
    main_known: int = 0
    main_score: float = -1.0
    threshold_gap: float = 0.0
    main_viable: bool = False
    hv_adjacency: int = 0
    downstream_support: int = 0
    shared_vert_count: int = 0
    main_rank: Optional[FrontierRank] = None
    main_rank_breakdown: Optional[FrontierRankBreakdown] = None
    summary: str = ""


@dataclass(frozen=True)
class FrontierRescueGapClassCount:
    candidate_class: str
    count: int


@dataclass(frozen=True)
class DualAnchorRectificationPreview:
    start_anchor: Optional["ChainAnchor"]
    end_anchor: Optional["ChainAnchor"]
    reason: str = ""
    anchor_adjustments: tuple[AnchorAdjustment, ...] = ()


@dataclass(frozen=True)
class ResolvedCandidateAnchors:
    start_anchor: Optional["ChainAnchor"]
    end_anchor: Optional["ChainAnchor"]
    known: int
    reason: str = ""
    anchor_adjustments: tuple[AnchorAdjustment, ...] = ()


@dataclass(frozen=True)
class FoundCandidateAnchors:
    start_anchor: Optional["ChainAnchor"]
    end_anchor: Optional["ChainAnchor"]


@dataclass(frozen=True)
class AnchorPairSafetyDecision:
    is_safe: bool
    reason: str = ""


@dataclass(frozen=True)
class DualAnchorClosureDecision:
    can_close: bool
    reason: str = ""


@dataclass(frozen=True)
class ClosurePreconstraintApplication:
    start_anchor: Optional["ChainAnchor"]
    end_anchor: Optional["ChainAnchor"]
    direction_override: Optional[Vector] = None
    reason: str = ""


@dataclass(frozen=True)
class ClosurePreconstraintOptionResult:
    metric: Optional["ClosurePreconstraintMetric"]
    anchor_label: str = ""
    direction_label: str = ""
    start_anchor: Optional["ChainAnchor"] = None
    end_anchor: Optional["ChainAnchor"] = None
    direction_override: Optional[Vector] = None


@dataclass(frozen=True)
class ClosureFollowUvBuildResult:
    uv_points: Optional[list[Vector]]
    follow_mode: str = ""
    shared_vert_count: int = 0


@dataclass(frozen=True)
class PatchChainGapDiagnostics:
    gap_reports: tuple[ChainGapReport, ...] = ()
    max_chain_gap: float = 0.0


@dataclass(frozen=True)
class ClosureFollowPlacementCandidate:
    rank: ClosureFollowCandidateRank
    chain_ref: ChainRef
    chain: BoundaryChain
    partner_ref: ChainRef
    effective_role: FrameRole
    uv_points: list[Vector]
    follow_mode: str
    shared_vert_count: int


@dataclass(frozen=True)
class FreeIngressPlacementCandidate:
    rank: FreeIngressCandidateRank
    chain_ref: ChainRef
    chain: BoundaryChain
    start_anchor: Optional["ChainAnchor"]
    end_anchor: Optional["ChainAnchor"]
    anchor_adjustments: tuple[AnchorAdjustment, ...]
    uv_points: list[Vector]
    downstream_refs: tuple[ChainRef, ...]
    downstream_cross_patch: int


@dataclass(frozen=True)
class TreeIngressPlacementCandidate:
    rank: TreeIngressCandidateRank
    chain_ref: ChainRef
    chain: BoundaryChain
    effective_role: FrameRole
    start_anchor: Optional["ChainAnchor"]
    end_anchor: Optional["ChainAnchor"]
    anchor_adjustments: tuple[AnchorAdjustment, ...]
    uv_points: list[Vector]
    downstream_hv_count: int
    role_priority: int
    hv_adjacency: int


@dataclass(frozen=True)
class SeedChainChoice:
    loop_index: int
    chain_index: int
    chain: BoundaryChain
    score: float


@dataclass(frozen=True)
class SeedPlacementResult:
    placement: ScaffoldChainPlacement
    uv_points: list[Vector]


@dataclass(frozen=True)
class DirectionOption:
    label: str
    direction_override: Optional[Vector]


@dataclass(frozen=True)
class AnchorOption:
    label: str
    start_anchor: Optional["ChainAnchor"]
    end_anchor: Optional["ChainAnchor"]


@dataclass(frozen=True)
class SharedClosureUvOffsets:
    sampled_shared_vert_count: int = 0
    shared_uv_delta_max: float = 0.0
    shared_uv_delta_mean: float = 0.0
    axis_phase_offset_max: float = 0.0
    axis_phase_offset_mean: float = 0.0
    cross_axis_offset_max: float = 0.0
    cross_axis_offset_mean: float = 0.0


@dataclass(frozen=True, order=True)
class ClosurePreconstraintMetric:
    same_patch_gap_max: float = 0.0
    axis_phase_offset_max: float = 0.0
    all_gap_max: float = 0.0
    span_mismatch: float = 0.0
    axis_phase_offset_mean: float = 0.0
    all_gap_mean: float = 0.0


@dataclass(frozen=True)
class ChainAnchor:
    uv: Vector
    source_ref: ChainRef
    source_point_index: int
    source_kind: PlacementSourceKind = PlacementSourceKind.SAME_PATCH


@dataclass(frozen=True)
class FrontierCandidateEval:
    raw_start_anchor: Optional[ChainAnchor]
    raw_end_anchor: Optional[ChainAnchor]
    start_anchor: Optional[ChainAnchor]
    end_anchor: Optional[ChainAnchor]
    known: int
    placed_in_patch: int
    effective_role: FrameRole = FrameRole.FREE
    anchor_reason: str = ""
    anchor_adjustments: tuple[AnchorAdjustment, ...] = ()
    closure_dir_override: Optional[Vector] = None
    score: float = -1.0
    length_factor: float = 0.0
    downstream_count: int = 0
    downstream_bonus: float = 0.0
    isolation_preview: bool = True
    isolation_penalty: float = 0.0
    structural_free_bonus: float = 0.0
    hv_adjacency: int = 0
    rank: Optional[FrontierRank] = None
    rank_breakdown: Optional[FrontierRankBreakdown] = None
    patch_context: Optional[PatchScoringContext] = None
    corner_hints: Optional[CornerScoringHints] = None
    seam_relation: Optional[SeamRelationProfile] = None
    seam_bonus: float = 0.0
    corner_bonus: float = 0.0
    shape_bonus: float = 0.0
    rescue_gap: Optional[FrontierRescueGap] = None


@dataclass(frozen=True)
class FrontierStopDiagnostics:
    remaining_count: int
    no_anchor_count: int
    low_score_count: int
    rejected_count: int
    placed_patch_ids: tuple[int, ...] = ()
    untouched_patch_ids: tuple[int, ...] = ()
    no_anchor_patch_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class FrontierPlacementCandidate:
    chain_ref: ChainRef
    chain: BoundaryChain
    node: PatchNode
    start_anchor: Optional[ChainAnchor]
    end_anchor: Optional[ChainAnchor]
    effective_role: FrameRole
    anchor_reason: str = ""
    anchor_adjustments: tuple[AnchorAdjustment, ...] = ()
    closure_dir_override: Optional[Vector] = None
    score: float = -1.0
    length_factor: float = 0.0
    downstream_count: int = 0
    downstream_bonus: float = 0.0
    isolation_preview: bool = True
    isolation_penalty: float = 0.0
    structural_free_bonus: float = 0.0
    hv_adjacency: int = 0
    rank: Optional[FrontierRank] = None
    rank_breakdown: Optional[FrontierRankBreakdown] = None
    patch_context: Optional[PatchScoringContext] = None
    corner_hints: Optional[CornerScoringHints] = None
    seam_relation: Optional[SeamRelationProfile] = None
    seam_bonus: float = 0.0
    corner_bonus: float = 0.0
    shape_bonus: float = 0.0


@dataclass(frozen=True)
class FrontierBootstrapResult:
    runtime_policy: "FrontierRuntimePolicy"
    seed_ref: ChainRef
    seed_chain: BoundaryChain
    seed_score: float


@dataclass(frozen=True)
class FrontierBootstrapAttempt:
    result: Optional[FrontierBootstrapResult]
    error: str = ""


@dataclass(frozen=True)
class FinalizedQuiltScaffold:
    quilt_scaffold: ScaffoldQuiltPlacement
    untouched_patch_ids: list[int]


@dataclass(frozen=True)
class FrameGroupMember:
    ref: ChainRef
    cross_uv: float
    weight: float
    patch_id: int


__all__ = [
    "AnchorAdjustment",
    "PointRegistryKey",
    "VertexPlacementRef",
    "PointRegistry",
    "VertexPlacementMap",
    "AnchorRefPair",
    "_point_registry_key",
    "ChainPoolEntry",
    "ClosureFollowCandidateRank",
    "FreeIngressCandidateRank",
    "TreeIngressCandidateRank",
    "FrontierTopologyFacts",
    "FrontierRank",
    "FrontierRankBreakdown",
    "PatchShapeProfile",
    "PatchScoringContext",
    "CornerScoringHints",
    "FrontierLocalScoreDetails",
    "FrontierRescueGap",
    "FrontierRescueGapClassCount",
    "DualAnchorRectificationPreview",
    "ResolvedCandidateAnchors",
    "FoundCandidateAnchors",
    "AnchorPairSafetyDecision",
    "DualAnchorClosureDecision",
    "ClosurePreconstraintApplication",
    "ClosurePreconstraintOptionResult",
    "ClosureFollowUvBuildResult",
    "PatchChainGapDiagnostics",
    "ClosureFollowPlacementCandidate",
    "FreeIngressPlacementCandidate",
    "TreeIngressPlacementCandidate",
    "SeedChainChoice",
    "SeedPlacementResult",
    "DirectionOption",
    "AnchorOption",
    "SharedClosureUvOffsets",
    "ClosurePreconstraintMetric",
    "ChainAnchor",
    "FrontierCandidateEval",
    "FrontierStopDiagnostics",
    "FrontierPlacementCandidate",
    "FrontierBootstrapResult",
    "FrontierBootstrapAttempt",
    "FinalizedQuiltScaffold",
    "FrameGroupMember",
    "CHAIN_FRONTIER_THRESHOLD",
]
