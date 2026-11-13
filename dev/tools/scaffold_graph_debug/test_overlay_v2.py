"""Headless checks for the debugger payload: Sides layer, offsets, snapshot capture."""

from __future__ import annotations

import importlib
import json

from dev.tools.scaffold_graph_debug.overlay_v2 import build_debug_payload
from dev.tools.scaffold_graph_debug.rail_offsets import RAIL_NORMAL_HOVER_FACTOR, RAIL_OFFSET_FACTOR
from dev.tools.scaffold_graph_debug.snapshot_io import dump_source_snapshot, load_source_snapshot
from scaffold_core.layer_4_features.model import FeatureOptions
from scaffold_core.layer_5_runtime.pins import run_skeleton_solve
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations, run_pass_2_features


def _context_payload(source):
    context = run_pass_2_features(run_pass_1_relations(run_pass_0(source)), FeatureOptions())
    return context, build_debug_payload(context, run_skeleton_solve(context))


def test_pure_overlay_modules_import_without_blender() -> None:
    importlib.import_module("dev.tools.scaffold_graph_debug")
    build_stamp = importlib.import_module("dev.tools.scaffold_graph_debug.build_stamp")
    importlib.import_module("dev.tools.scaffold_graph_debug.colors")
    importlib.import_module("dev.tools.scaffold_graph_debug.overlay_v2")
    importlib.import_module("dev.tools.scaffold_graph_debug.rail_offsets")
    assert RAIL_OFFSET_FACTOR > 0.0
    assert RAIL_NORMAL_HOVER_FACTOR > 0.0
    assert build_stamp.OVERLAY_VERSION == "overlay-v3"


def test_winding_rule_puts_each_edge_direction_on_its_own_face() -> None:
    from types import SimpleNamespace

    from dev.tools.scaffold_graph_debug.rail_offsets import build_side_index, edge_side

    # Two unit squares sharing edge b-c, both wound counter-clockwise seen from +z.
    positions = {"a": (0, 0, 0), "b": (1, 0, 0), "c": (1, 1, 0), "d": (0, 1, 0), "e": (2, 0, 0), "f": (2, 1, 0)}
    source = SimpleNamespace(
        vertices={key: SimpleNamespace(position=value) for key, value in positions.items()},
        faces={
            "left": SimpleNamespace(vertex_ids=("a", "b", "c", "d")),
            "right": SimpleNamespace(vertex_ids=("b", "e", "f", "c")),
        },
    )
    topology = SimpleNamespace(patches={"p": SimpleNamespace(source_face_ids=("left", "right"))})
    index = build_side_index(topology, source, {})

    up = edge_side(index, "p", "b", "c")  # left face walks b -> c
    down = edge_side(index, "p", "c", "b")  # right face walks c -> b
    assert (up.face_id, down.face_id) == ("left", "right")
    assert up.inward[0] < -0.99 and down.inward[0] > 0.99
    assert not up.fallback and not down.fallback
    assert up.normal[2] > 0.99

    outer = edge_side(index, "p", "b", "a")  # no face walks b -> a: old centroid rule, reported
    assert outer.fallback and outer.face_id == "left" and outer.inward[1] > 0.99


def test_snapshot_capture_records_empty_selection_fallback(tmp_path) -> None:
    source = load_source_snapshot("scaffold_core/tests/data/artist_cyl32.json")
    path = dump_source_snapshot(source, tmp_path / "snapshot.json")
    payload = json.loads(path.read_text())

    assert payload["selected_face_ids"] == []
    assert payload["selection_fallback_used"] is True
    assert "empty selected_face_ids" in payload["selection_fallback_reason"]


def test_face_strength_mark_round_trips_through_the_capture(tmp_path) -> None:
    source = load_source_snapshot("scaffold_core/tests/data/bevel_cases/a_cube_s3.capture.json")
    counts: dict[str, int] = {}
    for face in source.faces.values():
        counts[face.face_strength.value] = counts.get(face.face_strength.value, 0) + 1
    assert counts == {"STRONG": 6, "MEDIUM": 36, "WEAK": 56}

    again = load_source_snapshot(dump_source_snapshot(source, tmp_path / "marked.json"))
    assert again.faces == source.faces
    assert json.loads((tmp_path / "marked.json").read_text())["format"] == "scaffold_source_snapshot_v1"


