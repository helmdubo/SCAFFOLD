from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from mathutils import Vector

try:
    from .analysis_records import BandSpineData, _PatchDerivedTopologySummary
    from .shape_types import PatchShapeClass
    from .model import (
        AxisAuthorityKind,
        BandMode,
        BoundaryChain,
        ChainRef,
        FrameRole,
        ParameterAuthorityKind,
        PatchEdgeKey,
        PatchGraph,
        PlacementSourceKind,
        ScaffoldChainPlacement,
        StationAuthorityKind,
        SpanAuthorityKind,
    )
    from .solve_records import (
        ChainAnchor,
        FrontierCandidateEval,
        PatchShapeProfile,
        PointRegistry,
        SeamRelationProfile,
        VertexPlacementMap,
        _patch_pair_key,
        _point_registry_key,
    )
except ImportError:
    from analysis_records import BandSpineData, _PatchDerivedTopologySummary
    from shape_types import PatchShapeClass
    from model import (
        AxisAuthorityKind,
        BandMode,
        BoundaryChain,
        ChainRef,
        FrameRole,
        ParameterAuthorityKind,
        PatchEdgeKey,
        PatchGraph,
        PlacementSourceKind,
        ScaffoldChainPlacement,
        StationAuthorityKind,
        SpanAuthorityKind,
    )
    from solve_records import (
        ChainAnchor,
        FrontierCandidateEval,
        PatchShapeProfile,
        PointRegistry,
        SeamRelationProfile,
        VertexPlacementMap,
        _patch_pair_key,
        _point_registry_key,
    )

# Roles that count as "strong" for authority resolution and scoring.
_STRONG_ROLES = {FrameRole.H_FRAME, FrameRole.V_FRAME, FrameRole.STRAIGHTEN}


@dataclass(frozen=True)
class FrontierLaunchContext:
    graph: PatchGraph
    quilt_patch_ids: set[int]
    allowed_tree_edges: set[PatchEdgeKey]
    final_scale: float
    seam_relation_by_edge: dict[PatchEdgeKey, SeamRelationProfile] = field(default_factory=dict)
    tree_ingress_partner_by_chain: dict[ChainRef, ChainRef] = field(default_factory=dict)
    closure_pair_map: Optional[dict[ChainRef, ChainRef]] = None
    straighten_enabled: bool = False
    inherited_role_map: dict[ChainRef, tuple[FrameRole, int]] = field(default_factory=dict)
    patch_structural_summaries: dict[int, _PatchDerivedTopologySummary] = field(default_factory=dict)
    patch_shape_classes: dict[int, PatchShapeClass] = field(default_factory=dict)
    straighten_chain_refs: frozenset[ChainRef] = field(default_factory=frozenset)
    band_spine_data: dict[int, BandSpineData] = field(default_factory=dict)


@dataclass
class FrontierRuntimeState:
    point_registry: PointRegistry = field(default_factory=dict)
    vert_to_placements: VertexPlacementMap = field(default_factory=dict)
    placed_chain_refs: set[ChainRef] = field(default_factory=set)
    placed_chains_map: dict[ChainRef, ScaffoldChainPlacement] = field(default_factory=dict)
    chain_dependency_patches: dict[ChainRef, tuple[int, ...]] = field(default_factory=dict)
    rejected_chain_refs: set[ChainRef] = field(default_factory=set)
    build_order: list[ChainRef] = field(default_factory=list)
    placed_count_by_patch: dict[int, int] = field(default_factory=dict)
    placed_h_count_by_patch: dict[int, int] = field(default_factory=dict)
    placed_v_count_by_patch: dict[int, int] = field(default_factory=dict)
    placed_free_count_by_patch: dict[int, int] = field(default_factory=dict)
    _outer_chain_count_by_patch: dict[int, int] = field(init=False, default_factory=dict)
    _frame_chain_count_by_patch: dict[int, int] = field(init=False, default_factory=dict)
    _closure_pair_count_by_patch: dict[int, int] = field(init=False, default_factory=dict)
    _backbone_h_count_by_patch: dict[int, int] = field(init=False, default_factory=dict)
    _backbone_v_count_by_patch: dict[int, int] = field(init=False, default_factory=dict)
    _backbone_free_count_by_patch: dict[int, int] = field(init=False, default_factory=dict)
    _shape_profile_by_patch: dict[int, PatchShapeProfile] = field(init=False, default_factory=dict)
    _cached_evals: dict[ChainRef, FrontierCandidateEval] = field(init=False, default_factory=dict)
    _dirty_refs: set[ChainRef] = field(init=False, default_factory=set)
    _vert_to_pool_refs: dict[int, list[ChainRef]] = field(init=False, default_factory=dict)
    _patch_to_pool_refs: dict[int, list[ChainRef]] = field(init=False, default_factory=dict)
    _cache_hits: int = field(init=False, default=0)


