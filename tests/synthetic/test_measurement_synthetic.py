import cv2
import numpy as np
import pytest

from angle_measurement.calibration.model import CalibrationData, PlatformPose
from angle_measurement.measurement.service import AngleMeasurementService
from angle_measurement.models import (
    BrightLineExtractionConfig,
    EdgeExtractionConfig,
    EdgePolarity,
    RotatedRoi,
    QualityConfig,
)
from angle_measurement.recipe import BandConfig, BrightBandConfig, MeasurementRecipe


def _paint_boundary(image, roi, low=35, high=215):
    yy, xx = np.indices(image.shape)
    signed = (xx - roi.center_x) * roi.normal[0] + (yy - roi.center_y) * roi.normal[1]
    polygon = np.rint(roi.corners()).astype(np.int32)
    mask = np.zeros_like(image, dtype=np.uint8)
    cv2.fillConvexPoly(mask, polygon, 255)
    values = np.where(signed >= 0, high, low).astype(np.uint8)
    image[mask > 0] = values[mask > 0]


def _paint_bright_slit(image, roi, slit_width=6.0):
    yy, xx = np.indices(image.shape)
    signed = (xx - roi.center_x) * roi.normal[0] + (yy - roi.center_y) * roi.normal[1]
    polygon = np.rint(roi.corners()).astype(np.int32)
    mask = np.zeros_like(image, dtype=np.uint8)
    cv2.fillConvexPoly(mask, polygon, 255)
    image[mask > 0] = 35
    image[(mask > 0) & (np.abs(signed) <= slit_width / 2.0)] = 230


@pytest.mark.parametrize(
    "expected_angle",
    sorted({0.0, 1.0, 3.0, 87.0, 89.0, 90.0, *map(float, range(5, 90, 5))}),
)
def test_full_measurement_on_noisy_synthetic_lines(expected_angle):
    image = np.full((512, 512), 120, dtype=np.uint8)
    slit_roi = RotatedRoi(256, 145, 330, 34, 0.0)
    platform_mid = RotatedRoi(256, 350, 260, 30, expected_angle)
    offset = platform_mid.normal * 42
    platform_left = RotatedRoi(
        *(platform_mid.center - offset), 260, 30, expected_angle
    )
    platform_right = RotatedRoi(
        *(platform_mid.center + offset), 260, 30, expected_angle
    )
    _paint_bright_slit(image, slit_roi)
    _paint_boundary(image, platform_left)
    _paint_boundary(image, platform_right)
    image = cv2.GaussianBlur(image, (0, 0), 1.0)
    rng = np.random.default_rng(123)
    noise = rng.normal(0, 2.0, image.shape)
    image = np.clip(image.astype(np.float64) + noise, 0, 255).astype(np.uint8)

    edge = EdgeExtractionConfig(polarity=EdgePolarity.DARK_TO_LIGHT, min_gradient=8)
    bright = BrightLineExtractionConfig(
        min_gradient=5,
        min_contrast=15,
        min_width_px=3,
        max_width_px=10,
    )
    recipe = MeasurementRecipe(
        name="synthetic",
        slit_center=BrightBandConfig("slit_center", slit_roi, bright),
        platform_left=BandConfig("platform_left", platform_left, edge),
        platform_right=BandConfig("platform_right", platform_right, edge),
        require_height_compensation=False,
    )
    result = AngleMeasurementService(recipe).measure(image)
    assert result.valid, result.failure_reasons
    assert result.angle_deg == pytest.approx(expected_angle, abs=0.1)
    assert result.projected_angle_deg == pytest.approx(expected_angle, abs=0.1)


def test_missing_height_and_pose_returns_only_projected_diagnostic():
    image = np.full((400, 500), 120, dtype=np.uint8)
    slit = RotatedRoi(250, 100, 260, 30, 0)
    left = RotatedRoi(250, 260, 240, 30, 10)
    right = RotatedRoi(250, 330, 240, 30, 10)
    _paint_bright_slit(image, slit)
    _paint_boundary(image, left)
    _paint_boundary(image, right)
    image = cv2.GaussianBlur(image, (0, 0), 1)
    recipe = MeasurementRecipe(
        "formal",
        BrightBandConfig(
            "slit_center",
            slit,
            BrightLineExtractionConfig(min_width_px=3, max_width_px=10),
        ),
        BandConfig("platform_left", left),
        BandConfig("platform_right", right),
    )
    result = AngleMeasurementService(recipe).measure(image)
    assert not result.valid
    assert result.angle_deg is None
    assert result.projected_angle_deg == pytest.approx(10, abs=0.1)
    assert "高度差未设置" in result.failure_reasons


