"""
Layer: 2 - Geometry

Rules:
- Build raw geometry facts from Layer 0 source and Layer 1 topology.
- Do not build or mutate topology.
- Do not derive relations, semantic roles, features, or solve data.
"""

from __future__ import annotations

from scaffold_core.core.diagnostics import Diagnostic, DiagnosticSeverity
from collections import defaultdict

from scaffold_core.ids import PatchId, SourceEdgeId, SourceFaceId, SourceVertexId, VertexId
from scaffold_core.layer_0_source.marks import SourceMarkKind
from scaffold_core.layer_0_source.snapshot import SourceMeshSnapshot
from scaffold_core.layer_1_topology.model import Chain, Patch, SurfaceModel, Vertex
from scaffold_core.layer_2_geometry.facts import (
    ChainGeometryFacts,
    ChainSegmentGeometryFacts,
    ChainShapeHint,
    GeometryFactSnapshot,
    PatchGeometryFacts,
    Vector3,
    VertexFanGeometryFacts,
    VertexGeometryFacts,
)
from scaffold_core.layer_2_geometry.measures import (
    EPSILON,
    add,
    average,
    dot,
    length,
    normalize,
    scale,
    subtract,
    triangle_area_normal_centroid,
)


STRAIGHTNESS_TOLERANCE = 1.0e-6
SAWTOOTH_DETOUR_RATIO = 1.02


def build_geometry_facts(
    source: SourceMeshSnapshot,
    topology: SurfaceModel,
) -> GeometryFactSnapshot:
    """Build raw G2 geometry facts for a topology snapshot."""

    diagnostics: list[Diagnostic] = []
    patch_facts = {
        patch.id: _build_patch_geometry_facts(source, patch, diagnostics)
        for patch in topology.patches.values()
    }
    chain_facts = {
        chain.id: _build_chain_geometry_facts(source, topology, chain, diagnostics)
        for chain in topology.chains.values()
    }
    vertex_facts = {
        vertex.id: _build_vertex_geometry_facts(source, vertex, diagnostics)
        for vertex in topology.vertices.values()
    }
    vertex_fan_facts = _build_vertex_fan_geometry_facts(source, topology)
    return GeometryFactSnapshot(
        patch_facts=patch_facts,
        chain_facts=chain_facts,
        vertex_facts=vertex_facts,
        vertex_fan_facts=vertex_fan_facts,
        diagnostics=tuple(diagnostics),
    )


def _build_patch_geometry_facts(
    source: SourceMeshSnapshot,
    patch: Patch,
    diagnostics: list[Diagnostic],
) -> PatchGeometryFacts:
    total_area = 0.0
    normal_accumulator = (0.0, 0.0, 0.0)
    centroid_accumulator = (0.0, 0.0, 0.0)
    fallback_points: list[Vector3] = []

    for source_face_id in patch.source_face_ids:
        face_points = _face_points(source, source_face_id)
        fallback_points.extend(face_points)
        if len(face_points) < 3:
            continue
        first = face_points[0]
        for index in range(1, len(face_points) - 1):
            area, area_vector, triangle_centroid = triangle_area_normal_centroid(
                first,
                face_points[index],
                face_points[index + 1],
            )
            total_area += area
            normal_accumulator = add(normal_accumulator, area_vector)
            centroid_accumulator = add(centroid_accumulator, scale(triangle_centroid, area))

    if total_area <= EPSILON:
        diagnostics.append(
            Diagnostic(
                code="GEOMETRY_PATCH_DEGENERATE_AREA",
                severity=DiagnosticSeverity.DEGRADED,
                message="Patch has zero or near-zero measured area.",
                source="layer_2_geometry.build.build_geometry_facts",
                entity_ids=(str(patch.id),),
                evidence={"area": total_area},
            )
        )
        return PatchGeometryFacts(
            patch_id=patch.id,
            area=0.0,
            normal=(0.0, 0.0, 0.0),
            centroid=average(tuple(fallback_points)),
        )

    return PatchGeometryFacts(
        patch_id=patch.id,
        area=total_area,
        normal=normalize(normal_accumulator),
        centroid=scale(centroid_accumulator, 1.0 / total_area),
    )


