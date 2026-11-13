"""
Layer: tests

Rules:
- PatchQuadLadderRelation v0 tests: synthetic quad patches and the bevel
  cases of tests/data/bevel_cases (ground truth from Blender's Face Strength).
- The relation is pure topology: no geometry is read.
- No production logic here.
"""

from __future__ import annotations

import inspect
import json
from collections import Counter
from pathlib import Path

import pytest

from scaffold_core.ids import SourceEdgeId, SourceFaceId, SourceMeshId, SourceVertexId
from scaffold_core.layer_0_source.marks import SourceFaceStrength, SourceMark, SourceMarkKind
from scaffold_core.layer_0_source.snapshot import MeshEdgeRef, MeshFaceRef, MeshVertexRef, SourceMeshSnapshot
from scaffold_core.layer_1_topology.build import build_topology_snapshot
from scaffold_core.layer_2_geometry.build import build_geometry_facts
from scaffold_core.layer_3_relations import quad_ladders
from scaffold_core.layer_3_relations.build import build_relation_snapshot
from scaffold_core.layer_3_relations.quad_ladders import (
    REASON_NOT_ALL_QUADS,
    REASON_NOT_TWO_WAY,
    build_patch_quad_ladder_relations,
    patch_quad_ladder_relations_with_reasons,
)
from scaffold_core.pipeline.inspection import inspect_pipeline_context
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
from scaffold_core.tests.fixtures.cylinder_tube import (
    make_cylinder_tube_without_caps_with_one_seam_source,
    make_segmented_cylinder_tube_without_caps_with_one_seam_source,
)
from scaffold_core.tests.fixtures.quad_ladders import (
    make_five_quad_pole_source,
    make_quad_grid_source,
    make_quad_grid_with_triangle_source,
    make_quad_ring_source,
)

BEVEL_CASES = Path(__file__).with_name("data") / "bevel_cases"
CASE_NAMES = sorted(path.name[: -len(".capture.json")] for path in BEVEL_CASES.glob("*.capture.json"))


def _relations(source):
    return build_patch_quad_ladder_relations(build_topology_snapshot(source), source)


def _only(source):
    relations = _relations(source)
    assert len(relations) == 1
    return relations[0]


def _faces(reading) -> list[str]:
    return [str(face) for column in reading.columns for face in column]


# --------------------------------------------------------------------------- synthetic


def test_quad_grid_has_two_readings_across_and_along() -> None:
    relation = _only(make_quad_grid_source(3, 2))
    assert relation.face_count == 6
    assert relation.closed_column_count == 0
    first, second = relation.readings
    # More columns first: three columns of two faces, then two columns of three.
    assert (len(first.columns), first.faces_per_column) == (3, 2)
    assert (len(second.columns), second.faces_per_column) == (2, 3)
    for reading in relation.readings:
        assert not reading.is_closed
        assert sorted(_faces(reading)) == sorted(f"f{i}" for i in range(6))
        assert len(reading.rail_a_source_edge_ids) == len(reading.columns)
        assert len(reading.rail_b_source_edge_ids) == len(reading.columns)
        assert len(reading.profile_vertex_ids) == len(reading.columns) + 1
        assert reading.end_a_source_edge_ids == reading.profile_edge_ids[0]
        assert reading.end_b_source_edge_ids == reading.profile_edge_ids[-1]
        assert all(len(line) == reading.faces_per_column + 1 for line in reading.profile_vertex_ids)
        # One patch, one loop, one chain: the single use lies on every side.
        assert len(reading.shared_patch_chain_ids) == 1
    assert [tuple(map(str, column)) for column in first.columns] == [("f0", "f3"), ("f1", "f4"), ("f2", "f5")]
    assert [tuple(map(str, column)) for column in second.columns] == [("f0", "f1", "f2"), ("f3", "f4", "f5")]


