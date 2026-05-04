"""
Layer: tests

Rules:
- Layer 3 ScaffoldContinuityComponent evidence tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

import json

from scaffold_core.ids import BoundaryLoopId, ChainId, PatchChainId, PatchId
from scaffold_core.layer_3_relations.model import (
    PatchChainEndpointRole,
    RelationSnapshot,
    ScaffoldEdge,
    ScaffoldNodeIncidentEdgeRelation,
    ScaffoldNodeIncidentEdgeRelationKind,
)
from scaffold_core.layer_3_relations.scaffold_continuity import build_scaffold_continuity_components
from scaffold_core.pipeline.inspection import relation_summary_to_dict
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
from scaffold_core.tests.fixtures.closed_shared_loop import make_closed_shared_boundary_loop_source
from scaffold_core.tests.fixtures.cylinder_tube import (
    make_cylinder_tube_without_caps_with_one_seam_source,
    make_segmented_cylinder_tube_without_caps_with_one_seam_source,
)
from scaffold_core.tests.fixtures.l_shape import (
    make_two_patch_source_with_two_edge_seam_run,
    make_two_quad_folded_source_with_seam_on_shared_edge,
)


def test_surface_continuation_edges_become_one_component() -> None:
    components = _components(
        ("a", "b"),
        (_relation("ab", "a", "b", ScaffoldNodeIncidentEdgeRelationKind.SURFACE_CONTINUATION_CANDIDATE),),
    )

    assert len(components) == 1
    assert components[0].scaffold_edge_ids == ("scaffold_edge:a", "scaffold_edge:b")
    assert components[0].propagating_incident_relation_ids == ("relation:ab",)
    assert not components[0].is_ambiguous


def test_surface_sliding_continuation_edges_become_one_component() -> None:
    components = _components(
        ("a", "b"),
        (
            _relation(
                "ab",
                "a",
                "b",
                ScaffoldNodeIncidentEdgeRelationKind.SURFACE_SLIDING_CONTINUATION_CANDIDATE,
            ),
        ),
    )

    assert len(components) == 1
    assert components[0].scaffold_edge_ids == ("scaffold_edge:a", "scaffold_edge:b")
    assert components[0].propagating_incident_relation_ids == ("relation:ab",)


def test_orthogonal_corner_does_not_propagate() -> None:
    components = _components(
        ("a", "b"),
        (_relation("ab", "a", "b", ScaffoldNodeIncidentEdgeRelationKind.ORTHOGONAL_CORNER),),
    )

    assert [component.scaffold_edge_ids for component in components] == [
        ("scaffold_edge:a",),
        ("scaffold_edge:b",),
    ]
    assert all(component.blocked_incident_relation_ids == ("relation:ab",) for component in components)


def test_cross_surface_connector_does_not_propagate() -> None:
    components = _components(
        ("a", "b"),
        (_relation("ab", "a", "b", ScaffoldNodeIncidentEdgeRelationKind.CROSS_SURFACE_CONNECTOR),),
    )

    assert len(components) == 2
    assert all(component.propagating_incident_relation_ids == () for component in components)


def test_straight_continuation_candidate_is_weak_and_does_not_propagate() -> None:
    components = _components(
        ("a", "b"),
        (_relation("ab", "a", "b", ScaffoldNodeIncidentEdgeRelationKind.STRAIGHT_CONTINUATION_CANDIDATE),),
    )

    assert len(components) == 2
    assert all(component.propagating_incident_relation_ids == () for component in components)
    assert all(component.blocked_incident_relation_ids == ("relation:ab",) for component in components)


def test_oblique_connector_does_not_propagate() -> None:
    components = _components(
        ("a", "b"),
        (_relation("ab", "a", "b", ScaffoldNodeIncidentEdgeRelationKind.OBLIQUE_CONNECTOR),),
    )

    assert len(components) == 2
    assert all(component.propagating_incident_relation_ids == () for component in components)


def test_same_ray_ambiguous_does_not_propagate_and_marks_ambiguity() -> None:
    components = _components(
        ("a", "b"),
        (_relation("ab", "a", "b", ScaffoldNodeIncidentEdgeRelationKind.SAME_RAY_AMBIGUOUS),),
    )

    assert len(components) == 2
    assert all(component.is_ambiguous for component in components)
    assert all(component.ambiguous_incident_relation_ids == ("relation:ab",) for component in components)


def test_missing_and_degraded_evidence_do_not_propagate() -> None:
    components = _components(
        ("a", "b", "c"),
        (
            _relation("ab", "a", "b", ScaffoldNodeIncidentEdgeRelationKind.MISSING_ENDPOINT_EVIDENCE),
            _relation("bc", "b", "c", ScaffoldNodeIncidentEdgeRelationKind.DEGRADED),
        ),
    )

    assert len(components) == 3
    assert all(component.propagating_incident_relation_ids == () for component in components)


def test_chained_surface_continuations_become_one_component() -> None:
    components = _components(
        ("a", "b", "c"),
        (
            _relation("ab", "a", "b", ScaffoldNodeIncidentEdgeRelationKind.SURFACE_CONTINUATION_CANDIDATE),
            _relation("bc", "b", "c", ScaffoldNodeIncidentEdgeRelationKind.SURFACE_CONTINUATION_CANDIDATE),
        ),
    )

    assert len(components) == 1
    assert components[0].scaffold_edge_ids == ("scaffold_edge:a", "scaffold_edge:b", "scaffold_edge:c")
    assert components[0].propagating_incident_relation_ids == ("relation:ab", "relation:bc")


def test_branching_surface_candidates_mark_ambiguity_without_path_choice() -> None:
    components = _components(
        ("a", "b", "c"),
        (
            _relation("ab", "a", "b", ScaffoldNodeIncidentEdgeRelationKind.SURFACE_CONTINUATION_CANDIDATE),
            _relation("ac", "a", "c", ScaffoldNodeIncidentEdgeRelationKind.SURFACE_CONTINUATION_CANDIDATE),
        ),
    )

    assert len(components) == 1
    assert components[0].scaffold_edge_ids == ("scaffold_edge:a", "scaffold_edge:b", "scaffold_edge:c")
    assert components[0].is_ambiguous
    assert components[0].ambiguous_incident_relation_ids == ("relation:ab", "relation:ac")


def test_competing_surface_sliding_candidates_mark_ambiguity_without_path_choice() -> None:
    components = _components(
        ("a", "b", "c"),
        (
            _relation(
                "ab",
                "a",
                "b",
                ScaffoldNodeIncidentEdgeRelationKind.SURFACE_SLIDING_CONTINUATION_CANDIDATE,
            ),
            _relation(
                "ac",
                "a",
                "c",
                ScaffoldNodeIncidentEdgeRelationKind.SURFACE_SLIDING_CONTINUATION_CANDIDATE,
            ),
        ),
    )

    assert len(components) == 1
    assert components[0].scaffold_edge_ids == ("scaffold_edge:a", "scaffold_edge:b", "scaffold_edge:c")
    assert components[0].is_ambiguous
    assert components[0].ambiguous_incident_relation_ids == ("relation:ab", "relation:ac")


def test_simple_tube_without_caps_merges_through_explicit_sliding_relations() -> None:
    snapshot = _snapshot(make_cylinder_tube_without_caps_with_one_seam_source)
    components = snapshot.scaffold_continuity_components
    sliding_relation_ids = {
        relation.id
        for relation in snapshot.scaffold_node_incident_edge_relations
        if relation.kind is ScaffoldNodeIncidentEdgeRelationKind.SURFACE_SLIDING_CONTINUATION_CANDIDATE
    }

    assert len(components) == 1
    assert sorted(len(component.scaffold_edge_ids) for component in components) == [4]
    assert {
        relation_id
        for component in components
        for relation_id in component.propagating_incident_relation_ids
    } == sliding_relation_ids


def test_segmented_tube_without_caps_merges_through_explicit_sliding_relations() -> None:
    components = _snapshot_components(make_segmented_cylinder_tube_without_caps_with_one_seam_source)

    assert len(components) == 1
    assert sorted(len(component.scaffold_edge_ids) for component in components) == [4]


def test_folded_90_seam_propagates_only_through_explicit_sliding_relations() -> None:
    snapshot = run_pass_1_relations(
        run_pass_0(make_two_quad_folded_source_with_seam_on_shared_edge())
    ).relation_snapshot

    assert snapshot is not None
    sliding_relation_ids = {
        relation.id
        for relation in snapshot.scaffold_node_incident_edge_relations
        if relation.kind is ScaffoldNodeIncidentEdgeRelationKind.SURFACE_SLIDING_CONTINUATION_CANDIDATE
    }
    assert len(sliding_relation_ids) == len(snapshot.side_surface_continuity_evidence)
    assert {
        relation_id
        for component in snapshot.scaffold_continuity_components
        for relation_id in component.propagating_incident_relation_ids
    } == sliding_relation_ids
    assert len(snapshot.scaffold_continuity_components) == 2


def test_closed_shared_loop_has_no_sliding_continuity_propagation() -> None:
    snapshot = run_pass_1_relations(
        run_pass_0(make_closed_shared_boundary_loop_source())
    ).relation_snapshot

    assert snapshot is not None
    assert not any(
        relation.kind is ScaffoldNodeIncidentEdgeRelationKind.SURFACE_SLIDING_CONTINUATION_CANDIDATE
        for relation in snapshot.scaffold_node_incident_edge_relations
    )
    assert all(
        not component.propagating_incident_relation_ids
        for component in snapshot.scaffold_continuity_components
    )


def test_planar_l_seam_explicit_side_surface_evidence_promotes_only_through_relations() -> None:
    snapshot = run_pass_1_relations(
        run_pass_0(make_two_patch_source_with_two_edge_seam_run())
    ).relation_snapshot

    assert snapshot is not None
    assert any(
        relation.kind is ScaffoldNodeIncidentEdgeRelationKind.SURFACE_CONTINUATION_CANDIDATE
        for relation in snapshot.scaffold_node_incident_edge_relations
    )
    sliding_relation_ids = {
        relation.id
        for relation in snapshot.scaffold_node_incident_edge_relations
        if relation.kind is ScaffoldNodeIncidentEdgeRelationKind.SURFACE_SLIDING_CONTINUATION_CANDIDATE
    }
    assert len(sliding_relation_ids) == len(snapshot.side_surface_continuity_evidence)
    assert {
        relation_id
        for component in snapshot.scaffold_continuity_components
        for relation_id in component.propagating_incident_relation_ids
    } >= sliding_relation_ids
    assert len(snapshot.scaffold_continuity_components) == 1


def test_every_scaffold_edge_is_assigned_exactly_once() -> None:
    edge_ids = ("a", "b", "c", "d")
    components = _components(
        edge_ids,
        (_relation("ab", "a", "b", ScaffoldNodeIncidentEdgeRelationKind.SURFACE_CONTINUATION_CANDIDATE),),
    )

    assigned_edge_ids = [
        edge_id
        for component in components
        for edge_id in component.scaffold_edge_ids
    ]
    assert sorted(assigned_edge_ids) == [f"scaffold_edge:{edge_id}" for edge_id in edge_ids]
    assert len(assigned_edge_ids) == len(set(assigned_edge_ids))
    assert ("scaffold_edge:c",) in [component.scaffold_edge_ids for component in components]
    assert ("scaffold_edge:d",) in [component.scaffold_edge_ids for component in components]


def test_inspection_serializes_continuity_components() -> None:
    edges = _edges(("a", "b"))
    components = build_scaffold_continuity_components(
        edges,
        (_relation("ab", "a", "b", ScaffoldNodeIncidentEdgeRelationKind.SURFACE_CONTINUATION_CANDIDATE),),
    )
    report = relation_summary_to_dict(
        RelationSnapshot(
            scaffold_edges=edges,
            scaffold_continuity_components=components,
        ),
        detail="full",
    )

    json.dumps(report)
    assert report["scaffold_continuity_component_count"] == 1
    assert report["scaffold_continuity_components"] == [
        {
            "id": "scaffold_continuity_component:0",
            "scaffold_edge_ids": ["scaffold_edge:a", "scaffold_edge:b"],
            "scaffold_node_ids": ["scaffold_node:shared"],
            "propagating_incident_relation_ids": ["relation:ab"],
            "ambiguous_incident_relation_ids": [],
            "blocked_incident_relation_ids": [],
            "propagation_policy": "scaffold_continuity_component_v0",
            "is_ambiguous": False,
            "confidence": 1.0,
            "evidence": [
                {
                    "source": "layer_3_relations.scaffold_continuity",
                    "summary": "continuity-family component over existing ScaffoldEdges",
                    "data": {
                        "policy": "scaffold_continuity_component_v0",
                        "component_id": "scaffold_continuity_component:0",
                        "scaffold_edge_ids": ["scaffold_edge:a", "scaffold_edge:b"],
                        "scaffold_node_ids": ["scaffold_node:shared"],
                        "propagating_incident_relation_ids": ["relation:ab"],
                        "ambiguous_incident_relation_ids": [],
                        "blocked_incident_relation_ids": [],
                        "propagating_kinds": [
                            "SURFACE_CONTINUATION_CANDIDATE",
                            "SURFACE_SLIDING_CONTINUATION_CANDIDATE",
                        ],
                        "confidence": 1.0,
                    },
                }
            ],
        }
    ]


def _components(
    edge_suffixes: tuple[str, ...],
    relations: tuple[ScaffoldNodeIncidentEdgeRelation, ...],
):
    return build_scaffold_continuity_components(_edges(edge_suffixes), relations)


def _snapshot_components(source_factory):
    return _snapshot(source_factory).scaffold_continuity_components


def _snapshot(source_factory):
    snapshot = run_pass_1_relations(run_pass_0(source_factory())).relation_snapshot
    assert snapshot is not None
    return snapshot


def _edges(suffixes: tuple[str, ...]) -> tuple[ScaffoldEdge, ...]:
    return tuple(_edge(suffix) for suffix in suffixes)


def _edge(suffix: str) -> ScaffoldEdge:
    return ScaffoldEdge(
        id=f"scaffold_edge:{suffix}",
        patch_chain_id=PatchChainId(f"patch_chain:{suffix}"),
        chain_id=ChainId(f"chain:{suffix}"),
        patch_id=PatchId("patch:test"),
        loop_id=BoundaryLoopId("loop:test"),
        start_scaffold_node_id="scaffold_node:shared",
        end_scaffold_node_id="scaffold_node:shared",
        confidence=1.0,
    )


def _relation(
    suffix: str,
    first_edge_suffix: str,
    second_edge_suffix: str,
    kind: ScaffoldNodeIncidentEdgeRelationKind,
) -> ScaffoldNodeIncidentEdgeRelation:
    return ScaffoldNodeIncidentEdgeRelation(
        id=f"relation:{suffix}",
        kind=kind,
        policy="test",
        scaffold_node_id="scaffold_node:shared",
        first_scaffold_edge_id=f"scaffold_edge:{first_edge_suffix}",
        second_scaffold_edge_id=f"scaffold_edge:{second_edge_suffix}",
        first_patch_chain_id=PatchChainId(f"patch_chain:{first_edge_suffix}"),
        second_patch_chain_id=PatchChainId(f"patch_chain:{second_edge_suffix}"),
        first_endpoint_role=PatchChainEndpointRole.START,
        second_endpoint_role=PatchChainEndpointRole.END,
        first_endpoint_sample_id=None,
        second_endpoint_sample_id=None,
        patch_chain_endpoint_relation_id=None,
        direction_dot=None,
        normal_dot=None,
        confidence=1.0,
    )