def _build_chain_geometry_facts(
    source: SourceMeshSnapshot,
    topology: SurfaceModel,
    chain: Chain,
    diagnostics: list[Diagnostic],
) -> ChainGeometryFacts:
    source_vertex_run, source_segment_vertex_ids = _source_vertex_run_for_chain(
        source,
        chain,
        diagnostics,
    )
    segments = tuple(
        _build_chain_segment_geometry_facts(
            source,
            chain,
            segment_index,
            source_edge_id,
            start_source_vertex_id,
            end_source_vertex_id,
        )
        for segment_index, (source_edge_id, start_source_vertex_id, end_source_vertex_id)
        in enumerate(source_segment_vertex_ids)
    )
    length_total = sum(segment.length for segment in segments)
    segment_vectors = [segment.vector for segment in segments]

    start_point = _topology_vertex_point(source, topology.vertices[chain.start_vertex_id])
    end_point = _topology_vertex_point(source, topology.vertices[chain.end_vertex_id])
    chord = subtract(end_point, start_point)
    chord_length = length(chord)
    chord_direction = normalize(chord)
    straightness = chord_length / length_total if length_total > EPSILON else 0.0
    detour_ratio = length_total / chord_length if chord_length > EPSILON else 0.0
    shape_hint = _chain_shape_hint(
        length_total,
        chord_length,
        detour_ratio,
        segment_vectors,
        chord_direction,
    )

    if length_total <= EPSILON:
        diagnostics.append(
            Diagnostic(
                code="GEOMETRY_CHAIN_ZERO_LENGTH",
                severity=DiagnosticSeverity.DEGRADED,
                message="Chain has zero or near-zero measured length.",
                source="layer_2_geometry.build.build_geometry_facts",
                entity_ids=(str(chain.id),),
                evidence={"length": length_total},
            )
        )

    return ChainGeometryFacts(
        chain_id=chain.id,
        length=length_total,
        chord_length=chord_length,
        chord_direction=chord_direction,
        straightness=straightness,
        detour_ratio=detour_ratio,
        shape_hint=shape_hint,
        source_vertex_run=source_vertex_run,
        segments=segments,
    )


def _source_vertex_run_for_chain(
    source: SourceMeshSnapshot,
    chain: Chain,
    diagnostics: list[Diagnostic],
) -> tuple[tuple[SourceVertexId, ...], tuple[tuple[SourceEdgeId, SourceVertexId, SourceVertexId], ...]]:
    if not chain.source_edge_ids:
        return (), ()

    first_edge = source.edges[chain.source_edge_ids[0]]
    attempts = (
        (first_edge.vertex_ids[0], first_edge.vertex_ids[1]),
        (first_edge.vertex_ids[1], first_edge.vertex_ids[0]),
    )
    for first_start_vertex_id, first_end_vertex_id in attempts:
        run = [first_start_vertex_id, first_end_vertex_id]
        segment_vertex_ids = [
            (chain.source_edge_ids[0], first_start_vertex_id, first_end_vertex_id)
        ]
        for source_edge_id in chain.source_edge_ids[1:]:
            edge = source.edges[source_edge_id]
            if edge.vertex_ids[0] == run[-1]:
                start_vertex_id = edge.vertex_ids[0]
                end_vertex_id = edge.vertex_ids[1]
            elif edge.vertex_ids[1] == run[-1]:
                start_vertex_id = edge.vertex_ids[1]
                end_vertex_id = edge.vertex_ids[0]
            else:
                break
            run.append(end_vertex_id)
            segment_vertex_ids.append((source_edge_id, start_vertex_id, end_vertex_id))
        else:
            return tuple(run), tuple(segment_vertex_ids)

    diagnostics.append(
        Diagnostic(
            code="GEOMETRY_CHAIN_SEGMENT_ORDER_DEGRADED",
            severity=DiagnosticSeverity.DEGRADED,
            message="Chain source edges could not be reconstructed as one continuous vertex run.",
            source="layer_2_geometry.build.build_geometry_facts",
            entity_ids=(str(chain.id),),
            evidence={
                "source_edge_ids": tuple(str(source_edge_id) for source_edge_id in chain.source_edge_ids),
            },
        )
    )
    fallback_segments = tuple(
        (
            source_edge_id,
            source.edges[source_edge_id].vertex_ids[0],
            source.edges[source_edge_id].vertex_ids[1],
        )
        for source_edge_id in chain.source_edge_ids
    )
    fallback_run: list[SourceVertexId] = []
    for _, start_vertex_id, end_vertex_id in fallback_segments:
        if not fallback_run:
            fallback_run.extend((start_vertex_id, end_vertex_id))
        else:
            fallback_run.extend((start_vertex_id, end_vertex_id))
    return tuple(fallback_run), fallback_segments


