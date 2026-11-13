"""
Layer: tests

Rules:
- Layer 4 bevel strip and bevel junction tests: the bevel cases of
  tests/data/bevel_cases with their Face Strength marks (Rule A) and with
  the marks stripped (Rule B), the non-bevel captures, synthetic rule edges.
- The rule reads marks, incidence, ladders and PatchAdjacency only; nothing
  in Layer 5 reads the records.
- No production logic here.
"""

from __future__ import annotations

import inspect
import json
import random
import re
from dataclasses import replace
from pathlib import Path

import pytest

from dev.tools.scaffold_graph_debug.snapshot_io import load_source_snapshot
from scaffold_core.layer_4_features import bevels as feature_bevels
from scaffold_core.layer_4_features import build as feature_build
from scaffold_core.layer_4_features.model import (
    BevelCornerKind,
    BevelEvidenceSource,
    BevelStripEnd,
    FeatureConstraintKind,
    FeatureInstanceStatus,
    FeatureKind,
    FeatureOptions,
    FeatureSuppressionReason,
)
from scaffold_core.layer_5_runtime.pins import run_skeleton_solve
from scaffold_core.pipeline.inspection import inspect_pipeline_context
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations, run_pass_2_features
from scaffold_core.ids import SourceEdgeId, SourceFaceId, SourceVertexId
from scaffold_core.layer_0_source.snapshot import MeshEdgeRef, MeshFaceRef, MeshVertexRef
from scaffold_core.tests.fixtures.bevel_patches import (
    MEDIUM,
    WEAK,
    make_capped_prism_source,
    make_corner_bevel_source,
    make_open_slab_source,
    make_quad_between_two_surfaces_source,
    make_quad_pointed_both_ways_source,
    make_quad_with_bevel_faces_on_both_readings_rails_source,
    make_quad_with_triangles_source,
    make_single_quad_source,
    make_tube_with_one_quad_column_source,
)

DATA = Path(__file__).with_name("data")
BEVEL_CASES = DATA / "bevel_cases"
CASE_NAMES = sorted(path.name[: -len(".capture.json")] for path in BEVEL_CASES.glob("*.capture.json"))

# Strips whose direction stays unresolved with the marks on, and why.
USER_MESH_SEGMENTS = 1  # the user's mesh has no segments entry; its bevel is one segment
UNRESOLVED_BY_MARK = {"h_rect_s2_tri": 4}  # triangulated bevel: no quad ladder relation
# Without marks, the structural rule finds these cases exactly ...
EXACT_BY_STRUCTURE = ("a_cube_s1", "a_cube_s3", "g_short", "u_rounded_wall_noise_top")
# ... and nothing on the others (known limit, accepted): a window rim whose
# strips meet at a miter without junction faces, a closed rim ring, an arch,
# a tube rim, a strip that runs to the mesh border, junctions that also touch
# the main surfaces (inner arc miter) and triangulated bevels give no
# junction, so only the mark finds them.
NOTHING_BY_STRUCTURE = tuple(name for name in CASE_NAMES if name not in EXACT_BY_STRUCTURE)


def _run(source):
    return run_pass_2_features(run_pass_1_relations(run_pass_0(source)))


def _case(name: str, *, marks: bool = True):
    source = load_source_snapshot(BEVEL_CASES / f"{name}.capture.json")
    if not marks:
        source = replace(source, faces={key: replace(face, face_strength=None) for key, face in source.faces.items()})
    truth = json.loads((BEVEL_CASES / f"{name}.gt.json").read_text(encoding="utf-8"))
    return _run(source), truth


def _truth_by_patch(context, truth) -> dict[str, str]:
    out = {}
    for patch_id, patch in context.topology_snapshot.patches.items():
        classes = {truth["faces"][str(face_id)][0] for face_id in patch.source_face_ids}
        assert len(classes) == 1  # the generator cut one patch per strip run and junction
        out[str(patch_id)] = classes.pop()
    return out


def _accepted(context, kind: FeatureKind) -> dict[str, object]:
    return {
        str(record.patch_id): record
        for record in context.feature_snapshot.bevels
        if record.kind is kind and record.status is FeatureInstanceStatus.ACCEPTED
    }


def _faces_across(context, face_id, edge_id):
    faces = [
        other
        for patch in context.topology_snapshot.patches.values()
        for other in patch.source_face_ids
        if other != face_id and edge_id in context.source_snapshot.faces[other].edge_ids
    ]
    return faces


def test_the_bevel_cases_are_present() -> None:
    assert len(CASE_NAMES) == 13
    assert set(EXACT_BY_STRUCTURE) <= set(CASE_NAMES)


# --------------------------------------------------------------------------- Rule A: by mark


