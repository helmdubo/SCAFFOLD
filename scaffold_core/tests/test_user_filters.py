"""
Layer: tests

Rules:
- The over filter of user options (plan Slice AH): patch classes by the
  angle between a Layer 2 patch normal and a user world vertical, bevel class
  rules, SeamDirectives, and no filter without a world_up.
- No production logic here.
"""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from dev.tools.scaffold_graph_debug.snapshot_io import load_source_snapshot
from scaffold_core.layer_4_features.model import (
    BevelEvidenceSource,
    BevelInstance,
    BevelJunctionContact,
    FeatureInstanceStatus,
    FeatureKind,
    FeatureSnapshot,
)
from scaffold_core.pipeline.passes import (
    run_pass_0,
    run_pass_1_relations,
    run_pass_2_features,
    run_pass_3_filters,
)
from scaffold_core.tests.fixtures.quad_ladders import _mesh
from scaffold_core.user_filters.build import build_filter_snapshot
from scaffold_core.user_filters.model import (
    RULE_BEVEL_WITH_ITS_SURFACES,
    RULE_VERTICAL_APART_FROM_HORIZONTAL,
    FilterOptions,
    FilterSnapshot,
    PatchClass,
    PatchClassRule,
    SeamDirectiveKind,
)

ROUNDED = Path(__file__).resolve().parent / "data" / "bevel_cases" / "u_rounded_wall_noise_top.capture.json"
H_RECT_TRI = Path(__file__).resolve().parent / "data" / "bevel_cases" / "h_rect_s2_tri.capture.json"
CROSS_BAND = Path(__file__).resolve().parent / "data" / "artist_cross_band.json"
UP = (0.0, 0.0, 1.0)


def _normal_at(degrees_from_up: float) -> tuple[float, float, float]:
    angle = math.radians(degrees_from_up)
    return (math.sin(angle), 0.0, math.cos(angle))


def _fake(normals: dict[str, tuple[float, float, float]], seams=(), bevels=()):
    """Topology, geometry, relations and features with only what the filter reads."""

    topology = SimpleNamespace(patches={patch_id: None for patch_id in normals})
    geometry = SimpleNamespace(patch_facts={
        patch_id: SimpleNamespace(normal=normal) for patch_id, normal in normals.items()
    })
    relations = SimpleNamespace(patch_adjacencies={
        f"a{index}": SimpleNamespace(id=f"a{index}", chain_id=chain, first_patch_id=first, second_patch_id=second)
        for index, (chain, first, second) in enumerate(seams)
    })
    return topology, geometry, relations, FeatureSnapshot(bevels=tuple(bevels))


def _strip(patch_id, rail_a=(), rail_b=(), source=BevelEvidenceSource.SOURCE_MARK, status=FeatureInstanceStatus.ACCEPTED):
    return BevelInstance(
        id=f"bevel:{patch_id}", kind=FeatureKind.BEVEL_STRIP, patch_id=patch_id, status=status, source=source,
        rail_a_neighbour_patch_ids=tuple(rail_a), rail_b_neighbour_patch_ids=tuple(rail_b),
    )


def _junction(patch_id, strips):
    return BevelInstance(
        id=f"bevel:{patch_id}", kind=FeatureKind.BEVEL_JUNCTION, patch_id=patch_id,
        status=FeatureInstanceStatus.ACCEPTED, source=BevelEvidenceSource.SOURCE_MARK,
        joined_strips=tuple(BevelJunctionContact(strip, None) for strip in strips),
    )


def _classes(snapshot: FilterSnapshot) -> dict[str, PatchClass]:
    return {str(record.patch_id): record.patch_class for record in snapshot.patch_classes}


def _rounded_context(source=None):
    source = source if source is not None else load_source_snapshot(ROUNDED)
    return run_pass_2_features(run_pass_1_relations(run_pass_0(source)))


def test_no_world_up_means_no_filter() -> None:
    snapshot = build_filter_snapshot(*_fake({"p": UP}), FilterOptions())

    assert snapshot == FilterSnapshot(options=FilterOptions())


