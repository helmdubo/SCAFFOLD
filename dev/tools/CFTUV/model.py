from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntFlag
from mathutils import Vector
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .solve_records import QuiltFrontierTelemetry
    from .solve_skeleton import SkeletonSolveReport


class PatchType(str, Enum):
    """Dispatch key for the patch UV strategy."""

    WALL = "WALL"
    FLOOR = "FLOOR"
    SLOPE = "SLOPE"


class WorldFacing(str, Enum):
    """Coarse patch orientation relative to world Z."""

    UP = "UP"
    DOWN = "DOWN"
    SIDE = "SIDE"


class LoopKind(str, Enum):
    """Kind of closed boundary loop."""

    OUTER = "OUTER"
    HOLE = "HOLE"


class FrameRole(str, Enum):
    """Alignment role of a boundary chain in the local patch basis."""

    H_FRAME = "H_FRAME"
    V_FRAME = "V_FRAME"
    STRAIGHTEN = "STRAIGHTEN"
    FREE = "FREE"


class BandMode(str, Enum):
    """Strict runtime mode for strip-like BAND patches."""

    NOT_BAND = "NOT_BAND"
    SOFT_BAND = "SOFT_BAND"
    HARD_BAND = "HARD_BAND"


class ChainNeighborKind(str, Enum):
    """Topology class of a boundary chain neighbor."""

    PATCH = "PATCH"
    MESH_BORDER = "MESH_BORDER"
    SEAM_SELF = "SEAM_SELF"


class CornerKind(str, Enum):
    """Semantic class of a loop corner."""

    JUNCTION = "JUNCTION"
    GEOMETRIC = "GEOMETRIC"


class PlacementSourceKind(str, Enum):
    """Provenance of a scaffolded source sample or anchor."""

    CHAIN = "chain"
    SAME_PATCH = "same_patch"
    CROSS_PATCH = "cross_patch"


class AxisAuthorityKind(str, Enum):
    """Who owns scaffold axis/frame authority for a placed chain."""

    NONE = "none"
    DIRECT_STRONG_NEIGHBOR = "direct-strong-neighbor"
    PAIRED_CANDIDATE = "paired-candidate"
    PATCH_SELF_CONSENSUS = "patch-self-consensus"


class SpanAuthorityKind(str, Enum):
    """Who owns resolved scaffold span/frame segment for a placed chain."""

    NONE = "none"
    DIRECT_STRONG_NEIGHBOR = "direct-strong-neighbor"
    PAIRED_CANDIDATE = "paired-candidate"
    PATCH_SELF_CONSENSUS = "patch-self-consensus"


class StationAuthorityKind(str, Enum):
    """Who owns shared station-domain authority for a placed chain."""

    NONE = "none"
    PAIRED_BAND_CONSENSUS = "paired-band-consensus"
    PATCH_SELF_CONSENSUS = "patch-self-consensus"
    SELF_ONLY = "self-only"


class ParameterAuthorityKind(str, Enum):
    """Who owns local stationing authority along a placed chain."""

    NONE = "none"
    SELF_ARCLENGTH = "self-arclength"


class ClosureAnchorMode(str, Enum):
    """Closure seam anchor availability classification."""

    UNKNOWN = "unknown"
    DUAL_ANCHOR = "dual-anchor"
    ONE_ANCHOR = "one-anchor"
    MIXED = "mixed"


class FrameAxisKind(str, Enum):
    """Diagnostic row / column class kind inside a quilt."""

    ROW = "ROW"
    COLUMN = "COLUMN"


class SkeletonFlags(IntFlag):
    """Служебные флаги skeleton solve на уровне junction."""

    SINGULAR_SPLIT = 1 << 0
    PURE_FREE = 1 << 1
    UNCONSTRAINED_COL = 1 << 2
    UNCONSTRAINED_ROW = 1 << 3


# Canonical solve/runtime reference to one boundary chain:
# (patch_id, loop_index, chain_index).
ChainRef = tuple[int, int, int]
ChainId = tuple[int, ...]
PatchEdgeKey = tuple[int, int]
LoopChainRef = tuple[int, int]
SourcePoint = tuple[int, Vector]
AnchorAdjustment = tuple[ChainRef, int, Vector]


