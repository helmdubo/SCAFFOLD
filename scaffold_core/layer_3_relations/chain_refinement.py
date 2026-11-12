"""
Layer: 3 - Relations

Rules:
- Build derived ChainDirectionalRun data from Layer 2 segment geometry.
- The chord shortcut of a zigzag Chain is decided per PatchChain use from that
  use's own PatchChainShapeRelation pieces (chain shape Stage B).
- Do not mutate Layer 1 Chain identity.
- Do not derive features, runtime solve data, UV data, API data, UI data, or Blender logic.
"""

from __future__ import annotations

from scaffold_core.core.evidence import Evidence
from scaffold_core.ids import ChainId, PatchChainId
from scaffold_core.layer_1_topology.model import PatchChain, SurfaceModel
from scaffold_core.layer_2_geometry.facts import (
    ChainGeometryFacts,
    ChainSegmentGeometryFacts,
    ChainShapeHint,
    GeometryFactSnapshot,
    Vector3,
)
from scaffold_core.layer_2_geometry.measures import EPSILON, dot, normalize
from scaffold_core.layer_3_relations.model import (
    ChainDirectionalRun,
    PatchChainDirectionalEvidence,
    PatchChainShapeKind,
    PatchChainShapeRelation,
)


DIRECTION_RUN_COS_TOLERANCE = 0.996
# Split runs of a Chain that also keeps its chord run for another use are
# "directional_run:{chain}:split:{index}"; the chord run stays ":0".
SPLIT_BESIDE_CHORD_RUN_ID_PART = "split"
# Per-vertex turn gate for run splitting; identical local curvature must
# yield identical segmentation regardless of total arc span (OQ-11).
RUN_TURN_TOLERANCE = DIRECTION_RUN_COS_TOLERANCE
POLICY_NAME = "g3c0_directional_runs"


def build_chain_directional_runs(
    topology: SurfaceModel,
    geometry: GeometryFactSnapshot,
    patch_chain_shape_relations: tuple[PatchChainShapeRelation, ...],
) -> tuple[ChainDirectionalRun, ...]:
    """Build direction-ready derived runs for topology Chains."""

    shape_by_use = _shape_relations_by_patch_chain(patch_chain_shape_relations)
    uses_by_chain: dict[ChainId, list[PatchChain]] = {}
    for patch_chain in topology.patch_chains.values():
        uses_by_chain.setdefault(patch_chain.chain_id, []).append(patch_chain)

    runs: list[ChainDirectionalRun] = []
    for chain_id in sorted(topology.chains, key=str):
        chain_facts = geometry.chain_facts.get(chain_id)
        if chain_facts is None:
            continue
        runs.extend(_runs_for_chain(chain_id, chain_facts, uses_by_chain.get(chain_id, ()), shape_by_use))
    return tuple(runs)


def build_patch_chain_directional_evidence(
    topology: SurfaceModel,
    directional_runs: tuple[ChainDirectionalRun, ...],
    patch_chain_shape_relations: tuple[PatchChainShapeRelation, ...],
) -> tuple[PatchChainDirectionalEvidence, ...]:
    """Build patch-local directional evidence for final PatchChains."""

    shape_by_use = _shape_relations_by_patch_chain(patch_chain_shape_relations)
    runs_by_chain: dict[ChainId, list[ChainDirectionalRun]] = {}
    for run in directional_runs:
        runs_by_chain.setdefault(run.parent_chain_id, []).append(run)

    directional_evidence_items: list[PatchChainDirectionalEvidence] = []
    for patch_chain in sorted(topology.patch_chains.values(), key=lambda item: str(item.id)):
        chain_runs = tuple(sorted(runs_by_chain.get(patch_chain.chain_id, ()), key=lambda item: item.id))
        chain_runs = _runs_of_use(patch_chain, chain_runs, shape_by_use)
        directional_evidence_items.extend(
            _directional_evidence_from_patch_chain(patch_chain, run_index, run)
            for run_index, run in enumerate(chain_runs)
        )
    return tuple(directional_evidence_items)