def test_classes_by_the_angle_between_the_patch_normal_and_up() -> None:
    normals = {
        "up": UP,
        "down": (0.0, 0.0, -1.0),
        "wall": (0.0, -1.0, 0.0),
        "steep_44": _normal_at(44.0),
        "steep_46": _normal_at(46.0),
        "under_44": _normal_at(180.0 - 44.0),
        "under_46": _normal_at(180.0 - 46.0),
    }
    snapshot = build_filter_snapshot(*_fake(normals), FilterOptions(world_up=UP))
    classes = _classes(snapshot)

    assert classes == {
        "up": PatchClass.HORIZONTAL,
        "down": PatchClass.HORIZONTAL,
        "wall": PatchClass.VERTICAL,
        "steep_44": PatchClass.HORIZONTAL,
        "steep_46": PatchClass.VERTICAL,
        "under_44": PatchClass.HORIZONTAL,
        "under_46": PatchClass.VERTICAL,
    }
    angles = {str(r.patch_id): r.angle_degrees for r in snapshot.patch_classes}
    assert angles["steep_44"] == pytest.approx(44.0) and angles["under_46"] == pytest.approx(46.0)
    assert all(r.rule is PatchClassRule.BY_NORMAL for r in snapshot.patch_classes)


def test_the_angle_is_a_user_option() -> None:
    normals = {"steep": _normal_at(50.0)}

    assert _classes(build_filter_snapshot(*_fake(normals), FilterOptions(UP, 45.0)))["steep"] is PatchClass.VERTICAL
    assert _classes(build_filter_snapshot(*_fake(normals), FilterOptions(UP, 55.0)))["steep"] is PatchClass.HORIZONTAL


def test_a_curved_wall_and_a_noisy_top_on_the_users_mesh() -> None:
    context = run_pass_3_filters(_rounded_context(), FilterOptions(world_up=UP))
    by_patch = {str(r.patch_id): r for r in context.filter_snapshot.patch_classes}

    # f110 and f211 are developable curved walls, f0 the noisy top, f111 the flat bottom.
    for wall in ("f110", "f211", "f112"):
        assert by_patch[f"patch:seed:{wall}"].patch_class is PatchClass.VERTICAL
        assert by_patch[f"patch:seed:{wall}"].angle_degrees == pytest.approx(90.0, abs=0.5)
    assert by_patch["patch:seed:f0"].patch_class is PatchClass.HORIZONTAL
    assert 0.0 < by_patch["patch:seed:f0"].angle_degrees < 10.0
    assert by_patch["patch:seed:f111"].patch_class is PatchClass.HORIZONTAL


def test_a_bevel_strip_goes_with_its_horizontal_neighbour() -> None:
    normals = {"top": UP, "wall": (0.0, -1.0, 0.0), "wall_b": (1.0, 0.0, 0.0), "s_top": _normal_at(45.0),
               "s_corner": (0.7, -0.7, 0.0)}
    bevels = (_strip("s_top", ["top"], ["wall"]), _strip("s_corner", ["wall"], ["wall_b"]))
    snapshot = build_filter_snapshot(*_fake(normals, bevels=bevels), FilterOptions(world_up=UP))
    by_patch = {str(r.patch_id): r for r in snapshot.patch_classes}

    assert by_patch["s_top"].patch_class is PatchClass.HORIZONTAL
    assert by_patch["s_corner"].patch_class is PatchClass.VERTICAL
    assert by_patch["s_top"].rule is PatchClassRule.BEVEL_STRIP_BY_RAIL_NEIGHBOURS
    assert by_patch["s_top"].is_bevel


def test_a_structural_bevel_record_is_an_ordinary_patch() -> None:
    normals = {"top": UP, "wall": (0.0, -1.0, 0.0), "s": (0.0, -0.1, 0.995)}
    bevels = (_strip("s", ["top"], ["wall"], source=BevelEvidenceSource.STRUCTURE),)
    snapshot = build_filter_snapshot(
        *_fake(normals, seams=[("c1", "s", "wall"), ("c2", "s", "top")], bevels=bevels), FilterOptions(world_up=UP)
    )

    record = next(r for r in snapshot.patch_classes if r.patch_id == "s")
    assert record.rule is PatchClassRule.BY_NORMAL and not record.is_bevel
    # No JOIN: the structure decides the seam to the top; the seam to the wall is split.
    assert [(str(d.chain_id), d.kind) for d in snapshot.directives] == [("c1", SeamDirectiveKind.SPLIT)]


