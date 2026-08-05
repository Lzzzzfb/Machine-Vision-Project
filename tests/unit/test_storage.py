import csv

import numpy as np

from angle_measurement.models import MeasurementResult
from angle_measurement.storage import ResultWriter


def test_result_writer_creates_images_and_csv(tmp_path):
    image = np.full((20, 30), 128, dtype=np.uint8)
    result = MeasurementResult(valid=False, calibrated=False, failure_reasons=["测试失败"])
    writer = ResultWriter(tmp_path)
    paths = writer.write(
        image,
        image,
        result,
        frame_id="帧 1",
        source_name="测试.png",
        recipe_name="测试配方",
        timestamp="2026-08-05T01:02:03+00:00",
    )
    assert all((tmp_path / "2026-08-05" / name).exists() for name in ["帧_1-raw.png", "帧_1-result.png"])
    with open(paths["csv"], encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["failure_reasons"] == "测试失败"
