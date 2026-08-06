from __future__ import annotations

from dataclasses import replace

import numpy as np

from angle_measurement.calibration.model import CalibrationData
from angle_measurement.models import LineFitConfig, LineModel, WorldLineModel

from .line import LineFitError, fit_line_ransac, fit_total_least_squares


class PlaneProjectionError(RuntimeError):
    pass


def backproject_pixels_to_parallel_plane(
    pixels: np.ndarray,
    calibration: CalibrationData,
    height_mm: float,
) -> np.ndarray:
    """Intersect rectified pixel rays with the platform plane offset toward the camera."""

    pose = calibration.platform_pose
    if pose is None:
        raise PlaneProjectionError("缺少平台姿态标定")
    pixels = np.asarray(pixels, dtype=np.float64)
    if pixels.ndim != 2 or pixels.shape[1] != 2 or len(pixels) < 2:
        raise PlaneProjectionError("反投影至少需要两个二维点")
    if height_mm < 0 or not np.isfinite(height_mm):
        raise PlaneProjectionError("高度差必须是非负有限数")

    homogeneous = np.column_stack((pixels, np.ones(len(pixels), dtype=np.float64)))
    rays_camera = (np.linalg.inv(calibration.camera_matrix) @ homogeneous.T).T
    rotation = pose.rotation_matrix
    rays_world = (rotation.T @ rays_camera.T).T
    camera_center = pose.camera_center_world
    normal = pose.platform_normal_toward_camera
    plane_point = normal * float(height_mm)
    denominators = rays_world @ normal
    if np.any(np.abs(denominators) < 1e-10):
        raise PlaneProjectionError("像素射线与目标平面近似平行")
    numerator = float(np.dot(plane_point - camera_center, normal))
    distances = numerator / denominators
    if np.any(distances <= 0) or not np.all(np.isfinite(distances)):
        raise PlaneProjectionError("目标平面交点位于相机后方或数值无效")
    points = camera_center[None, :] + distances[:, None] * rays_world
    if not np.all(np.isfinite(points)):
        raise PlaneProjectionError("反投影结果包含非有限数")
    return points


def fit_world_line(
    image_line: LineModel,
    world_points_3d: np.ndarray,
    config: LineFitConfig,
) -> tuple[WorldLineModel, np.ndarray]:
    """Refit backprojected points in platform XY with pixel thresholds scaled to mm."""

    xy = np.asarray(world_points_3d, dtype=np.float64)[:, :2]
    try:
        centre, direction = fit_total_least_squares(xy)
    except LineFitError as exc:
        raise PlaneProjectionError(str(exc)) from exc
    projections = (xy - centre) @ direction
    rough_span_mm = float(np.ptp(projections))
    scale_mm_per_px = rough_span_mm / max(image_line.span_px, 1e-9)
    if scale_mm_per_px <= 0 or not np.isfinite(scale_mm_per_px):
        raise PlaneProjectionError("无法估计反投影毫米比例")
    world_config = replace(
        config,
        ransac_threshold_px=max(config.ransac_threshold_px * scale_mm_per_px, 1e-6),
        min_span_px=max(config.min_span_px * scale_mm_per_px, 1e-6),
        max_rms_px=max(config.max_rms_px * scale_mm_per_px, 1e-6),
    )
    try:
        fitted = fit_line_ransac(xy, world_config)
    except LineFitError as exc:
        raise PlaneProjectionError(str(exc)) from exc
    world = WorldLineModel(
        point_mm=fitted.point,
        direction=fitted.direction,
        rms_mm=fitted.rms_px,
        max_residual_mm=fitted.max_residual_px,
        span_mm=fitted.span_px,
        inlier_ratio=fitted.inlier_ratio,
        inlier_count=int(np.count_nonzero(fitted.inlier_mask)),
    )
    return world, fitted.inlier_mask
