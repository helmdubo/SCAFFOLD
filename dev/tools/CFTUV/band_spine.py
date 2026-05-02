from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
import math
from types import MappingProxyType
from typing import Optional

from mathutils import Quaternion, Vector

try:
    from .analysis_records import BandSpineData
    from .model import BoundaryChain, ChainNeighborKind, FrameRole, PatchGraph
except ImportError:
    from analysis_records import BandSpineData
    from model import BoundaryChain, ChainNeighborKind, FrameRole, PatchGraph


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _chain_has_corner(chain: BoundaryChain, corner_index: int) -> bool:
    return corner_index >= 0 and corner_index in {chain.start_corner_index, chain.end_corner_index}


def _group_has_corner(
    graph: PatchGraph,
    chain_refs: tuple[tuple[int, int, int], ...],
    corner_index: int,
) -> bool:
    for chain_ref in chain_refs:
        chain = graph.get_chain(*chain_ref)
        if chain is not None and _chain_has_corner(chain, corner_index):
            return True
    return False


def _polyline_cumulative_lengths(points: tuple[Vector, ...]) -> tuple[tuple[float, ...], float]:
    if not points:
        return (), 0.0
    cumulative = [0.0]
    walked = 0.0
    for point_index in range(1, len(points)):
        walked += (points[point_index] - points[point_index - 1]).length
        cumulative.append(walked)
    return tuple(cumulative), walked


def _sample_polyline_at_distance(
    points: tuple[Vector, ...],
    cumulative: tuple[float, ...],
    distance: float,
) -> Vector:
    if not points:
        return Vector((0.0, 0.0, 0.0))
    if len(points) == 1 or not cumulative:
        return points[0].copy()
    if distance <= 0.0:
        return points[0].copy()
    total_length = cumulative[-1]
    if distance >= total_length:
        return points[-1].copy()

    for segment_index in range(len(points) - 1):
        start_distance = cumulative[segment_index]
        end_distance = cumulative[segment_index + 1]
        if distance > end_distance and segment_index < len(points) - 2:
            continue
        segment_span = end_distance - start_distance
        if segment_span <= 1e-8:
            return points[segment_index + 1].copy()
        t = _clamp01((distance - start_distance) / segment_span)
        return points[segment_index].lerp(points[segment_index + 1], t)

    return points[-1].copy()


def _resample_polyline(points: tuple[Vector, ...], sample_count: int) -> tuple[Vector, ...]:
    if not points:
        return ()
    if sample_count <= 1 or len(points) == 1:
        return (points[0].copy(),)

    cumulative, total_length = _polyline_cumulative_lengths(points)
    if total_length <= 1e-8:
        return tuple(points[0].copy() for _ in range(sample_count))

    samples = []
    for sample_index in range(sample_count):
        distance = total_length * float(sample_index) / float(sample_count - 1)
        samples.append(_sample_polyline_at_distance(points, cumulative, distance))
    return tuple(samples)


def _safe_normalized(vector: Vector, fallback: Vector) -> Vector:
    if vector.length > 1e-8:
        return vector.normalized()
    if fallback.length > 1e-8:
        return fallback.normalized()
    return Vector((1.0, 0.0, 0.0))


def _sample_polyline_direction(points: tuple[Vector, ...], sample_index: int) -> Vector:
    if len(points) < 2:
        return Vector((0.0, 0.0, 0.0))
    if sample_index <= 0:
        return points[1] - points[0]
    if sample_index >= len(points) - 1:
        return points[-1] - points[-2]
    return points[sample_index + 1] - points[sample_index - 1]


@dataclass(frozen=True)
class _SpineCurveData:
    points: tuple[Vector, ...]
    tangents: tuple[Vector, ...]
    normals: tuple[Vector, ...] = ()
    binormals: tuple[Vector, ...] = ()
    periodic: bool = False


def _distances_to_normalized_stations(
    cumulative: tuple[float, ...],
    total_length: float,
) -> tuple[float, ...]:
    if not cumulative:
        return ()
    if total_length <= 1e-8:
        count = len(cumulative)
        if count <= 1:
            return (0.0,)
        return tuple(float(index) / float(count - 1) for index in range(count))
    return tuple(distance / total_length for distance in cumulative)


def _sample_polyline_at_stations(
    points: tuple[Vector, ...],
    cumulative: tuple[float, ...],
    total_length: float,
    stations: tuple[float, ...],
) -> tuple[tuple[Vector, ...], tuple[float, ...]]:
    if not points or not stations:
        return (), ()
    if total_length <= 1e-8:
        return (
            tuple(points[0].copy() for _ in stations),
            tuple(0.0 for _ in stations),
        )

    sampled_points = []
    sampled_distances = []
    for station_t in stations:
        distance = _clamp01(station_t) * total_length
        sampled_distances.append(distance)
        sampled_points.append(_sample_polyline_at_distance(points, cumulative, distance))
    return tuple(sampled_points), tuple(sampled_distances)


def _build_bootstrap_sections(
    side_a_points: tuple[Vector, ...],
    side_b_points: tuple[Vector, ...],
) -> tuple[
    tuple[Vector, ...],
    tuple[Vector, ...],
    tuple[float, ...],
    tuple[float, ...],
    tuple[float, ...],
]:
    if not side_a_points or not side_b_points:
        return (), (), (), (), ()

    cumulative_a, total_a = _polyline_cumulative_lengths(side_a_points)
    cumulative_b, total_b = _polyline_cumulative_lengths(side_b_points)
    section_count = max(len(side_a_points), len(side_b_points), 2)
    section_stations = tuple(
        float(section_index) / float(section_count - 1)
        for section_index in range(section_count)
    )
    side_a_sections, side_a_section_distances = _sample_polyline_at_stations(
        side_a_points,
        cumulative_a,
        total_a,
        section_stations,
    )
    side_b_sections, side_b_section_distances = _sample_polyline_at_stations(
        side_b_points,
        cumulative_b,
        total_b,
        section_stations,
    )
    if not side_a_sections or not side_b_sections:
        return (), (), (), (), ()

    return (
        side_a_sections,
        side_b_sections,
        side_a_section_distances,
        side_b_section_distances,
        section_stations,
    )


def _chain_vertex_indices(chain: BoundaryChain, reversed_points: bool) -> tuple[int, ...]:
    indices = tuple(int(vertex_index) for vertex_index in chain.vert_indices)
    return tuple(reversed(indices)) if reversed_points else indices


def _collect_chain_group_vert_indices(
    graph: PatchGraph,
    chain_refs: tuple[tuple[int, int, int], ...],
) -> set[int]:
    result: set[int] = set()
    for chain_ref in chain_refs:
        chain = graph.get_chain(*chain_ref)
        if chain is None:
            continue
        result.update(int(vertex_index) for vertex_index in chain.vert_indices)
    return result


def _build_patch_vertex_cos(node) -> dict[int, Vector]:
    mesh_vert_indices = tuple(getattr(node, "mesh_vert_indices", ()) or ())
    if len(mesh_vert_indices) == len(node.mesh_verts):
        return {
            int(vertex_index): node.mesh_verts[index].copy()
            for index, vertex_index in enumerate(mesh_vert_indices)
        }

    result: dict[int, Vector] = {}
    for boundary_loop in node.boundary_loops:
        for chain in boundary_loop.chains:
            for vertex_index, point in zip(chain.vert_indices, chain.vert_cos):
                result.setdefault(int(vertex_index), point.copy())
    return result


def _build_patch_edge_adjacency(node, vertex_cos: dict[int, Vector]) -> dict[int, list[tuple[int, float]]]:
    adjacency: dict[int, list[tuple[int, float]]] = {vertex_index: [] for vertex_index in vertex_cos}
    for a, b in tuple(getattr(node, "mesh_edges", ()) or ()):
        a = int(a)
        b = int(b)
        if a == b or a not in vertex_cos or b not in vertex_cos:
            continue
        weight = max((vertex_cos[a] - vertex_cos[b]).length, 1e-8)
        adjacency[a].append((b, weight))
        adjacency[b].append((a, weight))
    return adjacency


def _dijkstra_distances(
    adjacency: dict[int, list[tuple[int, float]]],
    seed_vertices: set[int],
) -> dict[int, float]:
    distances: dict[int, float] = {}
    heap: list[tuple[float, int]] = []
    for vertex_index in seed_vertices:
        if vertex_index not in adjacency:
            continue
        distances[vertex_index] = 0.0
        heappush(heap, (0.0, vertex_index))

    while heap:
        distance, vertex_index = heappop(heap)
        if distance > distances.get(vertex_index, math.inf) + 1e-10:
            continue
        for neighbor_index, weight in adjacency.get(vertex_index, ()):
            next_distance = distance + weight
            if next_distance + 1e-10 >= distances.get(neighbor_index, math.inf):
                continue
            distances[neighbor_index] = next_distance
            heappush(heap, (next_distance, neighbor_index))
    return distances


def _initialize_station_values(
    adjacency: dict[int, list[tuple[int, float]]],
    vertex_indices: tuple[int, ...],
    start_vertices: set[int],
    end_vertices: set[int],
) -> dict[int, float]:
    start_distances = _dijkstra_distances(adjacency, start_vertices)
    end_distances = _dijkstra_distances(adjacency, end_vertices)
    values: dict[int, float] = {}
    for vertex_index in vertex_indices:
        if vertex_index in start_vertices:
            values[vertex_index] = 0.0
            continue
        if vertex_index in end_vertices:
            values[vertex_index] = 1.0
            continue
        start_distance = start_distances.get(vertex_index)
        end_distance = end_distances.get(vertex_index)
        if start_distance is None or end_distance is None:
            values[vertex_index] = 0.5
            continue
        denominator = start_distance + end_distance
        values[vertex_index] = (
            _clamp01(start_distance / denominator)
            if denominator > 1e-8 else
            0.5
        )
    return values


def _relax_harmonic_station_values(
    adjacency: dict[int, list[tuple[int, float]]],
    values: dict[int, float],
    fixed_vertices: set[int],
    *,
    iteration_count: int = 96,
) -> dict[int, float]:
    if not values:
        return {}
    solved = dict(values)
    free_vertices = tuple(
        vertex_index
        for vertex_index in sorted(solved)
        if vertex_index not in fixed_vertices and adjacency.get(vertex_index)
    )
    if not free_vertices:
        return solved

    for _iteration in range(max(iteration_count, 1)):
        max_delta = 0.0
        for vertex_index in free_vertices:
            weighted_sum = 0.0
            weight_sum = 0.0
            for neighbor_index, edge_length in adjacency.get(vertex_index, ()):
                if neighbor_index not in solved:
                    continue
                weight = 1.0 / max(edge_length, 1e-8)
                weighted_sum += solved[neighbor_index] * weight
                weight_sum += weight
            if weight_sum <= 1e-12:
                continue
            next_value = _clamp01(weighted_sum / weight_sum)
            max_delta = max(max_delta, abs(next_value - solved[vertex_index]))
            solved[vertex_index] = next_value
        if max_delta <= 1e-6:
            break
    return solved


def _build_topology_station_map(
    graph: PatchGraph,
    node,
    cap_start_refs: tuple[tuple[int, int, int], ...],
    cap_end_refs: tuple[tuple[int, int, int], ...],
) -> dict[int, float]:
    vertex_cos = _build_patch_vertex_cos(node)
    if not vertex_cos:
        return {}

    adjacency = _build_patch_edge_adjacency(node, vertex_cos)
    if not any(adjacency.values()):
        return {}

    start_vertices = _collect_chain_group_vert_indices(graph, cap_start_refs)
    end_vertices = _collect_chain_group_vert_indices(graph, cap_end_refs)
    if not start_vertices or not end_vertices:
        return {}

    vertex_indices = tuple(sorted(vertex_cos))
    initial_values = _initialize_station_values(
        adjacency,
        vertex_indices,
        start_vertices,
        end_vertices,
    )
    return _relax_harmonic_station_values(
        adjacency,
        initial_values,
        start_vertices | end_vertices,
    )


