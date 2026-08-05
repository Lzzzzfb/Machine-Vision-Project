from __future__ import annotations

import math
from typing import Protocol

import numpy as np

from angle_measurement.models import EdgePointSet, LineModel, MeasurementResult
from angle_measurement.recipe import BandConfig, MeasurementRecipe

from .angle import angle_between_directions, angle_between_lines, line_intersection
from .edge import EdgeExtractionError, extract_edge_points, to_gray_u8
from .line import LineFitError, fit_line_ransac


class CalibrationLike(Protocol):
    @property
    def image_size(self) -> tuple[int, int]: ...

    def undistort(self, image: np.ndarray) -> np.ndarray: ...


class AngleMeasurementService:
    def __init__(
        self,
        recipe: MeasurementRecipe,
        calibration: CalibrationLike | None = None,
    ) -> None:
        self.recipe = recipe
        self.calibration = calibration

    def _prepare(self, image: np.ndarray) -> tuple[np.ndarray, bool]:
        gray = to_gray_u8(image)
        if self.calibration is None:
            return gray, False
        expected = tuple(self.calibration.image_size)
        actual = (gray.shape[1], gray.shape[0])
        if actual != expected:
            raise ValueError(f"标定分辨率 {expected} 与当前图像 {actual} 不一致")
        return to_gray_u8(self.calibration.undistort(gray)), True

    def _image_failures(self, gray: np.ndarray) -> tuple[list[str], dict[str, float]]:
        stddev = float(np.std(gray))
        saturated_fraction = float(np.mean((gray <= 1) | (gray >= 254)))
        diagnostics = {
            "image_stddev": stddev,
            "saturated_fraction": saturated_fraction,
        }
        failures: list[str] = []
        if stddev < self.recipe.quality.min_image_stddev:
            failures.append("图像对比度不足")
        if saturated_fraction > self.recipe.quality.max_saturated_fraction:
            failures.append("图像饱和像素比例过高")
        return failures, diagnostics

    def _fit_band(self, gray: np.ndarray, band: BandConfig) -> tuple[EdgePointSet, LineModel]:
        point_set = extract_edge_points(gray, band.roi, band.edge)
        return point_set, fit_line_ransac(point_set.points, self.recipe.line_fit)

    def _line_failures(self, name: str, line: LineModel, band: BandConfig) -> list[str]:
        config = self.recipe.line_fit
        failures: list[str] = []
        if line.inlier_ratio < config.min_inlier_ratio:
            failures.append(f"{name}内点率过低")
        if line.span_px < config.min_span_px:
            failures.append(f"{name}有效线段过短")
        if line.rms_px > config.max_rms_px:
            failures.append(f"{name}拟合残差过大")
        deviation = angle_between_directions(line.direction, band.roi.direction)
        if deviation > band.edge.max_direction_deviation_deg:
            failures.append(f"{name}方向偏离测量带过大")
        return failures

    def _band_confidence(
        self,
        points: EdgePointSet,
        line: LineModel,
        band: BandConfig,
    ) -> float:
        config = self.recipe.line_fit
        completion = min(1.0, points.count / max(points.attempted_profiles, 1))
        inliers = min(1.0, line.inlier_ratio / max(config.min_inlier_ratio, 1e-9))
        span = min(1.0, line.span_px / max(band.roi.length * 0.8, config.min_span_px))
        residual = math.exp(-line.rms_px / max(config.max_rms_px, 1e-9))
        strength = min(
            1.0,
            float(np.mean(points.strengths)) / max(band.edge.min_gradient * 3.0, 1e-9),
        )
        return float(np.mean([completion, inliers, span, residual, strength]))

    def measure(self, image: np.ndarray) -> MeasurementResult:
        try:
            gray, calibrated = self._prepare(image)
        except (ValueError, EdgeExtractionError) as exc:
            return MeasurementResult(False, False, failure_reasons=[str(exc)])

        failures, diagnostics = self._image_failures(gray)
        if failures:
            return MeasurementResult(
                False,
                calibrated,
                failure_reasons=failures,
                diagnostics=diagnostics,
            )

        try:
            slit_points, slit_line = self._fit_band(gray, self.recipe.slit)
            platform_points, platform_line = self._fit_band(gray, self.recipe.platform)
        except (EdgeExtractionError, LineFitError) as exc:
            return MeasurementResult(
                False,
                calibrated,
                failure_reasons=[str(exc)],
                diagnostics=diagnostics,
            )

        failures.extend(self._line_failures("狭缝边缘", slit_line, self.recipe.slit))
        failures.extend(self._line_failures("平台边缘", platform_line, self.recipe.platform))
        diagnostics.update(
            {
                "slit_candidate_points": slit_points.count,
                "platform_candidate_points": platform_points.count,
                "slit_mean_gradient": float(np.mean(slit_points.strengths)),
                "platform_mean_gradient": float(np.mean(platform_points.strengths)),
                "slit_direction_deviation_deg": angle_between_directions(
                    slit_line.direction, self.recipe.slit.roi.direction
                ),
                "platform_direction_deviation_deg": angle_between_directions(
                    platform_line.direction, self.recipe.platform.roi.direction
                ),
            }
        )
        if failures:
            return MeasurementResult(
                False,
                calibrated,
                line_slit=slit_line,
                line_platform=platform_line,
                slit_edge_points=slit_points.points,
                platform_edge_points=platform_points.points,
                failure_reasons=failures,
                diagnostics=diagnostics,
            )

        angle = angle_between_lines(slit_line, platform_line)
        confidence_slit = self._band_confidence(slit_points, slit_line, self.recipe.slit)
        confidence_platform = self._band_confidence(
            platform_points, platform_line, self.recipe.platform
        )
        confidence = float(math.sqrt(confidence_slit * confidence_platform))
        diagnostics.update(
            {
                "slit_confidence": confidence_slit,
                "platform_confidence": confidence_platform,
            }
        )
        return MeasurementResult(
            True,
            calibrated,
            angle_deg=angle,
            confidence=confidence,
            line_slit=slit_line,
            line_platform=platform_line,
            slit_edge_points=slit_points.points,
            platform_edge_points=platform_points.points,
            intersection=line_intersection(slit_line, platform_line),
            diagnostics=diagnostics,
        )
