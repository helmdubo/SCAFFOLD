"""
Layer: 3 - Relations

Rules:
- Build evidence-only junctions for PatchChainDirectionalEvidence run endpoints.
- Preserve Layer 1 Vertex, Chain, PatchChain, ScaffoldNode and ScaffoldEdge identity.
- Do not choose traces, rails, circuits, continuations, runtime behavior or UV data.
"""

from __future__ import annotations

from scaffold_core.core.evidence import Evidence
from scaffold_core.ids import SourceVertexId, VertexId
from scaffold_core.layer_1_topology.model import PatchChain, SurfaceModel
from scaffold_core.layer_1_topology.queries import patch_chain_vertices
from scaffold_core.layer_2_geometry.facts import ChainGeometryFacts, GeometryFactSnapshot
from scaffold_core.layer_3_relations.model import (
    PatchChainDirectionalEvidence,
    PatchChainEndpointRole,
    RunEndpointJunction,
    ScaffoldNode,
)


POLICY_NAME = "run_endpoint_junction_v0"


def build_run_endpoint_junctions(
    topology: SurfaceModel,
    geometry: GeometryFactSnapshot,
    directional_evidence_items: tuple[PatchChainDirectionalEvidence, ...],
    scaffold_nodes: tuple[ScaffoldNode, ...],
) -> tuple[RunEndpointJunction, ...]:
    """Build grouped junction evidence for every directional-run endpoint."""

    source_vertex_to_vertices = _source_vertex_to_vertices(topology)
    topology_vertex_ids_by_key: dict[tuple[str, str], set[VertexId]] = {}
    source_vertex_id_by_key: dict[tuple[str, str], SourceVertexId | None] = {}
    occurrences_by_key: dict[tuple[str, str], list[tuple[str, PatchChainEndpointRole]]] = {}
    patch_ids_by_key: dict[tuple[str, str], set] = {}
    confidence_by_key: dict[tuple[str, str], list[float]] = {}

    for directional_evidence in sorted(directional_evidence_items, key=lambda item: item.id):
        for role in (PatchChainEndpointRole.START, PatchChainEndpointRole.END):
            vertex_ids, source_vertex_id = _endpoint_vertices(
                topology,
                geometry,
                directional_evidence,
                role,
                source_vertex_to_vertices,
            )
            key = _group_key(source_vertex_id, vertex_ids[0])
            topology_vertex_ids_by_key.setdefault(key, set()).update(vertex_ids)
            source_vertex_id_by_key[key] = source_vertex_id
            occurrences_by_key.setdefault(key, []).append((directional_evidence.id, role))
            patch_ids_by_key.setdefault(key, set()).add(directional_evidence.patch_id)
            confidence_by_key.setdefault(key, []).append(directional_evidence.confidence)

    junctions = [
        _junction(
            key,
            topology_vertex_ids_by_key[key],
            source_vertex_id_by_key[key],
            occurrences_by_key[key],
            patch_ids_by_key[key],
            confidence_by_key[key],
            scaffold_nodes,
        )
        for key in topology_vertex_ids_by_key
    ]
    return tuple(sorted(junctions, key=lambda item: item.id))


def _endpoint_vertices(
    topology: SurfaceModel,
    geometry: GeometryFactSnapshot,
    directional_evidence: PatchChainDirectionalEvidence,
    role: PatchChainEndpointRole,
    source_vertex_to_vertices: dict[SourceVertexId, tuple[VertexId, ...]],
) -> tuple[tuple[VertexId, ...], SourceVertexId | None]:
    patch_chain = topology.patch_chains[directional_evidence.patch_chain_id]
    chain_facts = geometry.chain_facts.get(directional_evidence.parent_chain_id)
    if chain_facts is not None:
        resolved = _endpoint_from_chain_walk(
            topology,
            chain_facts,
            patch_chain,
            directional_evidence,
            role,
            source_vertex_to_vertices,
        )
        if resolved is not None:
            return resolved

    source_vertex_id = (
        directional_evidence.start_source_vertex_id
        if role is PatchChainEndpointRole.START
        else directional_evidence.end_source_vertex_id
    )
    return (
        _vertices_for_source(
            topology,
            patch_chain,
            role,
            source_vertex_id,
            source_vertex_to_vertices,
        ),
        source_vertex_id,
    )