def _make_monotonic_stations(stations: tuple[float, ...]) -> tuple[float, ...]:
    if len(stations) < 2:
        return ()
    result = []
    previous = 0.0
    for index, station in enumerate(stations):
        value = _clamp01(station)
        if index == 0:
            previous = value
        elif value < previous:
            value = previous
        result.append(value)
        previous = value
    if result[-1] - result[0] <= 1e-5:
        return ()
    return tuple(result)


def _station_sequence_for_chain(
    chain: BoundaryChain,
    reversed_points: bool,
    station_map: dict[int, float],
) -> tuple[float, ...]:
    vertex_indices = _chain_vertex_indices(chain, reversed_points)
    if len(vertex_indices) < 2:
        return ()
    stations = []
    for vertex_index in vertex_indices:
        station = station_map.get(vertex_index)
        if station is None:
            return ()
        stations.append(station)
    return _make_monotonic_stations(tuple(stations))


def _merge_section_stations(*station_sequences: tuple[float, ...]) -> tuple[float, ...]:
    values = [0.0, 1.0]
    for sequence in station_sequences:
        values.extend(_clamp01(station) for station in sequence)
    values.sort()

    merged = []
    for value in values:
        if merged and abs(value - merged[-1]) <= 1e-5:
            continue
        merged.append(value)
    if len(merged) < 2:
        return ()
    merged[0] = 0.0
    merged[-1] = 1.0
    return tuple(merged)


def _sample_side_at_station(
    points: tuple[Vector, ...],
    point_distances: tuple[float, ...],
    point_stations: tuple[float, ...],
    station: float,
) -> tuple[Vector, float]:
    if not points or len(points) != len(point_distances) or len(points) != len(point_stations):
        return Vector((0.0, 0.0, 0.0)), 0.0
    target = _clamp01(station)
    if target <= point_stations[0] + 1e-6:
        return points[0].copy(), point_distances[0]
    if target >= point_stations[-1] - 1e-6:
        return points[-1].copy(), point_distances[-1]

    for index in range(len(points) - 1):
        start_station = point_stations[index]
        end_station = point_stations[index + 1]
        if end_station < start_station:
            continue
        if target < start_station - 1e-6 or target > end_station + 1e-6:
            continue
        span = end_station - start_station
        if span <= 1e-8:
            return points[index].copy(), point_distances[index]
        local_t = _clamp01((target - start_station) / span)
        point = points[index].lerp(points[index + 1], local_t)
        distance = point_distances[index] + (point_distances[index + 1] - point_distances[index]) * local_t
        return point, distance

    nearest_index = min(
        range(len(point_stations)),
        key=lambda index: abs(point_stations[index] - target),
    )
    return points[nearest_index].copy(), point_distances[nearest_index]


def _sample_side_sections_by_station(
    points: tuple[Vector, ...],
    point_stations: tuple[float, ...],
    section_stations: tuple[float, ...],
) -> tuple[tuple[Vector, ...], tuple[float, ...]]:
    point_distances, _total_length = _polyline_cumulative_lengths(points)
    if len(point_distances) != len(points) or len(point_stations) != len(points):
        return (), ()

    section_points = []
    section_distances = []
    for station in section_stations:
        point, distance = _sample_side_at_station(
            points,
            point_distances,
            point_stations,
            station,
        )
        section_points.append(point)
        section_distances.append(distance)
    return tuple(section_points), tuple(section_distances)


def _build_topology_sections(
    graph: PatchGraph,
    node,
    side_a_ref: tuple[int, int, int],
    side_b_ref: tuple[int, int, int],
    side_a_points: tuple[Vector, ...],
    side_b_points: tuple[Vector, ...],
    side_a_reversed: bool,
    side_b_reversed: bool,
    cap_start_refs: tuple[tuple[int, int, int], ...],
    cap_end_refs: tuple[tuple[int, int, int], ...],
) -> tuple[
    tuple[Vector, ...],
    tuple[Vector, ...],
    tuple[float, ...],
    tuple[float, ...],
    tuple[float, ...],
    tuple[float, ...],
    tuple[float, ...],
]:
    side_a_chain = graph.get_chain(*side_a_ref)
    side_b_chain = graph.get_chain(*side_b_ref)
    if side_a_chain is None or side_b_chain is None:
        return (), (), (), (), (), (), ()

    station_map = _build_topology_station_map(
        graph,
        node,
        cap_start_refs,
        cap_end_refs,
    )
    if not station_map:
        return (), (), (), (), (), (), ()

    side_a_stations = _station_sequence_for_chain(side_a_chain, side_a_reversed, station_map)
    side_b_stations = _station_sequence_for_chain(side_b_chain, side_b_reversed, station_map)
    if not side_a_stations or not side_b_stations:
        return (), (), (), (), (), (), ()
    if len(side_a_stations) != len(side_a_points) or len(side_b_stations) != len(side_b_points):
        return (), (), (), (), (), (), ()

    section_stations = _merge_section_stations(side_a_stations, side_b_stations)
    if not section_stations:
        return (), (), (), (), (), (), ()

    side_a_sections, side_a_distances = _sample_side_sections_by_station(
        side_a_points,
        side_a_stations,
        section_stations,
    )
    side_b_sections, side_b_distances = _sample_side_sections_by_station(
        side_b_points,
        side_b_stations,
        section_stations,
    )
    if not side_a_sections or not side_b_sections:
        return (), (), (), (), (), (), ()
    return (
        side_a_sections,
        side_b_sections,
        side_a_distances,
        side_b_distances,
        section_stations,
        side_a_stations,
        side_b_stations,
    )


def _polyline_centroid(points: tuple[Vector, ...]) -> Vector:
    if not points:
        return Vector((0.0, 0.0, 0.0))
    total = Vector((0.0, 0.0, 0.0))
    for point in points:
        total += point
    return total / float(len(points))


def _is_closed_ring(points: tuple[Vector, ...]) -> bool:
    """Return True when the polyline's first and last vertex coincide.

    Tube / cable caps are single boundary chains whose walking order
    traverses the full ring and returns to the seam vertex — ``points[0]``
    and ``points[-1]`` refer to the SAME physical vertex.  Open-strip
    BAND caps have distinct end vertices and return False here.  The
    closed-ring check gates the spine-relative orientation that replaces
    degenerate hint-based orientation at tube caps.
    """
    if len(points) < 3:
        return False
    _cumulative, perimeter = _polyline_cumulative_lengths(points)
    if perimeter <= 1e-8:
        return False
    gap = (points[0] - points[-1]).length
    return gap <= max(1e-6, 0.02 * perimeter)




def _oriented_chain_points(
    chain: BoundaryChain,
    start_hint: Vector,
    end_hint: Vector,
) -> tuple[tuple[Vector, ...], bool]:
    points = tuple(point.copy() for point in chain.vert_cos)
    if len(points) < 2:
        return points, False

    forward_score = (
        (points[0] - start_hint).length_squared
        + (points[-1] - end_hint).length_squared
    )
    reverse_score = (
        (points[-1] - start_hint).length_squared
        + (points[0] - end_hint).length_squared
    )
    if reverse_score + 1e-8 < forward_score:
        return tuple(reversed(points)), True
    return points, False


def _chain_group_length(
    graph: PatchGraph,
    chain_refs: tuple[tuple[int, int, int], ...],
) -> float:
    total = 0.0
    for chain_ref in chain_refs:
        chain = graph.get_chain(*chain_ref)
        if chain is None:
            continue
        _cumulative, chain_length = _polyline_cumulative_lengths(tuple(chain.vert_cos))
        total += chain_length
    return total


def _sample_station_section_points(
    node,
    station_map: dict[int, float],
    station: float,
    vertex_cos: dict[int, Vector],
) -> tuple[Vector, ...]:
    target = _clamp01(station)
    points: list[Vector] = []
    seen_keys: set[tuple[int, int, int]] = set()

    def _append_unique(point: Vector) -> None:
        key = (
            int(round(point.x * 100000.0)),
            int(round(point.y * 100000.0)),
            int(round(point.z * 100000.0)),
        )
        if key in seen_keys:
            return
        seen_keys.add(key)
        points.append(point)

    for edge_a, edge_b in tuple(getattr(node, "mesh_edges", ()) or ()):
        edge_a = int(edge_a)
        edge_b = int(edge_b)
        value_a = station_map.get(edge_a)
        value_b = station_map.get(edge_b)
        point_a = vertex_cos.get(edge_a)
        point_b = vertex_cos.get(edge_b)
        if value_a is None or value_b is None or point_a is None or point_b is None:
            continue

        if abs(value_a - target) <= 1e-6:
            _append_unique(point_a.copy())
        if abs(value_b - target) <= 1e-6:
            _append_unique(point_b.copy())

        delta = value_b - value_a
        if abs(delta) <= 1e-8:
            continue
        if (target - value_a) * (target - value_b) > 0.0:
            continue
        factor = _clamp01((target - value_a) / delta)
        _append_unique(point_a.lerp(point_b, factor))

    if points:
        return tuple(points)

    nearest = sorted(
        (
            (abs(value - target), vertex_index)
            for vertex_index, value in station_map.items()
            if vertex_index in vertex_cos
        ),
        key=lambda item: item[0],
    )[:8]
    return tuple(vertex_cos[vertex_index].copy() for _delta, vertex_index in nearest)


def _build_station_centerline_points(
    graph: PatchGraph,
    node,
    cap_start_refs: tuple[tuple[int, int, int], ...],
    cap_end_refs: tuple[tuple[int, int, int], ...],
    section_stations: tuple[float, ...],
) -> tuple[Vector, ...]:
    station_map = _build_topology_station_map(
        graph,
        node,
        cap_start_refs,
        cap_end_refs,
    )
    if not station_map or not section_stations:
        return ()

    vertex_cos = _build_patch_vertex_cos(node)
    if not vertex_cos:
        return ()

    start_vertices = _collect_chain_group_vert_indices(graph, cap_start_refs)
    end_vertices = _collect_chain_group_vert_indices(graph, cap_end_refs)
    start_points = tuple(
        vertex_cos[vertex_index].copy()
        for vertex_index in start_vertices
        if vertex_index in vertex_cos
    )
    end_points = tuple(
        vertex_cos[vertex_index].copy()
        for vertex_index in end_vertices
        if vertex_index in vertex_cos
    )

    centerline_points = []
    for station in section_stations:
        target = _clamp01(station)
        if target <= 1e-6 and start_points:
            centerline_points.append(_polyline_centroid(start_points))
            continue
        if target >= 1.0 - 1e-6 and end_points:
            centerline_points.append(_polyline_centroid(end_points))
            continue
        section_points = _sample_station_section_points(
            node,
            station_map,
            target,
            vertex_cos,
        )
        if not section_points:
            return ()
        centerline_points.append(_polyline_centroid(section_points))
    return tuple(centerline_points)


