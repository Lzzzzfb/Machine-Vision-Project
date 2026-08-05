from __future__ import annotations

import cv2
import numpy as np

from angle_measurement.models import EdgeExtractionConfig, EdgePointSet, EdgePolarity, RotatedRoi


class EdgeExtractionError(RuntimeError):
    pass


def to_gray_u8(image: np.ndarray) -> np.ndarray:
    if image is None or image.size == 0:
        raise EdgeExtractionError("图像为空")
    if image.ndim == 2:
        gray = image
    elif image.ndim == 3 and image.shape[2] == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    elif image.ndim == 3 and image.shape[2] == 4:
        gray = cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
    else:
        raise EdgeExtractionError(f"不支持的图像形状: {image.shape}")

    if gray.dtype == np.uint8:
        return np.ascontiguousarray(gray)
    finite = np.asarray(gray, dtype=np.float64)
    if not np.all(np.isfinite(finite)):
        raise EdgeExtractionError("图像包含非有限数值")
    minimum = float(finite.min())
    maximum = float(finite.max())
    if maximum <= minimum:
        return np.zeros(gray.shape, dtype=np.uint8)
    return np.clip((finite - minimum) * 255.0 / (maximum - minimum), 0, 255).astype(np.uint8)


def roi_is_inside_image(roi: RotatedRoi, shape: tuple[int, ...], margin: float = 1.5) -> bool:
    height, width = shape[:2]
    corners = roi.corners()
    return bool(
        np.all(corners[:, 0] >= margin)
        and np.all(corners[:, 0] <= width - 1 - margin)
        and np.all(corners[:, 1] >= margin)
        and np.all(corners[:, 1] <= height - 1 - margin)
    )


def _parabolic_peak(values: np.ndarray, index: int) -> float:
    if index <= 0 or index >= len(values) - 1:
        return float(index)
    left, center, right = (float(values[index - 1]), float(values[index]), float(values[index + 1]))
    denominator = left - 2.0 * center + right
    if abs(denominator) < 1e-12:
        return float(index)
    offset = 0.5 * (left - right) / denominator
    return float(index) + float(np.clip(offset, -1.0, 1.0))


def extract_edge_points(
    image: np.ndarray,
    roi: RotatedRoi,
    config: EdgeExtractionConfig,
) -> EdgePointSet:
    gray = to_gray_u8(image)
    if not roi_is_inside_image(roi, gray.shape):
        raise EdgeExtractionError("测量带超出图像边界")

    scan_count = max(2, int(np.floor(roi.length / config.scan_step_px)) + 1)
    profile_count = max(7, int(np.floor(roi.width / config.profile_step_px)) + 1)
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

    gradient = np.gradient(profiles, config.profile_step_px, axis=1)
    if config.polarity == EdgePolarity.DARK_TO_LIGHT:
        score = gradient
    elif config.polarity == EdgePolarity.LIGHT_TO_DARK:
        score = -gradient
    else:
        score = np.abs(gradient)

    if config.center_bias:
        normalized_offset = np.abs(across) / max(roi.width / 2.0, 1e-9)
        score = score * (1.0 - config.center_bias * normalized_offset[None, :])

    score[:, :2] = -np.inf
    score[:, -2:] = -np.inf
    points: list[np.ndarray] = []
    strengths: list[float] = []
    for row_index, row in enumerate(score):
        peak_index = int(np.argmax(row))
        strength = float(row[peak_index])
        if not np.isfinite(strength) or strength < config.min_gradient:
            continue
        peak_position = _parabolic_peak(row, peak_index)
        across_position = float(
            np.interp(peak_position, np.arange(profile_count, dtype=np.float64), across)
        )
        point = center + along[row_index] * direction + across_position * normal
        points.append(point)
        strengths.append(strength)

    if not points:
        return EdgePointSet(
            points=np.empty((0, 2), dtype=np.float64),
            strengths=np.empty((0,), dtype=np.float64),
            attempted_profiles=scan_count,
        )
    return EdgePointSet(
        points=np.asarray(points, dtype=np.float64),
        strengths=np.asarray(strengths, dtype=np.float64),
        attempted_profiles=scan_count,
    )
