from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from math import cos, radians, sin
from typing import Any

import numpy as np


class EdgePolarity(str, Enum):
    AUTO = "auto"
    DARK_TO_LIGHT = "dark_to_light"
    LIGHT_TO_DARK = "light_to_dark"


@dataclass(frozen=True)
class RotatedRoi:
    """A rectangular measurement band centered on an expected edge."""

    center_x: float
    center_y: float
    length: float
    width: float
    angle_deg: float

    def __post_init__(self) -> None:
        values = (self.center_x, self.center_y, self.length, self.width, self.angle_deg)
        if not all(np.isfinite(values)):
            raise ValueError("ROI values must be finite")
        if self.length <= 0 or self.width <= 0:
            raise ValueError("ROI length and width must be positive")

    @property
    def direction(self) -> np.ndarray:
        angle = radians(self.angle_deg)
        direction = np.array([cos(angle), sin(angle)], dtype=np.float64)
        direction[np.abs(direction) < 1e-12] = 0.0
        return direction / np.linalg.norm(direction)

    @property
    def normal(self) -> np.ndarray:
        direction = self.direction
        return np.array([-direction[1], direction[0]], dtype=np.float64)

    @property
    def center(self) -> np.ndarray:
        return np.array([self.center_x, self.center_y], dtype=np.float64)

    def corners(self) -> np.ndarray:
        direction = self.direction * (self.length / 2.0)
        normal = self.normal * (self.width / 2.0)
        center = self.center
        return np.array(
            [
                center - direction - normal,
                center + direction - normal,
                center + direction + normal,
                center - direction + normal,
            ],
            dtype=np.float64,
        )

    def to_dict(self) -> dict[str, float]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RotatedRoi":
        keys = ("center_x", "center_y", "length", "width", "angle_deg")
        return cls(**{key: float(data[key]) for key in keys})


@dataclass(frozen=True)
class EdgeExtractionConfig:
    polarity: EdgePolarity = EdgePolarity.AUTO
    scan_step_px: float = 3.0
    profile_step_px: float = 0.25
    gaussian_sigma: float = 1.0
    min_gradient: float = 8.0
    center_bias: float = 0.15
    max_direction_deviation_deg: float = 15.0

    def __post_init__(self) -> None:
        if self.scan_step_px <= 0 or self.profile_step_px <= 0:
            raise ValueError("Scan and profile steps must be positive")
        if self.gaussian_sigma < 0 or self.min_gradient < 0:
            raise ValueError("Sigma and minimum gradient cannot be negative")
        if not 0 <= self.center_bias <= 1:
            raise ValueError("center_bias must be in [0, 1]")
        if not 0 < self.max_direction_deviation_deg <= 90:
            raise ValueError("max_direction_deviation_deg must be in (0, 90]")


@dataclass(frozen=True)
class BrightLineExtractionConfig:
    """Configuration for locating the centre between two sides of a bright slit."""

    scan_step_px: float = 3.0
    profile_step_px: float = 0.25
    gaussian_sigma: float = 1.0
    min_gradient: float = 6.0
    min_contrast: float = 12.0
    min_width_px: float = 1.0
    max_width_px: float = 30.0
    center_bias: float = 0.15
    min_edge_symmetry: float = 0.25
    max_direction_deviation_deg: float = 15.0

    def __post_init__(self) -> None:
        if self.scan_step_px <= 0 or self.profile_step_px <= 0:
            raise ValueError("Scan and profile steps must be positive")
        if self.gaussian_sigma < 0 or self.min_gradient < 0 or self.min_contrast < 0:
            raise ValueError("Bright-line thresholds cannot be negative")
        if self.min_width_px <= 0 or self.max_width_px <= self.min_width_px:
            raise ValueError("Bright-line width range is invalid")
        if not 0 <= self.center_bias <= 1:
            raise ValueError("center_bias must be in [0, 1]")
        if not 0 <= self.min_edge_symmetry <= 1:
            raise ValueError("min_edge_symmetry must be in [0, 1]")
        if not 0 < self.max_direction_deviation_deg <= 90:
            raise ValueError("max_direction_deviation_deg must be in (0, 90]")


@dataclass(frozen=True)
class LineFitConfig:
    ransac_threshold_px: float = 0.8
    ransac_iterations: int = 300
    min_points: int = 12
    min_inlier_ratio: float = 0.65
    min_span_px: float = 30.0
    max_rms_px: float = 0.8
    random_seed: int = 20260805

    def __post_init__(self) -> None:
        if self.ransac_threshold_px <= 0 or self.ransac_iterations <= 0:
            raise ValueError("RANSAC parameters must be positive")
        if self.min_points < 2:
            raise ValueError("At least two points are required")
        if not 0 < self.min_inlier_ratio <= 1:
            raise ValueError("min_inlier_ratio must be in (0, 1]")
        if self.min_span_px <= 0 or self.max_rms_px <= 0:
            raise ValueError("Line quality thresholds must be positive")


