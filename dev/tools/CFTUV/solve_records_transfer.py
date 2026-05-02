from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from mathutils import Vector

from .model import BoundaryChain, FrameRole, PlacementSourceKind
from .solve_records_common import (
    FRAME_COLUMN_GROUP_TOLERANCE,
    FRAME_ROW_GROUP_TOLERANCE,
    SCAFFOLD_CLOSURE_EPSILON,
)


RowClassKey = tuple[int]
ColumnClassKey = tuple[int, int]
FrameClassKey = tuple[int, ...]
TransferTargetId = tuple[int, int]
ScaffoldKeyId = tuple[int, int, int, int, PlacementSourceKind]
TargetSampleMap = dict[TransferTargetId, list[Vector]]
PinnedTargetIdSet = set[TransferTargetId]
ScaffoldKeySet = set[ScaffoldKeyId]


def frame_row_class_key(chain: BoundaryChain) -> RowClassKey:
    """Row group key by average Z of 3D vertices."""

    if not chain.vert_cos:
        return (0,)
    avg_z = sum(point.z for point in chain.vert_cos) / float(len(chain.vert_cos))
    return (int(round(avg_z / FRAME_ROW_GROUP_TOLERANCE)),)


def frame_column_class_key(chain: BoundaryChain) -> ColumnClassKey:
    """Column group key by average X,Y of 3D vertices."""

    if not chain.vert_cos:
        return (0, 0)
    avg_x = sum(point.x for point in chain.vert_cos) / float(len(chain.vert_cos))
    avg_y = sum(point.y for point in chain.vert_cos) / float(len(chain.vert_cos))
    return (
        int(round(avg_x / FRAME_COLUMN_GROUP_TOLERANCE)),
        int(round(avg_y / FRAME_COLUMN_GROUP_TOLERANCE)),
    )


@dataclass(frozen=True)
class UvAxisMetrics:
    span: float
    axis_error: float


@dataclass(frozen=True)
class FrameUvComponents:
    axis: float
    cross: float


@dataclass(frozen=True)
class FrameGroupDisplayCoords:
    coord_a: float
    coord_b: float


@dataclass(frozen=True)
class UvBounds:
    bbox_min: Vector
    bbox_max: Vector


@dataclass(frozen=True)
class ScaffoldUvTarget:
    face_index: int
    vert_index: int
    loop_point_index: int


class PatchTransferStatus(str, Enum):
    OK = "ok"
    UNSUPPORTED = "unsupported"
    INVALID_SCAFFOLD = "invalid_scaffold"
    MISSING_PATCH = "missing_patch"


@dataclass(frozen=True)
class PatchTransferTargetsState:
    status: PatchTransferStatus = PatchTransferStatus.OK
    scaffold_points: int = 0
    resolved_scaffold_points: int = 0
    uv_targets_resolved: int = 0
    unresolved_scaffold_points: int = 0
    missing_uv_targets: int = 0
    conflicting_uv_targets: int = 0
    pinned_uv_targets: int = 0
    unpinned_uv_targets: int = 0
    invalid_scaffold_patches: int = 0
    closure_error: float = 0.0
    max_chain_gap: float = 0.0
    chain_gap_count: int = 0
    target_samples: TargetSampleMap = field(default_factory=dict)
    pin_target_ids: PinnedTargetIdSet = field(default_factory=set)
    scaffold_keys: ScaffoldKeySet = field(default_factory=set)
    unresolved_keys: ScaffoldKeySet = field(default_factory=set)
    conformal_patch: bool = False
    pin_map: Optional["PatchPinMap"] = None


@dataclass(frozen=True)
class PatchApplyStats:
    status: PatchTransferStatus = PatchTransferStatus.OK
    scaffold_points: int = 0
    resolved_scaffold_points: int = 0
    uv_targets_resolved: int = 0
    unresolved_scaffold_points: int = 0
    missing_uv_targets: int = 0
    conflicting_uv_targets: int = 0
    pinned_uv_loops: int = 0
    invalid_scaffold_patches: int = 0
    closure_error: float = 0.0
    max_chain_gap: float = 0.0
    chain_gap_count: int = 0

    def accumulate_into(self, bucket: dict[str, int]) -> None:
        bucket["scaffold_points"] += int(self.scaffold_points)
        bucket["resolved_scaffold_points"] += int(self.resolved_scaffold_points)
        bucket["uv_targets_resolved"] += int(self.uv_targets_resolved)
        bucket["unresolved_scaffold_points"] += int(self.unresolved_scaffold_points)
        bucket["missing_uv_targets"] += int(self.missing_uv_targets)
        bucket["conflicting_uv_targets"] += int(self.conflicting_uv_targets)
        bucket["pinned_uv_loops"] += int(self.pinned_uv_loops)
        bucket["invalid_scaffold_patches"] += int(self.invalid_scaffold_patches)


@dataclass(frozen=True)
class PinPolicy:
    """Immutable pin policy configuration. Passed as parameter, not global."""

    pin_connected_hv: bool = True
    pin_free_endpoints_with_hv_anchor: bool = True
    skip_conformal_patches: bool = True
    skip_isolated_hv: bool = True


@dataclass(frozen=True)
class ChainPinDecision:
    """Pin decision for one placed chain."""

    chain_index: int
    frame_role: FrameRole
    pin_all: bool
    pin_endpoints_only: bool
    pin_start: bool
    pin_end: bool
    pin_nothing: bool
    reason: str


@dataclass(frozen=True)
class PatchPinMap:
    """Complete pin map for one patch placement."""

    patch_id: int
    loop_index: int
    conformal_patch: bool
    scaffold_connected_chains: frozenset[int]
    chain_decisions: tuple[ChainPinDecision, ...]

    def is_point_pinned(self, chain_index: int, point_index: int, point_count: int) -> bool:
        for decision in self.chain_decisions:
            if decision.chain_index != chain_index:
                continue
            if decision.pin_all:
                return True
            if decision.pin_nothing:
                return False
            if point_index == 0:
                return decision.pin_start
            if point_count > 0 and point_index == point_count - 1:
                return decision.pin_end
            return False
        return False

    def pinned_chain_indices(self) -> frozenset[int]:
        return frozenset(
            decision.chain_index
            for decision in self.chain_decisions
            if decision.pin_all or decision.pin_endpoints_only
        )


__all__ = [
    "RowClassKey",
    "ColumnClassKey",
    "FrameClassKey",
    "TransferTargetId",
    "ScaffoldKeyId",
    "TargetSampleMap",
    "PinnedTargetIdSet",
    "ScaffoldKeySet",
    "frame_row_class_key",
    "frame_column_class_key",
    "UvAxisMetrics",
    "FrameUvComponents",
    "FrameGroupDisplayCoords",
    "UvBounds",
    "ScaffoldUvTarget",
    "PatchTransferStatus",
    "PatchTransferTargetsState",
    "PatchApplyStats",
    "PinPolicy",
    "ChainPinDecision",
    "PatchPinMap",
    "FRAME_ROW_GROUP_TOLERANCE",
    "FRAME_COLUMN_GROUP_TOLERANCE",
    "SCAFFOLD_CLOSURE_EPSILON",
]