def test_rail_vertices_correspond_through_the_profile_lines() -> None:
    source = make_quad_grid_source(3, 2)
    reading = _only(source).readings[0]
    ends = {edge_id: set(edge.vertex_ids) for edge_id, edge in source.edges.items()}
    for index, edge_id in enumerate(reading.rail_a_source_edge_ids):
        assert ends[edge_id] == {reading.profile_vertex_ids[index][0], reading.profile_vertex_ids[index + 1][0]}
    for index, edge_id in enumerate(reading.rail_b_source_edge_ids):
        assert ends[edge_id] == {reading.profile_vertex_ids[index][-1], reading.profile_vertex_ids[index + 1][-1]}
    for vertices, edges in zip(reading.profile_vertex_ids, reading.profile_edge_ids):
        for k, edge_id in enumerate(edges):
            assert ends[edge_id] == {vertices[k], vertices[k + 1]}


def test_single_quad_reads_both_ways_with_one_column_each() -> None:
    relation = _only(make_quad_grid_source(1, 1))
    assert len(relation.readings) == 2
    first, second = relation.readings
    assert first.columns == second.columns == ((SourceFaceId("f0"),),)
    assert set(first.rail_a_source_edge_ids + first.rail_b_source_edge_ids) == set(
        second.end_a_source_edge_ids + second.end_b_source_edge_ids
    )


def test_ring_is_one_closed_reading_and_its_along_rings_are_closed_columns() -> None:
    relation = _only(make_quad_ring_source(8, 2))
    assert relation.closed_column_count == 2
    (reading,) = relation.readings
    assert reading.is_closed
    assert (len(reading.columns), reading.faces_per_column) == (8, 2)
    assert reading.end_a_source_edge_ids == reading.end_b_source_edge_ids == ()
    assert len(reading.profile_vertex_ids) == 8
    rail_a_vertices = frozenset(line[0] for line in reading.profile_vertex_ids)
    rail_b_vertices = frozenset(line[-1] for line in reading.profile_vertex_ids)
    assert {rail_a_vertices, rail_b_vertices} == {
        frozenset(SourceVertexId(f"v{i}_0") for i in range(8)),
        frozenset(SourceVertexId(f"v{i}_2") for i in range(8)),
    }
    # Inner and outer circles are two loops: rails on two different uses.
    assert set(reading.rail_a_patch_chain_ids).isdisjoint(reading.rail_b_patch_chain_ids)


def test_a_patch_with_a_triangle_has_no_reading() -> None:
    source = make_quad_grid_with_triangle_source()
    relations, reasons = patch_quad_ladder_relations_with_reasons(build_topology_snapshot(source), source)
    assert relations == ()
    assert list(reasons.values()) == [(REASON_NOT_ALL_QUADS,)]


def test_a_five_quad_pole_has_no_reading() -> None:
    source = make_five_quad_pole_source()
    relations, reasons = patch_quad_ladder_relations_with_reasons(build_topology_snapshot(source), source)
    assert relations == ()
    assert list(reasons.values()) == [(REASON_NOT_TWO_WAY,)]


@pytest.mark.parametrize(
    "factory, rows",
    (
        (make_cylinder_tube_without_caps_with_one_seam_source, 1),
        (make_segmented_cylinder_tube_without_caps_with_one_seam_source, 2),
    ),
)
def test_seam_self_band_is_open_with_its_ends_on_the_two_sides_of_the_seam(factory, rows) -> None:
    source = factory()
    topology = build_topology_snapshot(source)
    relation = _only(source)
    seam_edges = {mark.target_id for mark in source.marks}
    seam_uses = {
        use.id
        for use in topology.patch_chains.values()
        if set(topology.chains[use.chain_id].source_edge_ids) <= seam_edges
    }
    assert len(seam_uses) == 2
    across = [reading for reading in relation.readings if reading.faces_per_column == rows]
    assert len(across) == 1
    reading = across[0]
    assert not reading.is_closed
    assert len(reading.columns) == 4
    assert set(reading.end_a_source_edge_ids) == set(reading.end_b_source_edge_ids) == seam_edges
    assert len(reading.end_a_patch_chain_ids) == len(reading.end_b_patch_chain_ids) == 1
    assert {reading.end_a_patch_chain_ids[0], reading.end_b_patch_chain_ids[0]} == seam_uses
    # Read along the band, each column runs from one side of the seam to the other.
    along = [reading for reading in relation.readings if reading.faces_per_column == 4]
    assert len(along) == 1 and len(along[0].columns) == rows
    assert set(along[0].rail_a_patch_chain_ids) | set(along[0].rail_b_patch_chain_ids) == seam_uses