def _runs_for_chain(
    chain_id: ChainId,
    chain_facts: ChainGeometryFacts,
    uses: tuple[PatchChain, ...] | list[PatchChain],
    shape_by_use: dict[PatchChainId, tuple[PatchChainShapeRelation, ...]],
) -> tuple[ChainDirectionalRun, ...]:
    segments = tuple(segment for segment in chain_facts.segments if segment.length > EPSILON)
    if not segments:
        return ()
    if len(segments) == 1:
        return (_run_from_segments(chain_id, chain_facts, 0, segments, segments[0].direction),)
    if chain_facts.shape_hint not in (ChainShapeHint.STRAIGHT, ChainShapeHint.SAWTOOTH_STRAIGHT) or _is_monotone_turning(segments):
        # Monotone-turning arcs never take the chord shortcut: a 90-degree
        # arc with a long chord is not straight.
        return _split_directional_runs(chain_id, chain_facts, segments)
    # A straight/zigzag polyline keeps one chord-directed run (the CFTUV
    # sawtooth lesson) only for a use where the whole Chain is one surface
    # line on that use's own side (chain shape Stage B). Every other use gets
    # the split runs. A Chain whose split is a single run is straight on
    # every side and keeps the chord run for all uses.
    chord_run = _run_from_segments(chain_id, chain_facts, 0, segments, chain_facts.chord_direction)
    split_runs = _split_directional_runs(chain_id, chain_facts, segments)
    if len(split_runs) == 1:
        return (chord_run,)
    keeps_chord = tuple(_use_keeps_chord_run(shape_by_use.get(use.id, ()), chord_run) for use in uses)
    if not uses or all(keeps_chord):
        return (chord_run,)
    if not any(keeps_chord):
        return split_runs
    return (chord_run,) + _split_directional_runs(chain_id, chain_facts, segments, SPLIT_BESIDE_CHORD_RUN_ID_PART)


def _shape_relations_by_patch_chain(
    patch_chain_shape_relations: tuple[PatchChainShapeRelation, ...],
) -> dict[PatchChainId, tuple[PatchChainShapeRelation, ...]]:
    pieces: dict[PatchChainId, list[PatchChainShapeRelation]] = {}
    for relation in patch_chain_shape_relations:
        pieces.setdefault(relation.patch_chain_id, []).append(relation)
    return {key: tuple(value) for key, value in pieces.items()}


def _use_keeps_chord_run(
    pieces: tuple[PatchChainShapeRelation, ...],
    chord_run: ChainDirectionalRun,
) -> bool:
    """A use keeps the chord run only where the whole Chain is one surface line on its side."""

    return (
        len(pieces) == 1
        and pieces[0].kind is PatchChainShapeKind.SURFACE_LINE
        and set(chord_run.segment_indices) <= set(pieces[0].segment_indices)
    )


def _runs_of_use(
    patch_chain: PatchChain,
    chain_runs: tuple[ChainDirectionalRun, ...],
    shape_by_use: dict[PatchChainId, tuple[PatchChainShapeRelation, ...]],
) -> tuple[ChainDirectionalRun, ...]:
    """The runs one use references: a Chain with a chord run and split runs serves each use one set."""

    split_runs = tuple(run for run in chain_runs if _is_split_beside_chord_run(run))
    if not split_runs:
        return chain_runs
    chord_runs = tuple(run for run in chain_runs if not _is_split_beside_chord_run(run))
    if _use_keeps_chord_run(shape_by_use.get(patch_chain.id, ()), chord_runs[0]):
        return chord_runs
    return split_runs


def _is_split_beside_chord_run(run: ChainDirectionalRun) -> bool:
    return run.id.startswith(f"directional_run:{run.parent_chain_id}:{SPLIT_BESIDE_CHORD_RUN_ID_PART}:")


def _is_monotone_turning(segments: tuple[ChainSegmentGeometryFacts, ...]) -> bool:
    """Return whether all significant turns bend the same way (an arc)."""

    reference_axis: Vector3 | None = None
    significant_turns = 0
    for previous, current in zip(segments, segments[1:]):
        if dot(previous.direction, current.direction) >= RUN_TURN_TOLERANCE:
            continue
        axis = normalize(_cross(previous.direction, current.direction))
        if axis == (0.0, 0.0, 0.0):
            continue
        significant_turns += 1
        if reference_axis is None:
            reference_axis = axis
        elif dot(reference_axis, axis) < 0.0:
            return False
    return significant_turns >= 1