def test_captures_without_the_mark_load_unmarked_and_dump_unchanged(tmp_path) -> None:
    path = "scaffold_core/tests/data/artist_walls_006.json"
    source = load_source_snapshot(path)
    assert all(face.face_strength is None for face in source.faces.values())
    dumped = json.loads(dump_source_snapshot(source, tmp_path / "plain.json").read_text())
    assert "face_strength" not in dumped
    assert dumped == {key: value for key, value in json.loads(open(path, encoding="utf-8").read()).items()}


def test_artist_arch_bevel_chain_shape_pieces_per_patch_side() -> None:
    context, payload = _context_payload(load_source_snapshot("scaffold_core/tests/data/artist_arch_bevel.json"))
    records = context.relation_snapshot.patch_chain_shape_relations
    pieces = payload["chain_shape_pieces"]
    assert pieces is payload["layers"]["Scaffold_Patch_Sides"]
    assert len(pieces) == len(records) > 0
    counts = payload["counts"]["chain_shape"]
    assert counts["chain_shape_undrawn_count"] == 0
    for kind in ("SURFACE_LINE", "SURFACE_CURVE", "UNRESOLVED"):
        assert counts[f"chain_shape_{kind.lower()}_count"] == sum(
            record.kind.value == kind for record in records
        )
    assert all(len(piece["polyline"]) == piece["segment_count"] + 1 for piece in pieces)
    assert len({tuple(piece["color"]) for piece in pieces}) == len({piece["kind"] for piece in pieces})
    assert all(piece["strokes"][0]["points"] == piece["polyline"] for piece in pieces)

    front_curves = sorted(
        (piece for piece in pieces if piece["patch_id"] == "patch:seed:f16" and piece["kind"] == "SURFACE_CURVE"),
        key=lambda piece: -piece["segment_count"],
    )
    assert [piece["segment_count"] for piece in front_curves] == [16, 11]
    front_lines = [
        piece for piece in pieces if piece["patch_id"] == "patch:seed:f16" and piece["kind"] == "SURFACE_LINE"
    ]
    assert len(front_lines) == 2
    assert all(piece["surface_turn_max_deg"] > 5.0 for piece in front_curves)

    for front, rim_patch_id in zip(front_curves, ("patch:seed:f0", "patch:seed:f85")):
        rim_sides = [
            piece
            for piece in pieces
            if piece["patch_id"] == rim_patch_id and piece["chain_id"] == front["chain_id"]
        ]
        assert len(rim_sides) == 1
        rim = rim_sides[0]
        assert rim["kind"] == "SURFACE_LINE"
        assert rim["kind"] != front["kind"]
        assert rim["segment_count"] == front["segment_count"]
        assert rim["surface_turn_max_deg"] < 0.01
        assert not rim["unoffset"] and not front["unoffset"]
        assert len(rim["polyline"]) == len(front["polyline"])
        # Each side follows its own use, and the two uses of a shared chain run
        # opposite ways: pair the points by position along the chain.
        distances = min(
            (
                [_distance(first, second) for first, second in zip(rim["polyline"], ordered)]
                for ordered in (front["polyline"], list(reversed(front["polyline"])))
            ),
            key=max,
        )
        assert all(distance > 1e-6 for distance in distances)
        assert max(distances) < 0.1


def test_self_seam_chain_shape_pieces_get_one_polyline_per_side() -> None:
    from scaffold_core.tests.fixtures.cylinder_tube import (
        make_cylinder_tube_without_caps_with_one_seam_source,
    )

    _context, payload = _context_payload(make_cylinder_tube_without_caps_with_one_seam_source())
    seam_sides = [piece for piece in payload["chain_shape_pieces"] if piece["chain_id"] == "chain:e_v0"]
    assert len(seam_sides) == 2
    assert len({piece["patch_chain_id"] for piece in seam_sides}) == 2
    assert not any(piece["unoffset"] for piece in seam_sides)
    first, second = sorted(seam_sides, key=lambda piece: piece["patch_chain_id"])
    # Both sides of the seam lie in one patch: the second side flips its offset.
    first_points = sorted(first["polyline"], key=lambda point: point[2])
    second_points = sorted(second["polyline"], key=lambda point: point[2])
    assert all(_distance(a, b) > 1e-6 for a, b in zip(first_points, second_points))


def _distance(first, second) -> float:
    return sum((float(first[index]) - float(second[index])) ** 2 for index in range(3)) ** 0.5
