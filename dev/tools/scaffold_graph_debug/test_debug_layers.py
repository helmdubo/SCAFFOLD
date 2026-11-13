"""Headless checks: every debugger layer equals the pipeline records it draws."""

from __future__ import annotations

import inspect
import math
from collections import Counter
from types import SimpleNamespace

import pytest

from dev.tools.scaffold_graph_debug import overlay_ladders, overlay_v2
from dev.tools.scaffold_graph_debug.overlay_v2 import (
    GROUPS,
    LAYER_SPECS,
    LEGENDS,
    PATCH_TYPE_LAYERS,
    build_debug_payload,
)
from dev.tools.scaffold_graph_debug.snapshot_io import load_source_snapshot
from scaffold_core.layer_4_features.model import FeatureOptions
from scaffold_core.layer_5_runtime.pins import run_skeleton_solve
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations, run_pass_2_features
from scaffold_core.tests.fixtures.beveled_wall_corner import make_beveled_wall_corner_source
from scaffold_core.tests.fixtures.cylinder_tube import make_cylinder_tube_without_caps_with_two_seams_source
from scaffold_core.tests.fixtures.extruded_cross import make_extruded_cross_source
from scaffold_core.tests.fixtures.run_corner_sheets import make_notched_sheet_source
from scaffold_core.tests.fixtures.tube_with_cap import make_tube_with_cap_source


def _capture(name):
    return lambda: load_source_snapshot(f"scaffold_core/tests/data/{name}.json")


CASES = {
    "beveled_corner": (make_beveled_wall_corner_source, False),
    "tube_two_seams": (make_cylinder_tube_without_caps_with_two_seams_source, False),
    "tube_with_cap": (make_tube_with_cap_source, False),
    "extruded_cross": (make_extruded_cross_source, False),
    "artist_cyl32": (_capture("artist_cyl32"), False),
    "artist_walls_004": (_capture("artist_walls_004_selection"), False),
    "artist_walls_007": (_capture("artist_walls_007"), False),
    "artist_arch_bevel_strips_on": (_capture("artist_arch_bevel"), True),
    "artist_arch_bevel_strips_off": (_capture("artist_arch_bevel"), False),
    "rounded_wall_bevel_marks": (_capture("bevel_cases/u_rounded_wall_noise_top.capture"), False),
}
# Written out here, not read from the module: AXIS_A yellow, AXIS_B cyan.
ROLE_RGBA = {"AXIS_A": [1.0, 0.85, 0.0, 1.0], "AXIS_B": [0.0, 0.85, 0.85, 1.0]}
OBLIQUE_RGBA = [0.55, 0.55, 0.55, 0.7]
_CACHE: dict[str, tuple] = {}


def _run(case: str):
    if case not in _CACHE:
        factory, straighten = CASES[case]
        context = run_pass_2_features(
            run_pass_1_relations(run_pass_0(factory())),
            FeatureOptions(straighten_strips=straighten),
        )
        solve = run_skeleton_solve(context)
        _CACHE[case] = (context, solve, build_debug_payload(context, solve, object_name=case))
    return _CACHE[case]


@pytest.mark.parametrize("case", sorted(CASES))
def test_every_use_gets_exactly_one_chain_stroke_set_with_its_run_roles(case) -> None:
    context, solve, payload = _run(case)
    evidence = context.relation_snapshot.patch_chain_directional_evidence
    runs_by_use: dict[str, set[str]] = {}
    for record in evidence:
        runs_by_use.setdefault(str(record.patch_chain_id), set()).add(record.id)
    role_by_run = {
        run_id: role for skeleton in solve.skeletons for run_id, role in skeleton.axis_role_by_run.items()
    }

    items = payload["layers"]["Scaffold_Chains"]
    by_use: dict[str, list[dict]] = {}
    for item in items:
        by_use.setdefault(item["patch_chain_id"], []).append(item)
    assert set(by_use) == {str(patch_chain_id) for patch_chain_id in context.topology_snapshot.patch_chains}
    for use_id, use_items in by_use.items():
        runs = runs_by_use.get(use_id, set())
        if runs:
            assert sorted(item["run_id"] for item in use_items) == sorted(runs)
        else:
            assert [item["run_id"] for item in use_items] == [None]
    for item in items:
        assert item["role"] == role_by_run.get(item["run_id"])
        assert len(item["strokes"]) == 1
        stroke = item["strokes"][0]
        if item["role"] in ROLE_RGBA:
            assert stroke["color"] == ROLE_RGBA[item["role"]]
            assert stroke["width"] == 6
        else:
            assert stroke["color"] == OBLIQUE_RGBA
            assert stroke["width"] == 3


