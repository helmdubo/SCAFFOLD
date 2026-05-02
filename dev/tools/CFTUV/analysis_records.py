from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from mathutils import Vector

try:
    from .model import (
        BandMode,
        BoundaryChain,
        BoundaryCorner,
        BoundaryLoop,
        ChainIncidence,
        ChainNeighborKind,
        ChainUse,
        ChainRef,
        FrameRole,
        LoopKind,
        PatchNode,
        PatchType,
        SkeletonFlags,
        WorldFacing,
    )
    from .shape_types import LoopShapeInterpretation, PatchShapeClass
    from .structural_tokens import LoopSignature
except ImportError:
    from model import (
        BandMode,
        BoundaryChain,
        BoundaryCorner,
        BoundaryLoop,
        ChainIncidence,
        ChainNeighborKind,
        ChainUse,
        ChainRef,
        FrameRole,
        LoopKind,
        PatchNode,
        PatchType,
        SkeletonFlags,
        WorldFacing,
    )
    from shape_types import LoopShapeInterpretation, PatchShapeClass
    from structural_tokens import LoopSignature


@dataclass
class _RawBoundaryLoop:
    """Private typed payload for one traced raw boundary loop."""

    vert_indices: list[int] = field(default_factory=list)
    vert_cos: list[Vector] = field(default_factory=list)
    edge_indices: list[int] = field(default_factory=list)
    side_face_indices: list[int] = field(default_factory=list)
    kind: LoopKind = LoopKind.OUTER
    depth: int = 0
    closed: bool = False


@dataclass
class _RawBoundaryChain:
    """Private typed payload for one intermediate raw chain."""

    vert_indices: list[int] = field(default_factory=list)
    vert_cos: list[Vector] = field(default_factory=list)
    edge_indices: list[int] = field(default_factory=list)
    side_face_indices: list[int] = field(default_factory=list)
    neighbor: int = -1
    is_closed: bool = False
    start_loop_index: int = 0
    end_loop_index: int = 0
    is_corner_split: bool = False


@dataclass
class _RawPatchBoundaryData:
    """Private typed payload for one patch before BoundaryLoop serialization."""

    face_indices: list[int] = field(default_factory=list)
    raw_loops: list[_RawBoundaryLoop] = field(default_factory=list)
    basis_u: Vector = field(default_factory=lambda: Vector((1.0, 0.0, 0.0)))
    basis_v: Vector = field(default_factory=lambda: Vector((0.0, 0.0, 1.0)))


@dataclass
class _PatchTopologyAssemblyState:
    """Typed patch assembly contract from raw patch trace to final PatchNode."""

    patch_id: int
    node: PatchNode
    raw_boundary_data: _RawPatchBoundaryData


@dataclass
class _BoundaryLoopBuildState:
    """Private step-by-step build contract for one finalized BoundaryLoop."""

    raw_loop: _RawBoundaryLoop
    boundary_loop: BoundaryLoop
    loop_neighbors: list[int] = field(default_factory=list)
    raw_chains: list[_RawBoundaryChain] = field(default_factory=list)


@dataclass
class _BoundaryLoopDerivedTopology:
    """Final derived topology written back into BoundaryLoop."""

    chains: list[BoundaryChain] = field(default_factory=list)
    corners: list[BoundaryCorner] = field(default_factory=list)
    uses_geometric_corner_fallback: bool = False


@dataclass
class _AnalysisUvClassificationState:
    """Rollback contract for the explicit UV-dependent OUTER/HOLE boundary step."""

    temp_uv_name: str = ""
    original_active_uv_name: str | None = None
    original_selection: list[int] = field(default_factory=list)

@dataclass(frozen=True)
class _BoundarySideKey:
    face_index: int
    edge_index: int
    vert_index: int


@dataclass(frozen=True)
class _PlanarPoint2D:
    x: float
    y: float


@dataclass(frozen=True, order=True)
class _PolygonEdgeLengthCandidate:
    len_squared: float
    index: int