@pytest.mark.parametrize("name", CASE_NAMES)
def test_by_mark_strips_and_junctions_are_the_ground_truth_patches(name) -> None:
    context, truth = _case(name)
    by_patch = _truth_by_patch(context, truth)
    strips = _accepted(context, FeatureKind.BEVEL_STRIP)
    junctions = _accepted(context, FeatureKind.BEVEL_JUNCTION)
    assert set(strips) == {patch for patch, kind in by_patch.items() if kind == "STRIP"}
    assert set(junctions) == {patch for patch, kind in by_patch.items() if kind == "JUNCTION"}
    assert len(context.feature_snapshot.bevels) == len(strips) + len(junctions)  # nothing suppressed
    assert all(record.source is BevelEvidenceSource.SOURCE_MARK for record in context.feature_snapshot.bevels)
    unresolved = [record for record in strips.values() if record.reading_index is None]
    assert len(unresolved) == UNRESOLVED_BY_MARK.get(name, 0)
    diagnostics = [d for d in context.feature_snapshot.diagnostics if d.code == feature_bevels.BEVEL_UNRESOLVED_CODE]
    assert sorted(d.entity_ids[0] for d in diagnostics) == sorted(str(record.patch_id) for record in unresolved)
    if name in UNRESOLVED_BY_MARK:
        assert {d.evidence["reason"] for d in diagnostics} == {feature_bevels.UNRESOLVED_NO_LADDER}
        assert not any(
            record.patch_id == relation.patch_id
            for record in unresolved
            for relation in context.relation_snapshot.patch_quad_ladder_relations
        )


@pytest.mark.parametrize("name", CASE_NAMES)
def test_by_mark_the_chosen_reading_runs_across_the_bevel(name) -> None:
    context, truth = _case(name)
    by_patch = _truth_by_patch(context, truth)
    ladders = {str(relation.patch_id): relation for relation in context.relation_snapshot.patch_quad_ladder_relations}
    for patch_id, record in _accepted(context, FeatureKind.BEVEL_STRIP).items():
        if record.reading_index is None:
            continue
        reading = ladders[patch_id].readings[record.reading_index]
        assert record.faces_per_column == reading.faces_per_column == truth.get("segments", USER_MESH_SEGMENTS)
        assert record.column_count == len(reading.columns)
        assert record.is_closed == reading.is_closed
        assert (record.rail_a_patch_chain_ids, record.rail_b_patch_chain_ids) == (
            reading.rail_a_patch_chain_ids, reading.rail_b_patch_chain_ids
        )
        assert (record.end_a_patch_chain_ids, record.end_b_patch_chain_ids) == (
            reading.end_a_patch_chain_ids, reading.end_b_patch_chain_ids
        )
        # Rails border only main surfaces, on both sides.
        assert record.rail_a_neighbour_patch_ids and record.rail_b_neighbour_patch_ids
        for neighbour in record.rail_a_neighbour_patch_ids + record.rail_b_neighbour_patch_ids:
            assert by_patch[str(neighbour)] == "OTHER"
        # Ends border bevel faces, the mesh border or the strip itself.
        for faces, edges in (
            (reading.columns[0], reading.end_a_source_edge_ids),
            (reading.columns[-1], reading.end_b_source_edge_ids),
        ):
            for face_id, edge_id in zip(faces, edges):
                for other in _faces_across(context, face_id, edge_id):
                    assert truth["faces"][str(other)][0] in ("STRIP", "JUNCTION")


def test_by_mark_junctions_list_the_strips_they_join_with_their_ends() -> None:
    context, _truth = _case("a_cube_s1")
    strips = _accepted(context, FeatureKind.BEVEL_STRIP)
    for junction in _accepted(context, FeatureKind.BEVEL_JUNCTION).values():
        assert len(junction.joined_strips) == 3  # a cube corner joins three edge strips
        assert {str(contact.strip_patch_id) for contact in junction.joined_strips} <= set(strips)
        assert all(contact.strip_end in (BevelStripEnd.A, BevelStripEnd.B) for contact in junction.joined_strips)
        assert junction.other_neighbour_patch_ids == ()
        assert not junction.touches_mesh_border
    # Every strip end meets exactly one junction.
    ends = [
        (str(contact.strip_patch_id), contact.strip_end)
        for junction in _accepted(context, FeatureKind.BEVEL_JUNCTION).values()
        for contact in junction.joined_strips
    ]
    assert sorted(ends) == sorted((patch_id, end) for patch_id in strips for end in (BevelStripEnd.A, BevelStripEnd.B))


def test_by_mark_the_users_mesh_junctions_join_strips_at_their_ends() -> None:
    context, _truth = _case("u_rounded_wall_noise_top")
    strips = _accepted(context, FeatureKind.BEVEL_STRIP)
    junctions = _accepted(context, FeatureKind.BEVEL_JUNCTION)
    assert (len(strips), len(junctions)) == (9, 6)
    for junction in junctions.values():
        assert junction.joined_strips
        for contact in junction.joined_strips:
            assert str(contact.strip_patch_id) in strips
            assert contact.strip_end in (BevelStripEnd.A, BevelStripEnd.B)


# --------------------------------------------------------------------------- Rule B: by structure


