"""
Layer: tests fixtures

Rules:
- Synthetic reflex-corner wall source fixture only.
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


def make_reflex_corner_walls_source() -> SourceMeshSnapshot:
    """Return wall A butting into the vertical edge of a notch in wall B.

    Wall B (plane x = 0, three quads, one patch) is an L around the notch
    y, z in [0, 1], so it wraps 270 degrees around the notch corner n. Wall A
    (plane y = 0, x in [-1, 0]) meets B along the notch's vertical edge n-h,
    the only seam. Both walls face into the 90 degree wedge between them, so
    the orientation is consistent. Unfolded about the hinge, A fills the
    notch: A's top continues B's top through h, while A's bottom lands on B's
    notch bottom and points back at n (a fold-back, not a continuation).
    """

    positions = {
        "n": (0.0, 0.0, 0.0),
        "h": (0.0, 0.0, 1.0),
        "a_bottom": (-1.0, 0.0, 0.0),
        "a_top": (-1.0, 0.0, 1.0),
        "b_top_left": (0.0, -1.0, 1.0),
        "b_mid_left": (0.0, -1.0, 0.0),
        "b_bottom_left": (0.0, -1.0, -1.0),
        "b_bottom_mid": (0.0, 0.0, -1.0),
        "b_bottom_right": (0.0, 1.0, -1.0),
        "b_mid_right": (0.0, 1.0, 0.0),
    }
    vertices = {
        SourceVertexId(name): MeshVertexRef(SourceVertexId(name), position)
        for name, position in positions.items()
    }
    edge_vertices = {
        "e_hinge": ("n", "h"),
        "e_a_top": ("h", "a_top"),
        "e_a_left": ("a_top", "a_bottom"),
        "e_a_bottom": ("a_bottom", "n"),
        "e_b_inner_left": ("n", "b_mid_left"),
        "e_b_inner_down": ("n", "b_bottom_mid"),
        "e_b_notch_bottom": ("n", "b_mid_right"),
        "e_b_right": ("b_mid_right", "b_bottom_right"),
        "e_b_bottom_right": ("b_bottom_right", "b_bottom_mid"),
        "e_b_bottom_left": ("b_bottom_mid", "b_bottom_left"),
        "e_b_left_lower": ("b_bottom_left", "b_mid_left"),
        "e_b_left_upper": ("b_mid_left", "b_top_left"),
        "e_b_top": ("b_top_left", "h"),
    }
    edges = {
        SourceEdgeId(name): MeshEdgeRef(
            SourceEdgeId(name),
            (SourceVertexId(first), SourceVertexId(second)),
        )
        for name, (first, second) in edge_vertices.items()
    }
    face_loops = {
        "f_wall_a": (("n", "h", "a_top", "a_bottom"), ("e_hinge", "e_a_top", "e_a_left", "e_a_bottom")),
        "f_b_upper": (
            ("n", "b_mid_left", "b_top_left", "h"),
            ("e_b_inner_left", "e_b_left_upper", "e_b_top", "e_hinge"),
        ),
        "f_b_lower": (
            ("b_bottom_mid", "b_bottom_left", "b_mid_left", "n"),
            ("e_b_bottom_left", "e_b_left_lower", "e_b_inner_left", "e_b_inner_down"),
        ),
        "f_b_right": (
            ("b_bottom_right", "b_bottom_mid", "n", "b_mid_right"),
            ("e_b_bottom_right", "e_b_inner_down", "e_b_notch_bottom", "e_b_right"),
        ),
    }
    faces = {
        SourceFaceId(name): MeshFaceRef(
            SourceFaceId(name),
            tuple(SourceVertexId(vertex) for vertex in loop),
            tuple(SourceEdgeId(edge) for edge in loop_edges),
        )
        for name, (loop, loop_edges) in face_loops.items()
    }
    return SourceMeshSnapshot(
        id=SourceMeshId("reflex_corner_walls"),
        vertices=vertices,
        edges=edges,
        faces=faces,
        selected_face_ids=tuple(faces),
        marks=(SourceMark(kind=SourceMarkKind.SEAM, target_id=SourceEdgeId("e_hinge")),),
    )
