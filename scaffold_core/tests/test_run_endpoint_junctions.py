"""
Layer: tests

Rules:
- Layer 3 RunEndpointJunction tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

import json

from scaffold_core.ids import (
    BoundaryLoopId,
    ChainId,
    PatchChainId,
    PatchId,
    SourceEdgeId,
    SourceVertexId,
    SurfaceModelId,
    VertexId,
)
from scaffold_core.layer_1_topology.model import Chain, PatchChain, SurfaceModel, Vertex
from scaffold_core.layer_2_geometry.facts import (
    ChainGeometryFacts,
    ChainSegmentGeometryFacts,
    GeometryFactSnapshot,
)
from scaffold_core.layer_3_relations.model import PatchChainDirectionalEvidence, PatchChainEndpointRole
from scaffold_core.layer_3_relations.run_endpoint_junctions import build_run_endpoint_junctions
from scaffold_core.pipeline.inspection import inspect_pipeline_context
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
from scaffold_core.tests.fixtures.beveled_wall_corner import (
    make_beveled_wall_corner_source,
    make_rounded_wall_corner_two_segment_source,
)
from scaffold_core.tests.fixtures.cylinder_tube import (
    make_cylinder_tube_without_caps_with_two_seams_source,
)
from scaffold_core.tests.fixtures.detached_parallel_walls import (
    make_detached_parallel_walls_source,
)
from scaffold_core.tests.fixtures.l_corridor_tunnel import (
    make_l_corridor_tunnel_seamed_folds_source,
    make_l_corridor_tunnel_single_patch_source,
)
from scaffold_core.tests.fixtures.tube_with_cap import make_tube_with_cap_source


CANONICAL_FIXTURES = (
    make_detached_parallel_walls_source,
    make_beveled_wall_corner_source,
    make_rounded_wall_corner_two_segment_source,
    make_l_corridor_tunnel_single_patch_source,
    make_l_corridor_tunnel_seamed_folds_source,
    make_tube_with_cap_source,
    make_cylinder_tube_without_caps_with_two_seams_source,
)


def _run(source):
    return run_pass_1_relations(run_pass_0(source))


def _junction_by_source(relations, source_vertex_id: str):
    matches = tuple(
        junction
        for junction in relations.run_endpoint_junctions
        if junction.source_vertex_id == SourceVertexId(source_vertex_id)
    )
    assert len(matches) == 1
    return matches[0]


def test_beveled_wall_corner_exposes_mid_chain_run_endpoint_junctions() -> None:
    context = _run(make_beveled_wall_corner_source())
    relations = context.relation_snapshot

    wall_a_corner_a3 = _junction_by_source(relations, "a3")
    assert wall_a_corner_a3.anchor_scaffold_node_id is None
    assert wall_a_corner_a3.incident_run_endpoint_occurrences == (
        (
            "patch_chain_directional_evidence:patch_chain:patch:seed:f_wall_a:0:0:0",
            PatchChainEndpointRole.END,
        ),
        (
            "patch_chain_directional_evidence:patch_chain:patch:seed:f_wall_a:0:0:1",
            PatchChainEndpointRole.START,
        ),
    )

    wall_a_corner_a0 = _junction_by_source(relations, "a0")
    assert wall_a_corner_a0.anchor_scaffold_node_id is None
    assert wall_a_corner_a0.incident_run_endpoint_occurrences == (
        (
            "patch_chain_directional_evidence:patch_chain:patch:seed:f_wall_a:0:0:1",
            PatchChainEndpointRole.END,
        ),
        (
            "patch_chain_directional_evidence:patch_chain:patch:seed:f_wall_a:0:0:2",
            PatchChainEndpointRole.START,
        ),
    )

    wall_b_corner_b0 = _junction_by_source(relations, "b0")
    wall_b_corner_b1 = _junction_by_source(relations, "b1")
    assert wall_b_corner_b0.anchor_scaffold_node_id is None
    assert wall_b_corner_b1.anchor_scaffold_node_id is None
    assert wall_b_corner_b0.incident_run_endpoint_occurrences == (
        (
            "patch_chain_directional_evidence:patch_chain:patch:seed:f_wall_b:0:0:0",
            PatchChainEndpointRole.END,
        ),
        (
            "patch_chain_directional_evidence:patch_chain:patch:seed:f_wall_b:0:0:1",
            PatchChainEndpointRole.START,
        ),
    )
    assert wall_b_corner_b1.incident_run_endpoint_occurrences == (
        (
            "patch_chain_directional_evidence:patch_chain:patch:seed:f_wall_b:0:0:1",
            PatchChainEndpointRole.END,
        ),
        (
            "patch_chain_directional_evidence:patch_chain:patch:seed:f_wall_b:0:0:2",
            PatchChainEndpointRole.START,
        ),
    )

    for source_vertex_id in ("a1", "a2", "c0", "c1"):
        assert _junction_by_source(relations, source_vertex_id).anchor_scaffold_node_id is not None


def test_l_corridor_single_patch_has_junction_at_every_closed_border_turn() -> None:
    context = _run(make_l_corridor_tunnel_single_patch_source())
    relations = context.relation_snapshot

    # The single closed PatchChain is an eight-segment folded border. Each
    # consecutive run changes direction, including the wrap back to w0.
    assert len(relations.run_endpoint_junctions) == 8
    assert {
        str(junction.source_vertex_id)
        for junction in relations.run_endpoint_junctions
    } == {"g0", "g1", "g2", "g3", "w0", "w1", "t0", "t1"}
    assert _junction_by_source(relations, "w0").anchor_scaffold_node_id is not None
    for source_vertex_id in ("g0", "g1", "g2", "g3", "w1", "t0", "t1"):
        assert _junction_by_source(relations, source_vertex_id).anchor_scaffold_node_id is None


def test_mid_run_endpoint_uses_canonical_vertex_when_duplicate_occurrences_are_other_patch() -> None:
    v3 = SourceVertexId("v3")
    v4 = SourceVertexId("v4")
    v5 = SourceVertexId("v5")
    chain_id = ChainId("chain:e0:e1")
    patch_chain_id = PatchChainId("patch_chain:patch:seed:f0:0:0")
    topology = SurfaceModel(
        id=SurfaceModelId("regression"),
        chains={
            chain_id: Chain(
                id=chain_id,
                start_vertex_id=VertexId("vertex:v3"),
                end_vertex_id=VertexId("vertex:v5"),
            )
        },
        patch_chains={
            patch_chain_id: PatchChain(
                id=patch_chain_id,
                chain_id=chain_id,
                patch_id=PatchId("patch:seed:f0"),
                loop_id=BoundaryLoopId("loop:f0:0"),
                orientation_sign=1,
                position_in_loop=0,
            )
        },
        vertices={
            VertexId("vertex:v3"): Vertex(VertexId("vertex:v3"), (v3,)),
            VertexId("vertex:v4"): Vertex(VertexId("vertex:v4"), (v4,)),
            VertexId("vertex:v5"): Vertex(VertexId("vertex:v5"), (v5,)),
            VertexId("vertex:v4:patch_chain:patch:seed:f1:0"): Vertex(
                VertexId("vertex:v4:patch_chain:patch:seed:f1:0"),
                (v4,),
            ),
            VertexId("vertex:v4:patch_chain:patch:seed:f1:1"): Vertex(
                VertexId("vertex:v4:patch_chain:patch:seed:f1:1"),
                (v4,),
            ),
        },
    )
    geometry = GeometryFactSnapshot(
        chain_facts={
            chain_id: ChainGeometryFacts(
                chain_id=chain_id,
                length=2.0,
                chord_length=2.0,
                chord_direction=(1.0, 0.0, 0.0),
                straightness=1.0,
                detour_ratio=1.0,
                source_vertex_run=(v3, v4, v5),
                segments=(
                    ChainSegmentGeometryFacts(
                        chain_id=chain_id,
                        source_edge_id=SourceEdgeId("e0"),
                        segment_index=0,
                        start_source_vertex_id=v3,
                        end_source_vertex_id=v4,
                        start_position=(0.0, 0.0, 0.0),
                        end_position=(1.0, 0.0, 0.0),
                        vector=(1.0, 0.0, 0.0),
                        length=1.0,
                        direction=(1.0, 0.0, 0.0),
                    ),
                    ChainSegmentGeometryFacts(
                        chain_id=chain_id,
                        source_edge_id=SourceEdgeId("e1"),
                        segment_index=1,
                        start_source_vertex_id=v4,
                        end_source_vertex_id=v5,
                        start_position=(1.0, 0.0, 0.0),
                        end_position=(2.0, 0.0, 0.0),
                        vector=(1.0, 0.0, 0.0),
                        length=1.0,
                        direction=(1.0, 0.0, 0.0),
                    ),
                ),
            )
        }
    )
    evidence = PatchChainDirectionalEvidence(
        id="patch_chain_directional_evidence:patch_chain:patch:seed:f0:0:0:0",
        directional_run_id="chain_directional_run:chain:e0:e1:0",
        parent_chain_id=chain_id,
        patch_chain_id=patch_chain_id,
        patch_id=PatchId("patch:seed:f0"),
        loop_id=BoundaryLoopId("loop:f0:0"),
        position_in_loop=0,
        orientation_sign=1,
        source_edge_ids=(SourceEdgeId("e0"),),
        segment_indices=(0,),
        start_source_vertex_id=v3,
        end_source_vertex_id=v4,
        length=1.0,
        direction=(1.0, 0.0, 0.0),
        confidence=1.0,
    )

    junctions = build_run_endpoint_junctions(topology, geometry, (evidence,), ())
    v4_junction = next(junction for junction in junctions if junction.source_vertex_id == v4)
    assert v4_junction.topology_vertex_ids == (VertexId("vertex:v4"),)


def test_mid_run_endpoint_preserves_same_patch_duplicate_occurrence_ambiguity() -> None:
    v3 = SourceVertexId("v3")
    v4 = SourceVertexId("v4")
    v5 = SourceVertexId("v5")
    chain_id = ChainId("chain:e0:e1")
    patch_chain_id = PatchChainId("patch_chain:patch:seed:f1:0:2")
    first_occurrence = VertexId("vertex:v4:patch_chain:patch:seed:f1:0")
    second_occurrence = VertexId("vertex:v4:patch_chain:patch:seed:f1:1")
    topology = SurfaceModel(
        id=SurfaceModelId("regression"),
        chains={
            chain_id: Chain(
                id=chain_id,
                start_vertex_id=VertexId("vertex:v3"),
                end_vertex_id=VertexId("vertex:v5"),
            )
        },
        patch_chains={
            patch_chain_id: PatchChain(
                id=patch_chain_id,
                chain_id=chain_id,
                patch_id=PatchId("patch:seed:f1"),
                loop_id=BoundaryLoopId("loop:f1:0"),
                orientation_sign=1,
                position_in_loop=2,
            )
        },
        vertices={
            VertexId("vertex:v3"): Vertex(VertexId("vertex:v3"), (v3,)),
            VertexId("vertex:v5"): Vertex(VertexId("vertex:v5"), (v5,)),
            first_occurrence: Vertex(first_occurrence, (v4,)),
            second_occurrence: Vertex(second_occurrence, (v4,)),
        },
    )
    geometry = GeometryFactSnapshot(
        chain_facts={
            chain_id: ChainGeometryFacts(
                chain_id=chain_id,
                length=2.0,
                chord_length=2.0,
                chord_direction=(1.0, 0.0, 0.0),
                straightness=1.0,
                detour_ratio=1.0,
                source_vertex_run=(v3, v4, v5),
                segments=(
                    ChainSegmentGeometryFacts(
                        chain_id=chain_id,
                        source_edge_id=SourceEdgeId("e0"),
                        segment_index=0,
                        start_source_vertex_id=v3,
                        end_source_vertex_id=v4,
                        start_position=(0.0, 0.0, 0.0),
                        end_position=(1.0, 0.0, 0.0),
                        vector=(1.0, 0.0, 0.0),
                        length=1.0,
                        direction=(1.0, 0.0, 0.0),
                    ),
                    ChainSegmentGeometryFacts(
                        chain_id=chain_id,
                        source_edge_id=SourceEdgeId("e1"),
                        segment_index=1,
                        start_source_vertex_id=v4,
                        end_source_vertex_id=v5,
                        start_position=(1.0, 0.0, 0.0),
                        end_position=(2.0, 0.0, 0.0),
                        vector=(1.0, 0.0, 0.0),
                        length=1.0,
                        direction=(1.0, 0.0, 0.0),
                    ),
                ),
            )
        }
    )
    evidence = PatchChainDirectionalEvidence(
        id="patch_chain_directional_evidence:patch_chain:patch:seed:f1:0:2:0",
        directional_run_id="chain_directional_run:chain:e0:e1:0",
        parent_chain_id=chain_id,
        patch_chain_id=patch_chain_id,
        patch_id=PatchId("patch:seed:f1"),
        loop_id=BoundaryLoopId("loop:f1:0"),
        position_in_loop=2,
        orientation_sign=1,
        source_edge_ids=(SourceEdgeId("e0"),),
        segment_indices=(0,),
        start_source_vertex_id=v3,
        end_source_vertex_id=v4,
        length=1.0,
        direction=(1.0, 0.0, 0.0),
        confidence=1.0,
    )

    junctions = build_run_endpoint_junctions(topology, geometry, (evidence,), ())
    v4_junction = next(junction for junction in junctions if junction.source_vertex_id == v4)
    assert v4_junction.topology_vertex_ids == (first_occurrence, second_occurrence)


def test_every_canonical_directional_evidence_endpoint_has_one_junction() -> None:
    for fixture in CANONICAL_FIXTURES:
        context = _run(fixture())
        relations = context.relation_snapshot

        endpoint_occurrences = [
            occurrence
            for junction in relations.run_endpoint_junctions
            for occurrence in junction.incident_run_endpoint_occurrences
        ]
        expected_occurrences = {
            (directional_evidence.id, role)
            for directional_evidence in relations.patch_chain_directional_evidence
            for role in (PatchChainEndpointRole.START, PatchChainEndpointRole.END)
        }

        assert set(endpoint_occurrences) == expected_occurrences
        assert len(endpoint_occurrences) == len(expected_occurrences)
        assert all(junction.topology_vertex_ids for junction in relations.run_endpoint_junctions)


def test_run_endpoint_junctions_are_full_detail_inspection_only() -> None:
    context = _run(make_beveled_wall_corner_source())

    compact_report = inspect_pipeline_context(context)
    assert "run_endpoint_junction_count" not in compact_report["relations"]
    assert "run_endpoint_junctions" not in compact_report["relations"]

    full_report = inspect_pipeline_context(context, detail="full")
    json.dumps(full_report)
    relations = full_report["relations"]
    assert relations["run_endpoint_junction_count"] == 8
    assert len(relations["run_endpoint_junctions"]) == 8
    mid_chain_junction = next(
        junction
        for junction in relations["run_endpoint_junctions"]
        if junction["source_vertex_id"] == "a3"
    )
    assert mid_chain_junction["anchor_scaffold_node_id"] is None
    assert len(mid_chain_junction["incident_run_endpoint_occurrences"]) == 2
