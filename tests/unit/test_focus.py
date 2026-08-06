import numpy as np

from angle_measurement.measurement.edge import localize_gradient_peak
from angle_measurement.measurement.focus import assess_focus


def test_gradient_centroid_reports_symmetric_blur_width():
    coordinates = np.arange(161, dtype=float)
    sigma_samples = 8.0
    values = np.exp(-0.5 * np.square((coordinates - 80.35) / sigma_samples))
    centre, fwhm = localize_gradient_peak(values, int(np.argmax(values)), 0.25)
    assert centre * 0.25 == pytest.approx(80.35 * 0.25, abs=0.03)
    assert fwhm == pytest.approx(2.35482 * sigma_samples * 0.25, rel=0.05)


def test_focus_assessment_rejects_large_blur():
    sharp = assess_focus(np.full(20, 3.0), np.full(20, 20.0), 20, 20, 8.0, 0.5)
    blurred = assess_focus(np.full(20, 10.0), np.full(20, 8.0), 20, 20, 8.0, 0.5)
    assert sharp.status == "清晰"
    assert blurred.status == "不足"


import pytest
