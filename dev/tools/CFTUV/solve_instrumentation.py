"""Сборщик телеметрии frontier-builder'а.

Модуль не изменяет поведение — только собирает данные.
Зависит только от solve_records и model (без circular imports).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from mathutils import Vector

try:
    from .model import (
        BoundaryChain, ChainRef, FrameRole, PlacementSourceKind,
    )
    from .solve_report_utils import (
        ReportingMode,
        ReportingOptions,
        coerce_reporting_options,
        format_chain_address,
        format_stall_address,
    )
    from .solve_records import (
        ChainAnchor, ChainPoolEntry, FrontierCandidateEval,
        FrontierPlacementRecord, FrontierRank, FrontierRankBreakdown, FrontierStallRecord, PatchScoringContext,
        CornerScoringHints, FrontierRescueGap, FrontierRescueGapClassCount, SeamRelationProfile,
        QuiltFrontierTelemetry,
        CHAIN_FRONTIER_THRESHOLD,
    )
    from .console_debug import (
        FrontierLiveTraceMode,
        get_frontier_live_trace_mode,
        trace_console,
    )
except ImportError:
    from model import (
        BoundaryChain, ChainRef, FrameRole, PlacementSourceKind,
    )
    from solve_report_utils import (
        ReportingMode,
        ReportingOptions,
        coerce_reporting_options,
        format_chain_address,
        format_stall_address,
    )
    from solve_records import (
        ChainAnchor, ChainPoolEntry, FrontierCandidateEval,
        FrontierPlacementRecord, FrontierRank, FrontierRankBreakdown, FrontierStallRecord, PatchScoringContext,
        CornerScoringHints, FrontierRescueGap, FrontierRescueGapClassCount, SeamRelationProfile,
        QuiltFrontierTelemetry,
        CHAIN_FRONTIER_THRESHOLD,
    )
    from console_debug import (
        FrontierLiveTraceMode,
        get_frontier_live_trace_mode,
        trace_console,
    )


# ============================================================
# Вспомогательные функции
# ============================================================

def _anchor_kind_label(anchor: Optional[ChainAnchor]) -> str:
    """Кодирует тип anchor в строку для FrontierPlacementRecord."""
    if anchor is None:
        return "none"
    if anchor.source_kind == PlacementSourceKind.CROSS_PATCH:
        return "cross_patch"
    return "same_patch"


def _anchor_kind_short(kind: str) -> str:
    """Краткая метка anchor из serialized telemetry record."""
    if kind == "cross_patch":
        return "XP"
    if kind == "same_patch":
        return "SP"
    return "-"


def _frame_role_short(role: Optional[FrameRole]) -> str:
    """Краткая метка frame-role для compact live trace."""
    if role == FrameRole.H_FRAME:
        return "H"
    if role == FrameRole.V_FRAME:
        return "V"
    if role == FrameRole.FREE:
        return "F"
    return "-"


def _placement_path_short(path: str) -> str:
    """Краткая метка placement-path для live trace."""
    return {
        "main": "main",
        "tree_ingress": "tree",
        "closure_follow": "clos",
    }.get(path, path)


def _frontier_rank_short(rank: Optional[FrontierRank]) -> str:
    if rank is None:
        return "-"
    return (
        f"{rank.viability_tier}/"
        f"{rank.role_tier}/"
        f"{rank.ingress_tier}/"
        f"{rank.patch_fit_tier}/"
        f"{rank.anchor_tier}/"
        f"{rank.closure_risk_tier}"
    )


def _frontier_rank_summary(rec: FrontierPlacementRecord) -> str:
    if rec.rank_breakdown is None or not rec.rank_breakdown.summary:
        return "-"
    return rec.rank_breakdown.summary


def _patch_context_short(ctx: Optional[PatchScoringContext]) -> str:
    if ctx is None:
        return "-"
    shape_short = "-"
    if ctx.shape_profile is not None:
        shape_short = (
            f"e:{ctx.shape_profile.elongation:.2f}"
            f"/r:{ctx.shape_profile.rectilinearity:.2f}"
            f"/f:{ctx.shape_profile.frame_dominance:.2f}"
            f"/h:{ctx.shape_profile.hole_ratio:.2f}"
            f"/s:{ctx.shape_profile.seam_multiplicity_hint:.2f}"
        )
    return (
        f"pc:{ctx.placed_chain_count}"
        f" hv:{ctx.placed_h_count + ctx.placed_v_count}"
        f" pr:{ctx.placed_ratio:.2f}"
        f" cov:{ctx.hv_coverage_ratio:.2f}"
        f" bb:{ctx.same_patch_backbone_strength:.2f}"
        f" cp:{ctx.closure_pressure:.2f}"
        f" sec:{'Y' if ctx.has_secondary_seam_pairs else 'N'}"
        f" sh:{shape_short}"
    )


def _corner_hints_short(hints: Optional[CornerScoringHints], bonus: float = 0.0) -> str:
    if hints is None:
        return "-"
    return (
        f"st:{hints.start_turn_strength:.2f}"
        f" et:{hints.end_turn_strength:.2f}"
        f" ort:{hints.orthogonal_turn_count}"
        f" sr:{hints.same_role_continuation_strength:.2f}"
        f" g:{'Y' if hints.has_geometric_corner else 'N'}"
        f" j:{'Y' if hints.has_junction_corner else 'N'}"
        f" b:{bonus:.2f}"
    )


def _seam_relation_membership(profile: Optional[SeamRelationProfile], chain_ref: ChainRef) -> str:
    if profile is None:
        return '-'
    if chain_ref in profile.primary_pair:
        return 'pri'
    for pair in profile.secondary_pairs:
        if chain_ref in pair:
            return 'sec'
    return 'sup'


def _seam_relation_short(
    profile: Optional[SeamRelationProfile],
    chain_ref: ChainRef,
    bonus: float = 0.0,
) -> str:
    if profile is None:
        return "-"
    return (
        f"m:{_seam_relation_membership(profile, chain_ref)}"
        f" sec:{profile.secondary_pair_count}"
        f" gap:{profile.pair_strength_gap:.2f}"
        f" cl:{'Y' if profile.is_closure_like else 'N'}"
        f" as:{profile.support_asymmetry:.2f}"
        f" in:{profile.ingress_preference:.2f}"
        f" b:{bonus:+.2f}"
    )


def _rescue_gap_short(gap: Optional[FrontierRescueGap]) -> str:
    if gap is None:
        return "-"
    return (
        f"cls:{gap.candidate_class or '-'}"
        f" k:{gap.main_known}"
        f" s:{gap.main_score:.2f}"
        f" dg:{gap.threshold_gap:.2f}"
        f" ok:{'Y' if gap.main_viable else 'N'}"
        f" hv:{gap.hv_adjacency}"
        f" ds:{gap.downstream_support}"
        f" sh:{gap.shared_vert_count}"
    )


def _rescue_gap_classes_short(classes: tuple[FrontierRescueGapClassCount, ...]) -> str:
    if not classes:
        return "-"
    return " ".join(
        f"{item.candidate_class}:{item.count}"
        for item in classes[:4]
    )


def _uv_chain_length(uv_points: list[Vector]) -> float:
    """Суммарная длина UV-цепочки по последовательным точкам."""
    if len(uv_points) < 2:
        return 0.0
    return sum(
        (uv_points[i + 1] - uv_points[i]).length
        for i in range(len(uv_points) - 1)
    )


def _percentile_sorted(sorted_vals: list[float], pct: float) -> float:
    """Процентиль из уже отсортированного списка. pct в [0, 1]."""
    n = len(sorted_vals)
    if n == 0:
        return 0.0
    if n == 1:
        return sorted_vals[0]
    idx = pct * (n - 1)
    lo = int(idx)
    hi = lo + 1
    if hi >= n:
        return sorted_vals[-1]
    frac = idx - lo
    return sorted_vals[lo] + frac * (sorted_vals[hi] - sorted_vals[lo])


def _format_live_placement_trace(
    quilt_index: int,
    rec: FrontierPlacementRecord,
    *,
    compact: bool,
) -> str:
    """Форматирует live placement trace отдельно от post-hoc report detail."""
    chain_addr = format_chain_address(rec.chain_ref, quilt_index=quilt_index)
    anchor_label = (
        f"{_anchor_kind_short(rec.start_anchor_kind)}/"
        f"{_anchor_kind_short(rec.end_anchor_kind)}"
    )
    if compact:
        return (
            f"[CFTUV][Telemetry] Q{quilt_index} S{rec.iteration} "
            f"{_placement_path_short(rec.placement_path)} {chain_addr} "
            f"{_frame_role_short(rec.frame_role)} s:{rec.score:.2f} "
            f"rk:{_frontier_rank_short(rec.rank)} "
            f"ctx:{_patch_context_short(rec.patch_context)} "
            f"sr:{_seam_relation_short(rec.seam_relation, rec.chain_ref, rec.seam_bonus)} "
            f"cr:{_corner_hints_short(rec.corner_hints, rec.corner_bonus)} "
            f"sh:{rec.shape_bonus:+.2f} "
            f"ep:{rec.anchor_count} {anchor_label} "
            f"b:{'Y' if rec.is_bridge else 'N'} "
            f"c:{'Y' if rec.is_closure_pair else 'N'} "
            f"hv:{rec.hv_adjacency} "
            f"gap:{_rescue_gap_short(rec.rescue_gap)}"
        )
    return (
        f"[CFTUV][Telemetry] Q{quilt_index} Step {rec.iteration}: "
        f"{rec.placement_path} {chain_addr} "
        f"{rec.frame_role.value} score:{rec.score:.2f} "
        f"rank:{_frontier_rank_short(rec.rank)} "
        f"ctx:{_patch_context_short(rec.patch_context)} "
        f"seam:{_seam_relation_short(rec.seam_relation, rec.chain_ref, rec.seam_bonus)} "
        f"corner:{_corner_hints_short(rec.corner_hints, rec.corner_bonus)} "
        f"shape:{rec.shape_bonus:+.2f} "
        f"ep:{rec.anchor_count} "
        f"{anchor_label} bridge:{'Y' if rec.is_bridge else 'N'} "
        f"closure:{'Y' if rec.is_closure_pair else 'N'} "
        f"hv:{rec.hv_adjacency} "
        f"gap:{_rescue_gap_short(rec.rescue_gap)}"
    )


def _stall_state_label(stall: FrontierStallRecord) -> str:
    """Краткая lifecycle-метка stall после close."""
    return "resolved" if stall.rescue_succeeded else "unresolved"


def _is_actionable_unresolved_stall(stall: FrontierStallRecord) -> bool:
    """True только для unresolved stall с проблемным остатком frontier."""
    if stall.rescue_succeeded:
        return False
    if (
        stall.best_rejected_ref is None
        and stall.best_rejected_score < 0.0
        and stall.available_count <= 0
        and stall.no_anchor_count <= 0
        and stall.below_threshold_count <= 0
    ):
        return False
    return True


def _format_live_stall_open_trace(
    quilt_index: int,
    stall: FrontierStallRecord,
    *,
    compact: bool,
) -> str:
    """Форматирует live stall-open trace."""
    ref_label = (
        format_chain_address(stall.best_rejected_ref, quilt_index=quilt_index)
        if stall.best_rejected_ref is not None else "-"
    )
    role_label = (
        _frame_role_short(stall.best_rejected_role)
        if compact else
        (stall.best_rejected_role.value if stall.best_rejected_role is not None else "NONE")
    )
    if compact:
        return (
            f"[CFTUV][Telemetry] Q{quilt_index} Stall{stall.iteration} open "
            f"rej:{stall.best_rejected_score:.3f} {ref_label} {role_label} "
            f"av:{stall.available_count} na:{stall.no_anchor_count}"
        )
    return (
        f"[CFTUV][Telemetry] Q{quilt_index} Stall {stall.iteration} open: "
        f"best_rejected:{stall.best_rejected_score:.3f} {ref_label} {role_label} "
        f"available:{stall.available_count} no_anchor:{stall.no_anchor_count}"
    )


def _format_live_stall_close_trace(
    quilt_index: int,
    stall: FrontierStallRecord,
    *,
    compact: bool,
) -> str:
    """Форматирует live stall-close trace."""
    rescue_label = f"{stall.rescue_attempted}={'Y' if stall.rescue_succeeded else 'N'}"
    if compact:
        return (
            f"[CFTUV][Telemetry] Q{quilt_index} Stall{stall.iteration} close "
            f"rescue:{rescue_label} st:{_stall_state_label(stall)}"
        )
    return (
        f"[CFTUV][Telemetry] Q{quilt_index} Stall {stall.iteration} close: "
        f"rescue:{rescue_label} state:{_stall_state_label(stall)}"
    )


def _emit_live_placement_trace(quilt_index: int, rec: FrontierPlacementRecord) -> None:
    """Печатает live placement trace по policy, не влияя на stored telemetry."""
    live_mode = get_frontier_live_trace_mode()
    if live_mode == FrontierLiveTraceMode.OFF:
        return
    trace_console(
        _format_live_placement_trace(
            quilt_index,
            rec,
            compact=(live_mode == FrontierLiveTraceMode.COMPACT),
        )
    )


def _emit_live_stall_open_trace(
    quilt_index: int,
    stall: FrontierStallRecord,
) -> None:
    """Печатает live stall-open trace по policy."""
    live_mode = get_frontier_live_trace_mode()
    if live_mode == FrontierLiveTraceMode.OFF:
        return
    trace_console(
        _format_live_stall_open_trace(
            quilt_index,
            stall,
            compact=(live_mode == FrontierLiveTraceMode.COMPACT),
        )
    )


def _emit_live_stall_close_trace(
    quilt_index: int,
    stall: FrontierStallRecord,
) -> None:
    """Печатает live stall-close trace по policy."""
    live_mode = get_frontier_live_trace_mode()
    if live_mode == FrontierLiveTraceMode.OFF:
        return
    trace_console(
        _format_live_stall_close_trace(
            quilt_index,
            stall,
            compact=(live_mode == FrontierLiveTraceMode.COMPACT),
        )
    )


# ============================================================
# Промежуточный open stall-record (до close)
# ============================================================

@dataclass
class _OpenStall:
    """Открытый stall до явного close после rescue/finalize."""
    iteration: int
    best_rejected_score: float
    best_rejected_ref: Optional[ChainRef]
    best_rejected_role: Optional[FrameRole]
    best_rejected_anchor_count: int
    available_count: int
    no_anchor_count: int
    below_threshold_count: int
    patches_with_placed: int
    patches_untouched: int
    rescue_attempted: str = "none"
    rescue_succeeded: bool = False

    def close(self) -> FrontierStallRecord:
        return FrontierStallRecord(
            iteration=self.iteration,
            best_rejected_score=self.best_rejected_score,
            best_rejected_ref=self.best_rejected_ref,
            best_rejected_role=self.best_rejected_role,
            best_rejected_anchor_count=self.best_rejected_anchor_count,
            available_count=self.available_count,
            no_anchor_count=self.no_anchor_count,
            below_threshold_count=self.below_threshold_count,
            rescue_attempted=self.rescue_attempted,
            rescue_succeeded=self.rescue_succeeded,
            patches_with_placed=self.patches_with_placed,
            patches_untouched=self.patches_untouched,
        )


# ============================================================
# FrontierTelemetryCollector
# ============================================================

@dataclass
class FrontierTelemetryCollector:
    """Mutable collector that accumulates records during frontier build.

    Created once per quilt. Passed to frontier loop and rescue functions.
    Finalized into immutable QuiltFrontierTelemetry at end of quilt.
    Collector is append-only — never read during the frontier loop.
    """

    quilt_index: int
    _t0: float = field(default_factory=time.perf_counter)
    _placement_records: list[FrontierPlacementRecord] = field(default_factory=list)
    _stall_records: list[FrontierStallRecord] = field(default_factory=list)
    _open_stall: Optional[_OpenStall] = field(default=None)

    def _begin_stall(
        self,
        iteration: int,
        best_rejected_score: float,
        best_rejected_ref: Optional[ChainRef],
        best_rejected_role: Optional[FrameRole],
        best_rejected_anchor_count: int,
        available_count: int,
        no_anchor_count: int,
        below_threshold_count: int,
        patches_with_placed: int,
        patches_untouched: int,
    ) -> None:
        """Открывает новый stall и сразу печатает open-trace."""
        self._open_stall = _OpenStall(
            iteration=iteration,
            best_rejected_score=best_rejected_score,
            best_rejected_ref=best_rejected_ref,
            best_rejected_role=best_rejected_role,
            best_rejected_anchor_count=best_rejected_anchor_count,
            available_count=available_count,
            no_anchor_count=no_anchor_count,
            below_threshold_count=below_threshold_count,
            patches_with_placed=patches_with_placed,
            patches_untouched=patches_untouched,
        )
        _emit_live_stall_open_trace(
            self.quilt_index,
            self._open_stall.close(),
        )

    def _close_open_stall(
        self,
        *,
        rescue_attempted: str,
        rescue_succeeded: bool,
        emit_live_close: bool = True,
    ) -> Optional[FrontierStallRecord]:
        """Явно закрывает открытый stall и записывает finalized record."""
        if self._open_stall is None:
            return None
        self._open_stall.rescue_attempted = rescue_attempted
        self._open_stall.rescue_succeeded = rescue_succeeded
        stall = self._open_stall.close()
        self._stall_records.append(stall)
        self._open_stall = None
        if emit_live_close:
            _emit_live_stall_close_trace(self.quilt_index, stall)
        return stall

    def _close_open_stall_unresolved(self) -> Optional[FrontierStallRecord]:
        """Явно закрывает открытый stall как unresolved."""
        return self._close_open_stall(
            rescue_attempted="none",
            rescue_succeeded=False,
        )

    def record_placement(
        self,
        iteration: int,
        chain_ref: ChainRef,
        chain: BoundaryChain,
        effective_role: FrameRole,
        placement_path: str,
        score: float,
        start_anchor: Optional[ChainAnchor],
        end_anchor: Optional[ChainAnchor],
        placed_in_patch_before: int,
        is_closure_pair: bool,
        uv_points: list[Vector],
        closure_preconstraint_applied: bool = False,
        anchor_adjustment_applied: bool = False,
        direction_inherited: bool = False,
        length_factor: float = 0.0,
        downstream_count: int = 0,
        downstream_bonus: float = 0.0,
        isolation_preview: bool = True,
        isolation_penalty: float = 0.0,
        structural_free_bonus: float = 0.0,
        hv_adjacency: int = 0,
        rank: Optional[FrontierRank] = None,
        rank_breakdown: Optional[FrontierRankBreakdown] = None,
        patch_context: Optional[PatchScoringContext] = None,
        corner_hints: Optional[CornerScoringHints] = None,
        seam_relation: Optional[SeamRelationProfile] = None,
        seam_bonus: float = 0.0,
        corner_bonus: float = 0.0,
        shape_bonus: float = 0.0,
        rescue_gap: Optional[FrontierRescueGap] = None,
        emit_live_trace: bool = True,
    ) -> None:
        """Записывает одно успешное размещение chain."""
        anchor_count = (
            (1 if start_anchor is not None else 0)
            + (1 if end_anchor is not None else 0)
        )
        rec = FrontierPlacementRecord(
            iteration=iteration,
            chain_ref=chain_ref,
            frame_role=effective_role,
            placement_path=placement_path,
            score=score,
            anchor_count=anchor_count,
            start_anchor_kind=_anchor_kind_label(start_anchor),
            end_anchor_kind=_anchor_kind_label(end_anchor),
            placed_in_patch_before=placed_in_patch_before,
            is_first_in_patch=(placed_in_patch_before == 0),
            is_bridge=(effective_role == FrameRole.FREE and len(chain.vert_cos) <= 2),
            is_corner_split=chain.is_corner_split,
            neighbor_kind=chain.neighbor_kind.value,
            is_closure_pair=is_closure_pair,
            closure_preconstraint_applied=closure_preconstraint_applied,
            anchor_adjustment_applied=anchor_adjustment_applied,
            direction_inherited=direction_inherited,
            chain_length_uv=_uv_chain_length(uv_points),
            length_factor=length_factor,
            downstream_count=downstream_count,
            downstream_bonus=downstream_bonus,
            isolation_preview=isolation_preview,
            isolation_penalty=isolation_penalty,
            structural_free_bonus=structural_free_bonus,
            hv_adjacency=hv_adjacency,
            rank=rank,
            rank_breakdown=rank_breakdown,
            patch_context=patch_context,
            corner_hints=corner_hints,
            seam_relation=seam_relation,
            seam_bonus=seam_bonus,
            corner_bonus=corner_bonus,
            shape_bonus=shape_bonus,
            rescue_gap=rescue_gap,
        )
        self._placement_records.append(rec)
        if emit_live_trace:
            _emit_live_placement_trace(self.quilt_index, rec)

    def record_seed_placement(
        self,
        chain_ref: ChainRef,
        chain: BoundaryChain,
        effective_role: FrameRole,
        score: float,
        uv_points: list[Vector],
        *,
        is_closure_pair: bool = False,
        hv_adjacency: int = 0,
    ) -> None:
        """Регистрирует bootstrap seed в structured telemetry без отдельного live-trace."""
        self.record_placement(
            iteration=0,
            chain_ref=chain_ref,
            chain=chain,
            effective_role=effective_role,
            placement_path="main",
            score=score,
            start_anchor=None,
            end_anchor=None,
            placed_in_patch_before=0,
            is_closure_pair=is_closure_pair,
            uv_points=uv_points,
            hv_adjacency=hv_adjacency,
            emit_live_trace=False,
        )

    def record_stall(
        self,
        iteration: int,
        best_rejected_score: float,
        best_rejected_ref: Optional[ChainRef],
        best_rejected_role: Optional[FrameRole],
        best_rejected_anchor_count: int,
        available_count: int,
        no_anchor_count: int,
        below_threshold_count: int,
        patches_with_placed: int,
        patches_untouched: int,
    ) -> None:
        """Открывает stall; close происходит через rescue или finalize()."""
        # Предыдущий open-stall не должен переживать новый stall silently.
        if self._open_stall is not None:
            self._close_open_stall_unresolved()

        self._begin_stall(
            iteration=iteration,
            best_rejected_score=best_rejected_score,
            best_rejected_ref=best_rejected_ref,
            best_rejected_role=best_rejected_role,
            best_rejected_anchor_count=best_rejected_anchor_count,
            available_count=available_count,
            no_anchor_count=no_anchor_count,
            below_threshold_count=below_threshold_count,
            patches_with_placed=patches_with_placed,
            patches_untouched=patches_untouched,
        )

    def update_last_stall_rescue(
        self,
        rescue_attempted: str,
        rescue_succeeded: bool,
    ) -> None:
        """Явно закрывает текущий open-stall результатом rescue-попытки."""
        self._close_open_stall(
            rescue_attempted=rescue_attempted,
            rescue_succeeded=rescue_succeeded,
        )

    def finalize(self) -> QuiltFrontierTelemetry:
        """Вычисляет агрегаты и возвращает immutable QuiltFrontierTelemetry."""
        # Любой открытый stall должен закрыться явно как unresolved.
        self._close_open_stall_unresolved()

        duration = time.perf_counter() - self._t0

        # Счётчики по путям
        total = len(self._placement_records)
        main_count = sum(1 for r in self._placement_records if r.placement_path == "main")
        tree_count = sum(1 for r in self._placement_records if r.placement_path == "tree_ingress")
        closure_count = sum(1 for r in self._placement_records if r.placement_path == "closure_follow")

        # Stall-агрегаты
        total_stalls = len(self._stall_records)
        stalls_resolved = sum(1 for s in self._stall_records if s.rescue_succeeded)
        stalls_unresolved = total_stalls - stalls_resolved

        # Score-статистика только для main-пути
        main_scores = sorted(
            r.score for r in self._placement_records
            if r.placement_path == "main" and r.score >= 0.0
        )
        if main_scores:
            score_min = main_scores[0]
            score_max = main_scores[-1]
            score_mean = sum(main_scores) / len(main_scores)
            score_p25 = _percentile_sorted(main_scores, 0.25)
            score_p50 = _percentile_sorted(main_scores, 0.50)
            score_p75 = _percentile_sorted(main_scores, 0.75)
        else:
            score_min = score_max = score_mean = 0.0
            score_p25 = score_p50 = score_p75 = 0.0

        best_rejected_max = max(
            (s.best_rejected_score for s in self._stall_records),
            default=0.0,
        )

        # Первая rescue-итерация
        rescue_iters = [
            r.iteration for r in self._placement_records
            if r.placement_path != "main"
        ]
        first_rescue_iteration = min(rescue_iters) if rescue_iters else -1

        rescue_total = tree_count + closure_count
        rescue_ratio = rescue_total / total if total > 0 else 0.0
        rescue_gaps = [
            r.rescue_gap
            for r in self._placement_records
            if r.placement_path != "main" and r.rescue_gap is not None
        ]
        rescue_gap_measured = len(rescue_gaps)
        rescue_gap_below_threshold = sum(
            1 for gap in rescue_gaps
            if gap.main_known > 0 and not gap.main_viable
        )
        rescue_gap_main_viable = sum(
            1 for gap in rescue_gaps
            if gap.main_viable
        )
        rescue_gap_no_anchor = sum(
            1 for gap in rescue_gaps
            if gap.main_known <= 0
        )
        if rescue_gaps:
            rescue_gap_mean = (
                sum(gap.threshold_gap for gap in rescue_gaps) / rescue_gap_measured
            )
            rescue_gap_max = max(gap.threshold_gap for gap in rescue_gaps)
        else:
            rescue_gap_mean = 0.0
            rescue_gap_max = 0.0

        class_counts: dict[str, int] = {}
        for gap in rescue_gaps:
            candidate_class = gap.candidate_class or "unknown"
            class_counts[candidate_class] = class_counts.get(candidate_class, 0) + 1
        rescue_gap_classes = tuple(
            FrontierRescueGapClassCount(candidate_class=label, count=count)
            for label, count in sorted(
                class_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
        )

        return QuiltFrontierTelemetry(
            quilt_index=self.quilt_index,
            total_placements=total,
            main_placements=main_count,
            tree_ingress_placements=tree_count,
            closure_follow_placements=closure_count,
            total_stalls=total_stalls,
            stalls_resolved_by_rescue=stalls_resolved,
            stalls_unresolved=stalls_unresolved,
            score_min=score_min,
            score_max=score_max,
            score_mean=score_mean,
            score_p25=score_p25,
            score_p50=score_p50,
            score_p75=score_p75,
            best_rejected_score_max=best_rejected_max,
            first_rescue_iteration=first_rescue_iteration,
            rescue_ratio=rescue_ratio,
            rescue_gap_measured=rescue_gap_measured,
            rescue_gap_below_threshold=rescue_gap_below_threshold,
            rescue_gap_main_viable=rescue_gap_main_viable,
            rescue_gap_no_anchor=rescue_gap_no_anchor,
            rescue_gap_mean=rescue_gap_mean,
            rescue_gap_max=rescue_gap_max,
            frontier_duration_sec=duration,
            rescue_gap_classes=rescue_gap_classes,
            placement_records=tuple(self._placement_records),
            stall_records=tuple(self._stall_records),
        )


# ============================================================
# Вычисление stall-данных в момент останова frontier
# (вызывается из solve_frontier.py, не из collector)
# ============================================================

def collect_stall_snapshot(
    cached_evals: dict,
    placed_chain_refs: set,
    rejected_chain_refs: set,
    placed_count_by_patch: dict,
    quilt_patch_ids: set,
    all_chain_pool: list,
) -> tuple:
    """Snapshot состояния frontier в момент stall.

    Принимает уже вычисленные поля из FrontierRuntimePolicy без импорта
    самого класса. Возвращает (score, ref, role, anchor_count, available,
    no_anchor, below_threshold, patches_with_placed, patches_untouched).
    """
    best_score = -1.0
    best_ref: Optional[ChainRef] = None
    best_role: Optional[FrameRole] = None
    best_anchor_count = 0

    available_count = 0
    no_anchor_count = 0
    below_threshold_count = 0

    for entry in all_chain_pool:
        ref = entry.chain_ref
        if ref in placed_chain_refs or ref in rejected_chain_refs:
            continue
        available_count += 1

        eval_result: Optional[FrontierCandidateEval] = cached_evals.get(ref)
        if eval_result is None:
            no_anchor_count += 1
            continue

        known = eval_result.known
        score = eval_result.score
        if known == 0:
            no_anchor_count += 1
        elif 0.0 <= score < CHAIN_FRONTIER_THRESHOLD:
            below_threshold_count += 1

        if score > best_score:
            best_score = score
            best_ref = ref
            best_role = entry.chain.frame_role
            best_anchor_count = known

    # Patches с хотя бы одним placed chain
    patches_with_placed = len(placed_count_by_patch)
    patches_untouched = sum(
        1 for pid in quilt_patch_ids if pid not in placed_count_by_patch
    )

    return (
        best_score,
        best_ref,
        best_role,
        best_anchor_count,
        available_count,
        no_anchor_count,
        below_threshold_count,
        patches_with_placed,
        patches_untouched,
    )


# ============================================================
# Форматирование для reporting
# ============================================================

def format_quilt_telemetry_summary(
    t: QuiltFrontierTelemetry,
    reporting: Optional[ReportingOptions] = None,
    *,
    mode: Optional[ReportingMode | str] = None,
) -> list[str]:
    """Краткая сводка телеметрии для regression snapshot (одна секция)."""
    reporting = coerce_reporting_options(reporting, mode=mode)
    actionable_unresolved_stalls = sum(
        1 for stall in t.stall_records if _is_actionable_unresolved_stall(stall)
    )
    terminal_stalls = sum(
        1
        for stall in t.stall_records
        if (not stall.rescue_succeeded) and (not _is_actionable_unresolved_stall(stall))
    )
    if (
        terminal_stalls == t.total_stalls
        and t.stalls_resolved_by_rescue == 0
        and actionable_unresolved_stalls == 0
    ):
        stalls_line = f"  stalls: terminal:{terminal_stalls}"
    else:
        stalls_line = (
            f"  stalls: {t.total_stalls} "
            f"resolved:{t.stalls_resolved_by_rescue} "
            f"unresolved:{actionable_unresolved_stalls}"
        )
    if terminal_stalls > 0 and not (
        terminal_stalls == t.total_stalls
        and t.stalls_resolved_by_rescue == 0
        and actionable_unresolved_stalls == 0
    ):
        stalls_line += f" terminal:{terminal_stalls}"
    lines = [
        "frontier_telemetry:",
        (
            f"  placements: {t.total_placements} "
            f"main:{t.main_placements} "
            f"tree_ingress:{t.tree_ingress_placements} "
            f"closure_follow:{t.closure_follow_placements}"
        ),
        stalls_line,
        (
            f"  scores: min:{t.score_min:.3f} "
            f"p25:{t.score_p25:.3f} "
            f"p50:{t.score_p50:.3f} "
            f"p75:{t.score_p75:.3f} "
            f"max:{t.score_max:.3f}"
        ),
        "  rank_order: viable>role>ingress>patch_fit>anchor>closure>score>length",
        f"  rescue_ratio: {t.rescue_ratio:.3f}",
        (
            f"  rescue_gap: measured:{t.rescue_gap_measured} "
            f"below_threshold:{t.rescue_gap_below_threshold} "
            f"main_viable:{t.rescue_gap_main_viable} "
            f"no_anchor:{t.rescue_gap_no_anchor} "
            f"mean:{t.rescue_gap_mean:.3f} "
            f"max:{t.rescue_gap_max:.3f}"
        ),
        f"  rescue_classes: {_rescue_gap_classes_short(t.rescue_gap_classes)}",
        f"  best_rejected_max: {t.best_rejected_score_max:.3f}",
        f"  duration: {t.frontier_duration_sec:.3f}s",
    ]
    return lines


def format_quilt_telemetry_posthoc_detail(
    t: QuiltFrontierTelemetry,
    reporting: Optional[ReportingOptions] = None,
    *,
    mode: Optional[ReportingMode | str] = None,
) -> list[str]:
    """Подробный post-hoc лог размещений и stall-событий для forensic report."""
    reporting = coerce_reporting_options(reporting, mode=mode)
    lines: list[str] = ["frontier_telemetry_detail:"]
    q = t.quilt_index

    # Объединяем placement и stall в хронологическом порядке по iteration
    stall_by_iter: dict[int, FrontierStallRecord] = {s.iteration: s for s in t.stall_records}
    placement_by_iter: dict[int, list[FrontierPlacementRecord]] = {}
    for r in t.placement_records:
        placement_by_iter.setdefault(r.iteration, []).append(r)

    all_iters = sorted(set(stall_by_iter) | set(placement_by_iter))
    for it in all_iters:
        stall = stall_by_iter.get(it)
        if stall is not None:
            ref_str = (
                format_chain_address(stall.best_rejected_ref, quilt_index=q)
                if stall.best_rejected_ref is not None else "-"
            )
            role_str = stall.best_rejected_role.value if stall.best_rejected_role is not None else "NONE"
            lines.append(
                f"  stall_open {format_stall_address(it, quilt_index=q)}: "
                f"best_rejected:{stall.best_rejected_score:.3f} "
                f"{ref_str} {role_str} "
                f"available:{stall.available_count} "
                f"no_anchor:{stall.no_anchor_count}"
            )
        for r in placement_by_iter.get(it, []):
            lines.append(
                f"  step {it}: "
                f"{r.placement_path} "
                f"{format_chain_address(r.chain_ref, quilt_index=q)} "
                f"{r.frame_role.value} score:{r.score:.2f} "
                f"rank:{_frontier_rank_short(r.rank)} "
                f"ctx:{_patch_context_short(r.patch_context)} "
                f"seam:{_seam_relation_short(r.seam_relation, r.chain_ref, r.seam_bonus)} "
                f"corner:{_corner_hints_short(r.corner_hints, r.corner_bonus)} "
                f"shape:{r.shape_bonus:+.2f} "
                f"ep:{r.anchor_count} "
                f"{_anchor_kind_short(r.start_anchor_kind)}/{_anchor_kind_short(r.end_anchor_kind)} "
                f"bridge:{'Y' if r.is_bridge else 'N'} "
                f"closure:{'Y' if r.is_closure_pair else 'N'} "
                f"[lf:{r.length_factor:.2f} ds:{r.downstream_count}:{r.downstream_bonus:.2f} "
                f"iso:{r.isolation_preview}:{r.isolation_penalty:.2f} sfb:{r.structural_free_bonus:.2f} "
                f"hv:{r.hv_adjacency}] "
                f"gap:{_rescue_gap_short(r.rescue_gap)} "
                f"why:{_frontier_rank_summary(r)}"
            )
        if stall is not None:
            lines.append(
                f"  stall_close {format_stall_address(it, quilt_index=q)}: "
                f"rescue:{stall.rescue_attempted}={'Y' if stall.rescue_succeeded else 'N'} "
                f"state:{_stall_state_label(stall)}"
            )
    return lines


def format_quilt_telemetry_detail(
    t: QuiltFrontierTelemetry,
    reporting: Optional[ReportingOptions] = None,
    *,
    mode: Optional[ReportingMode | str] = None,
) -> list[str]:
    """Совместимый wrapper для post-hoc telemetry detail."""
    return format_quilt_telemetry_posthoc_detail(t, reporting=reporting, mode=mode)
