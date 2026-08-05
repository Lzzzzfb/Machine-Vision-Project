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

    def __post_init__(self) -> None:
        if self.min_image_stddev < 0:
            raise ValueError("min_image_stddev cannot be negative")
        if not 0 <= self.max_saturated_fraction <= 1:
            raise ValueError("max_saturated_fraction must be in [0, 1]")


@dataclass
class EdgePointSet:
    points: np.ndarray
    strengths: np.ndarray
    attempted_profiles: int

    @property
    def count(self) -> int:
        return int(len(self.points))


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
class MeasurementResult:
    valid: bool
    calibrated: bool
    angle_deg: float | None = None
    confidence: float = 0.0
    line_slit: LineModel | None = None
    line_platform: LineModel | None = None
    slit_edge_points: np.ndarray | None = None
    platform_edge_points: np.ndarray | None = None
    intersection: np.ndarray | None = None
    failure_reasons: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "calibrated": self.calibrated,
            "angle_deg": self.angle_deg,
            "confidence": self.confidence,
            "line_slit": self.line_slit.to_dict() if self.line_slit else None,
            "line_platform": self.line_platform.to_dict() if self.line_platform else None,
            "slit_edge_point_count": 0 if self.slit_edge_points is None else len(self.slit_edge_points),
            "platform_edge_point_count": 0
            if self.platform_edge_points is None
            else len(self.platform_edge_points),
            "intersection": self.intersection.tolist() if self.intersection is not None else None,
            "failure_reasons": list(self.failure_reasons),
            "diagnostics": self.diagnostics,
        }