@dataclass(frozen=True, order=True)
class _ChainFrameConfidence:
    primary_support: float
    total_length: float
    avg_deviation_score: float
    max_deviation_score: float
    vert_count: int
    edge_count: int


@dataclass(frozen=True)
class _ProjectedSpan2D:
    u_span: float
    v_span: float


@dataclass(frozen=True)
class _LoopClassificationResult:
    kind: LoopKind
    depth: int


@dataclass(frozen=True)
class _PatchNeighborChainRef:
    patch_id: int
    loop_index: int
    chain_index: int
    neighbor_patch_id: int
    start_vert_index: int
    end_vert_index: int

    @property
    def endpoint_pair(self) -> tuple[int, int]:
        return (
            min(self.start_vert_index, self.end_vert_index),
            max(self.start_vert_index, self.end_vert_index),
        )


@dataclass(frozen=True)
class _ResolvedLoopCornerIdentity:
    loop_vert_index: int
    vert_index: int
    vert_co: Vector
    resolved_exactly: bool = True


DirectionBucketKey = tuple[float, float, float]
PatchLoopKey = tuple[int, int]
CornerJunctionKey = tuple[int, int, int]
RunKey = tuple[int, int, int]          # (patch_id, loop_index, run_index)
JunctionPatchKey = tuple[int, int]     # (vert_index, patch_id)


@dataclass(frozen=True)
class _FrameRunBuildEntry:
    dominant_role: FrameRole
    chain_indices: tuple[int, ...]


@dataclass(frozen=True)
class _LoopFrameRunBuildResult:
    effective_roles: tuple[FrameRole, ...]
    runs: tuple["_FrameRun", ...]


@dataclass(frozen=True)
class _FrameRunEndpointSpec:
    endpoint_kind: str
    corner_index: int


@dataclass
class _FrameRun:
    """Diagnostic-only continuity view over final neighboring chains of one loop."""

    patch_id: int
    loop_index: int
    chain_indices: tuple[int, ...] = ()
    dominant_role: FrameRole = FrameRole.FREE
    start_corner_index: int = -1
    end_corner_index: int = -1
    total_length: float = 0.0
    support_length: float = 0.0
    gap_free_length: float = 0.0
    max_free_gap_length: float = 0.0
    projected_u_span: float = 0.0
    projected_v_span: float = 0.0


class _JunctionStructuralKind(str, Enum):
    """Structural role of a junction vertex in context of one patch."""
    TERMINAL = "TERMINAL"
    CONTINUATION = "CONTINUATION"
    TURN = "TURN"
    BRIDGE = "BRIDGE"
    BRANCH = "BRANCH"
    AMBIGUOUS = "AMBIGUOUS"
    FREE = "FREE"


@dataclass(frozen=True)
class _RunStructuralRole:
    """Structural interpretation of one FrameRun within its patch.
    Companion to _FrameRun — fact vs interpretation separation."""

    run_key: RunKey
    is_spine_candidate: bool = False
    spine_rank: int = -1
    opposing_run_key: Optional[RunKey] = None
    side_pair_length_ratio: float = 0.0
    inherited_role: Optional[FrameRole] = None
    inherited_from_patch_id: Optional[int] = None


@dataclass(frozen=True)
class _JunctionStructuralRole:
    """Structural role of a junction vertex in context of one patch.
    Derived view over existing _Junction + _FrameRun data."""

    vert_index: int
    patch_id: int
    kind: _JunctionStructuralKind = _JunctionStructuralKind.FREE
    spine_run_key: Optional[RunKey] = None
    dominant_axis: FrameRole = FrameRole.FREE
    supports_inherited_axis: bool = False
    implied_turn: float = -1.0


@dataclass(frozen=True)
class _JunctionCornerRef:
    patch_id: int
    loop_index: int
    corner_index: int
    prev_chain_index: int
    next_chain_index: int


