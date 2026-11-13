"""
Layer: user filters - model

Rules:
- Frozen filter model only: options, patch classes, seam directives, snapshot.
- The world vertical (FilterOptions.world_up) is a user option of this stage
  and never an input of Layers 1-4; nothing here is written back to them.
- A SeamDirective is the only channel into Layer 5: island assembly reads it
  to split or join one seam; Layer 5 never reads the patch classes or the
  world vertical.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from scaffold_core.core.diagnostics import Diagnostic
from scaffold_core.ids import ChainId, PatchId

RULE_VERTICAL_APART_FROM_HORIZONTAL = "vertical apart from horizontal"
RULE_BEVEL_WITH_ITS_SURFACES = "a bevel lies with its surfaces"


class PatchClass(str, Enum):
    HORIZONTAL = "HORIZONTAL"
    VERTICAL = "VERTICAL"


class PatchClassRule(str, Enum):
    """How a patch got its class."""

    BY_NORMAL = "by its normal"
    BEVEL_STRIP_BY_RAIL_NEIGHBOURS = "bevel strip: by its rail neighbours"
    BEVEL_JUNCTION_BY_STRIPS = "bevel junction: by the strips it joins"


class SeamDirectiveKind(str, Enum):
    SPLIT = "SPLIT"
    JOIN = "JOIN"


@dataclass(frozen=True)
class FilterOptions:
    """User options of the over filter.

    world_up None (the default) means no filter: no class, no directive, and
    every output equals a run without this stage. With a world_up a patch is
    HORIZONTAL when its normal lies within horizontal_angle_degrees of +up or
    -up, else VERTICAL.
    """

    world_up: tuple[float, float, float] | None = None
    horizontal_angle_degrees: float = 45.0


@dataclass(frozen=True)
class PatchClassRecord:
    """The class of one patch and why.

    angle_degrees is the measured angle between the patch's Layer 2 normal
    (PatchGeometryFacts.normal) and the up line (0 = facing up or down);
    None when the normal is degenerate. A bevel patch by mark takes its class
    by rule, and its own measured angle is kept for inspection.
    """

    patch_id: PatchId
    patch_class: PatchClass
    rule: PatchClassRule
    angle_degrees: float | None
    is_bevel: bool = False


@dataclass(frozen=True)
class SeamDirective:
    """What the filter says about one Chain shared by two different patches."""

    chain_id: ChainId
    first_patch_id: PatchId
    second_patch_id: PatchId
    kind: SeamDirectiveKind
    rule: str


@dataclass(frozen=True)
class FilterSnapshot:
    options: FilterOptions = FilterOptions()
    patch_classes: tuple[PatchClassRecord, ...] = ()
    directives: tuple[SeamDirective, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()