@pytest.mark.parametrize("case", sorted(CASES))
def test_lines_group_exactly_the_runs_of_line_by_run(case) -> None:
    _context, solve, payload = _run(case)
    expected = {}
    for skeleton in solve.skeletons:
        for run_id, line_id in skeleton.line_by_run.items():
            expected.setdefault((skeleton.island_id, str(line_id)), set()).add(run_id)
    items = payload["layers"]["Scaffold_Skeleton_Lines"]
    got = {(item["island_id"], item["line_id"]): set(item["run_ids"]) for item in items}
    assert got == expected
    for item in items:
        assert len({tuple(stroke["color"]) for stroke in item["strokes"]}) <= 1
        assert len(item["strokes"]) == len(item["run_ids"])


@pytest.mark.parametrize("case", sorted(CASES))
def test_seams_equal_the_stitch_decisions_one_to_one(case) -> None:
    _context, solve, payload = _run(case)
    items = payload["layers"]["Scaffold_Seams"]
    assert [
        (item["chain_id"], item["first_patch_id"], item["second_patch_id"], item["accepted"], item["reason"])
        for item in items
    ] == [
        (str(d.chain_id), str(d.first_patch_id), str(d.second_patch_id), bool(d.accepted), str(d.reason))
        for d in solve.assembly.decisions
    ]
    for item in items:
        assert item["strokes"]
        materials = {stroke["material"] for stroke in item["strokes"]}
        assert materials == {"seam_accepted" if item["accepted"] else "seam_refused"}
        if not item["accepted"]:
            assert len(item["strokes"]) == 1
        else:
            assert all(len(stroke["points"]) == 2 for stroke in item["strokes"])


@pytest.mark.parametrize("case", sorted(CASES))
def test_patch_types_equal_the_layer_4_instances(case) -> None:
    context, _solve, payload = _run(case)
    features = context.feature_snapshot
    expected = {str(patch_id): "OTHER" for patch_id in context.topology_snapshot.patches}
    for instance in features.instances:
        patch_id = str(instance.patch_id)
        if instance.status.value == "ACCEPTED":
            expected[patch_id] = "STRIP"
        elif expected[patch_id] == "OTHER":
            expected[patch_id] = {
                "option off": "STRIP_OFF",
                "already a rectangle": "RECTANGLE",
                "long sides are straight on the surface": "FOUR_SIDED",
                "laid from its bevel ladder": "STRIP",
            }[instance.suppression_reason.value]
    assert {patch_id: row["type"] for patch_id, row in payload["patch_types"].items()} == expected
    for type_name, layer in PATCH_TYPE_LAYERS.items():
        assert {item["patch_id"] for item in payload["layers"][layer]} == {
            patch_id for patch_id, value in expected.items() if value == type_name
        }


@pytest.mark.parametrize("case", sorted(CASES))
def test_island_layers_equal_the_frame_kinds(case) -> None:
    _context, solve, payload = _run(case)
    frame_by_island = {skeleton.island_id: skeleton.frame for skeleton in solve.skeletons}
    for frame_kind in ("UNFOLDED", "FRAME_FREE", "STRIP", "LADDER"):
        items = payload["layers"][f"Scaffold_Islands_{frame_kind}"]
        assert {item["island_id"] for item in items} == {
            island_id for island_id, frame in frame_by_island.items() if frame == frame_kind
        }
    all_items = [
        item
        for frame_kind in ("UNFOLDED", "FRAME_FREE", "STRIP", "LADDER")
        for item in payload["layers"][f"Scaffold_Islands_{frame_kind}"]
    ]
    assert sorted(patch for item in all_items for patch in item["patch_ids"]) == sorted(
        str(patch_id) for island in solve.assembly.islands for patch_id in island.patch_ids
    )
    assert all(stroke["fill"] for item in all_items for stroke in item["strokes"])