def test_a_bevel_junction_takes_the_majority_of_its_strips_and_a_tie_is_horizontal() -> None:
    normals = {"top": UP, "wall": (0.0, -1.0, 0.0), "wall_b": (1.0, 0.0, 0.0),
               "h1": _normal_at(45.0), "h2": _normal_at(45.0), "v": (0.7, -0.7, 0.0),
               "j_major": (0.5, -0.5, 0.7), "j_tie": (0.5, -0.5, 0.7), "j_vertical": (0.5, -0.5, 0.7)}
    bevels = (
        _strip("h1", ["top"], ["wall"]), _strip("h2", ["top"], ["wall_b"]), _strip("v", ["wall"], ["wall_b"]),
        _junction("j_major", ["h1", "h2", "v"]), _junction("j_tie", ["h1", "v"]), _junction("j_vertical", ["v"]),
    )
    snapshot = build_filter_snapshot(*_fake(normals, bevels=bevels), FilterOptions(world_up=UP))
    classes = _classes(snapshot)

    assert classes["j_major"] is PatchClass.HORIZONTAL
    assert classes["j_tie"] is PatchClass.HORIZONTAL
    assert classes["j_vertical"] is PatchClass.VERTICAL
    assert [d.code for d in snapshot.diagnostics] == ["FILTER_BEVEL_JUNCTION_TIE"]
    assert snapshot.diagnostics[0].entity_ids == ("j_tie",)


def test_directives_split_vertical_from_horizontal_and_join_a_bevel_with_its_surfaces() -> None:
    normals = {"top": UP, "wall": (0.0, -1.0, 0.0), "wall_b": (1.0, 0.0, 0.0), "floor": (0.0, 0.0, -1.0),
               "s_top": _normal_at(45.0), "s_corner": (0.7, -0.7, 0.0)}
    seams = [
        ("top|s_top", "top", "s_top"), ("s_top|wall", "s_top", "wall"),
        ("wall|s_corner", "wall", "s_corner"), ("s_corner|wall_b", "s_corner", "wall_b"),
        ("wall|wall_b", "wall", "wall_b"), ("wall|floor", "wall", "floor"),
    ]
    bevels = (_strip("s_top", ["top"], ["wall"]), _strip("s_corner", ["wall"], ["wall_b"]))
    snapshot = build_filter_snapshot(*_fake(normals, seams=seams, bevels=bevels), FilterOptions(world_up=UP))

    assert {(str(d.chain_id), d.kind, d.rule) for d in snapshot.directives} == {
        ("top|s_top", SeamDirectiveKind.JOIN, RULE_BEVEL_WITH_ITS_SURFACES),
        ("s_top|wall", SeamDirectiveKind.SPLIT, RULE_VERTICAL_APART_FROM_HORIZONTAL),
        ("wall|s_corner", SeamDirectiveKind.JOIN, RULE_BEVEL_WITH_ITS_SURFACES),
        ("s_corner|wall_b", SeamDirectiveKind.JOIN, RULE_BEVEL_WITH_ITS_SURFACES),
        ("wall|floor", SeamDirectiveKind.SPLIT, RULE_VERTICAL_APART_FROM_HORIZONTAL),
    }  # wall|wall_b: same class, no bevel -> no directive, the structure decides


def test_directives_on_the_users_mesh() -> None:
    context = run_pass_3_filters(_rounded_context(), FilterOptions(world_up=UP))
    short = lambda patch_id: str(patch_id).replace("patch:seed:", "")  # noqa: E731
    split = {frozenset((short(d.first_patch_id), short(d.second_patch_id)))
             for d in context.filter_snapshot.directives if d.kind is SeamDirectiveKind.SPLIT}
    joined = {frozenset((short(d.first_patch_id), short(d.second_patch_id)))
              for d in context.filter_snapshot.directives if d.kind is SeamDirectiveKind.JOIN}

    # Horizontal strips are split from the walls, the vertical strips from the junctions.
    assert split == {frozenset(pair) for pair in (
        ("f35", "f110"), ("f36", "f110"), ("f71", "f211"), ("f73", "f211"), ("f95", "f112"), ("f96", "f112"),
        ("f28", "f34"), ("f29", "f34"), ("f30", "f94"), ("f31", "f72"), ("f32", "f72"), ("f33", "f94"),
    )}
    assert len(joined) == 24
    assert {frozenset(("f34", "f110")), frozenset(("f0", "f35")), frozenset(("f111", "f36"))} <= joined
    assert not context.filter_snapshot.diagnostics


def _rotate(point, matrix):
    return tuple(sum(matrix[i][k] * point[k] for k in range(3)) for i in range(3))


