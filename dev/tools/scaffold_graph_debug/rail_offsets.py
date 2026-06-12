"""Per PatchChain-use rail offset geometry for ScaffoldGraph debug overlay."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from scaffold_core.layer_2_geometry.measures import dot, length, normalize, subtract


RAIL_OFFSET_FACTOR = 0.035


def self_seam_flip_keys(rails, segment_by_evidence_id, self_seam_chain_ids: set[str]) -> set[tuple[str, str, str]]:
    rows: dict[tuple[str, str], list[Any]] = defaultdict(list)
    for rail in rails:
        for evidence_id in rail.directional_evidence_ids:
            segment = segment_by_evidence_id.get(evidence_id)
            if segment is not None and segment.parent_chain_id in self_seam_chain_ids:
                rows[(segment.parent_chain_id, segment.patch_id)].append(segment)
    flip_keys = set()
    for segments in rows.values():
        for index, segment in enumerate(sorted(segments, key=lambda item: item.patch_chain_id)):
            if index % 2 == 1:
                flip_keys.add((segment.parent_chain_id, segment.patch_id, segment.patch_chain_id))
    return flip_keys


def offset_segment_polyline(
    topology: Any,
    source: Any,
    segment: Any,
    *,
    flip: bool,
    self_seam_chain_ids: set[str],
):
    direction = (
        _inward_offset_direction(topology, source, segment, self_seam_chain_ids)
        if source is not None
        else None
    )
    issue = None
    if direction is None:
        issue = f"unoffset rail segment: ambiguous inward offset for {segment.id}"
        vector = (0.0, 0.0, 0.0)
        magnitude = 0.0
    else:
        if flip:
            direction = tuple(-value for value in direction)
        magnitude = _offset_magnitude(source, segment)
        vector = tuple(value * magnitude for value in direction)
    polyline = tuple(_add(point, vector) for point in segment.polyline)
    return polyline, _offset_record(segment, vector, direction, magnitude, issue)


def _inward_offset_direction(topology: Any, source: Any, segment: Any, self_seam_chain_ids: set[str]):
    patch = topology.patches.get(_id_like(topology.patches, segment.patch_id))
    if patch is None:
        return None
    directions = []
    for source_edge_id in segment.source_edge_ids:
        direction = _source_edge_inward_direction(
            source,
            patch.source_face_ids,
            source_edge_id,
            allow_two_face_seam=segment.parent_chain_id in self_seam_chain_ids,
        )
        if direction is not None:
            directions.append(direction)
    if not directions:
        return None
    total = (
        sum(direction[0] for direction in directions),
        sum(direction[1] for direction in directions),
        sum(direction[2] for direction in directions),
    )
    return normalize(total) if length(total) > 0.0 else None


def _source_edge_inward_direction(
    source: Any,
    source_face_ids: tuple[Any, ...],
    source_edge_id: str,
    *,
    allow_two_face_seam: bool,
):
    edge = _source_edge(source, source_edge_id)
    if edge is None:
        return None
    points = tuple(_source_position(source, vertex_id) for vertex_id in edge.vertex_ids)
    if len(points) != 2 or points[0] is None or points[1] is None:
        return None
    edge_direction = subtract(points[1], points[0])
    if length(edge_direction) == 0.0:
        return None
    midpoint = _midpoint(points[0], points[1])
    candidates = []
    for source_face_id in source_face_ids:
        face = source.faces.get(source_face_id)
        if face is None or not any(str(edge_id) == source_edge_id for edge_id in face.edge_ids):
            continue
        centroid = _face_centroid(source, face.vertex_ids)
        if centroid is None:
            continue
        projected = _reject(subtract(centroid, midpoint), normalize(edge_direction))
        if length(projected) > 0.0:
            candidates.append(normalize(projected))
    if len(candidates) == 2 and allow_two_face_seam:
        return candidates[0]
    if len(candidates) != 1:
        return None
    return candidates[0]


def _offset_magnitude(source: Any, segment: Any) -> float:
    lengths = []
    for source_edge_id in segment.source_edge_ids:
        edge = _source_edge(source, source_edge_id)
        if edge is None:
            continue
        points = tuple(_source_position(source, vertex_id) for vertex_id in edge.vertex_ids)
        if len(points) == 2 and points[0] is not None and points[1] is not None:
            lengths.append(length(subtract(points[1], points[0])))
    if not lengths:
        lengths = [length(subtract(second, first)) for first, second in zip(segment.polyline, segment.polyline[1:])]
    average_length = sum(lengths) / len(lengths) if lengths else 0.0
    return average_length * RAIL_OFFSET_FACTOR


def _offset_record(segment: Any, vector, direction, magnitude, issue):
    base_midpoint = _polyline_midpoint(segment.polyline)
    offset_midpoint = _add(base_midpoint, vector)
    return {
        "directional_evidence_id": segment.directional_evidence_id,
        "patch_id": segment.patch_id,
        "patch_chain_id": segment.patch_chain_id,
        "parent_chain_id": segment.parent_chain_id,
        "source_edge_ids": list(segment.source_edge_ids),
        "base_midpoint": list(_round_point(base_midpoint)),
        "offset_midpoint": list(_round_point(offset_midpoint)),
        "offset_vector": list(_round_point(vector)),
        "offset_direction": list(_round_point(direction or (0.0, 0.0, 0.0))),
        "offset_magnitude": round(float(magnitude), 6),
        "unoffset": issue is not None,
        "issue": issue,
    }


def _source_edge(source: Any, source_edge_id: str):
    for edge_id, edge in source.edges.items():
        if str(edge_id) == source_edge_id:
            return edge
    return None


def _source_position(source: Any, source_vertex_id: Any):
    vertex = source.vertices.get(source_vertex_id)
    if vertex is None:
        return None
    return tuple(float(value) for value in vertex.position)


def _face_centroid(source: Any, vertex_ids: tuple[Any, ...]):
    points = [_source_position(source, vertex_id) for vertex_id in vertex_ids]
    points = [point for point in points if point is not None]
    if not points:
        return None
    return (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
        sum(point[2] for point in points) / len(points),
    )


def _reject(vector, axis):
    projection = dot(vector, axis)
    return tuple(vector[index] - projection * axis[index] for index in range(3))


def _midpoint(first, second):
    return ((first[0] + second[0]) * 0.5, (first[1] + second[1]) * 0.5, (first[2] + second[2]) * 0.5)


def _polyline_midpoint(polyline):
    if not polyline:
        return (0.0, 0.0, 0.0)
    return _midpoint(polyline[0], polyline[-1]) if len(polyline) > 1 else polyline[0]


def _add(first, second):
    return (first[0] + second[0], first[1] + second[1], first[2] + second[2])


def _round_point(point):
    return (round(float(point[0]), 6), round(float(point[1]), 6), round(float(point[2]), 6))


def _id_like(mapping, text_id: str):
    for item_id in mapping:
        if str(item_id) == text_id:
            return item_id
    return text_id