@dataclass(frozen=True)
class FormattedReport:
    lines: list[str]
    summary: str


def _chain_id_from_spans(edge_indices: list[int], vert_indices: list[int]) -> ChainId:
    if edge_indices:
        return (-1, *sorted(int(edge_index) for edge_index in edge_indices))
    return (-2, *sorted(int(vert_index) for vert_index in vert_indices))


def _chain_axis_sign_from_vertices(vert_indices: list[int], edge_indices: list[int]) -> int:
    sequence = tuple(int(vert_index) for vert_index in vert_indices) or tuple(int(edge_index) for edge_index in edge_indices)
    if not sequence:
        return 1

    reversed_sequence = tuple(reversed(sequence))
    if sequence == reversed_sequence:
        return 1
    return 1 if sequence < reversed_sequence else -1


@dataclass(frozen=True)
class ChainUse:
    """Patch-local usage of a boundary chain in one oriented boundary loop walk."""

    chain_id: ChainId
    patch_id: int
    loop_index: int
    chain_index: int
    position_in_loop: int
    axis_sign: int
    role_in_loop: FrameRole


def _build_chain_use(
    chain: "BoundaryChain",
    patch_id: int,
    loop_index: int,
    chain_index: int,
    position_in_loop: Optional[int] = None,
) -> ChainUse:
    return ChainUse(
        chain_id=_chain_id_from_spans(chain.edge_indices, chain.vert_indices),
        patch_id=int(patch_id),
        loop_index=int(loop_index),
        chain_index=int(chain_index),
        position_in_loop=int(chain_index if position_in_loop is None else position_in_loop),
        axis_sign=_chain_axis_sign_from_vertices(chain.vert_indices, chain.edge_indices),
        role_in_loop=chain.frame_role,
    )


@dataclass(frozen=True)
class ChainIncidence:
    """One chain-use incidence inside a junction disk-cycle order."""

    chain_use: ChainUse
    role: FrameRole
    side: str
    angle: float


@dataclass
class BoundaryChain:
    """Continuous part of a boundary loop with one neighbor.
    Chain — первичная единица placement в solve."""

    # Intrinsic topology
    vert_indices: list[int] = field(default_factory=list)
    vert_cos: list[Vector] = field(default_factory=list)
    edge_indices: list[int] = field(default_factory=list)
    side_face_indices: list[int] = field(default_factory=list)
    is_closed: bool = False

    # Contextual topology
    neighbor_patch_id: int = -1
    frame_role: FrameRole = FrameRole.FREE
    start_loop_index: int = 0
    end_loop_index: int = 0

    # Derived topology
    start_corner_index: int = -1
    end_corner_index: int = -1
    is_corner_split: bool = False

    # Dihedral convexity at seam between owner patch and neighbor patch.
    # -1.0 = concave (inner corner), +1.0 = convex (outer corner), 0.0 = neutral/unknown.
    # Computed only for neighbor_kind == PATCH. Zero for MESH_BORDER and SEAM_SELF.
    dihedral_convexity: float = 0.0

    @property
    def neighbor_kind(self) -> ChainNeighborKind:
        """Derive the neighbor kind from the encoded neighbor id."""

        if self.neighbor_patch_id == -2:
            return ChainNeighborKind.SEAM_SELF
        if self.neighbor_patch_id == -1:
            return ChainNeighborKind.MESH_BORDER
        return ChainNeighborKind.PATCH

    @property
    def has_patch_neighbor(self) -> bool:
        return self.neighbor_kind == ChainNeighborKind.PATCH

    @property
    def start_vert_index(self) -> int:
        return self.vert_indices[0] if self.vert_indices else -1

    @property
    def end_vert_index(self) -> int:
        return self.vert_indices[-1] if self.vert_indices else -1