@pytest.mark.parametrize("name", EXACT_BY_STRUCTURE)
def test_by_structure_finds_the_cubes_the_short_prism_and_the_users_mesh_exactly(name) -> None:
    context, truth = _case(name, marks=False)
    marked, _truth = _case(name)
    by_patch = _truth_by_patch(context, truth)
    strips = _accepted(context, FeatureKind.BEVEL_STRIP)
    junctions = _accepted(context, FeatureKind.BEVEL_JUNCTION)
    assert set(strips) == {patch for patch, kind in by_patch.items() if kind == "STRIP"}
    assert set(junctions) == {patch for patch, kind in by_patch.items() if kind == "JUNCTION"}
    assert all(record.source is BevelEvidenceSource.STRUCTURE for record in context.feature_snapshot.bevels)
    assert context.feature_snapshot.diagnostics == ()
    # The structural reading is the one the marks choose.
    by_mark = _accepted(marked, FeatureKind.BEVEL_STRIP)
    for patch_id, record in strips.items():
        assert record.reading_index is not None
        assert record.reading_index == by_mark[patch_id].reading_index
        assert record.faces_per_column == by_mark[patch_id].faces_per_column
        assert replace(record, source=BevelEvidenceSource.SOURCE_MARK) == by_mark[patch_id]


@pytest.mark.parametrize("name", NOTHING_BY_STRUCTURE)
def test_by_structure_finds_nothing_without_a_junction_known_limit(name) -> None:
    context, _truth = _case(name, marks=False)
    assert context.feature_snapshot.bevels == ()


@pytest.mark.parametrize("name", CASE_NAMES)
def test_by_structure_never_calls_a_main_surface_or_reveal_a_bevel(name) -> None:
    context, truth = _case(name, marks=False)
    by_patch = _truth_by_patch(context, truth)
    for record in context.feature_snapshot.bevels:
        expected = "STRIP" if record.kind is FeatureKind.BEVEL_STRIP else "JUNCTION"
        assert by_patch[str(record.patch_id)] == expected


# The non-bevel captures give no bevel record by structure. Before the
# conditions "strips between non-strips" and "junctions join a strip" a tube
# cut into one-column wall pieces between n-gon caps (artist_cyl_multiseam)
# read as six strips and two junctions, and the caps of artist_cyl32 and the
# end patches of artist_cross_band as strip-less junctions.
@pytest.mark.parametrize("path", sorted(DATA.glob("*.json")), ids=lambda path: path.stem)
def test_by_structure_on_the_non_bevel_captures_finds_nothing(path) -> None:
    context = _run(load_source_snapshot(path))
    assert context.feature_snapshot.bevels == ()


# --------------------------------------------------------------------------- corner kind


def test_rule_b_reads_a_marked_ladder_patch_as_a_ladder() -> None:
    """Rule B decides only unmarked patches; a marked ladder patch takes part in its state as a ladder."""

    unmarked, _truth = _case("a_cube_s1", marks=False)
    kept = "patch:seed:f10"  # one bevel strip keeps its mark, every other face is unmarked
    source = load_source_snapshot(BEVEL_CASES / "a_cube_s1.capture.json")
    marked_faces = set(unmarked.topology_snapshot.patches[kept].source_face_ids)
    source = replace(source, faces={
        key: face if key in marked_faces else replace(face, face_strength=None) for key, face in source.faces.items()
    })
    context = _run(source)
    records = {str(r.patch_id): r for r in context.feature_snapshot.bevels}
    before = {str(r.patch_id): r for r in unmarked.feature_snapshot.bevels}
    assert set(records) == set(before)
    # Every unmarked patch, the junctions at both ends of the marked strip
    # included, is decided by structure exactly as on the fully unmarked mesh:
    # Rule B reads the marked strip as a decided ladder. Only a junction's
    # contact with the marked strip names no strip end (see below).
    def without_end_on_kept(record):
        return replace(record, joined_strips=tuple(
            replace(c, strip_end=None) if str(c.strip_patch_id) == kept else c for c in record.joined_strips
        ))

    touching = 0
    for patch_id, record in records.items():
        if patch_id != kept:
            assert record == without_end_on_kept(before[patch_id]), patch_id
            touching += any(str(c.strip_patch_id) == kept for c in record.joined_strips)
    assert touching == 2  # the junctions at its two ends
    junctions = {p for p, r in records.items() if r.kind is FeatureKind.BEVEL_JUNCTION}
    assert len(junctions) == 8 and all(records[p].source is BevelEvidenceSource.STRUCTURE for p in junctions)
    # The marked strip is Rule A's: a strip by mark. Its ends lie on unmarked
    # patches, so the mark picks no reading (no ladder constraint for it).
    strip = records[kept]
    assert strip.kind is FeatureKind.BEVEL_STRIP and strip.status is FeatureInstanceStatus.ACCEPTED
    assert strip.source is BevelEvidenceSource.SOURCE_MARK and strip.reading_index is None
    assert before[kept].source is BevelEvidenceSource.STRUCTURE and before[kept].reading_index is not None


