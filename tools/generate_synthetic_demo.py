from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from angle_measurement.models import EdgeExtractionConfig, EdgePolarity, RotatedRoi
from angle_measurement.recipe import BandConfig, MeasurementRecipe
from angle_measurement.storage import write_image_unicode


def paint_boundary(image: np.ndarray, roi: RotatedRoi) -> None:
    yy, xx = np.indices(image.shape)
    signed = (xx - roi.center_x) * roi.normal[0] + (yy - roi.center_y) * roi.normal[1]
    mask = np.zeros_like(image, dtype=np.uint8)
    cv2.fillConvexPoly(mask, np.rint(roi.corners()).astype(np.int32), 255)
    values = np.where(signed >= 0, 220, 32).astype(np.uint8)
    image[mask > 0] = values[mask > 0]


def main() -> int:
    image = np.full((600, 800), 120, dtype=np.uint8)
    slit = RotatedRoi(400, 220, 520, 55, 0.0)
    platform = RotatedRoi(400, 410, 460, 55, 20.0)
    paint_boundary(image, slit)
    paint_boundary(image, platform)
    image = cv2.GaussianBlur(image, (0, 0), 1.1)
    rng = np.random.default_rng(20260805)
    image = np.clip(image.astype(np.float64) + rng.normal(0, 1.5, image.shape), 0, 255).astype(
        np.uint8
    )
    edge = EdgeExtractionConfig(
        polarity=EdgePolarity.DARK_TO_LIGHT,
        min_gradient=8.0,
    )
    recipe = MeasurementRecipe(
        name="synthetic-demo-20deg",
        slit=BandConfig("slit_edge", slit, edge),
        platform=BandConfig("platform_edge", platform, edge),
    )
    write_image_unicode(Path("examples/synthetic-20deg.png"), image)
    recipe.save("configs/synthetic-demo.json")
    print("examples/synthetic-20deg.png")
    print("configs/synthetic-demo.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
