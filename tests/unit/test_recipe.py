import json

import pytest

from angle_measurement.models import RotatedRoi
from angle_measurement.recipe import MeasurementRecipe, default_recipe


def test_recipe_round_trip(tmp_path):
    recipe = default_recipe(640, 480)
    path = recipe.save(tmp_path / "recipe.json")
    restored = MeasurementRecipe.load(path)
    assert restored == recipe
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 1


def test_roi_rejects_non_positive_size():
    with pytest.raises(ValueError):
        RotatedRoi(10, 10, 0, 5, 0)


def test_recipe_rejects_unknown_version():
    data = default_recipe().to_dict()
    data["version"] = 99
    with pytest.raises(ValueError, match="Unsupported"):
        MeasurementRecipe.from_dict(data)
