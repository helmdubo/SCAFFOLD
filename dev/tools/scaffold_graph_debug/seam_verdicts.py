"""Debug-side Level A seam verdicts for ScaffoldGraph overlay v2."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import pi
from typing import Any


INTERIOR_ANGLE_BASELINE = 2.0 * pi
ANGLE_DEFECT_TOLERANCE = 1.0e-5


@dataclass(frozen=True)
class SeamVerdict:
    id: str
    chain_id: str
    patch_ids: tuple[str, ...]
    status: str
    polyline: tuple[tuple[float, float, float], ...]
    failing_vertex_ids: tuple[str, ...]
    failing_positions: tuple[tuple[float, float, float], ...]
    would_be_interior_vertex_ids: tuple[str, ...]
    excluded_endpoint_vertex_ids: tuple[str, ...]
    vertex_angle_defects: tuple[tuple[str, float | None], ...]
    reason: str


def build_seam_verdicts(topology: Any, geometry: Any, relations: Any) -> tuple[SeamVerdict, ...]:
    """Classify shared patch-adjacency chains as sewable or cut for debug display."""

    self_seam_chain_ids = {
        str(junction.matched_chain_id)
        for junction in relations.scaffold_junctions
        if junction.kind.value == "SELF_SEAM" and junction.matched_chain_id is not None
    }
    gate_context = _build_gate_context(topology, relations, self_seam_chain_ids)
    verdicts = [
        _verdict_for_adjacency(topology, geometry, adjacency, self_seam_chain_ids, gate_context)
        for adjacency in sorted(relations.patch_adjacencies.values(), key=lambda item: item.id)
    ]
    return tuple(verdicts)


def _build_gate_context(topology: Any, relations: Any, self_seam_chain_ids: set[str]) -> dict[str, Any]:
    cut_chain_ids = {str(adjacency.chain_id) for adjacency in relations.patch_adjacencies.values()}
    cut_chain_ids.update(self_seam_chain_ids)
    vertex_source_ids = _vertex_source_ids(topology)
    endpoint_cut_chains_by_source: dict[str, set[str]] = defaultdict(set)
    for chain in topology.chains.values():
        if str(chain.id) not in cut_chain_ids:
            continue
        for vertex_id in (chain.start_vertex_id, chain.end_vertex_id):
            for source_vertex_id in vertex_source_ids.get(str(vertex_id), ()):
                endpoint_cut_chains_by_source[source_vertex_id].add(str(chain.id))
    return {
        "cut_chain_ids": cut_chain_ids,
        "endpoint_cut_chains_by_source": {
            source_vertex_id: frozenset(chain_ids)
            for source_vertex_id, chain_ids in endpoint_cut_chains_by_source.items()
        },
        "vertex_ids_by_source": _vertex_ids_by_source(topology),
        "vertex_source_ids": vertex_source_ids,
    }


def _verdict_for_adjacency(
    topology: Any,
    geometry: Any,
    adjacency: Any,
    self_seam_chain_ids: set[str],
    gate_context: dict[str, Any],
) -> SeamVerdict:
    chain_id = str(adjacency.chain_id)
    gate = _empty_gate()
    chain = topology.chains[adjacency.chain_id]
    chain_facts = geometry.chain_facts.get(chain.id)
    reason = ""
    if chain_id in self_seam_chain_ids:
        status = "CUT"
        reason = "SEAM_SELF chains stay cut"
    elif chain_facts is None:
        status = "CUT"
        reason = "missing ChainGeometryFacts.source_vertex_run"
    else:
        for vertex_id in _mid_chain_vertex_ids(chain_facts, gate_context):
            reason = _add_test_vertex(geometry, vertex_id, gate) or reason
        for vertex_id in _unique_endpoint_vertex_ids(chain):
            exclusion_reason = _endpoint_exclusion_reason(geometry, vertex_id, chain_id, gate_context)
            if exclusion_reason is not None:
                gate["excluded_endpoint_vertex_ids"].append(str(vertex_id))
                continue
            reason = _add_test_vertex(geometry, vertex_id, gate) or reason
        status, reason = _status_from_gate(gate, reason)

    failing_vertex_ids = tuple(
        vertex_id
        for vertex_id, defect in gate["vertex_angle_defects"].items()
        if defect is None or abs(defect) > ANGLE_DEFECT_TOLERANCE
    )
    return SeamVerdict(
        id=f"seam_verdict:{chain_id}",
        chain_id=chain_id,
        patch_ids=tuple(sorted((str(adjacency.first_patch_id), str(adjacency.second_patch_id)))),
        status=status,
        polyline=_chain_polyline(geometry, adjacency.chain_id),
        failing_vertex_ids=failing_vertex_ids,
        failing_positions=tuple(
            _vertex_position(geometry, vertex_id)
            for vertex_id in failing_vertex_ids
            if _vertex_position(geometry, vertex_id) is not None
        ),
        would_be_interior_vertex_ids=tuple(gate["would_be_interior_vertex_ids"]),
        excluded_endpoint_vertex_ids=tuple(gate["excluded_endpoint_vertex_ids"]),
        vertex_angle_defects=tuple(sorted(gate["vertex_angle_defects"].items())),
        reason=reason,
    )


def _status_from_gate(gate: dict[str, Any], reason: str) -> tuple[str, str]:
    if reason:
        return "CUT", reason
    defects = gate["vertex_angle_defects"]
    if not defects:
        return "SEWABLE", "no would-be interior vertices after endpoint exclusions"
    if all(value is not None and abs(value) <= ANGLE_DEFECT_TOLERANCE for value in defects.values()):
        return "SEWABLE", "all would-be interior vertices have near-zero 2pi angle defect"
    return "CUT", "would-be interior angle defect exceeds stitch limit"


def _empty_gate() -> dict[str, Any]:
    return {
        "would_be_interior_vertex_ids": [],
        "excluded_endpoint_vertex_ids": [],
        "vertex_angle_defects": {},
    }


def _vertex_source_ids(topology: Any) -> dict[str, tuple[str, ...]]:
    return {
        str(vertex.id): tuple(str(source_vertex_id) for source_vertex_id in vertex.source_vertex_ids)
        for vertex in topology.vertices.values()
    }


def _vertex_ids_by_source(topology: Any) -> dict[str, tuple[Any, ...]]:
    rows: dict[str, list[Any]] = defaultdict(list)
    for vertex in topology.vertices.values():
        for source_vertex_id in vertex.source_vertex_ids:
            rows[str(source_vertex_id)].append(vertex.id)
    return {
        source_vertex_id: tuple(sorted(vertex_ids, key=str))
        for source_vertex_id, vertex_ids in rows.items()
    }


def _mid_chain_vertex_ids(chain_facts: Any, gate_context: dict[str, Any]) -> tuple[Any, ...]:
    source_run = tuple(str(source_vertex_id) for source_vertex_id in chain_facts.source_vertex_run)
    if len(source_run) <= 2:
        return ()
    vertex_ids = []
    seen = set()
    for source_vertex_id in source_run[1:-1]:
        for vertex_id in gate_context["vertex_ids_by_source"].get(source_vertex_id, ()):
            if str(vertex_id) in seen:
                continue
            seen.add(str(vertex_id))
            vertex_ids.append(vertex_id)
    return tuple(vertex_ids)


def _unique_endpoint_vertex_ids(chain: Any) -> tuple[Any, ...]:
    vertex_ids = []
    seen = set()
    for vertex_id in (chain.start_vertex_id, chain.end_vertex_id):
        if str(vertex_id) in seen:
            continue
        seen.add(str(vertex_id))
        vertex_ids.append(vertex_id)
    return tuple(vertex_ids)


def _endpoint_exclusion_reason(
    geometry: Any,
    vertex_id: Any,
    current_chain_id: str,
    gate_context: dict[str, Any],
) -> str | None:
    facts = geometry.vertex_facts.get(vertex_id)
    if facts is not None and facts.is_boundary:
        return "mesh_or_selection_boundary"
    other_cut_chains = {
        chain_id
        for source_vertex_id in gate_context["vertex_source_ids"].get(str(vertex_id), ())
        for chain_id in gate_context["endpoint_cut_chains_by_source"].get(source_vertex_id, ())
        if chain_id != current_chain_id
    }
    return "remaining_cut_incidence" if other_cut_chains else None


def _add_test_vertex(geometry: Any, vertex_id: Any, gate: dict[str, Any]) -> str | None:
    facts = geometry.vertex_facts.get(vertex_id)
    gate["would_be_interior_vertex_ids"].append(str(vertex_id))
    if facts is None:
        gate["vertex_angle_defects"][str(vertex_id)] = None
        return "missing VertexGeometryFacts.interior_angle_sum"
    gate["vertex_angle_defects"][str(vertex_id)] = INTERIOR_ANGLE_BASELINE - facts.interior_angle_sum
    return None


def _chain_polyline(geometry: Any, chain_id: Any) -> tuple[tuple[float, float, float], ...]:
    chain_facts = geometry.chain_facts.get(chain_id)
    if chain_facts is None or not chain_facts.segments:
        return ()
    points = [chain_facts.segments[0].start_position]
    points.extend(segment.end_position for segment in chain_facts.segments)
    return tuple(points)


def _vertex_position(geometry: Any, vertex_id: str) -> tuple[float, float, float] | None:
    for facts_id, facts in geometry.vertex_facts.items():
        if str(facts_id) == vertex_id:
            return facts.position
    return None
