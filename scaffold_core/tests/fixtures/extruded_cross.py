"""
Layer: tests fixtures

Rules:
- Synthetic extruded-cross source fixture only.
- Fixtures build small explicit source data.
- No production logic here.
"""

from __future__ import annotations

from scaffold_core.ids import SourceEdgeId, SourceFaceId, SourceMeshId, SourceVertexId
from scaffold_core.layer_0_source.marks import SourceMark, SourceMarkKind
from scaffold_core.layer_0_source.snapshot import (
    MeshEdgeRef,
    MeshFaceRef,
    MeshVertexRef,
    SourceMeshSnapshot,
)


def make_extruded_cross_source() -> SourceMeshSnapshot:
    """Return the user-validated cross footprint with side band, caps and one seam."""

    footprint = (
        (-1.0, 3.0),
        (1.0, 3.0),
        (1.0, 1.0),
        (3.0, 1.0),
        (3.0, -1.0),
        (1.0, -1.0),
        (1.0, -3.0),
        (-1.0, -3.0),
        (-1.0, -1.0),
        (-3.0, -1.0),
        (-3.0, 1.0),
        (-1.0, 1.0),
    )
    top = tuple(SourceVertexId(f"t{index}") for index in range(len(footprint)))
    bottom = tuple(SourceVertexId(f"b{index}") for index in range(len(footprint)))
    top_edges = tuple(SourceEdgeId(f"e_t{index}") for index in range(len(footprint)))
    bottom_edges = tuple(SourceEdgeId(f"e_b{index}") for index in range(len(footprint)))
    vertical_edges = tuple(SourceEdgeId(f"e_v{index}") for index in range(len(footprint)))

    vertices = {
        **{
            top[index]: MeshVertexRef(top[index], (x, y, 1.0))
            for index, (x, y) in enumerate(footprint)
        },
        **{
            bottom[index]: MeshVertexRef(bottom[index], (x, y, 0.0))
            for index, (x, y) in enumerate(footprint)
        },
    }
    edge_count = len(footprint)
    edges = {}
    for index in range(edge_count):
        next_index = (index + 1) % edge_count
        edges[top_edges[index]] = MeshEdgeRef(top_edges[index], (top[index], top[next_index]))
        edges[bottom_edges[index]] = MeshEdgeRef(bottom_edges[index], (bottom[index], bottom[next_index]))
        edges[vertical_edges[index]] = MeshEdgeRef(vertical_edges[index], (top[index], bottom[index]))

    side_faces = {
        SourceFaceId(f"f_side_{index}"): MeshFaceRef(
            SourceFaceId(f"f_side_{index}"),
            (top[index], bottom[index], bottom[(index + 1) % edge_count], top[(index + 1) % edge_count]),
            (vertical_edges[index], bottom_edges[index], vertical_edges[(index + 1) % edge_count], top_edges[index]),
        )
        for index in range(edge_count)
    }
    top_face = SourceFaceId("f_cap_top")
    bottom_face = SourceFaceId("f_cap_bottom")
    faces = {
        **side_faces,
        top_face: MeshFaceRef(top_face, top, top_edges),
        bottom_face: MeshFaceRef(bottom_face, bottom, bottom_edges),
    }
    seam_marks = tuple(
        SourceMark(kind=SourceMarkKind.SEAM, target_id=edge_id)
        for edge_id in (*top_edges, *bottom_edges, vertical_edges[0])
    )
    return SourceMeshSnapshot(
        id=SourceMeshId("extruded_cross_building"),
        vertices=vertices,
        edges=edges,
        faces=faces,
        selected_face_ids=tuple(faces),
        marks=seam_marks,
    )
