from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

try:
    from .model import FrameRole
except ImportError:
    from model import FrameRole


class ChainRoleClass(str, Enum):
    """Structural role assigned by shape-policy interpretation."""

    SIDE = "SIDE"
    CAP = "CAP"
    BORDER = "BORDER"
    FREE = "FREE"


class PatchShapeClass(str, Enum):
    """Patch shape classification emitted by the shape layer."""

    MIX = "MIX"
    BAND = "BAND"
    CYLINDER = "CYLINDER"
    CABLE = "CABLE"


@dataclass(frozen=True)
class LoopShapeInterpretation:
    """Shape-policy view derived from one generic loop signature."""

    loop_index: int
    shape_class: PatchShapeClass = PatchShapeClass.MIX
    chain_roles: tuple[ChainRoleClass, ...] = ()
    effective_frame_roles: tuple[FrameRole, ...] = ()
    side_chain_indices: tuple[int, ...] = ()
    cap_chain_indices: tuple[int, ...] = ()