class FrontierRuntimePolicy:
    """Compatibility wrapper over immutable launch context and mutable runtime state."""

    _CONTEXT_FIELDS = frozenset(
        {
            "graph",
            "quilt_patch_ids",
            "allowed_tree_edges",
            "final_scale",
            "seam_relation_by_edge",
            "tree_ingress_partner_by_chain",
            "closure_pair_map",
            "straighten_enabled",
            "inherited_role_map",
            "patch_structural_summaries",
            "patch_shape_classes",
            "straighten_chain_refs",
            "band_spine_data",
        }
    )
    _STATE_FIELDS = frozenset(
        {
            "point_registry",
            "vert_to_placements",
            "placed_chain_refs",
            "placed_chains_map",
            "chain_dependency_patches",
            "rejected_chain_refs",
            "build_order",
            "placed_count_by_patch",
            "placed_h_count_by_patch",
            "placed_v_count_by_patch",
            "placed_free_count_by_patch",
            "_outer_chain_count_by_patch",
            "_frame_chain_count_by_patch",
            "_closure_pair_count_by_patch",
            "_backbone_h_count_by_patch",
            "_backbone_v_count_by_patch",
            "_backbone_free_count_by_patch",
            "_shape_profile_by_patch",
            "_cached_evals",
            "_dirty_refs",
            "_vert_to_pool_refs",
            "_patch_to_pool_refs",
            "_cache_hits",
        }
    )

    def __init__(
        self,
        context: FrontierLaunchContext,
        state: Optional[FrontierRuntimeState] = None,
    ) -> None:
        object.__setattr__(self, "context", context)
        object.__setattr__(self, "state", state if state is not None else FrontierRuntimeState())

    @classmethod
    def from_parts(
        cls,
        *,
        graph: PatchGraph,
        quilt_patch_ids: set[int],
        allowed_tree_edges: set[PatchEdgeKey],
        final_scale: float,
        seam_relation_by_edge: Optional[dict[PatchEdgeKey, SeamRelationProfile]] = None,
        tree_ingress_partner_by_chain: Optional[dict[ChainRef, ChainRef]] = None,
        closure_pair_map: Optional[dict[ChainRef, ChainRef]] = None,
        straighten_enabled: bool = False,
        inherited_role_map: Optional[dict[ChainRef, tuple[FrameRole, int]]] = None,
        patch_structural_summaries: Optional[dict[int, _PatchDerivedTopologySummary]] = None,
        patch_shape_classes: Optional[dict[int, PatchShapeClass]] = None,
        straighten_chain_refs: Optional[frozenset[ChainRef]] = None,
        band_spine_data: Optional[dict[int, BandSpineData]] = None,
    ) -> "FrontierRuntimePolicy":
        context = FrontierLaunchContext(
            graph=graph,
            quilt_patch_ids=quilt_patch_ids,
            allowed_tree_edges=allowed_tree_edges,
            final_scale=final_scale,
            seam_relation_by_edge=seam_relation_by_edge or {},
            tree_ingress_partner_by_chain=tree_ingress_partner_by_chain or {},
            closure_pair_map=closure_pair_map,
            straighten_enabled=straighten_enabled,
            inherited_role_map=inherited_role_map or {},
            patch_structural_summaries=patch_structural_summaries or {},
            patch_shape_classes=patch_shape_classes or {},
            straighten_chain_refs=straighten_chain_refs or frozenset(),
            band_spine_data=band_spine_data or {},
        )
        return cls(context=context, state=FrontierRuntimeState())

    def __getattr__(self, name: str):
        if name in self._CONTEXT_FIELDS:
            return getattr(self.context, name)
        if name in self._STATE_FIELDS:
            return getattr(self.state, name)
        raise AttributeError(name)

    def __setattr__(self, name: str, value) -> None:
        if name in {"context", "state"}:
            object.__setattr__(self, name, value)
            return
        if name in self._CONTEXT_FIELDS:
            raise AttributeError(f"{name} belongs to immutable frontier launch context")
        if name in self._STATE_FIELDS:
            setattr(self.state, name, value)
            return
        object.__setattr__(self, name, value)

    @property
    def closure_pair_refs(self) -> frozenset[ChainRef]:
        return frozenset(self.closure_pair_map.keys()) if self.closure_pair_map else frozenset()

    def band_spine(self, patch_id: int) -> Optional[BandSpineData]:
        if not self.straighten_enabled:
            return None
        return self.band_spine_data.get(patch_id)

    def runtime_spine(self, patch_id: int) -> Optional[BandSpineData]:
        return self.band_spine(patch_id)

    def band_side_role(self, chain_ref: ChainRef) -> FrameRole:
        spine = self.band_spine(chain_ref[0])
        if spine is None:
            return FrameRole.FREE
        if chain_ref in {spine.side_a_ref, spine.side_b_ref}:
            return FrameRole.STRAIGHTEN
        return FrameRole.FREE

    def band_cap_role(self, chain_ref: ChainRef) -> FrameRole:
        spine = self.band_spine(chain_ref[0])
        if spine is None:
            return FrameRole.FREE
        cap_refs = set(spine.cap_start_refs or (spine.cap_start_ref,))
        cap_refs.update(spine.cap_end_refs or (spine.cap_end_ref,))
        if chain_ref not in cap_refs:
            return FrameRole.FREE
        if spine.spine_axis == FrameRole.H_FRAME:
            return FrameRole.V_FRAME
        if spine.spine_axis == FrameRole.V_FRAME:
            return FrameRole.H_FRAME
        return FrameRole.FREE

    def effective_placement_role(self, chain_ref: ChainRef, chain: BoundaryChain) -> FrameRole:
        """Unified semantic switch for placement, scoring, and viability.

        Priority:
        1. Native H/V → return as-is.
        2. STRAIGHTEN from structural tokens (BAND SIDE) → STRAIGHTEN.
        3. Inherited H/V from strong neighbor → return inherited role.
        4. Otherwise → FREE.
        """
        if chain.frame_role != FrameRole.FREE:
            return chain.frame_role
        if chain_ref in self.straighten_chain_refs or self.band_side_role(chain_ref) == FrameRole.STRAIGHTEN:
            return FrameRole.STRAIGHTEN
        band_cap_role = self.band_cap_role(chain_ref)
        if band_cap_role in {FrameRole.H_FRAME, FrameRole.V_FRAME}:
            return band_cap_role
        patch_id = chain_ref[0]
        if self._patch_allows_straighten_runtime(patch_id) and chain_ref in self.inherited_role_map:
            return self.inherited_role_map[chain_ref][0]
        return FrameRole.FREE

    def seed_placement_role(self, chain_ref: ChainRef, chain: BoundaryChain) -> FrameRole:
        role = self.effective_placement_role(chain_ref, chain)
        if chain.frame_role != FrameRole.FREE:
            return role
        if role not in _STRONG_ROLES:
            return role
        # STRAIGHTEN from structural tokens is always valid as seed role.
        if role == FrameRole.STRAIGHTEN:
            return role
        patch_id = chain_ref[0]
        if not self._patch_allows_straighten_runtime(patch_id):
            return FrameRole.FREE
        if chain_ref not in self.inherited_role_map:
            return role
        if self._patch_summary_attr(patch_id, 'spine_axis', FrameRole.FREE) in {FrameRole.H_FRAME, FrameRole.V_FRAME}:
            return role
        if self._patch_summary_attr(patch_id, 'inherited_spine_count', 0) >= 2:
            return role
        if self._patch_band_mode(patch_id) != BandMode.NOT_BAND:
            return role
        return FrameRole.FREE

    def resolved_placement_role(self, chain_ref: ChainRef, chain: BoundaryChain) -> FrameRole:
        placement = self.placed_chains_map.get(chain_ref)
        if placement is not None:
            return placement.frame_role
        return self.effective_placement_role(chain_ref, chain)

    def placed_in_patch(self, patch_id: int) -> int:
        return self.placed_count_by_patch.get(patch_id, 0)

    def placed_h_in_patch(self, patch_id: int) -> int:
        return self.placed_h_count_by_patch.get(patch_id, 0)

    def placed_v_in_patch(self, patch_id: int) -> int:
        return self.placed_v_count_by_patch.get(patch_id, 0)

    def placed_free_in_patch(self, patch_id: int) -> int:
        return self.placed_free_count_by_patch.get(patch_id, 0)

    def placed_backbone_h_in_patch(self, patch_id: int) -> int:
        return self._backbone_h_count_by_patch.get(patch_id, 0)

    def placed_backbone_v_in_patch(self, patch_id: int) -> int:
        return self._backbone_v_count_by_patch.get(patch_id, 0)

    def placed_backbone_free_in_patch(self, patch_id: int) -> int:
        return self._backbone_free_count_by_patch.get(patch_id, 0)

    # Temporary compatibility accessors for score-owned caches until P7.
    def outer_chain_count(self, patch_id: int) -> int:
        return self._outer_chain_count_by_patch.get(patch_id, 0)

    def frame_chain_count(self, patch_id: int) -> int:
        return self._frame_chain_count_by_patch.get(patch_id, 0)

    def closure_pair_count(self, patch_id: int) -> int:
        return self._closure_pair_count_by_patch.get(patch_id, 0)

    def shape_profile(self, patch_id: int) -> Optional[PatchShapeProfile]:
        return self._shape_profile_by_patch.get(patch_id)

    def seam_relation(self, patch_a_id: int, patch_b_id: int) -> Optional[SeamRelationProfile]:
        return self.seam_relation_by_edge.get(_patch_pair_key(patch_a_id, patch_b_id))

    def total_placed(self) -> int:
        return len(self.build_order)

    def _patch_summary_attr(self, patch_id: int, attr_name: str, default):
        summary = self.patch_structural_summaries.get(patch_id)
        if summary is None:
            return default
        return getattr(summary, attr_name, default)

    def _patch_band_mode(self, patch_id: int) -> BandMode:
        return self._patch_summary_attr(patch_id, 'band_mode', BandMode.NOT_BAND)

    def _patch_allows_straighten_runtime(self, patch_id: int) -> bool:
        if not self.straighten_enabled:
            return False
        if self.band_spine(patch_id) is not None:
            return True
        return bool(
            self._patch_band_mode(patch_id) in {BandMode.SOFT_BAND, BandMode.HARD_BAND}
            and self._patch_summary_attr(patch_id, 'band_requires_intervention', False)
        )

    def _chain_polyline_length(self, chain: BoundaryChain) -> float:
        if len(chain.vert_cos) < 2:
            return 0.0
        return sum(
            (chain.vert_cos[index + 1] - chain.vert_cos[index]).length
            for index in range(len(chain.vert_cos) - 1)
        )

    def _chain_uv_length(self, chain: BoundaryChain) -> float:
        return self._chain_polyline_length(chain) * self.final_scale

    def _chain_normalized_stations(self, chain: BoundaryChain) -> list[float]:
        point_count = len(chain.vert_cos)
        if point_count <= 0:
            return []
        if point_count == 1:
            return [0.0]

        edge_lengths = [
            max((chain.vert_cos[index + 1] - chain.vert_cos[index]).length, 0.0)
            for index in range(point_count - 1)
        ]
        total_length = sum(edge_lengths)
        if total_length <= 1e-8:
            return [float(index) / float(point_count - 1) for index in range(point_count)]

        stations = [0.0]
        walked = 0.0
        for edge_length in edge_lengths:
            walked += edge_length
            stations.append(min(1.0, walked / total_length))
        stations[0] = 0.0
        stations[-1] = 1.0
        prev_value = 0.0
        for index, station in enumerate(stations):
            station = min(max(station, prev_value), 1.0)
            stations[index] = station
            prev_value = station
        stations[-1] = 1.0
        return stations

    def _average_station_sets(self, station_sets: list[list[float]]) -> Optional[list[float]]:
        if not station_sets:
            return None
        point_count = len(station_sets[0])
        if point_count <= 0:
            return None
        if any(len(stations) != point_count for stations in station_sets):
            return None
        if point_count == 1:
            return [0.0]

        averaged = [
            sum(stations[index] for stations in station_sets) / float(len(station_sets))
            for index in range(point_count)
        ]
        averaged[0] = 0.0
        averaged[-1] = 1.0
        prev_value = 0.0
        for index, station in enumerate(averaged):
            station = min(max(station, prev_value), 1.0)
            averaged[index] = station
            prev_value = station
        averaged[-1] = 1.0
        return averaged

    def _placement_axis_span(self, placement: ScaffoldChainPlacement) -> float:
        if len(placement.points) < 2:
            return 0.0
        start_uv = placement.points[0][1]
        end_uv = placement.points[-1][1]
        if placement.frame_role == FrameRole.H_FRAME:
            return abs(end_uv.x - start_uv.x)
        if placement.frame_role == FrameRole.V_FRAME:
            return abs(end_uv.y - start_uv.y)
        return (end_uv - start_uv).length

    def _patch_self_consensus_spans(
        self,
        chain_ref: ChainRef,
        chain: BoundaryChain,
        effective_role: Optional[FrameRole] = None,
    ) -> list[float]:
        role = effective_role if effective_role is not None else self.effective_placement_role(chain_ref, chain)
        if role not in {FrameRole.H_FRAME, FrameRole.V_FRAME}:
            return []

        patch_id, loop_index, chain_index = chain_ref
        node = self.graph.nodes.get(patch_id)
        if node is None or loop_index < 0 or loop_index >= len(node.boundary_loops):
            return []
        boundary_loop = node.boundary_loops[loop_index]
        if chain_index < 0 or chain_index >= len(boundary_loop.chains):
            return []

        chain_spans: list[float] = []
        fallback_spans: list[float] = []
        for other_use, other_chain in boundary_loop.iter_oriented_chain_records():
            other_index = other_use.chain_index
            if other_index == chain_index:
                continue
            other_ref = (patch_id, loop_index, other_index)
            other_role = self._resolved_chain_role(other_ref, other_chain)
            if other_role != role:
                continue
            other_placement = self.placed_chains_map.get(other_ref)
            if other_placement is not None and other_placement.frame_role == role:
                span = self._placement_axis_span(other_placement)
            else:
                span = self._chain_uv_length(other_chain)
            if span <= 1e-8:
                continue
            fallback_spans.append(span)
            if not self._chains_share_corner(chain, other_chain):
                chain_spans.append(span)
        return chain_spans if chain_spans else fallback_spans

    def _orthogonal_role(self, role: FrameRole) -> FrameRole:
        if role == FrameRole.H_FRAME:
            return FrameRole.V_FRAME
        if role == FrameRole.V_FRAME:
            return FrameRole.H_FRAME
        return FrameRole.FREE

    def _resolved_chain_role(self, chain_ref: ChainRef, chain: BoundaryChain) -> FrameRole:
        placement = self.placed_chains_map.get(chain_ref)
        if placement is not None:
            return placement.frame_role
        return self.effective_placement_role(chain_ref, chain)

    def _chains_share_corner(self, chain_a: BoundaryChain, chain_b: BoundaryChain) -> bool:
        corner_indices_a = {
            corner_index
            for corner_index in (chain_a.start_corner_index, chain_a.end_corner_index)
            if corner_index >= 0
        }
        corner_indices_b = {
            corner_index
            for corner_index in (chain_b.start_corner_index, chain_b.end_corner_index)
            if corner_index >= 0
        }
        return bool(corner_indices_a & corner_indices_b)

    def _paired_candidate_ref(
        self,
        chain_ref: ChainRef,
        chain: BoundaryChain,
        effective_role: Optional[FrameRole] = None,
    ) -> Optional[ChainRef]:
        role = effective_role if effective_role is not None else self.effective_placement_role(chain_ref, chain)
        if role not in {FrameRole.H_FRAME, FrameRole.V_FRAME}:
            return None

        patch_id, loop_index, chain_index = chain_ref
        node = self.graph.nodes.get(patch_id)
        if node is None or loop_index < 0 or loop_index >= len(node.boundary_loops):
            return None
        boundary_loop = node.boundary_loops[loop_index]
        if chain_index < 0 or chain_index >= len(boundary_loop.chains):
            return None

        best_ref: Optional[ChainRef] = None
        best_length = -1.0
        for other_use, other_chain in boundary_loop.iter_oriented_chain_records():
            other_index = other_use.chain_index
            if other_index == chain_index:
                continue
            if self._chains_share_corner(chain, other_chain):
                continue
            other_ref = (patch_id, loop_index, other_index)
            other_role = self._resolved_chain_role(other_ref, other_chain)
            if other_role != role:
                continue
            other_length = self._chain_polyline_length(other_chain)
            if other_length > best_length:
                best_length = other_length
                best_ref = other_ref
        return best_ref

    def _paired_band_station_sources(
        self,
        chain_ref: ChainRef,
        chain: BoundaryChain,
        effective_role: Optional[FrameRole] = None,
    ) -> Optional[tuple[list[float], list[float]]]:
        role = effective_role if effective_role is not None else self.effective_placement_role(chain_ref, chain)
        if role not in {FrameRole.H_FRAME, FrameRole.V_FRAME}:
            return None

        partner_ref = self._paired_candidate_ref(chain_ref, chain, effective_role=role)
        if partner_ref is None:
            return None
        partner_chain = self.graph.get_chain(*partner_ref)
        if partner_chain is None:
            return None
        partner_role = self._resolved_chain_role(partner_ref, partner_chain)
        if partner_role != role:
            return None

        current_stations = self._chain_normalized_stations(chain)
        partner_stations = self._chain_normalized_stations(partner_chain)
        if len(current_stations) < 2 or len(current_stations) != len(partner_stations):
            return None
        return current_stations, partner_stations

    def _patch_self_station_sets(
        self,
        chain_ref: ChainRef,
        chain: BoundaryChain,
        effective_role: Optional[FrameRole] = None,
    ) -> list[list[float]]:
        role = effective_role if effective_role is not None else self.effective_placement_role(chain_ref, chain)
        if role not in {FrameRole.H_FRAME, FrameRole.V_FRAME}:
            return []

        patch_id, loop_index, chain_index = chain_ref
        node = self.graph.nodes.get(patch_id)
        if node is None or loop_index < 0 or loop_index >= len(node.boundary_loops):
            return []
        boundary_loop = node.boundary_loops[loop_index]
        if chain_index < 0 or chain_index >= len(boundary_loop.chains):
            return []

        point_count = len(chain.vert_cos)
        if point_count < 2:
            return []

        station_sets = [self._chain_normalized_stations(chain)]
        for other_use, other_chain in boundary_loop.iter_oriented_chain_records():
            other_index = other_use.chain_index
            if other_index == chain_index:
                continue
            if len(other_chain.vert_cos) != point_count:
                continue
            other_ref = (patch_id, loop_index, other_index)
            other_role = self._resolved_chain_role(other_ref, other_chain)
            if other_role != role:
                continue
            station_sets.append(self._chain_normalized_stations(other_chain))
        return station_sets if len(station_sets) >= 2 else []

    def resolve_axis_authority_kind(
        self,
        chain_ref: ChainRef,
        chain: BoundaryChain,
        start_anchor: Optional[ChainAnchor] = None,
        end_anchor: Optional[ChainAnchor] = None,
        effective_role: Optional[FrameRole] = None,
    ) -> AxisAuthorityKind:
        if not self.straighten_enabled:
            return AxisAuthorityKind.NONE
        if not self._patch_allows_straighten_runtime(chain_ref[0]):
            return AxisAuthorityKind.NONE

        role = effective_role if effective_role is not None else self.effective_placement_role(chain_ref, chain)
        if role not in _STRONG_ROLES:
            return AxisAuthorityKind.NONE

        for anchor in (start_anchor, end_anchor):
            if anchor is None:
                continue
            source_chain = self.graph.get_chain(*anchor.source_ref)
            if source_chain is None:
                continue
            source_role = self._resolved_chain_role(anchor.source_ref, source_chain)
            if source_role in _STRONG_ROLES:
                return AxisAuthorityKind.DIRECT_STRONG_NEIGHBOR

        inherited_role = self.inherited_role_map.get(chain_ref, (FrameRole.FREE, 0))[0]
        if inherited_role in {FrameRole.H_FRAME, FrameRole.V_FRAME}:
            return AxisAuthorityKind.DIRECT_STRONG_NEIGHBOR

        partner_ref = self._paired_candidate_ref(chain_ref, chain, effective_role=role)
        if partner_ref is not None and partner_ref in self.placed_chains_map:
            return AxisAuthorityKind.PAIRED_CANDIDATE

        patch_id = chain_ref[0]
        if (
            self._patch_summary_attr(patch_id, 'axis_candidate', FrameRole.FREE) in {FrameRole.H_FRAME, FrameRole.V_FRAME}
            or self._patch_summary_attr(patch_id, 'junction_supported_axis', FrameRole.FREE) in {FrameRole.H_FRAME, FrameRole.V_FRAME}
        ):
            return AxisAuthorityKind.PATCH_SELF_CONSENSUS
        return AxisAuthorityKind.NONE

    def resolve_span_authority_kind(
        self,
        chain_ref: ChainRef,
        chain: BoundaryChain,
        start_anchor: Optional[ChainAnchor] = None,
        end_anchor: Optional[ChainAnchor] = None,
        effective_role: Optional[FrameRole] = None,
    ) -> SpanAuthorityKind:
        if not self.straighten_enabled:
            return SpanAuthorityKind.NONE
        if not self._patch_allows_straighten_runtime(chain_ref[0]):
            return SpanAuthorityKind.NONE

        role = effective_role if effective_role is not None else self.effective_placement_role(chain_ref, chain)
        if role not in _STRONG_ROLES:
            return SpanAuthorityKind.NONE

        for anchor in (start_anchor, end_anchor):
            if anchor is None:
                continue
            source_chain = self.graph.get_chain(*anchor.source_ref)
            if source_chain is None:
                continue
            source_role = self._resolved_chain_role(anchor.source_ref, source_chain)
            if source_role in _STRONG_ROLES:
                return SpanAuthorityKind.DIRECT_STRONG_NEIGHBOR

        partner_ref = self._paired_candidate_ref(chain_ref, chain, effective_role=role)
        if partner_ref is not None:
            partner_chain = self.graph.get_chain(*partner_ref)
            if partner_chain is not None:
                partner_role = self._resolved_chain_role(partner_ref, partner_chain)
                if partner_role == role:
                    return SpanAuthorityKind.PAIRED_CANDIDATE

        if self._patch_self_consensus_spans(chain_ref, chain, effective_role=role):
            return SpanAuthorityKind.PATCH_SELF_CONSENSUS
        return SpanAuthorityKind.NONE

    def resolve_target_span(
        self,
        chain_ref: ChainRef,
        chain: BoundaryChain,
        start_anchor: Optional[ChainAnchor] = None,
        end_anchor: Optional[ChainAnchor] = None,
        effective_role: Optional[FrameRole] = None,
        span_authority_kind: Optional[SpanAuthorityKind] = None,
    ) -> float:
        role = effective_role if effective_role is not None else self.effective_placement_role(chain_ref, chain)
        local_span = self._chain_uv_length(chain)
        if not self.straighten_enabled:
            return local_span
        if not self._patch_allows_straighten_runtime(chain_ref[0]):
            return local_span
        if role not in _STRONG_ROLES:
            return local_span

        authority_kind = (
            span_authority_kind
            if span_authority_kind is not None else
            self.resolve_span_authority_kind(
                chain_ref,
                chain,
                start_anchor,
                end_anchor,
                effective_role=role,
            )
        )

        if authority_kind == SpanAuthorityKind.DIRECT_STRONG_NEIGHBOR:
            spans: list[float] = []
            for anchor in (start_anchor, end_anchor):
                if anchor is None:
                    continue
                source_chain = self.graph.get_chain(*anchor.source_ref)
                if source_chain is None:
                    continue
                source_role = self._resolved_chain_role(anchor.source_ref, source_chain)
                if source_role != role:
                    continue
                source_placement = self.placed_chains_map.get(anchor.source_ref)
                if source_placement is not None and source_placement.frame_role == role:
                    span = self._placement_axis_span(source_placement)
                else:
                    span = self._chain_uv_length(source_chain)
                if span > 1e-8:
                    spans.append(span)
            if spans:
                return sum(spans) / float(len(spans))

        if authority_kind == SpanAuthorityKind.PAIRED_CANDIDATE:
            partner_ref = self._paired_candidate_ref(chain_ref, chain, effective_role=role)
            if partner_ref is not None:
                partner_chain = self.graph.get_chain(*partner_ref)
                partner_placement = self.placed_chains_map.get(partner_ref)
                if partner_placement is not None and partner_placement.frame_role == role:
                    span = self._placement_axis_span(partner_placement)
                    if span > 1e-8:
                        return span
                if partner_chain is not None:
                    span = self._chain_uv_length(partner_chain)
                    if span > 1e-8:
                        return span

        if authority_kind == SpanAuthorityKind.PATCH_SELF_CONSENSUS:
            spans = self._patch_self_consensus_spans(chain_ref, chain, effective_role=role)
            if spans:
                return sum(spans) / float(len(spans))

        return local_span

    def resolve_station_authority_kind(
        self,
        chain_ref: ChainRef,
        chain: BoundaryChain,
        start_anchor: Optional[ChainAnchor] = None,
        end_anchor: Optional[ChainAnchor] = None,
        effective_role: Optional[FrameRole] = None,
    ) -> StationAuthorityKind:
        _ = start_anchor, end_anchor
        if not self.straighten_enabled:
            return StationAuthorityKind.NONE
        if not self._patch_allows_straighten_runtime(chain_ref[0]):
            return StationAuthorityKind.NONE

        role = effective_role if effective_role is not None else self.effective_placement_role(chain_ref, chain)
        if role not in _STRONG_ROLES:
            return StationAuthorityKind.NONE

        if self._paired_band_station_sources(chain_ref, chain, effective_role=role) is not None:
            return StationAuthorityKind.PAIRED_BAND_CONSENSUS

        if self._patch_self_station_sets(chain_ref, chain, effective_role=role):
            return StationAuthorityKind.PATCH_SELF_CONSENSUS

        return StationAuthorityKind.SELF_ONLY

    def resolve_shared_station_map(
        self,
        chain_ref: ChainRef,
        chain: BoundaryChain,
        start_anchor: Optional[ChainAnchor] = None,
        end_anchor: Optional[ChainAnchor] = None,
        effective_role: Optional[FrameRole] = None,
        station_authority_kind: Optional[StationAuthorityKind] = None,
    ) -> Optional[list[float]]:
        _ = start_anchor, end_anchor
        if not self.straighten_enabled:
            return None
        if not self._patch_allows_straighten_runtime(chain_ref[0]):
            return None

        role = effective_role if effective_role is not None else self.effective_placement_role(chain_ref, chain)
        if role not in _STRONG_ROLES:
            return None

        authority_kind = (
            station_authority_kind
            if station_authority_kind is not None else
            self.resolve_station_authority_kind(
                chain_ref,
                chain,
                start_anchor,
                end_anchor,
                effective_role=role,
            )
        )

        if authority_kind == StationAuthorityKind.PAIRED_BAND_CONSENSUS:
            station_sources = self._paired_band_station_sources(chain_ref, chain, effective_role=role)
            if station_sources is not None:
                return self._average_station_sets(list(station_sources))

        if authority_kind == StationAuthorityKind.PATCH_SELF_CONSENSUS:
            station_sets = self._patch_self_station_sets(chain_ref, chain, effective_role=role)
            if station_sets:
                return self._average_station_sets(station_sets)

        return None

    def resolve_parameter_authority_kind(
        self,
        chain_ref: ChainRef,
        chain: BoundaryChain,
        start_anchor: Optional[ChainAnchor] = None,
        end_anchor: Optional[ChainAnchor] = None,
        effective_role: Optional[FrameRole] = None,
    ) -> ParameterAuthorityKind:
        _ = chain_ref, start_anchor, end_anchor
        if not self.straighten_enabled:
            return ParameterAuthorityKind.NONE
        if not self._patch_allows_straighten_runtime(chain_ref[0]):
            return ParameterAuthorityKind.NONE

        role = effective_role if effective_role is not None else self.effective_placement_role(chain_ref, chain)
        if role in _STRONG_ROLES:
            return ParameterAuthorityKind.SELF_ARCLENGTH
        return ParameterAuthorityKind.NONE

    def _is_corner_orthogonal_band_turn(self, turn_angle_deg: float) -> bool:
        angle = abs(float(turn_angle_deg))
        return 60.0 <= angle <= 120.0

    def _same_patch_continuation_hint(
        self,
        chain_ref: ChainRef,
        chain: BoundaryChain,
        anchor: Optional[ChainAnchor],
        *,
        is_start_anchor: bool,
    ) -> Optional[tuple[int, FrameRole]]:
        if anchor is None or anchor.source_kind != PlacementSourceKind.SAME_PATCH:
            return None
        if anchor.source_ref[0] != chain_ref[0] or anchor.source_ref[1] != chain_ref[1]:
            return None

        patch_id, loop_index, chain_index = chain_ref
        node = self.graph.nodes.get(patch_id)
        if node is None or loop_index >= len(node.boundary_loops):
            return None
        boundary_loop = node.boundary_loops[loop_index]

        corner_index = chain.start_corner_index if is_start_anchor else chain.end_corner_index
        if corner_index < 0 or corner_index >= len(boundary_loop.corners):
            return None
        corner = boundary_loop.corners[corner_index]
        # ARCHITECTURAL_DEBT: F3_LOOP_PREVNEXT
        # Same-patch continuation still infers prev/next chain identity from
        # corner records instead of direct ChainUse loop adjacency.
        expected_source_chain_index = corner.prev_chain_index if is_start_anchor else corner.next_chain_index
        expected_candidate_chain_index = corner.next_chain_index if is_start_anchor else corner.prev_chain_index
        if expected_candidate_chain_index != chain_index or expected_source_chain_index != anchor.source_ref[2]:
            return None
        if not self._is_corner_orthogonal_band_turn(corner.turn_angle_deg):
            return None

        source_chain = self.graph.get_chain(*anchor.source_ref)
        if source_chain is None:
            return None
        source_placement = self.placed_chains_map.get(anchor.source_ref)
        source_role = (
            source_placement.frame_role
            if source_placement is not None else
            self.effective_placement_role(anchor.source_ref, source_chain)
        )
        if source_role not in {FrameRole.H_FRAME, FrameRole.V_FRAME}:
            return None

        priority = 0
        if source_chain.frame_role == FrameRole.FREE:
            priority += 2
        if len(source_chain.vert_cos) <= 2:
            priority += 1
        return priority, self._orthogonal_role(source_role)

    def should_gate_inherited_same_patch(self, chain_ref: ChainRef, chain: BoundaryChain) -> bool:
        if not self.straighten_enabled or chain.frame_role != FrameRole.FREE:
            return False
        eff_role = self.effective_placement_role(chain_ref, chain)
        if eff_role not in {FrameRole.H_FRAME, FrameRole.V_FRAME}:
            return False
        patch_id = chain_ref[0]
        if self._patch_summary_attr(patch_id, 'spine_axis', FrameRole.FREE) in {FrameRole.H_FRAME, FrameRole.V_FRAME}:
            return False
        if self._patch_summary_attr(patch_id, 'inherited_spine_count', 0) >= 2:
            return False
        if self._patch_allows_straighten_runtime(patch_id):
            return False
        return True

    def should_use_continuation_role(self, chain_ref: ChainRef, chain: BoundaryChain) -> bool:
        if not self.straighten_enabled or chain.frame_role != FrameRole.FREE:
            return False
        eff_role = self.effective_placement_role(chain_ref, chain)
        if eff_role not in {FrameRole.H_FRAME, FrameRole.V_FRAME}:
            return False
        patch_id = chain_ref[0]
        if not self._patch_allows_straighten_runtime(patch_id):
            return False
        if self._patch_summary_attr(patch_id, 'spine_axis', FrameRole.FREE) in {FrameRole.H_FRAME, FrameRole.V_FRAME}:
            return False
        if self._patch_summary_attr(patch_id, 'inherited_spine_count', 0) >= 2:
            return False
        return bool(
            self._patch_summary_attr(patch_id, 'single_sided_inherited_support', False)
            or self._patch_band_mode(patch_id) != BandMode.NOT_BAND
        )

    def backbone_placement_role(
        self,
        chain_ref: ChainRef,
        chain: BoundaryChain,
        effective_role: Optional[FrameRole] = None,
    ) -> FrameRole:
        role = effective_role if effective_role is not None else self.effective_placement_role(chain_ref, chain)
        if self.should_gate_inherited_same_patch(chain_ref, chain):
            return FrameRole.FREE
        return role

    def candidate_placement_role(
        self,
        chain_ref: ChainRef,
        chain: BoundaryChain,
        start_anchor: Optional[ChainAnchor],
        end_anchor: Optional[ChainAnchor],
        effective_role: Optional[FrameRole] = None,
    ) -> FrameRole:
        role = effective_role if effective_role is not None else self.effective_placement_role(chain_ref, chain)
        _ = start_anchor, end_anchor
        return role

    def continuation_placement_role(
        self,
        chain_ref: ChainRef,
        chain: BoundaryChain,
        start_anchor: Optional[ChainAnchor],
        end_anchor: Optional[ChainAnchor],
        effective_role: Optional[FrameRole] = None,
    ) -> FrameRole:
        role = effective_role if effective_role is not None else self.effective_placement_role(chain_ref, chain)
        if not self.should_use_continuation_role(chain_ref, chain):
            return role
        if role not in {FrameRole.H_FRAME, FrameRole.V_FRAME}:
            return role

        has_cross_patch_anchor = any(
            anchor is not None and anchor.source_kind == PlacementSourceKind.CROSS_PATCH
            for anchor in (start_anchor, end_anchor)
        )
        if has_cross_patch_anchor:
            return role

        best_priority: Optional[int] = None
        derived_roles: set[FrameRole] = set()
        for is_start_anchor, anchor in (
            (True, start_anchor),
            (False, end_anchor),
        ):
            hint = self._same_patch_continuation_hint(
                chain_ref,
                chain,
                anchor,
                is_start_anchor=is_start_anchor,
            )
            if hint is None:
                continue
            priority, derived_role = hint
            if best_priority is None or priority > best_priority:
                best_priority = priority
                derived_roles = {derived_role}
            elif priority == best_priority:
                derived_roles.add(derived_role)

        if len(derived_roles) == 1:
            return next(iter(derived_roles))
        return FrameRole.FREE

    def is_chain_available(self, chain_ref: ChainRef) -> bool:
        return chain_ref not in self.placed_chain_refs and chain_ref not in self.rejected_chain_refs

    def placed_patch_ids(self) -> tuple[int, ...]:
        return tuple(sorted(self.placed_count_by_patch.keys()))

    def reject_chain(self, chain_ref: ChainRef) -> None:
        self.rejected_chain_refs.add(chain_ref)
        self._cached_evals.pop(chain_ref, None)
        self._dirty_refs.discard(chain_ref)

    def dependency_patches_from_anchors(
        self,
        owner_patch_id: int,
        *anchors: Optional[ChainAnchor],
    ) -> tuple[int, ...]:
        return tuple(
            sorted({
                anchor.source_ref[0]
                for anchor in anchors
                if anchor is not None and anchor.source_ref[0] != owner_patch_id
            })
        )

    def register_chain(
        self,
        chain_ref: ChainRef,
        chain: BoundaryChain,
        chain_placement: ScaffoldChainPlacement,
        uv_points: list[Vector],
        dependency_patches: tuple[int, ...] = (),
        placed_role: Optional[FrameRole] = None,
    ) -> None:
        self.placed_chain_refs.add(chain_ref)
        self.placed_chains_map[chain_ref] = chain_placement
        self.chain_dependency_patches[chain_ref] = tuple(sorted(set(dependency_patches)))
        self.build_order.append(chain_ref)
        self.placed_count_by_patch[chain_ref[0]] = self.placed_count_by_patch.get(chain_ref[0], 0) + 1
        # Use effective placement role for counters so bookkeeping matches geometry
        eff_role = placed_role if placed_role is not None else self.effective_placement_role(chain_ref, chain)
        if eff_role == FrameRole.H_FRAME:
            self.placed_h_count_by_patch[chain_ref[0]] = self.placed_h_count_by_patch.get(chain_ref[0], 0) + 1
        elif eff_role == FrameRole.V_FRAME:
            self.placed_v_count_by_patch[chain_ref[0]] = self.placed_v_count_by_patch.get(chain_ref[0], 0) + 1
        else:
            self.placed_free_count_by_patch[chain_ref[0]] = self.placed_free_count_by_patch.get(chain_ref[0], 0) + 1
        backbone_role = self.backbone_placement_role(chain_ref, chain, effective_role=eff_role)
        if backbone_role == FrameRole.H_FRAME:
            self._backbone_h_count_by_patch[chain_ref[0]] = self._backbone_h_count_by_patch.get(chain_ref[0], 0) + 1
        elif backbone_role == FrameRole.V_FRAME:
            self._backbone_v_count_by_patch[chain_ref[0]] = self._backbone_v_count_by_patch.get(chain_ref[0], 0) + 1
        else:
            self._backbone_free_count_by_patch[chain_ref[0]] = self._backbone_free_count_by_patch.get(chain_ref[0], 0) + 1
        _cf_register_points(chain_ref, chain, uv_points, self.point_registry, self.vert_to_placements)
        self._cached_evals.pop(chain_ref, None)
        self._dirty_refs.discard(chain_ref)
        _mark_neighbors_dirty(self, chain_ref, chain)


