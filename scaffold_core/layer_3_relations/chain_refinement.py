"""
Layer: 3 - Relations

Rules:
- Build derived ChainDirectionalRun data from Layer 2 segment geometry.
- Do not mutate Layer 1 Chain identity.
- Do not derive features, runtime solve data, UV data, API data, UI data, or Blender logic.
"""

from __future__ import annotations

from scaffold_core.core.evidence import Evidence
from scaffold_core.ids import ChainId
from scaffold_core.layer_1_topology.model import ChainUse, SurfaceModel
from scaffold_core.layer_2_geometry.facts import (
    ChainGeometryFacts,
    ChainSegmentGeometryFacts,
    ChainShapeHint,
    GeometryFactSnapshot,
    Vector3,
)
from scaffold_core.layer_2_geometry.measures import EPSILON, dot, normalize
from scaffold_core.layer_3_relations.model import ChainDirectionalRun, ChainDirectionalRunUse


DIRECTION_RUN_COS_TOLERANCE = 0.996
POLICY_NAME = "g3c0_directional_runs"


def build_chain_directional_runs(
    topology: SurfaceModel,
    geometry: GeometryFactSnapshot,
) -> tuple[ChainDirectionalRun, ...]:
    """Build direction-ready derived runs for topology Chains."""

    runs: list[ChainDirectionalRun] = []
    for chain_id in sorted(topology.chains, key=str):
        chain_facts = geometry.chain_facts.get(chain_id)
        if chain_facts is None:
            continue
        runs.extend(_runs_for_chain(chain_id, chain_facts))
    return tuple(runs)


def build_chain_directional_run_uses(
    topology: SurfaceModel,
    directional_runs: tuple[ChainDirectionalRun, ...],
) -> tuple[ChainDirectionalRunUse, ...]:
    """Build patch-local directional evidence for final PatchChains."""

    runs_by_chain: dict[ChainId, list[ChainDirectionalRun]] = {}
    for run in directional_runs:
        runs_by_chain.setdefault(run.parent_chain_id, []).append(run)

    run_uses: list[ChainDirectionalRunUse] = []
    for chain_use in sorted(topology.chain_uses.values(), key=lambda item: str(item.id)):
        chain_runs = tuple(sorted(runs_by_chain.get(chain_use.chain_id, ()), key=lambda item: item.id))
        run_uses.extend(
            _run_use_from_chain_use(chain_use, run_index, run)
            for run_index, run in enumerate(chain_runs)
        )
    return tuple(run_uses)


def _runs_for_chain(
    chain_id: ChainId,
    chain_facts: ChainGeometryFacts,
) -> tuple[ChainDirectionalRun, ...]:
    segments = tuple(segment for segment in chain_facts.segments if segment.length > EPSILON)
    if not segments:
        return ()
    if len(segments) == 1:
        return (_run_from_segments(chain_id, chain_facts, 0, segments, segments[0].direction),)
    if chain_facts.shape_hint in (ChainShapeHint.STRAIGHT, ChainShapeHint.SAWTOOTH_STRAIGHT):
        return (_run_from_segments(chain_id, chain_facts, 0, segments, chain_facts.chord_direction),)
    return _split_directional_runs(chain_id, chain_facts, segments)


def _split_directional_runs(
    chain_id: ChainId,
    chain_facts: ChainGeometryFacts,
    segments: tuple[ChainSegmentGeometryFacts, ...],
) -> tuple[ChainDirectionalRun, ...]:
    runs: list[ChainDirectionalRun] = []
    current_segments: list[ChainSegmentGeometryFacts] = [segments[0]]
    run_index = 0

    for segment in segments[1:]:
        previous_direction = current_segments[-1].direction
        if dot(previous_direction, segment.direction) >= DIRECTION_RUN_COS_TOLERANCE:
            current_segments.append(segment)
            continue
        runs.append(_run_from_segments(chain_id, chain_facts, run_index, tuple(current_segments)))
        run_index += 1
        current_segments = [segment]

    runs.append(_run_from_segments(chain_id, chain_facts, run_index, tuple(current_segments)))
    return tuple(runs)


def _run_from_segments(
    chain_id: ChainId,
    chain_facts: ChainGeometryFacts,
    run_index: int,
    segments: tuple[ChainSegmentGeometryFacts, ...],
    direction: Vector3 | None = None,
) -> ChainDirectionalRun:
    run_direction = direction if direction is not None else _aggregate_direction(segments)
    return ChainDirectionalRun(
        id=f"directional_run:{chain_id}:{run_index}",
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


def _run_use_from_chain_use(
    chain_use: ChainUse,
    run_index: int,
    run: ChainDirectionalRun,
) -> ChainDirectionalRunUse:
    if chain_use.orientation_sign == -1:
        direction = (-run.direction[0], -run.direction[1], -run.direction[2])
        start_source_vertex_id = run.end_source_vertex_id
        end_source_vertex_id = run.start_source_vertex_id
    else:
        direction = run.direction
        start_source_vertex_id = run.start_source_vertex_id
        end_source_vertex_id = run.end_source_vertex_id

    return ChainDirectionalRunUse(
        id=f"directional_run_use:{chain_use.id}:{run_index}",
        directional_run_id=run.id,
        parent_chain_id=run.parent_chain_id,
        chain_use_id=chain_use.id,
        patch_id=chain_use.patch_id,
        loop_id=chain_use.loop_id,
        position_in_loop=chain_use.position_in_loop,
        orientation_sign=chain_use.orientation_sign,
        source_edge_ids=run.source_edge_ids,
        segment_indices=run.segment_indices,
        start_source_vertex_id=start_source_vertex_id,
        end_source_vertex_id=end_source_vertex_id,
        length=run.length,
        direction=direction,
        confidence=run.confidence,
        evidence=(_run_use_evidence(run),),
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


def _run_use_evidence(run: ChainDirectionalRun) -> Evidence:
    return Evidence(
        source="layer_3_relations.chain_refinement",
        summary="patch-local directional run occurrence derived from ChainUse",
        data={
            "policy": "g3c1_directional_run_uses",
            "directional_run_id": run.id,
        },
    )
