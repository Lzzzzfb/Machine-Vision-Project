from __future__ import annotations

from pathlib import Path
from typing import Iterable

import cv2
import numpy as np

from angle_measurement.measurement.edge import to_gray_u8

from .model import CalibrationData


class CalibrationError(RuntimeError):
    pass


def detect_checkerboard(
    image: np.ndarray,
    inner_corners: tuple[int, int] = (9, 6),
) -> np.ndarray | None:
    gray = to_gray_u8(image)
    flags = cv2.CALIB_CB_NORMALIZE_IMAGE | cv2.CALIB_CB_EXHAUSTIVE
    found, corners = cv2.findChessboardCornersSB(gray, inner_corners, flags=flags)
    if not found or corners is None:
        return None
    return corners.reshape(-1, 2).astype(np.float32)


def _object_points(inner_corners: tuple[int, int], square_size_mm: float) -> np.ndarray:
    columns, rows = inner_corners
    points = np.zeros((columns * rows, 3), dtype=np.float32)
    points[:, :2] = np.mgrid[0:columns, 0:rows].T.reshape(-1, 2)
    points[:, :2] *= float(square_size_mm)
    return points


def calibrate_from_images(
    image_paths: Iterable[str | Path],
    square_size_mm: float,
    inner_corners: tuple[int, int] = (9, 6),
    minimum_images: int = 8,
) -> CalibrationData:
    if square_size_mm <= 0:
        raise ValueError("square_size_mm must be positive")
    object_template = _object_points(inner_corners, square_size_mm)
    object_points: list[np.ndarray] = []
    image_points: list[np.ndarray] = []
    accepted_paths: list[str] = []
    image_size: tuple[int, int] | None = None

    for path_like in image_paths:
        path = Path(path_like)
        image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        if image is None:
            continue
        current_size = (int(image.shape[1]), int(image.shape[0]))
        if image_size is None:
            image_size = current_size
        elif current_size != image_size:
            raise CalibrationError(
                f"标定图像分辨率不一致: {path.name} 为 {current_size}，预期 {image_size}"
            )
        corners = detect_checkerboard(image, inner_corners)
        if corners is None:
            continue
        object_points.append(object_template.copy())
        image_points.append(corners.reshape(-1, 1, 2))
        accepted_paths.append(str(path))

    if image_size is None:
        raise CalibrationError("没有可读取的标定图像")
    if len(image_points) < minimum_images:
        raise CalibrationError(
            f"有效棋盘图像不足: {len(image_points)} < {minimum_images}"
        )

    rms, camera_matrix, distortion, rotations, translations = cv2.calibrateCamera(
        object_points,
        image_points,
        image_size,
        None,
        None,
    )
    per_view_errors: list[float] = []
    for object_set, observed, rotation, translation in zip(
        object_points,
        image_points,
        rotations,
        translations,
        strict=True,
    ):
        projected, _ = cv2.projectPoints(
            object_set,
            rotation,
            translation,
            camera_matrix,
            distortion,
        )
        error = cv2.norm(observed, projected, cv2.NORM_L2) / np.sqrt(len(projected))
        per_view_errors.append(float(error))

    return CalibrationData(
        camera_matrix=camera_matrix,
        distortion_coefficients=distortion,
        image_size=image_size,
        rms_reprojection_error=float(rms),
        square_size_mm=float(square_size_mm),
        inner_corners=inner_corners,
        per_view_errors=per_view_errors,
        source_images=accepted_paths,
    )
