from __future__ import annotations

from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Callable, Mapping, Optional

try:
    from .constants import TUBE_SEAM_LENGTH_DOMINANCE_MIN
    from .analysis_records import BandSpineData, RuntimeSpineData, _PatchDerivedTopologySummary
    from .band_spine import (
        build_band_spine_from_groups,
        build_canonical_4chain_band_spine,
        build_canonical_4chain_tube_spine,
    )
    from .model import ChainRef, FrameRole, LoopKind, PatchGraph
    from .shape_classify import PatchShapeSemantics, classify_patch_shape_semantics
    from .shape_types import ChainRoleClass, LoopShapeInterpretation, PatchShapeClass
    from .structural_tokens import LoopSignature, build_loop_signature
except ImportError:
    from constants import TUBE_SEAM_LENGTH_DOMINANCE_MIN
    from analysis_records import BandSpineData, RuntimeSpineData, _PatchDerivedTopologySummary
    from band_spine import (
        build_band_spine_from_groups,
        build_canonical_4chain_band_spine,
        build_canonical_4chain_tube_spine,
    )
    from model import ChainRef, FrameRole, LoopKind, PatchGraph
    from shape_classify import PatchShapeSemantics, classify_patch_shape_semantics
    from shape_types import ChainRoleClass, LoopShapeInterpretation, PatchShapeClass
    from structural_tokens import LoopSignature, build_loop_signature


ShapeSupportHandler = Callable[
    [PatchGraph, _PatchDerivedTopologySummary, "PatchShapeFingerprint"],
    "PatchShapeSupportArtifact",
]


@dataclass(frozen=True)
class PatchShapeFingerprint:
    patch_id: int
    loop_signatures: tuple[LoopSignature, ...]
    loop_interpretations: tuple[LoopShapeInterpretation, ...]
    shape_class: PatchShapeClass


@dataclass(frozen=True)
class PatchShapeSupportResult:
    patch_shape_classes: Mapping[int, PatchShapeClass]
    loop_signatures: Mapping[int, list[LoopSignature]]
    loop_shape_interpretations: Mapping[int, list[LoopShapeInterpretation]]
    straighten_chain_refs: frozenset[ChainRef]
    band_spine_data: Mapping[int, BandSpineData]

    @property
    def runtime_spine_data(self) -> Mapping[int, RuntimeSpineData]:
        return self.band_spine_data


@dataclass(frozen=True)
class PatchShapeSupportArtifact:
    straighten_chain_refs: frozenset[ChainRef] = frozenset()
    band_spine_data: Optional[BandSpineData] = None

    @property
    def runtime_spine_data(self) -> Optional[RuntimeSpineData]:
        return self.band_spine_data


def detect_patch_shape_fingerprint(
    graph: PatchGraph,
    patch_id: int,
) -> PatchShapeFingerprint:
    node = graph.nodes[patch_id]
    loop_signatures = tuple(
        build_loop_signature(patch_id, loop_index, boundary_loop, node)
        for loop_index, boundary_loop in enumerate(node.boundary_loops)
    )
    semantics: PatchShapeSemantics = classify_patch_shape_semantics(
        loop_signatures,
        _debug_patch_id=patch_id,
    )
    return PatchShapeFingerprint(
        patch_id=patch_id,
        loop_signatures=loop_signatures,
        loop_interpretations=semantics.loop_interpretations,
        shape_class=semantics.shape_class,
    )


def classify_patch_shape_fingerprint(fingerprint: PatchShapeFingerprint) -> PatchShapeClass:
    return fingerprint.shape_class


def _resolve_outer_loop_shape(
    graph: PatchGraph,
    patch_id: int,
    fingerprint: PatchShapeFingerprint,
) -> tuple[Optional[LoopSignature], Optional[LoopShapeInterpretation]]:
    node = graph.nodes.get(patch_id)
    if node is None:
        return None, None

    outer_signature = next(
        (
            signature
            for signature in fingerprint.loop_signatures
            if 0 <= signature.loop_index < len(node.boundary_loops)
            and node.boundary_loops[signature.loop_index].kind == LoopKind.OUTER
        ),
        None,
    )
    if outer_signature is None:
        return None, None

    outer_interpretation = next(
        (
            interpretation
            for interpretation in fingerprint.loop_interpretations
            if interpretation.loop_index == outer_signature.loop_index
        ),
        None,
    )
    return outer_signature, outer_interpretation


def _is_mutual_opposite(signature: LoopSignature, chain_a_index: int, chain_b_index: int) -> bool:
    if chain_a_index < 0 or chain_b_index < 0:
        return False
    if chain_a_index >= len(signature.chain_tokens) or chain_b_index >= len(signature.chain_tokens):
        return False
    token_a = signature.chain_tokens[chain_a_index]
    token_b = signature.chain_tokens[chain_b_index]
    return token_a.opposite_ref == token_b.chain_ref and token_b.opposite_ref == token_a.chain_ref


