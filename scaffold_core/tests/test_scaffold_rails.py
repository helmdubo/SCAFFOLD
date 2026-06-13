"""
Layer: tests

Rules:
- ScaffoldTrace and ScaffoldRail tests use in-repo synthetic fixtures only.
- Tests assert Layer 3 evidence contracts, not Layer 5 solve behavior.
- Branches, loops and occurrence ambiguity must remain explicit.
"""

from __future__ import annotations

import json

from scaffold_core.pipeline.inspection import inspect_pipeline_context
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
from scaffold_core.tests.fixtures.cylinder_tube import (
    make_cylinder_tube_without_caps_with_two_seams_source,
)
from scaffold_core.tests.fixtures.extruded_cross import make_extruded_cross_source
from scaffold_core.tests.fixtures.l_corridor_tunnel import make_l_corridor_tunnel_seamed_folds_source
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
