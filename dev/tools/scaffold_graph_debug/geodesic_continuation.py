"""Debug-side geodesic continuation checks for overlay rail views."""

from __future__ import annotations

from collections.abc import Iterable
from math import pi
from typing import Any

from scaffold_core.layer_2_geometry.measures import angle_between, subtract


GEODESIC_STRAIGHT_TOLERANCE = 0.1


def is_geodesic_straight_at_patch_vertex(
    source: Any,
    geometry: Any,
    *,
    patch_id: str,
    source_vertex_id: str | None,
    topology_vertex_ids: Iterable[str],
    tolerance: float = GEODESIC_STRAIGHT_TOLERANCE,
) -> tuple[bool, str | None]:
    """Return whether the patch-local face fan is straight at the vertex."""

    if source is None:
        return False, "missing source snapshot for patch-local geodesic angle"
    if source_vertex_id is None:
        return False, "missing source vertex id for patch-local geodesic angle"
    angles = _patch_local_angle_sums(
        source,
        geometry,
        patch_id=patch_id,
        source_vertex_id=source_vertex_id,
        topology_vertex_ids=tuple(topology_vertex_ids),
    )
    if not angles:
        return False, f"missing patch-local face-fan angle for {patch_id}:{source_vertex_id}"
    if any(abs(angle - pi) <= tolerance for angle in angles):
        return True, None
    return False, None


def _patch_local_angle_sums(
    source: Any,
    geometry: Any,
    *,
    patch_id: str,
    source_vertex_id: str,
    topology_vertex_ids: tuple[str, ...],
) -> tuple[float, ...]:
    topology_vertex_id_set = set(topology_vertex_ids)
    fans = tuple(
        fan
        for fan in getattr(geometry, "local_face_fan_facts", {}).values()
        if str(fan.patch_id) == patch_id and str(fan.source_vertex_id) == source_vertex_id
    )
    if topology_vertex_id_set:
        matching_fans = tuple(
            fan
            for fan in fans
            if str(fan.vertex_id) in topology_vertex_id_set
        )
        if matching_fans:
            fans = matching_fans
    return tuple(
        angle_sum
        for fan in fans
        for angle_sum in (_source_vertex_angle_sum(source, source_vertex_id, fan.source_face_ids),)
        if angle_sum is not None
    )


def _source_vertex_angle_sum(
    source: Any,
    source_vertex_id: str,
    source_face_ids: tuple[Any, ...],
) -> float | None:
    total = 0.0
    found = False
    source_vertex_key = _source_key(source_vertex_id)
    for source_face_id in source_face_ids:
        face = source.faces.get(source_face_id)
        if face is None:
            continue
        vertex_ids = tuple(face.vertex_ids)
        for index, vertex_id in enumerate(vertex_ids):
            if _source_key(vertex_id) != source_vertex_key:
                continue
            point = _source_position(source, vertex_id)
            previous_point = _source_position(source, vertex_ids[index - 1])
            next_point = _source_position(source, vertex_ids[(index + 1) % len(vertex_ids)])
            if point is None or previous_point is None or next_point is None:
                continue
            total += angle_between(
                subtract(previous_point, point),
                subtract(next_point, point),
            )
            found = True
    return total if found else None


def _source_position(source: Any, source_vertex_id: Any) -> tuple[float, float, float] | None:
    vertex = source.vertices.get(source_vertex_id)
    if vertex is None:
        return None
    return tuple(float(value) for value in vertex.position)


def _source_key(source_vertex_id: Any) -> str:
    return str(source_vertex_id)