def _build_chain_segment_geometry_facts(
    source: SourceMeshSnapshot,
    chain: Chain,
    segment_index: int,
    source_edge_id: SourceEdgeId,
    start_source_vertex_id: SourceVertexId,
    end_source_vertex_id: SourceVertexId,
) -> ChainSegmentGeometryFacts:
    start = _source_vertex_point(source, start_source_vertex_id)
    end = _source_vertex_point(source, end_source_vertex_id)
    segment = subtract(end, start)
    segment_length = length(segment)
    return ChainSegmentGeometryFacts(
        chain_id=chain.id,
        source_edge_id=source_edge_id,
        segment_index=segment_index,
        start_source_vertex_id=start_source_vertex_id,
        end_source_vertex_id=end_source_vertex_id,
        start_position=start,
        end_position=end,
        vector=segment,
        length=segment_length,
        direction=normalize(segment),
    )


def _chain_shape_hint(
    length_total: float,
    chord_length: float,
    detour_ratio: float,
    segment_vectors: list[Vector3],
    chord_direction: Vector3,
) -> ChainShapeHint:
    if length_total <= EPSILON or chord_length <= EPSILON:
        return ChainShapeHint.UNKNOWN
    if abs(1.0 - (chord_length / length_total)) <= STRAIGHTNESS_TOLERANCE:
        return ChainShapeHint.STRAIGHT
    if detour_ratio >= SAWTOOTH_DETOUR_RATIO and _segments_advance_along_chord(
        segment_vectors,
        chord_direction,
    ):
        return ChainShapeHint.SAWTOOTH_STRAIGHT
    return ChainShapeHint.UNKNOWN


def _segments_advance_along_chord(
    segment_vectors: list[Vector3],
    chord_direction: Vector3,
) -> bool:
    return all(dot(segment, chord_direction) > EPSILON for segment in segment_vectors)


def _build_vertex_geometry_facts(
    source: SourceMeshSnapshot,
    vertex: Vertex,
    diagnostics: list[Diagnostic],
) -> VertexGeometryFacts:
    points = tuple(_source_vertex_point(source, source_vertex_id) for source_vertex_id in vertex.source_vertex_ids)
    if not points:
        diagnostics.append(
            Diagnostic(
                code="GEOMETRY_VERTEX_MISSING_SOURCE",
                severity=DiagnosticSeverity.DEGRADED,
                message="Topology Vertex has no source vertex reference.",
                source="layer_2_geometry.build.build_geometry_facts",
                entity_ids=(str(vertex.id),),
            )
        )
    return VertexGeometryFacts(vertex_id=vertex.id, position=average(points))