def _mark_neighbors_dirty(
    runtime_policy: FrontierRuntimePolicy,
    chain_ref: ChainRef,
    chain: BoundaryChain,
) -> None:
    """Помечает dirty все pool refs, затронутые только что размещённым chain.

    Два триггера:
    1. Shared vertex — anchor-lookup этого ref мог измениться.
    2. First-chain-in-patch — placed_in_patch изменился 0→1, score всех refs
       этого patch меняется из-за momentum bonus.
    """
    dirty = runtime_policy._dirty_refs
    vtp = runtime_policy._vert_to_pool_refs
    patch_id = chain_ref[0]

    for vi in chain.vert_indices:
        for ref in vtp.get(vi, ()):
            dirty.add(ref)

    if runtime_policy.placed_count_by_patch.get(patch_id, 0) == 1:
        for refs_list in vtp.values():
            for ref in refs_list:
                if ref[0] == patch_id:
                    dirty.add(ref)
    for ref in runtime_policy._patch_to_pool_refs.get(patch_id, ()):
        dirty.add(ref)


def _cf_register_points(
    chain_ref: ChainRef,
    chain: BoundaryChain,
    uv_points: list[Vector],
    point_registry: PointRegistry,
    vert_to_placements: VertexPlacementMap,
) -> None:
    """Регистрирует все точки chain в обоих registry."""
    for i, uv in enumerate(uv_points):
        key = _point_registry_key(chain_ref, i)
        point_registry[key] = uv.copy()

        if i < len(chain.vert_indices):
            vert_idx = chain.vert_indices[i]
            vert_to_placements.setdefault(vert_idx, []).append((chain_ref, i))