@dataclass
class BoundaryCorner:
    """Junction corner between two neighboring chains inside one loop.
    Угол не имеет своей геометрии, он только соединяет две chain."""

    loop_vert_index: int = -1
    vert_index: int = -1
    vert_co: Vector = field(default_factory=lambda: Vector((0.0, 0.0, 0.0)))

    prev_chain_index: int = -1
    next_chain_index: int = -1

    corner_kind: CornerKind = CornerKind.JUNCTION
    turn_angle_deg: float = 0.0

    prev_role: FrameRole = FrameRole.FREE
    next_role: FrameRole = FrameRole.FREE

    wedge_face_indices: tuple[int, ...] = ()
    wedge_normal: Vector = field(default_factory=lambda: Vector((0.0, 0.0, 0.0)))
    wedge_normal_valid: bool = False

    @property
    def corner_type(self) -> str:
        return f"{self.prev_role.value}_TO_{self.next_role.value}"

    @property
    def is_geometric(self) -> bool:
        return self.corner_kind == CornerKind.GEOMETRIC


@dataclass
class BoundaryLoop:
    """Closed boundary loop of a patch."""

    # Composite loop geometry
    vert_indices: list[int] = field(default_factory=list)
    vert_cos: list[Vector] = field(default_factory=list)
    edge_indices: list[int] = field(default_factory=list)
    side_face_indices: list[int] = field(default_factory=list)

    # Contextual loop semantics
    kind: LoopKind = LoopKind.OUTER
    depth: int = 0

    # Composite substructure
    chains: list[BoundaryChain] = field(default_factory=list)
    corners: list[BoundaryCorner] = field(default_factory=list)
    chain_uses: list[ChainUse] = field(default_factory=list)

    def get_chain_use(self, chain_index: int) -> Optional[ChainUse]:
        if chain_index < 0 or chain_index >= len(self.chains):
            return None
        if self.chain_uses and chain_index < len(self.chain_uses):
            return self.chain_uses[chain_index]
        return None

    def iter_chain_uses_oriented(self) -> tuple[ChainUse, ...]:
        if not self.chain_uses or len(self.chain_uses) != len(self.chains):
            return ()
        return tuple(
            sorted(
                self.chain_uses,
                key=lambda chain_use: (
                    chain_use.position_in_loop,
                    chain_use.chain_index,
                ),
            )
        )

    def iter_oriented_chain_records(self) -> tuple[tuple[ChainUse, "BoundaryChain"], ...]:
        records = []
        for chain_use in self.iter_chain_uses_oriented():
            if 0 <= chain_use.chain_index < len(self.chains):
                records.append((chain_use, self.chains[chain_use.chain_index]))
        return tuple(records)

    def oriented_neighbor_chain_indices(self, chain_index: int) -> tuple[int, ...]:
        if chain_index < 0 or chain_index >= len(self.chains):
            return ()

        oriented_chain_uses = self.iter_chain_uses_oriented()
        if len(oriented_chain_uses) < 2:
            return ()

        oriented_position = -1
        for position, chain_use in enumerate(oriented_chain_uses):
            if chain_use.chain_index == chain_index:
                oriented_position = position
                break
        if oriented_position < 0:
            return ()

        chain_count = len(oriented_chain_uses)
        prev_index = oriented_chain_uses[(oriented_position - 1) % chain_count].chain_index
        next_index = oriented_chain_uses[(oriented_position + 1) % chain_count].chain_index
        if prev_index == next_index:
            return (prev_index,)
        return (prev_index, next_index)

    def resolve_chain_use_source_point(self, chain_use: ChainUse, source_point_index: int) -> Optional[tuple[int, int]]:
        if chain_use.chain_index < 0 or chain_use.chain_index >= len(self.chains):
            return None

        chain = self.chains[chain_use.chain_index]
        if source_point_index < 0 or source_point_index >= len(chain.vert_indices):
            return None

        loop_count = len(self.vert_indices)
        if loop_count <= 0:
            return None

        loop_point_index = (chain.start_loop_index + source_point_index) % loop_count
        vert_index = chain.vert_indices[source_point_index]
        return (loop_point_index, vert_index)


