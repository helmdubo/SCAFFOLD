"""Pure-python spine/rib assembly for ScaffoldGraph overlay v2."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from scaffold_core.layer_2_geometry.measures import dot, normalize
from scaffold_core.layer_3_relations.model import PatchChainEndpointRole

from .geodesic_continuation import (
    GEODESIC_STRAIGHT_TOLERANCE,
    is_geodesic_straight_at_patch_vertex,
)
from .rail_offsets import offset_segment_polyline, self_seam_flip_keys


PARALLEL_DOT = 0.99


@dataclass(frozen=True)
class RunSegmentView:
    id: str
    directional_evidence_id: str
    family_id: str | None
    patch_id: str
    patch_chain_id: str
    parent_chain_id: str
    loop_id: str
    segment_indices: tuple[int, ...]
    start_junction_id: str
    end_junction_id: str
    length: float
    direction: tuple[float, float, float]
    polyline: tuple[tuple[float, float, float], ...]
    source_edge_ids: tuple[str, ...]


@dataclass(frozen=True)
class RailView:
    id: str
    family_id: str
    role: str
    directional_evidence_ids: tuple[str, ...]
    patch_ids: tuple[str, ...]
    junction_ids: tuple[str, ...]
    segment_polylines: tuple[tuple[tuple[float, float, float], ...], ...]
    segment_offset_records: tuple[dict[str, Any], ...]
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
class JunctionContext:
    id: str
    source_vertex_id: str | None
    topology_vertex_ids: tuple[str, ...]


@dataclass(frozen=True)
class RailAssembly:
    run_segments: tuple[RunSegmentView, ...]
    rails: tuple[RailView, ...]
    junction_glyphs: tuple[JunctionGlyph, ...]
    branch_glyphs: tuple[JunctionGlyph, ...]
    rail_contract_inputs: tuple[str, ...]


def build_rail_assembly(
    topology: Any,
    geometry: Any,
    relations: Any,
    source: Any = None,
) -> RailAssembly:
    """Assemble debug-side rails over ScaffoldNode union RunEndpointJunction."""

    contract_inputs = set(_base_contract_inputs())
    family_by_evidence_id = _family_by_evidence_id(relations)
    endpoint_junction_by_occurrence = _endpoint_junction_by_occurrence(relations)
    junction_context_by_id = _junction_context_by_id(relations)
    position_by_junction_id = _junction_positions(geometry, relations)
    self_seam_chain_ids = _self_seam_chain_ids(relations)
    segments = tuple(
        segment
        for evidence in sorted(relations.patch_chain_directional_evidence, key=lambda item: item.id)
        for segment in (
            _segment_view(geometry, evidence, family_by_evidence_id, endpoint_junction_by_occurrence),
        )
        if segment is not None
    )
    valence_by_junction_id = _valence_by_junction_id(segments)
    rails = _rails_from_segments(
        topology,
        geometry,
        segments,
        source,
        valence_by_junction_id,
        junction_context_by_id,
        self_seam_chain_ids,
        contract_inputs,
    )
    glyphs = _junction_glyphs(relations, position_by_junction_id, valence_by_junction_id)
    return RailAssembly(
        run_segments=segments,
        rails=rails,
        junction_glyphs=glyphs,
        branch_glyphs=tuple(glyph for glyph in glyphs if glyph.valence > 2),
        rail_contract_inputs=_contract_inputs(relations, segments, contract_inputs),
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


def _junction_context_by_id(relations: Any) -> dict[str, JunctionContext]:
    contexts: dict[str, JunctionContext] = {}
    for node in relations.scaffold_nodes:
        contexts[node.id] = JunctionContext(
            id=node.id,
            source_vertex_id=_single_source_vertex_id(node.source_vertex_ids),
            topology_vertex_ids=tuple(sorted((str(vertex_id) for vertex_id in node.vertex_ids))),
        )
    for junction in relations.run_endpoint_junctions:
        if junction.anchor_scaffold_node_id is not None:
            continue
        contexts[junction.id] = JunctionContext(
            id=junction.id,
            source_vertex_id=str(junction.source_vertex_id) if junction.source_vertex_id is not None else None,
            topology_vertex_ids=tuple(sorted((str(vertex_id) for vertex_id in junction.topology_vertex_ids))),
        )
    return contexts


def _single_source_vertex_id(source_vertex_ids: tuple[Any, ...]) -> str | None:
    if not source_vertex_ids:
        return None
    sorted_ids = tuple(sorted(str(source_vertex_id) for source_vertex_id in source_vertex_ids))
    return sorted_ids[0]


def _self_seam_chain_ids(relations: Any) -> set[str]:
    return {
        str(junction.matched_chain_id)
        for junction in relations.scaffold_junctions
        if junction.kind.value == "SELF_SEAM" and junction.matched_chain_id is not None
    }


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
        loop_id=str(evidence.loop_id),
        segment_indices=tuple(evidence.segment_indices),
        start_junction_id=start_junction_id,
        end_junction_id=end_junction_id,
        length=float(evidence.length),
        direction=tuple(float(value) for value in evidence.direction),
        polyline=polyline,
        source_edge_ids=tuple(str(source_edge_id) for source_edge_id in evidence.source_edge_ids),
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
    geometry: Any,
    segments: tuple[RunSegmentView, ...],
    source: Any,
    valence_by_junction_id: dict[str, int],
    junction_context_by_id: dict[str, JunctionContext],
    self_seam_chain_ids: set[str],
    contract_inputs: set[str],
) -> tuple[RailView, ...]:
    rails: list[RailView] = []
    for index, component in enumerate(
        _segment_components(
            geometry,
            source,
            segments,
            junction_context_by_id,
            self_seam_chain_ids,
            contract_inputs,
        )
    ):
        role = "CUT" if any(segment.parent_chain_id in self_seam_chain_ids for segment in component) else "UNASSIGNED"
        family_id = _component_family_id(component, index)
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
                role=role,
                directional_evidence_ids=tuple(sorted(segment.directional_evidence_id for segment in component)),
                patch_ids=tuple(sorted({segment.patch_id for segment in component})),
                junction_ids=tuple(sorted({
                    junction_id
                    for segment in component
                    for junction_id in (segment.start_junction_id, segment.end_junction_id)
                })),
                segment_polylines=tuple(segment.polyline for segment in sorted(component, key=lambda item: item.id)),
                segment_offset_records=(),
                length=_deduped_length(component),
                branch_junction_ids=branch_junction_ids,
                is_ambiguous=bool(branch_junction_ids),
            )
        )
    assigned = _assign_roles(
        topology,
        tuple(sorted(rails, key=lambda item: item.id)),
        segments,
        valence_by_junction_id,
    )
    return _with_offset_polylines(topology, source, assigned, segments, self_seam_chain_ids, contract_inputs)


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


def _component_family_id(component: tuple[RunSegmentView, ...], index: int) -> str:
    family_ids = tuple(sorted({segment.family_id for segment in component if segment.family_id is not None}))
    if len(family_ids) == 1:
        return family_ids[0]
    patches = ".".join(sorted({segment.patch_id for segment in component}))
    return f"geodesic_patch_rail:{patches}:{index}"


def _segment_components(
    geometry: Any,
    source: Any,
    segments: tuple[RunSegmentView, ...],
    junction_context_by_id: dict[str, JunctionContext],
    self_seam_chain_ids: set[str],
    contract_inputs: set[str],
) -> tuple[tuple[RunSegmentView, ...], ...]:
    neighbors: dict[str, set[str]] = {segment.id: set() for segment in segments}
    segment_ids_by_junction: dict[str, list[str]] = defaultdict(list)
    by_id = {segment.id: segment for segment in segments}
    for segment in segments:
        segment_ids_by_junction[segment.start_junction_id].append(segment.id)
        segment_ids_by_junction[segment.end_junction_id].append(segment.id)
    for junction_id, segment_ids in segment_ids_by_junction.items():
        for first_id in segment_ids:
            for second_id in segment_ids:
                if second_id == first_id:
                    continue
                if _segments_continue_at_junction(
                    geometry,
                    source,
                    by_id[first_id],
                    by_id[second_id],
                    junction_id,
                    segment_ids_by_junction[junction_id],
                    by_id,
                    junction_context_by_id,
                    self_seam_chain_ids,
                    contract_inputs,
                ):
                    neighbors[first_id].add(second_id)

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


def _segments_continue_at_junction(
    geometry: Any,
    source: Any,
    first: RunSegmentView,
    second: RunSegmentView,
    junction_id: str,
    incident_segment_ids: list[str],
    segment_by_id: dict[str, RunSegmentView],
    junction_context_by_id: dict[str, JunctionContext],
    self_seam_chain_ids: set[str],
    contract_inputs: set[str],
) -> bool:
    if first.parent_chain_id in self_seam_chain_ids or second.parent_chain_id in self_seam_chain_ids:
        return False
    if first.patch_id != second.patch_id:
        if first.family_id is None or first.family_id != second.family_id:
            return False
        return _family_incidence_count(first.family_id, incident_segment_ids, segment_by_id) <= 2
    if _patch_incidence_count(first.patch_id, incident_segment_ids, segment_by_id) > 2:
        return False
    context = junction_context_by_id.get(junction_id)
    if context is None:
        contract_inputs.add(f"missing junction context for geodesic rail continuation at {junction_id}")
        return False
    is_straight, issue = is_geodesic_straight_at_patch_vertex(
        source,
        geometry,
        patch_id=first.patch_id,
        source_vertex_id=context.source_vertex_id,
        topology_vertex_ids=context.topology_vertex_ids,
        tolerance=GEODESIC_STRAIGHT_TOLERANCE,
    )
    if issue is not None:
        contract_inputs.add(issue)
    return is_straight


def _patch_incidence_count(
    patch_id: str,
    incident_segment_ids: list[str],
    segment_by_id: dict[str, RunSegmentView],
) -> int:
    return sum(
        1
        for segment_id in incident_segment_ids
        if segment_by_id[segment_id].patch_id == patch_id
    )


def _family_incidence_count(
    family_id: str,
    incident_segment_ids: list[str],
    segment_by_id: dict[str, RunSegmentView],
) -> int:
    return sum(
        1
        for segment_id in incident_segment_ids
        if segment_by_id[segment_id].family_id == family_id
    )


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
            and rail.role != "CUT"
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
    assigned_rails = tuple(
        RailView(
            id=rail.id,
            family_id=rail.family_id,
            role=rail.role if rail.role == "CUT" else assigned.get(rail.id, "RIB"),
            directional_evidence_ids=rail.directional_evidence_ids,
            patch_ids=rail.patch_ids,
            junction_ids=rail.junction_ids,
            segment_polylines=rail.segment_polylines,
            segment_offset_records=rail.segment_offset_records,
            length=rail.length,
            branch_junction_ids=rail.branch_junction_ids,
            is_ambiguous=rail.is_ambiguous or any(valence_by_junction_id.get(junction_id, 0) > 2 for junction_id in rail.junction_ids),
        )
        for rail in rails
    )
    return assigned_rails


def _with_offset_polylines(
    topology: Any,
    source: Any,
    rails: tuple[RailView, ...],
    segments: tuple[RunSegmentView, ...],
    self_seam_chain_ids: set[str],
    contract_inputs: set[str],
) -> tuple[RailView, ...]:
    segment_by_evidence_id = {segment.directional_evidence_id: segment for segment in segments}
    flip_keys = self_seam_flip_keys(rails, segment_by_evidence_id, self_seam_chain_ids)
    output = []
    for rail in rails:
        polylines = []
        records = []
        for evidence_id in rail.directional_evidence_ids:
            segment = segment_by_evidence_id.get(evidence_id)
            if segment is None:
                continue
            flip = (segment.parent_chain_id, segment.patch_id, segment.patch_chain_id) in flip_keys
            polyline, record = offset_segment_polyline(
                topology,
                source,
                segment,
                flip=flip,
                self_seam_chain_ids=self_seam_chain_ids,
            )
            polylines.append(polyline)
            records.append(record)
            if record["unoffset"]:
                contract_inputs.add(record["issue"])
        output.append(
            RailView(
                id=rail.id,
                family_id=rail.family_id,
                role=rail.role,
                directional_evidence_ids=rail.directional_evidence_ids,
                patch_ids=rail.patch_ids,
                junction_ids=rail.junction_ids,
                segment_polylines=tuple(polylines),
                segment_offset_records=tuple(records),
                length=rail.length,
                branch_junction_ids=rail.branch_junction_ids,
                is_ambiguous=rail.is_ambiguous,
            )
        )
    return tuple(output)


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


def _base_contract_inputs() -> tuple[str, str]:
    return (
        "future ScaffoldRail needs a geodesic continuation criterion: same-patch consecutive runs continue when patch-local face-fan angle is within GEODESIC_STRAIGHT_TOLERANCE of pi",
        "future ScaffoldRail needs per PatchChain-use rail membership: the same Chain can be straight in one owning patch view and cornered in an adjacent patch view",
    )


def _contract_inputs(
    relations: Any,
    segments: tuple[RunSegmentView, ...],
    contract_inputs: set[str],
) -> tuple[str, ...]:
    missing = len(relations.patch_chain_directional_evidence) - len(segments)
    if missing > 0:
        contract_inputs.add(f"{missing} directional evidence endpoints could not be converted to debug run segments")
    ordered = list(_base_contract_inputs())
    ordered.extend(sorted(contract_inputs - set(ordered)))
    return tuple(ordered)