@pytest.mark.parametrize("name", ("a_cube_s1", "a_cube_s3", "g_short", "u_rounded_wall_noise_top"))
def test_corner_kind_of_cube_prism_and_user_strips(name) -> None:
    context, _truth = _case(name)
    kinds = sorted(record.corner_kind.value for record in _accepted(context, FeatureKind.BEVEL_STRIP).values())
    if name == "g_short":
        # The one-quad strip on the very short side: its two rail seams' patch
        # dihedrals disagree (Layer 3 PatchAdjacency).
        assert kinds.count("MIXED") == 1 and kinds.count("CONVEX") == len(kinds) - 1
    else:
        assert set(kinds) == {"CONVEX"}


def test_corner_kind_comes_from_the_rail_seams_dihedral_convex_and_concave() -> None:
    for concave, expected in ((False, BevelCornerKind.CONVEX), (True, BevelCornerKind.CONCAVE)):
        context = _run(make_corner_bevel_source(concave=concave))
        (record,) = context.feature_snapshot.bevels
        assert record.kind is FeatureKind.BEVEL_STRIP and record.status is FeatureInstanceStatus.ACCEPTED
        assert record.reading_index is not None and record.faces_per_column == 1
        assert {record.rail_a_neighbour_patch_ids, record.rail_b_neighbour_patch_ids} == {
            ("patch:seed:f0",), ("patch:seed:f2",)
        }
        assert record.corner_kind is expected
        assert {a.dihedral_kind.value for a in context.relation_snapshot.patch_adjacencies.values()} == {expected.value}


def test_corner_kind_on_a_tube_rim_reads_the_patch_level_dihedral() -> None:
    # A rim strip between the flat top and a curved wall: PatchAdjacency
    # compares mean patch normals, so it can be MIXED or UNDEFINED there.
    context, _truth = _case("d_cyl_s2")
    kinds = sorted(record.corner_kind.value for record in _accepted(context, FeatureKind.BEVEL_STRIP).values())
    assert kinds == ["MIXED", "MIXED", "MIXED", "MIXED", "UNDEFINED"]


# --------------------------------------------------------------------------- synthetic rule edges


def test_bevel_faces_not_isolated_by_seams_are_suppressed() -> None:
    context = _run(make_corner_bevel_source(seams=False))
    (record,) = context.feature_snapshot.bevels
    assert record.kind is FeatureKind.BEVEL_STRIP
    assert record.status is FeatureInstanceStatus.SUPPRESSED
    assert record.suppression_reason is FeatureSuppressionReason.BEVEL_NOT_ISOLATED
    assert record.reading_index is None


def test_strip_and_junction_faces_in_one_patch_are_suppressed() -> None:
    context = _run(make_corner_bevel_source(rows=2, strip_strengths=(MEDIUM, WEAK)))
    (record,) = context.feature_snapshot.bevels
    assert record.status is FeatureInstanceStatus.SUPPRESSED
    assert record.suppression_reason is FeatureSuppressionReason.BEVEL_STRIP_AND_JUNCTION_FACES


def test_all_weak_faces_make_a_junction_by_mark() -> None:
    context = _run(make_corner_bevel_source(rows=2, strip_strengths=(WEAK, WEAK)))
    (record,) = context.feature_snapshot.bevels
    assert record.kind is FeatureKind.BEVEL_JUNCTION and record.status is FeatureInstanceStatus.ACCEPTED
    assert record.joined_strips == ()
    assert sorted(record.other_neighbour_patch_ids) == ["patch:seed:f0", "patch:seed:f2"]
    assert record.touches_mesh_border


def test_strong_marks_are_authoritative_and_stop_the_structural_rule() -> None:
    # The quad between two surfaces with a pure junction is a strip by structure,
    # but not once every face carries the STRONG mark.
    source = make_quad_between_two_surfaces_source(junction_touches_surface=False)
    assert _accepted(_run(source), FeatureKind.BEVEL_STRIP)
    strong = replace(source, faces={k: replace(f, face_strength=feature_bevels.SourceFaceStrength.STRONG)
                                    for k, f in source.faces.items()})
    assert _run(strong).feature_snapshot.bevels == ()


def test_a_marked_quad_with_bevel_faces_across_the_rails_of_both_readings_fits_none() -> None:
    # Each reading of q has its ends on bevel faces or the border, but a
    # bevel face across a rail: only the rail clause rejects them.
    context = _run(make_quad_with_bevel_faces_on_both_readings_rails_source())
    record = _accepted(context, FeatureKind.BEVEL_STRIP)["patch:seed:f0"]
    assert record.reading_index is None
    (diagnostic,) = [
        d for d in context.feature_snapshot.diagnostics
        if d.entity_ids == ("patch:seed:f0",) and d.code == feature_bevels.BEVEL_UNRESOLVED_CODE
    ]
    assert diagnostic.evidence["reason"] == feature_bevels.UNRESOLVED_NO_READING_FITS_MARKS
    # A junction across an end of an unresolved strip: the contact has no end.
    for junction_id in ("patch:seed:f1", "patch:seed:f2"):
        (contact,) = _accepted(context, FeatureKind.BEVEL_JUNCTION)[junction_id].joined_strips
        assert contact.strip_patch_id == "patch:seed:f0" and contact.strip_end is None