def _detect_canonical_tube_shape(
    graph: PatchGraph,
    patch_id: int,
    fingerprint: PatchShapeFingerprint,
) -> tuple[PatchShapeClass, LoopSignature, tuple[int, int], tuple[tuple[int, ...], tuple[int, ...]]] | None:
    if graph.nodes.get(patch_id) is None:
        return None

    outer_signature, _outer_interpretation = _resolve_outer_loop_shape(
        graph,
        patch_id,
        fingerprint,
    )
    if outer_signature is None:
        return None
    if outer_signature.chain_count != 4 or len(outer_signature.chain_tokens) != 4:
        return None

    pair_a = (0, 2)
    pair_b = (1, 3)
    if not _is_mutual_opposite(outer_signature, *pair_a):
        return None
    if not _is_mutual_opposite(outer_signature, *pair_b):
        return None

    pair_a_all_seam = all(outer_signature.chain_tokens[index].is_seam_self for index in pair_a)
    pair_b_all_seam = all(outer_signature.chain_tokens[index].is_seam_self for index in pair_b)
    if pair_a_all_seam == pair_b_all_seam:
        return None

    seam_pair = pair_a if pair_a_all_seam else pair_b
    ring_pair = pair_b if pair_a_all_seam else pair_a
    seam_avg_length = (
        outer_signature.chain_tokens[seam_pair[0]].length
        + outer_signature.chain_tokens[seam_pair[1]].length
    ) * 0.5
    ring_avg_length = (
        outer_signature.chain_tokens[ring_pair[0]].length
        + outer_signature.chain_tokens[ring_pair[1]].length
    ) * 0.5
    if seam_avg_length <= max(ring_avg_length * TUBE_SEAM_LENGTH_DOMINANCE_MIN, 1e-8):
        return None

    seam_roles = {
        outer_signature.chain_tokens[index].frame_role
        for index in seam_pair
    }
    seam_role = next(iter(seam_roles)) if len(seam_roles) == 1 else None
    shape_class = (
        PatchShapeClass.CYLINDER
        if seam_role in {FrameRole.H_FRAME, FrameRole.V_FRAME}
        else PatchShapeClass.CABLE
    )
    return (
        shape_class,
        outer_signature,
        seam_pair,
        ((ring_pair[0],), (ring_pair[1],)),
    )


def _build_tube_loop_interpretation(
    outer_signature: LoopSignature,
    shape_class: PatchShapeClass,
    side_chain_indices: tuple[int, int],
    cap_path_groups: tuple[tuple[int, ...], tuple[int, ...]],
) -> LoopShapeInterpretation:
    chain_roles = [ChainRoleClass.FREE] * outer_signature.chain_count
    effective_roles = [
        token.frame_role for token in outer_signature.chain_tokens
    ]

    for chain_index in side_chain_indices:
        chain_roles[chain_index] = ChainRoleClass.SIDE
        effective_roles[chain_index] = FrameRole.STRAIGHTEN
    for group in cap_path_groups:
        for chain_index in group:
            chain_roles[chain_index] = ChainRoleClass.CAP

    return LoopShapeInterpretation(
        loop_index=outer_signature.loop_index,
        shape_class=shape_class,
        chain_roles=tuple(chain_roles),
        effective_frame_roles=tuple(effective_roles),
        side_chain_indices=tuple(side_chain_indices),
        cap_chain_indices=tuple(group[0] for group in cap_path_groups if group),
    )


def _default_shape_support(
    graph: PatchGraph,
    patch_summary: _PatchDerivedTopologySummary,
    fingerprint: PatchShapeFingerprint,
) -> PatchShapeSupportArtifact:
    _ = graph, patch_summary, fingerprint
    return PatchShapeSupportArtifact()


def _summary_has_split_band_support(patch_summary: _PatchDerivedTopologySummary) -> bool:
    """Structural summary can express BAND CAP paths that generic 4-chain shape cannot."""

    cap_path_groups = tuple(patch_summary.band_cap_path_groups)
    return (
        len(tuple(patch_summary.band_side_indices)) == 2
        and len(cap_path_groups) == 2
        and any(len(group) > 1 for group in cap_path_groups)
    )


def _summary_implies_band_shape(patch_summary: _PatchDerivedTopologySummary) -> bool:
    """Structural summary may override shape classification only for runtime-confirmed split-cap BAND."""

    return (
        patch_summary.band_confirmed_for_runtime
        and _summary_has_split_band_support(patch_summary)
    )