def test_blank_image_is_invalid_without_angle():
    image = np.full((512, 512), 120, dtype=np.uint8)
    recipe = MeasurementRecipe(
        name="blank",
        slit_center=BrightBandConfig(
            "slit_center", RotatedRoi(256, 120, 220, 30, 0)
        ),
        platform_left=BandConfig(
            "platform_left", RotatedRoi(256, 300, 220, 30, 10)
        ),
        platform_right=BandConfig(
            "platform_right", RotatedRoi(256, 370, 220, 30, 10)
        ),
        require_height_compensation=False,
    )
    result = AngleMeasurementService(recipe).measure(image)
    assert not result.valid
    assert result.angle_deg is None
    assert result.failure_reasons


def test_severely_blurred_platform_edges_are_rejected():
    image = np.full((480, 640), 120, dtype=np.uint8)
    slit = RotatedRoi(320, 100, 280, 36, 0)
    left = RotatedRoi(320, 280, 300, 40, 0)
    right = RotatedRoi(320, 390, 300, 40, 0)
    _paint_bright_slit(image, slit)
    _paint_boundary(image, left)
    _paint_boundary(image, right)
    image = cv2.GaussianBlur(image, (0, 0), 5.0)
    edge = EdgeExtractionConfig(
        polarity=EdgePolarity.DARK_TO_LIGHT,
        min_gradient=3,
    )
    recipe = MeasurementRecipe(
        "blurred",
        BrightBandConfig(
            "slit_center",
            slit,
            BrightLineExtractionConfig(
                min_gradient=3, min_contrast=10, min_width_px=2, max_width_px=20
            ),
        ),
        BandConfig("platform_left", left, edge),
        BandConfig("platform_right", right, edge),
        quality=QualityConfig(
            max_platform_blur_width_px=7.0,
            max_slit_edge_blur_width_px=14.0,
        ),
        require_height_compensation=False,
    )
    result = AngleMeasurementService(recipe).measure(image)
    assert not result.valid
    assert "平台左边缘清晰度不足" in result.failure_reasons
    assert "平台右边缘清晰度不足" in result.failure_reasons


def test_dual_plane_compensation_recovers_world_angle_under_perspective():
    image = np.full((480, 640), 120, dtype=np.uint8)
    camera_matrix = np.array([[800, 0, 320], [0, 800, 240], [0, 0, 1]], dtype=float)
    rotation_vector = np.array([0.28, -0.20, 0.08], dtype=float)
    translation_vector = np.array([0.0, 0.0, 260.0], dtype=float)
    pose = PlatformPose(rotation_vector, translation_vector, 0.1)
    calibration = CalibrationData(
        camera_matrix=camera_matrix,
        distortion_coefficients=np.zeros(5),
        image_size=(640, 480),
        rms_reprojection_error=0.1,
        square_size_mm=5,
        platform_pose=pose,
    )

    def projected_roi(center, direction, length, z, width):
        endpoints = np.array(
            [
                [*(center - direction * length / 2), z],
                [*(center + direction * length / 2), z],
            ],
            dtype=float,
        )
        pixels, _ = cv2.projectPoints(
            endpoints, rotation_vector, translation_vector, camera_matrix, np.zeros(5)
        )
        first, second = pixels.reshape(-1, 2)
        delta = second - first
        return RotatedRoi(
            *(0.5 * (first + second)),
            float(np.linalg.norm(delta) * 0.9),
            width,
            float(np.degrees(np.arctan2(delta[1], delta[0]))),
        )

    platform_direction = np.array([1.0, 0.0])
    slit_direction = np.array([np.cos(np.radians(20)), np.sin(np.radians(20))])
    left = projected_roi(np.array([0.0, -24.0]), platform_direction, 90, 0, 28)
    right = projected_roi(np.array([0.0, 24.0]), platform_direction, 90, 0, 28)
    slit = projected_roi(np.array([0.0, 0.0]), slit_direction, 60, -30, 28)
    _paint_boundary(image, left)
    _paint_boundary(image, right)
    _paint_bright_slit(image, slit, 6)
    image = cv2.GaussianBlur(image, (0, 0), 0.8)
    edge = EdgeExtractionConfig(polarity=EdgePolarity.DARK_TO_LIGHT, min_gradient=6)
    recipe = MeasurementRecipe(
        "dual-plane",
        BrightBandConfig(
            "slit_center",
            slit,
            BrightLineExtractionConfig(
                min_gradient=4, min_contrast=15, min_width_px=3, max_width_px=10
            ),
        ),
        BandConfig("platform_left", left, edge),
        BandConfig("platform_right", right, edge),
        height_difference_mm=30,
    )
    result = AngleMeasurementService(recipe, calibration).measure(image)
    assert result.valid, result.failure_reasons
    assert result.height_compensated
    assert result.angle_deg == pytest.approx(20.0, abs=0.15)
    assert abs(result.projected_angle_deg - result.angle_deg) > 0.2
