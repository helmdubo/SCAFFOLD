"""Pure-python spine/rib assembly for ScaffoldGraph overlay v2."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from scaffold_core.layer_2_geometry.measures import dot, normalize
from scaffold_core.layer_3_relations.model import PatchChainEndpointRole


PARALLEL_DOT = 0.99


@dataclass(frozen=True)
class RunSegmentView:
    id: str
    directional_evidence_id: str
    family_id: str | None
    patch_id: str
    patch_chain_id: str
    parent_chain_id: str
    segment_indices: tuple[int, ...]
    start_junction_id: str
    end_junction_id: str
    length: float
    direction: tuple[float, float, float]
    polyline: tuple[tuple[float, float, float], ...]


@dataclass(frozen=True)
class RailView:
    id: str
    family_id: str
    role: str
    directional_evidence_ids: tuple[str, ...]
    patch_ids: tuple[str, ...]
    junction_ids: tuple[str, ...]
    segment_polylines: tuple[tuple[tuple[float, float, float], ...], ...]
    length: float
    branch_junction_ids: tuple[str, ...]
    is_ambiguous: bool


@dataclass(frozen=True)
class JunctionGlyph:
    id: str
    kind: str
    position: tuple[float, float, float]
    valence: int
    size_step: int


@dataclass(frozen=True)
class RailAssembly:
    run_segments: tuple[RunSegmentView, ...]
    rails: tuple[RailView, ...]
    junction_glyphs: tuple[JunctionGlyph, ...]
    branch_glyphs: tuple[JunctionGlyph, ...]
    rail_contract_inputs: tuple[str, ...]


def build_rail_assembly(topology: Any, geometry: Any, relations: Any) -> RailAssembly:
    """Assemble debug-side rails over ScaffoldNode union RunEndpointJunction."""

    family_by_evidence_id = _family_by_evidence_id(relations)
    endpoint_junction_by_occurrence = _endpoint_junction_by_occurrence(relations)
    position_by_junction_id = _junction_positions(geometry, relations)
    segments = tuple(
        segment
        for evidence in sorted(relations.patch_chain_directional_evidence, key=lambda item: item.id)
        for segment in (
            _segment_view(geometry, evidence, family_by_evidence_id, endpoint_junction_by_occurrence),
        )
        if segment is not None
    )
    valence_by_junction_id = _valence_by_junction_id(segments)
    rails = _rails_from_segments(topology, segments, relations, valence_by_junction_id)
    glyphs = _junction_glyphs(relations, position_by_junction_id, valence_by_junction_id)
    return RailAssembly(
        run_segments=segments,
        rails=rails,
        junction_glyphs=glyphs,
        branch_glyphs=tuple(glyph for glyph in glyphs if glyph.valence > 2),
        rail_contract_inputs=_contract_inputs(relations, segments),
    )


def _family_by_evidence_id(relations: Any) -> dict[str, str]:
    family_by_evidence_id: dict[str, str] = {}
    for family in relations.connected_direction_families:
        for evidence_id in family.member_directional_evidence_ids:
            family_by_evidence_id[evidence_id] = family.id
    return family_by_evidence_id


def _endpoint_junction_by_occurrence(relations: Any) -> dict[tuple[str, PatchChainEndpointRole], str]:
    junction_by_occurrence: dict[tuple[str, PatchChainEndpointRole], str] = {}
    for junction in relations.run_endpoint_junctions:
        junction_id = junction.anchor_scaffold_node_id or junction.id
        for occurrence in junction.incident_run_endpoint_occurrences:
            junction_by_occurrence[occurrence] = junction_id
    return junction_by_occurrence


def _segment_view(
    geometry: Any,
    evidence: Any,
    family_by_evidence_id: dict[str, str],
    endpoint_junction_by_occurrence: dict[tuple[str, PatchChainEndpointRole], str],
) -> RunSegmentView | None:
    start_junction_id = endpoint_junction_by_occurrence.get((evidence.id, PatchChainEndpointRole.START))
    end_junction_id = endpoint_junction_by_occurrence.get((evidence.id, PatchChainEndpointRole.END))
    if start_junction_id is None or end_junction_id is None:
        return None
    polyline = _evidence_polyline(geometry, evidence)
    if len(polyline) < 2:
        return None
    return RunSegmentView(
        id=f"run_segment:{evidence.id}",
        directional_evidence_id=evidence.id,
        family_id=family_by_evidence_id.get(evidence.id),
        patch_id=str(evidence.patch_id),
        patch_chain_id=str(evidence.patch_chain_id),
        parent_chain_id=str(evidence.parent_chain_id),
        segment_indices=tuple(evidence.segment_indices),
        start_junction_id=start_junction_id,
        end_junction_id=end_junction_id,
        length=float(evidence.length),
        direction=tuple(float(value) for value in evidence.direction),
        polyline=polyline,
    )


def _evidence_polyline(geometry: Any, evidence: Any) -> tuple[tuple[float, float, float], ...]:
    chain_facts = geometry.chain_facts.get(evidence.parent_chain_id)
    if chain_facts is None:
        return ()
    segments_by_index = {segment.segment_index: segment for segment in chain_facts.segments}
    segments = tuple(
        segments_by_index[index]
        for index in evidence.segment_indices
        if index in segments_by_index
    )
    if not segments:
        return ()
    points = [segments[0].start_position]
    points.extend(segment.end_position for segment in segments)
    if (
        evidence.start_source_vertex_id == segments[-1].end_source_vertex_id
        and evidence.end_source_vertex_id == segments[0].start_source_vertex_id
    ) or (
        evidence.orientation_sign == -1
        and evidence.start_source_vertex_id != segments[0].start_source_vertex_id
    ):
        return tuple(reversed(points))
    return tuple(points)


def _valence_by_junction_id(segments: tuple[RunSegmentView, ...]) -> dict[str, int]:
    evidence_ids_by_junction: dict[str, set[str]] = defaultdict(set)
    for segment in segments:
        evidence_ids_by_junction[segment.start_junction_id].add(segment.directional_evidence_id)
        evidence_ids_by_junction[segment.end_junction_id].add(segment.directional_evidence_id)
    return {
        junction_id: len(evidence_ids)
        for junction_id, evidence_ids in evidence_ids_by_junction.items()
    }


def _rails_from_segments(
    topology: Any,
    segments: tuple[RunSegmentView, ...],
    relations: Any,
    valence_by_junction_id: dict[str, int],
) -> tuple[RailView, ...]:
    rails: list[RailView] = []
    for family_id, family_segments in _segments_by_family(segments).items():
        for index, component in enumerate(_segment_components(family_segments)):
            branch_junction_ids = tuple(
                sorted(
                    {
                        junction_id
                        for segment in component
                        for junction_id in (segment.start_junction_id, segment.end_junction_id)
                        if _family_valence(junction_id, component) > 2
                    }
                )
            )
            rails.append(
                RailView(
                    id=f"rail:{family_id}:{index}",
                    family_id=family_id,
                    role="UNASSIGNED",
                    directional_evidence_ids=tuple(sorted(segment.directional_evidence_id for segment in component)),
                    patch_ids=tuple(sorted({segment.patch_id for segment in component})),
                    junction_ids=tuple(sorted({
                        junction_id
                        for segment in component
                        for junction_id in (segment.start_junction_id, segment.end_junction_id)
                    })),
                    segment_polylines=tuple(segment.polyline for segment in sorted(component, key=lambda item: item.id)),
                    length=_deduped_length(component),
                    branch_junction_ids=branch_junction_ids,
                    is_ambiguous=bool(branch_junction_ids),
                )
            )
    return _assign_roles(
        topology,
        tuple(sorted(rails, key=lambda item: item.id)),
        segments,
        valence_by_junction_id,
    )


def _segments_by_family(segments: tuple[RunSegmentView, ...]) -> dict[str, tuple[RunSegmentView, ...]]:
    rows: dict[str, list[RunSegmentView]] = defaultdict(list)
    for segment in segments:
        if segment.family_id is None:
            continue
        rows[segment.family_id].append(segment)
    return {
        family_id: tuple(sorted(values, key=lambda item: item.id))
        for family_id, values in rows.items()
    }


def _segment_components(segments: tuple[RunSegmentView, ...]) -> tuple[tuple[RunSegmentView, ...], ...]:
    neighbors: dict[str, set[str]] = {segment.id: set() for segment in segments}
    segment_ids_by_junction: dict[str, list[str]] = defaultdict(list)
    by_id = {segment.id: segment for segment in segments}
    for segment in segments:
        segment_ids_by_junction[segment.start_junction_id].append(segment.id)
        segment_ids_by_junction[segment.end_junction_id].append(segment.id)
    for segment_ids in segment_ids_by_junction.values():
        for first_id in segment_ids:
            neighbors[first_id].update(second_id for second_id in segment_ids if second_id != first_id)

    components: list[tuple[RunSegmentView, ...]] = []
    visited: set[str] = set()
    for segment in segments:
        if segment.id in visited:
            continue
        stack = [segment.id]
        component_ids: list[str] = []
        while stack:
            segment_id = stack.pop()
            if segment_id in visited:
                continue
            visited.add(segment_id)
            component_ids.append(segment_id)
            stack.extend(sorted(neighbors[segment_id] - visited, reverse=True))
        components.append(tuple(by_id[segment_id] for segment_id in sorted(component_ids)))
    return tuple(components)


def _family_valence(junction_id: str, segments: tuple[RunSegmentView, ...]) -> int:
    return sum(
        junction_id in (segment.start_junction_id, segment.end_junction_id)
        for segment in segments
    )


def _deduped_length(segments: tuple[RunSegmentView, ...]) -> float:
    seen: set[tuple[str, tuple[int, ...]]] = set()
    total = 0.0
    for segment in segments:
        key = (segment.parent_chain_id, segment.segment_indices)
        if key in seen:
            continue
        seen.add(key)
        total += segment.length
    return total


def _assign_roles(
    topology: Any,
    rails: tuple[RailView, ...],
    segments: tuple[RunSegmentView, ...],
    valence_by_junction_id: dict[str, int],
) -> tuple[RailView, ...]:
    segment_by_evidence_id = {segment.directional_evidence_id: segment for segment in segments}
    patch_group_by_patch_id = _patch_group_by_patch_id(topology)
    group_ids = sorted(set(patch_group_by_patch_id.values()))
    assigned: dict[str, str] = {}
    for group_id in group_ids:
        group_rails = tuple(
            rail
            for rail in rails
            if group_id in _rail_group_ids(rail, patch_group_by_patch_id)
        )
        if not group_rails:
            continue
        spine = sorted(group_rails, key=lambda rail: (-rail.length, rail.id))[0]
        assigned[spine.id] = "SPINE"
        for rail in group_rails:
            if rail.id == spine.id:
                continue
            assigned[rail.id] = (
                "PARALLEL"
                if _rails_are_parallel(rail, spine, segment_by_evidence_id)
                else "RIB"
            )
    return tuple(
        RailView(
            id=rail.id,
            family_id=rail.family_id,
            role=assigned.get(rail.id, "RIB"),
            directional_evidence_ids=rail.directional_evidence_ids,
            patch_ids=rail.patch_ids,
            junction_ids=rail.junction_ids,
            segment_polylines=rail.segment_polylines,
            length=rail.length,
            branch_junction_ids=rail.branch_junction_ids,
            is_ambiguous=rail.is_ambiguous or any(valence_by_junction_id.get(junction_id, 0) > 2 for junction_id in rail.junction_ids),
        )
        for rail in rails
    )


def _patch_group_by_patch_id(topology: Any) -> dict[str, str]:
    rows: dict[str, str] = {}
    for shell in topology.shells.values():
        group_id = f"patch_group:{shell.id}"
        for patch_id in shell.patch_ids:
            rows[str(patch_id)] = group_id
    return rows


def _rail_group_ids(rail: RailView, patch_group_by_patch_id: dict[str, str]) -> tuple[str, ...]:
    group_ids = {
        patch_group_by_patch_id.get(patch_id, f"patch_group:{patch_id}")
        for patch_id in rail.patch_ids
    }
    return tuple(sorted(group_ids))


def _rails_are_parallel(
    first: RailView,
    second: RailView,
    segment_by_evidence_id: dict[str, RunSegmentView],
) -> bool:
    first_segments = tuple(
        segment_by_evidence_id[evidence_id]
        for evidence_id in first.directional_evidence_ids
        if evidence_id in segment_by_evidence_id
    )
    second_segments = tuple(
        segment_by_evidence_id[evidence_id]
        for evidence_id in second.directional_evidence_ids
        if evidence_id in segment_by_evidence_id
    )
    return any(
        abs(dot(normalize(first_segment.direction), normalize(second_segment.direction))) >= PARALLEL_DOT
        for first_segment in first_segments
        for second_segment in second_segments
    )


def _junction_positions(geometry: Any, relations: Any) -> dict[str, tuple[float, float, float]]:
    positions: dict[str, tuple[float, float, float]] = {}
    for node in relations.scaffold_nodes:
        position = _average_vertex_position(geometry, tuple(str(vertex_id) for vertex_id in node.vertex_ids))
        if position is not None:
            positions[node.id] = position
    for junction in relations.run_endpoint_junctions:
        if junction.anchor_scaffold_node_id is not None:
            continue
        position = _average_vertex_position(geometry, tuple(str(vertex_id) for vertex_id in junction.topology_vertex_ids))
        if position is not None:
            positions[junction.id] = position
    return positions


def _average_vertex_position(geometry: Any, vertex_ids: tuple[str, ...]) -> tuple[float, float, float] | None:
    points = [
        facts.position
        for vertex_id, facts in geometry.vertex_facts.items()
        if str(vertex_id) in set(vertex_ids)
    ]
    if not points:
        return None
    return (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
        sum(point[2] for point in points) / len(points),
    )


def _junction_glyphs(
    relations: Any,
    position_by_junction_id: dict[str, tuple[float, float, float]],
    valence_by_junction_id: dict[str, int],
) -> tuple[JunctionGlyph, ...]:
    glyphs: list[JunctionGlyph] = []
    for node in sorted(relations.scaffold_nodes, key=lambda item: item.id):
        if node.id in position_by_junction_id:
            valence = valence_by_junction_id.get(node.id, 0)
            glyphs.append(_glyph(node.id, "SCAFFOLD_NODE", position_by_junction_id[node.id], valence))
    for junction in sorted(relations.run_endpoint_junctions, key=lambda item: item.id):
        if junction.anchor_scaffold_node_id is not None or junction.id not in position_by_junction_id:
            continue
        valence = valence_by_junction_id.get(junction.id, 0)
        glyphs.append(_glyph(junction.id, "RUN_ENDPOINT_JUNCTION", position_by_junction_id[junction.id], valence))
    return tuple(glyphs)


def _glyph(
    glyph_id: str,
    kind: str,
    position: tuple[float, float, float],
    valence: int,
) -> JunctionGlyph:
    return JunctionGlyph(
        id=glyph_id,
        kind=kind,
        position=position,
        valence=valence,
        size_step=max(0, min(3, valence - 1)),
    )


def _contract_inputs(relations: Any, segments: tuple[RunSegmentView, ...]) -> tuple[str, ...]:
    missing = len(relations.patch_chain_directional_evidence) - len(segments)
    if missing <= 0:
        return ()
    return (f"{missing} directional evidence endpoints could not be converted to debug run segments",)
