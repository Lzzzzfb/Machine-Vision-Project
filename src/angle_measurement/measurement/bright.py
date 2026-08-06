from __future__ import annotations

import cv2
import numpy as np

from angle_measurement.models import (
    BrightLineExtractionConfig,
    BrightLinePointSet,
    RotatedRoi,
)

from .edge import EdgeExtractionError, roi_is_inside_image, to_gray_u8


def _subpixel_peak(values: np.ndarray, index: int) -> float:
    if index <= 0 or index >= len(values) - 1:
        return float(index)
    left, center, right = map(float, values[index - 1 : index + 2])
    denominator = left - 2.0 * center + right
    if abs(denominator) < 1e-12:
        return float(index)
    offset = 0.5 * (left - right) / denominator
    return float(index) + float(np.clip(offset, -1.0, 1.0))


def extract_bright_line_points(
    image: np.ndarray,
    roi: RotatedRoi,
    config: BrightLineExtractionConfig,
) -> BrightLinePointSet:
    """Sample profiles normal to a slit and return paired-edge centre points."""

    gray = to_gray_u8(image)
    if not roi_is_inside_image(roi, gray.shape):
        raise EdgeExtractionError("狭缝测量带超出图像边界")

    scan_count = max(2, int(np.floor(roi.length / config.scan_step_px)) + 1)
    profile_count = max(9, int(np.floor(roi.width / config.profile_step_px)) + 1)
    along = np.linspace(-roi.length / 2.0, roi.length / 2.0, scan_count, dtype=np.float64)
    across = np.linspace(-roi.width / 2.0, roi.width / 2.0, profile_count, dtype=np.float64)
    center = roi.center
    direction = roi.direction
    normal = roi.normal
    map_x = (
        center[0]
        + along[:, None] * direction[0]
        + across[None, :] * normal[0]
    ).astype(np.float32)
    map_y = (
        center[1]
        + along[:, None] * direction[1]
        + across[None, :] * normal[1]
    ).astype(np.float32)
    profiles = cv2.remap(
        gray,
        map_x,
        map_y,
        interpolation=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    ).astype(np.float64)
    if config.gaussian_sigma > 0:
        profiles = cv2.GaussianBlur(
            profiles,
            (0, 0),
            sigmaX=config.gaussian_sigma / config.profile_step_px,
            sigmaY=0.35,
        )

    gradients = np.gradient(profiles, config.profile_step_px, axis=1)
    centre_weight = 1.0 - config.center_bias * (
        np.abs(across) / max(roi.width / 2.0, 1e-9)
    )
    margin = max(3, int(np.ceil(config.min_width_px / config.profile_step_px / 2.0)) + 1)
    points: list[np.ndarray] = []
    strengths: list[float] = []
    widths: list[float] = []
    contrasts: list[float] = []

    for row_index, (profile, gradient) in enumerate(zip(profiles, gradients, strict=True)):
        peak_score = profile * centre_weight
        peak_score[:margin] = -np.inf
        peak_score[-margin:] = -np.inf
        peak_index = int(np.argmax(peak_score))
        if peak_index <= 2 or peak_index >= profile_count - 3:
            continue

        left_score = gradient.copy()
        right_score = -gradient.copy()
        left_score[peak_index:] = -np.inf
        right_score[: peak_index + 1] = -np.inf
        left_score[:1] = -np.inf
        right_score[-1:] = -np.inf
        left_index = int(np.argmax(left_score))
        right_index = int(np.argmax(right_score))
        left_strength = float(left_score[left_index])
        right_strength = float(right_score[right_index])
        if (
            not np.isfinite(left_strength)
            or not np.isfinite(right_strength)
            or min(left_strength, right_strength) < config.min_gradient
        ):
            continue

        left_position = float(
            np.interp(
                _subpixel_peak(left_score, left_index),
                np.arange(profile_count, dtype=np.float64),
                across,
            )
        )
        right_position = float(
            np.interp(
                _subpixel_peak(right_score, right_index),
                np.arange(profile_count, dtype=np.float64),
                across,
            )
        )
        width_px = right_position - left_position
        if not config.min_width_px <= width_px <= config.max_width_px:
            continue
        symmetry = min(left_strength, right_strength) / max(left_strength, right_strength)
        if symmetry < config.min_edge_symmetry:
            continue

        side_values = np.concatenate((profile[: max(left_index, 1)], profile[right_index + 1 :]))
        background = float(np.median(side_values)) if len(side_values) else float(np.min(profile))
        contrast = float(profile[peak_index] - background)
        if contrast < config.min_contrast:
            continue

        centre_position = 0.5 * (left_position + right_position)
        points.append(center + along[row_index] * direction + centre_position * normal)
        strengths.append(min(left_strength, right_strength))
        widths.append(width_px)
        contrasts.append(contrast)

    return BrightLinePointSet(
        points=np.asarray(points, dtype=np.float64).reshape(-1, 2),
        strengths=np.asarray(strengths, dtype=np.float64),
        attempted_profiles=scan_count,
        widths_px=np.asarray(widths, dtype=np.float64),
        contrasts=np.asarray(contrasts, dtype=np.float64),
    )