def _intersect_section_plane_with_polyline(
    polyline_points: tuple[Vector, ...],
    cumulative_distances: tuple[float, ...],
    plane_point: Vector,
    plane_normal: Vector,
    *,
    previous_distance: Optional[float],
    fallback_point: Vector,
    fallback_distance: float,
) -> tuple[Vector, float]:
    """Intersect a 3D plane with a polyline; return the forward-progress crossing.

    The plane passes through ``plane_point`` with normal ``plane_normal``.
    Each polyline segment is tested for a sign change of the signed distance
    ``(X - plane_point) · plane_normal``; a change implies the segment crosses
    the plane, and the exact crossing is linear interpolation of the signed
    values.  Among crossings, the one with the smallest forward-progress
    relative to ``previous_distance`` is returned (falling back to closest
    approach when no forward crossing exists).

    This is a 3D-native replacement for the earlier patch-plane 2D-projection
    intersection: it produces correct section distances for both in-plane and
    out-of-plane bands (serpentines folded along the face normal) and
    preserves the local rail compression/expansion at bends that drives the
    rigidity-weighted section redistribution.
    """

    if plane_normal.length <= 1e-8:
        return fallback_point.copy(), fallback_distance
    normal_dir = plane_normal.normalized()
    candidates: list[tuple[float, float, Vector]] = []
    for segment_index in range(len(polyline_points) - 1):
        segment_start = polyline_points[segment_index]
        segment_end = polyline_points[segment_index + 1]
        d_start = (segment_start - plane_point).dot(normal_dir)
        d_end = (segment_end - plane_point).dot(normal_dir)
        # Skip segments entirely on one side of the plane; a near-grazing
        # tolerance keeps duplicate hits at shared vertices from exploding.
        if d_start > 1e-8 and d_end > 1e-8:
            continue
        if d_start < -1e-8 and d_end < -1e-8:
            continue
        denominator = d_start - d_end
        if abs(denominator) <= 1e-10:
            # Segment lies within the plane; treat its start as the crossing.
            segment_t = 0.0
        else:
            segment_t = _clamp01(d_start / denominator)
        point = segment_start.lerp(segment_end, segment_t)
        segment_length = (segment_end - segment_start).length
        distance = cumulative_distances[segment_index] + segment_length * segment_t
        line_offset = (point - plane_point).length
        candidates.append((distance, line_offset, point))

    if not candidates:
        return fallback_point.copy(), fallback_distance

    if previous_distance is None:
        best_distance, _offset, best_point = min(candidates, key=lambda item: item[1])
        return best_point, best_distance

    forward_candidates = [
        candidate for candidate in candidates
        if candidate[0] + 1e-6 >= previous_distance
    ]
    if forward_candidates:
        best_distance, _offset, best_point = min(
            forward_candidates,
            key=lambda item: (item[0] - previous_distance, item[1]),
        )
        return best_point, best_distance

    best_distance, _offset, best_point = min(
        candidates,
        key=lambda item: (abs(item[0] - previous_distance), item[1]),
    )
    return best_point, best_distance


def _build_spine_normal_sections(
    side_a_points: tuple[Vector, ...],
    side_b_points: tuple[Vector, ...],
    spine_points: tuple[Vector, ...],
    fallback_side_a_sections: tuple[Vector, ...],
    fallback_side_b_sections: tuple[Vector, ...],
    fallback_side_a_distances: tuple[float, ...],
    fallback_side_b_distances: tuple[float, ...],
    spine_tangents: Optional[tuple[Vector, ...]] = None,
) -> tuple[
    tuple[Vector, ...],
    tuple[Vector, ...],
    tuple[float, ...],
    tuple[float, ...],
]:
    """Cut spine-normal sections in 3D and intersect with rail polylines.

    The cutting plane at each interior spine station is perpendicular to the
    spine 3D tangent (the plane normal IS the tangent).  Rail crossings are
    located by signed-distance sign changes along each polyline segment, so
    the sectioning is intrinsically 3D and preserves the local rail
    compression/expansion at bends -- both in-plane bends (cones, arcs in the
    patch plane) and out-of-plane bends (serpentines folded along the face
    normal).
    """

    if not side_a_points or not side_b_points or not spine_points:
        return (), (), (), ()

    cumulative_a, _total_a = _polyline_cumulative_lengths(side_a_points)
    cumulative_b, _total_b = _polyline_cumulative_lengths(side_b_points)

    side_a_sections = []
    side_b_sections = []
    side_a_section_distances = []
    side_b_section_distances = []
    previous_a_distance: Optional[float] = None
    previous_b_distance: Optional[float] = None

    for sample_index, spine_point in enumerate(spine_points):
        if sample_index < len(fallback_side_a_sections):
            fallback_a_point = fallback_side_a_sections[sample_index]
            fallback_a_distance = fallback_side_a_distances[sample_index]
        else:
            fallback_a_point = side_a_points[-1]
            fallback_a_distance = cumulative_a[-1]

        if sample_index < len(fallback_side_b_sections):
            fallback_b_point = fallback_side_b_sections[sample_index]
            fallback_b_distance = fallback_side_b_distances[sample_index]
        else:
            fallback_b_point = side_b_points[-1]
            fallback_b_distance = cumulative_b[-1]

        if sample_index == 0:
            side_a_sections.append(fallback_a_point.copy())
            side_b_sections.append(fallback_b_point.copy())
            side_a_section_distances.append(fallback_a_distance)
            side_b_section_distances.append(fallback_b_distance)
            previous_a_distance = fallback_a_distance
            previous_b_distance = fallback_b_distance
            continue

        if sample_index == len(spine_points) - 1:
            side_a_sections.append(fallback_a_point.copy())
            side_b_sections.append(fallback_b_point.copy())
            side_a_section_distances.append(fallback_a_distance)
            side_b_section_distances.append(fallback_b_distance)
            previous_a_distance = fallback_a_distance
            previous_b_distance = fallback_b_distance
            continue

        if spine_tangents and sample_index < len(spine_tangents):
            tangent = spine_tangents[sample_index]
        else:
            tangent = _sample_polyline_direction(spine_points, sample_index)
        # The spine 3D tangent is the section plane's normal; no 2D projection.
        plane_normal_3d = _safe_normalized(
            tangent,
            fallback_b_point - fallback_a_point,
        )

        side_a_section, side_a_distance = _intersect_section_plane_with_polyline(
            side_a_points,
            cumulative_a,
            spine_point,
            plane_normal_3d,
            previous_distance=previous_a_distance,
            fallback_point=fallback_a_point,
            fallback_distance=fallback_a_distance,
        )
        side_b_section, side_b_distance = _intersect_section_plane_with_polyline(
            side_b_points,
            cumulative_b,
            spine_point,
            plane_normal_3d,
            previous_distance=previous_b_distance,
            fallback_point=fallback_b_point,
            fallback_distance=fallback_b_distance,
        )
        side_a_sections.append(side_a_section)
        side_b_sections.append(side_b_section)
        side_a_section_distances.append(side_a_distance)
        side_b_section_distances.append(side_b_distance)
        previous_a_distance = side_a_distance
        previous_b_distance = side_b_distance

    return (
        tuple(side_a_sections),
        tuple(side_b_sections),
        tuple(side_a_section_distances),
        tuple(side_b_section_distances),
    )


def _median(values: tuple[float, ...]) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[mid]
    return 0.5 * (ordered[mid - 1] + ordered[mid])


def _polyline_turn_strengths(points: tuple[Vector, ...]) -> tuple[float, ...]:
    if not points:
        return ()
    strengths = [0.0] * len(points)
    for point_index in range(1, len(points) - 1):
        prev_dir = points[point_index] - points[point_index - 1]
        next_dir = points[point_index + 1] - points[point_index]
        if prev_dir.length <= 1e-8 or next_dir.length <= 1e-8:
            continue
        prev_dir.normalize()
        next_dir.normalize()
        strengths[point_index] = _clamp01((1.0 - prev_dir.dot(next_dir)) * 0.5)
    return tuple(strengths)


def _build_weighted_section_target_distances(
    side_a_section_distances: tuple[float, ...],
    side_b_section_distances: tuple[float, ...],
    spine_points: tuple[Vector, ...],
    target_total_override: Optional[float] = None,
) -> tuple[tuple[float, ...], float]:
    section_count = min(
        len(side_a_section_distances),
        len(side_b_section_distances),
        len(spine_points),
    )
    if section_count <= 0:
        return (), 0.0
    if section_count == 1:
        return (0.0,), 0.0

    spine_turns = _polyline_turn_strengths(spine_points)
    avg_lengths = []
    spine_lengths = []
    asymmetries = []
    curvatures = []
    for section_index in range(1, section_count):
        delta_a = max(
            0.0,
            side_a_section_distances[section_index] - side_a_section_distances[section_index - 1],
        )
        delta_b = max(
            0.0,
            side_b_section_distances[section_index] - side_b_section_distances[section_index - 1],
        )
        avg_lengths.append(0.5 * (delta_a + delta_b))
        spine_lengths.append(
            (spine_points[section_index] - spine_points[section_index - 1]).length
        )
        asymmetries.append(
            _clamp01(abs(delta_a - delta_b) / max(delta_a, delta_b, 1e-8))
        )
        curvatures.append(
            max(
                spine_turns[section_index - 1] if section_index - 1 < len(spine_turns) else 0.0,
                spine_turns[section_index] if section_index < len(spine_turns) else 0.0,
            )
        )

    median_avg = max(_median(tuple(avg_lengths)), 1e-8)
    rigidity_weights = []
    for avg_len, asymmetry, curvature in zip(
        avg_lengths,
        asymmetries,
        curvatures,
    ):
        len_factor = min(max(avg_len / median_avg, 0.35), 3.25)
        straight_factor = max(0.05, 1.0 - curvature)
        symmetry_factor = max(0.1, 1.0 - asymmetry)
        rigidity = (
            (len_factor ** 1.9)
            * (straight_factor ** 2.8)
            * (symmetry_factor ** 1.15)
        )
        if len_factor > 1.05 and curvature <= 0.08:
            rigidity *= 1.0 + min((len_factor - 1.0) * 0.8, 0.6)
        rigidity_weights.append(max(0.02, rigidity))

    rest_total = sum(avg_lengths)
    target_total = (
        target_total_override
        if target_total_override is not None and target_total_override > 1e-8
        else sum(spine_lengths)
    )
    inv_rigidity_sum = sum(1.0 / weight for weight in rigidity_weights)
    if rest_total <= 1e-8 or inv_rigidity_sum <= 1e-8:
        adjusted_lengths = list(avg_lengths)
    else:
        lambda_scale = (target_total - rest_total) / inv_rigidity_sum
        adjusted_lengths = [
            max(avg_len + (lambda_scale / rigidity), 1e-6)
            for avg_len, rigidity in zip(avg_lengths, rigidity_weights)
        ]
        adjusted_total = sum(adjusted_lengths)
        if adjusted_total > 1e-8:
            total_scale = target_total / adjusted_total
            adjusted_lengths = [max(length * total_scale, 1e-6) for length in adjusted_lengths]

    target_distances = [0.0]
    walked = 0.0
    for interval_length in adjusted_lengths:
        walked += max(interval_length, 0.0)
        target_distances.append(walked)

    return tuple(target_distances), walked


def _remap_distances_to_section_profile(
    point_distances: tuple[float, ...],
    section_source_distances: tuple[float, ...],
    section_target_distances: tuple[float, ...],
) -> tuple[float, ...]:
    if not point_distances:
        return ()
    if (
        len(section_source_distances) < 2
        or len(section_source_distances) != len(section_target_distances)
    ):
        return tuple(0.0 for _ in point_distances)

    mapped_distances = []
    section_index = 0
    for distance in point_distances:
        while (
            section_index < len(section_source_distances) - 2
            and distance > section_source_distances[section_index + 1]
        ):
            section_index += 1

        start_source = section_source_distances[section_index]
        end_source = section_source_distances[section_index + 1]
        start_target = section_target_distances[section_index]
        end_target = section_target_distances[section_index + 1]

        if end_source - start_source <= 1e-8:
            local_t = 0.0
        else:
            local_t = _clamp01((distance - start_source) / (end_source - start_source))
        mapped_distances.append(start_target + (end_target - start_target) * local_t)

    return tuple(mapped_distances)


