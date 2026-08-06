import cv2
import numpy as np

from angle_measurement.cli import main
from angle_measurement.models import (
    BrightLineExtractionConfig,
    EdgeExtractionConfig,
    EdgePolarity,
    RotatedRoi,
)
from angle_measurement.recipe import BandConfig, BrightBandConfig, MeasurementRecipe


def _paint_boundary(image, roi):
    yy, xx = np.indices(image.shape)
    signed = (xx - roi.center_x) * roi.normal[0] + (yy - roi.center_y) * roi.normal[1]
    polygon = np.rint(roi.corners()).astype(np.int32)
    mask = np.zeros_like(image, dtype=np.uint8)
    cv2.fillConvexPoly(mask, polygon, 255)
    values = np.where(signed >= 0, 220, 30).astype(np.uint8)
    image[mask > 0] = values[mask > 0]


def _paint_bright(image, roi):
    yy, xx = np.indices(image.shape)
    signed = (xx - roi.center_x) * roi.normal[0] + (yy - roi.center_y) * roi.normal[1]
    polygon = np.rint(roi.corners()).astype(np.int32)
    mask = np.zeros_like(image, dtype=np.uint8)
    cv2.fillConvexPoly(mask, polygon, 255)
    image[mask > 0] = 30
    image[(mask > 0) & (np.abs(signed) <= 3)] = 230


def test_cli_measures_and_saves(tmp_path, capsys):
    image = np.full((400, 500), 120, dtype=np.uint8)
    slit = RotatedRoi(250, 90, 280, 32, 0)
    left = RotatedRoi(250, 270, 240, 30, 20)
    right = RotatedRoi(225, 338, 240, 30, 20)
    _paint_bright(image, slit)
    _paint_boundary(image, left)
    _paint_boundary(image, right)
    image = cv2.GaussianBlur(image, (0, 0), 1.0)
    image_path = tmp_path / "input.png"
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    encoded.tofile(image_path)

    edge = EdgeExtractionConfig(polarity=EdgePolarity.DARK_TO_LIGHT, min_gradient=8)
    recipe = MeasurementRecipe(
        "cli-test",
        BrightBandConfig(
            "slit_center",
            slit,
            BrightLineExtractionConfig(min_width_px=3, max_width_px=10),
        ),
        BandConfig("platform_left", left, edge),
        BandConfig("platform_right", right, edge),
        require_height_compensation=False,
    )
    recipe_path = recipe.save(tmp_path / "recipe.json")
    output = tmp_path / "out"
    code = main([str(image_path), "--recipe", str(recipe_path), "--output", str(output)])
    captured = capsys.readouterr().out
    assert code == 0
    assert '"valid": true' in captured
    assert list(output.rglob("measurements.csv"))
    assert list(output.rglob("*-result.json"))
