from __future__ import annotations

from dataclasses import dataclass

try:
    from .constants import BAND_CAP_SIMILARITY_MIN
    from .model import FrameRole
    from .shape_types import ChainRoleClass, LoopShapeInterpretation, PatchShapeClass
    from .structural_tokens import LoopSignature
except ImportError:
    from constants import BAND_CAP_SIMILARITY_MIN
    from model import FrameRole
    from shape_types import ChainRoleClass, LoopShapeInterpretation, PatchShapeClass
    from structural_tokens import LoopSignature


@dataclass(frozen=True)
class PatchShapeSemantics:
    shape_class: PatchShapeClass
    loop_interpretations: tuple[LoopShapeInterpretation, ...]


def _pair_length_similarity(len_a: float, len_b: float) -> float:
    max_len = max(len_a, len_b)
    if max_len <= 1e-9:
        return 1.0
    return 1.0 - abs(len_a - len_b) / max_len


def _pair_average_length(signature: LoopSignature, pair: tuple[int, int]) -> float:
    return (
        signature.chain_tokens[pair[0]].length
        + signature.chain_tokens[pair[1]].length
    ) * 0.5


def _default_loop_interpretation(signature: LoopSignature) -> LoopShapeInterpretation:
    chain_roles = tuple(
        ChainRoleClass.BORDER if token.is_border else ChainRoleClass.FREE
        for token in signature.chain_tokens
    )
    effective_roles = tuple(token.frame_role for token in signature.chain_tokens)
    return LoopShapeInterpretation(
        loop_index=signature.loop_index,
        shape_class=PatchShapeClass.MIX,
        chain_roles=chain_roles,
        effective_frame_roles=effective_roles,
    )


def _is_mutual_opposite(signature: LoopSignature, chain_a_index: int, chain_b_index: int) -> bool:
    if chain_a_index < 0 or chain_b_index < 0:
        return False
    if chain_a_index >= len(signature.chain_tokens) or chain_b_index >= len(signature.chain_tokens):
        return False
    token_a = signature.chain_tokens[chain_a_index]
    token_b = signature.chain_tokens[chain_b_index]
    return token_a.opposite_ref == token_b.chain_ref and token_b.opposite_ref == token_a.chain_ref


def _classify_band_loop(signature: LoopSignature) -> LoopShapeInterpretation | None:
    if signature.chain_count != 4 or len(signature.chain_tokens) != 4:
        return None

    pair_a = (0, 2)
    pair_b = (1, 3)
    if not _is_mutual_opposite(signature, *pair_a):
        return None
    if not _is_mutual_opposite(signature, *pair_b):
        return None

    pair_a_both_free = all(
        signature.chain_tokens[index].frame_role == FrameRole.FREE
        for index in pair_a
    )
    pair_b_both_free = all(
        signature.chain_tokens[index].frame_role == FrameRole.FREE
        for index in pair_b
    )

    side_pair: tuple[int, int] | None = None
    cap_pair: tuple[int, int] | None = None
    if pair_a_both_free and not pair_b_both_free:
        side_pair, cap_pair = pair_a, pair_b
    elif pair_b_both_free and not pair_a_both_free:
        side_pair, cap_pair = pair_b, pair_a
    elif pair_a_both_free and pair_b_both_free:
        # Topology first: a SEAM_SELF pair is the seam cut of a closed tube,
        # not a rail. Its two halves form the CAPS (rings), the other pair
        # are the SIDES. Fall back to the length heuristic only when the
        # SEAM_SELF signal is absent or symmetric (open both-FREE case).
        pair_a_all_seam = all(
            signature.chain_tokens[index].is_seam_self for index in pair_a
        )
        pair_b_all_seam = all(
            signature.chain_tokens[index].is_seam_self for index in pair_b
        )
        if pair_a_all_seam and not pair_b_all_seam:
            side_pair, cap_pair = pair_b, pair_a
        elif pair_b_all_seam and not pair_a_all_seam:
            side_pair, cap_pair = pair_a, pair_b
        else:
            avg_a = _pair_average_length(signature, pair_a)
            avg_b = _pair_average_length(signature, pair_b)
            if avg_a >= avg_b:
                side_pair, cap_pair = pair_a, pair_b
            else:
                side_pair, cap_pair = pair_b, pair_a

    if side_pair is None or cap_pair is None:
        return None

    cap_similarity = _pair_length_similarity(
        signature.chain_tokens[cap_pair[0]].length,
        signature.chain_tokens[cap_pair[1]].length,
    )
    if cap_similarity < BAND_CAP_SIMILARITY_MIN:
        return None

    chain_roles = [ChainRoleClass.FREE] * signature.chain_count
    effective_roles = [token.frame_role for token in signature.chain_tokens]
    for chain_index in cap_pair:
        chain_roles[chain_index] = ChainRoleClass.CAP
    for chain_index in side_pair:
        chain_roles[chain_index] = ChainRoleClass.SIDE
        effective_roles[chain_index] = FrameRole.STRAIGHTEN

    return LoopShapeInterpretation(
        loop_index=signature.loop_index,
        shape_class=PatchShapeClass.BAND,
        chain_roles=tuple(chain_roles),
        effective_frame_roles=tuple(effective_roles),
        side_chain_indices=tuple(side_pair),
        cap_chain_indices=tuple(cap_pair),
    )


def classify_loop_shape(signature: LoopSignature) -> LoopShapeInterpretation:
    band_interpretation = _classify_band_loop(signature)
    if band_interpretation is not None:
        return band_interpretation
    return _default_loop_interpretation(signature)


def classify_patch_shape_semantics(
    signatures: tuple[LoopSignature, ...],
    _debug_patch_id: int = -1,
) -> PatchShapeSemantics:
    _ = _debug_patch_id
    if not signatures:
        return PatchShapeSemantics(
            shape_class=PatchShapeClass.MIX,
            loop_interpretations=(),
        )

    loop_interpretations = tuple(classify_loop_shape(signature) for signature in signatures)
    outer_shape_class = loop_interpretations[0].shape_class if loop_interpretations else PatchShapeClass.MIX
    return PatchShapeSemantics(
        shape_class=outer_shape_class,
        loop_interpretations=loop_interpretations,
    )


def classify_patch_shape(
    signatures: list[LoopSignature],
    _debug_patch_id: int = -1,
) -> PatchShapeClass:
    semantics = classify_patch_shape_semantics(tuple(signatures), _debug_patch_id=_debug_patch_id)
    return semantics.shape_class
