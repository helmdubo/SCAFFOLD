"""
Layer: tests

Rules:
- G5a skeleton runtime acceptance on canonical and artist fixtures.
- Invariants are asserted as validation outputs per the phase contract.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from scaffold_core.ids import SourceEdgeId, SourceFaceId, SourceMeshId, SourceVertexId
from scaffold_core.layer_0_source.marks import SourceMark, SourceMarkKind
from scaffold_core.layer_0_source.snapshot import (
    MeshEdgeRef,
    MeshFaceRef,
    MeshVertexRef,
    SourceMeshSnapshot,
)
from scaffold_core.layer_5_runtime.pins import run_skeleton_solve
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
from scaffold_core.tests.fixtures.cylinder_tube import (
    make_cylinder_tube_without_caps_with_two_seams_source,
)
from scaffold_core.tests.fixtures.detached_parallel_walls import (
    make_detached_parallel_walls_source,
)
from scaffold_core.tests.fixtures.extruded_cross import make_extruded_cross_source
from scaffold_core.tests.fixtures.l_corridor_tunnel import (
    make_l_corridor_tunnel_seamed_folds_source,
)
from scaffold_core.tests.fixtures.tube_with_cap import make_tube_with_cap_source

DATA = Path(__file__).resolve().parent / "data"


def _solve(source):
    return run_skeleton_solve(run_pass_1_relations(run_pass_0(source)))


def _load_capture(name: str) -> SourceMeshSnapshot:
    data = json.loads((DATA / name).read_text(encoding="utf-8"))
    vertices = {
        SourceVertexId(k): MeshVertexRef(SourceVertexId(k), tuple(v))
        for k, v in data["vertices"].items()
    }
    edges = {
        SourceEdgeId(k): MeshEdgeRef(SourceEdgeId(k), (SourceVertexId(v[0]), SourceVertexId(v[1])))
        for k, v in data["edges"].items()
    }
    faces = {
        SourceFaceId(k): MeshFaceRef(
            SourceFaceId(k),
            tuple(SourceVertexId(v) for v in f["vertex_ids"]),
            tuple(SourceEdgeId(e) for e in f["edge_ids"]),
        )
        for k, f in data["faces"].items()
    }
    return SourceMeshSnapshot(
        id=SourceMeshId(data["id"]),
        vertices=vertices,
        edges=edges,
        faces=faces,
        selected_face_ids=tuple(SourceFaceId(f) for f in data["selected_face_ids"]),
        marks=tuple(
            SourceMark(kind=SourceMarkKind(m["kind"]), target_id=SourceEdgeId(m["target_id"]))
            for m in data["marks"]
        ),
    )


def test_two_seam_tube_unwraps_to_an_exact_rectangle() -> None:
    result = _solve(make_cylinder_tube_without_caps_with_two_seams_source())

    assert len(result.assembly.islands) == 1
    assert result.residual_max < 1e-6
    assert result.axis_parallel_violations == ()
    assert result.seam_length_mismatches == ()
    rows = {round(vertex.uv[1], 6) for vertex in result.vertices}
    assert len(rows) == 2  # top rail and bottom rail are two straight rows
    top = sorted(round(v.uv[0], 4) for v in result.vertices if round(v.uv[1], 6) == min(rows))
    bottom = sorted(round(v.uv[0], 4) for v in result.vertices if round(v.uv[1], 6) == max(rows))
    assert top == bottom  # columns align across the rails


def test_extruded_cross_band_unwraps_with_caps_as_separate_islands() -> None:
    result = _solve(make_extruded_cross_source())

    assert len(result.assembly.islands) == 3
    assert result.residual_max < 1e-6
    assert result.axis_parallel_violations == ()
    band_rows = {
        round(vertex.uv[1], 6)
        for vertex in result.vertices
        if "f_side" in vertex.patch_id
    }
    assert len(band_rows) == 2  # top rim and bottom rim are straight rows


def test_artist_cyl32_band_solves_as_rigid_grid() -> None:
    result = _solve(_load_capture("artist_cyl32.json"))

    assert len(result.assembly.islands) == 3  # stitched side band + two caps
    assert result.residual_max < 1e-6
    assert result.axis_parallel_violations == ()
    assert sum(1 for vertex in result.vertices if vertex.pinned) >= 60


def test_tube_with_cap_keeps_cap_island_separate() -> None:
    result = _solve(make_tube_with_cap_source())

    assert len(result.assembly.islands) == 2
    blocked = [d for d in result.assembly.decisions if not d.accepted and "defect" in d.reason]
    assert blocked  # the cap stitch is rejected by the Level A gate


def test_tunnel_folds_stitch_into_one_island() -> None:
    result = _solve(make_l_corridor_tunnel_seamed_folds_source())

    assert len(result.assembly.islands) == 1
    assert result.residual_max < 1e-6
    assert result.axis_parallel_violations == ()


def test_detached_walls_stay_two_islands() -> None:
    result = _solve(make_detached_parallel_walls_source())

    assert len(result.assembly.islands) == 2


def test_frustum_band_is_developable_and_solves_exactly() -> None:
    # Stretching the top ring turns the tube into a frustum band - still
    # a developable surface. The gate must keep stitching it and the
    # skeleton must stay exact (a wrong "non-developable" rejection here
    # would be over-blocking).
    source = make_cylinder_tube_without_caps_with_two_seams_source()
    stretched = dict(source.vertices)
    for vertex_id, ref in source.vertices.items():
        x, y, z = ref.position
        if z > 0.5:
            stretched[vertex_id] = MeshVertexRef(ref.id, (x * 2.0, y * 2.0, z))
    result = _solve(replace(source, vertices=stretched))

    assert len(result.assembly.islands) == 1
    assert result.residual_max < 1e-6
    assert result.axis_parallel_violations == ()


def test_contradictory_equations_are_excluded_with_diagnostics() -> None:
    # Direct unit check of the UNCONSTRAINED path: three nodes, two
    # consistent equations plus one contradicting the loop sum.
    from scaffold_core.layer_5_runtime.skeleton import _lstsq

    consistent, residuals = _lstsq([("a", "b", 1.0, "e1"), ("b", "c", 1.0, "e2")])
    assert max(abs(r) for r in residuals) < 1e-9
    _coords, residuals = _lstsq(
        [("a", "b", 1.0, "e1"), ("b", "c", 1.0, "e2"), ("a", "c", 5.0, "e3")]
    )
    assert max(abs(r) for r in residuals) > 1e-2  # contradiction is visible, not hidden


import pytest


def test_multiseam_cylinder_open_band_should_solve_xfail() -> None:
    # KNOWN LIMITATION (ScaffoldRail/Trace consumer not integrated yet): a 32-segment
    # cylinder cut into 6 vertical strips is an OPEN developable band (one
    # seam stays SPLIT, the rest SEW) and MUST unroll to a rectangle. It
    # currently collapses because G5a still does not consume unambiguous
    # ScaffoldRail evidence or explicit cut-context for loop opening. Do not
    # patch this with another Layer 5 traversal heuristic; flip after the
    # consumer slice replaces local rail-order/sign derivation.
    result = _solve(_load_capture("artist_cyl_multiseam.json"))
    band = max(result.assembly.islands, key=lambda island: len(island.patch_ids))
    pinned_in_band = [
        v for v in result.vertices if v.island_id == band.id and v.pinned
    ]
    if result.diagnostics or not pinned_in_band:
        pytest.xfail("multiseam open band needs ScaffoldRail consumer integration")
    assert result.residual_max < 1e-6