@pytest.mark.parametrize("case", sorted(CASES))
def test_structure_nodes_pins_and_corners_follow_their_records(case) -> None:
    context, solve, payload = _run(case)
    layers = payload["layers"]
    topology = context.topology_snapshot
    relations = context.relation_snapshot

    assert {item["patch_id"] for item in layers["Scaffold_Patches"]} == {str(p) for p in topology.patches}
    assert len(layers["Scaffold_Loops_Boundary"]) == sum(loop.kind.value == "OUTER" for loop in topology.loops.values())
    assert len(layers["Scaffold_Loops_Holes"]) == sum(loop.kind.value != "OUTER" for loop in topology.loops.values())

    expected_nodes = {
        (skeleton.island_id, str(node)) for skeleton in solve.skeletons for node in skeleton.node_by_run_end.values()
    }
    assert {(item["island_id"], item["node_id"]) for item in layers["Scaffold_Skeleton_Nodes"]} == expected_nodes
    assert all(len(item["strokes"]) == 3 for item in layers["Scaffold_Skeleton_Nodes"])

    assert len(layers["Scaffold_Pins"]) == sum(vertex.pinned for vertex in solve.vertices)

    corners = [corner for corner in relations.run_corner_relations if corner.kind.value != "STRAIGHT"]
    corner_ids = {corner.id for corner in corners} | {corner.id for corner in relations.run_bridged_corner_relations}
    assert {item["corner_id"] for item in layers["Scaffold_Patch_Corners"]} == corner_ids
    for item in layers["Scaffold_Patch_Corners"]:
        if item["kind"] == "BRIDGED_RIGHT":
            assert item["category"] == "BRIDGED_RIGHT"
        elif item["kind"] == "RIGHT":
            assert item["category"] == ("RIGHT_CONVEX" if item["interior_angle_sum"] < math.pi else "RIGHT_REFLEX")
        else:
            assert item["category"] == "OTHER"
    assert len(layers["Scaffold_L3_Families"]) == len(relations.patch_chain_directional_evidence)


def test_bridged_right_corner_is_drawn_once_at_its_bridge_run_midpoint() -> None:
    context = run_pass_1_relations(run_pass_0(make_notched_sheet_source(folded=True)))
    payload = build_debug_payload(context, run_skeleton_solve(context), object_name="notched_sheet")
    relations = context.relation_snapshot
    evidence = {e.id: e for e in relations.patch_chain_directional_evidence}
    position = {str(k): v.position for k, v in context.source_snapshot.vertices.items()}
    items = [item for item in payload["layers"]["Scaffold_Patch_Corners"] if item["kind"] == "BRIDGED_RIGHT"]

    assert {item["corner_id"] for item in items} == {corner.id for corner in relations.run_bridged_corner_relations}
    assert len(items) == 4
    for item in items:
        bridge = evidence[item["bridge_run_id"]]
        assert len(item["strokes"]) == 3
        midpoint = [
            (position[str(bridge.start_source_vertex_id)][k] + position[str(bridge.end_source_vertex_id)][k]) / 2.0
            for k in range(3)
        ]
        center = [sum(point[k] for point in item["strokes"][0]["points"]) / 2.0 for k in range(3)]
        # The marker sits on the bridge's displayed polyline (offset inward by a few marker units).
        assert math.dist(center, midpoint) < 0.1


def test_strip_option_moves_the_arch_front_between_strip_layers() -> None:
    _context, solve_on, payload_on = _run("artist_arch_bevel_strips_on")
    _context, _solve_off, payload_off = _run("artist_arch_bevel_strips_off")
    assert payload_on["layers"]["Scaffold_Types_Strip"]
    assert not payload_on["layers"]["Scaffold_Types_StripOff"]
    assert not payload_off["layers"]["Scaffold_Types_Strip"]
    # Layer 4 grades the shape first, so "option off" marks exactly the strips
    # the option accepts; rectangles and four-sided patches keep their layers.
    assert {item["patch_id"] for item in payload_off["layers"]["Scaffold_Types_StripOff"]} == {
        item["patch_id"] for item in payload_on["layers"]["Scaffold_Types_Strip"]
    }
    for layer in ("Scaffold_Types_Rectangle", "Scaffold_Types_FourSided", "Scaffold_Types_Other"):
        assert {item["patch_id"] for item in payload_off["layers"][layer]} == {
            item["patch_id"] for item in payload_on["layers"][layer]
        }
    assert payload_on["layers"]["Scaffold_Islands_STRIP"]
    assert any(skeleton.frame == "STRIP" for skeleton in solve_on.skeletons)


def test_payload_holds_every_layer_and_takes_no_visibility_input() -> None:
    _context, _solve, payload = _run("tube_with_cap")
    assert set(payload["layers"]) == {spec.layer for spec in LAYER_SPECS}
    assert len({spec.layer for spec in LAYER_SPECS}) == len(LAYER_SPECS)
    assert len({spec.prop for spec in LAYER_SPECS}) == len(LAYER_SPECS)
    parameters = inspect.signature(build_debug_payload).parameters
    assert set(parameters) == {"context", "solve", "object_name"}
    assert {spec.group for spec in LAYER_SPECS} == set(GROUPS) == set(LEGENDS)
    defaults = {spec.layer for spec in LAYER_SPECS if spec.default}
    assert defaults == {
        "Scaffold_Patches", "Scaffold_Loops_Boundary", "Scaffold_Loops_Holes", "Scaffold_Chains",
        "Scaffold_Skeleton_Lines", "Scaffold_Skeleton_Nodes", "Scaffold_Seams",
    }
    for items in payload["layers"].values():
        for item in items:
            for stroke in item["strokes"]:
                assert set(stroke) == {"points", "material", "color", "width", "fill"}
                assert len(stroke["color"]) == 4
                assert all(len(point) == 3 for point in stroke["points"])