@dataclass
class PatchNode:
    """Patch node stored inside the central PatchGraph IR."""

    # Intrinsic topology / geometry
    patch_id: int
    face_indices: list[int]
    centroid: Vector = field(default_factory=lambda: Vector((0.0, 0.0, 0.0)))
    normal: Vector = field(default_factory=lambda: Vector((0.0, 0.0, 1.0)))
    area: float = 0.0
    perimeter: float = 0.0
    basis_u: Vector = field(default_factory=lambda: Vector((1.0, 0.0, 0.0)))
    basis_v: Vector = field(default_factory=lambda: Vector((0.0, 0.0, 1.0)))

    # Contextual semantics
    patch_type: PatchType = PatchType.WALL
    world_facing: WorldFacing = WorldFacing.SIDE

    # Composite topology
    boundary_loops: list[BoundaryLoop] = field(default_factory=list)

    # Derived debug geometry
    mesh_verts: list[Vector] = field(default_factory=list)
    mesh_vert_indices: list[int] = field(default_factory=list)
    mesh_edges: list[tuple[int, int]] = field(default_factory=list)
    mesh_tris: list[tuple[int, int, int]] = field(default_factory=list)

    @property
    def semantic_key(self) -> str:
        patch_type = self.patch_type.value if hasattr(self.patch_type, "value") else str(self.patch_type)
        world_facing = self.world_facing.value if hasattr(self.world_facing, "value") else str(self.world_facing)
        return f"{patch_type}.{world_facing}"

    def iter_boundary_loop_oriented(self, loop_index: int = 0) -> tuple[ChainUse, ...]:
        """Возвращает chain uses в каноническом порядке обхода boundary loop."""

        if loop_index < 0 or loop_index >= len(self.boundary_loops):
            return ()

        boundary_loop = self.boundary_loops[loop_index]
        if not boundary_loop.chain_uses or len(boundary_loop.chain_uses) != len(boundary_loop.chains):
            return tuple(
                _build_chain_use(
                    chain,
                    self.patch_id,
                    loop_index,
                    chain_index,
                    position_in_loop=chain_index,
                )
                for chain_index, chain in enumerate(boundary_loop.chains)
            )
        return boundary_loop.iter_chain_uses_oriented()


@dataclass
class SeamEdge:
    """Shared seam relation between two neighboring patches."""

    patch_a_id: int
    patch_b_id: int
    shared_length: float = 0.0
    shared_vert_indices: list[int] = field(default_factory=list)
    longest_edge_verts: tuple[int, int] = (0, 0)
    longest_edge_length: float = 0.0


@dataclass(frozen=True)
class UVSettings:
    """Immutable snapshot of UV settings passed through the pipeline."""

    texel_density: int = 512
    texture_size: int = 2048
    uv_scale: float = 1.0
    uv_range_limit: float = 16.0
    straighten_strips: bool = False

    @property
    def final_scale(self) -> float:
        return (self.texel_density / self.texture_size) * self.uv_scale

    @staticmethod
    def from_blender_settings(settings) -> "UVSettings":
        """Build a UVSettings object from the Blender PropertyGroup."""

        return UVSettings(
            texel_density=int(settings.target_texel_density),
            texture_size=int(settings.texture_size),
            uv_scale=float(settings.uv_scale),
            uv_range_limit=float(settings.uv_range_limit),
            straighten_strips=bool(getattr(settings, 'straighten_strips', False)),
        )


@dataclass(frozen=True)
class MeshPreflightIssue:
    """Preflight issue blocking the solve pipeline."""

    code: str
    message: str
    face_indices: tuple[int, ...] = ()
    edge_indices: tuple[int, ...] = ()
    vert_indices: tuple[int, ...] = ()


