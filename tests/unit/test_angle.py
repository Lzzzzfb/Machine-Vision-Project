import numpy as np
import pytest

from angle_measurement.measurement.angle import angle_between_directions


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        ((1, 0), (1, 0), 0.0),
        ((1, 0), (-1, 0), 0.0),
        ((1, 0), (0, 1), 90.0),
        ((1, 0), (1, 1), 45.0),
        ((0, 1), (np.cos(np.deg2rad(80)), np.sin(np.deg2rad(80))), 10.0),
    ],
)
def test_smaller_angle(first, second, expected):
    assert angle_between_directions(first, second) == pytest.approx(expected, abs=1e-9)
