"""Per PatchChain-use rail offset geometry for ScaffoldGraph debug overlay."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from scaffold_core.layer_2_geometry.measures import cross, dot, length, normalize, subtract


RAIL_OFFSET_FACTOR = 0.012
RAIL_NORMAL_HOVER_FACTOR = 0.016


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
    inward_direction = (
        _inward_offset_direction(topology, source, segment, self_seam_chain_ids)
        if source is not None
        else None
    )
    normal_direction = _patch_normal_direction(topology, source, segment) if source is not None else None
    issue = None
    if inward_direction is None:
        issue = f"unoffset rail segment: ambiguous inward offset for {segment.id}"
        inward_vector = (0.0, 0.0, 0.0)
        inward_magnitude = 0.0
    else:
        if flip:
            inward_direction = tuple(-value for value in inward_direction)
        inward_magnitude = _local_average_edge_length(source, segment) * RAIL_OFFSET_FACTOR
        inward_vector = tuple(value * inward_magnitude for value in inward_direction)

    hover_magnitude = (
        _local_average_edge_length(source, segment) * RAIL_NORMAL_HOVER_FACTOR
        if normal_direction is not None
        else 0.0
    )
    hover_vector = (
        tuple(value * hover_magnitude for value in normal_direction)
        if normal_direction is not None
        else (0.0, 0.0, 0.0)
    )
    visual_vector = _add(inward_vector, hover_vector)
    polyline = tuple(_add(point, visual_vector) for point in segment.polyline)
    return polyline, _offset_record(
        segment,
        visual_vector,
        inward_vector,
        hover_vector,
        inward_direction,
        normal_direction,
        inward_magnitude,
        hover_magnitude,
        issue,
    )


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


def _patch_normal_direction(topology: Any, source: Any, segment: Any):
    patch = topology.patches.get(_id_like(topology.patches, segment.patch_id))
    if patch is None:
        return None
    normals = []
    for source_edge_id in segment.source_edge_ids:
        normals.extend(_source_edge_patch_normals(source, patch.source_face_ids, source_edge_id))
    if normals:
        total = (
            sum(normal[0] for normal in normals),
            sum(normal[1] for normal in normals),
            sum(normal[2] for normal in normals),
        )
        normal = normalize(total)
        if length(normal) > 0.0:
            return normal

    total = (0.0, 0.0, 0.0)
    for source_face_id in patch.source_face_ids:
        total = _add(total, _face_area_normal(source, source_face_id))
    normal = normalize(total)
    return normal if length(normal) > 0.0 else None


def _source_edge_patch_normals(source: Any, source_face_ids: tuple[Any, ...], source_edge_id: str):
    normals = []
    for source_face_id in source_face_ids:
        face = source.faces.get(source_face_id)
        if face is None or not any(str(edge_id) == source_edge_id for edge_id in face.edge_ids):
            continue
        normal = normalize(_face_area_normal(source, source_face_id))
        if length(normal) > 0.0:
            normals.append(normal)
    return normals


def _face_area_normal(source: Any, source_face_id: Any):
    face = source.faces.get(source_face_id)
    if face is None or len(face.vertex_ids) < 3:
        return (0.0, 0.0, 0.0)
    points = [_source_position(source, vertex_id) for vertex_id in face.vertex_ids]
    points = [point for point in points if point is not None]
    if len(points) < 3:
        return (0.0, 0.0, 0.0)
    origin = points[0]
    total = (0.0, 0.0, 0.0)
    for index in range(1, len(points) - 1):
        total = _add(total, cross(subtract(points[index], origin), subtract(points[index + 1], origin)))
    return total


def _local_average_edge_length(source: Any, segment: Any) -> float:
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
    return sum(lengths) / len(lengths) if lengths else 0.0


def coalesce_polylines(polylines, *, base_polylines=None):
    visual_rows = [tuple(polyline) for polyline in polylines if len(polyline) >= 2]
    if base_polylines is None:
        base_rows = visual_rows
    else:
        base_rows = [tuple(polyline) for polyline in base_polylines if len(polyline) >= 2]
    rows = [
        (base, visual)
        for base, visual in zip(base_rows, visual_rows)
        if len(base) >= 2 and len(visual) >= 2
    ]
    if len(rows) <= 1:
        return tuple(visual for _base, visual in rows)
    endpoint_counts: dict[tuple[float, float, float], int] = defaultdict(int)
    for base, _visual in rows:
        endpoint_counts[_point_key(base[0])] += 1
        endpoint_counts[_point_key(base[-1])] += 1

    output = list(rows)
    changed = True
    while changed:
        changed = False
        for first_index in range(len(output)):
            if changed:
                break
            first = output[first_index]
            for second_index in range(first_index + 1, len(output)):
                second = output[second_index]
                merged = _try_merge_polylines(first, second, endpoint_counts)
                if merged is None:
                    continue
                output[first_index] = merged
                del output[second_index]
                changed = True
                break
    return tuple(visual for _base, visual in sorted(output, key=_polyline_sort_key))


def _try_merge_polylines(first, second, endpoint_counts):
    first_base, first_visual = first
    second_base, second_visual = second
    first_start = _point_key(first_base[0])
    first_end = _point_key(first_base[-1])
    second_start = _point_key(second_base[0])
    second_end = _point_key(second_base[-1])
    if first_end == second_start and endpoint_counts[first_end] <= 2:
        return first_base + second_base[1:], _join_visual_polylines(first_visual, second_visual)
    if first_end == second_end and endpoint_counts[first_end] <= 2:
        return first_base + tuple(reversed(second_base[:-1])), _join_visual_polylines(first_visual, tuple(reversed(second_visual)))
    if first_start == second_end and endpoint_counts[first_start] <= 2:
        return second_base + first_base[1:], _join_visual_polylines(second_visual, first_visual)
    if first_start == second_start and endpoint_counts[first_start] <= 2:
        return tuple(reversed(second_base)) + first_base[1:], _join_visual_polylines(tuple(reversed(second_visual)), first_visual)
    return None


def _join_visual_polylines(first, second):
    shared = _midpoint(first[-1], second[0])
    return first[:-1] + (shared,) + second[1:]


def _polyline_sort_key(polyline):
    base, visual = polyline
    return (
        _point_key(base[0]),
        _point_key(base[-1]),
        len(visual),
    )


def _point_key(point):
    return (
        round(float(point[0]), 6),
        round(float(point[1]), 6),
        round(float(point[2]), 6),
    )


def _offset_record(
    segment: Any,
    visual_vector,
    inward_vector,
    hover_vector,
    inward_direction,
    normal_direction,
    inward_magnitude,
    hover_magnitude,
    issue,
):
    base_midpoint = _polyline_midpoint(segment.polyline)
    offset_midpoint = _add(base_midpoint, visual_vector)
    return {
        "directional_evidence_id": segment.directional_evidence_id,
        "patch_id": segment.patch_id,
        "patch_chain_id": segment.patch_chain_id,
        "parent_chain_id": segment.parent_chain_id,
        "source_edge_ids": list(segment.source_edge_ids),
        "base_midpoint": list(_round_point(base_midpoint)),
        "offset_midpoint": list(_round_point(offset_midpoint)),
        "offset_vector": list(_round_point(visual_vector)),
        "inward_offset_vector": list(_round_point(inward_vector)),
        "normal_hover_vector": list(_round_point(hover_vector)),
        "offset_direction": list(_round_point(inward_direction or (0.0, 0.0, 0.0))),
        "normal_hover_direction": list(_round_point(normal_direction or (0.0, 0.0, 0.0))),
        "offset_magnitude": round(float(inward_magnitude), 6),
        "normal_hover_magnitude": round(float(hover_magnitude), 6),
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
