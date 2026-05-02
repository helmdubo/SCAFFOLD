from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .model import (
    BoundaryChain,
    BoundaryCorner,
    BoundaryLoop,
    ChainNeighborKind,
    ChainRef,
    ChainUse,
    FrameRole,
    LoopChainRef,
    LoopKind,
    PatchEdgeKey,
    PatchGraph,
)
from .solve_records_common import EDGE_PROPAGATE_MIN, EDGE_WEAK_MIN


@dataclass(frozen=True)
class PatchCertainty:
    patch_id: int
    local_solvable: bool
    root_score: float
    outer_count: int
    hole_count: int
    chain_count: int
    free_count: int
    h_count: int
    v_count: int
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class SolveComponentsResult:
    components: list[set[int]]
    component_by_patch: dict[int, int]


@dataclass(frozen=True)
class PatchRoleCounts:
    outer_count: int
    hole_count: int
    chain_count: int
    free_count: int
    h_count: int
    v_count: int


@dataclass(frozen=True)
class AttachmentCandidate:
    owner_patch_id: int
    target_patch_id: int
    score: float
    seam_length: float
    seam_norm: float
    best_pair_strength: float
    frame_continuation: float
    endpoint_bridge: float
    corner_strength: float
    semantic_strength: float
    endpoint_strength: float
    owner_certainty: float
    target_certainty: float
    ambiguity_penalty: float
    owner_loop_index: int
    owner_chain_index: int
    target_loop_index: int
    target_chain_index: int
    owner_loop_kind: LoopKind
    target_loop_kind: LoopKind
    owner_role: FrameRole
    target_role: FrameRole
    owner_transition: str
    target_transition: str
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class SeamRelationProfile:
    """Explicit seam context preserved from planning for Phase 5 frontier hints."""

    edge_key: PatchEdgeKey
    primary_pair: tuple[ChainRef, ChainRef] = ()
    secondary_pairs: tuple[tuple[ChainRef, ChainRef], ...] = ()
    secondary_pair_count: int = 0
    pair_strength_gap: float = 0.0
    is_closure_like: bool = False
    support_asymmetry: float = 0.0
    ingress_preference: float = 0.0


@dataclass
class SolverGraph:
    patch_scores: dict[int, PatchCertainty] = field(default_factory=dict)
    candidates: list[AttachmentCandidate] = field(default_factory=list)
    candidates_by_owner: dict[int, list[AttachmentCandidate]] = field(default_factory=dict)
    solve_components: list[set[int]] = field(default_factory=list)
    component_by_patch: dict[int, int] = field(default_factory=dict)
    seam_relation_by_edge: dict[PatchEdgeKey, SeamRelationProfile] = field(default_factory=dict)
    max_shared_length: float = 0.0


@dataclass(frozen=True)
class SolveView:
    graph: PatchGraph
    visible_loop_indices_by_patch: dict[int, tuple[int, ...]] = field(default_factory=dict)
    primary_loop_index_by_patch: dict[int, int] = field(default_factory=dict)
    locally_solvable_patch_ids: frozenset[int] = frozenset()

    def get_visible_loop_indices(self, patch_id: int) -> tuple[int, ...]:
        return self.visible_loop_indices_by_patch.get(patch_id, ())

    def iter_visible_loops(self, patch_id: int):
        node = self.graph.nodes.get(patch_id)
        if node is None:
            return
        for loop_index in self.get_visible_loop_indices(patch_id):
            if 0 <= loop_index < len(node.boundary_loops):
                yield loop_index, node.boundary_loops[loop_index]

    def iter_visible_chain_records(self, patch_id: int):
        node = self.graph.nodes.get(patch_id)
        if node is None:
            return

        for loop_index, boundary_loop in self.iter_visible_loops(patch_id):
            oriented_chain_uses = node.iter_boundary_loop_oriented(loop_index)
            if oriented_chain_uses:
                for chain_use in oriented_chain_uses:
                    chain = self.graph.get_chain(
                        chain_use.patch_id,
                        chain_use.loop_index,
                        chain_use.chain_index,
                    )
                    if chain is None:
                        continue
                    yield chain_use, boundary_loop, chain
                continue

            for chain_index, chain in enumerate(boundary_loop.chains):
                chain_use = self.graph.get_chain_use(patch_id, loop_index, chain_index)
                if chain_use is None:
                    continue
                yield chain_use, boundary_loop, chain

    def iter_visible_chains(self, patch_id: int):
        for chain_use, boundary_loop, chain in self.iter_visible_chain_records(patch_id):
            yield chain_use.loop_index, chain_use.chain_index, boundary_loop, chain

    def iter_attachment_neighbor_chains(self, owner_patch_id: int, target_patch_id: int):
        refs: list[AttachmentNeighborRef] = []
        for chain_use, boundary_loop, chain in self.iter_visible_chain_records(owner_patch_id):
            if chain.neighbor_kind != ChainNeighborKind.PATCH:
                continue
            if chain.neighbor_patch_id != target_patch_id:
                continue
            refs.append(
                AttachmentNeighborRef(
                    loop_index=chain_use.loop_index,
                    chain_index=chain_use.chain_index,
                    boundary_loop=boundary_loop,
                    chain=chain,
                    chain_use=chain_use,
                )
            )
        return refs

    def primary_loop_index(self, patch_id: int) -> int:
        return self.primary_loop_index_by_patch.get(patch_id, -1)

    def patch_is_locally_solvable(self, patch_id: int) -> bool:
        return patch_id in self.locally_solvable_patch_ids

    def patch_types_compatible(self, owner_patch_id: int, target_patch_id: int) -> bool:
        owner_node = self.graph.nodes.get(owner_patch_id)
        target_node = self.graph.nodes.get(target_patch_id)
        if owner_node is None or target_node is None:
            return False

        owner_type = owner_node.patch_type.value if hasattr(owner_node.patch_type, "value") else str(owner_node.patch_type)
        target_type = target_node.patch_type.value if hasattr(target_node.patch_type, "value") else str(target_node.patch_type)
        return owner_type == target_type


