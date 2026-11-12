"""
Layer: 3 - Relations

Rules:
- Build evidence-only PatchChainShapeRelation records per PatchChain use and piece.
- Judge a piece on its own patch side only: no world axis, no H/V, no patch types.
- Preserve every run, family, rail, junction, node and Layer 1 identity; nothing reads these records yet.
- Report a disagreement between the face angle sum and the turn law as a diagnostic, never as a silent choice.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pi, radians, sin

from scaffold_core.core.diagnostics import Diagnostic, DiagnosticSeverity
from scaffold_core.core.evidence import Evidence
from scaffold_core.ids import PatchId, SourceVertexId
from scaffold_core.layer_1_topology.model import PatchChain, SurfaceModel
from scaffold_core.layer_2_geometry.facts import (
    ChainGeometryFacts,
    ChainSegmentGeometryFacts,
    GeometryFactSnapshot,
    LocalFaceFanGeometryFacts,
    PatchChainGeometryFacts,
    Vector3,
)
from scaffold_core.layer_2_geometry.measures import (
    COLLINEAR_SINE,
    EPSILON,
    angle_between,
    cross,
    length,
    max_plane_distance,
    normalize,
    plane_tilt,
    polyline_plane_normal,
    subtract,
)
from scaffold_core.layer_3_relations.direction_families import GEODESIC_STRAIGHT_TOLERANCE
from scaffold_core.layer_3_relations.model import PatchChainShapeKind, PatchChainShapeRelation


POLICY_NAME = "patch_chain_shape_v0"
SOURCE = "layer_3_relations.patch_chain_shape"
# Surface turns on real meshes cluster at 0-3, 6-30 and 80-100 degrees. 42
# sits between a regular 9-gon (40) and an 8-gon (45): an 8-gon is cornered,
# a 9-gon and finer is a curve.
SURFACE_CORNER_MIN_TURN = radians(42.0)
LAW_ERROR_MAX = radians(5.0)
PLANAR_RELATIVE_DEVIATION = 0.01
LAW_MISMATCH_CODE = "PATCH_CHAIN_SHAPE_LAW_MISMATCH"
UNRESOLVED_OCCURRENCE_CODE = "PATCH_CHAIN_SHAPE_OCCURRENCE_UNRESOLVED"


@dataclass(frozen=True)
class _VertexTurn:
    """Surface turn at one interior chain vertex on one PatchChain side."""

    source_vertex_id: SourceVertexId
    surface_turn: float | None
    law_error: float | None


def build_patch_chain_shape_relations(
    topology: SurfaceModel,
    geometry: GeometryFactSnapshot,
) -> tuple[tuple[PatchChainShapeRelation, ...], tuple[Diagnostic, ...]]:
    """Build shape evidence for every PatchChain use, cut at surface corners."""

    fans_by_patch_source_vertex = _fans_by_patch_source_vertex(geometry)
    relations: list[PatchChainShapeRelation] = []
    diagnostics: list[Diagnostic] = []
    for patch_chain in sorted(topology.patch_chains.values(), key=lambda item: str(item.id)):
        chain_fact = geometry.chain_facts.get(patch_chain.chain_id)
        if chain_fact is None or not chain_fact.segments:
            continue
        side = geometry.patch_chain_facts.get(patch_chain.id)
        start_vertex = topology.vertices.get(patch_chain.start_vertex_id) if patch_chain.start_vertex_id else None
        records, use_diagnostics = _patch_chain_shape(
            patch_chain,
            chain_fact,
            side,
            fans_by_patch_source_vertex,
            start_vertex.source_vertex_ids if start_vertex is not None else (),
        )
        relations.extend(records)
        diagnostics.extend(use_diagnostics)
    return tuple(relations), tuple(diagnostics)


def _fans_by_patch_source_vertex(
    geometry: GeometryFactSnapshot,
) -> dict[tuple[PatchId, SourceVertexId], tuple[LocalFaceFanGeometryFacts, ...]]:
    fans: dict[tuple[PatchId, SourceVertexId], list[LocalFaceFanGeometryFacts]] = {}
    for fan in geometry.local_face_fan_facts.values():
        fans.setdefault((fan.patch_id, fan.source_vertex_id), []).append(fan)
    return {key: tuple(sorted(values, key=lambda item: item.id)) for key, values in fans.items()}


def _patch_chain_shape(
    patch_chain: PatchChain,
    chain_fact: ChainGeometryFacts,
    side: PatchChainGeometryFacts | None,
    fans_by_patch_source_vertex,
    use_start_source_vertex_ids: tuple[SourceVertexId, ...] = (),
) -> tuple[list[PatchChainShapeRelation], list[Diagnostic]]:
    face_ids = side.segment_side_face_ids if side is not None else ()
    normals = side.segment_side_normals if side is not None else ()
    ordered = sorted(
        (
            (segment, _item(face_ids, position), _item(normals, position))
            for position, segment in enumerate(chain_fact.segments)
        ),
        key=lambda item: item[0].segment_index,
    )
    ordered = _rotated_to_use_start(ordered, use_start_source_vertex_ids)
    segments = tuple(item[0] for item in ordered)
    side_face_ids = tuple(item[1] for item in ordered)
    side_normals = tuple(item[2] for item in ordered)

    # Interior vertex k sits between segments k-1 and k. A closed chain is
    # rotated to start at this use's own start vertex, so that vertex is a piece
    # end and the Chain's closing vertex is judged like any interior vertex.
    turns: list[_VertexTurn] = []
    for index in range(1, len(segments)):
        fan = _side_fan(
            fans_by_patch_source_vertex.get((patch_chain.patch_id, segments[index].start_source_vertex_id), ()),
            _item(side_face_ids, index - 1),
            _item(side_face_ids, index),
        )
        turns.append(_vertex_turn(segments[index - 1], segments[index], fan))

    pieces: list[tuple[int, int]] = []
    piece_start = 0
    for index, turn in enumerate(turns, start=1):
        if turn.surface_turn is not None and abs(turn.surface_turn) >= SURFACE_CORNER_MIN_TURN:
            pieces.append((piece_start, index - 1))
            piece_start = index
    pieces.append((piece_start, len(segments) - 1))

    records: list[PatchChainShapeRelation] = []
    diagnostics: list[Diagnostic] = []
    for piece_index, (first, last) in enumerate(pieces):
        interior = tuple(turns[index - 1] for index in range(first + 1, last + 1))
        record = _piece_record(
            patch_chain,
            piece_index,
            segments[first:last + 1],
            tuple(side_normals[first:last + 1]),
            interior,
        )
        records.append(record)
        diagnostics.extend(_piece_diagnostics(record, interior))
    return records, diagnostics


def _rotated_to_use_start(ordered: list, use_start_source_vertex_ids: tuple[SourceVertexId, ...]) -> list:
    """Rotate a closed chain's segments to start at the use's own start vertex."""

    if len(ordered) < 2 or ordered[0][0].start_source_vertex_id != ordered[-1][0].end_source_vertex_id:
        return ordered
    for position, item in enumerate(ordered):
        if item[0].start_source_vertex_id in use_start_source_vertex_ids:
            return ordered[position:] + ordered[:position]
    return ordered


def _item(values: tuple, index: int):
    return values[index] if index < len(values) else None


def _side_fan(
    fans: tuple[LocalFaceFanGeometryFacts, ...],
    previous_side_face_id,
    next_side_face_id,
) -> LocalFaceFanGeometryFacts | None:
    """The face fan at this vertex occurrence that holds the side faces of both chain edges."""

    if len(fans) == 1:
        return fans[0]
    if previous_side_face_id is None or next_side_face_id is None:
        return None
    holding = tuple(
        fan
        for fan in fans
        if previous_side_face_id in fan.source_face_ids and next_side_face_id in fan.source_face_ids
    )
    return holding[0] if len(holding) == 1 else None


def _vertex_turn(
    previous: ChainSegmentGeometryFacts,
    following: ChainSegmentGeometryFacts,
    fan: LocalFaceFanGeometryFacts | None,
) -> _VertexTurn:
    source_vertex_id = following.start_source_vertex_id
    if fan is None:
        return _VertexTurn(source_vertex_id, None, None)
    surface_turn = fan.interior_angle_sum - pi
    return _VertexTurn(source_vertex_id, surface_turn, _law_error(previous, following, fan, surface_turn))


def _law_error(
    previous: ChainSegmentGeometryFacts,
    following: ChainSegmentGeometryFacts,
    fan: LocalFaceFanGeometryFacts,
    surface_turn: float,
) -> float | None:
    """|3D turn x sin(local tilt) - |surface turn||, or None without a local plane."""

    normal = cross(previous.vector, following.vector)
    if length(normal) <= COLLINEAR_SINE * previous.length * following.length:
        return None
    local_tilt = plane_tilt(normalize(normal), fan.normal)
    if local_tilt is None:
        return None
    predicted = angle_between(previous.vector, following.vector) * sin(local_tilt)
    return abs(predicted - abs(surface_turn))


def _piece_record(
    patch_chain: PatchChain,
    piece_index: int,
    segments: tuple[ChainSegmentGeometryFacts, ...],
    side_normals: tuple[Vector3 | None, ...],
    interior: tuple[_VertexTurn, ...],
) -> PatchChainShapeRelation:
    piece_length = sum(segment.length for segment in segments)
    points = (segments[0].start_position,) + tuple(segment.end_position for segment in segments)
    plane_normal = polyline_plane_normal(points) if len(points) >= 3 else None
    is_planar = plane_normal is None or (
        max_plane_distance(_distinct_closed_points(points), plane_normal)
        <= PLANAR_RELATIVE_DEVIATION * piece_length
    )
    tilts = (
        tuple(
            tilt
            for normal in side_normals
            if normal is not None
            for tilt in (plane_tilt(plane_normal, normal),)
            if tilt is not None
        )
        if plane_normal is not None
        else ()
    )
    resolved_turns = tuple(turn.surface_turn for turn in interior if turn.surface_turn is not None)
    law_errors = tuple(turn.law_error for turn in interior if turn.law_error is not None)
    law_error_max = max(law_errors, default=0.0)
    occurrence_unresolved = len(resolved_turns) != len(interior)
    law_mismatch = law_error_max > LAW_ERROR_MAX
    if occurrence_unresolved or law_mismatch:
        kind = PatchChainShapeKind.UNRESOLVED
    elif all(abs(turn) <= GEODESIC_STRAIGHT_TOLERANCE for turn in resolved_turns):
        kind = PatchChainShapeKind.SURFACE_LINE
    else:
        kind = PatchChainShapeKind.SURFACE_CURVE
    return PatchChainShapeRelation(
        id=f"patch_chain_shape:{patch_chain.id}:{piece_index}",
        patch_chain_id=patch_chain.id,
        chain_id=patch_chain.chain_id,
        patch_id=patch_chain.patch_id,
        kind=kind,
        segment_indices=tuple(segment.segment_index for segment in segments),
        start_source_vertex_id=segments[0].start_source_vertex_id,
        end_source_vertex_id=segments[-1].end_source_vertex_id,
        length=piece_length,
        surface_turn_max=max((abs(turn) for turn in resolved_turns), default=0.0),
        surface_turning_total=sum(resolved_turns),
        tilt_min=min(tilts) if tilts else None,
        tilt_max=max(tilts) if tilts else None,
        is_planar=is_planar,
        law_error_max=law_error_max,
        confidence=0.0 if kind is PatchChainShapeKind.UNRESOLVED else 1.0,
        evidence=(
            Evidence(
                source=SOURCE,
                summary="per-side shape of one PatchChain piece between surface corners",
                data={
                    "policy": POLICY_NAME,
                    "surface_corner_min_turn": SURFACE_CORNER_MIN_TURN,
                    "surface_line_tolerance": GEODESIC_STRAIGHT_TOLERANCE,
                    "law_error_max_allowed": LAW_ERROR_MAX,
                    "interior_source_vertex_ids": tuple(str(turn.source_vertex_id) for turn in interior),
                    "surface_turns": tuple(turn.surface_turn for turn in interior),
                    "law_errors": tuple(turn.law_error for turn in interior),
                    "occurrence_unresolved": occurrence_unresolved,
                    "law_mismatch": law_mismatch,
                },
            ),
        ),
    )


def _distinct_closed_points(points: tuple[Vector3, ...]) -> tuple[Vector3, ...]:
    # A closed piece repeats its first vertex at the end; count it once.
    if len(points) > 1 and length(subtract(points[-1], points[0])) <= EPSILON:
        return points[:-1]
    return points


def _piece_diagnostics(
    record: PatchChainShapeRelation,
    interior: tuple[_VertexTurn, ...],
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for turn in interior:
        if turn.surface_turn is None:
            diagnostics.append(Diagnostic(
                code=UNRESOLVED_OCCURRENCE_CODE,
                severity=DiagnosticSeverity.DEGRADED,
                message=(
                    f"{record.patch_chain_id}: no single face fan of {record.patch_id} holds the chain "
                    f"edges at {turn.source_vertex_id}; piece shape is UNRESOLVED"
                ),
                source=SOURCE,
                entity_ids=(str(record.patch_chain_id), str(turn.source_vertex_id), record.id),
                evidence={"patch_id": str(record.patch_id)},
            ))
        elif turn.law_error is not None and turn.law_error > LAW_ERROR_MAX:
            diagnostics.append(Diagnostic(
                code=LAW_MISMATCH_CODE,
                severity=DiagnosticSeverity.DEGRADED,
                message=(
                    f"{record.patch_chain_id}: surface turn at {turn.source_vertex_id} disagrees with "
                    f"3D turn x sin(tilt) by {turn.law_error:.4f} rad; piece shape is UNRESOLVED"
                ),
                source=SOURCE,
                entity_ids=(str(record.patch_chain_id), str(turn.source_vertex_id), record.id),
                evidence={
                    "patch_id": str(record.patch_id),
                    "surface_turn": turn.surface_turn,
                    "law_error": turn.law_error,
                    "law_error_max_allowed": LAW_ERROR_MAX,
                },
            ))
    return diagnostics
