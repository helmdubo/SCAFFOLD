"""
Layer: tests

Rules:
- ConnectedDirectionFamily tests use in-repo synthetic fixtures only.
- Tests may inspect Layer 3 evidence but must not define production logic.
- AlignmentClass behavior remains covered separately and must not be migrated here.
"""

from __future__ import annotations

import json
from pathlib import Path

from scaffold_core.ids import SourceEdgeId, SourceFaceId, SourceMeshId, SourceVertexId
from scaffold_core.layer_0_source.marks import SourceMark, SourceMarkKind
from scaffold_core.layer_0_source.snapshot import (
    MeshEdgeRef,
    MeshFaceRef,
    MeshVertexRef,
    SourceMeshSnapshot,
)
from scaffold_core.layer_2_geometry.measures import dot, normalize
from scaffold_core.layer_3_relations.model import PatchChainEndpointRole
from scaffold_core.pipeline.inspection import inspect_pipeline_context
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
from scaffold_core.tests.fixtures.beveled_wall_corner import make_beveled_wall_corner_source
from scaffold_core.tests.fixtures.cylinder_tube import (
    make_cylinder_tube_without_caps_with_two_seams_source,
)
from scaffold_core.tests.fixtures.detached_parallel_walls import make_detached_parallel_walls_source
from scaffold_core.tests.fixtures.extruded_cross import make_extruded_cross_source
from scaffold_core.tests.fixtures.l_corridor_tunnel import make_l_corridor_tunnel_seamed_folds_source
from scaffold_core.tests.fixtures.l_corridor_tunnel import make_l_corridor_tunnel_single_patch_source
from scaffold_core.tests.fixtures.single_patch import make_single_quad_source
from scaffold_core.tests.fixtures.tube_with_cap import make_tube_with_cap_source


def test_detached_parallel_walls_connected_families_do_not_cross_shells() -> None:
    context = run_pass_1_relations(run_pass_0(make_detached_parallel_walls_source()))
    relations = context.relation_snapshot

    assert len(relations.alignment_classes) == 2
    for alignment_class in relations.alignment_classes:
        assert len(alignment_class.patch_ids) == 2
    assert all(len(family.patch_ids) == 1 for family in relations.connected_direction_families)


