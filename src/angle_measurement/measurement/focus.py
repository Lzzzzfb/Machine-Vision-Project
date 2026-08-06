from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class FocusAssessment:
    status: str
    valid_fraction: float
    median_blur_width_px: float | None
    mean_gradient: float | None

    @property
    def acceptable(self) -> bool:
        return self.status != "不足"

    def to_dict(self) -> dict[str, float | str | None]:
        return {
            "status": self.status,
            "valid_fraction": self.valid_fraction,
            "median_blur_width_px": self.median_blur_width_px,
            "mean_gradient": self.mean_gradient,
        }


def assess_focus(
    blur_widths_px: np.ndarray,
    strengths: np.ndarray,
    valid_count: int,
    attempted_profiles: int,
    max_blur_width_px: float,
    min_valid_fraction: float,
) -> FocusAssessment:
    blur = np.asarray(blur_widths_px, dtype=np.float64)
    blur = blur[np.isfinite(blur)]
    strength = np.asarray(strengths, dtype=np.float64)
    strength = strength[np.isfinite(strength)]
    fraction = float(valid_count / max(attempted_profiles, 1))
    median_blur = float(np.median(blur)) if len(blur) else None
    mean_gradient = float(np.mean(strength)) if len(strength) else None
    if fraction < min_valid_fraction or median_blur is None:
        status = "不足"
    elif median_blur > max_blur_width_px:
        status = "不足"
    elif median_blur > max_blur_width_px * 0.65 or fraction < min(0.8, min_valid_fraction * 1.5):
        status = "临界"
    else:
        status = "清晰"
    return FocusAssessment(status, fraction, median_blur, mean_gradient)
