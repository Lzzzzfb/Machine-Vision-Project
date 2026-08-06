import pytest

from angle_measurement.models import MeasurementResult
from angle_measurement.stability import StabilityTracker


def _result(angle=None, valid=True):
    return MeasurementResult(valid=valid, calibrated=True, angle_deg=angle)


def test_stability_requires_a_complete_valid_window():
    tracker = StabilityTracker(window_size=3, stddev_max_deg=0.1)
    assert tracker.add(_result(1.0)).status == "样本不足"
    assert tracker.add(_result(valid=False)).status == "样本不足"
    snapshot = tracker.add(_result(1.02))
    assert snapshot.status == "不稳定"
    assert not snapshot.stable


def test_stability_statistics_and_reset():
    tracker = StabilityTracker(window_size=3, stddev_max_deg=0.1)
    for value in (1.00, 1.02, 0.98):
        snapshot = tracker.add(_result(value))
    assert snapshot.stable
    assert snapshot.median_deg == pytest.approx(1.0)
    assert snapshot.stddev_deg == pytest.approx(0.02)
    assert tracker.reset().sample_count == 0