def test_a_marked_strip_with_two_fitting_readings_is_accepted_unresolved() -> None:
    context = _run(make_single_quad_source())
    (record,) = context.feature_snapshot.bevels
    assert record.status is FeatureInstanceStatus.ACCEPTED and record.reading_index is None
    diagnostic, not_laid = context.feature_snapshot.diagnostics
    assert diagnostic.entity_ids == ("patch:seed:f0",)
    assert diagnostic.evidence["reason"] == feature_bevels.UNRESOLVED_TWO_READINGS_FIT_MARKS
    # Without a chosen reading the strip is not laid from its ladder.
    assert not_laid.code == feature_bevels.LADDER_NOT_LAID_CODE
    assert not_laid.evidence["reason"] == feature_bevels.NOT_LAID_NO_READING
    assert context.feature_snapshot.constraints == ()


def _fixpoint(context):
    mesh = feature_bevels._BevelMesh(context.topology_snapshot, context.relation_snapshot, context.source_snapshot)
    return mesh, feature_bevels.rule_b_fixpoint(mesh, list(mesh.patch_ids))


@pytest.mark.parametrize("top", (False, True), ids=("F2_border_on_top", "triangle_on_top"))
def test_an_undecided_quad_among_triangles_anchors_nothing(top) -> None:
    # Reviewer case F2: both readings of the quad end on triangles or the
    # border, so it is undecided, and no triangle touches a decided end.
    context = _run(make_quad_with_triangles_source(top=top))
    assert context.feature_snapshot.bevels == ()
    _mesh, (decided, undecided, blocked, junctions) = _fixpoint(context)
    assert (decided, undecided, blocked, junctions) == ({}, {"patch:seed:f0"}, set(), set())


def test_a_quad_whose_junctions_point_to_both_readings_is_blocked() -> None:
    # The bottom and left triangles of q are junctions (anchored by the
    # decided strips D1, D2) and lie on ends of different readings of q.
    context = _run(make_quad_pointed_both_ways_source())
    _mesh, (decided, undecided, blocked, junctions) = _fixpoint(context)
    assert blocked == undecided == {"patch:seed:f0"}
    assert junctions == {"patch:seed:f1", "patch:seed:f4"}
    assert sorted(_accepted(context, FeatureKind.BEVEL_STRIP)) == ["patch:seed:f5", "patch:seed:f8"]
    assert sorted(_accepted(context, FeatureKind.BEVEL_JUNCTION)) == ["patch:seed:f1", "patch:seed:f4"]
    assert "patch:seed:f0" not in decided


def test_a_non_manifold_end_edge_is_not_end_strict() -> None:
    assert _accepted(_run(make_quad_between_two_surfaces_source(junction_touches_surface=False)), FeatureKind.BEVEL_STRIP)
    finned = _run(make_quad_between_two_surfaces_source(junction_touches_surface=False, fins_on_top=True))
    assert finned.feature_snapshot.bevels == ()


def test_a_junction_next_to_decided_ladders_that_fail_the_rail_test_gets_no_record() -> None:
    # The quad column q and the wall W of a capped tube are both decided
    # (ends on the cap and the border) and the cap is a junction of both,
    # but q has W on both rails and W has q: no strip, so the cap joins none.
    context = _run(make_tube_with_one_quad_column_source())
    assert context.feature_snapshot.bevels == ()
    _mesh, (decided, _undecided, _blocked, junctions) = _fixpoint(context)
    assert set(decided) == {"patch:seed:f0", "patch:seed:f5"}
    assert junctions == {"patch:seed:f6"}


def test_a_slab_with_an_open_bottom_is_a_known_false_positive() -> None:
    # Reviewer case F3: outer, inner and top quads with two 5-gon end caps
    # have the topology of a one-segment bevel (top) between two surfaces
    # (outer, inner) with its junctions (the caps). Documented, not tuned.
    context = _run(make_open_slab_source())
    strips = _accepted(context, FeatureKind.BEVEL_STRIP)
    junctions = _accepted(context, FeatureKind.BEVEL_JUNCTION)
    assert list(strips) == ["patch:seed:f2"]
    assert sorted(junctions) == ["patch:seed:f3", "patch:seed:f4"]
    assert {strips["patch:seed:f2"].rail_a_neighbour_patch_ids, strips["patch:seed:f2"].rail_b_neighbour_patch_ids} == {
        ("patch:seed:f0",), ("patch:seed:f1",)
    }
    for junction in junctions.values():
        (contact,) = junction.joined_strips
        assert contact.strip_end is not None and junction.touches_mesh_border


