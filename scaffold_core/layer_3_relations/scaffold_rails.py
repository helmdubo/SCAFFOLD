"""
Layer: 3 - Relations

Rules:
- Build ScaffoldTrace and ScaffoldRail evidence views from existing Layer 3 records.
- Do not mutate topology, ScaffoldGraph, ConnectedDirectionFamily, or directional evidence.
- Do not choose paths through branches or open closed loops without an explicit structural cut.
- Do not derive coordinates, pins, packing, feature labels, world roles, or runtime behavior.

A rail is ordered by stations. The two uses of one hinge Chain (a SHARED_CHAIN
crossing) cover the same source edges, so they form one station rather than two
consecutive members; stations connect through node crossings at trace nodes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from scaffold_core.core.evidence import Evidence
from scaffold_core.layer_3_relations.model import (
    ConnectedDirectionFamily,
    CrossingRecord,
    PatchChainDirectionalEvidence,
    PatchChainEndpointRole,
    RunEndpointJunction,
    ScaffoldRail,
    ScaffoldRailSegment,
    ScaffoldTrace,
    ScaffoldTraceMember,
)


POLICY_NAME = "scaffold_trace_rail_v1"
STATION_CROSSING_KIND = "SHARED_CHAIN"


@dataclass(frozen=True)
class MemberTraceEndpoints:
    """Trace nodes at the start and the end of one directional member."""

    start_trace_node_id: str | None
    end_trace_node_id: str | None


@dataclass(frozen=True)
class _StationRail:
    ordered_member_ids: tuple[str, ...]
    ordered_node_ids: tuple[str, ...]
    signs: Mapping[str, int]
    branch_records: Mapping[str, tuple[str, ...]]
    is_closed_loop: bool
    diagnostics: tuple[str, ...]
    station_of: Mapping[str, str]
    member_crossing_index: Mapping[frozenset[str], int]
    station_link_index: Mapping[frozenset[str], int]


def build_scaffold_traces_and_rails(
    direction_families: tuple[ConnectedDirectionFamily, ...],
    directional_evidence_items: tuple[PatchChainDirectionalEvidence, ...],
    run_endpoint_junctions: tuple[RunEndpointJunction, ...],
) -> tuple[tuple[ScaffoldTrace, ...], tuple[ScaffoldRail, ...]]:
    """Build ordered trace/rail evidence from ConnectedDirectionFamily records."""

    evidence_by_id = {item.id: item for item in directional_evidence_items}
    endpoint_by_member_id = rail_member_endpoints(run_endpoint_junctions)
    traces: list[ScaffoldTrace] = []
    rails: list[ScaffoldRail] = []

    for index, family in enumerate(sorted(direction_families, key=lambda item: item.id)):
        trace, rail = _build_family_trace_and_rail(
            index,
            family,
            evidence_by_id,
            endpoint_by_member_id,
        )
        traces.append(trace)
        rails.append(rail)
    return tuple(traces), tuple(rails)


def rail_member_endpoints(
    run_endpoint_junctions: tuple[RunEndpointJunction, ...],
) -> dict[str, MemberTraceEndpoints]:
    """Map each directional member to the trace nodes at its start and end."""

    starts: dict[str, str] = {}
    ends: dict[str, str] = {}
    for junction in sorted(run_endpoint_junctions, key=lambda item: item.id):
        trace_node_id = junction.anchor_scaffold_node_id or junction.id
        for member_id, role in junction.incident_run_endpoint_occurrences:
            if role is PatchChainEndpointRole.START:
                starts.setdefault(member_id, trace_node_id)
            elif role is PatchChainEndpointRole.END:
                ends.setdefault(member_id, trace_node_id)
    return {
        member_id: MemberTraceEndpoints(starts.get(member_id), ends.get(member_id))
        for member_id in sorted(set(starts) | set(ends))
    }


def cut_scaffold_rail(
    family: ConnectedDirectionFamily,
    member_endpoints: Mapping[str, MemberTraceEndpoints],
    member_ids: Iterable[str],
    kept_chain_ids: Iterable[str],
) -> tuple[ScaffoldRailSegment, ...]:
    """Cut a family's rail by a caller-supplied structural cut (DD-47 draft).

    The caller keeps a set of members (for example the runs of one island) and
    the Chains its cut keeps joined (for example the island's stitched hinges).
    A crossing survives when both members are kept and it stays in one patch or
    passes a kept Chain. Each connected piece is ordered through its stations
    like a whole rail, so a loop opens exactly where the caller cut it. A branch
    or a loop the cut leaves closed stays unordered with a diagnostic; this
    function never chooses an opening or a branch itself.
    """

    kept_members = set(member_ids)
    kept_chains = {str(chain_id) for chain_id in kept_chain_ids}
    members = sorted(member for member in family.member_directional_evidence_ids if member in kept_members)
    crossings = [
        (index, crossing)
        for index, crossing in enumerate(family.crossing_records)
        if crossing.first_directional_evidence_id in kept_members
        and crossing.second_directional_evidence_id in kept_members
        and (
            crossing.first_patch_id == crossing.second_patch_id
            or str(crossing.shared_chain_id) in kept_chains
        )
    ]
    segments: list[ScaffoldRailSegment] = []
    for piece, piece_crossings in _connected_pieces(members, crossings):
        rail = _station_rail(piece, piece_crossings, member_endpoints)
        diagnostics = list(rail.diagnostics)
        if rail.is_closed_loop:
            diagnostics.append("closed_loop")
        diagnostics.extend(f"branch:{record_id}" for record_id in sorted(rail.branch_records))
        is_ordered = not diagnostics and all(rail.signs.get(member, 0) != 0 for member in piece)
        segments.append(ScaffoldRailSegment(
            direction_family_id=family.id,
            ordered_member_directional_evidence_ids=rail.ordered_member_ids if is_ordered else tuple(piece),
            ordered_trace_node_ids=rail.ordered_node_ids,
            orientation_sign_by_member=dict(rail.signs) if is_ordered else {member: 0 for member in piece},
            is_ordered=is_ordered,
            diagnostics=tuple(diagnostics),
        ))
    return tuple(segments)


def _build_family_trace_and_rail(
    index: int,
    family: ConnectedDirectionFamily,
    evidence_by_id: Mapping[str, PatchChainDirectionalEvidence],
    endpoint_by_member_id: Mapping[str, MemberTraceEndpoints],
) -> tuple[ScaffoldTrace, ScaffoldRail]:
    station_rail = _station_rail(
        sorted(family.member_directional_evidence_ids),
        list(enumerate(family.crossing_records)),
        endpoint_by_member_id,
    )
    branch_records = dict(station_rail.branch_records)
    is_branch_ambiguous = bool(branch_records)
    is_closed_loop = station_rail.is_closed_loop
    loop_ambiguity_records = (
        {"closed_loop": tuple(sorted(family.member_directional_evidence_ids))}
        if is_closed_loop
        else {}
    )
    if is_branch_ambiguous or is_closed_loop:
        ordered_member_ids = tuple(family.ordered_member_directional_evidence_ids)
        ordered_node_ids = _unordered_node_ids(ordered_member_ids, endpoint_by_member_id)
        orientation_sign_by_member = {member_id: 0 for member_id in ordered_member_ids}
    else:
        ordered_member_ids = station_rail.ordered_member_ids
        ordered_node_ids = list(station_rail.ordered_node_ids)
        orientation_sign_by_member = dict(station_rail.signs)

    diagnostics = list(station_rail.diagnostics)
    if (
        len(ordered_node_ids) > 1
        and not is_closed_loop
        and ordered_node_ids[0] == ordered_node_ids[-1]
    ):
        diagnostics.append(f"coincident_open_trace_endpoints:{ordered_node_ids[0]}")
    diagnostics.extend(
        _missing_member_diagnostics(ordered_member_ids, evidence_by_id, endpoint_by_member_id)
    )

    members = tuple(
        _trace_member(
            member_id,
            family,
            evidence_by_id,
            endpoint_by_member_id,
            station_rail,
            ordered_member_ids,
        )
        for member_id in ordered_member_ids
    )
    trace_id = f"scaffold_trace:{index}"
    confidence = _confidence(family, diagnostics, is_branch_ambiguous, is_closed_loop)
    trace = ScaffoldTrace(
        id=trace_id,
        direction_family_id=family.id,
        member_directional_evidence_ids=family.member_directional_evidence_ids,
        ordered_member_directional_evidence_ids=ordered_member_ids,
        trace_node_ids=tuple(ordered_node_ids),
        members=members,
        crossing_records=family.crossing_records,
        branch_records=branch_records,
        loop_ambiguity_records=loop_ambiguity_records,
        diagnostics=tuple(diagnostics),
        confidence=confidence,
        evidence=(_trace_evidence(family, diagnostics, is_branch_ambiguous, is_closed_loop),),
    )
    is_consumable = (
        len(ordered_member_ids) > 1
        and not is_branch_ambiguous
        and not is_closed_loop
        and not diagnostics
        and all(orientation_sign_by_member.get(member_id, 0) != 0 for member_id in ordered_member_ids)
    )
    rail = ScaffoldRail(
        id=f"scaffold_rail:{index}",
        scaffold_trace_id=trace_id,
        direction_family_id=family.id,
        ordered_member_directional_evidence_ids=ordered_member_ids,
        ordered_trace_node_ids=tuple(ordered_node_ids),
        first_trace_node_id=ordered_node_ids[0] if ordered_node_ids else None,
        last_trace_node_id=ordered_node_ids[-1] if ordered_node_ids else None,
        is_closed_loop=is_closed_loop,
        orientation_sign_by_member=orientation_sign_by_member,
        crossing_records=family.crossing_records,
        branch_records=branch_records,
        loop_ambiguity_records=loop_ambiguity_records,
        is_consumable_by_g5a=is_consumable,
        diagnostics=tuple(diagnostics),
        confidence=confidence,
        evidence=(_rail_evidence(family, diagnostics, is_consumable, is_closed_loop),),
    )
    return trace, rail


def _connected_pieces(
    members: list[str],
    crossings: list[tuple[int, CrossingRecord]],
) -> list[tuple[list[str], list[tuple[int, CrossingRecord]]]]:
    parents = {member: member for member in members}

    def find(member: str) -> str:
        while parents[member] != member:
            parents[member] = parents[parents[member]]
            member = parents[member]
        return member

    for _, crossing in crossings:
        first_root = find(crossing.first_directional_evidence_id)
        second_root = find(crossing.second_directional_evidence_id)
        if first_root != second_root:
            parents[max(first_root, second_root)] = min(first_root, second_root)
    members_by_root: dict[str, list[str]] = {}
    for member in members:
        members_by_root.setdefault(find(member), []).append(member)
    crossings_by_root: dict[str, list[tuple[int, CrossingRecord]]] = {}
    for item in crossings:
        crossings_by_root.setdefault(find(item[1].first_directional_evidence_id), []).append(item)
    return [
        (sorted(members_by_root[root]), crossings_by_root.get(root, []))
        for root in sorted(members_by_root)
    ]


def _station_rail(
    members: list[str],
    crossings: list[tuple[int, CrossingRecord]],
    member_endpoints: Mapping[str, MemberTraceEndpoints],
) -> _StationRail:
    """Order one connected member set through its stations.

    Stations are the members joined by SHARED_CHAIN crossings; every other
    crossing links two stations at its trace node. Branches are counted on
    stations, never on the two uses of one hinge.
    """

    parents = {member: member for member in members}

    def find(member: str) -> str:
        while parents[member] != member:
            parents[member] = parents[parents[member]]
            member = parents[member]
        return member

    member_crossing_index: dict[frozenset[str], int] = {}
    for index, crossing in crossings:
        first_id = crossing.first_directional_evidence_id
        second_id = crossing.second_directional_evidence_id
        member_crossing_index.setdefault(frozenset((first_id, second_id)), index)
        if crossing.kind == STATION_CROSSING_KIND:
            first_root, second_root = find(first_id), find(second_id)
            if first_root != second_root:
                parents[max(first_root, second_root)] = min(first_root, second_root)
    station_of = {member: find(member) for member in members}
    members_of: dict[str, list[str]] = {}
    for member in members:
        members_of.setdefault(station_of[member], []).append(member)

    diagnostics: list[str] = []
    links: dict[str, list[tuple[str, str | None]]] = {station: [] for station in members_of}
    station_link_index: dict[frozenset[str], int] = {}
    for index, crossing in crossings:
        if crossing.kind == STATION_CROSSING_KIND:
            continue
        first_id = crossing.first_directional_evidence_id
        second_id = crossing.second_directional_evidence_id
        first_station, second_station = station_of[first_id], station_of[second_id]
        if first_station == second_station:
            diagnostics.append(f"crossing_inside_station:{first_id}:{second_id}:{crossing.kind}")
            continue
        node = crossing.scaffold_node_id or crossing.run_endpoint_junction_id
        if node is None:
            diagnostics.append(f"non_node_crossing:{first_id}:{second_id}:{crossing.kind}")
        if (second_station, node) in links[first_station]:
            continue
        links[first_station].append((second_station, node))
        links[second_station].append((first_station, node))
        station_link_index.setdefault(frozenset((first_station, second_station)), index)

    branch_records: dict[str, tuple[str, ...]] = {}
    for station, station_links in sorted(links.items()):
        if len(station_links) > 2:
            branch_records[f"station:{station}"] = tuple(sorted({neighbor for neighbor, _ in station_links}))
    stations_by_node: dict[str, set[str]] = {}
    for member in members:
        endpoints = member_endpoints.get(member)
        if endpoints is None:
            continue
        for trace_node_id in (endpoints.start_trace_node_id, endpoints.end_trace_node_id):
            if trace_node_id is not None:
                stations_by_node.setdefault(trace_node_id, set()).add(station_of[member])
    for trace_node_id, station_ids in sorted(stations_by_node.items()):
        if len(station_ids) > 2:
            branch_records[f"trace_node:{trace_node_id}"] = tuple(sorted(station_ids))
    is_closed_loop = len(links) > 1 and all(len(station_links) == 2 for station_links in links.values())

    if branch_records or is_closed_loop or not members:
        return _StationRail(
            tuple(members),
            tuple(_unordered_node_ids(tuple(members), member_endpoints)),
            {member: 0 for member in members},
            branch_records,
            is_closed_loop,
            tuple(diagnostics),
            station_of,
            member_crossing_index,
            station_link_index,
        )

    order = _station_order(links)
    if len(order) != len(links):
        diagnostics.append("disconnected_stations")
        order.extend(station for station in sorted(links) if station not in order)
    signs: dict[str, int] = {}
    ordered_nodes: list[str] = []
    for position, station in enumerate(order):
        previous_node = _link_node(links, station, order[position - 1]) if position > 0 else None
        next_node = _link_node(links, station, order[position + 1]) if position + 1 < len(order) else None
        station_members = members_of[station]
        if len(order) == 1:
            station_nodes = _orient_single_station(station_members, member_endpoints, signs, diagnostics)
        else:
            station_nodes = ()
            for member in station_members:
                endpoints = member_endpoints.get(member)
                if endpoints is None:
                    signs[member] = 0
                    diagnostics.append(f"missing_endpoints:{member}")
                    continue
                sign, member_nodes = _member_orientation(member, endpoints, previous_node, next_node, diagnostics)
                signs[member] = sign
                if not station_nodes and sign != 0:
                    station_nodes = member_nodes
        for trace_node_id in station_nodes:
            if not ordered_nodes or ordered_nodes[-1] != trace_node_id:
                ordered_nodes.append(trace_node_id)
    ordered_member_ids = tuple(member for station in order for member in members_of[station])
    return _StationRail(
        ordered_member_ids,
        tuple(ordered_nodes),
        signs,
        branch_records,
        False,
        tuple(diagnostics),
        station_of,
        member_crossing_index,
        station_link_index,
    )


def _station_order(links: Mapping[str, list[tuple[str, str | None]]]) -> list[str]:
    leaves = sorted(station for station, station_links in links.items() if len(station_links) <= 1)
    if not leaves:
        return []
    order: list[str] = []
    previous: str | None = None
    current: str | None = leaves[0]
    while current is not None and current not in order:
        order.append(current)
        candidates = [neighbor for neighbor, _ in links[current] if neighbor != previous]
        previous, current = current, (candidates[0] if len(candidates) == 1 else None)
    return order


def _link_node(
    links: Mapping[str, list[tuple[str, str | None]]],
    station: str,
    neighbor: str,
) -> str | None:
    for linked_station, trace_node_id in links[station]:
        if linked_station == neighbor:
            return trace_node_id
    return None


def _orient_single_station(
    station_members: list[str],
    member_endpoints: Mapping[str, MemberTraceEndpoints],
    signs: dict[str, int],
    diagnostics: list[str],
) -> tuple[str, ...]:
    """Orient the uses of one station against its first member."""

    reference = member_endpoints.get(station_members[0])
    if reference is None or reference.start_trace_node_id is None or reference.end_trace_node_id is None:
        for member in station_members:
            signs[member] = 0
            diagnostics.append(f"missing_endpoint_node:{member}")
        return ()
    forward = (reference.start_trace_node_id, reference.end_trace_node_id)
    for member in station_members:
        endpoints = member_endpoints.get(member)
        nodes = (endpoints.start_trace_node_id, endpoints.end_trace_node_id) if endpoints else (None, None)
        if nodes == forward:
            signs[member] = 1
        elif nodes == forward[::-1]:
            signs[member] = -1
        else:
            signs[member] = 0
            diagnostics.append(f"inconsistent_orientation:{member}")
    return forward


def _member_orientation(
    member_id: str,
    endpoints: MemberTraceEndpoints,
    previous_crossing_node: str | None,
    next_crossing_node: str | None,
    diagnostics: list[str],
) -> tuple[int, tuple[str, ...]]:
    start_node = endpoints.start_trace_node_id
    end_node = endpoints.end_trace_node_id
    if start_node is None or end_node is None:
        diagnostics.append(f"missing_endpoint_node:{member_id}")
        return 0, tuple(node for node in (start_node, end_node) if node is not None)

    if previous_crossing_node is None and next_crossing_node is None:
        return 1, (start_node, end_node)
    if previous_crossing_node is None:
        if next_crossing_node == end_node:
            return 1, (start_node, end_node)
        if next_crossing_node == start_node:
            return -1, (end_node, start_node)
    elif next_crossing_node is None:
        if previous_crossing_node == start_node:
            return 1, (start_node, end_node)
        if previous_crossing_node == end_node:
            return -1, (end_node, start_node)
    else:
        if previous_crossing_node == start_node and next_crossing_node == end_node:
            return 1, (start_node, end_node)
        if previous_crossing_node == end_node and next_crossing_node == start_node:
            return -1, (end_node, start_node)

    diagnostics.append(f"inconsistent_orientation:{member_id}")
    return 0, (start_node, end_node)


def _unordered_node_ids(
    ordered_member_ids: tuple[str, ...],
    endpoint_by_member_id: Mapping[str, MemberTraceEndpoints],
) -> list[str]:
    node_ids: set[str] = set()
    for member_id in ordered_member_ids:
        endpoints = endpoint_by_member_id.get(member_id)
        if endpoints is None:
            continue
        for trace_node_id in (endpoints.start_trace_node_id, endpoints.end_trace_node_id):
            if trace_node_id is not None:
                node_ids.add(trace_node_id)
    return sorted(node_ids)


def _missing_member_diagnostics(
    ordered_member_ids: tuple[str, ...],
    evidence_by_id: Mapping[str, PatchChainDirectionalEvidence],
    endpoint_by_member_id: Mapping[str, MemberTraceEndpoints],
) -> list[str]:
    diagnostics: list[str] = []
    for member_id in ordered_member_ids:
        if member_id not in evidence_by_id:
            diagnostics.append(f"missing_directional_evidence:{member_id}")
        endpoints = endpoint_by_member_id.get(member_id)
        if endpoints is None:
            diagnostics.append(f"missing_trace_nodes:{member_id}")
        elif endpoints.start_trace_node_id is None or endpoints.end_trace_node_id is None:
            diagnostics.append(f"partial_trace_nodes:{member_id}")
    return diagnostics


def _trace_member(
    member_id: str,
    family: ConnectedDirectionFamily,
    evidence_by_id: Mapping[str, PatchChainDirectionalEvidence],
    endpoint_by_member_id: Mapping[str, MemberTraceEndpoints],
    station_rail: _StationRail,
    ordered_member_ids: tuple[str, ...],
) -> ScaffoldTraceMember:
    evidence = evidence_by_id[member_id]
    member_map = family.member_map[member_id]
    endpoints = endpoint_by_member_id.get(member_id, MemberTraceEndpoints(None, None))
    member_index = ordered_member_ids.index(member_id)
    previous_index = (
        _crossing_index(station_rail, ordered_member_ids[member_index - 1], member_id)
        if member_index > 0
        else None
    )
    next_index = (
        _crossing_index(station_rail, member_id, ordered_member_ids[member_index + 1])
        if member_index + 1 < len(ordered_member_ids)
        else None
    )
    return ScaffoldTraceMember(
        directional_evidence_id=member_id,
        patch_id=evidence.patch_id,
        patch_chain_id=evidence.patch_chain_id,
        scaffold_edge_id=member_map[1],
        start_trace_node_id=endpoints.start_trace_node_id,
        end_trace_node_id=endpoints.end_trace_node_id,
        start_vertex_id=member_map[2],
        end_vertex_id=member_map[3],
        previous_crossing_index=previous_index,
        next_crossing_index=next_index,
        confidence=evidence.confidence,
    )


def _crossing_index(station_rail: _StationRail, first_id: str, second_id: str) -> int | None:
    direct = station_rail.member_crossing_index.get(frozenset((first_id, second_id)))
    if direct is not None:
        return direct
    first_station = station_rail.station_of.get(first_id)
    second_station = station_rail.station_of.get(second_id)
    if first_station is None or second_station is None or first_station == second_station:
        return None
    return station_rail.station_link_index.get(frozenset((first_station, second_station)))


def _confidence(
    family: ConnectedDirectionFamily,
    diagnostics: list[str],
    is_branch_ambiguous: bool,
    is_closed_loop: bool,
) -> float:
    if diagnostics:
        return min(family.confidence, 0.5)
    if is_branch_ambiguous or is_closed_loop:
        return min(family.confidence, 0.75)
    return family.confidence


def _trace_evidence(
    family: ConnectedDirectionFamily,
    diagnostics: list[str],
    is_branch_ambiguous: bool,
    is_closed_loop: bool,
) -> Evidence:
    return Evidence(
        source="layer_3_relations.scaffold_rails",
        summary="ScaffoldTrace v1 ordered through stations of ConnectedDirectionFamily members",
        data={
            "policy": POLICY_NAME,
            "direction_family_id": family.id,
            "member_count": len(family.member_directional_evidence_ids),
            "crossing_count": len(family.crossing_records),
            "branch_ambiguous": is_branch_ambiguous,
            "closed_loop": is_closed_loop,
            "diagnostic_count": len(diagnostics),
        },
    )


def _rail_evidence(
    family: ConnectedDirectionFamily,
    diagnostics: list[str],
    is_consumable: bool,
    is_closed_loop: bool,
) -> Evidence:
    return Evidence(
        source="layer_3_relations.scaffold_rails",
        summary="ScaffoldRail v1 direction-stability view over ScaffoldTrace",
        data={
            "policy": POLICY_NAME,
            "direction_family_id": family.id,
            "consumable_by_g5a": is_consumable,
            "closed_loop": is_closed_loop,
            "diagnostic_count": len(diagnostics),
        },
    )
