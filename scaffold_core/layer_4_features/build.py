"""
Layer: 4 - Features

Rules:
- Build the FeatureSnapshot from Layers 1-3 read-only; never write Layer 3
  (G0 DD-25) and never import Layer 5.
- One rule per feature kind, as plain functions: candidate rule, resolver,
  constraint. A second feature kind is a second set of functions.
- Every pattern match is a candidate (DD-15); the resolver accepts or
  suppresses with a reason, and suppressed instances are retained (DD-20).
- Structure only: no world axes, no H/V, no surface-role vocabulary.
- The bevel kinds and the ladder constraint live in bevels.py; this module
  holds the strip feature and assembles the FeatureSnapshot.
"""

from __future__ import annotations

from scaffold_core.layer_0_source.snapshot import SourceMeshSnapshot
from scaffold_core.layer_1_topology.model import SurfaceModel
from scaffold_core.layer_2_geometry.facts import GeometryFactSnapshot
from scaffold_core.layer_3_relations.model import PatchChainShapeKind, RelationSnapshot
from scaffold_core.layer_4_features.bevels import bevel_instances, ladder_constraints
from scaffold_core.layer_4_features.model import (
    FeatureCandidate,
    FeatureConstraint,
    FeatureConstraintKind,
    FeatureInstance,
    FeatureInstanceStatus,
    FeatureKind,
    FeatureOptions,
    FeatureSnapshot,
    FeatureSuppressionReason,
    StripSide,
)

STRIP_SIDE_COUNT = 4
# Opposite sides whose 3D lengths differ by more than this share of the
# longer one need straightening.
STRIP_LENGTH_MISMATCH = 0.01
STRIP_OPPOSITE_PAIRS = ((0, 2), (1, 3))


def build_feature_snapshot(
    topology: SurfaceModel,
    geometry: GeometryFactSnapshot,
    relations: RelationSnapshot,
    options: FeatureOptions = FeatureOptions(),
    source: SourceMeshSnapshot | None = None,
) -> FeatureSnapshot:
    """Run every feature rule, then resolve and constrain its candidates.

    The bevel rule runs always: it emits records. With the option
    straighten_bevel_strips each marked bevel strip with a usable reading
    whose rails are not both straight on its surface emits a STRAIGHT_LADDER
    constraint; a strip candidate on such a patch
    then emits no STRAIGHT_STRIP and is suppressed as laid from its bevel
    ladder. The bevel rule needs the Layer 0 source faces (marks and
    incidence): without source (the default) bevels is empty. Pass 2 always
    passes it.
    """

    candidates = strip_candidates(topology, geometry, relations)
    bevels, bevel_diagnostics = bevel_instances(topology, relations, source)
    ladders, ladder_diagnostics = ladder_constraints(bevels, relations, geometry, options)
    laid_by_ladder = {constraint.patch_id for constraint in ladders}
    instances = tuple(
        _laid_as_bevel_strip(instance) if instance.patch_id in laid_by_ladder else instance
        for instance in (resolve_strip(candidate, options) for candidate in candidates)
    )
    candidate_by_id = {candidate.id: candidate for candidate in candidates}
    constraints = tuple(
        strip_constraint(instance, candidate_by_id[instance.candidate_id])
        for instance in instances
        if instance.status is FeatureInstanceStatus.ACCEPTED
    ) + ladders
    return FeatureSnapshot(
        options=options,
        candidates=candidates,
        instances=instances,
        constraints=constraints,
        bevels=bevels,
        diagnostics=bevel_diagnostics + ladder_diagnostics,
    )


def _laid_as_bevel_strip(instance: FeatureInstance) -> FeatureInstance:
    """A strip the strip rule would accept on a patch its bevel ladder lays: the ladder takes it."""

    if instance.status is not FeatureInstanceStatus.ACCEPTED:
        return instance
    return FeatureInstance(
        id=instance.id,
        candidate_id=instance.candidate_id,
        kind=instance.kind,
        patch_id=instance.patch_id,
        status=FeatureInstanceStatus.SUPPRESSED,
        suppression_reason=FeatureSuppressionReason.LAID_AS_BEVEL_STRIP,
    )


# ---------------------------------------------------------------- STRIP rule


