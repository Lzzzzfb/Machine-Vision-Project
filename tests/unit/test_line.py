import numpy as np
import pytest

from angle_measurement.measurement.angle import angle_between_directions
from angle_measurement.measurement.line import fit_line_ransac
from angle_measurement.models import LineFitConfig


def test_ransac_rejects_outliers_and_recovers_direction():
    rng = np.random.default_rng(42)
    x = np.linspace(-100, 100, 120)
    y = 0.4 * x + 12 + rng.normal(0, 0.15, size=x.shape)
    inliers = np.column_stack([x, y])
    outliers = rng.uniform(-100, 100, size=(30, 2))
    points = np.vstack([inliers, outliers])
    model = fit_line_ransac(points, LineFitConfig(ransac_threshold_px=0.6))
    expected = np.array([1.0, 0.4])
    assert angle_between_directions(model.direction, expected) < 0.05
    assert model.inlier_ratio > 0.75
    assert model.rms_px < 0.3


def test_ransac_rejects_too_few_points():
    with pytest.raises(Exception, match="不足"):
        fit_line_ransac(np.array([[0.0, 0.0], [1.0, 1.0]]), LineFitConfig())
