"""
Layer: tests

Rules:
- Layer 3 adjacency relation tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

from scaffold_core.ids import ChainId, PatchId, VertexId
from scaffold_core.layer_1_topology.build import build_topology_snapshot
from scaffold_core.layer_2_geometry.build import build_geometry_facts
from scaffold_core.layer_2_geometry.facts import (
    ChainGeometryFacts,
    GeometryFactSnapshot,
    PatchGeometryFacts,
    VertexGeometryFacts,
)
from scaffold_core.layer_3_relations.build import build_relation_snapshot
from scaffold_core.layer_3_relations.model import DihedralKind
from scaffold_core.tests.fixtures.non_manifold import make_three_quad_non_manifold_source
from scaffold_core.tests.fixtures.seam_self import make_seam_self_model
from scaffold_core.tests.fixtures.single_patch import make_single_quad_source
from scaffold_core.tests.fixtures.l_shape import make_two_quad_l_source_with_seam_on_shared_edge


def test_shared_two_patch_chain_builds_patch_adjacency() -> None:
    source = make_two_quad_l_source_with_seam_on_shared_edge()
    topology = build_topology_snapshot(source)
    geometry = build_geometry_facts(source, topology)

    relations = build_relation_snapshot(topology, geometry)

    assert len(relations.patch_adjacencies) == 1
    adjacency = next(iter(relations.patch_adjacencies.values()))
    assert adjacency.chain_id == ChainId("chain:e1")
    assert {adjacency.first_patch_id, adjacency.second_patch_id} == {
        PatchId("patch:seed:f0"),
        PatchId("patch:seed:f1"),
    }
    assert adjacency.shared_length == 1.0
    assert adjacency.signed_angle_radians == 0.0
    assert adjacency.dihedral_kind is DihedralKind.COPLANAR


def test_border_chains_do_not_build_patch_adjacency() -> None:
    source = make_single_quad_source()
    topology = build_topology_snapshot(source)
    geometry = build_geometry_facts(source, topology)

    relations = build_relation_snapshot(topology, geometry)

    assert relations.patch_adjacencies == {}


def test_non_manifold_chain_does_not_build_normal_patch_adjacency() -> None:
    source = make_three_quad_non_manifold_source()
    topology = build_topology_snapshot(source)
    geometry = build_geometry_facts(source, topology)

    relations = build_relation_snapshot(topology, geometry)

    assert relations.patch_adjacencies == {}


def test_seam_self_chain_does_not_build_patch_adjacency() -> None:
    topology = make_seam_self_model()
    geometry = GeometryFactSnapshot(
        patch_facts={
            PatchId("patch:self"): PatchGeometryFacts(
                patch_id=PatchId("patch:self"),
                area=1.0,
                normal=(0.0, 0.0, 1.0),
                centroid=(0.5, 0.5, 0.0),
            )
        },
        chain_facts={
            ChainId("chain:self"): ChainGeometryFacts(
                chain_id=ChainId("chain:self"),
                length=1.0,
                chord_length=1.0,
                chord_direction=(1.0, 0.0, 0.0),
                straightness=1.0,
                detour_ratio=1.0,
            )
        },
        vertex_facts={
            VertexId("vertex:0"): VertexGeometryFacts(
                vertex_id=VertexId("vertex:0"),
                position=(0.0, 0.0, 0.0),
            ),
            VertexId("vertex:1"): VertexGeometryFacts(
                vertex_id=VertexId("vertex:1"),
                position=(1.0, 0.0, 0.0),
            ),
        },
    )

    relations = build_relation_snapshot(topology, geometry)

    assert relations.patch_adjacencies == {}