def test_report_counts_islands_decisions_and_types() -> None:
    _context, solve, payload = _run("artist_walls_004")
    report = payload["report"]
    assert report.splitlines()[0] == "Scaffold debug report: artist_walls_004"
    assert f"islands: {len(solve.assembly.islands)}" in report
    assert f"stitch decisions: {len(solve.assembly.decisions)}" in report
    for (accepted, reason), count in Counter((d.accepted, d.reason) for d in solve.assembly.decisions).items():
        assert f"{'stitched' if accepted else 'cut'}: {reason}: {count}" in report
    assert f"solver diagnostics: {len(solve.diagnostics)}" in report


LADDER_CASES = ("b_ring_s1", "a_cube_s3", "f_border", "d_cyl_s2")


def _bevel_payload(name: str, *, marks: bool = True):
    source = load_source_snapshot(f"scaffold_core/tests/data/bevel_cases/{name}.capture.json")
    if not marks:
        from dataclasses import replace

        source = replace(source, faces={key: replace(face, face_strength=None) for key, face in source.faces.items()})
    context = run_pass_2_features(run_pass_1_relations(run_pass_0(source)), FeatureOptions())
    solve = run_skeleton_solve(context)
    return context, build_debug_payload(context, solve, object_name=name)


def _drawn_reading_index(context) -> dict[str, int]:
    """Relation id -> the reading the ladder layers must draw: Layer 4's choice for a bevel strip, else 0."""

    chosen = {
        str(record.patch_id): record.reading_index
        for record in context.feature_snapshot.bevels
        if record.kind.value == "BEVEL_STRIP" and record.status.value == "ACCEPTED" and record.reading_index is not None
    }
    return {
        record.id: chosen.get(str(record.patch_id), 0)
        for record in context.relation_snapshot.patch_quad_ladder_relations
    }


@pytest.mark.parametrize("name", LADDER_CASES)
def test_ladder_layers_draw_the_chosen_bevel_reading_else_the_first(name) -> None:
    context, payload = _bevel_payload(name)
    relations = {record.id: record for record in context.relation_snapshot.patch_quad_ladder_relations}
    assert relations
    drawn = _drawn_reading_index(context)
    # Every case here has bevel strips; on the cube some of them are read the second way.
    assert any(index != 0 for index in drawn.values()) or name != "a_cube_s3"
    records = {record_id: SimpleNamespace(readings=(relation.readings[drawn[record_id]],))
               for record_id, relation in relations.items()}
    layers = payload["layers"]
    for layer in ("Scaffold_Ladder_Rails", "Scaffold_Ladder_Ends", "Scaffold_Ladder_Columns"):
        assert all(item["reading_index"] == drawn[item["relation_id"]] for item in layers[layer])
    rails = layers["Scaffold_Ladder_Rails"]
    assert sorted((item["relation_id"], item["rail"]) for item in rails) == sorted(
        (record_id, rail) for record_id in records for rail in ("A", "B")
    )
    for item in rails:
        reading = records[item["relation_id"]].readings[0]
        edges = reading.rail_a_source_edge_ids if item["rail"] == "A" else reading.rail_b_source_edge_ids
        assert item["source_edge_ids"] == [str(edge) for edge in edges]
        (stroke,) = item["strokes"]
        assert len(stroke["points"]) == len(edges) + 1
        assert stroke["color"] == list(overlay_ladders.LADDER_RAIL_COLORS[item["rail"]])
    open_ids = {record_id for record_id, record in records.items() if not record.readings[0].is_closed}
    ends = layers["Scaffold_Ladder_Ends"]
    assert sorted((item["relation_id"], item["end"]) for item in ends) == sorted(
        (record_id, end) for record_id in open_ids for end in ("A", "B")
    )
    for item in ends:
        assert len(item["strokes"][0]["points"]) == records[item["relation_id"]].readings[0].faces_per_column + 1
    columns = {item["relation_id"]: item for item in layers["Scaffold_Ladder_Columns"]}
    assert set(columns) == set(records)
    for record_id, item in columns.items():
        reading = records[record_id].readings[0]
        inner = len(reading.columns) if reading.is_closed else len(reading.columns) - 1
        assert len(item["strokes"]) == inner
        assert all(stroke["width"] == overlay_ladders.LADDER_COLUMN_WIDTH for stroke in item["strokes"])
    counts = payload["ladder_counts"]
    assert counts["ladder_patches"] == len(records)
    assert f"ladder patches: {len(records)} (closed {counts['closed']}" in payload["report"]