def _remap_stations_to_section_profile(
    point_stations: tuple[float, ...],
    section_stations: tuple[float, ...],
    section_target_distances: tuple[float, ...],
) -> tuple[float, ...]:
    if not point_stations:
        return ()
    if len(section_stations) < 2 or len(section_stations) != len(section_target_distances):
        return tuple(0.0 for _ in point_stations)

    mapped_distances = []
    section_index = 0
    for station in point_stations:
        value = _clamp01(station)
        while (
            section_index < len(section_stations) - 2
            and value > section_stations[section_index + 1]
        ):
            section_index += 1

        start_station = section_stations[section_index]
        end_station = section_stations[section_index + 1]
        start_target = section_target_distances[section_index]
        end_target = section_target_distances[section_index + 1]

        if end_station - start_station <= 1e-8:
            local_t = 0.0
        else:
            local_t = _clamp01((value - start_station) / (end_station - start_station))
        mapped_distances.append(start_target + (end_target - start_target) * local_t)

    return tuple(mapped_distances)


def _endpoint_direction(points: tuple[Vector, ...], *, at_start: bool) -> Vector:
    if len(points) < 2:
        return Vector((0.0, 0.0, 0.0))
    if at_start:
        return points[1] - points[0]
    return points[-1] - points[-2]


def _mean_direction(
    first: Vector,
    second: Vector,
    fallback: Vector,
) -> Vector:
    if first.length <= 1e-8 and second.length <= 1e-8:
        if fallback.length <= 1e-8:
            return Vector((0.0, 0.0, 0.0))
        return fallback.normalized()
    if first.length <= 1e-8:
        return _safe_normalized(second, fallback)
    if second.length <= 1e-8:
        return _safe_normalized(first, fallback)
    aligned_second = second.copy()
    if first.dot(aligned_second) < 0.0:
        aligned_second.negate()
    return _safe_normalized(first + aligned_second, fallback)


def _build_midpoint_spine_points(
    side_a_sections: tuple[Vector, ...],
    side_b_sections: tuple[Vector, ...],
) -> tuple[Vector, ...]:
    sample_count = min(len(side_a_sections), len(side_b_sections))
    if sample_count <= 0:
        return ()
    return tuple(
        (side_a_sections[index] + side_b_sections[index]) * 0.5
        for index in range(sample_count)
    )


def _build_spine_curve_from_control_points(
    graph: PatchGraph,
    control_points: tuple[Vector, ...],
    frame_side_a_sections: tuple[Vector, ...],
    frame_side_b_sections: tuple[Vector, ...],
    cap_start_refs: tuple[tuple[int, int, int], ...],
    cap_end_refs: tuple[tuple[int, int, int], ...],
    sample_stations: Optional[tuple[float, ...]] = None,
) -> _SpineCurveData:
    if not control_points:
        return _SpineCurveData(points=(), tangents=(), normals=(), binormals=())

    periodic = _cap_groups_are_periodic_boundary(graph, cap_start_refs, cap_end_refs)
    if periodic:
        start_tangent = None
        end_tangent = None
    else:
        fallback_start = _endpoint_direction(control_points, at_start=True)
        fallback_end = _endpoint_direction(control_points, at_start=False)
        start_tangent = _mean_direction(
            _endpoint_direction(frame_side_a_sections, at_start=True),
            _endpoint_direction(frame_side_b_sections, at_start=True),
            fallback_start,
        )
        end_tangent = _mean_direction(
            _endpoint_direction(frame_side_a_sections, at_start=False),
            _endpoint_direction(frame_side_b_sections, at_start=False),
            fallback_end,
        )

    sample_count = len(control_points)
    control_params = _build_centripetal_parameter_values(control_points)
    total_param = control_params[-1] if control_params else 0.0
    sample_params: tuple[float, ...]
    if sample_count <= 1:
        spine_points = tuple(point.copy() for point in control_points)
        sample_params = (0.0,) if spine_points else ()
    elif total_param <= 1e-8:
        spine_points = tuple(control_points[0].copy() for _ in range(sample_count))
        sample_params = tuple(0.0 for _ in range(sample_count))
    else:
        if sample_stations is not None and len(sample_stations) == sample_count:
            sample_params = tuple(total_param * _clamp01(station) for station in sample_stations)
        else:
            sample_params = tuple(
                total_param * float(sample_index) / float(sample_count - 1)
                for sample_index in range(sample_count)
            )
        spine_points = tuple(
            _evaluate_centripetal_catmull_rom(
                control_points,
                control_params,
                sample_param,
                periodic=periodic,
                start_tangent=start_tangent,
                end_tangent=end_tangent,
            )
            for sample_param in sample_params
        )

    if not spine_points:
        spine_tangents = ()
    elif total_param <= 1e-8:
        spine_tangents = tuple(
            _safe_normalized(
                _sample_polyline_direction(spine_points, point_index),
                start_tangent if point_index == 0 and start_tangent is not None else (
                    end_tangent if point_index == len(spine_points) - 1 and end_tangent is not None else Vector((1.0, 0.0, 0.0))
                ),
            )
            for point_index in range(len(spine_points))
        )
    else:
        spine_tangents = tuple(
            _sample_centripetal_curve_tangent(
                control_points,
                control_params,
                sample_params[min(point_index, len(sample_params) - 1)],
                periodic=periodic,
                start_tangent=start_tangent,
                end_tangent=end_tangent,
            )
            for point_index in range(len(spine_points))
        )

    if len(spine_points) > 1 and len(spine_tangents) != len(spine_points):
        spine_tangents = tuple(
            _safe_normalized(
                _sample_polyline_direction(spine_points, point_index),
                Vector((1.0, 0.0, 0.0)),
            )
            for point_index in range(len(spine_points))
        )

    initial_normal = _choose_initial_frame_normal(
        frame_side_a_sections,
        frame_side_b_sections,
        spine_tangents,
    )
    spine_normals, spine_binormals = _build_rotation_minimizing_frames(
        spine_points,
        spine_tangents,
        initial_normal,
        periodic=periodic,
    )

    return _SpineCurveData(
        points=spine_points,
        tangents=spine_tangents,
        normals=spine_normals,
        binormals=spine_binormals,
        periodic=periodic,
    )


def _cap_groups_are_periodic_boundary(
    graph: PatchGraph,
    cap_start_refs: tuple[tuple[int, int, int], ...],
    cap_end_refs: tuple[tuple[int, int, int], ...],
) -> bool:
    all_refs = tuple(cap_start_refs) + tuple(cap_end_refs)
    if not all_refs:
        return False
    for cap_ref in all_refs:
        cap_chain = graph.get_chain(*cap_ref)
        if cap_chain is None or cap_chain.neighbor_kind != ChainNeighborKind.SEAM_SELF:
            return False
    return True


def _centripetal_step(point_a: Vector, point_b: Vector) -> float:
    return max(math.sqrt(max((point_b - point_a).length, 1e-8)), 1e-8)


def _build_centripetal_parameter_values(points: tuple[Vector, ...]) -> tuple[float, ...]:
    if not points:
        return ()
    values = [0.0]
    walked = 0.0
    for point_index in range(1, len(points)):
        walked += _centripetal_step(points[point_index - 1], points[point_index])
        values.append(walked)
    return tuple(values)


def _build_endpoint_ghost_point(
    point: Vector,
    neighbor: Vector,
    tangent: Optional[Vector],
    *,
    before: bool,
) -> Vector:
    span = max((neighbor - point).length, 1e-8)
    if tangent is not None and tangent.length > 1e-8:
        forward_dir = tangent.normalized()
    else:
        fallback = neighbor - point if before else point - neighbor
        forward_dir = _safe_normalized(fallback, Vector((1.0, 0.0, 0.0)))
    return point - forward_dir * span if before else point + forward_dir * span


def _lerp_parametric(
    point_a: Vector,
    point_b: Vector,
    t_a: float,
    t_b: float,
    t: float,
) -> Vector:
    span = t_b - t_a
    if abs(span) <= 1e-8:
        return point_a.copy()
    return point_a.lerp(point_b, _clamp01((t - t_a) / span))


def _sample_centripetal_catmull_rom_segment(
    point_0: Vector,
    point_1: Vector,
    point_2: Vector,
    point_3: Vector,
    local_t: float,
) -> Vector:
    t_1 = 0.0
    t_2 = _centripetal_step(point_1, point_2)
    t_0 = t_1 - _centripetal_step(point_0, point_1)
    t_3 = t_2 + _centripetal_step(point_2, point_3)
    t = max(t_1, min(t_2, local_t))

    a_1 = _lerp_parametric(point_0, point_1, t_0, t_1, t)
    a_2 = _lerp_parametric(point_1, point_2, t_1, t_2, t)
    a_3 = _lerp_parametric(point_2, point_3, t_2, t_3, t)

    b_1 = _lerp_parametric(a_1, a_2, t_0, t_2, t)
    b_2 = _lerp_parametric(a_2, a_3, t_1, t_3, t)
    return _lerp_parametric(b_1, b_2, t_1, t_2, t)


def _resolve_catmull_segment_points(
    control_points: tuple[Vector, ...],
    segment_index: int,
    *,
    periodic: bool,
    start_tangent: Optional[Vector],
    end_tangent: Optional[Vector],
) -> tuple[Vector, Vector, Vector, Vector]:
    point_count = len(control_points)
    point_1 = control_points[segment_index]
    point_2 = control_points[segment_index + 1]

    if periodic and point_count >= 3:
        point_0 = control_points[segment_index - 1] if segment_index > 0 else control_points[-1]
        point_3 = (
            control_points[segment_index + 2]
            if segment_index + 2 < point_count
            else control_points[0]
        )
        return point_0, point_1, point_2, point_3

    point_0 = (
        control_points[segment_index - 1]
        if segment_index > 0
        else _build_endpoint_ghost_point(
            point_1,
            point_2,
            start_tangent,
            before=True,
        )
    )
    point_3 = (
        control_points[segment_index + 2]
        if segment_index + 2 < point_count
        else _build_endpoint_ghost_point(
            point_2,
            point_1,
            end_tangent,
            before=False,
        )
    )
    return point_0, point_1, point_2, point_3


def _evaluate_centripetal_catmull_rom(
    control_points: tuple[Vector, ...],
    control_params: tuple[float, ...],
    sample_param: float,
    *,
    periodic: bool,
    start_tangent: Optional[Vector],
    end_tangent: Optional[Vector],
) -> Vector:
    point_count = len(control_points)
    if point_count <= 0:
        return Vector((0.0, 0.0, 0.0))
    if point_count == 1:
        return control_points[0].copy()
    if point_count == 2:
        total = max(control_params[-1], 1e-8)
        return control_points[0].lerp(
            control_points[1],
            _clamp01(sample_param / total),
        )

    total_param = control_params[-1]
    if sample_param <= 0.0:
        segment_index = 0
        local_t = 0.0
    elif sample_param >= total_param:
        segment_index = point_count - 2
        local_t = control_params[-1] - control_params[-2]
    else:
        segment_index = 0
        for probe_index in range(point_count - 1):
            if sample_param <= control_params[probe_index + 1]:
                segment_index = probe_index
                break
        local_t = sample_param - control_params[segment_index]

    point_0, point_1, point_2, point_3 = _resolve_catmull_segment_points(
        control_points,
        segment_index,
        periodic=periodic,
        start_tangent=start_tangent,
        end_tangent=end_tangent,
    )
    return _sample_centripetal_catmull_rom_segment(
        point_0,
        point_1,
        point_2,
        point_3,
        local_t,
    )


