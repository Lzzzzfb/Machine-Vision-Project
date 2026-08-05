import cv2
import numpy as np

from angle_measurement.measurement.edge import extract_edge_points
from angle_measurement.models import EdgeExtractionConfig, EdgePolarity, RotatedRoi


def test_subpixel_edge_points_follow_horizontal_boundary():
    image = np.full((240, 320), 30, dtype=np.uint8)
    image[121:, :] = 220
    image = cv2.GaussianBlur(image, (0, 0), 1.2)
    roi = RotatedRoi(160, 120.5, 240, 24, 0)
    points = extract_edge_points(
        image,
        roi,
        EdgeExtractionConfig(
            polarity=EdgePolarity.DARK_TO_LIGHT,
            min_gradient=5,
        ),
    )
    assert points.count > 60
    assert abs(float(np.mean(points.points[:, 1])) - 120.5) < 0.25
    assert float(np.std(points.points[:, 1])) < 0.05