def _band_shape_support(
    graph: PatchGraph,
    patch_summary: _PatchDerivedTopologySummary,
    fingerprint: PatchShapeFingerprint,
) -> PatchShapeSupportArtifact:
    node = graph.nodes.get(patch_summary.patch_id)
    if node is None or any(boundary_loop.kind == LoopKind.HOLE for boundary_loop in node.boundary_loops):
        return PatchShapeSupportArtifact()

    outer_signature, outer_interpretation = _resolve_outer_loop_shape(
        graph,
        patch_summary.patch_id,
        fingerprint,
    )
    if outer_signature is None:
        return PatchShapeSupportArtifact()

    shape_side_indices = (
        tuple(outer_interpretation.side_chain_indices)
        if outer_interpretation is not None
        else ()
    )
    shape_cap_path_groups = (
        tuple((chain_index,) for chain_index in outer_interpretation.cap_chain_indices)
        if outer_interpretation is not None and len(outer_interpretation.cap_chain_indices) == 2
        else ()
    )
    if shape_side_indices and shape_cap_path_groups:
        side_chain_indices = shape_side_indices
        cap_path_groups = shape_cap_path_groups
    elif _summary_implies_band_shape(patch_summary):
        side_chain_indices = tuple(patch_summary.band_side_indices)
        cap_path_groups = tuple(patch_summary.band_cap_path_groups)
    else:
        return PatchShapeSupportArtifact()
    if len(side_chain_indices) != 2 or len(cap_path_groups) != 2:
        return PatchShapeSupportArtifact()

    straighten_chain_refs = frozenset(
        (patch_summary.patch_id, outer_signature.loop_index, chain_index)
        for chain_index in side_chain_indices
        if 0 <= chain_index < outer_signature.chain_count
    )
    # Fast-path for canonical 4-chain BAND (simple strip between two rails).
    # Only fall back to the general topology-heavy builder for split-cap (>4 chain).
    spine_data = None
    if (
        outer_signature.chain_count == 4
        and len(cap_path_groups) == 2
        and all(len(g) == 1 for g in cap_path_groups)
    ):
        spine_data = build_canonical_4chain_band_spine(
            graph,
            patch_summary.patch_id,
            outer_signature.loop_index,
            side_chain_indices,
            cap_path_groups,
        )
    if spine_data is None:
        spine_data = build_band_spine_from_groups(
            graph,
            patch_summary.patch_id,
            outer_signature.loop_index,
            side_chain_indices,
            cap_path_groups,
        )
    return PatchShapeSupportArtifact(
        straighten_chain_refs=straighten_chain_refs,
        band_spine_data=spine_data,
    )


def _tube_shape_support(
    graph: PatchGraph,
    patch_summary: _PatchDerivedTopologySummary,
    fingerprint: PatchShapeFingerprint,
    *,
    expected_shape_class: PatchShapeClass,
) -> PatchShapeSupportArtifact:
    node = graph.nodes.get(patch_summary.patch_id)
    if node is None or any(boundary_loop.kind == LoopKind.HOLE for boundary_loop in node.boundary_loops):
        return PatchShapeSupportArtifact()

    detected = _detect_canonical_tube_shape(
        graph,
        patch_summary.patch_id,
        fingerprint,
    )
    if detected is None:
        return PatchShapeSupportArtifact()

    shape_class, outer_signature, side_chain_indices, cap_path_groups = detected
    if shape_class != expected_shape_class:
        return PatchShapeSupportArtifact()

    straighten_chain_refs = frozenset(
        (patch_summary.patch_id, outer_signature.loop_index, chain_index)
        for chain_index in side_chain_indices
    )
    spine_data = build_canonical_4chain_tube_spine(
        graph,
        patch_summary.patch_id,
        outer_signature.loop_index,
        side_chain_indices,
        cap_path_groups,
    )
    return PatchShapeSupportArtifact(
        straighten_chain_refs=straighten_chain_refs,
        band_spine_data=spine_data,
    )


def _cylinder_shape_support(
    graph: PatchGraph,
    patch_summary: _PatchDerivedTopologySummary,
    fingerprint: PatchShapeFingerprint,
) -> PatchShapeSupportArtifact:
    return _tube_shape_support(
        graph,
        patch_summary,
        fingerprint,
        expected_shape_class=PatchShapeClass.CYLINDER,
    )


def _cable_shape_support(
    graph: PatchGraph,
    patch_summary: _PatchDerivedTopologySummary,
    fingerprint: PatchShapeFingerprint,
) -> PatchShapeSupportArtifact:
    return _tube_shape_support(
        graph,
        patch_summary,
        fingerprint,
        expected_shape_class=PatchShapeClass.CABLE,
    )