def _sample_centripetal_curve_tangent(
    control_points: tuple[Vector, ...],
    control_params: tuple[float, ...],
    sample_param: float,
    *,
    periodic: bool,
    start_tangent: Optional[Vector],
    end_tangent: Optional[Vector],
) -> Vector:
    point_count = len(control_points)
    if point_count <= 1:
        fallback = start_tangent if start_tangent is not None else Vector((1.0, 0.0, 0.0))
        return _safe_normalized(fallback, Vector((1.0, 0.0, 0.0)))

    total_param = max(control_params[-1], 1e-8)
    delta = min(max(total_param * 1e-3, 1e-4), total_param * 0.2)
    if point_count > 1:
        min_segment = min(
            max(control_params[index + 1] - control_params[index], 1e-8)
            for index in range(point_count - 1)
        )
        delta = min(delta, min_segment * 0.25)
    delta = max(delta, 1e-5)

    if periodic and total_param > delta:
        prev_param = sample_param - delta
        next_param = sample_param + delta
        if prev_param < 0.0:
            prev_param += total_param
        if next_param > total_param:
            next_param -= total_param
    else:
        prev_param = max(0.0, sample_param - delta)
        next_param = min(total_param, sample_param + delta)
        if next_param - prev_param <= 1e-8:
            if sample_param <= 0.0:
                fallback = (
                    start_tangent
                    if start_tangent is not None and start_tangent.length > 1e-8
                    else control_points[1] - control_points[0]
                )
            else:
                fallback = (
                    end_tangent
                    if end_tangent is not None and end_tangent.length > 1e-8
                    else control_points[-1] - control_points[-2]
                )
            return _safe_normalized(fallback, Vector((1.0, 0.0, 0.0)))

    prev_point = _evaluate_centripetal_catmull_rom(
        control_points,
        control_params,
        prev_param,
        periodic=periodic,
        start_tangent=start_tangent,
        end_tangent=end_tangent,
    )
    next_point = _evaluate_centripetal_catmull_rom(
        control_points,
        control_params,
        next_param,
        periodic=periodic,
        start_tangent=start_tangent,
        end_tangent=end_tangent,
    )

    if sample_param <= 0.0 and start_tangent is not None and start_tangent.length > 1e-8:
        return _safe_normalized(next_point - prev_point, start_tangent)
    if sample_param >= total_param and end_tangent is not None and end_tangent.length > 1e-8:
        return _safe_normalized(next_point - prev_point, end_tangent)
    return _safe_normalized(next_point - prev_point, Vector((1.0, 0.0, 0.0)))


def _orthogonal_fallback(reference: Vector) -> Vector:
    reference_dir = _safe_normalized(reference, Vector((1.0, 0.0, 0.0)))
    for candidate in (Vector((0.0, 0.0, 1.0)), Vector((0.0, 1.0, 0.0)), Vector((1.0, 0.0, 0.0))):
        projected = candidate - reference_dir * candidate.dot(reference_dir)
        if projected.length > 1e-8:
            return projected.normalized()
    return Vector((0.0, 1.0, 0.0))


def _project_onto_normal_plane(vector: Vector, normal: Vector) -> Vector:
    normal_dir = _safe_normalized(normal, Vector((1.0, 0.0, 0.0)))
    return vector - normal_dir * vector.dot(normal_dir)


def _signed_angle_around_axis(from_vector: Vector, to_vector: Vector, axis: Vector) -> float:
    axis_dir = _safe_normalized(axis, Vector((1.0, 0.0, 0.0)))
    from_proj = _project_onto_normal_plane(from_vector, axis_dir)
    to_proj = _project_onto_normal_plane(to_vector, axis_dir)
    if from_proj.length <= 1e-8 or to_proj.length <= 1e-8:
        return 0.0
    from_dir = from_proj.normalized()
    to_dir = to_proj.normalized()
    sin_value = axis_dir.dot(from_dir.cross(to_dir))
    cos_value = max(-1.0, min(1.0, from_dir.dot(to_dir)))
    return math.atan2(sin_value, cos_value)


def _transport_vector_between_tangents(
    vector: Vector,
    from_tangent: Vector,
    to_tangent: Vector,
) -> Vector:
    from_dir = _safe_normalized(from_tangent, Vector((1.0, 0.0, 0.0)))
    to_dir = _safe_normalized(to_tangent, from_dir)
    axis = from_dir.cross(to_dir)
    if axis.length <= 1e-8:
        if from_dir.dot(to_dir) < 0.0:
            return (Quaternion(_orthogonal_fallback(from_dir), math.pi) @ vector)
        return vector.copy()
    dot_value = max(-1.0, min(1.0, from_dir.dot(to_dir)))
    return Quaternion(axis.normalized(), math.acos(dot_value)) @ vector


def _choose_initial_frame_normal(
    side_a_sections: tuple[Vector, ...],
    side_b_sections: tuple[Vector, ...],
    tangents: tuple[Vector, ...],
) -> Vector:
    tangent_0 = tangents[0] if tangents else Vector((1.0, 0.0, 0.0))
    lateral_sum = Vector((0.0, 0.0, 0.0))
    for point_a, point_b in zip(side_a_sections, side_b_sections):
        lateral = point_b - point_a
        if lateral.length <= 1e-8:
            continue
        if lateral_sum.length > 1e-8 and lateral.dot(lateral_sum) < 0.0:
            lateral.negate()
        lateral_sum += lateral
    if lateral_sum.length <= 1e-8 and side_a_sections and side_b_sections:
        lateral_sum = side_b_sections[0] - side_a_sections[0]

    tangent_dir = _safe_normalized(tangent_0, Vector((1.0, 0.0, 0.0)))
    projected = lateral_sum - tangent_dir * lateral_sum.dot(tangent_dir)
    if projected.length > 1e-8:
        return projected.normalized()
    return _orthogonal_fallback(tangent_dir)


def _build_rotation_minimizing_frames(
    spine_points: tuple[Vector, ...],
    tangents: tuple[Vector, ...],
    initial_normal: Vector,
    *,
    periodic: bool = False,
) -> tuple[tuple[Vector, ...], tuple[Vector, ...]]:
    point_count = min(len(spine_points), len(tangents))
    if point_count <= 0:
        return (), ()

    tangent_0 = _safe_normalized(tangents[0], Vector((1.0, 0.0, 0.0)))
    normal_0 = initial_normal - tangent_0 * initial_normal.dot(tangent_0)
    if normal_0.length <= 1e-8:
        normal_0 = _orthogonal_fallback(tangent_0)
    else:
        normal_0.normalize()
    binormal_0 = tangent_0.cross(normal_0)
    if binormal_0.length <= 1e-8:
        normal_0 = _orthogonal_fallback(tangent_0)
        binormal_0 = tangent_0.cross(normal_0)
    binormal_0.normalize()
    normal_0 = binormal_0.cross(tangent_0).normalized()

    normals = [normal_0]
    binormals = [binormal_0]

    for point_index in range(1, point_count):
        prev_tangent = _safe_normalized(tangents[point_index - 1], tangents[point_index])
        curr_tangent = _safe_normalized(tangents[point_index], prev_tangent)
        transported_normal = normals[-1].copy()
        axis = prev_tangent.cross(curr_tangent)
        if axis.length > 1e-8:
            dot_value = max(-1.0, min(1.0, prev_tangent.dot(curr_tangent)))
            rotation = Quaternion(axis.normalized(), math.acos(dot_value))
            transported_normal = rotation @ transported_normal

        transported_normal -= curr_tangent * transported_normal.dot(curr_tangent)
        if transported_normal.length <= 1e-8:
            transported_normal = normals[-1].copy()
            transported_normal -= curr_tangent * transported_normal.dot(curr_tangent)
        if transported_normal.length <= 1e-8:
            transported_normal = _orthogonal_fallback(curr_tangent)
        else:
            transported_normal.normalize()

        transported_binormal = curr_tangent.cross(transported_normal)
        if transported_binormal.length <= 1e-8:
            transported_normal = _orthogonal_fallback(curr_tangent)
            transported_binormal = curr_tangent.cross(transported_normal)
        transported_binormal.normalize()
        transported_normal = transported_binormal.cross(curr_tangent).normalized()

        if transported_normal.dot(normals[-1]) < 0.0:
            transported_normal.negate()
            transported_binormal.negate()

        normals.append(transported_normal)
        binormals.append(transported_binormal)

    if periodic and point_count >= 3:
        cumulative_lengths, total_length = _polyline_cumulative_lengths(spine_points)
        if total_length > 1e-8:
            end_normal_in_start_plane = _transport_vector_between_tangents(
                normals[-1],
                tangents[-1],
                tangents[0],
            )
            closure_angle = _signed_angle_around_axis(
                end_normal_in_start_plane,
                normals[0],
                tangents[0],
            )
            if abs(closure_angle) > 1e-6:
                corrected_normals = []
                corrected_binormals = []
                for point_index in range(point_count):
                    blend = cumulative_lengths[point_index] / total_length
                    tangent_dir = _safe_normalized(tangents[point_index], Vector((1.0, 0.0, 0.0)))
                    twist = Quaternion(tangent_dir, closure_angle * blend)
                    corrected_normal = twist @ normals[point_index]
                    corrected_binormal = twist @ binormals[point_index]
                    corrected_normals.append(corrected_normal.normalized())
                    corrected_binormals.append(corrected_binormal.normalized())
                normals = corrected_normals
                binormals = corrected_binormals

    return tuple(normals), tuple(binormals)


def _build_midpoint_spine_curve(
    graph: PatchGraph,
    side_a_sections: tuple[Vector, ...],
    side_b_sections: tuple[Vector, ...],
    cap_start_refs: tuple[tuple[int, int, int], ...],
    cap_end_refs: tuple[tuple[int, int, int], ...],
    sample_stations: Optional[tuple[float, ...]] = None,
) -> _SpineCurveData:
    control_points = _build_midpoint_spine_points(side_a_sections, side_b_sections)
    return _build_spine_curve_from_control_points(
        graph,
        control_points,
        side_a_sections,
        side_b_sections,
        cap_start_refs,
        cap_end_refs,
        sample_stations,
    )


def _resolve_spine_axis_from_points(
    side_a_points: tuple[Vector, ...],
    side_b_points: tuple[Vector, ...],
    basis_u: Vector,
    basis_v: Vector,
) -> FrameRole:
    if not side_a_points or not side_b_points:
        return FrameRole.H_FRAME
    start_mid = (side_a_points[0] + side_b_points[0]) * 0.5
    end_mid = (side_a_points[-1] + side_b_points[-1]) * 0.5
    chord = end_mid - start_mid
    u_comp = abs(chord.dot(basis_u))
    v_comp = abs(chord.dot(basis_v))
    return FrameRole.H_FRAME if u_comp >= v_comp else FrameRole.V_FRAME


def _canonicalize_band_orientation(
    side_a_ref: tuple[int, int, int],
    side_b_ref: tuple[int, int, int],
    side_a_points: tuple[Vector, ...],
    side_b_points: tuple[Vector, ...],
    cap_start_refs: tuple[tuple[int, int, int], ...],
    cap_end_refs: tuple[tuple[int, int, int], ...],
    side_a_reversed: bool,
    side_b_reversed: bool,
    basis_u: Vector,
    basis_v: Vector,
) -> tuple[
    tuple[int, int, int],
    tuple[int, int, int],
    tuple[Vector, ...],
    tuple[Vector, ...],
    tuple[tuple[int, int, int], ...],
    tuple[tuple[int, int, int], ...],
    bool,
    bool,
]:
    spine_axis = _resolve_spine_axis_from_points(
        side_a_points,
        side_b_points,
        basis_u,
        basis_v,
    )
    along_basis = basis_u if spine_axis == FrameRole.H_FRAME else basis_v
    start_mid = (side_a_points[0] + side_b_points[0]) * 0.5
    end_mid = (side_a_points[-1] + side_b_points[-1]) * 0.5
    if (end_mid - start_mid).dot(along_basis) < 0.0:
        side_a_points = tuple(reversed(side_a_points))
        side_b_points = tuple(reversed(side_b_points))
        cap_start_refs, cap_end_refs = cap_end_refs, cap_start_refs
        side_a_reversed = not side_a_reversed
        side_b_reversed = not side_b_reversed

    cross_basis = basis_v if spine_axis == FrameRole.H_FRAME else (-basis_u)
    side_a_cross = sum(point.dot(cross_basis) for point in side_a_points) / float(max(len(side_a_points), 1))
    side_b_cross = sum(point.dot(cross_basis) for point in side_b_points) / float(max(len(side_b_points), 1))
    if side_a_cross < side_b_cross:
        side_a_ref, side_b_ref = side_b_ref, side_a_ref
        side_a_points, side_b_points = side_b_points, side_a_points
        side_a_reversed, side_b_reversed = side_b_reversed, side_a_reversed

    return (
        side_a_ref,
        side_b_ref,
        side_a_points,
        side_b_points,
        cap_start_refs,
        cap_end_refs,
        side_a_reversed,
        side_b_reversed,
    )


