"""
Layer: tests fixtures

Rules:
- Synthetic capped polygonal prism source fixtures only.
- Fixtures build small explicit source data.
- No production logic here.
"""

from __future__ import annotations

from math import cos, pi, sin

from scaffold_core.ids import SourceEdgeId, SourceFaceId, SourceMeshId, SourceVertexId
from scaffold_core.layer_0_source.marks import SourceMark, SourceMarkKind
from scaffold_core.layer_0_source.snapshot import (
    MeshEdgeRef,
    MeshFaceRef,
    MeshVertexRef,
    SourceMeshSnapshot,
)


def make_capped_decagon_prism_odd_strips_source() -> SourceMeshSnapshot:
    """Return a capped 10-segment prism cut into two 5-segment side strips.

    Vertical seams at ring vertices 0 and 5 split the side band into two
    strips of five quads. Both decagon caps are ngon patches behind fully
    seamed rims. Minimal synthetic reproduction of the artist_cyl_multiseam
    collapse: each strip rim is a curved 5-run shared chain whose middle run
    is parallel to the chain chord, so SHARED_CHAIN transport into the caps
    passes and the same-patch bridge then welds the top and bottom rims.
    """

    return _make_capped_prism_source(
        "capped_decagon_prism_odd_strips",
        segment_count=10,
        seam_vertex_indices=(0, 5),
    )


def make_capped_hex_prism_uneven_strips_source() -> SourceMeshSnapshot:
    """Return a capped hexagonal prism cut into 2- and 4-segment side strips.

    Rims stay separate here, but the vertical seam runs transport through the
    90-degree rim corner nodes onto cap perimeter runs, forming one family
    across the side band and both caps.
    """

    return _make_capped_prism_source(
        "capped_hex_prism_uneven_strips",
        segment_count=6,
        seam_vertex_indices=(0, 2),
    )


def make_capped_square_prism_all_seams_source() -> SourceMeshSnapshot:
    """Return a capped square prism (a box) with every edge seamed.

    Each face is its own patch, like the artist walls meshes where nearly every
    edge carries a seam. Rim chains are straight single runs, so the Slice L1
    straight-hinge rule lets families cross into the end patches; the Slice L2
    patch-revisit rule must still keep each wall's top and bottom apart.
    """

    return _make_capped_prism_source(
        "capped_square_prism_all_seams",
        segment_count=4,
        seam_vertex_indices=(0, 1, 2, 3),
    )


def _make_capped_prism_source(
    name: str,
    segment_count: int,
    seam_vertex_indices: tuple[int, ...],
) -> SourceMeshSnapshot:
    count = segment_count
    top = tuple(SourceVertexId(f"t{index}") for index in range(count))
    bottom = tuple(SourceVertexId(f"b{index}") for index in range(count))
    vertices: dict[SourceVertexId, MeshVertexRef] = {}
    for index in range(count):
        angle = 2.0 * pi * index / count
        x = cos(angle)
        y = sin(angle)
        vertices[top[index]] = MeshVertexRef(top[index], (x, y, 1.0))
        vertices[bottom[index]] = MeshVertexRef(bottom[index], (x, y, 0.0))

    top_edges = tuple(SourceEdgeId(f"e_t{index}") for index in range(count))
    bottom_edges = tuple(SourceEdgeId(f"e_b{index}") for index in range(count))
    vertical_edges = tuple(SourceEdgeId(f"e_v{index}") for index in range(count))
    edges: dict[SourceEdgeId, MeshEdgeRef] = {}
    for index in range(count):
        following = (index + 1) % count
        edges[top_edges[index]] = MeshEdgeRef(top_edges[index], (top[index], top[following]))
        edges[bottom_edges[index]] = MeshEdgeRef(
            bottom_edges[index],
            (bottom[index], bottom[following]),
        )
        edges[vertical_edges[index]] = MeshEdgeRef(
            vertical_edges[index],
            (top[index], bottom[index]),
        )

    faces: dict[SourceFaceId, MeshFaceRef] = {}
    for index in range(count):
        following = (index + 1) % count
        face_id = SourceFaceId(f"f{index}")
        faces[face_id] = MeshFaceRef(
            face_id,
            (top[index], bottom[index], bottom[following], top[following]),
            (
                vertical_edges[index],
                bottom_edges[index],
                vertical_edges[following],
                top_edges[index],
            ),
        )
    cap_top = SourceFaceId("f_cap_top")
    faces[cap_top] = MeshFaceRef(cap_top, top, top_edges)
    cap_bottom = SourceFaceId("f_cap_bottom")
    faces[cap_bottom] = MeshFaceRef(
        cap_bottom,
        (bottom[0], *reversed(bottom[1:])),
        tuple(reversed(bottom_edges)),
    )

    marks = tuple(
        SourceMark(kind=SourceMarkKind.SEAM, target_id=edge_id)
        for edge_id in (
            *(vertical_edges[index] for index in seam_vertex_indices),
            *top_edges,
            *bottom_edges,
        )
    )
    return SourceMeshSnapshot(
        id=SourceMeshId(name),
        vertices=vertices,
        edges=edges,
        faces=faces,
        selected_face_ids=tuple(faces),
        marks=marks,
    )