def test_rotating_the_mesh_and_the_up_vector_together_changes_nothing() -> None:
    a, b = 0.7, -0.4
    rz = ((math.cos(a), -math.sin(a), 0.0), (math.sin(a), math.cos(a), 0.0), (0.0, 0.0, 1.0))
    rx = ((1.0, 0.0, 0.0), (0.0, math.cos(b), -math.sin(b)), (0.0, math.sin(b), math.cos(b)))
    matrix = tuple(tuple(sum(rx[i][k] * rz[k][j] for k in range(3)) for j in range(3)) for i in range(3))
    source = load_source_snapshot(ROUNDED)
    rotated = replace(source, vertices={
        key: replace(vertex, position=_rotate(vertex.position, matrix)) for key, vertex in source.vertices.items()
    })
    plain = run_pass_3_filters(_rounded_context(source), FilterOptions(world_up=UP)).filter_snapshot
    turned = run_pass_3_filters(_rounded_context(rotated), FilterOptions(world_up=_rotate(UP, matrix))).filter_snapshot

    assert [(r.patch_id, r.patch_class, r.rule) for r in plain.patch_classes] == [
        (r.patch_id, r.patch_class, r.rule) for r in turned.patch_classes
    ]
    assert [r.angle_degrees for r in turned.patch_classes] == pytest.approx(
        [r.angle_degrees for r in plain.patch_classes], abs=1e-6
    )
    assert plain.directives == turned.directives


def test_a_different_world_up_reclassifies() -> None:
    context = _rounded_context()
    by_z = _classes(run_pass_3_filters(context, FilterOptions(world_up=UP)).filter_snapshot)
    by_y = _classes(run_pass_3_filters(context, FilterOptions(world_up=(0.0, 1.0, 0.0))).filter_snapshot)

    assert by_z["patch:seed:f0"] is PatchClass.HORIZONTAL and by_y["patch:seed:f0"] is PatchClass.VERTICAL
    assert by_z["patch:seed:f112"] is PatchClass.VERTICAL and by_y["patch:seed:f112"] is PatchClass.HORIZONTAL


def test_pass_3_without_world_up_stores_an_empty_snapshot() -> None:
    context = run_pass_3_filters(_rounded_context(), FilterOptions())

    assert context.filter_snapshot == FilterSnapshot()
    assert context.pass_timings[-1].name == "pass_3.filter_snapshot"


def test_a_zero_world_up_is_refused() -> None:
    with pytest.raises(ValueError):
        build_filter_snapshot(*_fake({"p": UP}), FilterOptions(world_up=(0.0, 0.0, 0.0)))


def test_the_angle_threshold_is_inclusive() -> None:
    # A normal exactly perpendicular to up is at exactly 90 degrees.
    snapshot = build_filter_snapshot(*_fake({"wall": (1.0, 0.0, 0.0)}), FilterOptions(UP, 90.0))

    assert snapshot.patch_classes[0].angle_degrees == 90.0
    assert _classes(snapshot)["wall"] is PatchClass.HORIZONTAL


def test_a_degenerate_normal_is_vertical_with_a_diagnostic() -> None:
    snapshot = build_filter_snapshot(*_fake({"p": (0.0, 0.0, 0.0)}), FilterOptions(UP, 90.0))

    assert _classes(snapshot)["p"] is PatchClass.VERTICAL
    assert snapshot.patch_classes[0].angle_degrees is None
    assert [d.code for d in snapshot.diagnostics] == ["FILTER_PATCH_NORMAL_DEGENERATE"]


def test_no_join_for_a_suppressed_bevel_record() -> None:
    normals = {"top": UP, "wall": (0.0, -1.0, 0.0), "s": _normal_at(45.0)}
    bevels = (_strip("s", ["top"], ["wall"], status=FeatureInstanceStatus.SUPPRESSED),)
    snapshot = build_filter_snapshot(
        *_fake(normals, seams=[("c1", "s", "top"), ("c2", "s", "wall")], bevels=bevels), FilterOptions(world_up=UP)
    )

    record = next(r for r in snapshot.patch_classes if r.patch_id == "s")
    assert record.rule is PatchClassRule.BY_NORMAL and not record.is_bevel
    assert not any(d.kind is SeamDirectiveKind.JOIN for d in snapshot.directives)