@pytest.mark.parametrize("name", LADDER_CASES)
def test_source_face_mark_layer_fills_each_marked_face_once_by_class(name) -> None:
    context, payload = _bevel_payload(name)
    expected = Counter(
        face.face_strength.value for face in context.source_snapshot.faces.values() if face.face_strength is not None
    )
    items = payload["layers"]["Scaffold_Source_Face_Strength"]
    assert {item["face_strength"]: len(item["face_ids"]) for item in items} == dict(expected)
    assert payload["face_strength_counts"] == dict(expected)
    for item in items:
        assert {tuple(stroke["color"]) for stroke in item["strokes"]} == {
            tuple(overlay_ladders.FACE_STRENGTH_COLORS[item["face_strength"]])
        }
        assert all(stroke["fill"] for stroke in item["strokes"])
    assert "faces by source face mark: weak=" in payload["report"]


@pytest.mark.parametrize("name, marks", [(name, True) for name in LADDER_CASES + ("u_rounded_wall_noise_top", "h_rect_s2_tri")]
                         + [("u_rounded_wall_noise_top", False), ("a_cube_s3", False)])
def test_bevel_layers_fill_each_bevel_record_once_by_kind_and_source(name, marks) -> None:
    context, payload = _bevel_payload(name, marks=marks)
    bevels = context.feature_snapshot.bevels
    assert bevels
    layers = payload["layers"]
    expected_group = {
        str(record.patch_id): (
            "SUPPRESSED" if record.status.value != "ACCEPTED"
            else record.kind.value + ("" if record.source.value == "SOURCE_MARK" else "_STRUCTURE")
        )
        for record in bevels
    }
    expected = {
        layer: sorted(patch_id for patch_id, group_name in expected_group.items() if group_name == group)
        for group, layer in overlay_ladders.BEVEL_LAYERS.items()
    }
    if not marks:  # records by structure never land on the mark layers
        assert layers["Scaffold_Bevel_Strip"] == layers["Scaffold_Bevel_Junction"] == []
        assert layers["Scaffold_Bevel_Strip_Structure"] and layers["Scaffold_Bevel_Junction_Structure"]
    for group, layer in overlay_ladders.BEVEL_LAYERS.items():
        assert sorted(item["patch_id"] for item in layers[layer]) == expected[layer]
        for item in layers[layer]:
            faces = context.topology_snapshot.patches[item["patch_id"]].source_face_ids
            assert item["strokes"] and all(stroke["fill"] for stroke in item["strokes"])
            assert len(item["strokes"]) >= len(faces)
            assert {tuple(stroke["color"]) for stroke in item["strokes"]} == {tuple(overlay_ladders.BEVEL_COLORS[group])}
    counts = payload["bevel_counts"]
    strips = [r for r in bevels if r.kind.value == "BEVEL_STRIP" and r.status.value == "ACCEPTED"]
    assert sum(counts["strips_by_source"].values()) == len(strips)
    assert counts["unresolved"] == sum(1 for r in strips if r.reading_index is None)
    assert ("bevel strips: source_mark=" if marks else "bevel strips: structure=") in payload["report"]
    assert f"unresolved {counts['unresolved']}" in payload["report"]


def test_bevel_strips_laid_from_their_ladder_have_their_island_layer_and_report_line() -> None:
    _context, solve, payload = _run("rounded_wall_bevel_marks")
    ladder_islands = {skeleton.island_id for skeleton in solve.skeletons if skeleton.frame == "LADDER"}
    assert len(ladder_islands) == 9
    assert {item["island_id"] for item in payload["layers"]["Scaffold_Islands_LADDER"]} == ladder_islands
    assert payload["bevel_ladders"] == {"constraints": 9, "islands": 9, "not_laid": []}
    assert "bevel strips laid from their ladder: 9 of 9 constraints" in payload["report"]
    # A closed ring by mark gets no constraint and is named with its reason.
    ring = load_source_snapshot("scaffold_core/tests/data/bevel_cases/b_ring_s1.capture.json")
    context = run_pass_2_features(run_pass_1_relations(run_pass_0(ring)))
    ring_payload = build_debug_payload(context, run_skeleton_solve(context), object_name="ring")
    assert ring_payload["bevel_ladders"]["not_laid"] == [("patch:seed:f8", "the reading is a closed ring")]
    assert "  not laid: patch:seed:f8: the reading is a closed ring" in ring_payload["report"]


