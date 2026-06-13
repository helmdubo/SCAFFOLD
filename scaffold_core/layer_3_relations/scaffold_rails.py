"""
Layer: 3 - Relations

Rules:
- Build ScaffoldTrace and ScaffoldRail evidence views from existing Layer 3 records.
- Do not mutate topology, ScaffoldGraph, ConnectedDirectionFamily, or directional evidence.
- Do not choose paths through branches or open closed loops without an explicit structural cut.
- Do not derive coordinates, pins, packing, feature labels, world roles, or runtime behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from scaffold_core.core.evidence import Evidence
from scaffold_core.layer_3_relations.model import (
    ConnectedDirectionFamily,
    CrossingRecord,
    PatchChainDirectionalEvidence,
    PatchChainEndpointRole,
    RunEndpointJunction,
    ScaffoldRail,
    ScaffoldTrace,
    ScaffoldTraceMember,
)


POLICY_NAME = "scaffold_trace_rail_v0"


@dataclass(frozen=True)
class _MemberEndpoint:
    start_trace_node_id: str | None
    end_trace_node_id: str | None


def build_scaffold_traces_and_rails(
    direction_families: tuple[ConnectedDirectionFamily, ...],
    directional_evidence_items: tuple[PatchChainDirectionalEvidence, ...],
    run_endpoint_junctions: tuple[RunEndpointJunction, ...],
) -> tuple[tuple[ScaffoldTrace, ...], tuple[ScaffoldRail, ...]]:
    """Build ordered trace/rail evidence from ConnectedDirectionFamily records."""

    evidence_by_id = {item.id: item for item in directional_evidence_items}
    endpoint_by_member_id = _member_endpoints(run_endpoint_junctions)
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


def _build_family_trace_and_rail(
    index: int,
    family: ConnectedDirectionFamily,
    evidence_by_id: Mapping[str, PatchChainDirectionalEvidence],
    endpoint_by_member_id: Mapping[str, _MemberEndpoint],
) -> tuple[ScaffoldTrace, ScaffoldRail]:
    member_graph, crossing_index_by_pair, crossing_node_by_pair, diagnostics = _family_member_graph(family)
    branch_records = _branch_records(family, member_graph, endpoint_by_member_id)
    is_branch_ambiguous = bool(branch_records)
    is_closed_loop = _is_closed_loop(family.member_directional_evidence_ids, member_graph)
    loop_ambiguity_records = (
        {"closed_loop": tuple(sorted(family.member_directional_evidence_ids))}
        if is_closed_loop
        else {}
    )

    ordered_member_ids = _ordered_member_ids(family, member_graph, is_branch_ambiguous, is_closed_loop)
    ordered_node_ids, orientation_sign_by_member, orientation_diagnostics = _rail_orientation(
        ordered_member_ids,
        endpoint_by_member_id,
        crossing_node_by_pair,
        is_branch_ambiguous,
        is_closed_loop,
    )
    diagnostics.extend(orientation_diagnostics)
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
            crossing_index_by_pair,
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


def _member_endpoints(
    run_endpoint_junctions: tuple[RunEndpointJunction, ...],
) -> dict[str, _MemberEndpoint]:
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
        member_id: _MemberEndpoint(starts.get(member_id), ends.get(member_id))
        for member_id in sorted(set(starts) | set(ends))
    }


def _family_member_graph(
    family: ConnectedDirectionFamily,
) -> tuple[dict[str, set[str]], dict[frozenset[str], int], dict[frozenset[str], str | None], list[str]]:
    graph = {member_id: set() for member_id in family.member_directional_evidence_ids}
    crossing_index_by_pair: dict[frozenset[str], int] = {}
    crossing_node_by_pair: dict[frozenset[str], str | None] = {}
    diagnostics: list[str] = []
    for index, crossing in enumerate(family.crossing_records):
        first_id = crossing.first_directional_evidence_id
        second_id = crossing.second_directional_evidence_id
        if first_id not in graph or second_id not in graph:
            continue
        graph[first_id].add(second_id)
        graph[second_id].add(first_id)
        pair = frozenset((first_id, second_id))
        if pair in crossing_index_by_pair:
            diagnostics.append(f"multiple_crossings:{first_id}:{second_id}")
            continue
        crossing_index_by_pair[pair] = index
        crossing_node_by_pair[pair] = _crossing_trace_node_id(crossing)
        if crossing_node_by_pair[pair] is None:
            diagnostics.append(f"non_node_crossing:{first_id}:{second_id}:{crossing.kind}")
    return graph, crossing_index_by_pair, crossing_node_by_pair, diagnostics


def _crossing_trace_node_id(crossing: CrossingRecord) -> str | None:
    return crossing.scaffold_node_id or crossing.run_endpoint_junction_id


def _branch_records(
    family: ConnectedDirectionFamily,
    member_graph: Mapping[str, set[str]],
    endpoint_by_member_id: Mapping[str, _MemberEndpoint],
) -> dict[str, tuple[str, ...]]:
    records = {
        record_id: tuple(neighbor_ids)
        for record_id, neighbor_ids in family.branch_records.items()
    }
    for member_id, neighbor_ids in sorted(member_graph.items()):
        if len(neighbor_ids) > 2:
            records[f"member:{member_id}"] = tuple(sorted(neighbor_ids))

    incident_members_by_node: dict[str, set[str]] = {}
    for member_id in family.member_directional_evidence_ids:
        endpoints = endpoint_by_member_id.get(member_id)
        if endpoints is None:
            continue
        for trace_node_id in (endpoints.start_trace_node_id, endpoints.end_trace_node_id):
            if trace_node_id is not None:
                incident_members_by_node.setdefault(trace_node_id, set()).add(member_id)
    for trace_node_id, member_ids in sorted(incident_members_by_node.items()):
        if len(member_ids) > 2:
            records[f"trace_node:{trace_node_id}"] = tuple(sorted(member_ids))
    return records


def _is_closed_loop(member_ids: tuple[str, ...], member_graph: Mapping[str, set[str]]) -> bool:
    if len(member_ids) <= 1:
        return False
    if not member_graph:
        return False
    return all(len(member_graph.get(member_id, set())) == 2 for member_id in member_ids)


def _ordered_member_ids(
    family: ConnectedDirectionFamily,
    member_graph: Mapping[str, set[str]],
    is_branch_ambiguous: bool,
    is_closed_loop: bool,
) -> tuple[str, ...]:
    if is_branch_ambiguous or is_closed_loop or not member_graph:
        return tuple(family.ordered_member_directional_evidence_ids)

    leaf_ids = sorted(member_id for member_id, neighbors in member_graph.items() if len(neighbors) <= 1)
    if not leaf_ids:
        return tuple(family.ordered_member_directional_evidence_ids)

    ordered: list[str] = []
    previous_id: str | None = None
    current_id: str | None = leaf_ids[0]
    while current_id is not None and current_id not in ordered:
        ordered.append(current_id)
        candidates = sorted(member_graph[current_id] - ({previous_id} if previous_id else set()))
        previous_id, current_id = current_id, candidates[0] if len(candidates) == 1 else None
    ordered.extend(member_id for member_id in family.ordered_member_directional_evidence_ids if member_id not in ordered)
    return tuple(ordered)


def _rail_orientation(
    ordered_member_ids: tuple[str, ...],
    endpoint_by_member_id: Mapping[str, _MemberEndpoint],
    crossing_node_by_pair: Mapping[frozenset[str], str | None],
    is_branch_ambiguous: bool,
    is_closed_loop: bool,
) -> tuple[list[str], dict[str, int], list[str]]:
    if is_branch_ambiguous or is_closed_loop:
        return _unordered_node_ids(ordered_member_ids, endpoint_by_member_id), {
            member_id: 0 for member_id in ordered_member_ids
        }, []

    if not ordered_member_ids:
        return [], {}, []

    diagnostics: list[str] = []
    signs: dict[str, int] = {}
    ordered_nodes: list[str] = []
    previous_crossing_node: str | None = None

    for index, member_id in enumerate(ordered_member_ids):
        endpoints = endpoint_by_member_id.get(member_id)
        if endpoints is None:
            signs[member_id] = 0
            diagnostics.append(f"missing_endpoints:{member_id}")
            continue
        next_crossing_node = _adjacent_crossing_node(
            ordered_member_ids,
            index,
            crossing_node_by_pair,
            forward=True,
        )
        previous_crossing_node = previous_crossing_node or _adjacent_crossing_node(
            ordered_member_ids,
            index,
            crossing_node_by_pair,
            forward=False,
        )
        sign, member_nodes = _member_orientation(
            member_id,
            endpoints,
            previous_crossing_node,
            next_crossing_node,
            diagnostics,
        )
        signs[member_id] = sign
        for trace_node_id in member_nodes:
            if not ordered_nodes or ordered_nodes[-1] != trace_node_id:
                ordered_nodes.append(trace_node_id)
        previous_crossing_node = next_crossing_node

    return ordered_nodes, signs, diagnostics


def _adjacent_crossing_node(
    ordered_member_ids: tuple[str, ...],
    index: int,
    crossing_node_by_pair: Mapping[frozenset[str], str | None],
    *,
    forward: bool,
) -> str | None:
    other_index = index + 1 if forward else index - 1
    if other_index < 0 or other_index >= len(ordered_member_ids):
        return None
    return crossing_node_by_pair.get(frozenset((ordered_member_ids[index], ordered_member_ids[other_index])))


def _member_orientation(
    member_id: str,
    endpoints: _MemberEndpoint,
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
    endpoint_by_member_id: Mapping[str, _MemberEndpoint],
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
    endpoint_by_member_id: Mapping[str, _MemberEndpoint],
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
    endpoint_by_member_id: Mapping[str, _MemberEndpoint],
    crossing_index_by_pair: Mapping[frozenset[str], int],
    ordered_member_ids: tuple[str, ...],
) -> ScaffoldTraceMember:
    evidence = evidence_by_id[member_id]
    member_map = family.member_map[member_id]
    endpoints = endpoint_by_member_id.get(member_id, _MemberEndpoint(None, None))
    member_index = ordered_member_ids.index(member_id)
    previous_index = (
        crossing_index_by_pair.get(frozenset((ordered_member_ids[member_index - 1], member_id)))
        if member_index > 0
        else None
    )
    next_index = (
        crossing_index_by_pair.get(frozenset((member_id, ordered_member_ids[member_index + 1])))
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
        summary="ScaffoldTrace v0 derived from ConnectedDirectionFamily ordering",
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
        summary="ScaffoldRail v0 direction-stability view over ScaffoldTrace",
        data={
            "policy": POLICY_NAME,
            "direction_family_id": family.id,
            "consumable_by_g5a": is_consumable,
            "closed_loop": is_closed_loop,
            "diagnostic_count": len(diagnostics),
        },
    )