def _resolve_spine_axis(chain: BoundaryChain, basis_u: Vector, basis_v: Vector) -> FrameRole:
    if len(chain.vert_cos) < 2:
        return FrameRole.H_FRAME
    chord = chain.vert_cos[-1] - chain.vert_cos[0]
    u_comp = abs(chord.dot(basis_u))
    v_comp = abs(chord.dot(basis_v))
    return FrameRole.H_FRAME if u_comp >= v_comp else FrameRole.V_FRAME


def _refs_from_indices(
    patch_id: int,
    loop_index: int,
    chain_indices: tuple[int, ...],
) -> tuple[tuple[int, int, int], ...]:
    return tuple((patch_id, loop_index, chain_index) for chain_index in chain_indices)


def _orient_side_pair(
    graph: PatchGraph,
    side_a_ref: tuple[int, int, int],
    side_b_ref: tuple[int, int, int],
    cap_path_refs: tuple[tuple[tuple[int, int, int], ...], ...],
) -> Optional[
    tuple[
        tuple[int, int, int],
        tuple[int, int, int],
        tuple[Vector, ...],
        tuple[Vector, ...],
        tuple[tuple[int, int, int], ...],
        tuple[tuple[int, int, int], ...],
        bool,
        bool,
    ]
]:
    side_a = graph.get_chain(*side_a_ref)
    side_b = graph.get_chain(*side_b_ref)
    if side_a is None or side_b is None:
        return None
    if len(side_a.vert_cos) < 2 or len(side_b.vert_cos) < 2:
        return None
    if len(cap_path_refs) != 2:
        return None

    cap_start_refs = next(
        (
            group_refs
            for group_refs in cap_path_refs
            if _group_has_corner(graph, group_refs, side_a.start_corner_index)
        ),
        (),
    )
    cap_end_refs = next(
        (
            group_refs
            for group_refs in cap_path_refs
            if _group_has_corner(graph, group_refs, side_a.end_corner_index)
        ),
        (),
    )
    if not cap_start_refs or not cap_end_refs or cap_start_refs == cap_end_refs:
        return None

    side_a_points = tuple(point.copy() for point in side_a.vert_cos)
    side_b_points = tuple(point.copy() for point in side_b.vert_cos)
    side_a_reversed = False
    side_b_reversed = False

    if _group_has_corner(graph, cap_start_refs, side_b.end_corner_index):
        side_b_points = tuple(reversed(side_b_points))
        side_b_reversed = True
    elif not _group_has_corner(graph, cap_start_refs, side_b.start_corner_index):
        start_to_start = (side_a_points[0] - side_b_points[0]).length_squared
        start_to_end = (side_a_points[0] - side_b_points[-1]).length_squared
        if start_to_end < start_to_start:
            side_b_points = tuple(reversed(side_b_points))
            side_b_reversed = True

    return (
        side_a_ref,
        side_b_ref,
        side_a_points,
        side_b_points,
        cap_start_refs,
        cap_end_refs,
        side_a_reversed,
        side_b_reversed,
    )


def _parametrize_side(
    side_points: tuple[Vector, ...],
    section_source_distances: tuple[float, ...],
    section_target_distances: tuple[float, ...],
    total_length: float,
    cap_start_width: float,
    cap_end_width: float,
    side_sign: float,
) -> tuple[tuple[float, float], ...]:
    side_distances, _ = _polyline_cumulative_lengths(side_points)
    mapped_distances = _remap_distances_to_section_profile(
        side_distances,
        section_source_distances,
        section_target_distances,
    )
    uv_targets = []
    for v_distance in mapped_distances:
        v_ratio = _clamp01(v_distance / total_length) if total_length > 1e-8 else 0.0
        half_width = 0.5 * (
            cap_start_width
            + (cap_end_width - cap_start_width) * v_ratio
        )
        uv_targets.append((side_sign * half_width, v_distance))
    return tuple(uv_targets)


def _parametrize_side_by_stations(
    side_stations: tuple[float, ...],
    section_stations: tuple[float, ...],
    section_target_distances: tuple[float, ...],
    total_length: float,
    cap_start_width: float,
    cap_end_width: float,
    side_sign: float,
) -> tuple[tuple[float, float], ...]:
    mapped_distances = _remap_stations_to_section_profile(
        side_stations,
        section_stations,
        section_target_distances,
    )
    uv_targets = []
    for v_distance in mapped_distances:
        v_ratio = _clamp01(v_distance / total_length) if total_length > 1e-8 else 0.0
        half_width = 0.5 * (
            cap_start_width
            + (cap_end_width - cap_start_width) * v_ratio
        )
        uv_targets.append((side_sign * half_width, v_distance))
    return tuple(uv_targets)


def _parametrize_cap(
    cap_chain: BoundaryChain,
    side_a_endpoint: Vector,
    side_b_endpoint: Vector,
    guide_tangent: Vector,
    v_distance: float,
    cap_width: float,
) -> tuple[tuple[float, float], ...]:
    segment = side_b_endpoint - side_a_endpoint
    segment_len_sq = segment.length_squared
    tangent_dir = guide_tangent.normalized() if guide_tangent.length > 1e-8 else Vector((0.0, 0.0, 0.0))
    uv_targets = []
    for point in cap_chain.vert_cos:
        if segment_len_sq <= 1e-12:
            side_t = 0.5
            segment_point = (side_a_endpoint + side_b_endpoint) * 0.5
        else:
            side_t = _clamp01((point - side_a_endpoint).dot(segment) / segment_len_sq)
            segment_point = side_a_endpoint.lerp(side_b_endpoint, side_t)
        u_distance = (0.5 - side_t) * cap_width
        v_offset = (point - segment_point).dot(tangent_dir) if tangent_dir.length > 1e-8 else 0.0
        uv_targets.append((u_distance, v_distance + v_offset))
    return tuple(uv_targets)


def _parametrize_cap_by_arclength(
    cap_chain: BoundaryChain,
    start_hint: Vector,
    end_hint: Vector,
    v_distance: float,
    cap_width: float,
    force_reversed: Optional[bool] = None,
) -> tuple[tuple[float, float], ...]:
    """Lay out cap UV targets by arc length along the chain.

    For BAND-style open-strip caps the two hints (side_a endpoint vs
    side_b endpoint) are distinct points, so ``_oriented_chain_points``
    picks a deterministic walking direction from them.

    For tube / cable closed-ring caps the two hints collapse to the
    single seam vertex and the hint heuristic is degenerate.  The
    layout formula ``U = 0.5*W - arc_distance`` assigns
    ``vert_cos[0] → +W/2`` and ``vert_cos[-1] → -W/2``.  Whether this
    matches side_a / side_b UV continuity depends on which side
    follows the cap in the canonical boundary loop — exactly one of
    the two caps of a tube always has the "wrong" walking direction
    and ends up UV-mirrored.  The caller resolves this by reading
    ``side_a_reversed`` (opposite signs at cap_start vs cap_end) and
    passes ``force_reversed`` to override the degenerate hint path.
    """

    if not cap_chain.vert_cos:
        return ()

    if force_reversed is not None:
        points = tuple(point.copy() for point in cap_chain.vert_cos)
        reversed_points = bool(force_reversed)
        if reversed_points:
            points = tuple(reversed(points))
    else:
        points, reversed_points = _oriented_chain_points(
            cap_chain,
            start_hint,
            end_hint,
        )
    if not points:
        return ()

    cumulative, total_length = _polyline_cumulative_lengths(points)
    if total_length <= 1e-8:
        point_count = len(points)
        if point_count <= 1:
            uv_targets = ((0.0, v_distance),)
        else:
            uv_targets = tuple(
                (0.5 * cap_width - cap_width * float(index) / float(point_count - 1), v_distance)
                for index in range(point_count)
            )
    else:
        uv_targets = tuple(
            (0.5 * cap_width - distance, v_distance)
            for distance in cumulative
        )
    return tuple(reversed(uv_targets)) if reversed_points else uv_targets


