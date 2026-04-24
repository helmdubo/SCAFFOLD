"""
Layer: tests

Rules:
- Blender IO boundary tests only.
- Tests use fake mesh objects and do not import Blender.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from scaffold_core.layer_0_source.blender_io import read_source_mesh_from_blender
from scaffold_core.layer_0_source.marks import SourceMarkKind


def _fake_context() -> SimpleNamespace:
    vertices = [
        SimpleNamespace(index=0, co=SimpleNamespace(x=0.0, y=0.0, z=0.0)),
        SimpleNamespace(index=1, co=SimpleNamespace(x=1.0, y=0.0, z=0.0)),
        SimpleNamespace(index=2, co=SimpleNamespace(x=1.0, y=1.0, z=0.0)),
        SimpleNamespace(index=3, co=SimpleNamespace(x=0.0, y=1.0, z=0.0)),
    ]
    edges = [
        SimpleNamespace(index=0, vertices=(0, 1), use_seam=False, use_edge_sharp=False),
        SimpleNamespace(index=1, vertices=(1, 2), use_seam=True, use_edge_sharp=False),
        SimpleNamespace(index=2, vertices=(2, 3), use_seam=False, use_edge_sharp=True),
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
    return SimpleNamespace(object=active_object)


def test_read_source_mesh_from_blender_reads_selected_faces_and_edge_marks() -> None:
    source = read_source_mesh_from_blender(_fake_context())

    assert len(source.vertices) == 4
    assert len(source.edges) == 4
    assert len(source.faces) == 1
    assert tuple(str(face_id) for face_id in source.selected_face_ids) == ("f0",)
    assert {mark.kind for mark in source.marks} == {
        SourceMarkKind.SEAM,
        SourceMarkKind.SHARP,
    }


def test_read_source_mesh_from_blender_requires_active_mesh_object() -> None:
    with pytest.raises(ValueError, match="No active Blender object"):
        read_source_mesh_from_blender(SimpleNamespace(object=None))

    with pytest.raises(ValueError, match="not a mesh"):
        read_source_mesh_from_blender(SimpleNamespace(object=SimpleNamespace(type="CURVE")))