@pytest.mark.parametrize("name", ("a_cube_s1", "a_cube_s3", "g_short"))
def test_main_quads_split_into_triangles_make_no_junction_by_structure(name) -> None:
    # Reviewer case F1: with each main quad split into two triangles in its
    # patch, every strip has two end-strict readings (undecided) and
    # no main surface may become a junction. Nothing is found.
    context = _run(_with_triangulated_main_faces(name))
    assert context.feature_snapshot.bevels == ()
    _mesh, (decided, undecided, _blocked, junctions) = _fixpoint(context)
    assert junctions == set() and decided == {}
    assert len(undecided) == 12 if name != "g_short" else len(undecided) == 15  # every strip


def _with_triangulated_main_faces(name: str):
    source = load_source_snapshot(BEVEL_CASES / f"{name}.capture.json")
    truth = json.loads((BEVEL_CASES / f"{name}.gt.json").read_text(encoding="utf-8"))
    faces, edges, selected = {}, dict(source.edges), []
    for face_id, face in source.faces.items():
        if truth["faces"][str(face_id)][0] != "OTHER" or len(face.vertex_ids) != 4:
            faces[face_id] = replace(face, face_strength=None)
            selected.append(face_id)
            continue
        v, e = face.vertex_ids, face.edge_ids
        diagonal = SourceEdgeId(f"diag_{face_id}")
        edges[diagonal] = MeshEdgeRef(diagonal, (v[0], v[2]))
        first, second = SourceFaceId(f"{face_id}a"), SourceFaceId(f"{face_id}b")
        faces[first] = MeshFaceRef(first, (v[0], v[1], v[2]), (e[0], e[1], diagonal))
        faces[second] = MeshFaceRef(second, (v[0], v[2], v[3]), (diagonal, e[2], e[3]))
        selected.extend((first, second))
    return replace(source, edges=edges, faces=faces, selected_face_ids=tuple(selected))


def _permuted(source, seed: int):
    """The same mesh under shuffled vertex, edge and face ids and order; returns it and new face id -> old."""

    rng = random.Random(seed)

    def renames(keys, prefix):
        order = list(keys)
        rng.shuffle(order)
        return {old: f"{prefix}{index}" for index, old in enumerate(order)}

    vertex_ids = renames(source.vertices, "pv")
    edge_ids = renames(source.edges, "pe")
    face_ids = renames(source.faces, "pf")
    vertices = {SourceVertexId(vertex_ids[k]): MeshVertexRef(SourceVertexId(vertex_ids[k]), v.position) for k, v in source.vertices.items()}
    edges = {
        SourceEdgeId(edge_ids[k]): MeshEdgeRef(SourceEdgeId(edge_ids[k]), tuple(SourceVertexId(vertex_ids[x]) for x in e.vertex_ids))
        for k, e in source.edges.items()
    }
    faces = {
        SourceFaceId(face_ids[k]): MeshFaceRef(
            SourceFaceId(face_ids[k]),
            tuple(SourceVertexId(vertex_ids[x]) for x in f.vertex_ids),
            tuple(SourceEdgeId(edge_ids[x]) for x in f.edge_ids),
            f.face_strength,
        )
        for k, f in source.faces.items()
    }
    shuffled = list(faces.items())
    rng.shuffle(shuffled)
    selected = [SourceFaceId(face_ids[k]) for k in source.selected_face_ids]
    rng.shuffle(selected)
    marks = tuple(replace(mark, target_id=SourceEdgeId(edge_ids[mark.target_id])) for mark in source.marks)
    permuted = replace(
        source,
        vertices=vertices,
        edges=dict(sorted(edges.items(), key=lambda _item: rng.random())),
        faces=dict(shuffled),
        selected_face_ids=tuple(selected),
        marks=marks,
    )
    return permuted, {new: old for old, new in face_ids.items()}


def _signature(context, face_map=None):
    faces_of = {
        patch_id: frozenset((face_map or {}).get(str(face), str(face)) for face in patch.source_face_ids)
        for patch_id, patch in context.topology_snapshot.patches.items()
    }
    out = set()
    for record in context.feature_snapshot.bevels:
        if record.kind is FeatureKind.BEVEL_STRIP:
            extra = (
                record.faces_per_column, record.column_count, record.reading_index is None, record.corner_kind,
                frozenset((frozenset(faces_of[p] for p in record.rail_a_neighbour_patch_ids),
                           frozenset(faces_of[p] for p in record.rail_b_neighbour_patch_ids))),
            )
        else:
            extra = (
                frozenset((faces_of[c.strip_patch_id], c.strip_end is None) for c in record.joined_strips),
                frozenset(faces_of[p] for p in record.other_neighbour_patch_ids),
                record.touches_mesh_border,
            )
        out.add((faces_of[record.patch_id], record.kind, record.status, record.source, extra))
    return out


@pytest.mark.parametrize("make", (
    lambda: _case("u_rounded_wall_noise_top", marks=False)[0].source_snapshot,
    lambda: _case("g_short", marks=False)[0].source_snapshot,
    lambda: _with_triangulated_main_faces("a_cube_s3"),
    make_open_slab_source,
    make_tube_with_one_quad_column_source,
), ids=("user_mesh", "g_short", "cube_s3_triangulated_mains", "open_slab", "tube_one_column"))
def test_rule_b_does_not_depend_on_ids_or_order(make) -> None:
    source = make()
    expected = _signature(_run(source))
    for seed in range(4):
        permuted, face_map = _permuted(source, seed)
        assert _signature(_run(permuted), face_map) == expected