def build_canonical_4chain_band_spine(
    graph: PatchGraph,
    patch_id: int,
    loop_index: int,
    side_chain_indices: tuple[int, ...],
    cap_path_groups: tuple[tuple[int, ...], ...],
) -> Optional[BandSpineData]:
    """Unified UV builder for canonical 4-chain BAND patches.

    Handles exactly 2 side chains + 2 single-chain cap groups.  Bypasses
    the topology-heavy general path (harmonic station map, Dijkstra) but
    keeps the same universal 3D spine core:

    - Arc-length resampling of both side rails
    - Centripetal Catmull-Rom midpoint spine
    - Rotation-minimizing frame transport along the spine
    - Rigidity-weighted section distance redistribution
    - Per-vertex remap through section profile

    For curved bands (C/L-shape) long straight segments keep their UV
    proportion while short curved segments absorb compression.  For
    uniform geometry (rings, straight strips) the corrections are
    near-zero and the result is equivalent to simple midpoint + linear.
    """

    node = graph.nodes.get(patch_id)
    if node is None or loop_index < 0 or loop_index >= len(node.boundary_loops):
        return None
    if len(side_chain_indices) != 2 or len(cap_path_groups) != 2:
        return None
    if any(len(group) != 1 for group in cap_path_groups):
        return None

    side_a_ref = (patch_id, loop_index, side_chain_indices[0])
    side_b_ref = (patch_id, loop_index, side_chain_indices[1])
    cap_0_ref = (patch_id, loop_index, cap_path_groups[0][0])
    cap_1_ref = (patch_id, loop_index, cap_path_groups[1][0])

    side_a = graph.get_chain(*side_a_ref)
    side_b = graph.get_chain(*side_b_ref)
    cap_0 = graph.get_chain(*cap_0_ref)
    cap_1 = graph.get_chain(*cap_1_ref)
    if side_a is None or side_b is None or cap_0 is None or cap_1 is None:
        return None
    if len(side_a.vert_cos) < 2 or len(side_b.vert_cos) < 2:
        return None

    # ── orient: match side_a start → cap_start, side_a end → cap_end ──
    if _chain_has_corner(cap_0, side_a.start_corner_index):
        cap_start_ref, cap_end_ref = cap_0_ref, cap_1_ref
    elif _chain_has_corner(cap_1, side_a.start_corner_index):
        cap_start_ref, cap_end_ref = cap_1_ref, cap_0_ref
    else:
        d0 = (side_a.vert_cos[0] - cap_0.vert_cos[0]).length_squared
        d1 = (side_a.vert_cos[0] - cap_1.vert_cos[0]).length_squared
        if d0 <= d1:
            cap_start_ref, cap_end_ref = cap_0_ref, cap_1_ref
        else:
            cap_start_ref, cap_end_ref = cap_1_ref, cap_0_ref

    cap_start = graph.get_chain(*cap_start_ref)
    cap_end = graph.get_chain(*cap_end_ref)
    if cap_start is None or cap_end is None:
        return None

    side_a_points = tuple(v.copy() for v in side_a.vert_cos)
    side_b_points = tuple(v.copy() for v in side_b.vert_cos)
    side_a_reversed = False
    side_b_reversed = False

    if _chain_has_corner(cap_start, side_b.end_corner_index):
        side_b_points = tuple(reversed(side_b_points))
        side_b_reversed = True
    elif not _chain_has_corner(cap_start, side_b.start_corner_index):
        d_start = (side_a_points[0] - side_b_points[0]).length_squared
        d_end = (side_a_points[0] - side_b_points[-1]).length_squared
        if d_end < d_start:
            side_b_points = tuple(reversed(side_b_points))
            side_b_reversed = True

    cap_start_refs = (cap_start_ref,)
    cap_end_refs = (cap_end_ref,)

    # ── canonicalize orientation (align with basis) ──
    (
        side_a_ref, side_b_ref,
        side_a_points, side_b_points,
        cap_start_refs, cap_end_refs,
        side_a_reversed, side_b_reversed,
    ) = _canonicalize_band_orientation(
        side_a_ref, side_b_ref,
        side_a_points, side_b_points,
        cap_start_refs, cap_end_refs,
        side_a_reversed, side_b_reversed,
        node.basis_u, node.basis_v,
    )

    # Re-fetch cap chains after canonicalization (may have been swapped).
    cap_start = graph.get_chain(*cap_start_refs[0])
    cap_end = graph.get_chain(*cap_end_refs[0])
    if cap_start is None or cap_end is None:
        return None

    # ── resample both sides to uniform arc-length stations ──
    cumul_a, total_a = _polyline_cumulative_lengths(side_a_points)
    cumul_b, total_b = _polyline_cumulative_lengths(side_b_points)
    section_count = max(len(side_a_points), len(side_b_points), 4)
    stations = tuple(
        float(i) / float(section_count - 1) for i in range(section_count)
    )
    resampled_a, section_dist_a = _sample_polyline_at_stations(
        side_a_points, cumul_a, total_a, stations,
    )
    resampled_b, section_dist_b = _sample_polyline_at_stations(
        side_b_points, cumul_b, total_b, stations,
    )
    if not resampled_a or not resampled_b:
        return None

    spine_curve = _build_midpoint_spine_curve(
        graph,
        resampled_a,
        resampled_b,
        cap_start_refs,
        cap_end_refs,
        stations,
    )
    spine_points = spine_curve.points
    spine_tangents = spine_curve.tangents
    spine_normals = spine_curve.normals
    spine_binormals = spine_curve.binormals
    if not spine_points:
        return None

    # ── spine-normal re-sectioning (3D-native) ──
    # Cut sections perpendicular to the 3D spine tangent and intersect
    # with the rail polylines directly in 3D.  At a bend the outer side
    # intercepts are further apart (long delta) while inner intercepts
    # are closer (short delta), producing non-uniform section distances
    # that drive the rigidity-weighted redistribution.  Unlike the old
    # 2D-projected variant this works for BOTH in-plane bends (cones,
    # arcs in the patch plane) AND out-of-plane bends (serpentines
    # folded along the face normal), so it runs unconditionally and
    # preserves the local rail compression/expansion in every case.
    (
        _snorm_pts_a, _snorm_pts_b,
        snorm_dist_a, snorm_dist_b,
    ) = _build_spine_normal_sections(
        side_a_points,
        side_b_points,
        spine_points,
        resampled_a,
        resampled_b,
        section_dist_a,
        section_dist_b,
        spine_tangents,
    )
    if snorm_dist_a and snorm_dist_b:
        section_dist_a = snorm_dist_a
        section_dist_b = snorm_dist_b

    # ── rigidity-weighted section target distances ──
    # Long straight segments keep their UV proportion; short curved
    # segments absorb compression.  For uniform geometry the weights
    # are equal and the redistribution is a no-op.
    section_target_distances, total_spine = _build_weighted_section_target_distances(
        section_dist_a,
        section_dist_b,
        spine_points,
    )
    if not section_target_distances or total_spine <= 1e-8:
        spine_cumul, total_spine = _polyline_cumulative_lengths(spine_points)
        if total_spine <= 1e-8:
            return None
        section_target_distances = spine_cumul

    spine_cumul, _ = _polyline_cumulative_lengths(spine_points)
    spine_arc_lengths = tuple(
        d / total_spine if total_spine > 1e-8 else 0.0 for d in spine_cumul
    )

    # ── endpoint widths ──
    cap_start_width = (side_a_points[0] - side_b_points[0]).length
    cap_end_width = (side_a_points[-1] - side_b_points[-1]).length

    # ── UV targets for side chains (remap through section profile) ──
    side_a_targets = _parametrize_side(
        side_a_points, section_dist_a, section_target_distances,
        total_spine, cap_start_width, cap_end_width, side_sign=1.0,
    )
    side_b_targets = _parametrize_side(
        side_b_points, section_dist_b, section_target_distances,
        total_spine, cap_start_width, cap_end_width, side_sign=-1.0,
    )
    if side_a_reversed:
        side_a_targets = tuple(reversed(side_a_targets))
    if side_b_reversed:
        side_b_targets = tuple(reversed(side_b_targets))

    # ── UV targets for cap chains ──
    start_tangent = spine_tangents[0] if spine_tangents else _endpoint_direction(spine_points, at_start=True)
    end_tangent = spine_tangents[-1] if spine_tangents else _endpoint_direction(spine_points, at_start=False)

    cap_start_uv = _parametrize_cap(
        cap_start, side_a_points[0], side_b_points[0],
        start_tangent, 0.0, cap_start_width,
    )
    cap_end_uv = _parametrize_cap(
        cap_end, side_a_points[-1], side_b_points[-1],
        end_tangent, total_spine, cap_end_width,
    )

    chain_uv_targets = {
        side_a_ref: side_a_targets,
        side_b_ref: side_b_targets,
        cap_start_refs[0]: cap_start_uv,
        cap_end_refs[0]: cap_end_uv,
    }

    # ── spine axis: use mid-chord for robustness (handles closed rings) ──
    mid_idx = len(spine_points) // 2
    mid_chord = spine_points[mid_idx] - spine_points[0]
    u_comp = abs(mid_chord.dot(node.basis_u))
    v_comp = abs(mid_chord.dot(node.basis_v))
    if max(u_comp, v_comp) > 1e-8:
        spine_axis = FrameRole.H_FRAME if u_comp >= v_comp else FrameRole.V_FRAME
    else:
        spine_axis = _resolve_spine_axis_from_points(
            side_a_points, side_b_points, node.basis_u, node.basis_v,
        )

    return BandSpineData(
        patch_id=patch_id,
        side_a_ref=side_a_ref,
        side_b_ref=side_b_ref,
        cap_start_ref=cap_start_refs[0],
        cap_end_ref=cap_end_refs[0],
        cap_start_refs=cap_start_refs,
        cap_end_refs=cap_end_refs,
        spine_points_3d=tuple(p.copy() for p in spine_points),
        spine_tangents_3d=tuple(t.copy() for t in spine_tangents),
        spine_normals_3d=tuple(n.copy() for n in spine_normals),
        spine_binormals_3d=tuple(b.copy() for b in spine_binormals),
        spine_arc_lengths=spine_arc_lengths,
        spine_arc_length=total_spine,
        spine_is_periodic=spine_curve.periodic,
        cap_start_width=cap_start_width,
        cap_end_width=cap_end_width,
        chain_uv_targets=MappingProxyType(dict(chain_uv_targets)),
        spine_axis=spine_axis,
    )


