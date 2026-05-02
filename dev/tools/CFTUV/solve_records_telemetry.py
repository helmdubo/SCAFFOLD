from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .model import ChainRef, FrameRole
from .solve_records_frontier import (
    CornerScoringHints,
    FrontierRank,
    FrontierRankBreakdown,
    FrontierRescueGap,
    FrontierRescueGapClassCount,
    PatchScoringContext,
    SeamRelationProfile,
)


@dataclass(frozen=True)
class FrontierPlacementRecord:
    """Telemetry record for one frontier placement step."""

    iteration: int
    chain_ref: ChainRef
    frame_role: FrameRole
    placement_path: str
    score: float
    anchor_count: int
    start_anchor_kind: str
    end_anchor_kind: str
    placed_in_patch_before: int
    is_first_in_patch: bool
    is_bridge: bool
    is_corner_split: bool
    neighbor_kind: str
    is_closure_pair: bool
    closure_preconstraint_applied: bool
    anchor_adjustment_applied: bool
    direction_inherited: bool
    chain_length_uv: float
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
class FrontierStallRecord:
    """Telemetry record for one frontier stall event."""

    iteration: int
    best_rejected_score: float
    best_rejected_ref: Optional[ChainRef]
    best_rejected_role: Optional[FrameRole]
    best_rejected_anchor_count: int
    available_count: int
    no_anchor_count: int
    below_threshold_count: int
    rescue_attempted: str
    rescue_succeeded: bool
    patches_with_placed: int
    patches_untouched: int


@dataclass(frozen=True)
class QuiltFrontierTelemetry:
    """Aggregated frontier telemetry for one quilt."""

    quilt_index: int
    total_placements: int
    main_placements: int
    tree_ingress_placements: int
    closure_follow_placements: int
    total_stalls: int
    stalls_resolved_by_rescue: int
    stalls_unresolved: int
    score_min: float
    score_max: float
    score_mean: float
    score_p25: float
    score_p50: float
    score_p75: float
    best_rejected_score_max: float
    first_rescue_iteration: int
    rescue_ratio: float
    rescue_gap_measured: int
    rescue_gap_below_threshold: int
    rescue_gap_main_viable: int
    rescue_gap_no_anchor: int
    rescue_gap_mean: float
    rescue_gap_max: float
    frontier_duration_sec: float
    rescue_gap_classes: tuple[FrontierRescueGapClassCount, ...]
    placement_records: tuple[FrontierPlacementRecord, ...]
    stall_records: tuple[FrontierStallRecord, ...]


__all__ = [
    "FrontierPlacementRecord",
    "FrontierStallRecord",
    "QuiltFrontierTelemetry",
]
