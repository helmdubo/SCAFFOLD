"""
Layer: 4 - Features

Rules:
- Frozen feature model only: candidates, instances, constraints, options.
- Candidates are evidence (G0 DD-15); suppressed instances are retained with
  their reason (DD-20).
- A FeatureConstraint is self-contained (G0_full section 15) and is the only
  channel into Layer 5 solve (DD-18, DD-26).
- No world axes, no H/V, no surface-role vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from scaffold_core.core.diagnostics import Diagnostic
from scaffold_core.ids import BoundaryLoopId, ChainId, PatchChainId, PatchId


class FeatureKind(str, Enum):
    STRIP = "STRIP"


class FeatureInstanceStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    SUPPRESSED = "SUPPRESSED"


class FeatureSuppressionReason(str, Enum):
    OPTION_OFF = "option off"
    ALREADY_RECTANGLE = "already a rectangle"
    NO_BENT_OPPOSITE_PAIR = "no bent opposite pair"


class FeatureConstraintKind(str, Enum):
    STRAIGHT_STRIP = "STRAIGHT_STRIP"


@dataclass(frozen=True)
class FeatureOptions:
    """User-facing feature switches; every feature is off by default."""

    straighten_strips: bool = False


@dataclass(frozen=True)
class StripSide:
    """One PatchChain use of a strip candidate, in loop order."""

    patch_chain_id: PatchChainId
    chain_id: ChainId
    position_in_loop: int
    length: float  # 3D length of the Chain
    is_bent: bool  # Chain length exceeds its chord by > 1%, or the Chain is closed
    is_surface_line: bool  # the use is one SURFACE_LINE piece (Layer 3)


@dataclass(frozen=True)
class FeatureCandidate:
    """A structural pattern match; evidence, not a decision."""

    id: str
    kind: FeatureKind
    patch_id: PatchId
    loop_id: BoundaryLoopId
    sides: tuple[StripSide, ...]


@dataclass(frozen=True)
class FeatureInstance:
    """The resolver's verdict on one candidate."""

    id: str
    candidate_id: str
    kind: FeatureKind
    patch_id: PatchId
    status: FeatureInstanceStatus
    suppression_reason: FeatureSuppressionReason | None = None


@dataclass(frozen=True)
class FeatureConstraint:
    """Self-contained solve requirement of an accepted instance.

    STRAIGHT_STRIP: the patch is laid as a rectangle. patch_chain_ids are the
    four uses in loop order; target_lengths[0] is the length of the opposite
    pair at loop positions 0 and 2, target_lengths[1] that of positions 1 and 3.
    """

    id: str
    kind: FeatureConstraintKind
    instance_id: str
    patch_id: PatchId
    patch_chain_ids: tuple[PatchChainId, ...]
    target_lengths: tuple[float, float]


@dataclass(frozen=True)
class FeatureSnapshot:
    options: FeatureOptions = FeatureOptions()
    candidates: tuple[FeatureCandidate, ...] = ()
    instances: tuple[FeatureInstance, ...] = ()
    constraints: tuple[FeatureConstraint, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()
