from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np


@dataclass
class PlatformPose:
    """World-to-camera pose of the checkerboard plane coincident with the platform."""

    rotation_vector: np.ndarray
    translation_vector: np.ndarray
    reprojection_error_px: float
    reference_image: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    def __post_init__(self) -> None:
        self.rotation_vector = np.asarray(self.rotation_vector, dtype=np.float64).reshape(3)
        self.translation_vector = np.asarray(self.translation_vector, dtype=np.float64).reshape(3)
        if not np.all(np.isfinite(self.rotation_vector)) or not np.all(
            np.isfinite(self.translation_vector)
        ):
            raise ValueError("Platform pose must contain finite values")
        if self.reprojection_error_px < 0:
            raise ValueError("Pose reprojection error cannot be negative")

    @property
    def rotation_matrix(self) -> np.ndarray:
        matrix, _ = cv2.Rodrigues(self.rotation_vector)
        return matrix

    @property
    def camera_center_world(self) -> np.ndarray:
        rotation = self.rotation_matrix
        return -rotation.T @ self.translation_vector

    @property
    def platform_normal_toward_camera(self) -> np.ndarray:
        normal = np.array([0.0, 0.0, 1.0], dtype=np.float64)
        if float(np.dot(normal, self.camera_center_world)) < 0:
            normal = -normal
        return normal

    def to_dict(self) -> dict[str, Any]:
        return {
            "rotation_vector": self.rotation_vector.tolist(),
            "translation_vector": self.translation_vector.tolist(),
            "reprojection_error_px": float(self.reprojection_error_px),
            "reference_image": self.reference_image,
            "created_at": self.created_at,
            "world_to_camera_convention": "Xc = R Xw + t",
            "platform_plane_z_mm": 0.0,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlatformPose":
        return cls(
            rotation_vector=np.asarray(data["rotation_vector"], dtype=np.float64),
            translation_vector=np.asarray(data["translation_vector"], dtype=np.float64),
            reprojection_error_px=float(data["reprojection_error_px"]),
            reference_image=str(data.get("reference_image", "")),
            created_at=str(data.get("created_at", "unknown")),
        )


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
    platform_pose: PlatformPose | None = None
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
            "version": 2,
            "created_at": self.created_at,
            "camera_matrix": self.camera_matrix.tolist(),
            "distortion_coefficients": self.distortion_coefficients.tolist(),
            "image_size": list(self.image_size),
            "rms_reprojection_error": float(self.rms_reprojection_error),
            "square_size_mm": float(self.square_size_mm),
            "inner_corners": list(self.inner_corners),
            "per_view_errors": [float(value) for value in self.per_view_errors],
            "source_images": list(self.source_images),
            "platform_pose": self.platform_pose.to_dict() if self.platform_pose else None,
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
        version = int(data.get("version", 1))
        if version not in (1, 2):
            raise ValueError("Unsupported calibration file version")
        pose_data = data.get("platform_pose") if version >= 2 else None
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
            platform_pose=PlatformPose.from_dict(pose_data) if pose_data else None,
            created_at=str(data.get("created_at", "unknown")),
        )

    @classmethod
    def load(cls, path: str | Path) -> "CalibrationData":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
