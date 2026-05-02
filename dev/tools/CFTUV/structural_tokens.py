from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

try:
    from .model import (
        BoundaryChain,
        BoundaryLoop,
        ChainNeighborKind,
        ChainRef,
        FrameRole,
        PatchNode,
    )
except ImportError:
    from model import (
        BoundaryChain,
        BoundaryLoop,
        ChainNeighborKind,
        ChainRef,
        FrameRole,
        PatchNode,
    )


@dataclass(frozen=True)
class ChainToken:
    """Thin structural view of one boundary chain.

    This module holds generic structural fingerprints only. Shape-policy
    interpretation belongs to ``shape_classify.py``.
    """

    chain_ref: ChainRef
    frame_role: FrameRole
    length: float
    neighbor_patch_id: Optional[int]
    is_border: bool
    is_seam_self: bool
    opposite_ref: Optional[ChainRef]


@dataclass(frozen=True)
class CornerToken:
    """Thin structural view of one boundary corner."""

    vert_index: int
    turn_angle_deg: float
    prev_chain_ref: ChainRef
    next_chain_ref: ChainRef


@dataclass(frozen=True)
class LoopSignature:
    """Ordered structural view of one boundary loop."""

    patch_id: int
    loop_index: int
    chain_tokens: tuple[ChainToken, ...]
    corner_tokens: tuple[CornerToken, ...]
    chain_count: int
    has_opposite_pairs: bool


def _compute_chain_arc_length(chain: BoundaryChain) -> float:
    verts = chain.vert_cos
    if len(verts) < 2:
        return 0.0
    total = 0.0
    for index in range(len(verts) - 1):
        total += (verts[index + 1] - verts[index]).length
    return total


def _chains_share_corner(chain_a: BoundaryChain, chain_b: BoundaryChain) -> bool:
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


def _find_opposite_ref(
    chain_index: int,
    chain: BoundaryChain,
    loop: BoundaryLoop,
    patch_id: int,
    loop_index: int,
) -> Optional[ChainRef]:
    """Find the best non-adjacent like-oriented chain for non-4-chain loops."""

    role = chain.frame_role
    if role not in {FrameRole.H_FRAME, FrameRole.V_FRAME}:
        return None

    best_ref: Optional[ChainRef] = None
    best_length = -1.0
    for other_index, other_chain in enumerate(loop.chains):
        if other_index == chain_index:
            continue
        if other_chain.frame_role != role:
            continue
        if _chains_share_corner(chain, other_chain):
            continue
        other_length = _compute_chain_arc_length(other_chain)
        if other_length > best_length:
            best_length = other_length
            best_ref = (patch_id, loop_index, other_index)
    return best_ref


def build_loop_signature(
    patch_id: int,
    loop_index: int,
    loop: BoundaryLoop,
    node: PatchNode,
) -> LoopSignature:
    """Construct a frozen generic LoopSignature from a BoundaryLoop."""

    _ = node
    chain_count = len(loop.chains)

    chain_lengths: list[float] = []
    chain_frame_roles: list[FrameRole] = []
    neighbor_patch_ids: list[Optional[int]] = []
    is_borders: list[bool] = []
    is_seam_selfs: list[bool] = []

    for chain in loop.chains:
        chain_lengths.append(_compute_chain_arc_length(chain))
        chain_frame_roles.append(chain.frame_role)
        is_border = not chain.has_patch_neighbor and chain.neighbor_patch_id == -1
        is_borders.append(is_border)
        is_seam_selfs.append(chain.neighbor_kind == ChainNeighborKind.SEAM_SELF)
        neighbor_patch_ids.append(
            chain.neighbor_patch_id if chain.has_patch_neighbor else None
        )

    opposite_refs: list[Optional[ChainRef]] = [None] * chain_count
    if chain_count == 4:
        pair_a = (0, 2)
        pair_b = (1, 3)
        if not _chains_share_corner(loop.chains[pair_a[0]], loop.chains[pair_a[1]]):
            opposite_refs[pair_a[0]] = (patch_id, loop_index, pair_a[1])
            opposite_refs[pair_a[1]] = (patch_id, loop_index, pair_a[0])
        if not _chains_share_corner(loop.chains[pair_b[0]], loop.chains[pair_b[1]]):
            opposite_refs[pair_b[0]] = (patch_id, loop_index, pair_b[1])
            opposite_refs[pair_b[1]] = (patch_id, loop_index, pair_b[0])
    else:
        for chain_index, chain in enumerate(loop.chains):
            opposite_refs[chain_index] = _find_opposite_ref(
                chain_index,
                chain,
                loop,
                patch_id,
                loop_index,
            )

    chain_tokens = tuple(
        ChainToken(
            chain_ref=(patch_id, loop_index, chain_index),
            frame_role=chain_frame_roles[chain_index],
            length=chain_lengths[chain_index],
            neighbor_patch_id=neighbor_patch_ids[chain_index],
            is_border=is_borders[chain_index],
            is_seam_self=is_seam_selfs[chain_index],
            opposite_ref=opposite_refs[chain_index],
        )
        for chain_index, _chain in enumerate(loop.chains)
    )

    corner_tokens = tuple(
        CornerToken(
            vert_index=corner.vert_index,
            turn_angle_deg=corner.turn_angle_deg,
            prev_chain_ref=(patch_id, loop_index, corner.prev_chain_index),
            next_chain_ref=(patch_id, loop_index, corner.next_chain_index),
        )
        for corner in loop.corners
    )

    return LoopSignature(
        patch_id=patch_id,
        loop_index=loop_index,
        chain_tokens=chain_tokens,
        corner_tokens=corner_tokens,
        chain_count=chain_count,
        has_opposite_pairs=any(opposite_ref is not None for opposite_ref in opposite_refs),
    )
