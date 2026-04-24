"""
Layer: 3 - Relations

Rules:
- Frozen derived relation dataclasses only.
- No topology or geometry mutation.
- No feature, runtime, solve, UV, API, UI, or Blender logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from scaffold_core.core.diagnostics import Diagnostic
from scaffold_core.ids import ChainId, ChainUseId, PatchId


class DihedralKind(str, Enum):
    """Coarse signed dihedral classification for adjacent Patches."""

    UNKNOWN = "UNKNOWN"
    COPLANAR = "COPLANAR"
    CONVEX = "CONVEX"
    CONCAVE = "CONCAVE"


@dataclass(frozen=True)
class PatchAdjacency:
    id: str
    first_patch_id: PatchId
    second_patch_id: PatchId
    chain_id: ChainId
    first_chain_use_id: ChainUseId
    second_chain_use_id: ChainUseId
    shared_length: float
    signed_angle_radians: float
    dihedral_kind: DihedralKind


@dataclass(frozen=True)
class RelationSnapshot:
    patch_adjacencies: Mapping[str, PatchAdjacency] = field(default_factory=dict)
    diagnostics: tuple[Diagnostic, ...] = ()