@dataclass(frozen=True)
class QualityConfig:
    min_image_stddev: float = 3.0
    max_saturated_fraction: float = 0.95
    max_platform_parallelism_deg: float = 1.0
    min_platform_edge_separation_px: float = 20.0
    max_intrinsic_rms_px: float = 0.5
    max_pose_rms_px: float = 0.5

    def __post_init__(self) -> None:
        if self.min_image_stddev < 0:
            raise ValueError("min_image_stddev cannot be negative")
        if not 0 <= self.max_saturated_fraction <= 1:
            raise ValueError("max_saturated_fraction must be in [0, 1]")
        if not 0 < self.max_platform_parallelism_deg <= 45:
            raise ValueError("max_platform_parallelism_deg must be in (0, 45]")
        if self.min_platform_edge_separation_px <= 0:
            raise ValueError("min_platform_edge_separation_px must be positive")
        if self.max_intrinsic_rms_px <= 0 or self.max_pose_rms_px <= 0:
            raise ValueError("Calibration RMS thresholds must be positive")


@dataclass
class EdgePointSet:
    points: np.ndarray
    strengths: np.ndarray
    attempted_profiles: int

    @property
    def count(self) -> int:
        return int(len(self.points))


@dataclass
class BrightLinePointSet(EdgePointSet):
    widths_px: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.float64))
    contrasts: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.float64))


@dataclass
class LineModel:
    point: np.ndarray
    direction: np.ndarray
    inlier_mask: np.ndarray
    rms_px: float
    max_residual_px: float
    span_px: float
    inlier_ratio: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "point": self.point.tolist(),
            "direction": self.direction.tolist(),
            "rms_px": self.rms_px,
            "max_residual_px": self.max_residual_px,
            "span_px": self.span_px,
            "inlier_ratio": self.inlier_ratio,
            "inlier_count": int(np.count_nonzero(self.inlier_mask)),
        }


@dataclass
class WorldLineModel:
    point_mm: np.ndarray
    direction: np.ndarray
    rms_mm: float
    max_residual_mm: float
    span_mm: float
    inlier_ratio: float
    inlier_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "point_mm": self.point_mm.tolist(),
            "direction": self.direction.tolist(),
            "rms_mm": float(self.rms_mm),
            "max_residual_mm": float(self.max_residual_mm),
            "span_mm": float(self.span_mm),
            "inlier_ratio": float(self.inlier_ratio),
            "inlier_count": int(self.inlier_count),
        }


@dataclass
class MeasurementResult:
    valid: bool
    calibrated: bool
    angle_deg: float | None = None
    projected_angle_deg: float | None = None
    height_compensated: bool = False
    confidence: float = 0.0
    line_slit: LineModel | None = None
    line_platform: LineModel | None = None
    line_platform_left: LineModel | None = None
    line_platform_right: LineModel | None = None
    world_line_slit: WorldLineModel | None = None
    world_line_platform_left: WorldLineModel | None = None
    world_line_platform_right: WorldLineModel | None = None
    slit_edge_points: np.ndarray | None = None
    platform_edge_points: np.ndarray | None = None
    platform_left_edge_points: np.ndarray | None = None
    platform_right_edge_points: np.ndarray | None = None
    intersection: np.ndarray | None = None
    platform_parallelism_deg: float | None = None
    failure_reasons: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "calibrated": self.calibrated,
            "angle_deg": self.angle_deg,
            "projected_angle_deg": self.projected_angle_deg,
            "height_compensated": self.height_compensated,
            "confidence": self.confidence,
            "line_slit": self.line_slit.to_dict() if self.line_slit else None,
            "line_platform": self.line_platform.to_dict() if self.line_platform else None,
            "line_platform_left": self.line_platform_left.to_dict()
            if self.line_platform_left
            else None,
            "line_platform_right": self.line_platform_right.to_dict()
            if self.line_platform_right
            else None,
            "world_line_slit": self.world_line_slit.to_dict() if self.world_line_slit else None,
            "world_line_platform_left": self.world_line_platform_left.to_dict()
            if self.world_line_platform_left
            else None,
            "world_line_platform_right": self.world_line_platform_right.to_dict()
            if self.world_line_platform_right
            else None,
            "slit_edge_point_count": 0 if self.slit_edge_points is None else len(self.slit_edge_points),
            "platform_edge_point_count": 0
            if self.platform_edge_points is None
            else len(self.platform_edge_points),
            "platform_left_edge_point_count": 0
            if self.platform_left_edge_points is None
            else len(self.platform_left_edge_points),
            "platform_right_edge_point_count": 0
            if self.platform_right_edge_points is None
            else len(self.platform_right_edge_points),
            "intersection": self.intersection.tolist() if self.intersection is not None else None,
            "platform_parallelism_deg": self.platform_parallelism_deg,
            "failure_reasons": list(self.failure_reasons),
            "diagnostics": self.diagnostics,
        }
