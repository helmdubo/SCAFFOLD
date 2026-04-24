"""
Layer: 0 — Source

Rules:
- This is the core mesh-read boundary for Blender/BMesh input.
- Convert Blender mesh state into SourceMeshSnapshot.
- Do not build topology, geometry facts, relations, features, or runtime solve here.
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


def read_source_mesh_from_blender(context: object) -> SourceMeshSnapshot:
    """Convert the active Blender mesh object into SourceMeshSnapshot.

    G1 reads mesh topology, selected faces and source edge marks only. It does
    not build Layer 1 topology and does not write data back to Blender.
    """

    active_object = getattr(context, "object", None)
    if active_object is None:
        raise ValueError("No active Blender object.")
    if getattr(active_object, "type", None) != "MESH":
        raise ValueError("Active Blender object is not a mesh.")

    sync_from_editmode = getattr(active_object, "update_from_editmode", None)
    if callable(sync_from_editmode):
        sync_from_editmode()

    mesh = active_object.data
    vertices = {
        SourceVertexId(f"v{vertex.index}"): MeshVertexRef(
            id=SourceVertexId(f"v{vertex.index}"),
            position=(float(vertex.co.x), float(vertex.co.y), float(vertex.co.z)),
        )
        for vertex in mesh.vertices
    }

    edges = {
        SourceEdgeId(f"e{edge.index}"): MeshEdgeRef(
            id=SourceEdgeId(f"e{edge.index}"),
            vertex_ids=(
                SourceVertexId(f"v{edge.vertices[0]}"),
                SourceVertexId(f"v{edge.vertices[1]}"),
            ),
        )
        for edge in mesh.edges
    }
    edge_ids_by_key = {
        tuple(sorted(edge.vertices)): SourceEdgeId(f"e{edge.index}")
        for edge in mesh.edges
    }

    faces: dict[SourceFaceId, MeshFaceRef] = {}
    selected_face_ids: list[SourceFaceId] = []
    for polygon in mesh.polygons:
        face_id = SourceFaceId(f"f{polygon.index}")
        vertex_ids = tuple(SourceVertexId(f"v{vertex_index}") for vertex_index in polygon.vertices)
        edge_ids = tuple(
            edge_ids_by_key[tuple(sorted(edge_key))]
            for edge_key in polygon.edge_keys
        )
        faces[face_id] = MeshFaceRef(
            id=face_id,
            vertex_ids=vertex_ids,
            edge_ids=edge_ids,
        )
        if getattr(polygon, "select", False):
            selected_face_ids.append(face_id)

    marks: list[SourceMark] = []
    for edge in mesh.edges:
        edge_id = SourceEdgeId(f"e{edge.index}")
        if getattr(edge, "use_seam", False):
            marks.append(SourceMark(kind=SourceMarkKind.SEAM, target_id=edge_id))
        if getattr(edge, "use_edge_sharp", False):
            marks.append(SourceMark(kind=SourceMarkKind.SHARP, target_id=edge_id))

    mesh_name = getattr(mesh, "name", "mesh")
    object_name = getattr(active_object, "name", mesh_name)
    return SourceMeshSnapshot(
        id=SourceMeshId(f"blender:{object_name}:{mesh_name}"),
        vertices=vertices,
        edges=edges,
        faces=faces,
        selected_face_ids=tuple(selected_face_ids),
        marks=tuple(marks),
    )
