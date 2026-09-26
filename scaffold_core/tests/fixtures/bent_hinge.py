"""
Layer: tests fixtures

Rules:
- Synthetic bent-hinge panel source fixture only.
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


def make_bent_hinge_panels_source(corner_lift: float = 0.0) -> SourceMeshSnapshot:
    """Return an L-shaped planar panel and a quad joined along an L-shaped seam.

    The panel is three quads in z = 0; the quad fills the missing corner and
    shares the bent two-edge seam through the center vertex, which stays flat
    (four right angles), so the stitch is accepted. corner_lift raises the
    quad's far corner: with a small lift the quad stays within the planarity
    tolerance but tilts away from the panel, and a bent hinge between
    non-coplanar patches has no rotation axis.
    """

    positions = {
        "p00": (-1.0, -1.0, 0.0),
        "p10": (0.0, -1.0, 0.0),
        "p20": (1.0, -1.0, 0.0),
        "p01": (-1.0, 0.0, 0.0),
        "p11": (0.0, 0.0, 0.0),
        "p21": (1.0, 0.0, 0.0),
        "p02": (-1.0, 1.0, 0.0),
        "p12": (0.0, 1.0, 0.0),
        "p22": (1.0, 1.0, corner_lift),
    }
    vertices = {
        SourceVertexId(name): MeshVertexRef(SourceVertexId(name), position)
        for name, position in positions.items()
    }
    face_loops = {
        "f_panel_a": ("p00", "p10", "p11", "p01"),
        "f_panel_b": ("p10", "p20", "p21", "p11"),
        "f_panel_c": ("p01", "p11", "p12", "p02"),
        "f_corner": ("p11", "p21", "p22", "p12"),
    }
    edges: dict[SourceEdgeId, MeshEdgeRef] = {}
    faces: dict[SourceFaceId, MeshFaceRef] = {}
    for face_name, loop in face_loops.items():
        edge_ids = []
        for index, first in enumerate(loop):
            second = loop[(index + 1) % len(loop)]
            edge_id = SourceEdgeId("e_" + "_".join(sorted((first, second))))
            edges.setdefault(edge_id, MeshEdgeRef(edge_id, (SourceVertexId(first), SourceVertexId(second))))
            edge_ids.append(edge_id)
        faces[SourceFaceId(face_name)] = MeshFaceRef(
            SourceFaceId(face_name),
            tuple(SourceVertexId(vertex) for vertex in loop),
            tuple(edge_ids),
        )
    seams = (SourceEdgeId("e_p11_p21"), SourceEdgeId("e_p11_p12"))
    return SourceMeshSnapshot(
        id=SourceMeshId("bent_hinge_panels"),
        vertices=vertices,
        edges=edges,
        faces=faces,
        selected_face_ids=tuple(faces),
        marks=tuple(SourceMark(kind=SourceMarkKind.SEAM, target_id=edge_id) for edge_id in seams),
    )
