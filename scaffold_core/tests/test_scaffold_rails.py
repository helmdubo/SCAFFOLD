"""
Layer: tests

Rules:
- ScaffoldTrace and ScaffoldRail tests use in-repo synthetic fixtures only.
- Tests assert Layer 3 evidence contracts, not Layer 5 solve behavior.
- Branches, loops and occurrence ambiguity must remain explicit.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from scaffold_core.layer_3_relations.scaffold_rails import (
    MemberTraceEndpoints,
    cut_scaffold_rail,
    rail_member_endpoints,
)
from scaffold_core.pipeline.inspection import inspect_pipeline_context
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
from scaffold_core.tests.fixtures.beveled_wall_corner import make_beveled_wall_corner_source
from scaffold_core.tests.fixtures.cylinder_tube import (
    make_cylinder_tube_without_caps_with_two_seams_source,
)
from scaffold_core.tests.fixtures.extruded_cross import make_extruded_cross_source
from scaffold_core.tests.fixtures.l_corridor_tunnel import make_l_corridor_tunnel_seamed_folds_source
from scaffold_core.tests.fixtures.t_vertex_wall import make_t_vertex_wall_source
from scaffold_core.tests.fixtures.tube_with_cap import make_tube_with_cap_source


def test_l_corridor_emits_open_consumable_length_rails() -> None:
    context = run_pass_1_relations(run_pass_0(make_l_corridor_tunnel_seamed_folds_source()))
    relations = context.relation_snapshot

    assert len(relations.scaffold_traces) == len(relations.connected_direction_families)
    assert len(relations.scaffold_rails) == len(relations.connected_direction_families)

    open_length_rails = tuple(
        rail
        for rail in relations.scaffold_rails
        if rail.is_consumable_by_g5a
        and len(rail.ordered_member_directional_evidence_ids) == 3
        and _family_patch_ids(relations, rail.direction_family_id)
        == {"patch:seed:f_ceiling", "patch:seed:f_floor", "patch:seed:f_wall"}
    )
    assert len(open_length_rails) == 2
    for rail in open_length_rails:
        assert not rail.is_closed_loop
        assert rail.first_trace_node_id is not None
        assert rail.last_trace_node_id is not None
        assert rail.first_trace_node_id != rail.last_trace_node_id
        assert set(rail.orientation_sign_by_member.values()) <= {-1, 1}
        assert rail.diagnostics == ()
        trace = _trace_for_rail(relations, rail.id)
        assert trace.direction_family_id == rail.direction_family_id
        assert trace.ordered_member_directional_evidence_ids == rail.ordered_member_directional_evidence_ids


def test_two_seam_cylinder_rings_preserve_loop_ambiguity() -> None:
    context = run_pass_1_relations(run_pass_0(make_cylinder_tube_without_caps_with_two_seams_source()))
    relations = context.relation_snapshot

    ring_rails = tuple(
        rail
        for rail in relations.scaffold_rails
        if len(rail.ordered_member_directional_evidence_ids) == 4
        and _family_patch_ids(relations, rail.direction_family_id)
        == {"patch:seed:f0", "patch:seed:f2"}
    )
    assert len(ring_rails) == 2
    for rail in ring_rails:
        assert rail.is_closed_loop
        assert not rail.is_consumable_by_g5a
        assert set(rail.loop_ambiguity_records) == {"closed_loop"}
        assert set(rail.orientation_sign_by_member.values()) == {0}
        assert rail.diagnostics == ()


def test_extruded_cross_side_rails_stay_distinct_with_occurrence_diagnostics() -> None:
    context = run_pass_1_relations(run_pass_0(make_extruded_cross_source()))
    relations = context.relation_snapshot

    bottom_rail = _rail_with_member_fragment(relations, "patch:seed:f_side_0:0:1")
    top_rail = _rail_with_member_fragment(relations, "patch:seed:f_side_0:0:3")

    assert bottom_rail.id != top_rail.id
    assert len(bottom_rail.ordered_member_directional_evidence_ids) == 12
    assert len(top_rail.ordered_member_directional_evidence_ids) == 12
    assert not bottom_rail.is_closed_loop
    assert not top_rail.is_closed_loop
    assert not bottom_rail.is_consumable_by_g5a
    assert not top_rail.is_consumable_by_g5a
    assert any(item.startswith("coincident_open_trace_endpoints:") for item in bottom_rail.diagnostics)
    assert any(item.startswith("coincident_open_trace_endpoints:") for item in top_rail.diagnostics)


def test_tube_with_cap_keeps_cap_and_side_rails_separate() -> None:
    context = run_pass_1_relations(run_pass_0(make_tube_with_cap_source()))
    relations = context.relation_snapshot

    assert not any(
        any("f_cap" in patch_id for patch_id in _family_patch_ids(relations, rail.direction_family_id))
        and any("f0" in patch_id for patch_id in _family_patch_ids(relations, rail.direction_family_id))
        for rail in relations.scaffold_rails
    )
    assert len(_rails_with_member_fragment(relations, "patch:seed:f_cap:0:0")) == 4


def test_fold_line_rail_is_one_station_of_both_hinge_uses() -> None:
    """The two uses of a hinge cover the same edges: one station, not two members in a row."""

    context = run_pass_1_relations(run_pass_0(make_beveled_wall_corner_source()))
    relations = context.relation_snapshot
    evidence_by_id = {item.id: item for item in relations.patch_chain_directional_evidence}

    fold_rails = tuple(
        rail
        for rail in relations.scaffold_rails
        if len(rail.ordered_member_directional_evidence_ids) == 2
        and len({evidence_by_id[member].patch_id for member in rail.ordered_member_directional_evidence_ids}) == 2
        and len({
            frozenset(evidence_by_id[member].source_edge_ids)
            for member in rail.ordered_member_directional_evidence_ids
        }) == 1
    )
    assert len(fold_rails) == 2
    for rail in fold_rails:
        assert rail.is_consumable_by_g5a
        assert rail.diagnostics == ()
        assert sorted(rail.orientation_sign_by_member.values()) == [-1, 1]
        assert rail.first_trace_node_id != rail.last_trace_node_id


def test_rail_orders_hinge_stations_through_their_node() -> None:
    """The T-vertex wall bottom is two hinges in a line: two stations linked at w1."""

    context = run_pass_1_relations(run_pass_0(make_t_vertex_wall_source()))
    relations = context.relation_snapshot
    rail = _rail_with_member_fragment(relations, "patch:seed:f_wall:0:1:")
    node_by_id = {node.id: node for node in relations.scaffold_nodes}
    evidence_by_id = {item.id: item for item in relations.patch_chain_directional_evidence}

    assert rail.is_consumable_by_g5a
    assert rail.diagnostics == ()
    node_sources = [node_by_id[node_id].source_vertex_ids for node_id in rail.ordered_trace_node_ids]
    assert node_sources in ([("w0",), ("w1",), ("w2",)], [("w2",), ("w1",), ("w0",)])
    members = rail.ordered_member_directional_evidence_ids
    assert len(members) == 4
    for first, second in (members[:2], members[2:]):
        assert set(evidence_by_id[first].source_edge_ids) == set(evidence_by_id[second].source_edge_ids)
        assert rail.orientation_sign_by_member[first] == -rail.orientation_sign_by_member[second]
    wall_signs = {
        rail.orientation_sign_by_member[member]
        for member in members
        if "f_wall" in str(evidence_by_id[member].patch_id)
    }
    assert len(wall_signs) == 1


def test_cut_rail_opens_a_loop_only_where_the_cut_is() -> None:
    context = run_pass_1_relations(run_pass_0(make_cylinder_tube_without_caps_with_two_seams_source()))
    relations = context.relation_snapshot
    endpoints = rail_member_endpoints(relations.run_endpoint_junctions)
    ring_rail = next(rail for rail in relations.scaffold_rails if rail.is_closed_loop)
    family = next(
        family for family in relations.connected_direction_families if family.id == ring_rail.direction_family_id
    )
    members = family.member_directional_evidence_ids
    seam_chains = sorted({str(adjacency.chain_id) for adjacency in relations.patch_adjacencies.values()})
    assert len(seam_chains) == 2

    (closed,) = cut_scaffold_rail(family, endpoints, members, seam_chains)
    assert not closed.is_ordered
    assert closed.diagnostics == ("closed_loop",)

    (opened,) = cut_scaffold_rail(family, endpoints, members, seam_chains[:1])
    assert opened.is_ordered
    assert sorted(opened.ordered_member_directional_evidence_ids) == sorted(members)
    assert set(opened.orientation_sign_by_member.values()) <= {-1, 1}

    halves = cut_scaffold_rail(family, endpoints, members, ())
    patch_of = {item.id: item.patch_id for item in relations.patch_chain_directional_evidence}
    assert len(halves) == 2
    assert all(half.is_ordered for half in halves)
    assert all(
        len({patch_of[member] for member in half.ordered_member_directional_evidence_ids}) == 1
        for half in halves
    )


def test_cut_rail_keeps_a_branch_unordered() -> None:
    """A station with three links never picks a continuation (DD-47 draft branch policy)."""

    def crossing(first: str, second: str, node: str) -> SimpleNamespace:
        return SimpleNamespace(
            kind="SCAFFOLD_NODE",
            first_directional_evidence_id=first,
            second_directional_evidence_id=second,
            first_patch_id=f"patch:{first}",
            second_patch_id=f"patch:{second}",
            shared_chain_id=f"chain:{first}:{second}",
            scaffold_node_id=node,
            run_endpoint_junction_id=None,
        )

    family = SimpleNamespace(
        id="family:branch",
        member_directional_evidence_ids=("m0", "m1", "m2", "m3"),
        crossing_records=(crossing("m0", "m1", "n1"), crossing("m0", "m2", "n2"), crossing("m0", "m3", "n3")),
    )
    endpoints = {
        "m0": MemberTraceEndpoints("n1", "n2"),
        "m1": MemberTraceEndpoints("n0", "n1"),
        "m2": MemberTraceEndpoints("n2", "n4"),
        "m3": MemberTraceEndpoints("n3", "n5"),
    }
    kept_chains = {crossing.shared_chain_id for crossing in family.crossing_records}

    (segment,) = cut_scaffold_rail(family, endpoints, family.member_directional_evidence_ids, kept_chains)
    assert not segment.is_ordered
    assert "branch:station:m0" in segment.diagnostics
    assert set(segment.orientation_sign_by_member.values()) == {0}


def test_scaffold_rails_inspect_full_serializes_typed_records() -> None:
    context = run_pass_1_relations(run_pass_0(make_l_corridor_tunnel_seamed_folds_source()))
    relations = context.relation_snapshot

    report = inspect_pipeline_context(context, detail="full")
    json.dumps(report)
    serialized = report["relations"]
    assert serialized["scaffold_trace_count"] == len(relations.scaffold_traces)
    assert serialized["scaffold_rail_count"] == len(relations.scaffold_rails)
    assert len(serialized["scaffold_traces"]) == len(relations.scaffold_traces)
    assert len(serialized["scaffold_rails"]) == len(relations.scaffold_rails)

    consumable = next(rail for rail in serialized["scaffold_rails"] if rail["is_consumable_by_g5a"])
    assert "ordered_member_directional_evidence_ids" in consumable
    assert "orientation_sign_by_member" in consumable
    assert "crossing_records" in consumable


def _family_patch_ids(relations, family_id: str) -> set[str]:
    family = next(family for family in relations.connected_direction_families if family.id == family_id)
    return {str(patch_id) for patch_id in family.patch_ids}


def _trace_for_rail(relations, rail_id: str):
    rail = next(rail for rail in relations.scaffold_rails if rail.id == rail_id)
    return next(trace for trace in relations.scaffold_traces if trace.id == rail.scaffold_trace_id)


def _rails_with_member_fragment(relations, member_fragment: str):
    return tuple(
        rail
        for rail in relations.scaffold_rails
        if any(member_fragment in member_id for member_id in rail.ordered_member_directional_evidence_ids)
    )


def _rail_with_member_fragment(relations, member_fragment: str):
    rails = _rails_with_member_fragment(relations, member_fragment)
    assert len(rails) == 1
    return rails[0]