@dataclass(frozen=True)
class QuiltStep:
    step_index: int
    patch_id: int
    is_root: bool = False
    incoming_candidate: Optional[AttachmentCandidate] = None


class QuiltStopReason(str, Enum):
    UNSET = ""
    FRONTIER_BELOW_THRESHOLD = "frontier_below_threshold"
    FRONTIER_EXHAUSTED = "frontier_exhausted"


@dataclass(frozen=True, order=True)
class AttachmentCandidatePreference:
    score: float
    frame_continuation: float
    endpoint_bridge: float
    endpoint_strength: float
    best_pair_strength: float
    seam_norm: float


@dataclass(frozen=True)
class AttachmentNeighborRef:
    loop_index: int
    chain_index: int
    boundary_loop: BoundaryLoop
    chain: BoundaryChain
    chain_use: ChainUse


@dataclass(frozen=True)
class ChainEndpointContext:
    vert_index: int
    corner: Optional[BoundaryCorner]
    neighbors: tuple[LoopChainRef, ...]


@dataclass(frozen=True)
class EndpointMatch:
    owner_label: str
    target_label: str


@dataclass(frozen=True)
class EndpointSupportStats:
    fixed_endpoint_count: int
    same_axis_endpoint_count: int
    free_touched_endpoint_count: int


@dataclass(frozen=True)
class EndpointBridgeMetrics:
    endpoint_bridge: float
    corner_strength: float


@dataclass(frozen=True)
class ChainPairSelection:
    owner_ref: AttachmentNeighborRef
    target_ref: AttachmentNeighborRef
    pair_strength: float
    endpoint_strength: float
    frame_continuation: float
    endpoint_bridge: float
    corner_strength: float
    semantic_strength: float


@dataclass
class QuiltPlan:
    quilt_index: int
    component_index: int
    root_patch_id: int
    root_score: float
    solved_patch_ids: list[int] = field(default_factory=list)
    steps: list[QuiltStep] = field(default_factory=list)
    original_solved_patch_ids: list[int] = field(default_factory=list)
    original_steps: list[QuiltStep] = field(default_factory=list)
    deferred_candidates: list[AttachmentCandidate] = field(default_factory=list)
    rejected_candidates: list[AttachmentCandidate] = field(default_factory=list)
    seam_relation_by_edge: dict[PatchEdgeKey, SeamRelationProfile] = field(default_factory=dict)
    stop_reason: QuiltStopReason = QuiltStopReason.UNSET


@dataclass
class SolvePlan:
    quilts: list[QuiltPlan] = field(default_factory=list)
    skipped_patch_ids: list[int] = field(default_factory=list)
    propagate_threshold: float = EDGE_PROPAGATE_MIN
    weak_threshold: float = EDGE_WEAK_MIN


@dataclass(frozen=True)
class ClosureCutHeuristic:
    edge_key: PatchEdgeKey
    candidate: AttachmentCandidate
    score: float
    support_label: str
    support_class: str
    fixed_endpoint_count: int
    same_axis_endpoint_count: int
    free_touched_endpoint_count: int
    representative_chain_length: float
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class QuiltClosureCutAnalysis:
    current_cut: ClosureCutHeuristic
    recommended_cut: ClosureCutHeuristic
    path_patch_ids: tuple[int, ...] = ()
    cycle_edges: tuple[ClosureCutHeuristic, ...] = ()


@dataclass(frozen=True)
class ClosureChainPairMatch:
    owner_ref: ChainRef
    owner_chain: BoundaryChain
    target_ref: ChainRef
    shared_vert_count: int
    target_chain: BoundaryChain


@dataclass(frozen=True)
class ClosureChainPairCandidate:
    score: int
    representative_length: float
    match: ClosureChainPairMatch


__all__ = [
    "PatchCertainty",
    "SolveComponentsResult",
    "PatchRoleCounts",
    "AttachmentCandidate",
    "SeamRelationProfile",
    "SolverGraph",
    "SolveView",
    "QuiltStep",
    "QuiltStopReason",
    "AttachmentCandidatePreference",
    "AttachmentNeighborRef",
    "ChainEndpointContext",
    "EndpointMatch",
    "EndpointSupportStats",
    "EndpointBridgeMetrics",
    "ChainPairSelection",
    "QuiltPlan",
    "SolvePlan",
    "ClosureCutHeuristic",
    "QuiltClosureCutAnalysis",
    "ClosureChainPairMatch",
    "ClosureChainPairCandidate",
]
