"""
Layer: tests

Rules:
- PatchChainShapeRelation evidence tests only (chain shape Stage A; its one reader is Stage B).
- Every "not one line" case is paired with a "still one line" case.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

from dataclasses import replace
from math import degrees, isclose, pi, radians, sin
from pathlib import Path

import pytest

from scaffold_core.ids import (
    BoundaryLoopId,
    ChainId,
    PatchChainId,
    PatchId,
    SourceEdgeId,
    SourceFaceId,
    SourceVertexId,
    SurfaceModelId,
    VertexId,
)
from scaffold_core.layer_1_topology.model import PatchChain, SurfaceModel, Vertex
from scaffold_core.layer_2_geometry.facts import (
    ChainGeometryFacts,
    ChainSegmentGeometryFacts,
    GeometryFactSnapshot,
    LocalFaceFanGeometryFacts,
    PatchChainGeometryFacts,
)
from scaffold_core.layer_3_relations import build as relations_build
from scaffold_core.layer_3_relations import chain_refinement
from scaffold_core.layer_3_relations.model import PatchChainShapeKind
from scaffold_core.layer_3_relations.patch_chain_shape import (
    LAW_MISMATCH_CODE,
    UNRESOLVED_OCCURRENCE_CODE,
    build_patch_chain_shape_relations,
)
from scaffold_core.layer_5_runtime.pins import run_skeleton_solve
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
from scaffold_core.tests.fixtures.beveled_wall_corner import make_beveled_wall_corner_source
from scaffold_core.tests.fixtures.capped_prism import make_capped_decagon_prism_odd_strips_source
from scaffold_core.tests.fixtures.chain_shape_surfaces import (
    make_cone_frustum_band_source,
    make_single_pentagon_source,
    make_stepped_seam_source,
)
from scaffold_core.tests.fixtures.closed_shared_loop import make_closed_shared_boundary_loop_source
from scaffold_core.tests.fixtures.cylinder_tube import (
    make_cylinder_tube_without_caps_with_one_seam_source,
    make_cylinder_tube_without_caps_with_two_seams_source,
)
from scaffold_core.tests.fixtures.extruded_cross import make_extruded_cross_source
from scaffold_core.tests.fixtures.l_corridor_tunnel import make_l_corridor_tunnel_seamed_folds_source
from scaffold_core.tests.fixtures.l_shape import make_two_quad_l_source_with_seam_on_shared_edge
from scaffold_core.tests.fixtures.single_patch import make_single_quad_source
from scaffold_core.tests.fixtures.tube_with_cap import make_tube_with_cap_source
from scaffold_core.tests.test_layer_5_runtime import DATA, _load_capture

LINE = PatchChainShapeKind.SURFACE_LINE
CURVE = PatchChainShapeKind.SURFACE_CURVE
UNRESOLVED = PatchChainShapeKind.UNRESOLVED


def _relations(source):
    return run_pass_1_relations(run_pass_0(source)).relation_snapshot


def _pieces(relations, patch_chain_id: str):
    return sorted(
        (piece for piece in relations.patch_chain_shape_relations if str(piece.patch_chain_id) == patch_chain_id),
        key=lambda piece: piece.segment_indices,
    )


def _uses_of_chain(relations, chain_id: str) -> dict[str, list]:
    uses: dict[str, list] = {}
    for piece in relations.patch_chain_shape_relations:
        if str(piece.chain_id) == chain_id:
            uses.setdefault(str(piece.patch_id), []).append(piece)
    return {patch_id: sorted(pieces, key=lambda piece: piece.segment_indices) for patch_id, pieces in uses.items()}


def _turns_degrees(piece) -> list[float]:
    return [abs(degrees(turn)) for turn in piece.evidence[0].data["surface_turns"]]


def _shape_codes(relations) -> list[str]:
    return [
        diagnostic.code
        for diagnostic in relations.diagnostics
        if diagnostic.code in (LAW_MISMATCH_CODE, UNRESOLVED_OCCURRENCE_CODE)
    ]


# --- arch with bevels (artist capture) ---------------------------------------------------

ARCH_RIM_ARCS = {
    "patch_chain:patch:seed:f0:0:0": 16,
    "patch_chain:patch:seed:f0:0:2": 16,
    "patch_chain:patch:seed:f85:0:0": 11,
    "patch_chain:patch:seed:f85:0:2": 11,
}
ARCH_FRONT_ARCS = {
    "patch_chain:patch:seed:f16:0:1": (16, 11.2, 11.3),
    "patch_chain:patch:seed:f16:0:3": (11, 11.2, 18.8),
}
ARCH_FOOT_FRONT = ("patch_chain:patch:seed:f16:0:0", "patch_chain:patch:seed:f16:0:2")
ARCH_FOOT_CAPS = ("patch_chain:patch:seed:f123:0:3", "patch_chain:patch:seed:f125:0:3")


@pytest.fixture(scope="module")
def arch_relations():
    return _relations(_load_capture("artist_arch_bevel.json"))


def test_arch_rim_arcs_are_one_surface_line_per_rim_side(arch_relations) -> None:
    for patch_chain_id, segment_count in ARCH_RIM_ARCS.items():
        (piece,) = _pieces(arch_relations, patch_chain_id)
        assert piece.kind is LINE
        assert piece.segment_indices == tuple(range(segment_count))
        assert piece.surface_turn_max < 1.0e-3
        assert piece.tilt_max < 1.0e-3  # the rim normal lies in the arc plane
        assert piece.is_planar


def test_arch_front_face_arcs_are_one_surface_curve_each(arch_relations) -> None:
    # Paired with the rim test: the same two arcs, judged on the front face.
    for patch_chain_id, (segment_count, low, high) in ARCH_FRONT_ARCS.items():
        (piece,) = _pieces(arch_relations, patch_chain_id)
        assert piece.kind is CURVE
        assert piece.segment_indices == tuple(range(segment_count))
        turns = _turns_degrees(piece)
        assert low - 0.1 <= min(turns) and max(turns) <= high + 0.1
        assert abs(degrees(piece.tilt_min) - 90.0) < 0.5
        assert piece.is_planar


def test_arch_foot_chain_is_a_line_on_the_front_and_cornered_on_the_cap(arch_relations) -> None:
    for patch_chain_id in ARCH_FOOT_FRONT:
        (piece,) = _pieces(arch_relations, patch_chain_id)
        assert piece.kind is LINE
        assert len(piece.segment_indices) == 5
        assert 0.0 <= degrees(piece.tilt_min) and degrees(piece.tilt_max) < 9.0
    for patch_chain_id in ARCH_FOOT_CAPS:
        pieces = _pieces(arch_relations, patch_chain_id)
        # The zigzag steps by right angles on the cap: five single-segment pieces.
        assert [piece.segment_indices for piece in pieces] == [(0,), (1,), (2,), (3,), (4,)]
        assert all(piece.kind is LINE for piece in pieces)


def test_arch_has_no_unresolved_piece_and_no_law_mismatch(arch_relations) -> None:
    assert all(piece.kind is not UNRESOLVED for piece in arch_relations.patch_chain_shape_relations)
    assert _shape_codes(arch_relations) == []
    assert max(piece.law_error_max for piece in arch_relations.patch_chain_shape_relations) < 0.06


# --- canonical fixtures -------------------------------------------------------------------

def test_cylinder_tube_rims_are_surface_lines_for_the_band() -> None:
    relations = _relations(make_cylinder_tube_without_caps_with_one_seam_source())

    for chain_id in ("chain:e_b0:e_b1:e_b2:e_b3", "chain:e_t3:e_t2:e_t1:e_t0"):
        (pieces,) = _uses_of_chain(relations, chain_id).values()
        (piece,) = pieces
        assert piece.kind is LINE
        assert piece.segment_indices == (0, 1, 2, 3)


def test_tube_with_cap_rim_is_a_line_for_the_side_and_cornered_on_the_square_cap() -> None:
    uses = _uses_of_chain(_relations(make_tube_with_cap_source()), "chain:e_t3:e_t2:e_t1:e_t0")

    (side,) = uses["patch:seed:f0"]
    assert side.kind is LINE and side.segment_indices == (0, 1, 2, 3)
    # Four sides turn 90 degrees per vertex on the cap: corners, not a curve.
    assert [piece.segment_indices for piece in uses["patch:seed:f_cap"]] == [(0,), (1,), (2,), (3,)]


def test_decagon_cap_rim_is_a_curve_on_the_cap_and_a_line_on_the_side() -> None:
    uses = _uses_of_chain(_relations(make_capped_decagon_prism_odd_strips_source()), "chain:e_t4:e_t3:e_t2:e_t1:e_t0")

    (side,) = uses["patch:seed:f0"]
    (cap,) = uses["patch:seed:f_cap_top"]
    assert side.kind is LINE
    assert cap.kind is CURVE
    assert cap.segment_indices == (0, 1, 2, 3, 4)
    assert all(isclose(turn, 36.0, abs_tol=1.0e-6) for turn in _turns_degrees(cap))


@pytest.mark.parametrize(("sides", "expected_cap_pieces"), ((8, 8), (9, 1), (12, 1)))
def test_polygon_cap_is_cornered_at_eight_sides_and_curved_from_nine(sides: int, expected_cap_pieces: int) -> None:
    relations = _relations(make_cone_frustum_band_source(sides=sides, top_radius=2.0, capped=True))

    cap_pieces = [piece for piece in relations.patch_chain_shape_relations if str(piece.patch_id) == "patch:seed:f_cap"]
    assert len(cap_pieces) == expected_cap_pieces
    expected_kind = LINE if sides == 8 else CURVE
    assert all(piece.kind is expected_kind for piece in cap_pieces)
    band_rim = [
        piece
        for piece in relations.patch_chain_shape_relations
        if str(piece.patch_id) == "patch:seed:f0" and len(piece.segment_indices) == sides
    ]
    assert len(band_rim) == 2 and all(piece.kind is LINE for piece in band_rim)


def test_flat_quad_is_cut_at_its_right_angle_corners() -> None:
    relations = _relations(make_single_quad_source())

    pieces = relations.patch_chain_shape_relations
    assert [piece.segment_indices for piece in pieces] == [(0,), (1,), (2,), (3,)]
    assert all(piece.kind is LINE for piece in pieces)
    assert all(piece.tilt_min is None and piece.is_planar for piece in pieces)


def test_flat_l_border_is_cut_at_corners_and_the_straight_seam_is_one_line() -> None:
    relations = _relations(make_two_quad_l_source_with_seam_on_shared_edge())

    border = _pieces(relations, "patch_chain:patch:seed:f0:0:0")
    assert [piece.segment_indices for piece in border] == [(0,), (1,), (2,)]
    (seam,) = _pieces(relations, "patch_chain:patch:seed:f0:0:1")
    assert seam.kind is LINE


# --- new synthetic fixtures -----------------------------------------------------------------

def test_cone_ring_is_a_surface_curve_following_the_turn_law() -> None:
    relations = _relations(make_cone_frustum_band_source())

    rings = [piece for piece in relations.patch_chain_shape_relations if len(piece.segment_indices) == 16]
    assert len(rings) == 2
    turn_3d = 2.0 * pi / 16
    for ring in rings:
        assert ring.kind is CURVE
        assert 0.0 < ring.tilt_min <= ring.tilt_max < pi / 2.0
        for turn in ring.evidence[0].data["surface_turns"]:
            assert abs(abs(turn) - turn_3d * sin(ring.tilt_min)) < 0.005
        assert ring.law_error_max < 0.005


def test_cylinder_band_ring_is_a_surface_line() -> None:
    relations = _relations(make_cone_frustum_band_source(top_radius=2.0))

    rings = [piece for piece in relations.patch_chain_shape_relations if len(piece.segment_indices) == 16]
    assert len(rings) == 2
    assert all(ring.kind is LINE and ring.tilt_max < 1.0e-9 for ring in rings)


def test_stepped_seam_is_three_pieces_on_both_sides() -> None:
    relations = _relations(make_stepped_seam_source(stepped=True))

    seam_chain = next(
        str(piece.chain_id) for piece in relations.patch_chain_shape_relations if "e0_1_1_1" in str(piece.chain_id)
    )
    uses = _uses_of_chain(relations, seam_chain)
    assert len(uses) == 2
    for pieces in uses.values():
        assert [piece.segment_indices for piece in pieces] == [(0,), (1,), (2,)]
        assert all(piece.kind is LINE for piece in pieces)


def test_straight_seam_is_one_line_on_both_sides() -> None:
    relations = _relations(make_stepped_seam_source(stepped=False))

    seam_chain = next(
        str(piece.chain_id) for piece in relations.patch_chain_shape_relations if "e0_1_1_1" in str(piece.chain_id)
    )
    uses = _uses_of_chain(relations, seam_chain)
    assert len(uses) == 2
    for pieces in uses.values():
        (piece,) = pieces
        assert piece.kind is LINE and piece.segment_indices == (0, 1, 2)


def test_warped_single_face_is_unresolved_with_a_law_mismatch_diagnostic() -> None:
    relations = _relations(make_single_pentagon_source(lift=0.5))

    first = _pieces(relations, "patch_chain:patch:seed:f0:0:0")[0]
    assert first.kind is UNRESOLVED
    assert first.segment_indices == (0, 1)
    assert first.law_error_max > 0.4
    (diagnostic,) = [d for d in relations.diagnostics if d.code == LAW_MISMATCH_CODE]
    assert diagnostic.severity.value == "DEGRADED"
    assert "patch_chain:patch:seed:f0:0:0" in diagnostic.entity_ids
    assert "v1" in diagnostic.entity_ids


def test_flat_single_face_has_no_law_mismatch() -> None:
    relations = _relations(make_single_pentagon_source(lift=0.0))

    first = _pieces(relations, "patch_chain:patch:seed:f0:0:0")[0]
    assert first.kind is LINE and first.segment_indices == (0, 1)
    assert _shape_codes(relations) == []


def test_closed_rim_on_the_box_is_one_line_and_cornered_on_the_lid() -> None:
    relations = _relations(make_closed_shared_boundary_loop_source())

    assert len(_pieces(relations, "patch_chain:patch:seed:f0:0:0")) == 4
    (rim,) = _pieces(relations, "patch_chain:patch:seed:f1:0:0")
    # The box use starts at v1, so the closed chain is read from segment 1 and
    # the Chain's closing vertex v0 is judged as an interior vertex.
    assert rim.kind is LINE and rim.segment_indices == (1, 2, 3, 0)
    assert rim.start_source_vertex_id == "v1" and rim.end_source_vertex_id == "v1"
    assert "v0" in rim.evidence[0].data["interior_source_vertex_ids"]


def test_cross_band_pinch_use_is_one_line_read_from_its_own_start() -> None:
    relations = _relations(_load_capture("artist_cross_band.json"))

    (piece,) = _pieces(relations, "patch_chain:patch:seed:f1:0:2")
    assert piece.kind is LINE
    assert piece.segment_indices == (4, 5, 6, 7, 8, 9, 10, 11, 0, 1, 2, 3)
    assert piece.start_source_vertex_id == "v4" and piece.end_source_vertex_id == "v4"
    assert piece.surface_turn_max < radians(0.2)
    assert all(piece.kind is not UNRESOLVED for piece in relations.patch_chain_shape_relations)
    assert _shape_codes(relations) == []


# --- hand-built facts: closing vertex, several face fans, planarity, signed total ------------

def _segment(chain_id, index, start, end, start_id, end_id):
    vector = tuple(b - a for a, b in zip(start, end))
    size = sum(value * value for value in vector) ** 0.5
    return ChainSegmentGeometryFacts(
        chain_id=chain_id,
        source_edge_id=SourceEdgeId(f"e{index}"),
        segment_index=index,
        start_source_vertex_id=SourceVertexId(start_id),
        end_source_vertex_id=SourceVertexId(end_id),
        start_position=start,
        end_position=end,
        vector=vector,
        length=size,
        direction=tuple(value / size for value in vector),
    )


def _fan(name, vertex_name, face_names, angle, normal):
    return LocalFaceFanGeometryFacts(
        id=f"local_face_fan:p:{name}",
        patch_id=PatchId("p"),
        vertex_id=VertexId(f"vertex:{vertex_name}"),
        source_vertex_id=SourceVertexId(vertex_name),
        source_face_ids=tuple(SourceFaceId(face) for face in face_names),
        area=1.0,
        normal=normal,
        interior_angle_sum=angle,
    )


def _hand_built(points, fans, side_faces, start_vertex="v0", side_normals=None):
    """One PatchChain use of one Chain through points v0, v1, ... in patch p."""

    chain_id = ChainId("chain:hand")
    closed = points[0] == points[-1]
    names = [f"v{index}" for index in range(len(points))]
    if closed:
        names[-1] = names[0]
    segments = tuple(
        _segment(chain_id, index, points[index], points[index + 1], names[index], names[index + 1])
        for index in range(len(points) - 1)
    )
    use_id = PatchChainId("patch_chain:hand")
    topology = SurfaceModel(
        id=SurfaceModelId("surface:hand"),
        patch_chains={
            use_id: PatchChain(
                id=use_id,
                chain_id=chain_id,
                patch_id=PatchId("p"),
                loop_id=BoundaryLoopId("loop:hand"),
                orientation_sign=1,
                position_in_loop=0,
                start_vertex_id=VertexId(f"vertex:{start_vertex}"),
                end_vertex_id=VertexId(f"vertex:{start_vertex}"),
            )
        },
        vertices={
            VertexId(f"vertex:{name}"): Vertex(VertexId(f"vertex:{name}"), (SourceVertexId(name),))
            for name in set(names)
        },
    )
    geometry = GeometryFactSnapshot(
        chain_facts={
            chain_id: ChainGeometryFacts(
                chain_id=chain_id,
                length=sum(segment.length for segment in segments),
                chord_length=0.0,
                chord_direction=(0.0, 0.0, 0.0),
                straightness=0.0,
                detour_ratio=0.0,
                segments=segments,
            )
        },
        local_face_fan_facts={fan.id: fan for fan in fans},
        patch_chain_facts={
            use_id: PatchChainGeometryFacts(
                patch_chain_id=use_id,
                chain_id=chain_id,
                patch_id=PatchId("p"),
                segment_side_face_ids=tuple(SourceFaceId(face) for face in side_faces),
                segment_side_normals=tuple(side_normals or (None,) * len(segments)),
            )
        },
    )
    return build_patch_chain_shape_relations(topology, geometry)


UP = (0.0, 0.0, 1.0)
IN_PLANE = (1.0, 0.0, 0.0)


def test_closed_chain_judges_its_closing_vertex_for_a_use_starting_elsewhere() -> None:
    # Unit square v0..v3; the use starts at v2. Only v0 is a surface corner.
    square = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 0.0))
    fans = [
        _fan("a0", "v0", ("f",), pi / 2.0, UP),
        _fan("a1", "v1", ("f",), pi, IN_PLANE),
        _fan("a2", "v2", ("f",), pi, IN_PLANE),
        _fan("a3", "v3", ("f",), pi, IN_PLANE),
    ]
    records, diagnostics = _hand_built(square, fans, ("f",) * 4, start_vertex="v2")

    assert [record.segment_indices for record in records] == [(2, 3), (0, 1)]
    assert all(record.kind is LINE for record in records)
    assert diagnostics == ()


def _pinch_line(side_faces):
    line = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0), (3.0, 0.0, 0.0))
    fans = [
        # Two fans at v1: "a" (a quarter, sorted first) and "b" (the chain's own side, straight).
        _fan("a", "v1", ("fa",), pi / 2.0, UP),
        _fan("b", "v1", ("fb0", "fb1"), pi, UP),
        _fan("c", "v2", ("fb1", "fc"), pi, UP),
    ]
    return _hand_built(line, fans, side_faces)


def test_several_fans_pick_the_one_holding_both_side_faces() -> None:
    records, diagnostics = _pinch_line(("fb0", "fb1", "fc"))

    (record,) = records
    assert record.kind is LINE and record.segment_indices == (0, 1, 2)
    assert diagnostics == ()


def test_side_faces_split_over_two_fans_leave_the_piece_unresolved() -> None:
    records, diagnostics = _pinch_line(("fb0", "fa", "fc"))

    (record,) = records
    assert record.kind is UNRESOLVED
    (diagnostic,) = diagnostics
    assert diagnostic.code == UNRESOLVED_OCCURRENCE_CODE
    assert "v1" in diagnostic.entity_ids


@pytest.mark.parametrize(("lift", "planar"), ((0.0, True), (0.6, False)))
def test_is_planar_tells_a_spatial_piece_from_a_planar_one(lift: float, planar: bool) -> None:
    points = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.3, 0.0), (3.0, 0.3, lift))
    fans = []
    for index in (1, 2):
        before = tuple(b - a for a, b in zip(points[index - 1], points[index]))
        after = tuple(b - a for a, b in zip(points[index], points[index + 1]))
        # A fan normal inside the local plane: the chain bends in depth, surface turn 0.
        normal = tuple(a / (sum(v * v for v in after) ** 0.5) - b / (sum(v * v for v in before) ** 0.5)
                       for a, b in zip(after, before))
        fans.append(_fan(f"n{index}", f"v{index}", ("f",), pi, normal))
    records, diagnostics = _hand_built(points, fans, ("f",) * 3)

    (record,) = records
    assert record.is_planar is planar
    assert record.kind is LINE and diagnostics == ()


def test_surface_turning_total_is_signed() -> None:
    line = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0), (3.0, 0.0, 0.0), (4.0, 0.0, 0.0))
    fans = [
        _fan("z1", "v1", ("f",), pi + 0.05, UP),
        _fan("z2", "v2", ("f",), pi - 0.05, UP),
        _fan("z3", "v3", ("f",), pi + 0.05, UP),
    ]
    records, _diagnostics = _hand_built(line, fans, ("f",) * 4)

    (record,) = records
    assert record.kind is LINE  # a gentle zigzag inside the line tolerance
    assert isclose(record.surface_turning_total, 0.05)
    assert isclose(record.surface_turn_max, 0.05)


# --- evidence only: nothing else changes -----------------------------------------------------

def _canonical_sources():
    return [
        make_cylinder_tube_without_caps_with_one_seam_source(),
        make_cylinder_tube_without_caps_with_two_seams_source(),
        make_tube_with_cap_source(),
        make_capped_decagon_prism_odd_strips_source(),
        make_extruded_cross_source(),
        make_l_corridor_tunnel_seamed_folds_source(),
        make_beveled_wall_corner_source(),
        make_closed_shared_boundary_loop_source(),
        make_stepped_seam_source(),
        make_cone_frustum_band_source(capped=True),
    ]


def _without_shape(relations):
    return replace(
        relations,
        patch_chain_shape_relations=(),
        diagnostics=tuple(
            diagnostic
            for diagnostic in relations.diagnostics
            if diagnostic.code not in (LAW_MISMATCH_CODE, UNRESOLVED_OCCURRENCE_CODE)
        ),
    )


def test_shape_relation_changes_other_relations_only_through_the_chord_shortcut(monkeypatch) -> None:
    # Stage B flipped this Stage A test: the per-use chord shortcut of the runs
    # is now the one reader. With that decision fixed to the old shortcut,
    # removing the shape records must change nothing else.
    monkeypatch.setattr(chain_refinement, "_use_keeps_chord_run", lambda pieces, chord_run: True)
    sources = [_load_capture(path.name) for path in sorted(DATA.glob("*.json"))] + _canonical_sources()
    assert len(sources) >= 17
    with_shape = []
    for source in sources:
        context = run_pass_1_relations(run_pass_0(source))
        with_shape.append((context.relation_snapshot, run_skeleton_solve(context)))

    monkeypatch.setattr(relations_build, "build_patch_chain_shape_relations", lambda topology, geometry: ((), ()))
    for source, (relations, solve) in zip(sources, with_shape):
        context = run_pass_1_relations(run_pass_0(source))
        assert context.relation_snapshot.patch_chain_shape_relations == ()
        assert _without_shape(relations) == context.relation_snapshot
        assert solve == run_skeleton_solve(context)


def test_the_chord_shortcut_is_the_only_reader_of_the_shape_relation() -> None:
    # Stage B flipped this Stage A test: chain_refinement is now the one reader.
    root = Path(__file__).resolve().parents[1]
    readers = []
    for path in list((root / "layer_3_relations").glob("*.py")) + list((root / "layer_5_runtime").glob("*.py")):
        if path.name in ("build.py", "model.py", "patch_chain_shape.py"):
            continue
        text = path.read_text(encoding="utf-8")
        if "patch_chain_shape" in text or "PatchChainShape" in text:
            readers.append(path.name)
    assert readers == ["chain_refinement.py"]