def test_bevel_legend_says_structural_records_are_not_confirmed() -> None:
    legend = " ".join(LEGENDS["Bevels"])
    assert "found by mesh structure, not confirmed by a mark" in legend
    assert "suppressed record" in legend


def test_bevel_layers_show_a_bevel_patch_that_is_not_isolated() -> None:
    from dataclasses import replace

    from scaffold_core.layer_0_source.marks import SourceFaceStrength

    # One face of a many-face main surface marked as a bevel face: that patch is shown red.
    source = load_source_snapshot("scaffold_core/tests/data/bevel_cases/u_rounded_wall_noise_top.capture.json")
    topology = run_pass_0(source).topology_snapshot
    patch = next(patch for patch in topology.patches.values() if len(patch.source_face_ids) > 1
                 and source.faces[patch.source_face_ids[0]].face_strength is SourceFaceStrength.STRONG)
    faces = dict(source.faces)
    face_id = patch.source_face_ids[0]
    faces[face_id] = replace(faces[face_id], face_strength=SourceFaceStrength.MEDIUM)
    context = run_pass_2_features(run_pass_1_relations(run_pass_0(replace(source, faces=faces))), FeatureOptions())
    payload = build_debug_payload(context, run_skeleton_solve(context), object_name="u_rounded_wall_noise_top")
    (item,) = payload["layers"]["Scaffold_Bevel_Not_Isolated"]
    assert item["patch_id"] == str(patch.id)
    assert item["reason"] == "bevel faces not isolated by seams"
    assert "bevel-marked, not isolated: bevel faces not isolated by seams=1" in payload["report"]


def test_unmarked_meshes_without_bevels_draw_no_bevel_layer() -> None:
    _context, _solve, payload = _run("artist_walls_004")
    for layer in overlay_ladders.BEVEL_LAYERS.values():
        assert payload["layers"][layer] == []
    assert "bevel strips" not in payload["report"]


def test_unmarked_meshes_draw_no_source_face_mark() -> None:
    _context, _solve, payload = _run("artist_walls_004")
    assert payload["layers"]["Scaffold_Source_Face_Strength"] == []
    assert "faces by source face mark" not in payload["report"]


def test_no_frame_or_world_vocabulary_in_the_payload_module() -> None:
    text = inspect.getsource(overlay_v2)
    for word in ("WALL", "FLOOR", "SLOPE", "WORLD_UP", "H_FRAME", "V_FRAME"):
        assert word not in text


# --------------------------------------------------------------------------- stroke positions


def _sub(a, b):
    return [float(a[k]) - float(b[k]) for k in range(3)]


def _dot(a, b):
    return sum(float(a[k]) * float(b[k]) for k in range(3))


