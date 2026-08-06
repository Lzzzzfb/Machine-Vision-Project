from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np

from .models import MeasurementResult


@dataclass(frozen=True)
class StabilitySnapshot:
    window_size: int
    sample_count: int
    valid_count: int
    stable: bool
    status: str
    median_deg: float | None = None
    mean_deg: float | None = None
    stddev_deg: float | None = None
    range_deg: float | None = None

    def to_dict(self) -> dict[str, int | bool | float | str | None]:
        return {
            "window_size": self.window_size,
            "sample_count": self.sample_count,
            "valid_count": self.valid_count,
            "stable": self.stable,
            "status": self.status,
            "median_deg": self.median_deg,
            "mean_deg": self.mean_deg,
            "stddev_deg": self.stddev_deg,
            "range_deg": self.range_deg,
        }


class StabilityTracker:
    def __init__(self, window_size: int = 10, stddev_max_deg: float = 0.1) -> None:
        if window_size < 2 or stddev_max_deg <= 0:
            raise ValueError("Invalid stability configuration")
        self.window_size = int(window_size)
        self.stddev_max_deg = float(stddev_max_deg)
        self._values: deque[float | None] = deque(maxlen=self.window_size)

    def reset(self) -> StabilitySnapshot:
        self._values.clear()
        return self.snapshot()

    def add(self, result: MeasurementResult) -> StabilitySnapshot:
        value = float(result.angle_deg) if result.valid and result.angle_deg is not None else None
        self._values.append(value)
        return self.snapshot()

    def snapshot(self) -> StabilitySnapshot:
        valid = np.asarray([value for value in self._values if value is not None], dtype=np.float64)
        complete = len(self._values) == self.window_size and len(valid) == self.window_size
        if not complete:
            status = "样本不足" if len(self._values) < self.window_size else "不稳定"
            return StabilitySnapshot(
                self.window_size, len(self._values), len(valid), False, status
            )
        mean = float(np.mean(valid))
        median = float(np.median(valid))
        stddev = float(np.std(valid, ddof=1))
        value_range = float(np.ptp(valid))
        stable = stddev <= self.stddev_max_deg
        return StabilitySnapshot(
            self.window_size,
            len(self._values),
            len(valid),
            stable,
            "稳定" if stable else "不稳定",
            median,
            mean,
            stddev,
            value_range,
        )
