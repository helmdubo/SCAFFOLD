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
"""

from __future__ import annotations

from scaffold_core.layer_1_topology.model import SurfaceModel
from scaffold_core.layer_2_geometry.facts import GeometryFactSnapshot
from scaffold_core.layer_2_geometry.measures import EPSILON
from scaffold_core.layer_3_relations.model import PatchChainShapeKind, RelationSnapshot
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
# A Chain is bent in 3D when its length exceeds its chord by more than this
# share; a closed Chain (chord ~0) is always bent. A vertex merely off the
# chord line (an arched chain whose length equals its chord) is not bent.
STRIP_BENT_DETOUR = 0.01


def build_feature_snapshot(
    topology: SurfaceModel,
    geometry: GeometryFactSnapshot,
    relations: RelationSnapshot,
    options: FeatureOptions = FeatureOptions(),
) -> FeatureSnapshot:
    """Run every feature rule, then resolve and constrain its candidates."""

    candidates = strip_candidates(topology, geometry, relations)
    instances = tuple(resolve_strip(candidate, options) for candidate in candidates)
    candidate_by_id = {candidate.id: candidate for candidate in candidates}
    constraints = tuple(
        strip_constraint(instance, candidate_by_id[instance.candidate_id])
        for instance in instances
        if instance.status is FeatureInstanceStatus.ACCEPTED
    )
    return FeatureSnapshot(
        options=options,
        candidates=candidates,
        instances=instances,
        constraints=constraints,
    )


# ---------------------------------------------------------------- STRIP rule


def strip_candidates(
    topology: SurfaceModel,
    geometry: GeometryFactSnapshot,
    relations: RelationSnapshot,
) -> tuple[FeatureCandidate, ...]:
    """Patches with exactly one boundary loop of exactly four PatchChain uses.

    Per use: 3D Chain length, whether the Chain is bent (chain_is_bent) and
    whether the use is exactly one SURFACE_LINE piece.
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
                    is_bent=chain_is_bent(facts),
                    is_surface_line=len(pieces) == 1 and pieces[0].kind is PatchChainShapeKind.SURFACE_LINE,
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


def chain_is_bent(facts) -> bool:
    """Bent in 3D: length > chord * (1 + STRIP_BENT_DETOUR), or a closed Chain."""

    if facts.chord_length <= EPSILON:
        return True
    return facts.length > facts.chord_length * (1.0 + STRIP_BENT_DETOUR)


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


def resolve_strip(candidate: FeatureCandidate, options: FeatureOptions) -> FeatureInstance:
    """ACCEPTED only with the option on, a strip that needs straightening and a bent opposite pair."""

    sides = candidate.sides
    if not options.straighten_strips:
        reason = FeatureSuppressionReason.OPTION_OFF
    elif not strip_needs_straightening(candidate):
        reason = FeatureSuppressionReason.ALREADY_RECTANGLE
    elif not any(sides[first].is_bent and sides[second].is_bent for first, second in STRIP_OPPOSITE_PAIRS):
        reason = FeatureSuppressionReason.NO_BENT_OPPOSITE_PAIR
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
    """The rectangle: four uses in loop order and the mean length of each opposite pair."""

    sides = candidate.sides
    return FeatureConstraint(
        id=f"feature_constraint:straight_strip:{candidate.patch_id}",
        kind=FeatureConstraintKind.STRAIGHT_STRIP,
        instance_id=instance.id,
        patch_id=candidate.patch_id,
        patch_chain_ids=tuple(side.patch_chain_id for side in sides),
        target_lengths=tuple(
            (sides[first].length + sides[second].length) / 2.0 for first, second in STRIP_OPPOSITE_PAIRS
        ),
    )