def _cross3(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _mid(a, b):
    return [(float(a[k]) + float(b[k])) / 2.0 for k in range(3)]


def _norm(a):
    return math.sqrt(_dot(a, a))


def _newell(points):
    total = [0.0, 0.0, 0.0]
    for current, following in zip(points, points[1:] + points[:1]):
        total[0] += (current[1] - following[1]) * (current[2] + following[2])
        total[1] += (current[2] - following[2]) * (current[0] + following[0])
        total[2] += (current[0] - following[0]) * (current[1] + following[1])
    return total


def _faces_by_patch_edge(context):
    """(patch, {u, v}) -> [(face id, the face's own cycle)], straight from the source mesh."""

    source = context.source_snapshot
    rows: dict[tuple[str, frozenset], list] = {}
    for patch_id, patch in context.topology_snapshot.patches.items():
        for face_id in patch.source_face_ids:
            cycle = [str(vertex_id) for vertex_id in source.faces[face_id].vertex_ids]
            for index, vertex in enumerate(cycle):
                key = (str(patch_id), frozenset((vertex, cycle[(index + 1) % len(cycle)])))
                rows.setdefault(key, []).append((str(face_id), cycle))
    return rows


def _face_inward(context, cycle, u, v):
    """Into the face across its edge u-v, by the face's own winding."""

    positions = {str(key): vertex.position for key, vertex in context.source_snapshot.vertices.items()}
    index = cycle.index(u)
    a, b = (u, v) if cycle[(index + 1) % len(cycle)] == v else (v, u)
    normal = _newell([positions[vertex] for vertex in cycle])
    return _cross3(normal, _sub(positions[b], positions[a]))


SIDE_CASES = ("tube_with_cap", "extruded_cross", "artist_cyl32")


@pytest.mark.parametrize("case", SIDE_CASES)
def test_chain_strokes_lie_beside_their_edges_on_the_owning_face(case) -> None:
    context, _solve, payload = _run(case)
    geometry = context.geometry_facts
    evidence_by_id = {e.id: e for e in context.relation_snapshot.patch_chain_directional_evidence}
    faces = _faces_by_patch_edge(context)
    unit = payload["marker_unit"]
    checked = 0
    for item in payload["layers"]["Scaffold_Chains"]:
        if item["run_id"] is None:
            continue
        run = evidence_by_id[item["run_id"]]
        by_index = {segment.segment_index: segment for segment in geometry.chain_facts[run.parent_chain_id].segments}
        segments = [by_index[index] for index in run.segment_indices]
        points = item["strokes"][0]["points"]
        assert len(points) == len(segments) + 1
        for first, second in zip(points, points[1:]):
            middle = _mid(first, second)
            segment = min(segments, key=lambda s: _norm(_sub(middle, _mid(s.start_position, s.end_position))))
            base = _mid(segment.start_position, segment.end_position)
            assert _norm(_sub(middle, base)) < 0.05 * segment.length + 0.05 * unit
            u, v = str(segment.start_source_vertex_id), str(segment.end_source_vertex_id)
            owners = faces[(str(run.patch_id), frozenset((u, v)))]
            if len(owners) != 1:
                continue  # SEAM_SELF edge: both faces are in this patch (own test below)
            assert _dot(_sub(middle, base), _face_inward(context, owners[0][1], u, v)) > 0.0
            checked += 1
    assert checked > 0

    points_by_use: dict[str, set] = {}
    for item in payload["layers"]["Scaffold_Chains"]:
        points_by_use.setdefault(item["patch_chain_id"], set()).update(
            tuple(round(value, 9) for value in point) for point in item["strokes"][0]["points"]
        )
    uses_by_chain: dict[str, list[str]] = {}
    for patch_chain in context.topology_snapshot.patch_chains.values():
        uses_by_chain.setdefault(str(patch_chain.chain_id), []).append(str(patch_chain.id))
    shared = [uses for uses in uses_by_chain.values() if len(uses) == 2]
    assert shared
    for first, second in shared:
        assert not points_by_use[first] & points_by_use[second]


def test_both_uses_of_a_self_seam_lie_on_their_two_different_faces() -> None:
    from scaffold_core.tests.fixtures.cylinder_tube import make_cylinder_tube_without_caps_with_one_seam_source

    context = run_pass_2_features(run_pass_1_relations(run_pass_0(make_cylinder_tube_without_caps_with_one_seam_source())))
    payload = build_debug_payload(context, run_skeleton_solve(context))
    seam_uses = {
        str(pc.id): pc for pc in context.topology_snapshot.patch_chains.values() if str(pc.chain_id) == "chain:e_v0"
    }
    assert len(seam_uses) == 2
    faces = _faces_by_patch_edge(context)
    segments = context.geometry_facts.chain_facts["chain:e_v0"].segments
    face_by_use: dict[str, set[str]] = {}
    for item in payload["layers"]["Scaffold_Chains"]:
        if item["patch_chain_id"] not in seam_uses:
            continue
        points = item["strokes"][0]["points"]
        for first, second in zip(points, points[1:]):
            middle = _mid(first, second)
            segment = min(segments, key=lambda s: _norm(_sub(middle, _mid(s.start_position, s.end_position))))
            base = _mid(segment.start_position, segment.end_position)
            u, v = str(segment.start_source_vertex_id), str(segment.end_source_vertex_id)
            owners = faces[(item["patch_id"], frozenset((u, v)))]
            assert len(owners) == 2
            sides = [face_id for face_id, cycle in owners if _dot(_sub(middle, base), _face_inward(context, cycle, u, v)) > 0.0]
            assert len(sides) == 1
            face_by_use.setdefault(item["patch_chain_id"], set()).update(sides)
    first, second = face_by_use.values()
    assert len(first) == len(second) == 1 and first != second


def test_both_axis_colours_occur_on_the_cylinder_capture() -> None:
    _context, _solve, payload = _run("artist_cyl32")
    colours = {tuple(item["strokes"][0]["color"]) for item in payload["layers"]["Scaffold_Chains"]}
    assert tuple(ROLE_RGBA["AXIS_A"]) in colours and tuple(ROLE_RGBA["AXIS_B"]) in colours


def test_holes_are_the_inner_loops_with_every_loop_vertex() -> None:
    context, _solve, payload = _run("artist_walls_007")
    topology = context.topology_snapshot
    inner = {str(loop_id): loop for loop_id, loop in topology.loops.items() if loop.kind.value != "OUTER"}
    assert len(inner) == 6
    items = payload["layers"]["Scaffold_Loops_Holes"]
    assert {item["loop_id"] for item in items} == set(inner)
    for item in items:
        loop = inner[item["loop_id"]]
        edges = sum(
            len(context.geometry_facts.chain_facts[topology.patch_chains[use].chain_id].segments)
            for use in loop.patch_chain_ids
        )
        assert len(item["strokes"][0]["points"]) == edges + 1  # closed: first point repeated


@pytest.mark.parametrize("case", ("beveled_corner", "tube_with_cap", "artist_walls_004"))
def test_seams_lift_along_both_patch_normals(case) -> None:
    context, _solve, payload = _run(case)
    sums: dict[tuple[str, str], list[float]] = {}
    for fan in context.geometry_facts.local_face_fan_facts.values():
        total = sums.setdefault((str(fan.patch_id), str(fan.source_vertex_id)), [0.0, 0.0, 0.0])
        for k in range(3):
            total[k] += float(fan.normal[k])
    normal = {key: [value / _norm(total) for value in total] for key, total in sums.items() if _norm(total) > 0}
    unit = payload["marker_unit"]
    checked = 0
    for item in payload["layers"]["Scaffold_Seams"]:
        if item["first_patch_id"] == item["second_patch_id"]:
            continue
        segments = context.geometry_facts.chain_facts[item["chain_id"]].segments
        vertices = {str(s.start_source_vertex_id): s.start_position for s in segments}
        vertices.update({str(s.end_source_vertex_id): s.end_position for s in segments})
        for stroke in item["strokes"]:
            for point in stroke["points"]:
                vertex, position = min(vertices.items(), key=lambda row: _norm(_sub(point, row[1])))
                lift = _sub(point, position)
                if _norm(lift) > 0.05 * unit:
                    continue  # a dash point between vertices
                first = normal.get((item["first_patch_id"], vertex))
                second = normal.get((item["second_patch_id"], vertex))
                if first is None or second is None:
                    continue
                assert _dot(lift, first) > 0.0 and _dot(lift, second) > 0.0
                assert abs(_dot(lift, first) - _dot(lift, second)) < 1e-9 + 1e-6 * unit
                checked += 1
    assert checked > 0


@pytest.mark.parametrize("case", ("artist_cyl32", "extruded_cross"))
def test_families_share_one_colour_and_differ_between_families(case) -> None:
    context, _solve, payload = _run(case)
    relations = context.relation_snapshot
    family_of = {
        member: family.id for family in relations.connected_direction_families for member in family.member_directional_evidence_ids
    }
    colours: dict[str, set] = {}
    for item in payload["layers"]["Scaffold_L3_Families"]:
        assert item["family_id"] == family_of.get(item["run_id"])
        if item["family_id"] is not None:
            colours.setdefault(item["family_id"], set()).add(tuple(item["strokes"][0]["color"]))
    assert len(colours) >= 2
    assert all(len(values) == 1 for values in colours.values())
    assert len({next(iter(values)) for values in colours.values()}) == len(colours)


@pytest.mark.parametrize("case", ("artist_cyl32", "beveled_corner"))
def test_junction_markers_one_per_node_and_endpoint_junction(case) -> None:
    context, _solve, payload = _run(case)
    relations = context.relation_snapshot
    items = payload["layers"]["Scaffold_L3_Junctions"]
    assert sorted((item["kind"], item["id"]) for item in items) == sorted(
        [("SCAFFOLD_NODE", node.id) for node in relations.scaffold_nodes]
        + [("RUN_ENDPOINT_JUNCTION", junction.id) for junction in relations.run_endpoint_junctions]
    )
    for item in items:
        segments = [_sub(stroke["points"][1], stroke["points"][0]) for stroke in item["strokes"]]
        if item["kind"] == "SCAFFOLD_NODE":  # a 3D "+": one segment along each axis
            assert len(segments) == 3
            assert sorted(max(range(3), key=lambda k: abs(segment[k])) for segment in segments) == [0, 1, 2]
            assert all(sum(1 for value in segment if abs(value) > 1e-12) == 1 for segment in segments)
        else:  # a 3D "*": four body diagonals
            assert len(segments) == 4
            assert all(sum(1 for value in segment if abs(value) > 1e-12) == 3 for segment in segments)