def test_a_prism_of_quad_columns_between_two_ngon_caps_is_no_bevel() -> None:
    # Every side patch has an end-strict reading between the caps with its
    # rails on two different patches, but those are side patches too: strips
    # must lie between surfaces that are not strips. Then the caps join no strip.
    source = make_capped_prism_source(6)
    context = _run(source)
    assert context.feature_snapshot.bevels == ()
    mesh = feature_bevels._BevelMesh(context.topology_snapshot, context.relation_snapshot, source)
    assert len(mesh.ladders) == 6
    for patch_id, relation in mesh.ladders.items():
        assert any(
            mesh.end_strict(patch_id, reading) and mesh.rails_on_two_patches(patch_id, reading)
            for reading in relation.readings
        )


def test_a_junction_touching_a_main_surface_is_no_pure_junction() -> None:
    context = _run(make_quad_between_two_surfaces_source(junction_touches_surface=True))
    assert context.feature_snapshot.bevels == ()
    control = _run(make_quad_between_two_surfaces_source(junction_touches_surface=False))
    strip = _accepted(control, FeatureKind.BEVEL_STRIP)["patch:seed:f0"]
    assert strip.source is BevelEvidenceSource.STRUCTURE and strip.reading_index is not None
    assert {strip.rail_a_neighbour_patch_ids, strip.rail_b_neighbour_patch_ids} == {("patch:seed:f2",), ("patch:seed:f3",)}
    junction = _accepted(control, FeatureKind.BEVEL_JUNCTION)["patch:seed:f1"]
    (contact,) = junction.joined_strips
    assert str(contact.strip_patch_id) == "patch:seed:f0" and contact.strip_end is not None
    assert junction.touches_mesh_border


def test_an_unmarked_strip_running_to_the_mesh_border_is_not_found_by_structure() -> None:
    assert _run(make_corner_bevel_source(marked=False)).feature_snapshot.bevels == ()


# --------------------------------------------------------------------------- boundaries


def test_positions_do_not_change_a_bevel_record_except_its_corner_kind() -> None:
    source = load_source_snapshot(BEVEL_CASES / "u_rounded_wall_noise_top.capture.json")
    rng = random.Random(7)
    moved = replace(source, vertices={
        key: replace(vertex, position=tuple(c + rng.uniform(-0.3, 0.3) for c in vertex.position))
        for key, vertex in source.vertices.items()
    })
    for marks in (True, False):
        pair = []
        for snapshot in (source, moved):
            if not marks:
                snapshot = replace(snapshot, faces={k: replace(f, face_strength=None) for k, f in snapshot.faces.items()})
            pair.append(tuple(replace(record, corner_kind=BevelCornerKind.UNDEFINED)
                              for record in _run(snapshot).feature_snapshot.bevels))
        assert pair[0] == pair[1] and pair[0]


def test_layer_5_does_not_read_the_bevel_records() -> None:
    context, _truth = _case("u_rounded_wall_noise_top")
    assert context.feature_snapshot.bevels
    without = replace(context, feature_snapshot=replace(context.feature_snapshot, bevels=(), diagnostics=()))
    assert run_skeleton_solve(context) == run_skeleton_solve(without)
    # The constraints are the channel: without them the ladder layout is gone.
    no_constraints = replace(without, feature_snapshot=replace(without.feature_snapshot, constraints=()))
    assert run_skeleton_solve(no_constraints) != run_skeleton_solve(context)


@pytest.mark.parametrize("straighten", (False, True))
def test_pass_2_emits_no_bevel_constraint_with_the_bevel_option_off(straighten) -> None:
    for name in ("u_rounded_wall_noise_top", "a_cube_s3", "c_arch_s2"):
        for marks in (True, False):
            context, _truth = _case(name, marks=marks)
            options = FeatureOptions(straighten_strips=straighten, straighten_bevel_strips=False)
            features = run_pass_2_features(context, options).feature_snapshot
            strip_only = feature_build.build_feature_snapshot(
                context.topology_snapshot, context.geometry_facts, context.relation_snapshot, options
            )
            assert features.constraints == strip_only.constraints
            assert all(c.kind is FeatureConstraintKind.STRAIGHT_STRIP for c in features.constraints)
            # Paired positive: with the option on, the marked cases get ladder constraints.
            on = run_pass_2_features(context, replace(options, straighten_bevel_strips=True)).feature_snapshot
            ladders = [c for c in on.constraints if c.kind is FeatureConstraintKind.STRAIGHT_LADDER]
            assert bool(ladders) == marks


def test_bevel_rule_reads_no_geometry_world_axis_or_layer_5() -> None:
    text = inspect.getsource(feature_bevels)
    bevel_part = text[text.index("# ---------------------------------------------------------------- BEVEL rule"):]
    for word in ("geometry", "position", "normal", "length", "chain_facts", "patch_facts", "WORLD", "uv", "island", "layer_5"):
        assert re.search(rf"\b{word}\b", bevel_part) is None, word