def _cross(left: Vector3, right: Vector3) -> Vector3:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _split_directional_runs(
    chain_id: ChainId,
    chain_facts: ChainGeometryFacts,
    segments: tuple[ChainSegmentGeometryFacts, ...],
    id_part: str = "",
) -> tuple[ChainDirectionalRun, ...]:
    runs: list[ChainDirectionalRun] = []
    current_segments: list[ChainSegmentGeometryFacts] = [segments[0]]
    run_index = 0

    for segment in segments[1:]:
        previous_direction = current_segments[-1].direction
        if dot(previous_direction, segment.direction) >= DIRECTION_RUN_COS_TOLERANCE:
            current_segments.append(segment)
            continue
        runs.append(_run_from_segments(chain_id, chain_facts, run_index, tuple(current_segments), id_part=id_part))
        run_index += 1
        current_segments = [segment]

    runs.append(_run_from_segments(chain_id, chain_facts, run_index, tuple(current_segments), id_part=id_part))
    return tuple(runs)


def _run_from_segments(
    chain_id: ChainId,
    chain_facts: ChainGeometryFacts,
    run_index: int,
    segments: tuple[ChainSegmentGeometryFacts, ...],
    direction: Vector3 | None = None,
    id_part: str = "",
) -> ChainDirectionalRun:
    run_direction = direction if direction is not None else _aggregate_direction(segments)
    run_key = f"{id_part}:{run_index}" if id_part else str(run_index)
    return ChainDirectionalRun(
        id=f"directional_run:{chain_id}:{run_key}",
        parent_chain_id=chain_id,
        source_edge_ids=tuple(segment.source_edge_id for segment in segments),
        segment_indices=tuple(segment.segment_index for segment in segments),
        start_source_vertex_id=segments[0].start_source_vertex_id,
        end_source_vertex_id=segments[-1].end_source_vertex_id,
        length=sum(segment.length for segment in segments),
        direction=run_direction,
        is_closed=chain_facts.chord_length <= EPSILON,
        confidence=1.0,
        evidence=(_evidence(chain_facts, segments),),
    )


def _aggregate_direction(segments: tuple[ChainSegmentGeometryFacts, ...]) -> Vector3:
    vector = (0.0, 0.0, 0.0)
    for segment in segments:
        vector = (
            vector[0] + segment.vector[0],
            vector[1] + segment.vector[1],
            vector[2] + segment.vector[2],
        )
    return normalize(vector)


def _directional_evidence_from_patch_chain(
    patch_chain: PatchChain,
    run_index: int,
    run: ChainDirectionalRun,
) -> PatchChainDirectionalEvidence:
    if patch_chain.orientation_sign == -1:
        direction = (-run.direction[0], -run.direction[1], -run.direction[2])
        start_source_vertex_id = run.end_source_vertex_id
        end_source_vertex_id = run.start_source_vertex_id
    else:
        direction = run.direction
        start_source_vertex_id = run.start_source_vertex_id
        end_source_vertex_id = run.end_source_vertex_id

    return PatchChainDirectionalEvidence(
        id=f"patch_chain_directional_evidence:{patch_chain.id}:{run_index}",
        directional_run_id=run.id,
        parent_chain_id=run.parent_chain_id,
        patch_chain_id=patch_chain.id,
        patch_id=patch_chain.patch_id,
        loop_id=patch_chain.loop_id,
        position_in_loop=patch_chain.position_in_loop,
        orientation_sign=patch_chain.orientation_sign,
        source_edge_ids=run.source_edge_ids,
        segment_indices=run.segment_indices,
        start_source_vertex_id=start_source_vertex_id,
        end_source_vertex_id=end_source_vertex_id,
        length=run.length,
        direction=direction,
        confidence=run.confidence,
        evidence=(_directional_evidence_evidence(run),),
    )


def _evidence(
    chain_facts: ChainGeometryFacts,
    segments: tuple[ChainSegmentGeometryFacts, ...],
) -> Evidence:
    return Evidence(
        source="layer_3_relations.chain_refinement",
        summary="directional Chain run derived from segment geometry",
        data={
            "policy": POLICY_NAME,
            "parent_shape_hint": chain_facts.shape_hint.value,
            "segment_count": len(segments),
            "cos_tolerance": DIRECTION_RUN_COS_TOLERANCE,
        },
    )


def _directional_evidence_evidence(run: ChainDirectionalRun) -> Evidence:
    return Evidence(
        source="layer_3_relations.chain_refinement",
        summary="patch-local directional run occurrence derived from PatchChain",
        data={
            "policy": "g3c1_patch_chain_directional_evidences",
            "directional_run_id": run.id,
        },
    )