@dataclass(frozen=True)
class _JunctionChainRef:
    patch_id: int
    loop_index: int
    chain_index: int
    frame_role: FrameRole
    neighbor_kind: ChainNeighborKind
    chain_use: Optional[ChainUse] = None


@dataclass(frozen=True)
class _JunctionRunEndpointRef:
    patch_id: int
    loop_index: int
    run_index: int
    dominant_role: FrameRole
    endpoint_kind: str
    corner_index: int


@dataclass(frozen=True)
class _JunctionRolePair:
    prev_role: FrameRole
    next_role: FrameRole


@dataclass
class _JunctionBuildEntry:
    vert_index: int
    vert_co: Vector
    corner_refs: list[_JunctionCornerRef] = field(default_factory=list)
    patch_ids: set[int] = field(default_factory=set)


@dataclass(frozen=True)
class _Junction:
    vert_index: int
    vert_co: Vector
    corner_refs: tuple[_JunctionCornerRef, ...] = ()
    chain_refs: tuple[_JunctionChainRef, ...] = ()
    disk_cycle: tuple[ChainIncidence, ...] = ()
    run_endpoint_refs: tuple[_JunctionRunEndpointRef, ...] = ()
    role_signature: tuple[_JunctionRolePair, ...] = ()
    patch_ids: tuple[int, ...] = ()
    valence: int = 0
    has_mesh_border: bool = False
    has_seam_self: bool = False
    is_open: bool = False
    h_count: int = 0
    v_count: int = 0
    free_count: int = 0
    row_component_id: int | None = None
    col_component_id: int | None = None
    canonical_u: float | None = None
    canonical_v: float | None = None
    skeleton_flags: SkeletonFlags = SkeletonFlags(0)

    def ordered_disk_cycle(self) -> list[ChainIncidence]:
        return list(
            sorted(
                self.disk_cycle,
                key=lambda incidence: (
                    incidence.angle,
                    incidence.chain_use.patch_id,
                    incidence.chain_use.loop_index,
                    incidence.chain_use.position_in_loop,
                    incidence.side,
                ),
            )
        )


@dataclass(frozen=True)
class _LoopDerivedTopologySummary:
    patch_id: int
    loop_index: int
    kind: LoopKind
    chain_count: int
    corner_count: int
    run_count: int


@dataclass(frozen=True)
class _PatchDerivedTopologySummary:
    patch_id: int
    semantic_key: str
    patch_type: PatchType
    world_facing: WorldFacing
    face_count: int
    loop_kinds: tuple[LoopKind, ...] = ()
    chain_count: int = 0
    corner_count: int = 0
    hole_count: int = 0
    run_count: int = 0
    role_sequence: tuple[FrameRole, ...] = ()
    h_count: int = 0
    v_count: int = 0
    free_count: int = 0
    loop_summaries: tuple[_LoopDerivedTopologySummary, ...] = ()
    spine_run_indices: tuple[int, ...] = ()
    spine_axis: FrameRole = FrameRole.FREE
    axis_candidate: FrameRole = FrameRole.FREE
    junction_supported_axis: FrameRole = FrameRole.FREE
    spine_length: float = 0.0
    inherited_spine_count: int = 0
    single_sided_inherited_support: bool = False
    band_cap_count: int = 0
    band_side_candidate_count: int = 0
    band_opposite_cap_length_ratio: float = 0.0
    band_width_stability: float = 0.0
    band_directional_consistency: float = 0.0
    band_candidate: bool = False
    band_side_indices: tuple[int, ...] = ()
    band_cap_path_groups: tuple[tuple[int, ...], ...] = ()
    band_mode: BandMode = BandMode.NOT_BAND
    band_confirmed_for_runtime: bool = False
    band_rejected_reason: str = ""
    band_requires_intervention: bool = False
    band_intervention_reject_reason: str = ""
    terminal_count: int = 0
    branch_count: int = 0
    strip_confidence: float = 0.0
    straighten_eligible: bool = False


