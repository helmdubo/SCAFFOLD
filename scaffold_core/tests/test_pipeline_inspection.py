"""
Layer: tests

Rules:
- Pipeline inspection tests only.
- Tests use fake mesh objects and do not import Blender.
"""

from __future__ import annotations

from types import SimpleNamespace

from scaffold_core.pipeline.inspection import describe_active_blender_mesh_topology


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
    assert "shell shell:0: patches ('patch:f0',)" in report
    assert "patch patch:f0: shell shell:0 faces ('f0',) loops ('loop:patch:f0:0',)" in report
    assert "chain chain:e0: uses 1" in report
