from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np


@dataclass
class CalibrationData:
    camera_matrix: np.ndarray
    distortion_coefficients: np.ndarray
    image_size: tuple[int, int]
    rms_reprojection_error: float
    square_size_mm: float
    inner_corners: tuple[int, int] = (9, 6)
    per_view_errors: list[float] = field(default_factory=list)
    source_images: list[str] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    def __post_init__(self) -> None:
        self.camera_matrix = np.asarray(self.camera_matrix, dtype=np.float64)
        self.distortion_coefficients = np.asarray(
            self.distortion_coefficients, dtype=np.float64
        ).reshape(-1)
        self.image_size = (int(self.image_size[0]), int(self.image_size[1]))
        self.inner_corners = (int(self.inner_corners[0]), int(self.inner_corners[1]))
        if self.camera_matrix.shape != (3, 3):
            raise ValueError("camera_matrix must be 3x3")
        if self.image_size[0] <= 0 or self.image_size[1] <= 0:
            raise ValueError("image_size must be positive")
        if self.square_size_mm <= 0:
            raise ValueError("square_size_mm must be positive")
        if self.inner_corners[0] < 2 or self.inner_corners[1] < 2:
            raise ValueError("inner_corners must be at least 2x2")

    def ensure_image_size(self, image: np.ndarray) -> None:
        actual = (int(image.shape[1]), int(image.shape[0]))
        if actual != self.image_size:
            raise ValueError(f"标定分辨率 {self.image_size} 与当前图像 {actual} 不一致")

    def undistort(self, image: np.ndarray) -> np.ndarray:
        self.ensure_image_size(image)
        return cv2.undistort(
            image,
            self.camera_matrix,
            self.distortion_coefficients,
            None,
            self.camera_matrix,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "created_at": self.created_at,
            "camera_matrix": self.camera_matrix.tolist(),
            "distortion_coefficients": self.distortion_coefficients.tolist(),
            "image_size": list(self.image_size),
            "rms_reprojection_error": float(self.rms_reprojection_error),
            "square_size_mm": float(self.square_size_mm),
            "inner_corners": list(self.inner_corners),
            "per_view_errors": [float(value) for value in self.per_view_errors],
            "source_images": list(self.source_images),
        }

    def save(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return destination

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CalibrationData":
        if int(data.get("version", 1)) != 1:
            raise ValueError("Unsupported calibration file version")
        return cls(
            camera_matrix=np.asarray(data["camera_matrix"], dtype=np.float64),
            distortion_coefficients=np.asarray(
                data["distortion_coefficients"], dtype=np.float64
            ),
            image_size=tuple(data["image_size"]),
            rms_reprojection_error=float(data["rms_reprojection_error"]),
            square_size_mm=float(data["square_size_mm"]),
            inner_corners=tuple(data.get("inner_corners", (9, 6))),
            per_view_errors=[float(value) for value in data.get("per_view_errors", [])],
            source_images=[str(value) for value in data.get("source_images", [])],
            created_at=str(data.get("created_at", "unknown")),
        )

    @classmethod
    def load(cls, path: str | Path) -> "CalibrationData":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