def build_band_spine_from_groups(
    graph: PatchGraph,
    patch_id: int,
    loop_index: int,
    side_chain_indices: tuple[int, ...],
    cap_path_groups: tuple[tuple[int, ...], ...],
) -> Optional[BandSpineData]:
    """Build BAND UV targets from section-based master-rail stations."""

    node = graph.nodes.get(patch_id)
    if node is None or loop_index < 0 or loop_index >= len(node.boundary_loops):
        return None
    if len(side_chain_indices) != 2 or len(cap_path_groups) != 2:
        return None

    side_a_ref = (patch_id, loop_index, side_chain_indices[0])
    side_b_ref = (patch_id, loop_index, side_chain_indices[1])
    cap_path_refs = tuple(
        _refs_from_indices(patch_id, loop_index, group)
        for group in cap_path_groups
        if group
    )
    if len(cap_path_refs) != 2:
        return None

    oriented = _orient_side_pair(
        graph,
        side_a_ref,
        side_b_ref,
        cap_path_refs,
    )
    if oriented is None:
        return None

    (
        side_a_ref,
        side_b_ref,
        side_a_points,
        side_b_points,
        cap_start_refs,
        cap_end_refs,
        side_a_reversed,
        side_b_reversed,
    ) = oriented
    (
        side_a_ref,
        side_b_ref,
        side_a_points,
        side_b_points,
        cap_start_refs,
        cap_end_refs,
        side_a_reversed,
        side_b_reversed,
    ) = _canonicalize_band_orientation(
        side_a_ref,
        side_b_ref,
        side_a_points,
        side_b_points,
        cap_start_refs,
        cap_end_refs,
        side_a_reversed,
        side_b_reversed,
        node.basis_u,
        node.basis_v,
    )
    use_topology_station_domain = False
    side_a_stations: tuple[float, ...] = ()
    side_b_stations: tuple[float, ...] = ()
    (
        bootstrap_side_a_sections,
        bootstrap_side_b_sections,
        bootstrap_side_a_distances,
        bootstrap_side_b_distances,
        section_stations,
        side_a_stations,
        side_b_stations,
    ) = _build_topology_sections(
        graph,
        node,
        side_a_ref,
        side_b_ref,
        side_a_points,
        side_b_points,
        side_a_reversed,
        side_b_reversed,
        cap_start_refs,
        cap_end_refs,
    )
    if not bootstrap_side_a_sections:
        (
            bootstrap_side_a_sections,
            bootstrap_side_b_sections,
            bootstrap_side_a_distances,
            bootstrap_side_b_distances,
            section_stations,
        ) = _build_bootstrap_sections(
            side_a_points,
            side_b_points,
        )
    else:
        use_topology_station_domain = True
    if not bootstrap_side_a_sections or not bootstrap_side_b_sections or not section_stations:
        return None

    spine_curve = _build_midpoint_spine_curve(
        graph,
        bootstrap_side_a_sections,
        bootstrap_side_b_sections,
        cap_start_refs,
        cap_end_refs,
        section_stations,
    )
    spine_points = spine_curve.points
    spine_tangents = spine_curve.tangents
    spine_normals = spine_curve.normals
    spine_binormals = spine_curve.binormals
    if not spine_points:
        return None

    # ── spine-normal re-sectioning (3D-native) ──
    # Runs for every geometry class: in-plane bends, out-of-plane
    # serpentines, and curve-split group assemblies.  The cutting plane's
    # normal is the 3D spine tangent itself, so rail crossings are located
    # directly in 3D and reflect real local arc-distance asymmetries at
    # bends (inner rail shorter delta, outer rail longer delta).  Topology
    # stations, when present, are a stronger bootstrap than uniform
    # sampling; otherwise fall back to the resampled bootstrap sections.
    (
        side_a_sections,
        side_b_sections,
        side_a_section_distances,
        side_b_section_distances,
    ) = _build_spine_normal_sections(
        side_a_points,
        side_b_points,
        spine_points,
        bootstrap_side_a_sections,
        bootstrap_side_b_sections,
        bootstrap_side_a_distances,
        bootstrap_side_b_distances,
        spine_tangents,
    )
    if not side_a_sections or not side_b_sections:
        return None

    topology_target_total = None
    if use_topology_station_domain:
        topology_target_total = 0.5 * (
            side_a_section_distances[-1]
            + side_b_section_distances[-1]
        )

    section_target_distances, total_arc_length = _build_weighted_section_target_distances(
        side_a_section_distances,
        side_b_section_distances,
        spine_points,
        target_total_override=topology_target_total,
    )
    if not section_target_distances:
        return None
    spine_arc_lengths = _distances_to_normalized_stations(
        section_target_distances,
        total_arc_length,
    )
    if not spine_arc_lengths:
        return None
    start_tangent = spine_tangents[0] if spine_tangents else _endpoint_direction(spine_points, at_start=True)
    end_tangent = spine_tangents[-1] if spine_tangents else _endpoint_direction(spine_points, at_start=False)

    cap_start_width = (side_a_points[0] - side_b_points[0]).length
    cap_end_width = (side_a_points[-1] - side_b_points[-1]).length

    side_a_chain = graph.get_chain(*side_a_ref)
    side_b_chain = graph.get_chain(*side_b_ref)
    if side_a_chain is None or side_b_chain is None:
        return None

    if use_topology_station_domain:
        side_a_targets = _parametrize_side_by_stations(
            side_a_stations,
            section_stations,
            section_target_distances,
            total_arc_length,
            cap_start_width,
            cap_end_width,
            side_sign=1.0,
        )
    else:
        side_a_targets = _parametrize_side(
            side_a_points,
            side_a_section_distances,
            section_target_distances,
            total_arc_length,
            cap_start_width,
            cap_end_width,
            side_sign=1.0,
        )
    if side_a_reversed:
        side_a_targets = tuple(reversed(side_a_targets))
    if use_topology_station_domain:
        side_b_targets = _parametrize_side_by_stations(
            side_b_stations,
            section_stations,
            section_target_distances,
            total_arc_length,
            cap_start_width,
            cap_end_width,
            side_sign=-1.0,
        )
    else:
        side_b_targets = _parametrize_side(
            side_b_points,
            side_b_section_distances,
            section_target_distances,
            total_arc_length,
            cap_start_width,
            cap_end_width,
            side_sign=-1.0,
        )
    if side_b_reversed:
        side_b_targets = tuple(reversed(side_b_targets))

    chain_uv_targets = {
        side_a_ref: side_a_targets,
        side_b_ref: side_b_targets,
    }

    for cap_ref in cap_start_refs:
        cap_chain = graph.get_chain(*cap_ref)
        if cap_chain is None:
            return None
        chain_uv_targets[cap_ref] = _parametrize_cap(
            cap_chain,
            side_a_points[0],
            side_b_points[0],
            start_tangent,
            0.0,
            cap_start_width,
        )

    for cap_ref in cap_end_refs:
        cap_chain = graph.get_chain(*cap_ref)
        if cap_chain is None:
            return None
        chain_uv_targets[cap_ref] = _parametrize_cap(
            cap_chain,
            side_a_points[-1],
            side_b_points[-1],
            end_tangent,
            total_arc_length,
            cap_end_width,
        )

    return BandSpineData(
        patch_id=patch_id,
        side_a_ref=side_a_ref,
        side_b_ref=side_b_ref,
        cap_start_ref=cap_start_refs[0],
        cap_end_ref=cap_end_refs[0],
        cap_start_refs=cap_start_refs,
        cap_end_refs=cap_end_refs,
        spine_points_3d=tuple(point.copy() for point in spine_points),
        spine_tangents_3d=tuple(tangent.copy() for tangent in spine_tangents),
        spine_normals_3d=tuple(normal.copy() for normal in spine_normals),
        spine_binormals_3d=tuple(binormal.copy() for binormal in spine_binormals),
        spine_arc_lengths=spine_arc_lengths,
        spine_arc_length=total_arc_length,
        spine_is_periodic=spine_curve.periodic,
        cap_start_width=cap_start_width,
        cap_end_width=cap_end_width,
        chain_uv_targets=MappingProxyType(dict(chain_uv_targets)),
        spine_axis=_resolve_spine_axis(side_a_chain, node.basis_u, node.basis_v),
    )


def build_canonical_4chain_tube_spine(
    graph: PatchGraph,
    patch_id: int,
    loop_index: int,
    side_chain_indices: tuple[int, ...],
    cap_path_groups: tuple[tuple[int, ...], ...],
) -> Optional[BandSpineData]:
    """Build centerline-driven UV targets for canonical tube/cable patches.

    Unlike BAND, the runtime spine does not live on the surface rails.  It is
    reconstructed from station isosection centroids through the patch interior,
    so the resulting curve follows the center of each cross-section.
    """

    node = graph.nodes.get(patch_id)
    if node is None or loop_index < 0 or loop_index >= len(node.boundary_loops):
        return None
    if len(side_chain_indices) != 2 or len(cap_path_groups) != 2:
        return None
    if any(len(group) != 1 for group in cap_path_groups):
        return None

    side_a_ref = (patch_id, loop_index, side_chain_indices[0])
    side_b_ref = (patch_id, loop_index, side_chain_indices[1])
    cap_path_refs = tuple(
        _refs_from_indices(patch_id, loop_index, group)
        for group in cap_path_groups
        if group
    )
    if len(cap_path_refs) != 2:
        return None

    oriented = _orient_side_pair(
        graph,
        side_a_ref,
        side_b_ref,
        cap_path_refs,
    )
    if oriented is None:
        return None

    (
        side_a_ref,
        side_b_ref,
        side_a_points,
        side_b_points,
        cap_start_refs,
        cap_end_refs,
        side_a_reversed,
        side_b_reversed,
    ) = oriented
    (
        side_a_ref,
        side_b_ref,
        side_a_points,
        side_b_points,
        cap_start_refs,
        cap_end_refs,
        side_a_reversed,
        side_b_reversed,
    ) = _canonicalize_band_orientation(
        side_a_ref,
        side_b_ref,
        side_a_points,
        side_b_points,
        cap_start_refs,
        cap_end_refs,
        side_a_reversed,
        side_b_reversed,
        node.basis_u,
        node.basis_v,
    )

    (
        side_a_sections,
        side_b_sections,
        _side_a_section_distances,
        _side_b_section_distances,
        section_stations,
        side_a_stations,
        side_b_stations,
    ) = _build_topology_sections(
        graph,
        node,
        side_a_ref,
        side_b_ref,
        side_a_points,
        side_b_points,
        side_a_reversed,
        side_b_reversed,
        cap_start_refs,
        cap_end_refs,
    )
    if not side_a_sections or not side_b_sections or not section_stations:
        return None

    centerline_points = _build_station_centerline_points(
        graph,
        node,
        cap_start_refs,
        cap_end_refs,
        section_stations,
    )
    if len(centerline_points) != len(section_stations):
        return None

    spine_curve = _build_spine_curve_from_control_points(
        graph,
        centerline_points,
        side_a_sections,
        side_b_sections,
        cap_start_refs,
        cap_end_refs,
        section_stations,
    )
    spine_points = spine_curve.points
    spine_tangents = spine_curve.tangents
    spine_normals = spine_curve.normals
    spine_binormals = spine_curve.binormals
    if not spine_points:
        return None

    section_target_distances, total_arc_length = _polyline_cumulative_lengths(spine_points)
    if total_arc_length <= 1e-8 or len(section_target_distances) != len(section_stations):
        return None
    spine_arc_lengths = _distances_to_normalized_stations(
        section_target_distances,
        total_arc_length,
    )
    if not spine_arc_lengths:
        return None

    cap_start_width = _chain_group_length(graph, cap_start_refs)
    cap_end_width = _chain_group_length(graph, cap_end_refs)
    if cap_start_width <= 1e-8 or cap_end_width <= 1e-8:
        return None

    side_a_targets = _parametrize_side_by_stations(
        side_a_stations,
        section_stations,
        section_target_distances,
        total_arc_length,
        cap_start_width,
        cap_end_width,
        side_sign=1.0,
    )
    side_b_targets = _parametrize_side_by_stations(
        side_b_stations,
        section_stations,
        section_target_distances,
        total_arc_length,
        cap_start_width,
        cap_end_width,
        side_sign=-1.0,
    )
    if side_a_reversed:
        side_a_targets = tuple(reversed(side_a_targets))
    if side_b_reversed:
        side_b_targets = tuple(reversed(side_b_targets))

    cap_start = graph.get_chain(*cap_start_refs[0])
    cap_end = graph.get_chain(*cap_end_refs[0])
    if cap_start is None or cap_end is None:
        return None

    # Closed-ring cap winding fix.  For canonical tube boundary loop
    # [cap_start, sideX, cap_end, sideY], sideX is side_a when
    # side_a_reversed=False (side_a's natural direction is
    # cap_start → cap_end), else sideX is side_b.  The default layout
    # formula ``U = +W/2 - arc_distance`` gives ``vert_cos[-1].U = -W/2``
    # — correct only when sideX = side_b (U_sign = -1).  So at cap_start
    # we force-reverse when side_a_reversed=False (sideX = side_a,
    # U_sign = +1).  At cap_end the roles swap: sideY is the
    # "follower" of cap_end, sideY = side_a iff side_a_reversed=True,
    # so we force-reverse cap_end when side_a_reversed=True.  Exactly
    # one of the two caps ends up reversed, matching the observed
    # symptom "one cap mirrored".  Open-strip BAND caps are not
    # closed rings; they fall through to the hint-based path.
    cap_start_is_ring = _is_closed_ring(tuple(cap_start.vert_cos))
    cap_end_is_ring = _is_closed_ring(tuple(cap_end.vert_cos))
    cap_start_force_reverse: Optional[bool] = (
        (not side_a_reversed) if cap_start_is_ring else None
    )
    cap_end_force_reverse: Optional[bool] = (
        bool(side_a_reversed) if cap_end_is_ring else None
    )

    cap_start_uv = _parametrize_cap_by_arclength(
        cap_start,
        side_a_points[0],
        side_b_points[0],
        0.0,
        cap_start_width,
        force_reversed=cap_start_force_reverse,
    )
    cap_end_uv = _parametrize_cap_by_arclength(
        cap_end,
        side_a_points[-1],
        side_b_points[-1],
        total_arc_length,
        cap_end_width,
        force_reversed=cap_end_force_reverse,
    )
    if not cap_start_uv or not cap_end_uv:
        return None

    spine_axis = _resolve_spine_axis_from_points(
        centerline_points,
        centerline_points,
        node.basis_u,
        node.basis_v,
    )

    return BandSpineData(
        patch_id=patch_id,
        side_a_ref=side_a_ref,
        side_b_ref=side_b_ref,
        cap_start_ref=cap_start_refs[0],
        cap_end_ref=cap_end_refs[0],
        cap_start_refs=cap_start_refs,
        cap_end_refs=cap_end_refs,
        spine_points_3d=tuple(point.copy() for point in spine_points),
        spine_tangents_3d=tuple(tangent.copy() for tangent in spine_tangents),
        spine_normals_3d=tuple(normal.copy() for normal in spine_normals),
        spine_binormals_3d=tuple(binormal.copy() for binormal in spine_binormals),
        spine_arc_lengths=spine_arc_lengths,
        spine_arc_length=total_arc_length,
        spine_is_periodic=spine_curve.periodic,
        cap_start_width=cap_start_width,
        cap_end_width=cap_end_width,
        chain_uv_targets=MappingProxyType(
            {
                side_a_ref: side_a_targets,
                side_b_ref: side_b_targets,
                cap_start_refs[0]: cap_start_uv,
                cap_end_refs[0]: cap_end_uv,
            }
        ),
        spine_axis=spine_axis,
    )