def _build_vertex_fan_geometry_facts(
    source: SourceMeshSnapshot,
    topology: SurfaceModel,
) -> dict[str, VertexFanGeometryFacts]:
    face_to_patch_id = {
        source_face_id: patch.id
        for patch in topology.patches.values()
        for source_face_id in patch.source_face_ids
    }
    selected_face_ids = tuple(face_to_patch_id)
    edge_incidence = _selected_edge_incidence(source, selected_face_ids)
    boundary_mark_edge_ids = _marked_patch_boundary_edge_ids(source)

    facts: dict[str, VertexFanGeometryFacts] = {}
    for patch in topology.patches.values():
        faces_by_vertex: dict[SourceVertexId, list[SourceFaceId]] = defaultdict(list)
        for source_face_id in patch.source_face_ids:
            for source_vertex_id in source.faces[source_face_id].vertex_ids:
                faces_by_vertex[source_vertex_id].append(source_face_id)

        for source_vertex_id, source_face_ids in faces_by_vertex.items():
            components = _source_vertex_face_components(
                source,
                patch.id,
                source_vertex_id,
                tuple(source_face_ids),
                face_to_patch_id,
                edge_incidence,
                boundary_mark_edge_ids,
            )
            for component_index, component_face_ids in enumerate(components):
                vertex_id = _vertex_id_for_fan_component(
                    topology,
                    patch.id,
                    source_vertex_id,
                    component_index,
                    len(components),
                )
                area, normal = _face_fan_area_normal(source, component_face_ids)
                fan_id = f"vertex_fan:{patch.id}:{vertex_id}"
                facts[fan_id] = VertexFanGeometryFacts(
                    id=fan_id,
                    patch_id=patch.id,
                    vertex_id=vertex_id,
                    source_vertex_id=source_vertex_id,
                    source_face_ids=component_face_ids,
                    area=area,
                    normal=normal,
                )

    return facts


def _source_vertex_face_components(
    source: SourceMeshSnapshot,
    patch_id: PatchId,
    source_vertex_id: SourceVertexId,
    source_face_ids: tuple[SourceFaceId, ...],
    face_to_patch_id: dict[SourceFaceId, PatchId],
    edge_incidence: dict[SourceEdgeId, tuple[SourceFaceId, ...]],
    boundary_mark_edge_ids: set[SourceEdgeId],
) -> tuple[tuple[SourceFaceId, ...], ...]:
    face_set = set(source_face_ids)
    if len(face_set) <= 1:
        return (tuple(sorted(face_set, key=str)),)

    parents = {source_face_id: source_face_id for source_face_id in face_set}

    def find(source_face_id: SourceFaceId) -> SourceFaceId:
        while parents[source_face_id] != source_face_id:
            parents[source_face_id] = parents[parents[source_face_id]]
            source_face_id = parents[source_face_id]
        return source_face_id

    def union(first: SourceFaceId, second: SourceFaceId) -> None:
        first_root = find(first)
        second_root = find(second)
        if first_root != second_root:
            parents[second_root] = first_root

    for source_edge_id, source_edge in source.edges.items():
        if source_vertex_id not in source_edge.vertex_ids:
            continue
        if _is_patch_boundary_edge(
            source_edge_id,
            edge_incidence.get(source_edge_id, ()),
            boundary_mark_edge_ids,
        ):
            continue
        incident_patch_face_ids = [
            incident_face_id
            for incident_face_id in edge_incidence.get(source_edge_id, ())
            if incident_face_id in face_set
            and face_to_patch_id[incident_face_id] == patch_id
        ]
        for incident_face_id in incident_patch_face_ids[1:]:
            union(incident_patch_face_ids[0], incident_face_id)

    components: dict[SourceFaceId, list[SourceFaceId]] = defaultdict(list)
    for source_face_id in face_set:
        components[find(source_face_id)].append(source_face_id)
    return tuple(
        sorted(
            (tuple(sorted(component, key=str)) for component in components.values()),
            key=lambda component: str(component[0]),
        )
    )