def strip_candidates(
    topology: SurfaceModel,
    geometry: GeometryFactSnapshot,
    relations: RelationSnapshot,
) -> tuple[FeatureCandidate, ...]:
    """Patches with exactly one boundary loop of exactly four PatchChain uses.

    Per use: 3D Chain length, whether the use is exactly one SURFACE_LINE
    piece, and the Chain's chord area vector as the use walks the loop.
    """

    pieces_by_use: dict[str, list] = {}
    for piece in relations.patch_chain_shape_relations:
        pieces_by_use.setdefault(str(piece.patch_chain_id), []).append(piece)
    candidates = []
    for patch_id in sorted(topology.patches, key=str):
        patch = topology.patches[patch_id]
        if len(patch.loop_ids) != 1:
            continue
        loop = topology.loops[patch.loop_ids[0]]
        if len(loop.patch_chain_ids) != STRIP_SIDE_COUNT:
            continue
        uses = sorted(
            (topology.patch_chains[pc_id] for pc_id in loop.patch_chain_ids),
            key=lambda pc: pc.position_in_loop,
        )
        sides = []
        for pc in uses:
            facts = geometry.chain_facts[pc.chain_id]
            pieces = pieces_by_use.get(str(pc.id), ())
            sides.append(
                StripSide(
                    patch_chain_id=pc.id,
                    chain_id=pc.chain_id,
                    position_in_loop=pc.position_in_loop,
                    length=facts.length,
                    is_surface_line=len(pieces) == 1 and pieces[0].kind is PatchChainShapeKind.SURFACE_LINE,
                    chord_area_vector=_use_chord_area_vector(facts, pc),
                )
            )
        candidates.append(
            FeatureCandidate(
                id=f"feature_candidate:strip:{patch_id}",
                kind=FeatureKind.STRIP,
                patch_id=patch_id,
                loop_id=loop.id,
                sides=tuple(sides),
            )
        )
    return tuple(candidates)


def _use_chord_area_vector(facts, pc) -> tuple[float, float, float] | None:
    """The Layer 2 chord area vector of the use's Chain, as the use walks its loop; None when it has none.

    Layer 2 measures it along the Chain's stored vertex run, which it walks
    from the Chain's start vertex; a reversed use walks it backwards, which
    flips the vector.
    """

    if facts.chord_area_vector is None:
        return None
    walk = float(pc.orientation_sign)
    return tuple(walk * component for component in facts.chord_area_vector)


def strip_needs_straightening(candidate: FeatureCandidate) -> bool:
    """Some side is not one surface line, or opposite sides differ in length."""

    sides = candidate.sides
    if any(not side.is_surface_line for side in sides):
        return True
    for first, second in STRIP_OPPOSITE_PAIRS:
        longer = max(sides[first].length, sides[second].length)
        if longer > 0.0 and abs(sides[first].length - sides[second].length) > STRIP_LENGTH_MISMATCH * longer:
            return True
    return False


def strip_long_pairs(candidate: FeatureCandidate) -> tuple[tuple[int, int], ...]:
    """The opposite pair with the larger summed 3D length; both pairs on an exact tie."""

    sides = candidate.sides
    sums = [sides[first].length + sides[second].length for first, second in STRIP_OPPOSITE_PAIRS]
    if sums[0] == sums[1]:
        return STRIP_OPPOSITE_PAIRS
    return (STRIP_OPPOSITE_PAIRS[0],) if sums[0] > sums[1] else (STRIP_OPPOSITE_PAIRS[1],)


def strip_long_sides_curved(candidate: FeatureCandidate) -> bool:
    """Both uses of the long opposite pair are not one surface line (curved, cornered or unresolved).

    A patch that develops without distortion has straight long sides on its
    own surface however it bends in 3D, so it is not a strip.
    """

    sides = candidate.sides
    return any(
        not sides[first].is_surface_line and not sides[second].is_surface_line
        for first, second in strip_long_pairs(candidate)
    )