def test_no_geometry_is_read() -> None:
    source = make_quad_grid_source(3, 2)
    moved = SourceMeshSnapshot(
        id=source.id,
        vertices={key: MeshVertexRef(key, (0.0, 0.0, 0.0)) for key in source.vertices},
        edges=source.edges,
        faces=source.faces,
        selected_face_ids=source.selected_face_ids,
    )
    assert _relations(moved) == _relations(source)
    text = inspect.getsource(quad_ladders)
    for word in (".position", "length(", "normal", "angle", "geometry", "layer_2", "layer_4", "layer_5"):
        assert word not in text.split('"""', 2)[2]


def test_relation_snapshot_and_pass_1_carry_the_records() -> None:
    source = make_quad_grid_source(3, 2)
    topology = build_topology_snapshot(source)
    geometry = build_geometry_facts(source, topology)
    assert build_relation_snapshot(topology, geometry).patch_quad_ladder_relations == ()
    assert build_relation_snapshot(topology, geometry, source).patch_quad_ladder_relations == _relations(source)
    context = run_pass_1_relations(run_pass_0(source))
    assert context.relation_snapshot.patch_quad_ladder_relations == _relations(source)
    summary = inspect_pipeline_context(context)["relations"]
    assert summary["patch_quad_ladder_relation_count"] == 1
    assert summary["patch_quad_ladder_two_reading_count"] == 1
    assert summary["patch_quad_ladder_closed_count"] == 0
    assert summary["patch_quad_ladder_patches_not_all_quads"] == 0
    assert summary["patch_quad_ladder_quad_patches_without_reading"] == 0


# --------------------------------------------------------------------------- bevel cases


def _load(name: str):
    data = json.loads((BEVEL_CASES / f"{name}.capture.json").read_text(encoding="utf-8"))
    strength = data.get("face_strength", {})
    source = SourceMeshSnapshot(
        id=SourceMeshId(data["id"]),
        vertices={SourceVertexId(k): MeshVertexRef(SourceVertexId(k), tuple(v)) for k, v in data["vertices"].items()},
        edges={
            SourceEdgeId(k): MeshEdgeRef(SourceEdgeId(k), (SourceVertexId(v[0]), SourceVertexId(v[1])))
            for k, v in data["edges"].items()
        },
        faces={
            SourceFaceId(k): MeshFaceRef(
                SourceFaceId(k),
                tuple(SourceVertexId(v) for v in f["vertex_ids"]),
                tuple(SourceEdgeId(e) for e in f["edge_ids"]),
                SourceFaceStrength(strength[k]) if k in strength else None,
            )
            for k, f in data["faces"].items()
        },
        selected_face_ids=tuple(SourceFaceId(f) for f in data["selected_face_ids"]),
        marks=tuple(
            SourceMark(kind=SourceMarkKind(m["kind"]), target_id=SourceEdgeId(m["target_id"])) for m in data["marks"]
        ),
    )
    truth = json.loads((BEVEL_CASES / f"{name}.gt.json").read_text(encoding="utf-8"))
    return source, truth


_CACHE: dict[str, tuple] = {}


def _case(name: str):
    if name not in _CACHE:
        source, truth = _load(name)
        topology = build_topology_snapshot(source)
        relations, reasons = patch_quad_ladder_relations_with_reasons(topology, source)
        kind = {}
        for patch_id, patch in topology.patches.items():
            classes = {truth["faces"][str(face)][0] for face in patch.source_face_ids}
            assert len(classes) == 1  # seams follow the ground truth: no mixed patch
            kind[patch_id] = classes.pop()
        _CACHE[name] = (source, truth, topology, {r.patch_id: r for r in relations}, reasons, kind)
    return _CACHE[name]


def test_the_bevel_cases_are_present() -> None:
    assert len(CASE_NAMES) == 12


@pytest.mark.parametrize("name", CASE_NAMES)
def test_face_strength_mark_is_the_ground_truth_class(name) -> None:
    source, truth, *_ = _case(name)
    expected = {"STRIP": SourceFaceStrength.MEDIUM, "JUNCTION": SourceFaceStrength.WEAK, "OTHER": SourceFaceStrength.STRONG}
    for face_id, face in source.faces.items():
        assert face.face_strength is expected[truth["faces"][str(face_id)][0]]