def _vertex_id_for_fan_component(
    topology: SurfaceModel,
    patch_id: PatchId,
    source_vertex_id: SourceVertexId,
    component_index: int,
    component_count: int,
) -> VertexId:
    vertex_id = (
        VertexId(f"vertex:{source_vertex_id}")
        if component_count == 1
        else VertexId(f"vertex:{source_vertex_id}:use:{patch_id}:{component_index}")
    )
    if vertex_id in topology.vertices:
        return vertex_id
    for topology_vertex in sorted(topology.vertices.values(), key=lambda item: str(item.id)):
        if source_vertex_id in topology_vertex.source_vertex_ids:
            return topology_vertex.id
    return vertex_id


def _face_fan_area_normal(
    source: SourceMeshSnapshot,
    source_face_ids: tuple[SourceFaceId, ...],
) -> tuple[float, Vector3]:
    total_area = 0.0
    normal_accumulator = (0.0, 0.0, 0.0)
    for source_face_id in source_face_ids:
        face_points = _face_points(source, source_face_id)
        if len(face_points) < 3:
            continue
        first = face_points[0]
        for index in range(1, len(face_points) - 1):
            area, area_vector, _triangle_centroid = triangle_area_normal_centroid(
                first,
                face_points[index],
                face_points[index + 1],
            )
            total_area += area
            normal_accumulator = add(normal_accumulator, area_vector)
    return total_area, normalize(normal_accumulator)


def _selected_edge_incidence(
    source: SourceMeshSnapshot,
    source_face_ids: tuple[SourceFaceId, ...],
) -> dict[SourceEdgeId, tuple[SourceFaceId, ...]]:
    incidence: dict[SourceEdgeId, list[SourceFaceId]] = defaultdict(list)
    for source_face_id in source_face_ids:
        for source_edge_id in source.faces[source_face_id].edge_ids:
            incidence[source_edge_id].append(source_face_id)
    return {
        source_edge_id: tuple(source_face_ids)
        for source_edge_id, source_face_ids in incidence.items()
    }


def _marked_patch_boundary_edge_ids(source: SourceMeshSnapshot) -> set[SourceEdgeId]:
    source_edge_ids = set(source.edges)
    return {
        SourceEdgeId(mark.target_id)
        for mark in source.marks
        if mark.target_id in source_edge_ids
        and mark.value
        and mark.kind in (SourceMarkKind.SEAM, SourceMarkKind.USER)
    }


def _is_patch_boundary_edge(
    source_edge_id: SourceEdgeId,
    selected_incident_face_ids: tuple[SourceFaceId, ...],
    boundary_mark_edge_ids: set[SourceEdgeId],
) -> bool:
    if len(selected_incident_face_ids) != 2:
        return True
    return source_edge_id in boundary_mark_edge_ids


def _face_points(source: SourceMeshSnapshot, source_face_id: SourceFaceId) -> tuple[Vector3, ...]:
    return tuple(_source_vertex_point(source, vertex_id) for vertex_id in source.faces[source_face_id].vertex_ids)


def _source_edge_points(source: SourceMeshSnapshot, source_edge_id: SourceEdgeId) -> tuple[Vector3, Vector3]:
    edge = source.edges[source_edge_id]
    return (
        _source_vertex_point(source, edge.vertex_ids[0]),
        _source_vertex_point(source, edge.vertex_ids[1]),
    )


def _topology_vertex_point(source: SourceMeshSnapshot, vertex: Vertex) -> Vector3:
    return average(tuple(_source_vertex_point(source, source_vertex_id) for source_vertex_id in vertex.source_vertex_ids))


def _source_vertex_point(source: SourceMeshSnapshot, source_vertex_id: SourceVertexId) -> Vector3:
    return source.vertices[source_vertex_id].position
