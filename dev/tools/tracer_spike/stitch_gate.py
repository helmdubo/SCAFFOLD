"""
Would-be-interior stitch gate for tracer spike v3.

This is disposable consumer tooling outside scaffold_core. It derives the
pairwise stitch test set from Layer 1 topology and Layer 2 raw vertex facts.
"""

from __future__ import annotations

from collections import defaultdict
from math import pi
from typing import Any


INTERIOR_ANGLE_BASELINE = 2.0 * pi


def build_stitch_gate_context(topology: Any, relations: Any, self_seam_chain_ids: set[str]) -> dict[str, Any]:
    cut_chain_ids = {str(adjacency.chain_id) for adjacency in relations.patch_adjacencies.values()}
    cut_chain_ids.update(str(chain_id) for chain_id in self_seam_chain_ids)
    vertex_source_ids = _vertex_source_ids(topology)
    endpoint_cut_chains_by_source = defaultdict(set)
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


def decide_stitch(
    topology: Any,
    geometry: Any,
    adjacency: Any,
    self_seam_chain_ids: set[str],
    gate_context: dict[str, Any],
    tolerance: float,
) -> tuple[bool, str, dict[str, Any]]:
    gate = _empty_gate()
    chain_id = str(adjacency.chain_id)
    if chain_id in self_seam_chain_ids:
        return False, "SEAM_SELF chains always remain island boundaries", gate

    chain = topology.chains[adjacency.chain_id]
    chain_facts = geometry.chain_facts.get(chain.id)
    if chain_facts is None:
        return False, "missing ChainGeometryFacts.source_vertex_run", gate

    for vertex_id in _mid_chain_vertex_ids(chain_facts, gate_context):
        reason = _add_test_vertex(geometry, vertex_id, gate)
        if reason is not None:
            return False, reason, gate

    for vertex_id in _unique_endpoint_vertex_ids(chain):
        exclusion_reason = _endpoint_exclusion_reason(geometry, vertex_id, chain_id, gate_context)
        if exclusion_reason is not None:
            gate["excluded_endpoint_vertex_ids"].append(str(vertex_id))
            gate["excluded_endpoint_reasons"][str(vertex_id)] = exclusion_reason
            continue
        reason = _add_test_vertex(geometry, vertex_id, gate)
        if reason is not None:
            return False, reason, gate

    if not gate["vertex_angle_defects"]:
        return True, "no would-be interior vertices after endpoint exclusions", gate
    if all(abs(value) <= tolerance for value in gate["vertex_angle_defects"].values()):
        return True, "all would-be interior vertices have near-zero 2pi angle defect", gate
    return False, "would-be interior angle defect exceeds stitch limit", gate


def _empty_gate() -> dict[str, Any]:
    return {
        "would_be_interior_vertex_ids": [],
        "excluded_endpoint_vertex_ids": [],
        "excluded_endpoint_reasons": {},
        "vertex_angle_defects": {},
        "vertex_interior_angle_sums": {},
    }


def _vertex_source_ids(topology: Any) -> dict[str, tuple[str, ...]]:
    return {
        str(vertex.id): tuple(str(source_vertex_id) for source_vertex_id in vertex.source_vertex_ids)
        for vertex in topology.vertices.values()
    }


def _vertex_ids_by_source(topology: Any) -> dict[str, tuple[Any, ...]]:
    rows = defaultdict(list)
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
            key = str(vertex_id)
            if key in seen:
                continue
            seen.add(key)
            vertex_ids.append(vertex_id)
    return tuple(vertex_ids)


def _unique_endpoint_vertex_ids(chain: Any) -> tuple[Any, ...]:
    vertex_ids = []
    seen = set()
    for vertex_id in (chain.start_vertex_id, chain.end_vertex_id):
        key = str(vertex_id)
        if key in seen:
            continue
        seen.add(key)
        vertex_ids.append(vertex_id)
    return tuple(vertex_ids)


def _endpoint_exclusion_reason(
    geometry: Any,
    vertex_id: Any,
    current_chain_id: str,
    gate_context: dict[str, Any],
) -> str | None:
    facts = geometry.vertex_facts.get(vertex_id)
    if facts is None:
        return None
    if facts.is_boundary:
        return "mesh_or_selection_boundary"
    other_cut_chains = sorted(
        {
            chain_id
            for source_vertex_id in gate_context["vertex_source_ids"].get(str(vertex_id), ())
            for chain_id in gate_context["endpoint_cut_chains_by_source"].get(source_vertex_id, ())
            if chain_id != current_chain_id
        }
    )
    if other_cut_chains:
        return "remaining_cut_incidence:" + ",".join(other_cut_chains)
    return None


def _add_test_vertex(geometry: Any, vertex_id: Any, gate: dict[str, Any]) -> str | None:
    facts = geometry.vertex_facts.get(vertex_id)
    gate["would_be_interior_vertex_ids"].append(str(vertex_id))
    if facts is None:
        gate["vertex_angle_defects"][str(vertex_id)] = None
        return "missing VertexGeometryFacts.interior_angle_sum"
    gate["vertex_interior_angle_sums"][str(vertex_id)] = facts.interior_angle_sum
    gate["vertex_angle_defects"][str(vertex_id)] = INTERIOR_ANGLE_BASELINE - facts.interior_angle_sum
    return None
