from __future__ import annotations

import math

import numpy as np

from angle_measurement.models import LineModel


def angle_between_directions(first: np.ndarray, second: np.ndarray) -> float:
    first = np.asarray(first, dtype=np.float64)
    second = np.asarray(second, dtype=np.float64)
    first_norm = float(np.linalg.norm(first))
    second_norm = float(np.linalg.norm(second))
    if first_norm <= 1e-12 or second_norm <= 1e-12:
        raise ValueError("Direction vectors must be non-zero")
    cosine = abs(float(np.dot(first / first_norm, second / second_norm)))
    return math.degrees(math.acos(float(np.clip(cosine, 0.0, 1.0))))


def angle_between_lines(first: LineModel, second: LineModel) -> float:
    return angle_between_directions(first.direction, second.direction)


def line_intersection(first: LineModel, second: LineModel) -> np.ndarray | None:
    matrix = np.column_stack((first.direction, -second.direction))
    determinant = float(np.linalg.det(matrix))
    if abs(determinant) < 1e-9:
        return None
    parameters = np.linalg.solve(matrix, second.point - first.point)
    return first.point + parameters[0] * first.direction