def test_a_strip_without_rails_goes_with_a_horizontal_adjacent_patch() -> None:
    # h_rect_s2_tri: the marked strips f8 and f12 are triangulated (no ladder
    # reading, no rails); at 49 degrees their own normal would make them
    # vertical and split them from their horizontal tops f18 and f23.
    context = run_pass_3_filters(_rounded_context(load_source_snapshot(H_RECT_TRI)), FilterOptions(world_up=UP))
    by_patch = {str(r.patch_id).replace("patch:seed:", ""): r for r in context.filter_snapshot.patch_classes}
    directive = {
        frozenset(str(p).replace("patch:seed:", "") for p in (d.first_patch_id, d.second_patch_id)): d.kind
        for d in context.filter_snapshot.directives
    }

    for strip, top in (("f8", "f18"), ("f12", "f23")):
        assert by_patch[strip].is_bevel and by_patch[strip].angle_degrees == pytest.approx(49.08, abs=0.01)
        assert by_patch[strip].patch_class is PatchClass.HORIZONTAL
        assert by_patch[strip].rule is PatchClassRule.BEVEL_STRIP_BY_ADJACENT_PATCHES
        assert directive[frozenset((strip, top))] is SeamDirectiveKind.JOIN
    assert not context.filter_snapshot.diagnostics


def test_a_strip_without_rails_ignores_bevel_neighbours_and_without_any_takes_its_normal() -> None:
    normals = {"wall": (0.0, -1.0, 0.0), "s": _normal_at(30.0), "s_only": _normal_at(30.0), "a_peer": UP}
    bevels = (_strip("s"), _strip("s_only"), _strip("a_peer"))
    seams = [("c1", "s", "wall"), ("c2", "s", "a_peer"), ("c3", "s_only", "a_peer")]
    snapshot = build_filter_snapshot(*_fake(normals, seams=seams, bevels=bevels), FilterOptions(world_up=UP))
    by_patch = {str(r.patch_id): r for r in snapshot.patch_classes}

    # Its one surface is a wall; the bevel peer (classed first, horizontal) is ignored.
    assert by_patch["s"].patch_class is PatchClass.VERTICAL
    assert by_patch["s"].rule is PatchClassRule.BEVEL_STRIP_BY_ADJACENT_PATCHES
    assert by_patch["s_only"].rule is PatchClassRule.BY_NORMAL
    assert by_patch["s_only"].patch_class is PatchClass.HORIZONTAL
    assert "FILTER_BEVEL_STRIP_WITHOUT_SURFACE" in {d.code for d in snapshot.diagnostics}


def test_a_patch_whose_face_normals_cancel_has_no_usable_normal() -> None:
    # artist_cross_band f1: a band around a cross, |sum of face area vectors|
    # is about 1.8e-4 of the total face area.
    context = run_pass_3_filters(_rounded_context(load_source_snapshot(CROSS_BAND)), FilterOptions(world_up=UP))
    by_patch = {str(r.patch_id): r for r in context.filter_snapshot.patch_classes}

    assert by_patch["patch:seed:f1"].angle_degrees is None
    assert by_patch["patch:seed:f1"].patch_class is PatchClass.VERTICAL
    assert [(d.code, d.entity_ids) for d in context.filter_snapshot.diagnostics] == [
        ("FILTER_PATCH_NORMAL_DEGENERATE", ("patch:seed:f1",))
    ]
    assert by_patch["patch:seed:f0"].patch_class is PatchClass.HORIZONTAL


def test_a_half_cylinder_keeps_its_normal_at_any_size() -> None:
    # |sum of face area vectors| / total area of a half cylinder is 2 / pi.
    for radius in (1e-4, 1.0, 1e4):
        segments = 8
        positions = {}
        for i in range(segments + 1):
            angle = math.pi * i / segments
            for j, y in enumerate((0.0, 2.0 * radius)):
                positions[f"v{i}_{j}"] = (radius * math.cos(angle), y, radius * math.sin(angle))
        faces = [(f"v{i}_0", f"v{i}_1", f"v{i + 1}_1", f"v{i + 1}_0") for i in range(segments)]
        context = run_pass_3_filters(_rounded_context(_mesh("half_cylinder", positions, faces)), FilterOptions(UP))
        (record,) = context.filter_snapshot.patch_classes

        assert record.angle_degrees == pytest.approx(0.0, abs=1e-6)
        assert record.patch_class is PatchClass.HORIZONTAL
        assert not context.filter_snapshot.diagnostics
