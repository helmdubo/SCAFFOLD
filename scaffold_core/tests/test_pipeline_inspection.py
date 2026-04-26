"""
Layer: tests

Rules:
- Pipeline inspection tests only.
- Tests use fake mesh objects and do not import Blender.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace

from scaffold_core.pipeline.inspection import (
    describe_active_blender_mesh_topology,
    inspect_pipeline_context,
)
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
from scaffold_core.tests.fixtures.closed_shared_loop import make_closed_shared_boundary_loop_source
from scaffold_core.tests.fixtures.l_shape import make_two_patch_source_with_two_edge_seam_run
from scaffold_core.tests.fixtures.single_patch import make_single_quad_source


ROOT = Path(__file__).resolve().parents[1]
INSPECTION_MODULE = ROOT / "pipeline" / "inspection.py"
FORBIDDEN_TOKENS = frozenset({
    "H_FRAME",
    "V_FRAME",
    "WALL",
    "FLOOR",
    "SLOPE",
    "AlignmentClass",
    "WorldOrientation",
    "Feature",
    "Runtime",
    "Solve",
    "UV",
})


def test_describe_active_blender_mesh_topology_reports_g1_counts() -> None:
    vertices = [
        SimpleNamespace(index=0, co=SimpleNamespace(x=0.0, y=0.0, z=0.0)),
        SimpleNamespace(index=1, co=SimpleNamespace(x=1.0, y=0.0, z=0.0)),
        SimpleNamespace(index=2, co=SimpleNamespace(x=1.0, y=1.0, z=0.0)),
        SimpleNamespace(index=3, co=SimpleNamespace(x=0.0, y=1.0, z=0.0)),
    ]
    edges = [
        SimpleNamespace(index=0, vertices=(0, 1), use_seam=False, use_edge_sharp=False),
        SimpleNamespace(index=1, vertices=(1, 2), use_seam=False, use_edge_sharp=False),
        SimpleNamespace(index=2, vertices=(2, 3), use_seam=False, use_edge_sharp=False),
        SimpleNamespace(index=3, vertices=(3, 0), use_seam=False, use_edge_sharp=False),
    ]
    polygons = [
        SimpleNamespace(
            index=0,
            vertices=(0, 1, 2, 3),
            edge_keys=((0, 1), (1, 2), (2, 3), (0, 3)),
            select=True,
        )
    ]
    mesh = SimpleNamespace(
        name="mesh",
        vertices=vertices,
        edges=edges,
        polygons=polygons,
    )
    active_object = SimpleNamespace(
        name="object",
        type="MESH",
        data=mesh,
        update_from_editmode=lambda: True,
    )

    report = describe_active_blender_mesh_topology(SimpleNamespace(object=active_object))

    assert "source faces: 1" in report
    assert "selected faces: 1" in report
    assert "shells: 1" in report
    assert "patches: 1" in report
    assert "chains: 4" in report
    assert "shell shell:0: patches ('patch:seed:f0',)" in report
    assert "patch patch:seed:f0: shell shell:0 faces ('f0',) loops ('loop:patch:seed:f0:0',)" in report
    assert "chain chain:e0: edges ('e0',) uses 1" in report
    assert (
        "chain use use:patch:seed:f0:0:0: chain chain:e0 "
        "patch patch:seed:f0 loop loop:patch:seed:f0:0 orientation 1"
    ) in report


def test_inspect_pipeline_context_reports_single_patch_topology_tree() -> None:
    context = run_pass_0(make_single_quad_source())

    report = inspect_pipeline_context(context, detail="full")

    json.dumps(report)
    surface = report["surface_model"]
    shell = surface["shells"][0]
    patch = shell["patches"][0]
    loop = patch["loops"][0]
    chain_use = loop["chain_uses"][0]
    chain = chain_use["chain"]
    assert surface["id"] == "surface:single_quad"
    assert shell["id"] == "shell:0"
    assert patch["source_face_ids"] == ["f0"]
    assert loop["kind"] == "OUTER"
    assert chain_use["orientation_sign"] in (-1, 1)
    assert chain["start_vertex_id"].startswith("vertex:")
    assert chain["start_source_vertex_ids"]
    assert chain["source_edge_count"] == 1
    assert not chain["is_closed"]
    assert chain["source_vertex_run"] == ["v0", "v1"]
    assert report["geometry"]["patch_count"] == 1
    assert report["diagnostics"]
    assert report["diagnostics"][0]["code"] == "TOPOLOGY_CHAIN_BORDER"


def test_inspect_pipeline_context_reports_relations_and_coalesced_chain() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_two_patch_source_with_two_edge_seam_run())
    )

    report = inspect_pipeline_context(context, detail="full")

    json.dumps(report)
    relations = report["relations"]
    assert relations["patch_adjacency_count"] == 1
    assert relations["chain_continuation_count"] > 0
    assert relations["patch_adjacencies"][0]["dihedral_kind"] == "COPLANAR"
    assert relations["chain_continuations"]
    assert any(
        len(chain_use["chain"]["source_edge_ids"]) > 1
        for shell in report["surface_model"]["shells"]
        for patch in shell["patches"]
        for loop in patch["loops"]
        for chain_use in loop["chain_uses"]
    )
    assert relations["chain_continuations"][0]["evidence"]
    assert relations["chain_continuations"][0]["evidence"][0]["data"]["policy"] == "conservative_g3b2"


def test_inspection_marks_closed_coalesced_chain_and_vertex_run() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_closed_shared_boundary_loop_source())
    )

    report = inspect_pipeline_context(context, detail="full")

    json.dumps(report)
    chains = [
        chain_use["chain"]
        for shell in report["surface_model"]["shells"]
        for patch in shell["patches"]
        for loop in patch["loops"]
        for chain_use in loop["chain_uses"]
    ]
    closed_chain = next(chain for chain in chains if chain["is_closed"])
    geometry_chain = next(
        chain
        for chain in report["geometry"]["chains"]
        if chain["id"] == closed_chain["id"]
    )
    assert closed_chain["source_edge_count"] == 4
    assert closed_chain["source_vertex_run"] == ["v0", "v1", "v2", "v3", "v0"]
    assert geometry_chain["is_closed"]
    assert not geometry_chain["is_direction_stable"]
    assert geometry_chain["source_vertex_run"] == ["v0", "v1", "v2", "v3", "v0"]
    assert len(geometry_chain["segments"]) == 4
    assert geometry_chain["segments"][0]["source_edge_id"] == "e10"
    assert geometry_chain["segments"][0]["start_source_vertex_id"] == "v0"
    assert geometry_chain["segments"][0]["end_source_vertex_id"] == "v1"


def test_inspection_output_order_is_stable() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_two_patch_source_with_two_edge_seam_run())
    )

    first_report = inspect_pipeline_context(context, detail="full")
    second_report = inspect_pipeline_context(context, detail="full")

    assert first_report == second_report


def test_inspection_default_output_is_compact() -> None:
    context = run_pass_1_relations(
        run_pass_0(make_closed_shared_boundary_loop_source())
    )

    report = inspect_pipeline_context(context)

    json.dumps(report)
    assert "surface_model" not in report
    assert report["geometry"] == {
        "patch_count": 2,
        "chain_count": 1,
        "vertex_count": 8,
    }
    assert report["relations"] == {
        "patch_adjacency_count": 1,
        "chain_continuation_count": 2,
        "chain_directional_run_count": 4,
        "chain_directional_run_use_count": 8,
        "junction_sample_count": 16,
        "alignment_class_count": 2,
        "patch_axes_count": 2,
    }


def test_inspection_code_does_not_introduce_deferred_semantic_terms() -> None:
    tree = ast.parse(INSPECTION_MODULE.read_text(encoding="utf-8"))
    identifiers: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            identifiers.add(node.id)
        elif isinstance(node, ast.Attribute):
            identifiers.add(node.attr)
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            identifiers.add(node.name)
        elif isinstance(node, ast.arg):
            identifiers.add(node.arg)
        elif isinstance(node, ast.alias):
            identifiers.add(node.name.split(".")[-1])
            if node.asname:
                identifiers.add(node.asname)

    assert not identifiers & FORBIDDEN_TOKENS
