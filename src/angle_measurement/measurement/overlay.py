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


def _draw_points(
    canvas: np.ndarray,
    points: np.ndarray | None,
    line: LineModel | None,
) -> None:
    if points is None or line is None or len(line.inlier_mask) != len(points):
        return
    for point, inlier in zip(points, line.inlier_mask, strict=True):
        cv2.circle(
            canvas,
            tuple(np.rint(point).astype(int)),
            2,
            (80, 255, 80) if inlier else (80, 80, 255),
            -1,
            cv2.LINE_AA,
        )


def draw_measurement_overlay(
    image: np.ndarray,
    recipe: MeasurementRecipe,
    result: MeasurementResult,
    show_rois: bool = True,
    show_auxiliary: bool = True,
) -> np.ndarray:
    if image.ndim == 2:
        canvas = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    else:
        canvas = image[:, :, :3].copy()
    height, width = canvas.shape[:2]
    if show_rois:
        _draw_roi(canvas, recipe.slit_center.roi, (0, 150, 255))
        _draw_roi(canvas, recipe.platform_left.roi, (255, 220, 0))
        _draw_roi(canvas, recipe.platform_right.roi, (220, 80, 220))

    if show_auxiliary:
        for line, color in (
            (result.line_slit, (0, 100, 255)),
            (result.line_platform_left, (255, 220, 0)),
            (result.line_platform_right, (220, 80, 220)),
            (result.line_platform, (60, 255, 255)),
        ):
            if line is not None:
                cv2.line(canvas, *_line_segment(line, width, height), color, 2, cv2.LINE_AA)
        _draw_points(canvas, result.slit_edge_points, result.line_slit)
        _draw_points(canvas, result.platform_left_edge_points, result.line_platform_left)
        _draw_points(canvas, result.platform_right_edge_points, result.line_platform_right)

    if show_auxiliary and result.intersection is not None:
        point = tuple(np.rint(result.intersection).astype(int))
        if 0 <= point[0] < width and 0 <= point[1] < height:
            cv2.drawMarker(canvas, point, (0, 0, 255), cv2.MARKER_CROSS, 18, 2)

    if result.valid and result.angle_deg is not None:
        prefix = "Compensated" if result.height_compensated else "Projected"
        text = f"{prefix} angle: {result.angle_deg:.4f} deg  Confidence: {result.confidence:.2f}"
        color = (20, 220, 20)
    elif result.projected_angle_deg is not None:
        text = f"INVALID - projected diagnostic: {result.projected_angle_deg:.4f} deg"
        color = (0, 165, 255)
    else:
        text = "INVALID - see failure_reasons in CSV/JSON"
        color = (0, 0, 255)
    if result.height_compensated:
        calibration_text = "intrinsics + platform pose + height compensation"
    elif result.calibrated:
        calibration_text = "intrinsics only - NO HEIGHT COMPENSATION"
    else:
        calibration_text = "UNCALIBRATED"
    cv2.rectangle(canvas, (8, 8), (min(width - 8, 1050), 70), (0, 0, 0), -1)
    cv2.putText(canvas, text, (18, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2, cv2.LINE_AA)
    cv2.putText(
        canvas,
        calibration_text,
        (18, 59),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (180, 255, 180) if result.height_compensated else (0, 180, 255),
        1,
        cv2.LINE_AA,
    )
    return canvas
