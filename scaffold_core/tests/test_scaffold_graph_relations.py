"""
Layer: tests

Rules:
- Layer 3 ScaffoldGraph evidence relation tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from scaffold_core.ids import BoundaryLoopId, ChainId, PatchChainId, PatchId, VertexId
from scaffold_core.layer_3_relations.model import (
    DihedralKind,
    LoopCorner,
    PatchAdjacency,
    PatchChainEndpointRole,
    PatchChainEndpointSample,
    OwnerNormalSource,
    ScaffoldEdge,
    ScaffoldJunctionKind,
    ScaffoldNode,
    ScaffoldNodeIncidentEdgeRelationKind,
    SharedChainPatchChainRelationKind,
)
from scaffold_core.layer_3_relations.patch_chain_endpoint_relations import (
    build_patch_chain_endpoint_relations,
)
from scaffold_core.layer_3_relations.scaffold_graph_relations import (
    build_scaffold_graph_relations,
)
from scaffold_core.pipeline.inspection import inspect_pipeline_context
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
from scaffold_core.tests.fixtures.closed_shared_loop import make_closed_shared_boundary_loop_source
from scaffold_core.tests.fixtures.cylinder_tube import (
    make_cylinder_tube_without_caps_with_one_seam_source,
    make_segmented_cylinder_tube_without_caps_with_one_seam_source,
)
from scaffold_core.tests.fixtures.l_shape import make_two_patch_source_with_two_edge_seam_run


ROOT = Path(__file__).resolve().parents[1]
SCAFFOLD_GRAPH_RELATIONS_MODULE = ROOT / "layer_3_relations" / "scaffold_graph_relations.py"
FORBIDDEN_TOKENS = frozenset({
    "H_FRAME",
    "V_FRAME",
    "WALL",
    "FLOOR",
    "SLOPE",
    "WorldOrientation",
    "WORLD_UP",
    "ScaffoldTrace",
    "ScaffoldCircuit",
    "ScaffoldRail",
    "FeatureCandidate",
    "Runtime",
    "Solve",
    "UV",
})
FORBIDDEN_IMPORTS = (
    "scaffold_core.layer_4_features",
    "scaffold_core.layer_5_runtime",
    "scaffold_core.api",
    "scaffold_core.ui",
    "scaffold_core.pipeline",
)


def test_same_patch_orthogonal_endpoint_relation_becomes_node_corner_relation() -> None:
    relation = _single_incident_relation(
        _sample(
            "a",
            (1.0, 0.0, 0.0),
            PatchId("patch:one"),
            owner_normal=(0.0, 0.0, 0.0),
            owner_normal_source=OwnerNormalSource.UNKNOWN,
        ),
        _sample(
            "b",
            (0.0, 1.0, 0.0),
            PatchId("patch:one"),
            owner_normal=(0.0, 0.0, 0.0),
            owner_normal_source=OwnerNormalSource.UNKNOWN,
        ),
    )

    assert relation.kind is ScaffoldNodeIncidentEdgeRelationKind.ORTHOGONAL_CORNER
    assert relation.patch_chain_endpoint_relation_id is not None
    assert relation.confidence == 1.0


def test_orthogonal_tangent_with_compatible_normals_stays_corner_relation() -> None:
    relation = _single_incident_relation(
        _sample("a", (1.0, 0.0, 0.0), PatchId("patch:one")),
        _sample("b", (0.0, 1.0, 0.0), PatchId("patch:one")),
    )

    assert relation.kind is ScaffoldNodeIncidentEdgeRelationKind.ORTHOGONAL_CORNER
    assert relation.normal_dot == 1.0


def test_same_patch_same_loop_end_start_local_normals_emit_side_surface_evidence() -> None:
    end_sample = _sample(
        "a",
        (1.0, 0.0, 0.0),
        PatchId("patch:one"),
        endpoint_role=PatchChainEndpointRole.END,
        owner_normal_source=OwnerNormalSource.LOCAL_FACE_FAN_NORMAL,
    )
    start_sample = _sample(
        "b",
        (1.0, 0.0, 0.0),
        PatchId("patch:one"),
        endpoint_role=PatchChainEndpointRole.START,
        owner_normal_source=OwnerNormalSource.LOCAL_FACE_FAN_NORMAL,
    )

    side_surface_evidence, incident_relations, shared_relations = build_scaffold_graph_relations(
        scaffold_nodes=(_node(end_sample.patch_chain_id, start_sample.patch_chain_id),),
        scaffold_edges=(
            _edge(
                "a",
                ChainId("chain:a"),
                PatchId("patch:one"),
                start_node_id="scaffold_node:two",
                end_node_id="scaffold_node:one",
                loop_id=BoundaryLoopId("loop:one"),
            ),
            _edge(
                "b",
                ChainId("chain:b"),
                PatchId("patch:one"),
                loop_id=BoundaryLoopId("loop:one"),
            ),
        ),
        endpoint_samples=(end_sample, start_sample),
        endpoint_relations=build_patch_chain_endpoint_relations((end_sample, start_sample)),
        patch_adjacencies={},
        loop_corners=(_loop_corner("a", end_sample.patch_chain_id, start_sample.patch_chain_id),),
    )

    assert shared_relations == ()
    assert len(side_surface_evidence) == 1
    assert side_surface_evidence[0].first_endpoint_role is PatchChainEndpointRole.END
    assert side_surface_evidence[0].second_endpoint_role is PatchChainEndpointRole.START
    assert side_surface_evidence[0].first_chain_id == ChainId("chain:a")
    assert side_surface_evidence[0].second_chain_id == ChainId("chain:b")
    assert side_surface_evidence[0].normal_dot == 1.0
    assert len(incident_relations) == 1
    assert (
        incident_relations[0].kind
        is ScaffoldNodeIncidentEdgeRelationKind.SURFACE_SLIDING_CONTINUATION_CANDIDATE
    )
    assert incident_relations[0].evidence[0].data["original_tangent_local_category"] == "SAME_RAY_AMBIGUOUS"
    assert (
        incident_relations[0].evidence[0].data["side_surface_continuity_evidence_id"]
        == side_surface_evidence[0].id
    )
    assert incident_relations[0].evidence[0].data["recurrence_evidence_present"] is False


def test_explicit_side_surface_evidence_promotes_orthogonal_pair_without_recurrence() -> None:
    end_sample = _sample(
        "a",
        (1.0, 0.0, 0.0),
        PatchId("patch:one"),
        endpoint_role=PatchChainEndpointRole.END,
        owner_normal_source=OwnerNormalSource.LOCAL_FACE_FAN_NORMAL,
    )
    start_sample = _sample(
        "b",
        (0.0, 1.0, 0.0),
        PatchId("patch:one"),
        endpoint_role=PatchChainEndpointRole.START,
        owner_normal_source=OwnerNormalSource.LOCAL_FACE_FAN_NORMAL,
    )

    side_surface_evidence, incident_relations, shared_relations = build_scaffold_graph_relations(
        scaffold_nodes=(_node(end_sample.patch_chain_id, start_sample.patch_chain_id),),
        scaffold_edges=(
            _edge(
                "a",
                ChainId("chain:a"),
                PatchId("patch:one"),
                start_node_id="scaffold_node:two",
                end_node_id="scaffold_node:one",
                loop_id=BoundaryLoopId("loop:one"),
            ),
            _edge(
                "b",
                ChainId("chain:b"),
                PatchId("patch:one"),
                loop_id=BoundaryLoopId("loop:one"),
            ),
        ),
        endpoint_samples=(end_sample, start_sample),
        endpoint_relations=build_patch_chain_endpoint_relations((end_sample, start_sample)),
        patch_adjacencies={},
        loop_corners=(_loop_corner("a", end_sample.patch_chain_id, start_sample.patch_chain_id),),
    )

    assert shared_relations == ()
    assert len(side_surface_evidence) == 1
    assert len(incident_relations) == 1
    relation = incident_relations[0]
    assert relation.kind is ScaffoldNodeIncidentEdgeRelationKind.SURFACE_SLIDING_CONTINUATION_CANDIDATE
    assert relation.normal_dot == 1.0
    assert relation.evidence[0].data["original_tangent_local_category"] == "ORTHOGONAL_CORNER"
    assert relation.evidence[0].data["side_surface_continuity_evidence_id"] == side_surface_evidence[0].id
    assert relation.evidence[0].data["normal_evidence_source"] == "LOCAL_FACE_FAN_NORMAL"
    assert relation.evidence[0].data["recurrence_evidence_present"] is False


def test_explicit_side_surface_pair_promotes_at_cross_patch_node() -> None:
    end_sample = _sample(
        "a",
        (1.0, 0.0, 0.0),
        PatchId("patch:one"),
        endpoint_role=PatchChainEndpointRole.END,
        owner_normal_source=OwnerNormalSource.LOCAL_FACE_FAN_NORMAL,
    )
    start_sample = _sample(
        "b",
        (0.0, 1.0, 0.0),
        PatchId("patch:one"),
        endpoint_role=PatchChainEndpointRole.START,
        owner_normal_source=OwnerNormalSource.LOCAL_FACE_FAN_NORMAL,
    )
    cross_patch_sample = _sample(
        "c",
        (0.0, 0.0, 1.0),
        PatchId("patch:two"),
        endpoint_role=PatchChainEndpointRole.START,
        owner_normal_source=OwnerNormalSource.LOCAL_FACE_FAN_NORMAL,
    )

    side_surface_evidence, incident_relations, _ = build_scaffold_graph_relations(
        scaffold_nodes=(_node(
            end_sample.patch_chain_id,
            start_sample.patch_chain_id,
            cross_patch_sample.patch_chain_id,
        ),),
        scaffold_edges=(
            _edge(
                "a",
                ChainId("chain:a"),
                PatchId("patch:one"),
                start_node_id="scaffold_node:two",
                end_node_id="scaffold_node:one",
                loop_id=BoundaryLoopId("loop:one"),
            ),
            _edge(
                "b",
                ChainId("chain:b"),
                PatchId("patch:one"),
                loop_id=BoundaryLoopId("loop:one"),
            ),
            _edge(
                "c",
                ChainId("chain:c"),
                PatchId("patch:two"),
                loop_id=BoundaryLoopId("loop:two"),
            ),
        ),
        endpoint_samples=(end_sample, start_sample, cross_patch_sample),
        endpoint_relations=build_patch_chain_endpoint_relations((end_sample, start_sample, cross_patch_sample)),
        patch_adjacencies={},
        loop_corners=(_loop_corner("a", end_sample.patch_chain_id, start_sample.patch_chain_id),),
    )

    assert len(side_surface_evidence) == 1
    promoted = [
        relation
        for relation in incident_relations
        if relation.kind is ScaffoldNodeIncidentEdgeRelationKind.SURFACE_SLIDING_CONTINUATION_CANDIDATE
    ]
    assert len(promoted) == 1
    assert promoted[0].first_patch_chain_id == end_sample.patch_chain_id
    assert promoted[0].second_patch_chain_id == start_sample.patch_chain_id
    assert promoted[0].evidence[0].data["side_surface_continuity_evidence_id"] == side_surface_evidence[0].id
    assert all(
        cross_patch_sample.patch_chain_id not in (
            relation.first_patch_chain_id,
            relation.second_patch_chain_id,
        )
        for relation in promoted
    )


def test_same_patch_self_seam_side_pair_becomes_surface_sliding_candidate() -> None:
    seam_sample = _sample(
        "seam_a",
        (0.0, 0.0, 1.0),
        PatchId("patch:one"),
        endpoint_role=PatchChainEndpointRole.END,
        owner_normal_source=OwnerNormalSource.LOCAL_FACE_FAN_NORMAL,
    )
    duplicate_seam_sample = _sample(
        "seam_b",
        (0.0, 0.0, 1.0),
        PatchId("patch:one"),
        endpoint_role=PatchChainEndpointRole.END,
        owner_normal_source=OwnerNormalSource.LOCAL_FACE_FAN_NORMAL,
    )
    side_sample = _sample(
        "side",
        (1.0, 0.0, 0.0),
        PatchId("patch:one"),
        endpoint_role=PatchChainEndpointRole.START,
        owner_normal_source=OwnerNormalSource.LOCAL_FACE_FAN_NORMAL,
    )
    edges = (
        _edge(
            "seam_a",
            ChainId("chain:seam"),
            PatchId("patch:one"),
            start_node_id="scaffold_node:two",
            end_node_id="scaffold_node:one",
            loop_id=BoundaryLoopId("loop:one"),
        ),
        _edge(
            "seam_b",
            ChainId("chain:seam"),
            PatchId("patch:one"),
            start_node_id="scaffold_node:two",
            end_node_id="scaffold_node:one",
            loop_id=BoundaryLoopId("loop:one"),
        ),
        _edge("side", ChainId("chain:side"), PatchId("patch:one"), loop_id=BoundaryLoopId("loop:one")),
    )
    node = _node(
        seam_sample.patch_chain_id,
        duplicate_seam_sample.patch_chain_id,
        side_sample.patch_chain_id,
    )

    side_surface_evidence, incident_relations, _ = build_scaffold_graph_relations(
        scaffold_nodes=(node,),
        scaffold_edges=edges,
        endpoint_samples=(seam_sample, duplicate_seam_sample, side_sample),
        endpoint_relations=build_patch_chain_endpoint_relations((
            seam_sample,
            duplicate_seam_sample,
            side_sample,
        )),
        patch_adjacencies={},
        loop_corners=(
            _loop_corner("seam_a", seam_sample.patch_chain_id, side_sample.patch_chain_id),
            _loop_corner(
                "seam_b",
                duplicate_seam_sample.patch_chain_id,
                side_sample.patch_chain_id,
                position_in_loop=1,
            ),
        ),
    )

    assert len(side_surface_evidence) == 2
    sliding_relations = [
        relation
        for relation in incident_relations
        if relation.kind is ScaffoldNodeIncidentEdgeRelationKind.SURFACE_SLIDING_CONTINUATION_CANDIDATE
    ]
    assert len(sliding_relations) == len(side_surface_evidence)
    assert {
        relation.evidence[0].data["original_tangent_local_category"]
        for relation in sliding_relations
    } == {"ORTHOGONAL_CORNER"}
    assert all(
        relation.evidence[0].data["normal_evidence_source"]
        == "LOCAL_FACE_FAN_NORMAL"
        for relation in sliding_relations
    )
    assert all(
        relation.evidence[0].data["same_side_surface_evidence_source"]
        == "side_surface_continuity_evidence_v0"
        for relation in sliding_relations
    )
    assert all(
        relation.evidence[0].data["recurrence_evidence_present"] is True
        for relation in sliding_relations
    )


def test_same_ray_self_seam_side_pair_becomes_surface_sliding_candidate() -> None:
    seam_sample = _sample(
        "seam_a",
        (1.0, 0.0, 0.0),
        PatchId("patch:one"),
        endpoint_role=PatchChainEndpointRole.END,
        owner_normal_source=OwnerNormalSource.LOCAL_FACE_FAN_NORMAL,
    )
    duplicate_seam_sample = _sample(
        "seam_b",
        (1.0, 0.0, 0.0),
        PatchId("patch:one"),
        endpoint_role=PatchChainEndpointRole.END,
        owner_normal_source=OwnerNormalSource.LOCAL_FACE_FAN_NORMAL,
    )
    side_sample = _sample(
        "side",
        (1.0, 0.0, 0.0),
        PatchId("patch:one"),
        endpoint_role=PatchChainEndpointRole.START,
        owner_normal_source=OwnerNormalSource.LOCAL_FACE_FAN_NORMAL,
    )
    edges = (
        _edge(
            "seam_a",
            ChainId("chain:seam"),
            PatchId("patch:one"),
            start_node_id="scaffold_node:two",
            end_node_id="scaffold_node:one",
            loop_id=BoundaryLoopId("loop:one"),
        ),
        _edge(
            "seam_b",
            ChainId("chain:seam"),
            PatchId("patch:one"),
            start_node_id="scaffold_node:two",
            end_node_id="scaffold_node:one",
            loop_id=BoundaryLoopId("loop:one"),
        ),
        _edge("side", ChainId("chain:side"), PatchId("patch:one"), loop_id=BoundaryLoopId("loop:one")),
    )

    side_surface_evidence, incident_relations, _ = build_scaffold_graph_relations(
        scaffold_nodes=(_node(
            seam_sample.patch_chain_id,
            duplicate_seam_sample.patch_chain_id,
            side_sample.patch_chain_id,
        ),),
        scaffold_edges=edges,
        endpoint_samples=(seam_sample, duplicate_seam_sample, side_sample),
        endpoint_relations=build_patch_chain_endpoint_relations((
            seam_sample,
            duplicate_seam_sample,
            side_sample,
        )),
        patch_adjacencies={},
        loop_corners=(
            _loop_corner("seam_a", seam_sample.patch_chain_id, side_sample.patch_chain_id),
            _loop_corner(
                "seam_b",
                duplicate_seam_sample.patch_chain_id,
                side_sample.patch_chain_id,
                position_in_loop=1,
            ),
        ),
    )

    assert len(side_surface_evidence) == 2
    sliding_relations = [
        relation
        for relation in incident_relations
        if relation.kind is ScaffoldNodeIncidentEdgeRelationKind.SURFACE_SLIDING_CONTINUATION_CANDIDATE
    ]
    assert len(sliding_relations) == len(side_surface_evidence)
    assert {
        relation.evidence[0].data["original_tangent_local_category"]
        for relation in sliding_relations
    } == {"SAME_RAY_AMBIGUOUS"}
    assert all(
        relation.evidence[0].data["recurrence_evidence_present"] is True
        for relation in sliding_relations
    )


def test_missing_local_face_fan_normal_evidence_does_not_slide() -> None:
    seam_sample = _sample(
        "seam_a",
        (0.0, 0.0, 1.0),
        PatchId("patch:one"),
        endpoint_role=PatchChainEndpointRole.END,
        owner_normal_source=OwnerNormalSource.LOCAL_FACE_FAN_NORMAL,
    )
    duplicate_seam_sample = _sample(
        "seam_b",
        (0.0, 0.0, 1.0),
        PatchId("patch:one"),
        endpoint_role=PatchChainEndpointRole.END,
        owner_normal_source=OwnerNormalSource.LOCAL_FACE_FAN_NORMAL,
    )
    side_sample = _sample(
        "side",
        (1.0, 0.0, 0.0),
        PatchId("patch:one"),
        endpoint_role=PatchChainEndpointRole.START,
        owner_normal_source=OwnerNormalSource.PATCH_AGGREGATE_NORMAL,
    )

    side_surface_evidence, incident_relations, _ = build_scaffold_graph_relations(
        scaffold_nodes=(_node(
            seam_sample.patch_chain_id,
            duplicate_seam_sample.patch_chain_id,
            side_sample.patch_chain_id,
        ),),
        scaffold_edges=(
            _edge(
                "seam_a",
                ChainId("chain:seam"),
                PatchId("patch:one"),
                start_node_id="scaffold_node:two",
                end_node_id="scaffold_node:one",
                loop_id=BoundaryLoopId("loop:one"),
            ),
            _edge(
                "seam_b",
                ChainId("chain:seam"),
                PatchId("patch:one"),
                start_node_id="scaffold_node:two",
                end_node_id="scaffold_node:one",
                loop_id=BoundaryLoopId("loop:one"),
            ),
            _edge("side", ChainId("chain:side"), PatchId("patch:one"), loop_id=BoundaryLoopId("loop:one")),
        ),
        endpoint_samples=(seam_sample, duplicate_seam_sample, side_sample),
        endpoint_relations=build_patch_chain_endpoint_relations((
            seam_sample,
            duplicate_seam_sample,
            side_sample,
        )),
        patch_adjacencies={},
        loop_corners=(
            _loop_corner("seam_a", seam_sample.patch_chain_id, side_sample.patch_chain_id),
            _loop_corner(
                "seam_b",
                duplicate_seam_sample.patch_chain_id,
                side_sample.patch_chain_id,
                position_in_loop=1,
            ),
        ),
    )

    assert side_surface_evidence == ()
    assert not any(
        relation.kind is ScaffoldNodeIncidentEdgeRelationKind.SURFACE_SLIDING_CONTINUATION_CANDIDATE
        for relation in incident_relations
    )


def test_same_chain_pair_does_not_emit_side_surface_evidence() -> None:
    first_sample = _sample(
        "a",
        (0.0, 0.0, 1.0),
        PatchId("patch:one"),
        endpoint_role=PatchChainEndpointRole.END,
        owner_normal_source=OwnerNormalSource.LOCAL_FACE_FAN_NORMAL,
    )
    second_sample = _sample(
        "b",
        (1.0, 0.0, 0.0),
        PatchId("patch:one"),
        endpoint_role=PatchChainEndpointRole.START,
        owner_normal_source=OwnerNormalSource.LOCAL_FACE_FAN_NORMAL,
    )

    side_surface_evidence, incident_relations, _ = build_scaffold_graph_relations(
        scaffold_nodes=(_node(first_sample.patch_chain_id, second_sample.patch_chain_id),),
        scaffold_edges=(
            _edge(
                "a",
                ChainId("chain:shared"),
                PatchId("patch:one"),
                start_node_id="scaffold_node:two",
                end_node_id="scaffold_node:one",
                loop_id=BoundaryLoopId("loop:one"),
            ),
            _edge("b", ChainId("chain:shared"), PatchId("patch:one"), loop_id=BoundaryLoopId("loop:one")),
        ),
        endpoint_samples=(first_sample, second_sample),
        endpoint_relations=build_patch_chain_endpoint_relations((first_sample, second_sample)),
        patch_adjacencies={},
        loop_corners=(_loop_corner("same_chain", first_sample.patch_chain_id, second_sample.patch_chain_id),),
    )

    assert side_surface_evidence == ()
    assert not any(
        relation.kind is ScaffoldNodeIncidentEdgeRelationKind.SURFACE_SLIDING_CONTINUATION_CANDIDATE
        for relation in incident_relations
    )


def test_different_loop_pair_does_not_emit_side_surface_evidence() -> None:
    seam_sample = _sample(
        "seam_a",
        (0.0, 0.0, 1.0),
        PatchId("patch:one"),
        endpoint_role=PatchChainEndpointRole.END,
        owner_normal_source=OwnerNormalSource.LOCAL_FACE_FAN_NORMAL,
    )
    duplicate_seam_sample = _sample(
        "seam_b",
        (0.0, 0.0, 1.0),
        PatchId("patch:one"),
        endpoint_role=PatchChainEndpointRole.END,
        owner_normal_source=OwnerNormalSource.LOCAL_FACE_FAN_NORMAL,
    )
    side_sample = _sample(
        "side",
        (1.0, 0.0, 0.0),
        PatchId("patch:one"),
        endpoint_role=PatchChainEndpointRole.START,
        owner_normal_source=OwnerNormalSource.LOCAL_FACE_FAN_NORMAL,
    )

    side_surface_evidence, incident_relations, _ = build_scaffold_graph_relations(
        scaffold_nodes=(_node(
            seam_sample.patch_chain_id,
            duplicate_seam_sample.patch_chain_id,
            side_sample.patch_chain_id,
        ),),
        scaffold_edges=(
            _edge(
                "seam_a",
                ChainId("chain:seam"),
                PatchId("patch:one"),
                start_node_id="scaffold_node:two",
                end_node_id="scaffold_node:one",
                loop_id=BoundaryLoopId("loop:one"),
            ),
            _edge(
                "seam_b",
                ChainId("chain:seam"),
                PatchId("patch:one"),
                start_node_id="scaffold_node:two",
                end_node_id="scaffold_node:one",
                loop_id=BoundaryLoopId("loop:one"),
            ),
            _edge("side", ChainId("chain:side"), PatchId("patch:one"), loop_id=BoundaryLoopId("loop:two")),
        ),
        endpoint_samples=(seam_sample, duplicate_seam_sample, side_sample),
        endpoint_relations=build_patch_chain_endpoint_relations((
            seam_sample,
            duplicate_seam_sample,
            side_sample,
        )),
        patch_adjacencies={},
        loop_corners=(
            _loop_corner("seam_a", seam_sample.patch_chain_id, side_sample.patch_chain_id),
            _loop_corner(
                "seam_b",
                duplicate_seam_sample.patch_chain_id,
                side_sample.patch_chain_id,
                position_in_loop=1,
            ),
        ),
    )

    assert side_surface_evidence == ()
    assert not any(
        relation.kind is ScaffoldNodeIncidentEdgeRelationKind.SURFACE_SLIDING_CONTINUATION_CANDIDATE
        for relation in incident_relations
    )


def test_low_normal_dot_pair_does_not_emit_side_surface_evidence() -> None:
    seam_sample = _sample(
        "seam_a",
        (0.0, 0.0, 1.0),
        PatchId("patch:one"),
        endpoint_role=PatchChainEndpointRole.END,
        owner_normal_source=OwnerNormalSource.LOCAL_FACE_FAN_NORMAL,
        owner_normal=(0.0, 0.0, 1.0),
    )
    duplicate_seam_sample = _sample(
        "seam_b",
        (0.0, 0.0, 1.0),
        PatchId("patch:one"),
        endpoint_role=PatchChainEndpointRole.END,
        owner_normal_source=OwnerNormalSource.LOCAL_FACE_FAN_NORMAL,
        owner_normal=(0.0, 0.0, 1.0),
    )
    side_sample = _sample(
        "side",
        (1.0, 0.0, 0.0),
        PatchId("patch:one"),
        endpoint_role=PatchChainEndpointRole.START,
        owner_normal_source=OwnerNormalSource.LOCAL_FACE_FAN_NORMAL,
        owner_normal=(0.0, 1.0, 0.0),
    )

    side_surface_evidence, incident_relations, _ = build_scaffold_graph_relations(
        scaffold_nodes=(_node(
            seam_sample.patch_chain_id,
            duplicate_seam_sample.patch_chain_id,
            side_sample.patch_chain_id,
        ),),
        scaffold_edges=(
            _edge(
                "seam_a",
                ChainId("chain:seam"),
                PatchId("patch:one"),
                start_node_id="scaffold_node:two",
                end_node_id="scaffold_node:one",
                loop_id=BoundaryLoopId("loop:one"),
            ),
            _edge(
                "seam_b",
                ChainId("chain:seam"),
                PatchId("patch:one"),
                start_node_id="scaffold_node:two",
                end_node_id="scaffold_node:one",
                loop_id=BoundaryLoopId("loop:one"),
            ),
            _edge("side", ChainId("chain:side"), PatchId("patch:one"), loop_id=BoundaryLoopId("loop:one")),
        ),
        endpoint_samples=(seam_sample, duplicate_seam_sample, side_sample),
        endpoint_relations=build_patch_chain_endpoint_relations((
            seam_sample,
            duplicate_seam_sample,
            side_sample,
        )),
        patch_adjacencies={},
        loop_corners=(
            _loop_corner("seam_a", seam_sample.patch_chain_id, side_sample.patch_chain_id),
            _loop_corner(
                "seam_b",
                duplicate_seam_sample.patch_chain_id,
                side_sample.patch_chain_id,
                position_in_loop=1,
            ),
        ),
    )

    assert side_surface_evidence == ()
    assert not any(
        relation.kind is ScaffoldNodeIncidentEdgeRelationKind.SURFACE_SLIDING_CONTINUATION_CANDIDATE
        for relation in incident_relations
    )


def test_degraded_normal_evidence_does_not_slide() -> None:
    relation = _single_incident_relation(
        _sample(
            "a",
            (1.0, 0.0, 0.0),
            PatchId("patch:one"),
            owner_normal_source=OwnerNormalSource.LOCAL_FACE_FAN_NORMAL,
        ),
        _sample(
            "b",
            (0.0, 1.0, 0.0),
            PatchId("patch:one"),
            owner_normal_source=OwnerNormalSource.PATCH_AGGREGATE_NORMAL,
        ),
    )

    assert relation.kind is ScaffoldNodeIncidentEdgeRelationKind.ORTHOGONAL_CORNER


def test_shared_chain_only_cross_patch_pair_does_not_slide() -> None:
    first_sample = _sample(
        "a",
        (1.0, 0.0, 0.0),
        PatchId("patch:one"),
        endpoint_role=PatchChainEndpointRole.END,
        owner_normal_source=OwnerNormalSource.LOCAL_FACE_FAN_NORMAL,
    )
    second_sample = _sample(
        "b",
        (0.0, 1.0, 0.0),
        PatchId("patch:two"),
        endpoint_role=PatchChainEndpointRole.START,
        owner_normal_source=OwnerNormalSource.LOCAL_FACE_FAN_NORMAL,
    )
    side_surface_evidence, incident_relations, shared_relations = build_scaffold_graph_relations(
        scaffold_nodes=(_node(first_sample.patch_chain_id, second_sample.patch_chain_id),),
        scaffold_edges=(
            _edge(
                "a",
                ChainId("chain:shared"),
                PatchId("patch:one"),
                start_node_id="scaffold_node:two",
                end_node_id="scaffold_node:one",
                loop_id=BoundaryLoopId("loop:one"),
            ),
            _edge("b", ChainId("chain:shared"), PatchId("patch:two"), loop_id=BoundaryLoopId("loop:one")),
        ),
        endpoint_samples=(first_sample, second_sample),
        endpoint_relations=build_patch_chain_endpoint_relations((first_sample, second_sample)),
        patch_adjacencies={},
    )

    assert side_surface_evidence == ()
    assert len(shared_relations) == 1
    assert not any(
        relation.kind is ScaffoldNodeIncidentEdgeRelationKind.SURFACE_SLIDING_CONTINUATION_CANDIDATE
        for relation in incident_relations
    )


def test_opposite_collinear_endpoint_relation_becomes_continuation_candidate() -> None:
    relation = _single_incident_relation(
        _sample("a", (1.0, 0.0, 0.0), PatchId("patch:one")),
        _sample("b", (-1.0, 0.0, 0.0), PatchId("patch:one")),
    )

    assert relation.kind is ScaffoldNodeIncidentEdgeRelationKind.SURFACE_CONTINUATION_CANDIDATE
    assert relation.evidence[0].data["endpoint_relation_kind"] == "CONTINUATION_CANDIDATE"


def test_opposite_tangent_with_missing_normal_proof_becomes_straight_candidate() -> None:
    relation = _single_incident_relation(
        _sample(
            "a",
            (1.0, 0.0, 0.0),
            PatchId("patch:one"),
            owner_normal=(0.0, 0.0, 0.0),
            owner_normal_source=OwnerNormalSource.UNKNOWN,
        ),
        _sample(
            "b",
            (-1.0, 0.0, 0.0),
            PatchId("patch:one"),
            owner_normal=(0.0, 0.0, 0.0),
            owner_normal_source=OwnerNormalSource.UNKNOWN,
        ),
    )

    assert relation.kind is ScaffoldNodeIncidentEdgeRelationKind.STRAIGHT_CONTINUATION_CANDIDATE
    assert relation.normal_dot == 0.0


def test_opposite_tangent_with_divergent_normals_becomes_cross_surface_connector() -> None:
    relation = _single_incident_relation(
        _sample("a", (1.0, 0.0, 0.0), PatchId("patch:one"), owner_normal=(0.0, 0.0, 1.0)),
        _sample("b", (-1.0, 0.0, 0.0), PatchId("patch:two"), owner_normal=(0.0, 1.0, 0.0)),
    )

    assert relation.kind is ScaffoldNodeIncidentEdgeRelationKind.CROSS_SURFACE_CONNECTOR
    assert relation.normal_dot == 0.0


def test_oblique_tangent_evidence_becomes_oblique_connector() -> None:
    relation = _single_incident_relation(
        _sample("a", (1.0, 0.0, 0.0), PatchId("patch:one")),
        _sample("b", (0.5, 0.8660254037844386, 0.0), PatchId("patch:one")),
    )

    assert relation.kind is ScaffoldNodeIncidentEdgeRelationKind.OBLIQUE_CONNECTOR
    assert relation.normal_dot == 1.0


def test_same_ray_endpoint_relation_becomes_ambiguous_pair_without_reversed_duplicate() -> None:
    relation = _single_incident_relation(
        _sample("b", (1.0, 0.0, 0.0), PatchId("patch:one")),
        _sample("a", (1.0, 0.0, 0.0), PatchId("patch:one")),
    )

    assert relation.kind is ScaffoldNodeIncidentEdgeRelationKind.SAME_RAY_AMBIGUOUS
    assert relation.first_scaffold_edge_id < relation.second_scaffold_edge_id


def test_degraded_endpoint_evidence_becomes_degraded_incident_edge_relation() -> None:
    relation = _single_incident_relation(
        _sample("a", (1.0, 0.0, 0.0), PatchId("patch:one")),
        _sample("b", (0.0, 0.0, 0.0), PatchId("patch:one"), confidence=0.0),
    )

    assert relation.kind is ScaffoldNodeIncidentEdgeRelationKind.DEGRADED
    assert relation.confidence == 0.0


def test_missing_endpoint_relation_pair_still_uses_sample_evidence_for_classification() -> None:
    first_sample = _sample("a", (1.0, 0.0, 0.0), PatchId("patch:one"))
    second_sample = _sample("b", (-1.0, 0.0, 0.0), PatchId("patch:one"))
    edges = (
        _edge("a", ChainId("chain:a"), first_sample.patch_id),
        _edge("b", ChainId("chain:b"), second_sample.patch_id),
    )
    node = _node(first_sample.patch_chain_id, second_sample.patch_chain_id)

    side_surface_evidence, incident_relations, shared_relations = build_scaffold_graph_relations(
        scaffold_nodes=(node,),
        scaffold_edges=edges,
        endpoint_samples=(first_sample, second_sample),
        endpoint_relations=(),
        patch_adjacencies={},
    )

    assert side_surface_evidence == ()
    assert shared_relations == ()
    assert len(incident_relations) == 1
    assert incident_relations[0].kind is ScaffoldNodeIncidentEdgeRelationKind.SURFACE_CONTINUATION_CANDIDATE
    assert incident_relations[0].patch_chain_endpoint_relation_id is None
    assert incident_relations[0].confidence == 1.0


def test_missing_endpoint_sample_pair_emits_missing_endpoint_evidence() -> None:
    edges = (
        _edge("a", ChainId("chain:a"), PatchId("patch:one")),
        _edge("b", ChainId("chain:b"), PatchId("patch:one")),
    )
    node = _node(edges[0].patch_chain_id, edges[1].patch_chain_id)

    side_surface_evidence, incident_relations, shared_relations = build_scaffold_graph_relations(
        scaffold_nodes=(node,),
        scaffold_edges=edges,
        endpoint_samples=(),
        endpoint_relations=(),
        patch_adjacencies={},
    )

    assert side_surface_evidence == ()
    assert shared_relations == ()
    assert len(incident_relations) == 1
    assert incident_relations[0].kind is ScaffoldNodeIncidentEdgeRelationKind.MISSING_ENDPOINT_EVIDENCE
    assert incident_relations[0].first_endpoint_sample_id is None
    assert incident_relations[0].second_endpoint_sample_id is None
    assert incident_relations[0].confidence == 0.0


def test_node_with_five_incident_edge_endpoint_occurrences_emits_ten_relations() -> None:
    samples = tuple(
        _sample(str(index), (1.0, 0.0, 0.0), PatchId("patch:one"))
        for index in range(5)
    )
    endpoint_relations = build_patch_chain_endpoint_relations(samples)
    edges = tuple(
        _edge(str(index), ChainId(f"chain:{index}"), PatchId("patch:one"))
        for index in range(5)
    )
    node = ScaffoldNode(
        id="scaffold_node:one",
        vertex_ids=(VertexId("vertex:one"),),
        source_vertex_ids=(),
        loop_corner_ids=(),
        patch_chain_endpoint_sample_ids=tuple(sample.id for sample in samples),
        patch_chain_endpoint_relation_ids=tuple(relation.id for relation in endpoint_relations),
        incident_patch_chain_ids=tuple(edge.patch_chain_id for edge in edges),
        patch_ids=(PatchId("patch:one"),),
        confidence=1.0,
    )

    side_surface_evidence, incident_relations, shared_relations = build_scaffold_graph_relations(
        scaffold_nodes=(node,),
        scaffold_edges=edges,
        endpoint_samples=samples,
        endpoint_relations=endpoint_relations,
        patch_adjacencies={},
    )

    assert side_surface_evidence == ()
    assert shared_relations == ()
    assert len(incident_relations) == 10
    assert len({relation.id for relation in incident_relations}) == 10


def test_cross_patch_shared_chain_relation_links_patch_adjacency_when_available() -> None:
    first_edge = _edge("a", ChainId("chain:shared"), PatchId("patch:left"))
    second_edge = _edge("b", ChainId("chain:shared"), PatchId("patch:right"))
    adjacency = PatchAdjacency(
        id="adjacency:shared:left:right",
        first_patch_id=first_edge.patch_id,
        second_patch_id=second_edge.patch_id,
        chain_id=first_edge.chain_id,
        first_patch_chain_id=first_edge.patch_chain_id,
        second_patch_chain_id=second_edge.patch_chain_id,
        shared_length=1.0,
        signed_angle_radians=0.0,
        dihedral_kind=DihedralKind.COPLANAR,
    )

    side_surface_evidence, incident_relations, shared_relations = build_scaffold_graph_relations(
        scaffold_nodes=(),
        scaffold_edges=(first_edge, second_edge),
        endpoint_samples=(),
        endpoint_relations=(),
        patch_adjacencies={adjacency.id: adjacency},
    )

    assert side_surface_evidence == ()
    assert incident_relations == ()
    assert len(shared_relations) == 1
    assert shared_relations[0].kind is SharedChainPatchChainRelationKind.CROSS_PATCH_SHARED_CHAIN
    assert shared_relations[0].chain_id == ChainId("chain:shared")
    assert shared_relations[0].patch_adjacency_id == adjacency.id


def test_cross_patch_node_has_incident_edge_pair_evidence_in_snapshot_and_inspection() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_two_patch_source_with_two_edge_seam_run())
    )

    snapshot = context.relation_snapshot
    assert snapshot is not None
    cross_patch_node_ids = {
        junction.scaffold_node_id
        for junction in snapshot.scaffold_junctions
        if junction.kind is ScaffoldJunctionKind.CROSS_PATCH
    }
    relation_node_ids = {
        relation.scaffold_node_id
        for relation in snapshot.scaffold_node_incident_edge_relations
    }

    assert cross_patch_node_ids
    assert cross_patch_node_ids <= relation_node_ids
    assert all(
        relation.first_endpoint_role and relation.second_endpoint_role
        for relation in snapshot.scaffold_node_incident_edge_relations
    )
    assert snapshot.shared_chain_patch_chain_relations

    report = inspect_pipeline_context(context, detail="full")
    json.dumps(report)
    relations = report["relations"]
    assert relations["scaffold_node_incident_edge_relation_count"] == len(
        snapshot.scaffold_node_incident_edge_relations
    )
    assert relations["shared_chain_patch_chain_relation_count"] == len(
        snapshot.shared_chain_patch_chain_relations
    )
    assert relations["scaffold_node_incident_edge_relations"]
    assert relations["shared_chain_patch_chain_relations"]


def test_closed_shared_loop_emits_one_pair_per_node_local_edge_occurrence_pair() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_closed_shared_boundary_loop_source())
    )

    snapshot = context.relation_snapshot
    assert snapshot is not None
    assert len(snapshot.scaffold_node_incident_edge_relations) == 2
    assert {
        relation.kind
        for relation in snapshot.scaffold_node_incident_edge_relations
    } == {
        ScaffoldNodeIncidentEdgeRelationKind.ORTHOGONAL_CORNER,
    }
    assert not any(
        relation.kind is ScaffoldNodeIncidentEdgeRelationKind.SURFACE_SLIDING_CONTINUATION_CANDIDATE
        for relation in snapshot.scaffold_node_incident_edge_relations
    )
    assert len({
        relation.patch_chain_endpoint_relation_id
        for relation in snapshot.scaffold_node_incident_edge_relations
    }) == 2
    assert len({
        relation.id
        for relation in snapshot.scaffold_node_incident_edge_relations
    }) == 2


def test_cylinder_seam_nodes_emit_complete_incident_edge_occurrence_matrix() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_segmented_cylinder_tube_without_caps_with_one_seam_source())
    )

    snapshot = context.relation_snapshot
    assert snapshot is not None
    assert context.topology_snapshot is not None
    assert len(context.topology_snapshot.patch_chains) == 4
    assert len(snapshot.scaffold_nodes) == 2
    assert len(snapshot.scaffold_edges) == 4
    assert len(snapshot.scaffold_node_incident_edge_relations) == 12
    sample_by_id = {
        sample.id: sample
        for sample in snapshot.patch_chain_endpoint_samples
    }
    node_by_id = {
        node.id: node
        for node in snapshot.scaffold_nodes
    }
    for relation in snapshot.scaffold_node_incident_edge_relations:
        node_vertex_ids = set(node_by_id[relation.scaffold_node_id].vertex_ids)
        for sample_id in (relation.first_endpoint_sample_id, relation.second_endpoint_sample_id):
            assert sample_id is None or sample_by_id[sample_id].vertex_id in node_vertex_ids
    relation_counts_by_node = {
        node.id: len([
            relation
            for relation in snapshot.scaffold_node_incident_edge_relations
            if relation.scaffold_node_id == node.id
        ])
        for node in snapshot.scaffold_nodes
    }
    assert set(relation_counts_by_node.values()) == {6}
    relation_kinds = {
        relation.kind
        for relation in snapshot.scaffold_node_incident_edge_relations
    }
    assert ScaffoldNodeIncidentEdgeRelationKind.MISSING_ENDPOINT_EVIDENCE not in relation_kinds
    assert ScaffoldNodeIncidentEdgeRelationKind.DEGRADED not in relation_kinds
    assert ScaffoldNodeIncidentEdgeRelationKind.ORTHOGONAL_CORNER in relation_kinds


def test_simple_tube_without_caps_emits_surface_sliding_relations_as_data() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_cylinder_tube_without_caps_with_one_seam_source())
    )

    snapshot = context.relation_snapshot
    assert snapshot is not None
    assert len(snapshot.side_surface_continuity_evidence) == 4
    sliding_relations = [
        relation
        for relation in snapshot.scaffold_node_incident_edge_relations
        if relation.kind is ScaffoldNodeIncidentEdgeRelationKind.SURFACE_SLIDING_CONTINUATION_CANDIDATE
    ]
    assert len(sliding_relations) == len(snapshot.side_surface_continuity_evidence)
    assert all(
        relation.evidence[0].data["same_side_surface_evidence_source"]
        == "side_surface_continuity_evidence_v0"
        for relation in sliding_relations
    )
    consumed_evidence_ids = {
        relation.evidence[0].data["side_surface_continuity_evidence_id"]
        for relation in sliding_relations
    }
    assert consumed_evidence_ids == {
        evidence.id
        for evidence in snapshot.side_surface_continuity_evidence
    }

    report = inspect_pipeline_context(context, detail="full")
    relations = report["relations"]
    assert relations["side_surface_continuity_evidence_count"] == 4
    assert len(relations["side_surface_continuity_evidence"]) == 4
    assert all(
        evidence["normal_evidence_source"] == "LOCAL_FACE_FAN_NORMAL"
        and evidence["first_endpoint_role"] == "END"
        and evidence["second_endpoint_role"] == "START"
        for evidence in relations["side_surface_continuity_evidence"]
    )


def test_scaffold_graph_relations_code_does_not_introduce_deferred_terms_or_imports() -> None:
    tree = ast.parse(SCAFFOLD_GRAPH_RELATIONS_MODULE.read_text(encoding="utf-8"))
    identifiers: set[str] = set()
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            identifiers.add(node.id)
        elif isinstance(node, ast.Attribute):
            identifiers.add(node.attr)
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            identifiers.add(node.name)
        elif isinstance(node, ast.arg):
            identifiers.add(node.arg)
        elif isinstance(node, ast.alias):
            identifiers.add(node.name.split(".")[-1])
            if node.asname:
                identifiers.add(node.asname)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)

    assert not identifiers & FORBIDDEN_TOKENS
    assert not any(imported.startswith(FORBIDDEN_IMPORTS) for imported in imports)


def _single_incident_relation(
    first_sample: PatchChainEndpointSample,
    second_sample: PatchChainEndpointSample,
):
    endpoint_relations = build_patch_chain_endpoint_relations((first_sample, second_sample))
    assert len(endpoint_relations) == 1
    edges = (
        _edge("a", ChainId("chain:a"), first_sample.patch_id),
        _edge("b", ChainId("chain:b"), second_sample.patch_id),
    )
    node = _node(first_sample.patch_chain_id, second_sample.patch_chain_id)

    side_surface_evidence, incident_relations, shared_relations = build_scaffold_graph_relations(
        scaffold_nodes=(node,),
        scaffold_edges=edges,
        endpoint_samples=(first_sample, second_sample),
        endpoint_relations=endpoint_relations,
        patch_adjacencies={},
    )

    assert side_surface_evidence == ()
    assert shared_relations == ()
    assert len(incident_relations) == 1
    return incident_relations[0]


def _sample(
    suffix: str,
    tangent,
    patch_id: PatchId,
    confidence: float = 1.0,
    owner_normal=(0.0, 0.0, 1.0),
    owner_normal_source: OwnerNormalSource = OwnerNormalSource.PATCH_AGGREGATE_NORMAL,
    endpoint_role: PatchChainEndpointRole = PatchChainEndpointRole.START,
) -> PatchChainEndpointSample:
    return PatchChainEndpointSample(
        id=f"sample:{suffix}",
        vertex_id=VertexId("vertex:one"),
        directional_evidence_id=f"directional_evidence:{suffix}",
        patch_chain_id=PatchChainId(f"patch_chain:{suffix}"),
        patch_id=patch_id,
        endpoint_role=endpoint_role,
        tangent_away_from_vertex=tangent,
        owner_normal=owner_normal,
        owner_normal_source=owner_normal_source,
        confidence=confidence,
    )


def _edge(
    suffix: str,
    chain_id: ChainId,
    patch_id: PatchId,
    start_node_id: str = "scaffold_node:one",
    end_node_id: str = "scaffold_node:two",
    loop_id: BoundaryLoopId | None = None,
) -> ScaffoldEdge:
    return ScaffoldEdge(
        id=f"scaffold_edge:patch_chain:{suffix}",
        patch_chain_id=PatchChainId(f"patch_chain:{suffix}"),
        chain_id=chain_id,
        patch_id=patch_id,
        loop_id=loop_id if loop_id is not None else BoundaryLoopId(f"loop:{suffix}"),
        start_scaffold_node_id=start_node_id,
        end_scaffold_node_id=end_node_id,
        confidence=1.0,
    )


def _loop_corner(
    suffix: str,
    previous_patch_chain_id: PatchChainId,
    next_patch_chain_id: PatchChainId,
    loop_id: BoundaryLoopId = BoundaryLoopId("loop:one"),
    position_in_loop: int = 0,
) -> LoopCorner:
    return LoopCorner(
        id=f"loop_corner:{suffix}",
        patch_id=PatchId("patch:one"),
        loop_id=loop_id,
        vertex_id=VertexId("vertex:one"),
        previous_patch_chain_id=previous_patch_chain_id,
        next_patch_chain_id=next_patch_chain_id,
        position_in_loop=position_in_loop,
    )


def _node(
    first_patch_chain_id: PatchChainId,
    second_patch_chain_id: PatchChainId,
    *extra_patch_chain_ids: PatchChainId,
) -> ScaffoldNode:
    return ScaffoldNode(
        id="scaffold_node:one",
        vertex_ids=(VertexId("vertex:one"),),
        source_vertex_ids=(),
        loop_corner_ids=(),
        patch_chain_endpoint_sample_ids=("sample:a", "sample:b"),
        patch_chain_endpoint_relation_ids=(),
        incident_patch_chain_ids=tuple(sorted(
            (first_patch_chain_id, second_patch_chain_id, *extra_patch_chain_ids),
            key=str,
        )),
        patch_ids=(PatchId("patch:one"),),
        confidence=1.0,
    )
