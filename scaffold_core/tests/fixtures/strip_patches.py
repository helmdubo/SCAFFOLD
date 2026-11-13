"""
Layer: tests fixtures

Rules:
- Synthetic flat patches for the Layer 4 strip feature: a cut annulus (a ring
  strip that is its own island), a ring sector stitched between two quads
  (straight stitches only) and the same with a band on its bent outer arc,
  an annulus with a tab (five uses), a square with a hole (two loops) and a
  three-row cut annulus with and without a hole.
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

RING_INNER_RADIUS = 1.0
RING_OUTER_RADIUS = 2.0
ANNULUS_SEGMENTS = 12
SECTOR_SEGMENTS = 6


def _mesh(name, points, faces, seam_edges=()) -> SourceMeshSnapshot:
    vertices = {SourceVertexId(key): MeshVertexRef(SourceVertexId(key), point) for key, point in points.items()}
    edges: dict[SourceEdgeId, MeshEdgeRef] = {}
    face_refs: dict[SourceFaceId, MeshFaceRef] = {}
    for face_name, corners in faces.items():
        edge_ids = []
        for first, second in zip(corners, corners[1:] + corners[:1]):
            low, high = sorted((first, second))
            edge_id = SourceEdgeId(f"e_{low}_{high}")
            edges[edge_id] = MeshEdgeRef(edge_id, (SourceVertexId(low), SourceVertexId(high)))
            edge_ids.append(edge_id)
        face_id = SourceFaceId(face_name)
        face_refs[face_id] = MeshFaceRef(face_id, tuple(SourceVertexId(c) for c in corners), tuple(edge_ids))
    marks = tuple(
        SourceMark(kind=SourceMarkKind.SEAM, target_id=SourceEdgeId(f"e_{min(a, b)}_{max(a, b)}"))
        for a, b in seam_edges
    )
    return SourceMeshSnapshot(
        id=SourceMeshId(name),
        vertices=vertices,
        edges=edges,
        faces=face_refs,
        selected_face_ids=tuple(face_refs),
        marks=marks,
    )


def _ring(segments: int, angle: float, closed: bool):
    """Points and quads (normal +Z) of a flat ring over the given angle."""

    count = segments if closed else segments + 1
    points = {}
    for index in range(count):
        theta = angle * index / segments
        points[f"i{index}"] = (RING_INNER_RADIUS * cos(theta), RING_INNER_RADIUS * sin(theta), 0.0)
        points[f"o{index}"] = (RING_OUTER_RADIUS * cos(theta), RING_OUTER_RADIUS * sin(theta), 0.0)
    faces = {
        f"f{index}": (f"i{index}", f"o{index}", f"o{(index + 1) % count}", f"i{(index + 1) % count}")
        for index in range(segments)
    }
    return points, faces


def make_cut_annulus_source() -> SourceMeshSnapshot:
    """Return a flat annulus cut by one radial UV seam (a SEAM_SELF).

    One patch, one loop of four uses: the two seam sides (straight radial
    ends of length 1), the outer circle (about 4 pi) and the inner circle
    (about 2 pi). SEAM_SELF never stitches, so the patch is its own island.
    """

    points, faces = _ring(ANNULUS_SEGMENTS, 2.0 * pi, closed=True)
    return _mesh("cut_annulus", points, faces, seam_edges=(("i0", "o0"),))


def make_annulus_with_tab_source() -> SourceMeshSnapshot:
    """Return the cut annulus plus a quad across a seam on the outer edge o0-o1.

    The annulus loop has five uses: the tab side, the rest of the outer
    circle, a seam side, the inner circle and the other seam side.
    """

    points, faces = _ring(ANNULUS_SEGMENTS, 2.0 * pi, closed=True)
    points["t0"] = (3.0 * cos(0.0), 3.0 * sin(0.0), 0.0)
    theta = 2.0 * pi / ANNULUS_SEGMENTS
    points["t1"] = (3.0 * cos(theta), 3.0 * sin(theta), 0.0)
    faces["f_tab"] = ("o0", "t0", "t1", "o1")
    return _mesh("annulus_with_tab", points, faces, seam_edges=(("i0", "o0"), ("o0", "o1")))


def make_cut_three_row_annulus_source(with_hole: bool) -> SourceMeshSnapshot:
    """Return a flat annulus of three radial rows cut by one radial UV seam.

    Without the hole it is a four-use strip like the cut annulus. With the
    hole, one middle-row cell away from the seam is removed: the outer loop
    keeps its four uses and the patch gains a second (inner) loop.
    """

    segments = ANNULUS_SEGMENTS
    radii = (RING_INNER_RADIUS, 4.0 / 3.0, 5.0 / 3.0, RING_OUTER_RADIUS)
    points = {}
    for row, radius in enumerate(radii):
        for index in range(segments):
            theta = 2.0 * pi * index / segments
            points[f"r{row}_{index}"] = (radius * cos(theta), radius * sin(theta), 0.0)
    faces = {}
    for row in range(len(radii) - 1):
        for index in range(segments):
            if with_hole and row == 1 and index == segments // 2:
                continue
            following = (index + 1) % segments
            faces[f"f{row}_{index}"] = (
                f"r{row}_{index}", f"r{row + 1}_{index}", f"r{row + 1}_{following}", f"r{row}_{following}"
            )
    seams = tuple((f"r{row}_0", f"r{row + 1}_0") for row in range(len(radii) - 1))
    name = "cut_annulus_with_hole" if with_hole else "cut_three_row_annulus"
    return _mesh(name, points, faces, seam_edges=seams)


def make_ring_sector_between_quads_source() -> SourceMeshSnapshot:
    """Return a flat quarter ring sector with a quad across a seam at each radial end.

    The sector has four uses (outer arc, quad side, inner arc, quad side);
    both stitch candidates are straight radial ends of one edge.
    """

    points, faces, seams = _ring_sector_between_quads()
    return _mesh("ring_sector_between_quads", points, faces, seam_edges=seams)


def make_ring_sector_between_quads_with_band_source() -> SourceMeshSnapshot:
    """Return the ring sector between quads plus a band across a seam on its outer arc.

    The band (radius 2 to 3, same angle) is stitched along the bent outer
    arc, so the sector keeps a bent stitch candidate beside the two straight
    radial ends.
    """

    points, faces, seams = _ring_sector_between_quads()
    band_radius = RING_OUTER_RADIUS + 1.0
    for index in range(SECTOR_SEGMENTS + 1):
        theta = (pi / 2.0) * index / SECTOR_SEGMENTS
        points[f"b{index}"] = (band_radius * cos(theta), band_radius * sin(theta), 0.0)
    for index in range(SECTOR_SEGMENTS):
        faces[f"f_band{index}"] = (f"o{index}", f"b{index}", f"b{index + 1}", f"o{index + 1}")
    seams += tuple((f"o{index}", f"o{index + 1}") for index in range(SECTOR_SEGMENTS))
    return _mesh("ring_sector_between_quads_with_band", points, faces, seam_edges=seams)


def _ring_sector_between_quads():
    points, faces = _ring(SECTOR_SEGMENTS, pi / 2.0, closed=False)
    last = SECTOR_SEGMENTS
    points["q0"] = (RING_INNER_RADIUS, -1.0, 0.0)
    points["q1"] = (RING_OUTER_RADIUS, -1.0, 0.0)
    points["r0"] = (-1.0, RING_INNER_RADIUS, 0.0)
    points["r1"] = (-1.0, RING_OUTER_RADIUS, 0.0)
    faces["f_quad_a"] = ("q0", "q1", "o0", "i0")
    faces["f_quad_b"] = (f"i{last}", f"o{last}", "r1", "r0")
    return points, faces, (("i0", "o0"), (f"i{last}", f"o{last}"))


def make_square_with_hole_source() -> SourceMeshSnapshot:
    """Return a flat 3x3 square with the centre cell removed: two boundary loops."""

    points = {f"g{x}{y}": (float(x), float(y), 0.0) for x in range(4) for y in range(4)}
    faces = {
        f"f{x}{y}": (f"g{x}{y}", f"g{x + 1}{y}", f"g{x + 1}{y + 1}", f"g{x}{y + 1}")
        for x in range(3)
        for y in range(3)
        if (x, y) != (1, 1)
    }
    return _mesh("square_with_hole", points, faces)
