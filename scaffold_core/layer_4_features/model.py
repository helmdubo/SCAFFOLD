"""
Layer: 4 - Features

Rules:
- Frozen feature model only: candidates, instances, constraints, options.
- Candidates are evidence (G0 DD-15); suppressed instances are retained with
  their reason (DD-20).
- A FeatureConstraint is self-contained (G0_full section 15) and is the only
  channel into Layer 5 solve (DD-18, DD-26).
- No world axes, no H/V, no surface-role vocabulary.
- Bevel records (BevelInstance) are evidence for later user-option filters;
  they emit no constraint and Layer 5 never reads them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from scaffold_core.core.diagnostics import Diagnostic
from scaffold_core.ids import BoundaryLoopId, ChainId, PatchChainId, PatchId


class FeatureKind(str, Enum):
    STRIP = "STRIP"
    BEVEL_STRIP = "BEVEL_STRIP"
    BEVEL_JUNCTION = "BEVEL_JUNCTION"


class FeatureInstanceStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    SUPPRESSED = "SUPPRESSED"


class FeatureSuppressionReason(str, Enum):
    OPTION_OFF = "option off"
    ALREADY_RECTANGLE = "already a rectangle"
    NO_BENT_OPPOSITE_PAIR = "no bent opposite pair"
    BEVEL_STRIP_AND_JUNCTION_FACES = "strip and junction faces in one patch"
    BEVEL_NOT_ISOLATED = "bevel faces not isolated by seams"


class BevelEvidenceSource(str, Enum):
    """What set a bevel record: the Blender Face Strength mark, or the strict structural rule."""

    SOURCE_MARK = "SOURCE_MARK"
    STRUCTURE = "STRUCTURE"


class BevelCornerKind(str, Enum):
    """The corner a bevel strip replaces, from Layer 3 PatchAdjacency.dihedral_kind of its rail seams.

    CONVEX or CONCAVE when every non-coplanar rail seam agrees, MIXED when
    they disagree, UNDEFINED when none is convex or concave. PatchAdjacency
    compares whole-patch (mean) normals, so next to a curved neighbour (a
    tube wall, an arch reveal) the kind can come out MIXED or UNDEFINED
    even though the bevel replaces one plain corner.
    """

    CONVEX = "CONVEX"
    CONCAVE = "CONCAVE"
    MIXED = "MIXED"
    UNDEFINED = "UNDEFINED"


class BevelStripEnd(str, Enum):
    """End A or end B of a bevel strip's chosen ladder reading (Layer 3 end_a / end_b)."""

    A = "A"
    B = "B"


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
class BevelJunctionContact:
    """One bevel strip a junction joins, at end A or end B of the strip's chosen reading.

    A junction never lies across a rail of a strip's chosen reading (by
    mark a rail has no bevel-marked face across; by structure a rail edge
    breaks a junction), so a contact is always on an end. strip_end is None
    only for a strip by mark with no chosen reading (direction unresolved);
    a junction by structure always has a strip_end.
    """

    strip_patch_id: PatchId
    strip_end: BevelStripEnd | None


@dataclass(frozen=True)
class BevelInstance:
    """A patch that is a bevel strip or a bevel junction (or a bevel-marked patch that cannot be one).

    One record type for both kinds: they share id, status, reason and
    source, and a suppressed record names the kind its marks point to
    (BEVEL_STRIP when any face is MEDIUM, else BEVEL_JUNCTION). Strip
    fields are copies from the chosen Layer 3 quad ladder reading
    (reading_index into PatchQuadLadderRelation.readings; None when the
    direction is unresolved or the patch has no ladder relation, and then
    the strip fields stay empty). Junction fields: the accepted bevel strips
    met along the boundary loops in loop order, the other neighbour patches
    and whether a boundary edge lies on the mesh border. No position,
    length, normal or world axis is stored or read.
    """

    id: str
    kind: FeatureKind
    patch_id: PatchId
    status: FeatureInstanceStatus
    source: BevelEvidenceSource
    suppression_reason: FeatureSuppressionReason | None = None
    # bevel strip
    reading_index: int | None = None
    faces_per_column: int | None = None
    column_count: int | None = None
    is_closed: bool | None = None
    rail_a_patch_chain_ids: tuple[PatchChainId, ...] = ()
    rail_b_patch_chain_ids: tuple[PatchChainId, ...] = ()
    end_a_patch_chain_ids: tuple[PatchChainId, ...] = ()
    end_b_patch_chain_ids: tuple[PatchChainId, ...] = ()
    rail_a_neighbour_patch_ids: tuple[PatchId, ...] = ()
    rail_b_neighbour_patch_ids: tuple[PatchId, ...] = ()
    corner_kind: BevelCornerKind = BevelCornerKind.UNDEFINED
    # bevel junction
    joined_strips: tuple[BevelJunctionContact, ...] = ()
    other_neighbour_patch_ids: tuple[PatchId, ...] = ()
    touches_mesh_border: bool = False


@dataclass(frozen=True)
class FeatureSnapshot:
    options: FeatureOptions = FeatureOptions()
    candidates: tuple[FeatureCandidate, ...] = ()
    instances: tuple[FeatureInstance, ...] = ()
    constraints: tuple[FeatureConstraint, ...] = ()
    bevels: tuple[BevelInstance, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()