def strip_is_rail_pair(candidate: FeatureCandidate, pair: tuple[int, int]) -> bool:
    """Both uses curved on the surface and, walked along the loop, bowing opposite ways.

    Each side carries the Layer 2 area vector of its Chain closed by its
    chord, oriented as the use walks the loop. Opposite sides of a loop are
    walked in opposite directions, so two sides that bow the same way in
    space have opposite vectors; mirrored sides, such as the two profiles of
    a flat wall, have the same one. A side whose area is zero within
    rounding (straight, or bows that cancel exactly) has no vector and is no
    rail. There is no floor on the bow and no bound on how alike the two
    sides are: no case on the captures and buildings needs one.
    Limits: a wrong reading is possible only where the bow of a side is
    below its noise. An inflected (S-shaped) side is read by its net bow.
    A cornered side counts as curved (it is not one surface line), so a
    planar band with a right-angle corner inside each long side is still a
    strip and is straightened, as before this grade.
    """

    first, second = (candidate.sides[index] for index in pair)
    if first.is_surface_line or second.is_surface_line:
        return False
    if first.chord_area_vector is None or second.chord_area_vector is None:
        return False
    return sum(a * b for a, b in zip(first.chord_area_vector, second.chord_area_vector)) < 0.0


def strip_rail_pair(candidate: FeatureCandidate) -> int | None:
    """Index into STRIP_OPPOSITE_PAIRS of the pair that holds the rails, or None.

    A single rail pair holds the rails whatever its length; when both are
    rail pairs the longer one does (pair 0 on an exact tie of the summed
    lengths, as Layer 5 has always taken it).
    """

    rail_pairs = [index for index, pair in enumerate(STRIP_OPPOSITE_PAIRS) if strip_is_rail_pair(candidate, pair)]
    if len(rail_pairs) != 2:
        return rail_pairs[0] if rail_pairs else None
    sides = candidate.sides
    sums = [sides[first].length + sides[second].length for first, second in STRIP_OPPOSITE_PAIRS]
    return 1 if sums[1] > sums[0] else 0


def resolve_strip(candidate: FeatureCandidate, options: FeatureOptions) -> FeatureInstance:
    """ACCEPTED only with the option on, long sides curved on the surface and a rail pair.

    The shape is graded first (already a rectangle, then long sides straight
    on the surface, then no rail pair), so "option off" marks exactly the
    candidates the option would accept.
    """

    if not strip_needs_straightening(candidate):
        reason = FeatureSuppressionReason.ALREADY_RECTANGLE
    elif not strip_long_sides_curved(candidate):
        reason = FeatureSuppressionReason.LONG_SIDES_STRAIGHT
    elif strip_rail_pair(candidate) is None:
        reason = FeatureSuppressionReason.NO_RAIL_PAIR
    elif not options.straighten_strips:
        reason = FeatureSuppressionReason.OPTION_OFF
    else:
        reason = None
    return FeatureInstance(
        id=f"feature_instance:strip:{candidate.patch_id}",
        candidate_id=candidate.id,
        kind=FeatureKind.STRIP,
        patch_id=candidate.patch_id,
        status=FeatureInstanceStatus.ACCEPTED if reason is None else FeatureInstanceStatus.SUPPRESSED,
        suppression_reason=reason,
    )


def strip_constraint(instance: FeatureInstance, candidate: FeatureCandidate) -> FeatureConstraint:
    """The rectangle: four uses in loop order, the mean length of each opposite pair, the rails and the free ends.

    An end that is one surface line is laid straight; one that is not is
    free: only its end points are laid, as the rails' ends.
    """

    sides = candidate.sides
    rail_pair = strip_rail_pair(candidate)
    return FeatureConstraint(
        id=f"feature_constraint:straight_strip:{candidate.patch_id}",
        kind=FeatureConstraintKind.STRAIGHT_STRIP,
        instance_id=instance.id,
        patch_id=candidate.patch_id,
        patch_chain_ids=tuple(side.patch_chain_id for side in sides),
        target_lengths=tuple(
            (sides[first].length + sides[second].length) / 2.0 for first, second in STRIP_OPPOSITE_PAIRS
        ),
        rail_pair=rail_pair,
        free_end_patch_chain_ids=tuple(
            sides[index].patch_chain_id
            for index in STRIP_OPPOSITE_PAIRS[1 - rail_pair]
            if not sides[index].is_surface_line
        ),
    )