@dataclass
class MeshPreflightReport:
    """Preflight result for solve input mesh."""

    checked_face_indices: tuple[int, ...] = ()
    issues: list[MeshPreflightIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.issues

# ============================================================
# PatchGraph — центральный IR
# ============================================================

@dataclass
class PatchGraph:
    """Central IR with patch nodes, seam edges, and lookup tables."""

    nodes: dict[int, PatchNode] = field(default_factory=dict)
    edges: dict[PatchEdgeKey, SeamEdge] = field(default_factory=dict)
    face_to_patch: dict[int, int] = field(default_factory=dict)
    _adjacency: dict[int, set[int]] = field(default_factory=dict)
    chain_use_by_ref: dict[ChainRef, ChainUse] = field(default_factory=dict)
    chain_refs_by_chain_id: dict[ChainId, tuple[ChainRef, ...]] = field(default_factory=dict)

    def add_node(self, node: PatchNode) -> None:
        self.nodes[node.patch_id] = node
        self._adjacency.setdefault(node.patch_id, set())
        for face_index in node.face_indices:
            self.face_to_patch[face_index] = node.patch_id

    def add_edge(self, seam: SeamEdge) -> None:
        key = (min(seam.patch_a_id, seam.patch_b_id), max(seam.patch_a_id, seam.patch_b_id))
        self.edges[key] = seam
        self._adjacency.setdefault(seam.patch_a_id, set()).add(seam.patch_b_id)
        self._adjacency.setdefault(seam.patch_b_id, set()).add(seam.patch_a_id)

    def get_neighbors(self, patch_id: int) -> set[int]:
        return self._adjacency.get(patch_id, set())

    def get_seam(self, patch_a: int, patch_b: int) -> Optional[SeamEdge]:
        key = (min(patch_a, patch_b), max(patch_a, patch_b))
        return self.edges.get(key)

    def get_patch_semantic_key(self, patch_id: int) -> str:
        node = self.nodes.get(patch_id)
        if node is None:
            return "UNKNOWN"
        return node.semantic_key

    def get_chain(self, patch_id: int, loop_index: int, chain_index: int) -> Optional[BoundaryChain]:
        node = self.nodes.get(patch_id)
        if node is None or loop_index < 0 or loop_index >= len(node.boundary_loops):
            return None
        boundary_loop = node.boundary_loops[loop_index]
        if chain_index < 0 or chain_index >= len(boundary_loop.chains):
            return None
        return boundary_loop.chains[chain_index]

    def rebuild_chain_use_index(self) -> None:
        chain_use_by_ref: dict[ChainRef, ChainUse] = {}
        refs_by_chain_id: dict[ChainId, list[ChainRef]] = {}

        for patch_id, node in self.nodes.items():
            for loop_index, boundary_loop in enumerate(node.boundary_loops):
                if not boundary_loop.chain_uses or len(boundary_loop.chain_uses) != len(boundary_loop.chains):
                    boundary_loop.chain_uses = [
                        _build_chain_use(
                            chain,
                            patch_id,
                            loop_index,
                            chain_index,
                            position_in_loop=chain_index,
                        )
                        for chain_index, chain in enumerate(boundary_loop.chains)
                    ]

                for chain_use in boundary_loop.chain_uses:
                    ref = (chain_use.patch_id, chain_use.loop_index, chain_use.chain_index)
                    chain_use_by_ref[ref] = chain_use
                    refs_by_chain_id.setdefault(chain_use.chain_id, []).append(ref)

        self.chain_use_by_ref = chain_use_by_ref
        self.chain_refs_by_chain_id = {
            chain_id: tuple(refs)
            for chain_id, refs in refs_by_chain_id.items()
        }

    def get_chain_use(self, patch_id: int, loop_index: int, chain_index: int) -> Optional[ChainUse]:
        ref = (patch_id, loop_index, chain_index)
        chain_use = self.chain_use_by_ref.get(ref)
        if chain_use is not None:
            return chain_use

        chain = self.get_chain(patch_id, loop_index, chain_index)
        if chain is None:
            return None
        return _build_chain_use(
            chain,
            patch_id,
            loop_index,
            chain_index,
            position_in_loop=chain_index,
        )

    def iter_chain_uses_for_chain_id(self, chain_id: ChainId) -> tuple[ChainUse, ...]:
        refs = self.chain_refs_by_chain_id.get(chain_id, ())
        return tuple(
            chain_use
            for chain_use in (
                self.chain_use_by_ref.get(ref)
                for ref in refs
            )
            if chain_use is not None
        )

    def find_chains_touching_vertex(
        self,
        patch_id: int,
        vert_index: int,
        exclude: Optional[LoopChainRef] = None,
    ) -> list[LoopChainRef]:
        node = self.nodes.get(patch_id)
        if node is None or vert_index < 0:
            return []

        matches = []
        for loop_index, boundary_loop in enumerate(node.boundary_loops):
            for chain_index, chain in enumerate(boundary_loop.chains):
                if exclude == (loop_index, chain_index):
                    continue
                if chain.start_vert_index == vert_index or chain.end_vert_index == vert_index:
                    matches.append((loop_index, chain_index))
        return matches

    def get_chain_endpoint_neighbors(self, patch_id: int, loop_index: int, chain_index: int) -> dict[str, list[LoopChainRef]]:
        chain = self.get_chain(patch_id, loop_index, chain_index)
        if chain is None:
            return {"start": [], "end": []}

        return {
            "start": self.find_chains_touching_vertex(
                patch_id,
                chain.start_vert_index,
                exclude=(loop_index, chain_index),
            ),
            "end": self.find_chains_touching_vertex(
                patch_id,
                chain.end_vert_index,
                exclude=(loop_index, chain_index),
            ),
        }

    def describe_chain_transition(self, owner_patch_id: int, chain: BoundaryChain) -> str:
        owner_key = self.get_patch_semantic_key(owner_patch_id)
        neighbor_kind = chain.neighbor_kind.value if hasattr(chain.neighbor_kind, "value") else str(chain.neighbor_kind)
        if neighbor_kind == ChainNeighborKind.PATCH.value:
            neighbor_key = self.get_patch_semantic_key(chain.neighbor_patch_id)
            return f"{owner_key} -> {neighbor_key}"
        if neighbor_kind == ChainNeighborKind.SEAM_SELF.value:
            return f"{owner_key} -> {owner_key}"
        return f"{owner_key} -> {neighbor_kind}"

    def traverse_bfs(self, root_id: int) -> list[list[int]]:
        visited = {root_id}
        levels = [[root_id]]
        current = [root_id]
        while current:
            next_level = []
            for patch_id in current:
                for neighbor_id in self.get_neighbors(patch_id):
                    if neighbor_id in visited:
                        continue
                    visited.add(neighbor_id)
                    next_level.append(neighbor_id)
            if next_level:
                levels.append(next_level)
            current = next_level
        return levels

    def find_root(self, patch_ids: Optional[set[int]] = None, strategy: str = "MAX_AREA") -> int:
        candidates = patch_ids or set(self.nodes.keys())
        if not candidates:
            raise ValueError("PatchGraph is empty")
        if strategy == "MIN_AREA":
            return min(candidates, key=lambda patch_id: self.nodes[patch_id].area)
        return max(candidates, key=lambda patch_id: self.nodes[patch_id].area)

    def connected_components(self) -> list[set[int]]:
        components = []
        visited = set()
        for patch_id in self.nodes:
            if patch_id in visited:
                continue
            component = set()
            stack = [patch_id]
            while stack:
                current_id = stack.pop()
                if current_id in visited:
                    continue
                visited.add(current_id)
                component.add(current_id)
                for neighbor_id in self.get_neighbors(current_id):
                    if neighbor_id not in visited:
                        stack.append(neighbor_id)
            components.append(component)
        return components


# ============================================================
# ScaffoldMap — solve IR (persistent result)
# Виртуальная 2D карта размещения chains/corners/patches.
# Может быть кэширован, отредактирован вручную, частично пересчитан.
# ============================================================

@dataclass(frozen=True)
class ScaffoldPointKey:
    """Уникальная ссылка на source point в PatchGraph."""

    patch_id: int
    loop_index: int
    chain_index: int
    source_point_index: int


@dataclass(frozen=True)
class ScaffoldChainPlacement:
    """Размещённый chain с UV координатами."""

    patch_id: int
    loop_index: int
    chain_index: int
    frame_role: FrameRole
    axis_authority_kind: AxisAuthorityKind = AxisAuthorityKind.NONE
    span_authority_kind: SpanAuthorityKind = SpanAuthorityKind.NONE
    station_authority_kind: StationAuthorityKind = StationAuthorityKind.NONE
    parameter_authority_kind: ParameterAuthorityKind = ParameterAuthorityKind.NONE
    source_kind: PlacementSourceKind = PlacementSourceKind.CHAIN
    anchor_count: int = 0
    primary_anchor_kind: PlacementSourceKind = PlacementSourceKind.CHAIN
    points: tuple[tuple[ScaffoldPointKey, Vector], ...] = ()


@dataclass(frozen=True)
class ScaffoldClosureSeamReport:
    """Диагностика non-tree closure seam внутри одного quilt."""

    owner_patch_id: int
    owner_loop_index: int
    owner_chain_index: int
    target_patch_id: int
    target_loop_index: int
    target_chain_index: int
    frame_role: FrameRole = FrameRole.FREE
    owner_anchor_count: int = 0
    target_anchor_count: int = 0
    anchor_mode: ClosureAnchorMode = ClosureAnchorMode.UNKNOWN
    canonical_3d_span: float = 0.0
    owner_uv_span: float = 0.0
    target_uv_span: float = 0.0
    owner_axis_error: float = 0.0
    target_axis_error: float = 0.0
    span_mismatch: float = 0.0
    sampled_shared_vert_count: int = 0
    shared_uv_delta_max: float = 0.0
    shared_uv_delta_mean: float = 0.0
    axis_phase_offset_max: float = 0.0
    axis_phase_offset_mean: float = 0.0
    cross_axis_offset_max: float = 0.0
    cross_axis_offset_mean: float = 0.0
    tree_patch_distance: int = 0
    free_bridge_count: int = 0
    shared_vert_count: int = 0


@dataclass(frozen=True)
class ScaffoldFrameAlignmentReport:
    """Диагностика согласованности row / column класса внутри quilt."""

    axis_kind: FrameAxisKind = FrameAxisKind.ROW
    semantic_key: str = ""
    frame_role: FrameRole = FrameRole.FREE
    class_coord_a: float = 0.0
    class_coord_b: float = 0.0
    chain_count: int = 0
    total_weight: float = 0.0
    target_cross_uv: float = 0.0
    scatter_max: float = 0.0
    scatter_mean: float = 0.0
    closure_sensitive: bool = False
    member_refs: tuple[ChainRef, ...] = ()


@dataclass(frozen=True)
class ChainGapReport:
    """Derived gap diagnostic between neighboring placed chains in loop order."""

    chain_index: int
    next_chain_index: int
    gap: float = 0.0


class PatchPlacementStatus(str, Enum):
    """Runtime scaffold status for one patch placement."""

    EMPTY = "EMPTY"
    PARTIAL = "PARTIAL"
    COMPLETE = "COMPLETE"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass
class ScaffoldPatchPlacement:
    """Per-patch envelope — результат scaffold placement."""

    # Active runtime envelope identity.
    patch_id: int
    loop_index: int

    # Active runtime provenance.
    # `-1` means there is no valid runtime root chain for this placement
    # (for example EMPTY / UNSUPPORTED paths).
    root_chain_index: int = -1

    # Active runtime envelope payload.
    corner_positions: dict[int, Vector] = field(default_factory=dict)
    chain_placements: list[ScaffoldChainPlacement] = field(default_factory=list)
    bbox_min: Vector = field(default_factory=lambda: Vector((0.0, 0.0)))
    bbox_max: Vector = field(default_factory=lambda: Vector((0.0, 0.0)))

    # Active runtime diagnostics / reporting.
    closure_error: float = 0.0
    closure_valid: bool = True
    notes: tuple[str, ...] = ()
    status: PatchPlacementStatus = PatchPlacementStatus.COMPLETE
    dependency_patches: tuple[int, ...] = ()
    unplaced_chain_indices: tuple[int, ...] = ()
    scaffold_connected_chains: frozenset[int] = field(default_factory=frozenset)

    # Derived runtime gap diagnostics.
    max_chain_gap: float = 0.0
    gap_reports: tuple[ChainGapReport, ...] = ()

@dataclass
class ScaffoldQuiltPlacement:
    """Per-quilt scaffold — коллекция patch placements с порядком сборки."""

    quilt_index: int
    root_patch_id: int
    patches: dict[int, ScaffoldPatchPlacement] = field(default_factory=dict)
    build_order: list[ChainRef] = field(default_factory=list)
    closure_seam_reports: tuple[ScaffoldClosureSeamReport, ...] = ()
    frame_alignment_reports: tuple[ScaffoldFrameAlignmentReport, ...] = ()
    frontier_telemetry: Optional[QuiltFrontierTelemetry] = None
    skeleton_solve_report: Optional["SkeletonSolveReport"] = None


@dataclass
class ScaffoldMap:
    """Корневой контейнер solve результата — коллекция quilts."""

    quilts: list[ScaffoldQuiltPlacement] = field(default_factory=list)