# A read of a raw position: an attribute named position or *_position, the
# vertex table of a snapshot, or a Blender coordinate.
POSITION_READS = (r"\.position\b", r"\w+_position\b", r"\.vertices\b", r"\.co\b")


def test_layer_4_reads_no_raw_position_anywhere() -> None:
    """Lengths are Layer 2 facts (G0 DD-03): no module of layer_4_features reads a vertex position."""

    package = Path(feature_build.__file__).parent
    modules = sorted(package.glob("*.py"))
    assert {path.name for path in modules} >= {"build.py", "bevels.py", "model.py"}
    for path in modules:
        text = path.read_text(encoding="utf-8")
        for pattern in POSITION_READS:
            assert re.search(pattern, text) is None, (path.name, pattern)
    # Paired positive: the guard sees a position read where there is one (Layer 2 builds them).
    layer_2 = (package.parent / "layer_2_geometry" / "build.py").read_text(encoding="utf-8")
    assert re.search(POSITION_READS[0], layer_2) and re.search(POSITION_READS[2], layer_2)


def test_inspection_counts_bevels_by_kind_source_and_status() -> None:
    context, _truth = _case("h_rect_s2_tri")
    report = inspect_pipeline_context(context)["features"]["bevels"]
    assert report == {
        "record_count": 4,
        "by_kind": {"BEVEL_STRIP": {"SOURCE_MARK ACCEPTED": 4}},
        "unresolved_strip_readings": 4,
        "strip_corner_kinds": {"UNDEFINED": 4},
    }
    suppressed = inspect_pipeline_context(_run(make_corner_bevel_source(seams=False)))["features"]["bevels"]
    assert suppressed["by_kind"] == {"BEVEL_STRIP": {"SOURCE_MARK bevel faces not isolated by seams": 1}}


# --------------------------------------------------------------------------- contacts and rails


def _contact_order(context, junction_id, strips):
    """The strips met along the junction's boundary loops, in loop order (each use walked its way)."""

    mesh = feature_bevels._BevelMesh(context.topology_snapshot, context.relation_snapshot, context.source_snapshot)
    order = []
    for loop_edges in mesh.loop_edges(junction_id):
        met = []
        for edge_id in loop_edges:
            kind, other = mesh.across(junction_id, edge_id)
            if kind == feature_bevels.ACROSS_PATCH and other in strips and (not met or met[-1] != other):
                met.append(other)
        if len(met) > 1 and met[0] == met[-1]:
            met.pop()
        order.extend(met)
    return order


@pytest.mark.parametrize("marks", (True, False))
def test_junction_contacts_follow_the_boundary_loop_and_lie_on_strip_ends(marks) -> None:
    differs_from_ids = False
    for name in ("a_cube_s1", "g_short", "u_rounded_wall_noise_top"):
        context, _truth = _case(name, marks=marks)
        strips = _accepted(context, FeatureKind.BEVEL_STRIP)
        for junction_id, junction in _accepted(context, FeatureKind.BEVEL_JUNCTION).items():
            contacts = [str(contact.strip_patch_id) for contact in junction.joined_strips]
            assert contacts == _contact_order(context, junction_id, strips)
            differs_from_ids |= contacts != sorted(contacts)
            for contact in junction.joined_strips:
                strip = strips[str(contact.strip_patch_id)]
                assert contact.strip_end is not None and strip.reading_index is not None
    assert differs_from_ids  # loop order is not id order on these meshes


@pytest.mark.parametrize("name", ("a_cube_s3", "g_short", "u_rounded_wall_noise_top", "c_arch_s2"))
def test_each_rail_lists_the_patches_across_its_own_edges(name) -> None:
    context, _truth = _case(name)
    ladders = {str(r.patch_id): r for r in context.relation_snapshot.patch_quad_ladder_relations}
    patch_of_face = {face: str(pid) for pid, patch in context.topology_snapshot.patches.items() for face in patch.source_face_ids}
    rails_differ = False
    for patch_id, record in _accepted(context, FeatureKind.BEVEL_STRIP).items():
        if record.reading_index is None:
            continue
        reading = ladders[patch_id].readings[record.reading_index]
        for faces, edges, neighbours in (
            ([column[0] for column in reading.columns], reading.rail_a_source_edge_ids, record.rail_a_neighbour_patch_ids),
            ([column[-1] for column in reading.columns], reading.rail_b_source_edge_ids, record.rail_b_neighbour_patch_ids),
        ):
            across = []
            for face_id, edge_id in zip(faces, edges):
                for other in _faces_across(context, face_id, edge_id):
                    if patch_of_face[other] not in across:
                        across.append(patch_of_face[other])
            assert [str(p) for p in neighbours] == across
        rails_differ |= set(record.rail_a_neighbour_patch_ids) != set(record.rail_b_neighbour_patch_ids)
    assert rails_differ
