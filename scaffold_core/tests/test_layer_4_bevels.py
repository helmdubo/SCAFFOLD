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
from scaffold_core.layer_4_features import build as feature_build
from scaffold_core.layer_4_features.model import (
    BevelCornerKind,
    BevelEvidenceSource,
    BevelStripEnd,
    FeatureInstanceStatus,
    FeatureKind,
    FeatureSuppressionReason,
)
from scaffold_core.layer_5_runtime.pins import run_skeleton_solve
from scaffold_core.pipeline.inspection import inspect_pipeline_context
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations, run_pass_2_features
from scaffold_core.tests.fixtures.bevel_patches import (
    MEDIUM,
    WEAK,
    make_capped_prism_source,
    make_corner_bevel_source,
    make_quad_between_junction_and_one_surface_source,
    make_quad_between_two_surfaces_source,
    make_quad_with_four_junctions_source,
    make_single_quad_source,
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
# the main surfaces (inner arc miter) and triangulated bevels have no pure
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
    diagnostics = [d for d in context.feature_snapshot.diagnostics if d.code == feature_build.BEVEL_UNRESOLVED_CODE]
    assert sorted(d.entity_ids[0] for d in diagnostics) == sorted(str(record.patch_id) for record in unresolved)
    if name in UNRESOLVED_BY_MARK:
        assert {d.evidence["reason"] for d in diagnostics} == {feature_build.UNRESOLVED_NO_LADDER}
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
def test_by_structure_finds_nothing_without_a_pure_junction_known_limit(name) -> None:
    context, _truth = _case(name, marks=False)
    assert context.feature_snapshot.bevels == ()


@pytest.mark.parametrize("name", CASE_NAMES)
def test_by_structure_never_calls_a_main_surface_or_reveal_a_bevel(name) -> None:
    context, truth = _case(name, marks=False)
    by_patch = _truth_by_patch(context, truth)
    for record in context.feature_snapshot.bevels:
        expected = "STRIP" if record.kind is FeatureKind.BEVEL_STRIP else "JUNCTION"
        assert by_patch[str(record.patch_id)] == expected


# The non-bevel captures give no bevel record by structure. Before the two
# Rule B conditions (strips between non-strips, junctions join a strip) a
# tube cut into one-column wall pieces between n-gon caps (artist_cyl_multiseam)
# read as six strips and two junctions, and the caps of artist_cyl32 and the
# end patches of artist_cross_band as strip-less junctions.
@pytest.mark.parametrize("path", sorted(DATA.glob("*.json")), ids=lambda path: path.stem)
def test_by_structure_on_the_non_bevel_captures_finds_nothing(path) -> None:
    context = _run(load_source_snapshot(path))
    assert context.feature_snapshot.bevels == ()


# --------------------------------------------------------------------------- corner kind


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
    strong = replace(source, faces={k: replace(f, face_strength=feature_build.SourceFaceStrength.STRONG)
                                    for k, f in source.faces.items()})
    assert _run(strong).feature_snapshot.bevels == ()


def test_a_marked_strip_with_two_fitting_readings_is_accepted_unresolved() -> None:
    context = _run(make_single_quad_source())
    (record,) = context.feature_snapshot.bevels
    assert record.status is FeatureInstanceStatus.ACCEPTED and record.reading_index is None
    (diagnostic,) = context.feature_snapshot.diagnostics
    assert diagnostic.entity_ids == ("patch:seed:f0",)
    assert diagnostic.evidence["reason"] == feature_build.UNRESOLVED_TWO_READINGS_FIT_MARKS


def test_two_qualifying_readings_by_structure_leave_the_strip_unresolved() -> None:
    context = _run(make_quad_with_four_junctions_source())
    strips = _accepted(context, FeatureKind.BEVEL_STRIP)
    assert list(strips) == ["patch:seed:f0"] and strips["patch:seed:f0"].reading_index is None
    assert sorted(_accepted(context, FeatureKind.BEVEL_JUNCTION)) == [f"patch:seed:f{i}" for i in range(1, 5)]
    (diagnostic,) = context.feature_snapshot.diagnostics
    assert diagnostic.evidence["reason"] == feature_build.UNRESOLVED_TWO_READINGS_QUALIFY


def test_a_pure_junction_next_to_ladders_that_fail_the_rail_test_gets_no_record() -> None:
    # The quad's ends lie on the pure junction J, but both its rails touch one
    # patch: no strip, so J joins no strip and gets no record either.
    source = make_quad_between_junction_and_one_surface_source()
    context = _run(source)
    assert context.feature_snapshot.bevels == ()
    mesh = feature_build._BevelMesh(context.topology_snapshot, context.relation_snapshot, source)
    (relation,) = [r for r in context.relation_snapshot.patch_quad_ladder_relations if r.patch_id == "patch:seed:f0"]
    assert all(mesh.end_strict("patch:seed:f0", reading) for reading in relation.readings)
    assert "patch:seed:f1" not in mesh.ladders


def test_a_prism_of_quad_columns_between_two_ngon_caps_is_no_bevel() -> None:
    # Every side patch has an end-strict reading between the caps with its
    # rails on two different patches, but those are side patches too: strips
    # must lie between surfaces that are not strips. Then the caps join no strip.
    source = make_capped_prism_source(6)
    context = _run(source)
    assert context.feature_snapshot.bevels == ()
    mesh = feature_build._BevelMesh(context.topology_snapshot, context.relation_snapshot, source)
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


def test_bevel_rule_reads_no_geometry_world_axis_or_layer_5() -> None:
    text = inspect.getsource(feature_build)
    bevel_part = text[text.index("# ---------------------------------------------------------------- BEVEL rule"):]
    for word in ("geometry", "position", "normal", "length", "chain_facts", "patch_facts", "WORLD", "uv", "island", "layer_5"):
        assert re.search(rf"\b{word}\b", bevel_part) is None, word


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