@dataclass(frozen=True)
class _PatchGraphAggregateCounts:
    total_patches: int = 0
    walls: int = 0
    floors: int = 0
    slopes: int = 0
    singles: int = 0
    total_loops: int = 0
    total_chains: int = 0
    total_corners: int = 0
    total_sharp_corners: int = 0
    total_holes: int = 0
    total_h: int = 0
    total_v: int = 0
    total_free: int = 0
    total_up: int = 0
    total_down: int = 0
    total_side: int = 0
    total_patch_links: int = 0
    total_self_seams: int = 0
    total_mesh_borders: int = 0
    total_run_h: int = 0
    total_run_v: int = 0
    total_run_free: int = 0


@dataclass(frozen=True)
class BandSpineData:
    """Analysis-owned strip/tube runtime spine artifact.

    Historical name is kept for compatibility with the current frontier path,
    but the payload is no longer BAND-only: it carries the evaluated 3D spine
    together with its transported local frame.
    """

    patch_id: int
    side_a_ref: ChainRef
    side_b_ref: ChainRef
    cap_start_ref: ChainRef
    cap_end_ref: ChainRef
    cap_start_refs: tuple[ChainRef, ...] = ()
    cap_end_refs: tuple[ChainRef, ...] = ()
    spine_points_3d: tuple[Vector, ...] = ()
    spine_tangents_3d: tuple[Vector, ...] = ()
    spine_normals_3d: tuple[Vector, ...] = ()
    spine_binormals_3d: tuple[Vector, ...] = ()
    spine_arc_lengths: tuple[float, ...] = ()
    spine_arc_length: float = 0.0
    spine_is_periodic: bool = False
    cap_start_width: float = 0.0
    cap_end_width: float = 0.0
    chain_uv_targets: Mapping[ChainRef, tuple[tuple[float, float], ...]] = field(default_factory=dict)
    spine_axis: FrameRole = FrameRole.FREE


RuntimeSpineData = BandSpineData


@dataclass(frozen=True)
class _PatchGraphDerivedTopology:
    patch_summaries: tuple[_PatchDerivedTopologySummary, ...] = ()
    patch_summaries_by_id: Mapping[int, _PatchDerivedTopologySummary] = field(default_factory=dict)
    loop_summaries_by_key: Mapping[PatchLoopKey, _LoopDerivedTopologySummary] = field(default_factory=dict)
    aggregate_counts: _PatchGraphAggregateCounts = field(default_factory=_PatchGraphAggregateCounts)
    loop_frame_results: Mapping[PatchLoopKey, _LoopFrameRunBuildResult] = field(default_factory=dict)
    frame_runs_by_loop: Mapping[PatchLoopKey, tuple[_FrameRun, ...]] = field(default_factory=dict)
    run_refs_by_corner: Mapping[CornerJunctionKey, tuple[_JunctionRunEndpointRef, ...]] = field(default_factory=dict)
    junctions: tuple[_Junction, ...] = ()
    junctions_by_vert_index: Mapping[int, _Junction] = field(default_factory=dict)
    run_structural_roles: Mapping[RunKey, _RunStructuralRole] = field(default_factory=dict)
    junction_structural_roles: Mapping[JunctionPatchKey, _JunctionStructuralRole] = field(default_factory=dict)
    neighbor_inherited_roles: Mapping[ChainRef, tuple[FrameRole, int]] = field(default_factory=dict)
    patch_shape_classes: Mapping[int, PatchShapeClass] = field(default_factory=dict)
    loop_signatures: Mapping[int, list[LoopSignature]] = field(default_factory=dict)
    loop_shape_interpretations: Mapping[int, list[LoopShapeInterpretation]] = field(default_factory=dict)
    straighten_chain_refs: frozenset[ChainRef] = field(default_factory=frozenset)
    band_spine_data: Mapping[int, BandSpineData] = field(default_factory=dict)

    @property
    def runtime_spine_data(self) -> Mapping[int, RuntimeSpineData]:
        return self.band_spine_data
