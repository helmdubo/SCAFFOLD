"""
Layer: tests

Rules:
- Layer 2 geometry fact tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

from math import isclose

from scaffold_core.core.diagnostics import DiagnosticSeverity
from scaffold_core.ids import (
    BoundaryLoopId,
    ChainId,
    ChainUseId,
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
    ChainUse,
    Patch,
    Shell,
    SurfaceModel,
    Vertex,
)
from scaffold_core.layer_2_geometry.build import build_geometry_facts
from scaffold_core.layer_2_geometry.facts import ChainShapeHint
from scaffold_core.tests.fixtures.chain_shape_geometry import make_chain_shape_source_and_topology
from scaffold_core.tests.fixtures.closed_shared_loop import make_closed_shared_boundary_loop_source
from scaffold_core.tests.fixtures.degenerate_geometry import make_degenerate_triangle_source
from scaffold_core.tests.fixtures.l_shape import make_two_quad_l_source
from scaffold_core.tests.fixtures.single_patch import make_single_quad_source


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


def _make_broken_chain_order_source_and_topology() -> tuple[SourceMeshSnapshot, SurfaceModel]:
    v0 = SourceVertexId("v0")
    v1 = SourceVertexId("v1")
    v2 = SourceVertexId("v2")
    v3 = SourceVertexId("v3")
    e0 = SourceEdgeId("e0")
    e1 = SourceEdgeId("e1")
    f0 = SourceFaceId("f0")
    chain_id = ChainId("chain:broken")
    use_id = ChainUseId("use:broken")
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
                chain_use_ids=(use_id,),
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
        chain_uses={
            use_id: ChainUse(
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