def test_l_corridor_tunnel_connected_families_span_length_and_width() -> None:
    context = run_pass_1_relations(run_pass_0(make_l_corridor_tunnel_seamed_folds_source()))
    relations = context.relation_snapshot

    assert _has_family_with_patches(
        relations,
        ("f_floor", "f_wall", "f_ceiling"),
        directions=((1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
    )
    assert _has_family_with_patches(
        relations,
        ("f_floor", "f_wall", "f_ceiling"),
        directions=((0.0, 1.0, 0.0),),
    )


def test_beveled_wall_corner_connected_families_span_horizontal_and_vertical() -> None:
    context = run_pass_1_relations(run_pass_0(make_beveled_wall_corner_source()))
    relations = context.relation_snapshot

    assert _has_family_with_patches(
        relations,
        ("f_wall_a", "f_chamfer", "f_wall_b"),
        directions=((1.0, 0.0, 0.0), (1.0, -1.0, 0.0), (0.0, 1.0, 0.0)),
    )
    assert _has_family_with_patches(
        relations,
        ("f_wall_a", "f_chamfer", "f_wall_b"),
        directions=((0.0, 0.0, 1.0),),
    )


def test_tube_with_cap_connected_families_keep_cap_and_side_separate() -> None:
    context = run_pass_1_relations(run_pass_0(make_tube_with_cap_source()))
    relations = context.relation_snapshot

    cap_side_families = tuple(
        family
        for family in relations.connected_direction_families
        if any("f_cap" in str(patch_id) for patch_id in family.patch_ids)
        and any("f0" in str(patch_id) for patch_id in family.patch_ids)
    )
    assert cap_side_families == ()
    assert len(_families_with_member_fragment(relations, "patch:seed:f0:0:1")) == 1
    assert len(_families_with_member_fragment(relations, "patch:seed:f0:0:3")) == 1
    assert len(_families_with_member_fragment(relations, "patch:seed:f_cap:0:0")) == 4


def test_two_seam_cylinder_connected_families_keep_top_and_bottom_rings() -> None:
    context = run_pass_1_relations(run_pass_0(make_cylinder_tube_without_caps_with_two_seams_source()))
    relations = context.relation_snapshot

    ring_families = tuple(
        family
        for family in relations.connected_direction_families
        if set(str(patch_id) for patch_id in family.patch_ids) == {"patch:seed:f0", "patch:seed:f2"}
        and len(family.member_directional_evidence_ids) == 2
        and all(record.kind == "SCAFFOLD_NODE" for record in family.crossing_records)
    )
    assert len(ring_families) == 2
    assert all(len(family.crossing_records) == 2 for family in ring_families)


def test_extruded_cross_connected_families_are_per_patch_use_geodesic() -> None:
    context = run_pass_1_relations(run_pass_0(make_extruded_cross_source()))
    relations = context.relation_snapshot

    bottom_rim = _single_family_with_member_fragment(relations, "patch:seed:f_side_0:0:1")
    top_rim = _single_family_with_member_fragment(relations, "patch:seed:f_side_0:0:3")
    assert bottom_rim.id != top_rim.id
    assert len(bottom_rim.member_directional_evidence_ids) == 12
    assert len(top_rim.member_directional_evidence_ids) == 12
    assert all(record.kind == "IN_PATCH_GEODESIC" for record in bottom_rim.crossing_records)
    assert all(record.kind == "IN_PATCH_GEODESIC" for record in top_rim.crossing_records)
    assert all(record.measured_angle_radians is not None for record in top_rim.crossing_records)

    seam_families = (
        *_families_with_member_fragment(relations, "patch:seed:f_side_0:0:0"),
        *_families_with_member_fragment(relations, "patch:seed:f_side_0:0:2"),
    )
    assert len(seam_families) == 2
    assert all(len(family.member_directional_evidence_ids) == 1 for family in seam_families)
    assert all(not family.crossing_records for family in seam_families)

    assert len(_families_with_member_fragment(relations, "patch:seed:f_cap_top:0:0")) == 12
    assert len(_families_with_member_fragment(relations, "patch:seed:f_cap_bottom:0:0")) == 12


def test_artist_cross_band_keeps_seam_duplicates_out_of_run_endpoint_junctions() -> None:
    context = run_pass_1_relations(run_pass_0(_load_artist_cross_band_source()))
    relations = context.relation_snapshot

    _assert_junction_occurrences_share_source_vertex(context)
    top_rim = _single_family_with_member_fragment(relations, "patch:seed:f1:0:0")
    bottom_rim = _single_family_with_member_fragment(relations, "patch:seed:f1:0:2")
    assert top_rim.id != bottom_rim.id
    assert len(top_rim.member_directional_evidence_ids) == 10
    assert len(bottom_rim.member_directional_evidence_ids) == 10

    assert all(
        len(family.member_directional_evidence_ids) == 1
        for family in _families_with_member_fragment(relations, "patch:seed:f0:0:0")
    )
    assert all(
        len(family.member_directional_evidence_ids) == 1
        for family in _families_with_member_fragment(relations, "patch:seed:f4:0:0")
    )
    assert len(_single_family_with_member_fragment(relations, "patch:seed:f1:0:1").member_directional_evidence_ids) == 1
    assert len(_single_family_with_member_fragment(relations, "patch:seed:f1:0:3").member_directional_evidence_ids) == 1


def test_in_patch_geodesic_merges_folded_single_patch_but_not_quad_corners() -> None:
    tunnel = run_pass_1_relations(run_pass_0(make_l_corridor_tunnel_single_patch_source()))
    tunnel_families = tuple(
        family
        for family in tunnel.relation_snapshot.connected_direction_families
        if len(family.member_directional_evidence_ids) == 3
        and all(record.kind == "IN_PATCH_GEODESIC" for record in family.crossing_records)
    )
    assert len(tunnel_families) == 2

    wall = run_pass_1_relations(run_pass_0(make_single_quad_source()))
    assert all(
        len(family.member_directional_evidence_ids) == 1
        for family in wall.relation_snapshot.connected_direction_families
    )


def test_connected_direction_families_carry_provenance_and_inspect_full() -> None:
    context = run_pass_1_relations(run_pass_0(make_cylinder_tube_without_caps_with_two_seams_source()))
    relations = context.relation_snapshot

    family = next(family for family in relations.connected_direction_families if family.crossing_records)
    assert family.member_directional_evidence_ids
    assert family.crossing_records
    assert family.confidence > 0.0
    assert all(record.signed_dihedral_radians is not None for record in family.crossing_records)
    assert any(
        record.scaffold_node_id is not None
        or record.shared_chain_id is not None
        for record in family.crossing_records
    )
    assert set(family.ordered_member_directional_evidence_ids) == set(family.member_directional_evidence_ids)
    assert set(family.member_map) == set(family.member_directional_evidence_ids)
    for member_id, member in family.member_map.items():
        evidence = next(
            evidence
            for evidence in relations.patch_chain_directional_evidence
            if evidence.id == member_id
        )
        assert member[0] == evidence.patch_chain_id
        assert member[1] is not None
        assert member[2] is not None
        assert member[3] is not None

    report = inspect_pipeline_context(context, detail="full")
    json.dumps(report)
    serialized_families = report["relations"]["connected_direction_families"]
    assert len(serialized_families) == len(relations.connected_direction_families)
    assert any(serialized["crossing_records"] for serialized in serialized_families)
    serialized_family = next(serialized for serialized in serialized_families if serialized["crossing_records"])
    serialized_crossing = serialized_family["crossing_records"][0]
    assert "first_directional_evidence_id" in serialized_crossing
    assert "transported_direction_dot" in serialized_crossing
    assert "measured_angle_radians" in serialized_crossing
    assert "run_endpoint_junction_id" in serialized_crossing
    assert "ordered_member_directional_evidence_ids" in serialized_family
    assert "member_map" in serialized_family


def _has_family_with_patches(relations, patch_fragments, directions) -> bool:
    for family in relations.connected_direction_families:
        if not all(
            any(fragment in str(patch_id) for patch_id in family.patch_ids)
            for fragment in patch_fragments
        ):
            continue
        members = tuple(
            evidence
            for evidence in relations.patch_chain_directional_evidence
            if evidence.id in family.member_directional_evidence_ids
        )
        if all(
            any(_direction_matches(member.direction, direction) for member in members)
            for direction in directions
        ):
            return True
    return False


def _families_with_member_fragment(relations, member_fragment: str):
    return tuple(
        family
        for family in relations.connected_direction_families
        if any(member_fragment in member_id for member_id in family.member_directional_evidence_ids)
    )


def _single_family_with_member_fragment(relations, member_fragment: str):
    families = _families_with_member_fragment(relations, member_fragment)
    assert len(families) == 1
    return families[0]


def _load_artist_cross_band_source() -> SourceMeshSnapshot:
    data = json.loads((Path(__file__).with_name("data") / "artist_cross_band.json").read_text())
    return SourceMeshSnapshot(
        id=SourceMeshId(data["id"]),
        vertices={
            SourceVertexId(vertex_id): MeshVertexRef(SourceVertexId(vertex_id), tuple(position))
            for vertex_id, position in data["vertices"].items()
        },
        edges={
            SourceEdgeId(edge_id): MeshEdgeRef(
                SourceEdgeId(edge_id),
                tuple(SourceVertexId(vertex_id) for vertex_id in vertex_ids),
            )
            for edge_id, vertex_ids in data["edges"].items()
        },
        faces={
            SourceFaceId(face_id): MeshFaceRef(
                SourceFaceId(face_id),
                tuple(SourceVertexId(vertex_id) for vertex_id in face["vertex_ids"]),
                tuple(SourceEdgeId(edge_id) for edge_id in face["edge_ids"]),
            )
            for face_id, face in data["faces"].items()
        },
        selected_face_ids=tuple(SourceFaceId(face_id) for face_id in data["selected_face_ids"]),
        marks=tuple(
            SourceMark(SourceMarkKind(mark["kind"]), SourceEdgeId(mark["target_id"]))
            for mark in data["marks"]
        ),
    )


def _assert_junction_occurrences_share_source_vertex(context) -> None:
    relations = context.relation_snapshot
    topology = context.topology_snapshot
    evidence_by_id = {
        evidence.id: evidence
        for evidence in relations.patch_chain_directional_evidence
    }
    for junction in relations.run_endpoint_junctions:
        assert junction.source_vertex_id is not None
        assert all(
            junction.source_vertex_id in topology.vertices[vertex_id].source_vertex_ids
            for vertex_id in junction.topology_vertex_ids
        )
        for evidence_id, role in junction.incident_run_endpoint_occurrences:
            evidence = evidence_by_id[evidence_id]
            source_vertex_id = (
                evidence.start_source_vertex_id
                if role is PatchChainEndpointRole.START
                else evidence.end_source_vertex_id
            )
            assert source_vertex_id == junction.source_vertex_id


def _direction_matches(actual, expected) -> bool:
    return abs(dot(normalize(actual), normalize(expected))) > 0.99
