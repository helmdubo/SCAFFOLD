"""
Layer: 2 - Geometry

Rules:
- Low-level vector measurement functions only.
- No topology building, relation derivation, feature interpretation, or solve logic.
- No semantic classification.
"""

from __future__ import annotations

from math import sqrt

from scaffold_core.layer_2_geometry.facts import Vector3


EPSILON = 1.0e-9


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


def length(vector: Vector3) -> float:
    return sqrt(vector[0] * vector[0] + vector[1] * vector[1] + vector[2] * vector[2])


def normalize(vector: Vector3) -> Vector3:
    vector_length = length(vector)
    if vector_length <= EPSILON:
        return (0.0, 0.0, 0.0)
    return scale(vector, 1.0 / vector_length)


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
