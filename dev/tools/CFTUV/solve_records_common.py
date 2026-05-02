from __future__ import annotations

from .constants import (
    FRONTIER_MINIMUM_SCORE,
    FRONTIER_PROPAGATE_THRESHOLD,
    FRONTIER_WEAK_THRESHOLD,
)
from .model import PatchEdgeKey


EDGE_PROPAGATE_MIN = FRONTIER_PROPAGATE_THRESHOLD
EDGE_WEAK_MIN = FRONTIER_WEAK_THRESHOLD
SCAFFOLD_CLOSURE_EPSILON = 1e-4
FRAME_ROW_GROUP_TOLERANCE = 1e-3
FRAME_COLUMN_GROUP_TOLERANCE = 1e-3
CHAIN_FRONTIER_THRESHOLD = FRONTIER_MINIMUM_SCORE


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _patch_pair_key(patch_a_id: int, patch_b_id: int) -> PatchEdgeKey:
    return (min(patch_a_id, patch_b_id), max(patch_a_id, patch_b_id))


__all__ = [
    "EDGE_PROPAGATE_MIN",
    "EDGE_WEAK_MIN",
    "SCAFFOLD_CLOSURE_EPSILON",
    "FRAME_ROW_GROUP_TOLERANCE",
    "FRAME_COLUMN_GROUP_TOLERANCE",
    "CHAIN_FRONTIER_THRESHOLD",
    "_clamp01",
    "_patch_pair_key",
]
