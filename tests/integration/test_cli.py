import cv2
import numpy as np

from angle_measurement.cli import main
from angle_measurement.models import EdgeExtractionConfig, EdgePolarity, RotatedRoi
from angle_measurement.recipe import BandConfig, MeasurementRecipe


def _paint_boundary(image, roi):
    yy, xx = np.indices(image.shape)
    signed = (xx - roi.center_x) * roi.normal[0] + (yy - roi.center_y) * roi.normal[1]
    polygon = np.rint(roi.corners()).astype(np.int32)
    mask = np.zeros_like(image, dtype=np.uint8)
    cv2.fillConvexPoly(mask, polygon, 255)
    values = np.where(signed >= 0, 220, 30).astype(np.uint8)
    image[mask > 0] = values[mask > 0]


def test_cli_measures_and_saves(tmp_path, capsys):
    image = np.full((400, 500), 120, dtype=np.uint8)
    slit = RotatedRoi(250, 120, 320, 40, 0)
    platform = RotatedRoi(250, 300, 260, 40, 20)
    _paint_boundary(image, slit)
    _paint_boundary(image, platform)
    image = cv2.GaussianBlur(image, (0, 0), 1.0)
    image_path = tmp_path / "input.png"
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    encoded.tofile(image_path)

    edge = EdgeExtractionConfig(polarity=EdgePolarity.DARK_TO_LIGHT, min_gradient=8)
    recipe = MeasurementRecipe(
        "cli-test",
        BandConfig("slit", slit, edge),
        BandConfig("platform", platform, edge),
    )
    recipe_path = recipe.save(tmp_path / "recipe.json")
    output = tmp_path / "out"
    code = main([str(image_path), "--recipe", str(recipe_path), "--output", str(output)])
    captured = capsys.readouterr().out
    assert code == 0
    assert '"valid": true' in captured
    assert list(output.rglob("measurements.csv"))