_ACTIVE_SHAPE_SUPPORT_HANDLERS: dict[PatchShapeClass, ShapeSupportHandler] = {
    PatchShapeClass.BAND: _band_shape_support,
    PatchShapeClass.CYLINDER: _cylinder_shape_support,
    PatchShapeClass.CABLE: _cable_shape_support,
    PatchShapeClass.MIX: _default_shape_support,
}


def build_patch_shape_support_artifact(
    graph: PatchGraph,
    patch_summary: _PatchDerivedTopologySummary,
    fingerprint: PatchShapeFingerprint,
) -> PatchShapeSupportArtifact:
    """Dispatch classified shape semantics to runtime-support builders.

    Shape-specific runtime hooks stay local to this layer:
    `CYLINDER` -> `_cylinder_shape_support`
    `CABLE` -> `_cable_shape_support`
    """

    if (
        fingerprint.shape_class not in {PatchShapeClass.CYLINDER, PatchShapeClass.CABLE}
        and _summary_implies_band_shape(patch_summary)
    ):
        return _band_shape_support(graph, patch_summary, fingerprint)

    handler = _ACTIVE_SHAPE_SUPPORT_HANDLERS.get(
        fingerprint.shape_class,
        _default_shape_support,
    )
    return handler(graph, patch_summary, fingerprint)


def build_patch_shape_support(
    graph: PatchGraph,
    patch_summaries_by_id: Mapping[int, _PatchDerivedTopologySummary],
) -> PatchShapeSupportResult:
    """Shape support phases: fingerprint -> classify -> support -> finalize."""

    loop_signatures: dict[int, list[LoopSignature]] = {}
    loop_shape_interpretations: dict[int, list[LoopShapeInterpretation]] = {}
    patch_shape_classes: dict[int, PatchShapeClass] = {}
    straighten_chain_refs: set[ChainRef] = set()
    band_spine_data: dict[int, BandSpineData] = {}

    for patch_id in sorted(graph.nodes.keys()):
        fingerprint = detect_patch_shape_fingerprint(graph, patch_id)
        patch_shape_class = classify_patch_shape_fingerprint(fingerprint)

        patch_summary = patch_summaries_by_id.get(patch_id)
        if patch_summary is None:
            loop_signatures[patch_id] = list(fingerprint.loop_signatures)
            loop_shape_interpretations[patch_id] = list(fingerprint.loop_interpretations)
            patch_shape_classes[patch_id] = patch_shape_class
            continue

        effective_fingerprint = fingerprint
        tube_detection = _detect_canonical_tube_shape(
            graph,
            patch_id,
            fingerprint,
        )
        if tube_detection is not None:
            tube_shape_class, outer_signature, side_chain_indices, cap_path_groups = tube_detection
            patch_shape_class = tube_shape_class
            updated_loop_interpretations = []
            for interpretation in fingerprint.loop_interpretations:
                if interpretation.loop_index != outer_signature.loop_index:
                    updated_loop_interpretations.append(interpretation)
                    continue
                updated_loop_interpretations.append(
                    _build_tube_loop_interpretation(
                        outer_signature,
                        tube_shape_class,
                        side_chain_indices,
                        cap_path_groups,
                    )
                )
            effective_fingerprint = replace(
                fingerprint,
                loop_interpretations=tuple(updated_loop_interpretations),
                shape_class=tube_shape_class,
            )
        elif _summary_implies_band_shape(patch_summary):
            patch_shape_class = PatchShapeClass.BAND
            effective_fingerprint = replace(
                fingerprint,
                shape_class=PatchShapeClass.BAND,
            )

        loop_signatures[patch_id] = list(effective_fingerprint.loop_signatures)
        loop_shape_interpretations[patch_id] = list(effective_fingerprint.loop_interpretations)

        artifact = build_patch_shape_support_artifact(
            graph,
            patch_summary,
            effective_fingerprint,
        )
        patch_shape_classes[patch_id] = patch_shape_class
        straighten_chain_refs.update(artifact.straighten_chain_refs)
        if artifact.band_spine_data is not None:
            band_spine_data[patch_id] = artifact.band_spine_data

    return PatchShapeSupportResult(
        patch_shape_classes=MappingProxyType(dict(patch_shape_classes)),
        loop_signatures=MappingProxyType(dict(loop_signatures)),
        loop_shape_interpretations=MappingProxyType(dict(loop_shape_interpretations)),
        straighten_chain_refs=frozenset(straighten_chain_refs),
        band_spine_data=MappingProxyType(dict(band_spine_data)),
    )


__all__ = [
    "PatchShapeFingerprint",
    "PatchShapeSupportArtifact",
    "PatchShapeSupportResult",
    "detect_patch_shape_fingerprint",
    "classify_patch_shape_fingerprint",
    "build_patch_shape_support_artifact",
    "build_patch_shape_support",
]
