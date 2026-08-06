from __future__ import annotations

import math
from typing import Protocol

import numpy as np

from angle_measurement.models import (
    BrightLinePointSet,
    EdgePointSet,
    LineModel,
    MeasurementResult,
)
from angle_measurement.recipe import BandConfig, BrightBandConfig, MeasurementRecipe

from .angle import angle_between_directions, line_intersection
from .bright import extract_bright_line_points
from .edge import EdgeExtractionError, extract_edge_points, to_gray_u8
from .line import LineFitError, fit_line_ransac
from .plane import PlaneProjectionError, backproject_pixels_to_parallel_plane, fit_world_line


class CalibrationLike(Protocol):
    @property
    def image_size(self) -> tuple[int, int]: ...

    @property
    def platform_pose(self): ...  # noqa: ANN201

    @property
    def camera_matrix(self) -> np.ndarray: ...

    @property
    def rms_reprojection_error(self) -> float: ...

    def undistort(self, image: np.ndarray) -> np.ndarray: ...


def _average_direction(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    first = np.asarray(first, dtype=np.float64)
    second = np.asarray(second, dtype=np.float64)
    if float(np.dot(first, second)) < 0:
        second = -second
    result = first + second
    norm = float(np.linalg.norm(result))
    if norm <= 1e-12:
        raise ValueError("平台双边平均方向无效")
    return result / norm


def _average_image_line(left: LineModel, right: LineModel) -> LineModel:
    return LineModel(
        point=0.5 * (left.point + right.point),
        direction=_average_direction(left.direction, right.direction),
        inlier_mask=np.empty(0, dtype=bool),
        rms_px=0.5 * (left.rms_px + right.rms_px),
        max_residual_px=max(left.max_residual_px, right.max_residual_px),
        span_px=min(left.span_px, right.span_px),
        inlier_ratio=min(left.inlier_ratio, right.inlier_ratio),
    )


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

    def _fit_edge_band(
        self, gray: np.ndarray, band: BandConfig
    ) -> tuple[EdgePointSet, LineModel]:
        point_set = extract_edge_points(gray, band.roi, band.edge)
        return point_set, fit_line_ransac(point_set.points, self.recipe.line_fit)

    def _fit_bright_band(
        self, gray: np.ndarray, band: BrightBandConfig
    ) -> tuple[BrightLinePointSet, LineModel]:
        point_set = extract_bright_line_points(gray, band.roi, band.bright)
        return point_set, fit_line_ransac(point_set.points, self.recipe.line_fit)

    def _line_failures(
        self,
        name: str,
        line: LineModel,
        roi_direction: np.ndarray,
        max_direction_deviation_deg: float,
    ) -> list[str]:
        config = self.recipe.line_fit
        failures: list[str] = []
        if line.inlier_ratio < config.min_inlier_ratio:
            failures.append(f"{name}内点率过低")
        if line.span_px < config.min_span_px:
            failures.append(f"{name}有效线段过短")
        if line.rms_px > config.max_rms_px:
            failures.append(f"{name}拟合残差过大")
        if angle_between_directions(line.direction, roi_direction) > max_direction_deviation_deg:
            failures.append(f"{name}方向偏离测量带过大")
        return failures

    def _edge_confidence(
        self, points: EdgePointSet, line: LineModel, band: BandConfig
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

    def _bright_confidence(
        self, points: BrightLinePointSet, line: LineModel, band: BrightBandConfig
    ) -> float:
        config = self.recipe.line_fit
        completion = min(1.0, points.count / max(points.attempted_profiles, 1))
        inliers = min(1.0, line.inlier_ratio / max(config.min_inlier_ratio, 1e-9))
        span = min(1.0, line.span_px / max(band.roi.length * 0.8, config.min_span_px))
        residual = math.exp(-line.rms_px / max(config.max_rms_px, 1e-9))
        contrast = min(
            1.0,
            float(np.mean(points.contrasts)) / max(band.bright.min_contrast * 3.0, 1e-9),
        )
        return float(np.mean([completion, inliers, span, residual, contrast]))

    def measure(self, image: np.ndarray) -> MeasurementResult:
        try:
            gray, calibrated = self._prepare(image)
        except (ValueError, EdgeExtractionError) as exc:
            return MeasurementResult(False, False, failure_reasons=[str(exc)])

        failures, diagnostics = self._image_failures(gray)
        if failures:
            return MeasurementResult(
                False, calibrated, failure_reasons=failures, diagnostics=diagnostics
            )

        try:
            slit_points, slit_line = self._fit_bright_band(gray, self.recipe.slit_center)
            left_points, left_line = self._fit_edge_band(gray, self.recipe.platform_left)
            right_points, right_line = self._fit_edge_band(gray, self.recipe.platform_right)
            platform_line = _average_image_line(left_line, right_line)
        except (EdgeExtractionError, LineFitError, ValueError) as exc:
            return MeasurementResult(
                False, calibrated, failure_reasons=[str(exc)], diagnostics=diagnostics
            )

        failures.extend(
            self._line_failures(
                "亮狭缝中心线",
                slit_line,
                self.recipe.slit_center.roi.direction,
                self.recipe.slit_center.bright.max_direction_deviation_deg,
            )
        )
        for label, line, band in (
            ("平台左边缘", left_line, self.recipe.platform_left),
            ("平台右边缘", right_line, self.recipe.platform_right),
        ):
            failures.extend(
                self._line_failures(
                    label,
                    line,
                    band.roi.direction,
                    band.edge.max_direction_deviation_deg,
                )
            )

        projected_parallelism = angle_between_directions(left_line.direction, right_line.direction)
        separation = abs(
            float(
                np.dot(
                    self.recipe.platform_right.roi.center - self.recipe.platform_left.roi.center,
                    np.array([-platform_line.direction[1], platform_line.direction[0]]),
                )
            )
        )
        if separation < self.recipe.quality.min_platform_edge_separation_px:
            failures.append("平台左右 ROI 疑似覆盖同一条边")
        if not self.recipe.platform_right_confirmed:
            failures.append("平台右边缘 ROI 尚未确认")

        projected_angle = angle_between_directions(slit_line.direction, platform_line.direction)
        slit_confidence = self._bright_confidence(
            slit_points, slit_line, self.recipe.slit_center
        )
        left_confidence = self._edge_confidence(
            left_points, left_line, self.recipe.platform_left
        )
        right_confidence = self._edge_confidence(
            right_points, right_line, self.recipe.platform_right
        )
        confidence = float((slit_confidence * left_confidence * right_confidence) ** (1.0 / 3.0))
        diagnostics.update(
            {
                "slit_candidate_points": slit_points.count,
                "platform_left_candidate_points": left_points.count,
                "platform_right_candidate_points": right_points.count,
                "slit_mean_width_px": float(np.mean(slit_points.widths_px)),
                "slit_width_stddev_px": float(np.std(slit_points.widths_px)),
                "slit_mean_contrast": float(np.mean(slit_points.contrasts)),
                "platform_parallelism_projected_deg": projected_parallelism,
                "platform_edge_separation_px": separation,
                "slit_confidence": slit_confidence,
                "platform_left_confidence": left_confidence,
                "platform_right_confidence": right_confidence,
            }
        )

        common = dict(
            calibrated=calibrated,
            projected_angle_deg=projected_angle,
            confidence=confidence,
            line_slit=slit_line,
            line_platform=platform_line,
            line_platform_left=left_line,
            line_platform_right=right_line,
            slit_edge_points=slit_points.points,
            platform_edge_points=np.vstack((left_points.points, right_points.points)),
            platform_left_edge_points=left_points.points,
            platform_right_edge_points=right_points.points,
            intersection=line_intersection(slit_line, platform_line),
            platform_parallelism_deg=projected_parallelism,
            diagnostics=diagnostics,
        )
        if failures:
            return MeasurementResult(False, failure_reasons=failures, **common)

        height = self.recipe.height_difference_mm
        pose = None if self.calibration is None else self.calibration.platform_pose
        compensation_ready = self.calibration is not None and pose is not None and height is not None
        if not compensation_ready:
            if self.recipe.require_height_compensation:
                if height is None:
                    failures.append("高度差未设置")
                if self.calibration is None:
                    failures.append("缺少相机内参标定")
                elif pose is None:
                    failures.append("缺少平台姿态标定")
                return MeasurementResult(False, failure_reasons=failures, **common)
            if projected_parallelism > self.recipe.quality.max_platform_parallelism_deg:
                failures.append("平台双边平行度超限")
                return MeasurementResult(False, failure_reasons=failures, **common)
            return MeasurementResult(True, angle_deg=projected_angle, **common)

        diagnostics["intrinsic_rms_px"] = float(self.calibration.rms_reprojection_error)
        diagnostics["platform_pose_rms_px"] = float(pose.reprojection_error_px)
        if self.calibration.rms_reprojection_error > self.recipe.quality.max_intrinsic_rms_px:
            failures.append("相机内参标定 RMS 超限")
        if pose.reprojection_error_px > self.recipe.quality.max_pose_rms_px:
            failures.append("平台姿态标定 RMS 超限")
        if failures:
            return MeasurementResult(False, failure_reasons=failures, **common)

        try:
            slit_world_points = backproject_pixels_to_parallel_plane(
                slit_points.points, self.calibration, float(height)
            )
            left_world_points = backproject_pixels_to_parallel_plane(
                left_points.points, self.calibration, 0.0
            )
            right_world_points = backproject_pixels_to_parallel_plane(
                right_points.points, self.calibration, 0.0
            )
            slit_world, _ = fit_world_line(slit_line, slit_world_points, self.recipe.line_fit)
            left_world, _ = fit_world_line(left_line, left_world_points, self.recipe.line_fit)
            right_world, _ = fit_world_line(right_line, right_world_points, self.recipe.line_fit)
        except PlaneProjectionError as exc:
            return MeasurementResult(False, failure_reasons=[str(exc)], **common)

        world_parallelism = angle_between_directions(
            left_world.direction, right_world.direction
        )
        world_platform_direction = _average_direction(
            left_world.direction, right_world.direction
        )
        compensated_angle = angle_between_directions(
            slit_world.direction, world_platform_direction
        )
        diagnostics["platform_parallelism_world_deg"] = world_parallelism
        diagnostics["height_difference_mm"] = float(height)
        if world_parallelism > self.recipe.quality.max_platform_parallelism_deg:
            return MeasurementResult(
                False,
                world_line_slit=slit_world,
                world_line_platform_left=left_world,
                world_line_platform_right=right_world,
                platform_parallelism_deg=world_parallelism,
                failure_reasons=["平台双边平行度超限"],
                **{key: value for key, value in common.items() if key != "platform_parallelism_deg"},
            )
        return MeasurementResult(
            True,
            angle_deg=compensated_angle,
            height_compensated=True,
            world_line_slit=slit_world,
            world_line_platform_left=left_world,
            world_line_platform_right=right_world,
            platform_parallelism_deg=world_parallelism,
            **{key: value for key, value in common.items() if key != "platform_parallelism_deg"},
        )
