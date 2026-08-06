import json

import pytest

from angle_measurement.models import RotatedRoi
from angle_measurement.recipe import MeasurementRecipe, default_recipe


def test_recipe_round_trip(tmp_path):
    recipe = default_recipe(640, 480)
    path = recipe.save(tmp_path / "recipe.json")
    restored = MeasurementRecipe.load(path)
    assert restored == recipe
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 2


def test_roi_rejects_non_positive_size():
    with pytest.raises(ValueError):
        RotatedRoi(10, 10, 0, 5, 0)


def test_recipe_rejects_unknown_version():
    data = default_recipe().to_dict()
    data["version"] = 99
    with pytest.raises(ValueError, match="Unsupported"):
        MeasurementRecipe.from_dict(data)


def test_v1_recipe_is_migrated_and_requires_right_roi_review():
    band = {
        "name": "edge",
        "roi": {"center_x": 10, "center_y": 20, "length": 30, "width": 8, "angle_deg": 0},
        "edge": {"polarity": "auto"},
    }
    migrated = MeasurementRecipe.from_dict(
        {"version": 1, "name": "old", "slit": band, "platform": band}
    )
    assert migrated.version == 2
    assert migrated.platform_left.roi == migrated.platform_right.roi
    assert not migrated.platform_right_confirmed
    assert migrated.require_height_compensation
