import cv2
import numpy as np
import pytest

from angle_measurement.measurement.service import AngleMeasurementService
from angle_measurement.models import EdgeExtractionConfig, EdgePolarity, RotatedRoi
from angle_measurement.recipe import BandConfig, MeasurementRecipe


def _paint_boundary(image, roi, low=35, high=215):
    yy, xx = np.indices(image.shape)
    signed = (xx - roi.center_x) * roi.normal[0] + (yy - roi.center_y) * roi.normal[1]
    polygon = np.rint(roi.corners()).astype(np.int32)
    mask = np.zeros_like(image, dtype=np.uint8)
    cv2.fillConvexPoly(mask, polygon, 255)
    values = np.where(signed >= 0, high, low).astype(np.uint8)
    image[mask > 0] = values[mask > 0]


@pytest.mark.parametrize(
    "expected_angle",
    sorted({0.0, 1.0, 3.0, 87.0, 89.0, 90.0, *map(float, range(5, 90, 5))}),
)
def test_full_measurement_on_noisy_synthetic_edges(expected_angle):
    image = np.full((512, 512), 120, dtype=np.uint8)
    slit_roi = RotatedRoi(256, 145, 360, 42, 0.0)
    platform_roi = RotatedRoi(256, 330, 280, 42, expected_angle)
    _paint_boundary(image, slit_roi)
    _paint_boundary(image, platform_roi)
    image = cv2.GaussianBlur(image, (0, 0), 1.0)
    rng = np.random.default_rng(123)
    noise = rng.normal(0, 2.0, image.shape)
    image = np.clip(image.astype(np.float64) + noise, 0, 255).astype(np.uint8)
    for _ in range(20):
        x, y = rng.integers(20, 492, size=2)
        cv2.circle(image, (int(x), int(y)), 2, int(rng.integers(0, 256)), -1)

    edge = EdgeExtractionConfig(
        polarity=EdgePolarity.DARK_TO_LIGHT,
        min_gradient=8,
    )
    recipe = MeasurementRecipe(
        name="synthetic",
        slit=BandConfig("slit", slit_roi, edge),
        platform=BandConfig("platform", platform_roi, edge),
    )
    result = AngleMeasurementService(recipe).measure(image)
    assert result.valid, result.failure_reasons
    assert result.angle_deg == pytest.approx(expected_angle, abs=0.1)


def test_blank_image_is_invalid_without_angle():
    image = np.full((512, 512), 120, dtype=np.uint8)
    recipe = MeasurementRecipe(
        name="blank",
        slit=BandConfig("slit", RotatedRoi(256, 150, 300, 40, 0)),
        platform=BandConfig("platform", RotatedRoi(256, 350, 300, 40, 10)),
    )
    result = AngleMeasurementService(recipe).measure(image)
    assert not result.valid
    assert result.angle_deg is None
    assert result.failure_reasons