def _endpoint_from_chain_walk(
    topology: SurfaceModel,
    chain_facts: ChainGeometryFacts,
    patch_chain: PatchChain,
    directional_evidence: PatchChainDirectionalEvidence,
    role: PatchChainEndpointRole,
    source_vertex_to_vertices: dict[SourceVertexId, tuple[VertexId, ...]],
) -> tuple[tuple[VertexId, ...], SourceVertexId | None] | None:
    source_path = _source_path(chain_facts)
    segment_indices = directional_evidence.segment_indices
    if not source_path or not segment_indices:
        return None
    if len(source_path) != len(chain_facts.segments) + 1:
        return None
    if not _segment_indices_are_contiguous(segment_indices):
        return None

    reversed_path = _patch_chain_reverses_source_path(topology, patch_chain, source_path)
    first_segment_index = segment_indices[0]
    last_segment_index = segment_indices[-1]
    if first_segment_index < 0 or last_segment_index >= len(chain_facts.segments):
        return None

    if reversed_path:
        oriented_path = tuple(reversed(source_path))
        start_position = len(chain_facts.segments) - (last_segment_index + 1)
        end_position = len(chain_facts.segments) - first_segment_index
    else:
        oriented_path = source_path
        start_position = first_segment_index
        end_position = last_segment_index + 1

    endpoint_position = start_position if role is PatchChainEndpointRole.START else end_position
    source_vertex_id = oriented_path[endpoint_position]
    vertex_ids = _vertices_for_oriented_position(
        topology,
        patch_chain,
        endpoint_position,
        len(chain_facts.segments),
        source_vertex_id,
        source_vertex_to_vertices,
    )
    return vertex_ids, source_vertex_id


def _source_path(chain_facts: ChainGeometryFacts) -> tuple[SourceVertexId, ...]:
    if chain_facts.source_vertex_run:
        return chain_facts.source_vertex_run
    if not chain_facts.segments:
        return ()
    path = [chain_facts.segments[0].start_source_vertex_id]
    path.extend(segment.end_source_vertex_id for segment in chain_facts.segments)
    return tuple(path)


def _segment_indices_are_contiguous(segment_indices: tuple[int, ...]) -> bool:
    return all(
        segment_indices[index] + 1 == segment_indices[index + 1]
        for index in range(len(segment_indices) - 1)
    )


def _patch_chain_reverses_source_path(
    topology: SurfaceModel,
    patch_chain: PatchChain,
    source_path: tuple[SourceVertexId, ...],
) -> bool:
    start_vertex_id, end_vertex_id = patch_chain_vertices(topology, patch_chain.id)
    start_sources = set(topology.vertices[start_vertex_id].source_vertex_ids)
    end_sources = set(topology.vertices[end_vertex_id].source_vertex_ids)
    source_start = source_path[0]
    source_end = source_path[-1]

    if source_start == source_end and source_start in start_sources and source_end in end_sources:
        return patch_chain.orientation_sign == -1
    if source_start in start_sources and source_end in end_sources:
        return False
    if source_end in start_sources and source_start in end_sources:
        return True
    return patch_chain.orientation_sign == -1


def _vertices_for_oriented_position(
    topology: SurfaceModel,
    patch_chain: PatchChain,
    endpoint_position: int,
    segment_count: int,
    source_vertex_id: SourceVertexId,
    source_vertex_to_vertices: dict[SourceVertexId, tuple[VertexId, ...]],
) -> tuple[VertexId, ...]:
    start_vertex_id, end_vertex_id = patch_chain_vertices(topology, patch_chain.id)
    if endpoint_position == 0:
        return (start_vertex_id,)
    if endpoint_position == segment_count:
        return (end_vertex_id,)
    return _vertices_for_source(
        topology,
        patch_chain,
        None,
        source_vertex_id,
        source_vertex_to_vertices,
    )


def _vertices_for_source(
    topology: SurfaceModel,
    patch_chain: PatchChain,
    role: PatchChainEndpointRole | None,
    source_vertex_id: SourceVertexId,
    source_vertex_to_vertices: dict[SourceVertexId, tuple[VertexId, ...]],
) -> tuple[VertexId, ...]:
    start_vertex_id, end_vertex_id = patch_chain_vertices(topology, patch_chain.id)
    start_sources = topology.vertices[start_vertex_id].source_vertex_ids
    end_sources = topology.vertices[end_vertex_id].source_vertex_ids
    if role is PatchChainEndpointRole.START and source_vertex_id in start_sources:
        return (start_vertex_id,)
    if role is PatchChainEndpointRole.END and source_vertex_id in end_sources:
        return (end_vertex_id,)

    candidates = source_vertex_to_vertices.get(source_vertex_id, ())
    if len(candidates) == 1:
        return (candidates[0],)
    patch_candidates = tuple(
        vertex_id
        for vertex_id in candidates
        if f":patch_chain:{patch_chain.patch_id}:" in str(vertex_id)
    )
    if patch_candidates:
        return patch_candidates
    canonical_vertex_id = VertexId(f"vertex:{source_vertex_id}")
    if canonical_vertex_id in candidates:
        return (canonical_vertex_id,)
    if not candidates:
        raise ValueError(
            "RunEndpointJunction endpoint has no topology Vertex occurrence for "
            f"{source_vertex_id} on {patch_chain.id}"
        )
    raise ValueError(
        "RunEndpointJunction endpoint maps ambiguously to topology Vertex occurrences for "
        f"{source_vertex_id} on {patch_chain.id}: "
        + ", ".join(str(vertex_id) for vertex_id in candidates)
    )


