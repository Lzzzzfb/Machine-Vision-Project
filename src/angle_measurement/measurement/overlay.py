from __future__ import annotations

import cv2
import numpy as np

from angle_measurement.models import LineModel, MeasurementResult, RotatedRoi
from angle_measurement.recipe import MeasurementRecipe


def _line_segment(line: LineModel, width: int, height: int) -> tuple[tuple[int, int], tuple[int, int]]:
    scale = float(max(width, height) * 2)
    first = line.point - line.direction * scale
    second = line.point + line.direction * scale
    return tuple(np.rint(first).astype(int)), tuple(np.rint(second).astype(int))


def _draw_roi(canvas: np.ndarray, roi: RotatedRoi, color: tuple[int, int, int]) -> None:
    corners = np.rint(roi.corners()).astype(np.int32).reshape((-1, 1, 2))
    cv2.polylines(canvas, [corners], True, color, 1, cv2.LINE_AA)


def draw_measurement_overlay(
    image: np.ndarray,
    recipe: MeasurementRecipe,
    result: MeasurementResult,
) -> np.ndarray:
    if image.ndim == 2:
        canvas = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    else:
        canvas = image[:, :, :3].copy()
    height, width = canvas.shape[:2]
    _draw_roi(canvas, recipe.slit.roi, (255, 160, 0))
    _draw_roi(canvas, recipe.platform.roi, (0, 200, 255))

    if result.line_slit is not None:
        cv2.line(canvas, *_line_segment(result.line_slit, width, height), (255, 80, 0), 2, cv2.LINE_AA)
        if result.slit_edge_points is not None:
            for point, inlier in zip(
                result.slit_edge_points,
                result.line_slit.inlier_mask,
                strict=True,
            ):
                cv2.circle(
                    canvas,
                    tuple(np.rint(point).astype(int)),
                    2,
                    (80, 255, 80) if inlier else (80, 80, 255),
                    -1,
                    cv2.LINE_AA,
                )
    if result.line_platform is not None:
        cv2.line(
            canvas,
            *_line_segment(result.line_platform, width, height),
            (0, 220, 255),
            2,
            cv2.LINE_AA,
        )
        if result.platform_edge_points is not None:
            for point, inlier in zip(
                result.platform_edge_points,
                result.line_platform.inlier_mask,
                strict=True,
            ):
                cv2.circle(
                    canvas,
                    tuple(np.rint(point).astype(int)),
                    2,
                    (80, 255, 80) if inlier else (80, 80, 255),
                    -1,
                    cv2.LINE_AA,
                )
    if result.intersection is not None:
        point = tuple(np.rint(result.intersection).astype(int))
        if 0 <= point[0] < width and 0 <= point[1] < height:
            cv2.drawMarker(canvas, point, (0, 0, 255), cv2.MARKER_CROSS, 18, 2)

    if result.valid:
        text = f"Angle: {result.angle_deg:.4f} deg  Confidence: {result.confidence:.2f}"
        color = (20, 220, 20)
    else:
        text = "INVALID - see failure_reasons in CSV/JSON"
        color = (0, 0, 255)
    calibration_text = "calibrated" if result.calibrated else "UNCALIBRATED"
    cv2.rectangle(canvas, (8, 8), (min(width - 8, 900), 70), (0, 0, 0), -1)
    cv2.putText(canvas, text, (18, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2, cv2.LINE_AA)
    cv2.putText(
        canvas,
        calibration_text,
        (18, 59),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 180, 255) if not result.calibrated else (180, 255, 180),
        1,
        cv2.LINE_AA,
    )
    return canvas
