"""Per PatchChain-use display offset for the debug overlay.

A use walks its loop the way its patch's faces wind (G0 DD-51). So for a use
edge a -> b the owning face is the patch face whose vertex cycle contains
a -> b in that order, and the side of the use is left of the edge for that
face's own winding: inward = normalize(cross(face normal, b - a)). Both uses
of a SEAM_SELF chain therefore land on their own faces without any flip.
For an n-gon the Layer 2 face-fan normals of the patch at a and b stand in
for its (possibly non-planar) face normal.

If no patch face contains a -> b, the edge falls back to the old rule (the
single patch face holding the edge, towards its centroid) and is reported.
Display only: nothing here is a Scaffold relation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from scaffold_core.layer_2_geometry.measures import cross, dot, length, normalize, subtract


RAIL_OFFSET_FACTOR = 0.012  # inward, x the local average edge length of the stroke
RAIL_NORMAL_HOVER_FACTOR = 0.016  # lift, x the mesh's median edge length
NGON_MIN_VERTICES = 5


@dataclass(frozen=True)
class SideIndex:
    """Read-only lookups for the winding rule over the source mesh."""

    faces_by_directed_edge: Mapping[tuple[str, str, str], tuple[str, ...]]
    faces_by_edge: Mapping[tuple[str, frozenset], tuple[str, ...]]
    face_vertices: Mapping[str, tuple[str, ...]]
    position: Mapping[str, tuple[float, float, float]]
    fan_normal: Mapping[tuple[str, str], tuple[float, float, float]]


@dataclass(frozen=True)
class EdgeSide:
    inward: tuple[float, float, float]
    normal: tuple[float, float, float]
    face_id: str
    fallback: bool


def build_side_index(topology: Any, source: Any, fan_normal: Mapping[tuple[str, str], tuple]) -> SideIndex:
    directed: dict[tuple[str, str, str], list[str]] = {}
    undirected: dict[tuple[str, frozenset], list[str]] = {}
    face_vertices: dict[str, tuple[str, ...]] = {}
    for patch_id, patch in topology.patches.items():
        for face_id in patch.source_face_ids:
            face = source.faces.get(face_id)
            if face is None:
                continue
            cycle = tuple(str(vertex_id) for vertex_id in face.vertex_ids)
            face_vertices[str(face_id)] = cycle
            for index, a in enumerate(cycle):
                b = cycle[(index + 1) % len(cycle)]
                directed.setdefault((str(patch_id), a, b), []).append(str(face_id))
                undirected.setdefault((str(patch_id), frozenset((a, b))), []).append(str(face_id))
    return SideIndex(
        faces_by_directed_edge={key: tuple(value) for key, value in directed.items()},
        faces_by_edge={key: tuple(value) for key, value in undirected.items()},
        face_vertices=face_vertices,
        position={
            str(vertex_id): tuple(float(value) for value in vertex.position)
            for vertex_id, vertex in source.vertices.items()
        },
        fan_normal=dict(fan_normal),
    )


def face_normal(index: SideIndex, face_id: str) -> tuple[float, float, float]:
    """Newell normal of a source face, following its own winding."""

    points = [index.position[vertex_id] for vertex_id in index.face_vertices.get(face_id, ()) if vertex_id in index.position]
    total = [0.0, 0.0, 0.0]
    for current, following in zip(points, points[1:] + points[:1]):
        total[0] += (current[1] - following[1]) * (current[2] + following[2])
        total[1] += (current[2] - following[2]) * (current[0] + following[0])
        total[2] += (current[0] - following[0]) * (current[1] + following[1])
    return _unit(tuple(total))


def edge_side(index: SideIndex, patch_id: str, a: str, b: str) -> EdgeSide | None:
    """The owning face and inward direction of use edge a -> b in patch_id."""

    if a not in index.position or b not in index.position:
        return None
    edge = subtract(index.position[b], index.position[a])
    if length(edge) <= 0.0:
        return None
    faces = index.faces_by_directed_edge.get((patch_id, a, b))
    if faces:
        face_id = faces[0]
        normal = _owning_normal(index, patch_id, face_id, a, b)
        inward = _unit(cross(normal, edge))
        if length(inward) <= 0.0:
            return None
        return EdgeSide(inward, normal, face_id, False)
    faces = index.faces_by_edge.get((patch_id, frozenset((a, b))), ())
    if len(faces) != 1:
        return None
    face_id = faces[0]
    centroid = _mean([index.position[vertex_id] for vertex_id in index.face_vertices[face_id]])
    midpoint = _mean([index.position[a], index.position[b]])
    axis = _unit(edge)
    toward = subtract(centroid, midpoint)
    inward = _unit(subtract(toward, tuple(value * dot(toward, axis) for value in axis)))
    if length(inward) <= 0.0:
        return None
    return EdgeSide(inward, face_normal(index, face_id), face_id, True)


def offset_use_polyline(
    index: SideIndex,
    patch_id: str,
    vertex_ids: tuple[str, ...],
    points: tuple[tuple[float, float, float], ...],
    *,
    lift: float,
):
    """Offset each point inward (RAIL_OFFSET_FACTOR x local edge length) and up by lift.

    vertex_ids and points follow the use direction. A point takes the mean
    inward direction and normal of its one or two edges. Returns the polyline
    and a record; the record keeps the keys earlier callers read.
    """

    sides = [edge_side(index, patch_id, a, b) for a, b in zip(vertex_ids, vertex_ids[1:])]
    lengths = [length(subtract(second, first)) for first, second in zip(points, points[1:])]
    local = sum(lengths) / len(lengths) if lengths else 0.0
    inward_magnitude = local * RAIL_OFFSET_FACTOR
    offsets = []
    for point_index in range(len(points)):
        adjacent = [
            sides[edge_index]
            for edge_index in (point_index - 1, point_index)
            if 0 <= edge_index < len(sides) and sides[edge_index] is not None
        ]
        inward = _unit(_sum([side.inward for side in adjacent])) if adjacent else (0.0, 0.0, 0.0)
        normal = _unit(_sum([side.normal for side in adjacent])) if adjacent else (0.0, 0.0, 0.0)
        offsets.append(tuple(inward[k] * inward_magnitude + normal[k] * lift for k in range(3)))
    polyline = tuple(tuple(point[k] + offset[k] for k in range(3)) for point, offset in zip(points, offsets))
    drawn = [side for side in sides if side is not None]
    record = {
        "patch_id": patch_id,
        "vertex_ids": list(vertex_ids),
        "offset_vectors": [list(offset) for offset in offsets],
        "offset_vector": list(_mean(offsets)) if offsets else [0.0, 0.0, 0.0],
        "normal_hover_direction": list(_unit(_sum([side.normal for side in drawn]))) if drawn else [0.0, 0.0, 0.0],
        "owning_face_ids": [side.face_id if side is not None else None for side in sides],
        "fallback_edges": [
            (a, b) for (a, b), side in zip(zip(vertex_ids, vertex_ids[1:]), sides) if side is not None and side.fallback
        ],
        "unoffset": len(drawn) != len(sides) or not sides,
    }
    return polyline, record


def _owning_normal(index: SideIndex, patch_id: str, face_id: str, a: str, b: str):
    if len(index.face_vertices.get(face_id, ())) >= NGON_MIN_VERTICES:
        fans = [index.fan_normal.get((patch_id, vertex_id)) for vertex_id in (a, b)]
        if all(fan is not None and length(fan) > 0.0 for fan in fans):
            normal = _unit(_sum(fans))
            if length(normal) > 0.0:
                return normal
    return face_normal(index, face_id)


def _unit(vector):
    return normalize(vector) if length(vector) > 0.0 else (0.0, 0.0, 0.0)


def _sum(vectors):
    return (
        sum(vector[0] for vector in vectors),
        sum(vector[1] for vector in vectors),
        sum(vector[2] for vector in vectors),
    )


def _mean(points):
    total = _sum(points)
    return (total[0] / len(points), total[1] / len(points), total[2] / len(points))
