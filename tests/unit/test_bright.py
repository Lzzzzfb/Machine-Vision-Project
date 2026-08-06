import cv2
import numpy as np

from angle_measurement.measurement.bright import extract_bright_line_points
from angle_measurement.models import BrightLineExtractionConfig, RotatedRoi


def test_bright_ridge_returns_paired_edge_centres():
    image = np.full((240, 320), 25, dtype=np.uint8)
    image[118:124, :] = 225
    image = cv2.GaussianBlur(image, (0, 0), 0.8)
    roi = RotatedRoi(160, 120.5, 240, 30, 0)
    points = extract_bright_line_points(
        image,
        roi,
        BrightLineExtractionConfig(
            min_gradient=4,
            min_contrast=20,
            min_width_px=3,
            max_width_px=10,
        ),
    )
    assert points.count > 60
    assert abs(float(np.mean(points.points[:, 1])) - 120.5) < 0.2
    assert float(np.mean(points.widths_px)) == pytest.approx(6.0, abs=0.5)


import pytest