def _source_vertex_to_vertices(topology: SurfaceModel) -> dict[SourceVertexId, tuple[VertexId, ...]]:
    vertices_by_source: dict[SourceVertexId, list[VertexId]] = {}
    for vertex in topology.vertices.values():
        for source_vertex_id in vertex.source_vertex_ids:
            vertices_by_source.setdefault(source_vertex_id, []).append(vertex.id)
    return {
        source_vertex_id: tuple(sorted(vertex_ids, key=str))
        for source_vertex_id, vertex_ids in vertices_by_source.items()
    }


def _group_key(
    source_vertex_id: SourceVertexId | None,
    vertex_id: VertexId,
) -> tuple[str, str]:
    if source_vertex_id is not None:
        return "source", str(source_vertex_id)
    return "vertex", str(vertex_id)


def _junction(
    key: tuple[str, str],
    topology_vertex_ids: set[VertexId],
    source_vertex_id: SourceVertexId | None,
    occurrences: list[tuple[str, PatchChainEndpointRole]],
    patch_ids: set,
    confidence_values: list[float],
    scaffold_nodes: tuple[ScaffoldNode, ...],
) -> RunEndpointJunction:
    sorted_vertex_ids = tuple(sorted(topology_vertex_ids, key=str))
    sorted_occurrences = tuple(
        sorted(
            occurrences,
            key=lambda occurrence: (occurrence[0], occurrence[1].value),
        )
    )
    sorted_patch_ids = tuple(sorted(patch_ids, key=str))
    anchor_scaffold_node_id = _anchor_scaffold_node_id(
        scaffold_nodes,
        source_vertex_id,
        sorted_vertex_ids,
    )
    return RunEndpointJunction(
        id=_junction_id(key),
        topology_vertex_ids=sorted_vertex_ids,
        source_vertex_id=source_vertex_id,
        incident_run_endpoint_occurrences=sorted_occurrences,
        incident_patch_ids=sorted_patch_ids,
        anchor_scaffold_node_id=anchor_scaffold_node_id,
        confidence=min(confidence_values) if confidence_values else 0.0,
        evidence=(
            _evidence(
                sorted_vertex_ids,
                source_vertex_id,
                len(sorted_occurrences),
                anchor_scaffold_node_id,
            ),
        ),
    )


def _junction_id(key: tuple[str, str]) -> str:
    return f"run_endpoint_junction:{key[0]}:{key[1]}"


def _anchor_scaffold_node_id(
    scaffold_nodes: tuple[ScaffoldNode, ...],
    source_vertex_id: SourceVertexId | None,
    topology_vertex_ids: tuple[VertexId, ...],
) -> str | None:
    if source_vertex_id is not None:
        matches = tuple(
            node.id
            for node in scaffold_nodes
            if source_vertex_id in node.source_vertex_ids
        )
    else:
        vertex_id_set = frozenset(topology_vertex_ids)
        matches = tuple(
            node.id
            for node in scaffold_nodes
            if vertex_id_set & frozenset(node.vertex_ids)
        )
    return sorted(matches)[0] if matches else None


def _evidence(
    topology_vertex_ids: tuple[VertexId, ...],
    source_vertex_id: SourceVertexId | None,
    incident_occurrence_count: int,
    anchor_scaffold_node_id: str | None,
) -> Evidence:
    return Evidence(
        source="layer_3_relations.run_endpoint_junctions",
        summary="RunEndpointJunction grouped from directional-run endpoints",
        data={
            "policy": POLICY_NAME,
            "grouping": "SOURCE_VERTEX" if source_vertex_id is not None else "TOPOLOGY_VERTEX",
            "topology_vertex_ids": [str(vertex_id) for vertex_id in topology_vertex_ids],
            "source_vertex_id": str(source_vertex_id) if source_vertex_id is not None else None,
            "incident_occurrence_count": incident_occurrence_count,
            "anchor_scaffold_node_id": anchor_scaffold_node_id,
        },
    )
