from __future__ import annotations

import numpy as np

from angle_measurement.models import LineFitConfig, LineModel


class LineFitError(RuntimeError):
    pass


def _canonical_direction(direction: np.ndarray) -> np.ndarray:
    direction = np.asarray(direction, dtype=np.float64)
    norm = float(np.linalg.norm(direction))
    if norm <= 1e-12:
        raise LineFitError("直线方向向量长度为零")
    direction = direction / norm
    if direction[0] < 0 or (abs(direction[0]) < 1e-12 and direction[1] < 0):
        direction = -direction
    return direction


def orthogonal_distances(points: np.ndarray, point: np.ndarray, direction: np.ndarray) -> np.ndarray:
    normal = np.array([-direction[1], direction[0]], dtype=np.float64)
    return np.abs((points - point) @ normal)


def fit_total_least_squares(points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    points = np.asarray(points, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 2 or len(points) < 2:
        raise LineFitError("总最小二乘至少需要两个二维点")
    if not np.all(np.isfinite(points)):
        raise LineFitError("拟合点包含非有限数值")
    center = points.mean(axis=0)
    centered = points - center
    covariance = centered.T @ centered
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    if float(eigenvalues[-1]) <= 1e-12:
        raise LineFitError("拟合点没有足够的空间跨度")
    direction = _canonical_direction(eigenvectors[:, -1])
    return center, direction


def fit_line_ransac(points: np.ndarray, config: LineFitConfig) -> LineModel:
    points = np.asarray(points, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 2:
        raise LineFitError("拟合点必须为 N×2 数组")
    if len(points) < config.min_points:
        raise LineFitError(f"有效边缘点不足: {len(points)} < {config.min_points}")

    rng = np.random.default_rng(config.random_seed)
    best_mask: np.ndarray | None = None
    best_count = 0
    best_median = np.inf
    for _ in range(config.ransac_iterations):
        indices = rng.choice(len(points), size=2, replace=False)
        delta = points[indices[1]] - points[indices[0]]
        norm = float(np.linalg.norm(delta))
        if norm <= 1e-9:
            continue
        direction = delta / norm
        distances = orthogonal_distances(points, points[indices[0]], direction)
        mask = distances <= config.ransac_threshold_px
        count = int(np.count_nonzero(mask))
        if count < 2:
            continue
        median = float(np.median(distances[mask]))
        if count > best_count or (count == best_count and median < best_median):
            best_mask = mask
            best_count = count
            best_median = median

    if best_mask is None or best_count < config.min_points:
        raise LineFitError("RANSAC 未找到满足最小点数的直线")

    point, direction = fit_total_least_squares(points[best_mask])
    distances = orthogonal_distances(points, point, direction)
    inlier_mask = distances <= config.ransac_threshold_px
    if np.count_nonzero(inlier_mask) >= 2:
        point, direction = fit_total_least_squares(points[inlier_mask])
        distances = orthogonal_distances(points, point, direction)
        inlier_mask = distances <= config.ransac_threshold_px

    inlier_count = int(np.count_nonzero(inlier_mask))
    if inlier_count < config.min_points:
        raise LineFitError("直线精修后的内点数量不足")
    inlier_points = points[inlier_mask]
    residuals = orthogonal_distances(inlier_points, point, direction)
    projections = (inlier_points - point) @ direction
    span = float(projections.max() - projections.min())
    return LineModel(
        point=point,
        direction=direction,
        inlier_mask=inlier_mask,
        rms_px=float(np.sqrt(np.mean(np.square(residuals)))),
        max_residual_px=float(np.max(residuals)),
        span_px=span,
        inlier_ratio=inlier_count / len(points),
    )
