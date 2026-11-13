"""
Layer: tests

Rules:
- Layer 2 geometry fact tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

from math import cos, isclose, pi, sin

from scaffold_core.core.diagnostics import DiagnosticSeverity
from scaffold_core.ids import (
    BoundaryLoopId,
    ChainId,
    PatchChainId,
    PatchId,
    ShellId,
    SourceEdgeId,
    SourceFaceId,
    SourceMeshId,
    SourceVertexId,
    SurfaceModelId,
    VertexId,
)
from scaffold_core.layer_0_source.snapshot import (
    MeshEdgeRef,
    MeshFaceRef,
    MeshVertexRef,
    SourceMeshSnapshot,
)
from scaffold_core.layer_1_topology.build import build_topology_snapshot
from scaffold_core.layer_1_topology.model import (
    BoundaryLoop,
    BoundaryLoopKind,
    Chain,
    PatchChain,
    Patch,
    Shell,
    SurfaceModel,
    Vertex,
)
from scaffold_core.layer_2_geometry.build import build_geometry_facts
from scaffold_core.layer_2_geometry.facts import ChainShapeHint
from scaffold_core.pipeline.inspection import geometry_summary_to_dict
from scaffold_core.tests.fixtures.capped_prism import make_capped_decagon_prism_odd_strips_source
from scaffold_core.tests.fixtures.chain_shape_geometry import (
    make_chain_shape_source_and_topology,
    make_reversed_one_edge_chain_source_and_topology,
)
from scaffold_core.tests.fixtures.chain_shape_surfaces import (
    make_cone_frustum_band_source,
    make_single_pentagon_source,
)
from scaffold_core.tests.fixtures.closed_shared_loop import make_closed_shared_boundary_loop_source
from scaffold_core.tests.fixtures.cylinder_tube import (
    make_cylinder_tube_without_caps_with_one_seam_source,
    make_segmented_cylinder_tube_without_caps_with_one_seam_source,
)
from scaffold_core.tests.fixtures.degenerate_geometry import make_degenerate_triangle_source
from scaffold_core.tests.fixtures.l_corridor_tunnel import make_l_corridor_tunnel_seamed_folds_source
from scaffold_core.tests.fixtures.l_shape import make_two_quad_l_source
from scaffold_core.tests.fixtures.quad_ladders import _mesh
from scaffold_core.tests.fixtures.run_corner_sheets import make_bow_tie_quad_source, make_flat_l_hexagon_source
from scaffold_core.tests.fixtures.single_patch import make_single_quad_source
from scaffold_core.tests.test_layer_5_runtime import DATA, _load_capture


def test_single_quad_geometry_facts_are_measured() -> None:
    source = make_single_quad_source()
    topology = build_topology_snapshot(source)

    facts = build_geometry_facts(source, topology)

    patch = facts.patch_facts[PatchId("patch:seed:f0")]
    assert patch.area == 1.0
    assert patch.normal == (0.0, 0.0, 1.0)
    assert patch.centroid == (0.5, 0.5, 0.0)
    chain = facts.chain_facts[ChainId("chain:e0:e1:e2:e3")]
    assert chain.length == 4.0
    assert chain.chord_length == 0.0
    assert chain.chord_direction == (0.0, 0.0, 0.0)
    assert chain.straightness == 0.0
    assert chain.detour_ratio == 0.0
    assert chain.shape_hint is ChainShapeHint.UNKNOWN
    assert chain.source_vertex_run == (
        SourceVertexId("v0"),
        SourceVertexId("v1"),
        SourceVertexId("v2"),
        SourceVertexId("v3"),
        SourceVertexId("v0"),
    )
    assert len(chain.segments) == 4
    assert facts.vertex_facts[VertexId("vertex:v0")].position == (0.0, 0.0, 0.0)


def test_two_quad_patch_geometry_aggregates_source_faces() -> None:
    source = make_two_quad_l_source()
    topology = build_topology_snapshot(source)

    facts = build_geometry_facts(source, topology)

    patch = facts.patch_facts[PatchId("patch:seed:f0")]
    assert patch.area == 2.0
    assert patch.normal == (0.0, 0.0, 1.0)
    assert patch.centroid == (1.0, 0.5, 0.0)
    assert patch.area_vector_length == 2.0  # planar: the length of the summed area vectors is the area


def test_patch_area_vector_length_is_the_length_of_the_summed_area_vectors() -> None:
    tube = make_cylinder_tube_without_caps_with_one_seam_source()
    (closed,) = build_geometry_facts(tube, build_topology_snapshot(tube)).patch_facts.values()
    segments = 16
    positions = {}
    for i in range(segments + 1):
        angle = pi * i / segments
        for j, y in enumerate((0.0, 2.0)):
            positions[f"v{i}_{j}"] = (cos(angle), y, sin(angle))
    faces = [(f"v{i}_0", f"v{i}_1", f"v{i + 1}_1", f"v{i + 1}_0") for i in range(segments)]
    half = _mesh("half_cylinder", positions, faces)
    (half_facts,) = build_geometry_facts(half, build_topology_snapshot(half)).patch_facts.values()

    assert closed.area > 1.0 and closed.area_vector_length < 1e-12  # a closed tube: the area vectors cancel
    # A half cylinder (polygon of 16 sides): the chord 2 over the arc length, 2/pi in the limit.
    assert isclose(
        half_facts.area_vector_length / half_facts.area, 2.0 / (segments * 2.0 * sin(pi / (2 * segments))), rel_tol=1e-9
    )
    assert isclose(half_facts.area_vector_length / half_facts.area, 2.0 / pi, rel_tol=0.01)


def test_local_face_fan_geometry_splits_materialized_seam_occurrences() -> None:
    source = make_segmented_cylinder_tube_without_caps_with_one_seam_source()
    topology = build_topology_snapshot(source)

    facts = build_geometry_facts(source, topology)

    seam_top_fans = tuple(
        fan
        for fan in facts.local_face_fan_facts.values()
        if fan.source_vertex_id == SourceVertexId("v_a_t")
    )
    assert len(seam_top_fans) == 2
    assert {fan.vertex_id for fan in seam_top_fans} == {
        VertexId("vertex:v_a_t:patch_chain:patch:seed:f_ab_top:0"),
        VertexId("vertex:v_a_t:patch_chain:patch:seed:f_ab_top:1"),
    }
    assert all(fan.normal != (0.0, 0.0, 0.0) for fan in seam_top_fans)
    assert {len(fan.source_face_ids) for fan in seam_top_fans} == {1}
    assert all(isclose(fan.interior_angle_sum, pi / 2.0) for fan in seam_top_fans)


def test_degenerate_geometry_emits_degraded_diagnostics() -> None:
    source = make_degenerate_triangle_source()
    topology = build_topology_snapshot(source)

    facts = build_geometry_facts(source, topology)

    codes = {diagnostic.code for diagnostic in facts.diagnostics}
    assert "GEOMETRY_PATCH_DEGENERATE_AREA" in codes
    assert any(
        segment.length == 0.0
        for chain in facts.chain_facts.values()
        for segment in chain.segments
    )
    assert all(
        diagnostic.severity is DiagnosticSeverity.DEGRADED
        for diagnostic in facts.diagnostics
    )


def test_chain_shape_hints_measure_straightness_and_detour() -> None:
    source, topology = make_chain_shape_source_and_topology()

    facts = build_geometry_facts(source, topology)

    straight = facts.chain_facts[ChainId("chain:straight")]
    assert straight.length == 2.0
    assert straight.chord_length == 2.0
    assert straight.straightness == 1.0
    assert straight.detour_ratio == 1.0
    assert straight.shape_hint is ChainShapeHint.STRAIGHT

    sawtooth = facts.chain_facts[ChainId("chain:sawtooth")]
    assert sawtooth.chord_length == 3.0
    assert sawtooth.length > sawtooth.chord_length
    assert isclose(sawtooth.straightness, sawtooth.chord_length / sawtooth.length)
    assert isclose(sawtooth.detour_ratio, sawtooth.length / sawtooth.chord_length)
    assert sawtooth.shape_hint is ChainShapeHint.SAWTOOTH_STRAIGHT


def test_closed_chain_segment_geometry_preserves_source_edge_run() -> None:
    source = make_closed_shared_boundary_loop_source()
    topology = build_topology_snapshot(source)

    facts = build_geometry_facts(source, topology)

    chain = facts.chain_facts[ChainId("chain:e10:e9:e6:e7")]
    assert chain.source_vertex_run == (
        SourceVertexId("v0"),
        SourceVertexId("v1"),
        SourceVertexId("v2"),
        SourceVertexId("v3"),
        SourceVertexId("v0"),
    )
    assert len(chain.segments) == 4
    assert chain.source_vertex_run[0] == chain.source_vertex_run[-1]
    assert isclose(sum(segment.length for segment in chain.segments), chain.length)
    assert all(
        left.end_source_vertex_id == right.start_source_vertex_id
        for left, right in zip(chain.segments, chain.segments[1:])
    )


def test_chain_segment_order_degraded_diagnostic_keeps_deterministic_segments() -> None:
    source, topology = _make_broken_chain_order_source_and_topology()

    facts = build_geometry_facts(source, topology)

    chain = facts.chain_facts[ChainId("chain:broken")]
    assert len(chain.segments) == 2
    assert chain.source_vertex_run == (
        SourceVertexId("v0"),
        SourceVertexId("v1"),
        SourceVertexId("v2"),
        SourceVertexId("v3"),
    )
    assert "GEOMETRY_CHAIN_SEGMENT_ORDER_DEGRADED" in {
        diagnostic.code
        for diagnostic in facts.diagnostics
    }


def test_cube_corner_vertex_angle_defect_is_measured() -> None:
    source = _make_cube_corner_angle_source()
    topology = _topology_with_vertices("cube_corner_angle", (SourceVertexId("v000"),))

    facts = build_geometry_facts(source, topology)

    vertex = facts.vertex_facts[VertexId("vertex:v000")]
    assert isclose(vertex.interior_angle_sum, 1.5 * pi)
    assert not vertex.is_boundary
    assert isclose(vertex.angle_defect, 0.5 * pi)


def test_flat_interior_vertex_angle_defect_is_zero() -> None:
    source = _make_flat_interior_angle_source()
    topology = _topology_with_vertices("flat_interior_angle", (SourceVertexId("v11"),))

    facts = build_geometry_facts(source, topology)

    vertex = facts.vertex_facts[VertexId("vertex:v11")]
    assert isclose(vertex.interior_angle_sum, 2.0 * pi)
    assert not vertex.is_boundary
    assert isclose(vertex.angle_defect, 0.0, abs_tol=1.0e-9)


def test_l_corridor_tunnel_fold_vertex_angle_defects_are_zero() -> None:
    source = make_l_corridor_tunnel_seamed_folds_source()
    topology = build_topology_snapshot(source)

    facts = build_geometry_facts(source, topology)

    fold_source_vertex_ids = {
        SourceVertexId("g1"),
        SourceVertexId("g2"),
        SourceVertexId("w0"),
        SourceVertexId("w1"),
    }
    fold_vertices = tuple(
        facts.vertex_facts[vertex.id]
        for vertex in topology.vertices.values()
        if any(source_vertex_id in fold_source_vertex_ids for source_vertex_id in vertex.source_vertex_ids)
    )
    assert fold_vertices
    for vertex in fold_vertices:
        assert isclose(vertex.interior_angle_sum, pi)
        assert vertex.is_boundary
        assert isclose(vertex.angle_defect, 0.0, abs_tol=1.0e-9)


def test_full_geometry_inspection_includes_vertex_angle_facts() -> None:
    source = _make_flat_interior_angle_source()
    topology = _topology_with_vertices("flat_interior_angle", (SourceVertexId("v11"),))
    facts = build_geometry_facts(source, topology)

    report = geometry_summary_to_dict(facts, detail="full")

    vertex = report["vertices"][0]
    assert vertex["id"] == "vertex:v11"
    assert isclose(vertex["interior_angle_sum"], 2.0 * pi)
    assert isclose(vertex["angle_defect"], 0.0, abs_tol=1.0e-9)
    assert vertex["is_boundary"] is False


def test_straight_chain_has_no_plane_and_no_chord_deviation() -> None:
    source, topology = make_chain_shape_source_and_topology()

    straight = build_geometry_facts(source, topology).chain_facts[ChainId("chain:straight")]

    assert straight.plane_normal is None
    assert straight.plane_deviation == 0.0
    assert isclose(straight.chord_deviation, 0.0, abs_tol=1.0e-12)


def test_planar_zigzag_chain_measures_plane_and_chord_deviation() -> None:
    source, topology = make_chain_shape_source_and_topology()

    zigzag = build_geometry_facts(source, topology).chain_facts[ChainId("chain:sawtooth")]

    # Turns alternate sign; each cross product is flipped to agree with the largest.
    assert zigzag.plane_normal is not None
    assert isclose(abs(zigzag.plane_normal[2]), 1.0)
    assert isclose(zigzag.plane_deviation, 0.0, abs_tol=1.0e-12)
    assert isclose(zigzag.chord_deviation, 0.25)


def test_planar_arc_chain_lies_in_its_plane() -> None:
    source = make_cone_frustum_band_source()
    topology = build_topology_snapshot(source)

    facts = build_geometry_facts(source, topology)

    ring = next(
        chain_fact
        for chain_fact in facts.chain_facts.values()
        if len(chain_fact.segments) == 16 and "e_t" in str(chain_fact.chain_id)
    )
    assert ring.plane_normal is not None
    assert isclose(abs(ring.plane_normal[2]), 1.0)
    assert isclose(ring.plane_deviation, 0.0, abs_tol=1.0e-9)
    # A closed ring has no chord: the deviation is measured from its start, the diameter.
    assert isclose(ring.chord_deviation, 2.0, rel_tol=1.0e-6)


def test_spatial_chain_reports_plane_deviation() -> None:
    source = make_single_pentagon_source(lift=0.5)
    topology = build_topology_snapshot(source)

    (border,) = build_geometry_facts(source, topology).chain_facts.values()

    assert border.plane_normal is not None
    assert border.plane_deviation > 0.05
    # A closed chain counts its first vertex once: deviation from the mean of the five corners.
    corners = [vertex.position for vertex in source.vertices.values()]
    center = tuple(sum(point[axis] for point in corners) / len(corners) for axis in range(3))
    expected = max(
        abs(sum((point[axis] - center[axis]) * border.plane_normal[axis] for axis in range(3)))
        for point in corners
    )
    assert isclose(border.plane_deviation, expected, rel_tol=1.0e-9)

    flat_source = make_single_pentagon_source(lift=0.0)
    (flat_border,) = build_geometry_facts(flat_source, build_topology_snapshot(flat_source)).chain_facts.values()
    assert isclose(flat_border.plane_deviation, 0.0, abs_tol=1.0e-12)


def test_tilt_is_measured_per_side_of_one_chain() -> None:
    source = make_capped_decagon_prism_odd_strips_source()
    topology = build_topology_snapshot(source)

    facts = build_geometry_facts(source, topology)

    rim = ChainId("chain:e_t4:e_t3:e_t2:e_t1:e_t0")
    sides = {
        str(use.patch_id): facts.patch_chain_facts[use.id]
        for use in topology.patch_chains.values()
        if use.chain_id == rim
    }
    side = sides["patch:seed:f0"]
    cap = sides["patch:seed:f_cap_top"]
    # The side band normal lies in the rim plane: the rim bends in depth there.
    assert isclose(side.tilt_min, 0.0, abs_tol=1.0e-9)
    assert isclose(side.tilt_max, 0.0, abs_tol=1.0e-9)
    # The cap is the rim plane itself.
    assert isclose(cap.tilt_min, pi / 2.0, abs_tol=1.0e-6)
    assert isclose(cap.tilt_max, pi / 2.0, abs_tol=1.0e-6)
    assert all(face_id is not None for face_id in side.segment_side_face_ids)
    assert set(cap.segment_side_face_ids) == {SourceFaceId("f_cap_top")}


def test_cone_ring_tilt_is_strictly_between_zero_and_right_angle() -> None:
    source = make_cone_frustum_band_source()
    topology = build_topology_snapshot(source)

    facts = build_geometry_facts(source, topology)

    tilts = [
        (side.tilt_min, side.tilt_max)
        for side in facts.patch_chain_facts.values()
        if side.tilt_min is not None
    ]
    assert len(tilts) == 2
    for tilt_min, tilt_max in tilts:
        assert 0.7 < tilt_min <= tilt_max < 0.8  # about 44.4 degrees on the 45-degree band


def test_seam_self_chain_takes_the_side_face_of_each_use() -> None:
    source = make_cylinder_tube_without_caps_with_one_seam_source()
    topology = build_topology_snapshot(source)

    facts = build_geometry_facts(source, topology)

    seam_uses = [use for use in topology.patch_chains.values() if str(use.chain_id) == "chain:e_v0"]
    assert len(seam_uses) == 2
    side_faces = [facts.patch_chain_facts[use.id].segment_side_face_ids for use in seam_uses]
    assert {face_ids[0] for face_ids in side_faces} == {SourceFaceId("f0"), SourceFaceId("f3")}
    # A straight seam has no plane, so no tilt.
    assert all(facts.patch_chain_facts[use.id].tilt_min is None for use in seam_uses)


def test_open_chain_vertex_run_follows_the_chain_from_its_start_vertex() -> None:
    checked = 0
    for path in sorted(DATA.glob("*.json")):
        source = _load_capture(path.name)
        topology = build_topology_snapshot(source)
        facts = build_geometry_facts(source, topology)
        for chain in topology.chains.values():
            start_sources = topology.vertices[chain.start_vertex_id].source_vertex_ids
            end_sources = topology.vertices[chain.end_vertex_id].source_vertex_ids
            if set(start_sources) & set(end_sources):
                continue  # a closed Chain has no end points to follow
            chain_facts = facts.chain_facts[chain.id]
            run = chain_facts.source_vertex_run
            assert run[0] in start_sources, (path.name, chain.id)
            assert run[-1] in end_sources, (path.name, chain.id)
            assert chain_facts.segments[0].start_source_vertex_id == run[0]
            assert chain_facts.segments[-1].end_source_vertex_id == run[-1]
            _assert_chord_follows_segments(chain_facts)
            checked += 1
    assert checked > 200


def test_one_edge_chain_stored_against_its_edge_runs_from_the_chain_start() -> None:
    source, topology = make_reversed_one_edge_chain_source_and_topology()

    chain_facts = build_geometry_facts(source, topology).chain_facts[ChainId("chain:reversed")]

    assert chain_facts.source_vertex_run == (SourceVertexId("v1"), SourceVertexId("v0"))
    (segment,) = chain_facts.segments
    assert (segment.start_source_vertex_id, segment.end_source_vertex_id) == (
        SourceVertexId("v1"),
        SourceVertexId("v0"),
    )
    assert chain_facts.chord_direction[0] < 0.0 and chain_facts.chord_direction[1] < 0.0
    _assert_chord_follows_segments(chain_facts)


def test_reflex_corner_of_an_n_gon_measures_its_full_interior_angle() -> None:
    source = make_flat_l_hexagon_source()
    topology = build_topology_snapshot(source)
    corners = ("a", "b", "d", "e", "f", "g")
    vertex_topology = _topology_with_vertices(
        "flat_l_hexagon",
        tuple(SourceVertexId(name) for name in corners),
    )

    fans = build_geometry_facts(source, topology).local_face_fan_facts.values()
    vertex_facts = build_geometry_facts(source, vertex_topology).vertex_facts

    fan_angle = {str(fan.source_vertex_id): fan.interior_angle_sum for fan in fans}
    assert set(fan_angle) == set(corners)
    for name in corners:
        expected = 1.5 * pi if name == "e" else 0.5 * pi
        assert isclose(fan_angle[name], expected), name
        assert isclose(vertex_facts[VertexId(f"vertex:{name}")].interior_angle_sum, expected), name


def test_self_crossing_face_keeps_the_plain_corner_angles() -> None:
    # Read by its winding, this quad would get two corners above pi and a
    # corner sum of 4*pi; a simple quad sums to 2*pi, and the plain reading
    # (every corner below pi) is the closer one.
    source = make_bow_tie_quad_source()
    corners = ("a", "b", "c", "d")
    vertex_topology = _topology_with_vertices(
        "bow_tie_quad",
        tuple(SourceVertexId(name) for name in corners),
    )

    vertex_facts = build_geometry_facts(source, vertex_topology).vertex_facts

    angles = [vertex_facts[VertexId(f"vertex:{name}")].interior_angle_sum for name in corners]
    assert all(0.0 < angle < pi for angle in angles)
    assert sum(angles) < 2.0 * pi


def _assert_chord_follows_segments(chain_facts) -> None:
    summed = tuple(sum(segment.vector[axis] for segment in chain_facts.segments) for axis in range(3))
    norm = sum(component * component for component in summed) ** 0.5
    assert isclose(norm, chain_facts.chord_length, rel_tol=1e-9, abs_tol=1e-12)
    if norm > 1e-9:
        for axis in range(3):
            assert isclose(chain_facts.chord_direction[axis], summed[axis] / norm, abs_tol=1e-9)


def _topology_with_vertices(
    suffix: str,
    source_vertex_ids: tuple[SourceVertexId, ...],
) -> SurfaceModel:
    vertices = {
        VertexId(f"vertex:{source_vertex_id}"): Vertex(
            id=VertexId(f"vertex:{source_vertex_id}"),
            source_vertex_ids=(source_vertex_id,),
        )
        for source_vertex_id in source_vertex_ids
    }
    return SurfaceModel(id=SurfaceModelId(f"surface:{suffix}"), vertices=vertices)


def _make_cube_corner_angle_source() -> SourceMeshSnapshot:
    return _source_from_faces(
        "cube_corner_angle",
        {
            "v000": (0.0, 0.0, 0.0),
            "v100": (1.0, 0.0, 0.0),
            "v010": (0.0, 1.0, 0.0),
            "v110": (1.0, 1.0, 0.0),
            "v001": (0.0, 0.0, 1.0),
            "v101": (1.0, 0.0, 1.0),
            "v011": (0.0, 1.0, 1.0),
        },
        {
            "f_bottom": ("v000", "v100", "v110", "v010"),
            "f_front": ("v000", "v001", "v101", "v100"),
            "f_left": ("v000", "v010", "v011", "v001"),
        },
    )


def _make_flat_interior_angle_source() -> SourceMeshSnapshot:
    return _source_from_faces(
        "flat_interior_angle",
        {
            "v00": (-1.0, -1.0, 0.0),
            "v10": (0.0, -1.0, 0.0),
            "v20": (1.0, -1.0, 0.0),
            "v01": (-1.0, 0.0, 0.0),
            "v11": (0.0, 0.0, 0.0),
            "v21": (1.0, 0.0, 0.0),
            "v02": (-1.0, 1.0, 0.0),
            "v12": (0.0, 1.0, 0.0),
            "v22": (1.0, 1.0, 0.0),
        },
        {
            "f_bottom_left": ("v00", "v10", "v11", "v01"),
            "f_bottom_right": ("v10", "v20", "v21", "v11"),
            "f_top_right": ("v11", "v21", "v22", "v12"),
            "f_top_left": ("v01", "v11", "v12", "v02"),
        },
    )


def _source_from_faces(
    mesh_id: str,
    vertex_positions: dict[str, tuple[float, float, float]],
    face_vertex_names: dict[str, tuple[str, ...]],
) -> SourceMeshSnapshot:
    vertices = {
        SourceVertexId(vertex_name): MeshVertexRef(
            SourceVertexId(vertex_name),
            position,
        )
        for vertex_name, position in vertex_positions.items()
    }
    edges: dict[SourceEdgeId, MeshEdgeRef] = {}
    faces: dict[SourceFaceId, MeshFaceRef] = {}
    for face_name, vertex_names in face_vertex_names.items():
        edge_ids: list[SourceEdgeId] = []
        for first_name, second_name in zip(vertex_names, vertex_names[1:] + vertex_names[:1]):
            edge_key = tuple(sorted((first_name, second_name)))
            edge_id = SourceEdgeId(f"edge:{edge_key[0]}:{edge_key[1]}")
            edges.setdefault(
                edge_id,
                MeshEdgeRef(
                    edge_id,
                    (SourceVertexId(edge_key[0]), SourceVertexId(edge_key[1])),
                ),
            )
            edge_ids.append(edge_id)
        source_face_id = SourceFaceId(face_name)
        faces[source_face_id] = MeshFaceRef(
            source_face_id,
            tuple(SourceVertexId(vertex_name) for vertex_name in vertex_names),
            tuple(edge_ids),
        )
    return SourceMeshSnapshot(
        id=SourceMeshId(mesh_id),
        vertices=vertices,
        edges=edges,
        faces=faces,
        selected_face_ids=tuple(faces),
    )


def _make_broken_chain_order_source_and_topology() -> tuple[SourceMeshSnapshot, SurfaceModel]:
    v0 = SourceVertexId("v0")
    v1 = SourceVertexId("v1")
    v2 = SourceVertexId("v2")
    v3 = SourceVertexId("v3")
    e0 = SourceEdgeId("e0")
    e1 = SourceEdgeId("e1")
    f0 = SourceFaceId("f0")
    chain_id = ChainId("chain:broken")
    use_id = PatchChainId("patch_chain:broken")
    vertex_0 = VertexId("vertex:v0")
    vertex_3 = VertexId("vertex:v3")
    patch_id = PatchId("patch:broken")
    shell_id = ShellId("shell:broken")
    loop_id = BoundaryLoopId("loop:broken")

    source = SourceMeshSnapshot(
        id=SourceMeshId("broken_chain_order"),
        vertices={
            v0: MeshVertexRef(v0, (0.0, 0.0, 0.0)),
            v1: MeshVertexRef(v1, (1.0, 0.0, 0.0)),
            v2: MeshVertexRef(v2, (2.0, 0.0, 0.0)),
            v3: MeshVertexRef(v3, (3.0, 0.0, 0.0)),
        },
        edges={
            e0: MeshEdgeRef(e0, (v0, v1)),
            e1: MeshEdgeRef(e1, (v2, v3)),
        },
        faces={
            f0: MeshFaceRef(f0, (v0, v1, v2), (e0, e1, e0)),
        },
    )
    topology = SurfaceModel(
        id=SurfaceModelId("surface:broken"),
        shells={shell_id: Shell(id=shell_id, patch_ids=(patch_id,))},
        patches={patch_id: Patch(id=patch_id, shell_id=shell_id, loop_ids=(loop_id,), source_face_ids=())},
        loops={
            loop_id: BoundaryLoop(
                id=loop_id,
                patch_id=patch_id,
                kind=BoundaryLoopKind.DEGRADED,
                patch_chain_ids=(use_id,),
                loop_index=0,
            )
        },
        chains={
            chain_id: Chain(
                id=chain_id,
                start_vertex_id=vertex_0,
                end_vertex_id=vertex_3,
                source_edge_ids=(e0, e1),
            )
        },
        patch_chains={
            use_id: PatchChain(
                id=use_id,
                chain_id=chain_id,
                patch_id=patch_id,
                loop_id=loop_id,
                orientation_sign=1,
                position_in_loop=0,
            )
        },
        vertices={
            vertex_0: Vertex(id=vertex_0, source_vertex_ids=(v0,)),
            vertex_3: Vertex(id=vertex_3, source_vertex_ids=(v3,)),
        },
    )
    return source, topology