@pytest.mark.parametrize("name", [name for name in CASE_NAMES if name != "h_rect_s2_tri"])
def test_every_strip_patch_reads_as_a_ladder_between_its_main_surfaces(name) -> None:
    _source, truth, topology, by_patch, _reasons, kind = _case(name)
    patches_of_chain: dict = {}
    for use in topology.patch_chains.values():
        patches_of_chain.setdefault(use.chain_id, set()).add(use.patch_id)

    def neighbours(patch_id, use_ids):
        out = set()
        for use_id in use_ids:
            others = patches_of_chain[topology.patch_chains[use_id].chain_id] - {patch_id}
            out |= {kind[other] for other in others} or {"BORDER_OR_SELF"}
        return out

    strips = [patch_id for patch_id, value in kind.items() if value == "STRIP"]
    assert strips
    closed_runs = []
    for patch_id in strips:
        relation = by_patch.get(patch_id)
        assert relation is not None, patch_id
        matching = [
            reading
            for reading in relation.readings
            if neighbours(patch_id, reading.rail_a_patch_chain_ids) == {"OTHER"}
            and neighbours(patch_id, reading.rail_b_patch_chain_ids) == {"OTHER"}
            and neighbours(patch_id, reading.end_a_patch_chain_ids + reading.end_b_patch_chain_ids)
            <= {"STRIP", "JUNCTION", "BORDER_OR_SELF"}
            and not reading.shared_patch_chain_ids
        ]
        assert len(matching) == 1, patch_id
        reading = matching[0]
        assert reading.faces_per_column == truth["segments"]
        # One column per bevelled source edge of the strip run.
        bevelled_edges = {truth["faces"][str(face)][2] for column in reading.columns for face in column}
        assert len(reading.columns) == len(bevelled_edges)
        # A closed strip run (a ring around a hole) is an annulus: two loops, no ends.
        assert reading.is_closed == (len(topology.patches[patch_id].loop_ids) == 2)
        closed_runs.append(reading.is_closed)
    assert sum(closed_runs) == {"b_ring_s1": 1, "d_cyl_s2": 1}.get(name, 0)


@pytest.mark.parametrize("name", CASE_NAMES)
def test_junction_patches_have_no_reading(name) -> None:
    _source, _truth, _topology, by_patch, reasons, kind = _case(name)
    for patch_id, value in kind.items():
        if value == "JUNCTION":
            assert patch_id not in by_patch
            assert reasons[patch_id] in ((REASON_NOT_ALL_QUADS,), (REASON_NOT_TWO_WAY,))


def test_quad_junction_patches_at_arc_miters_are_poles_without_reading() -> None:
    source, _truth, topology, _by_patch, reasons, kind = _case("f_rect_inarc")
    quad_junctions = [
        patch_id
        for patch_id, value in kind.items()
        if value == "JUNCTION" and all(len(source.faces[f].vertex_ids) == 4 for f in topology.patches[patch_id].source_face_ids)
    ]
    assert len(quad_junctions) == 4
    assert all(reasons[patch_id] == (REASON_NOT_TWO_WAY,) for patch_id in quad_junctions)


def test_triangulated_strips_have_no_reading() -> None:
    _source, _truth, _topology, by_patch, reasons, kind = _case("h_rect_s2_tri")
    assert by_patch == {}
    assert Counter(kind.values())["STRIP"] == 4
    assert set(reasons.values()) == {(REASON_NOT_ALL_QUADS,)}


def test_twenty_percent_noise_gives_the_same_relation_as_the_clean_arch() -> None:
    clean = _case("c_arch_s2")
    noisy = _case("e_arch_s2_n20")
    assert set(clean[0].faces) == set(noisy[0].faces)
    assert noisy[3] == clean[3]
    assert noisy[4] == clean[4]


def test_closed_rim_ring_and_quad_grids_on_the_tube() -> None:
    _source, _truth, _topology, by_patch, _reasons, kind = _case("d_cyl_s2")
    strips = {patch_id for patch_id, value in kind.items() if value == "STRIP"}
    closed = {patch_id for patch_id, relation in by_patch.items() if any(r.is_closed for r in relation.readings)}
    assert len(strips & closed) == 1  # the top rim ring; the hole rim is cut into four strips
