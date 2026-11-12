"""
Layer: 2 - Geometry

Rules:
- Low-level vector measurement functions only.
- No topology building, relation derivation, feature interpretation, or solve logic.
- No semantic classification.
"""

from __future__ import annotations

from math import acos, asin, sqrt

from scaffold_core.layer_2_geometry.facts import Vector3


EPSILON = 1.0e-9
COLLINEAR_SINE = 1.0e-6


def add(left: Vector3, right: Vector3) -> Vector3:
    return (left[0] + right[0], left[1] + right[1], left[2] + right[2])


def subtract(left: Vector3, right: Vector3) -> Vector3:
    return (left[0] - right[0], left[1] - right[1], left[2] - right[2])


def scale(vector: Vector3, factor: float) -> Vector3:
    return (vector[0] * factor, vector[1] * factor, vector[2] * factor)


def cross(left: Vector3, right: Vector3) -> Vector3:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def dot(left: Vector3, right: Vector3) -> float:
    return left[0] * right[0] + left[1] * right[1] + left[2] * right[2]


def length(vector: Vector3) -> float:
    return sqrt(vector[0] * vector[0] + vector[1] * vector[1] + vector[2] * vector[2])


def normalize(vector: Vector3) -> Vector3:
    vector_length = length(vector)
    if vector_length <= EPSILON:
        return (0.0, 0.0, 0.0)
    return scale(vector, 1.0 / vector_length)


def angle_between(left: Vector3, right: Vector3) -> float:
    left_normal = normalize(left)
    right_normal = normalize(right)
    if length(left_normal) <= EPSILON or length(right_normal) <= EPSILON:
        return 0.0
    cosine = max(-1.0, min(1.0, dot(left_normal, right_normal)))
    return acos(cosine)


def average(points: tuple[Vector3, ...]) -> Vector3:
    if not points:
        return (0.0, 0.0, 0.0)
    total = (0.0, 0.0, 0.0)
    for point in points:
        total = add(total, point)
    return scale(total, 1.0 / len(points))


def triangle_area_normal_centroid(
    first: Vector3,
    second: Vector3,
    third: Vector3,
) -> tuple[float, Vector3, Vector3]:
    area_vector = cross(subtract(second, first), subtract(third, first))
    area = 0.5 * length(area_vector)
    centroid = scale(add(add(first, second), third), 1.0 / 3.0)
    return area, area_vector, centroid


def polyline_plane_normal(points: tuple[Vector3, ...]) -> Vector3 | None:
    """Unit normal of the plane a polyline lies in, or None when it is collinear.

    Estimate: the cross products of consecutive segment vectors, each flipped to
    agree with the largest one, summed and normalized. Pairs whose sine is
    below COLLINEAR_SINE do not take part.
    """

    vectors = []
    for start, end in zip(points, points[1:]):
        vector = subtract(end, start)
        if length(vector) > EPSILON:
            vectors.append(vector)
    crosses = []
    for first, second in zip(vectors, vectors[1:]):
        product = cross(first, second)
        if length(product) > COLLINEAR_SINE * length(first) * length(second):
            crosses.append(product)
    if not crosses:
        return None
    reference = max(crosses, key=length)
    total = (0.0, 0.0, 0.0)
    for product in crosses:
        total = add(total, product if dot(product, reference) >= 0.0 else scale(product, -1.0))
    if length(total) <= EPSILON:
        return None
    return normalize(total)


def max_plane_distance(points: tuple[Vector3, ...], normal: Vector3 | None) -> float:
    """Largest distance of a point from the plane through their mean with this normal."""

    if normal is None or not points:
        return 0.0
    center = average(points)
    return max(abs(dot(subtract(point, center), normal)) for point in points)


def max_line_distance(points: tuple[Vector3, ...], start: Vector3, end: Vector3) -> float:
    """Largest distance of a point from the line through start and end.

    When start and end coincide, the distance is measured from start.
    """

    if not points:
        return 0.0
    axis = subtract(end, start)
    axis_length = length(axis)
    if axis_length <= EPSILON:
        return max(length(subtract(point, start)) for point in points)
    unit = scale(axis, 1.0 / axis_length)
    return max(length(cross(subtract(point, start), unit)) for point in points)


def plane_tilt(plane_normal: Vector3, surface_normal: Vector3) -> float | None:
    """Angle between a surface normal and a plane: asin(|dot|); None for a zero normal."""

    unit = normalize(surface_normal)
    if length(unit) <= EPSILON:
        return None
    return asin(min(1.0, abs(dot(plane_normal, unit))))
