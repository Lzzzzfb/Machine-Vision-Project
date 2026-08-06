import csv
import json
from pathlib import Path

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


def test_result_writer_flattens_focus_stability_and_runtime_fields(tmp_path):
    image = np.full((20, 30), 128, dtype=np.uint8)
    result = MeasurementResult(
        valid=True,
        calibrated=False,
        angle_deg=2.5,
        diagnostics={
            "slit_focus": {"status": "清晰", "median_blur_width_px": 2.2},
            "platform_left_focus": {"status": "临界", "median_blur_width_px": 5.5},
            "platform_right_focus": {"status": "清晰", "median_blur_width_px": 3.1},
        },
    )
    metadata = {
        "stability": {
            "status": "稳定",
            "stable": True,
            "window_size": 10,
            "valid_count": 10,
            "median_deg": 2.5,
            "mean_deg": 2.51,
            "stddev_deg": 0.02,
            "range_deg": 0.06,
        },
        "camera_fps": 4.0,
        "measurement_fps": 2.0,
        "exposure_us": 250000.0,
        "gain_db": 3.0,
    }
    paths = ResultWriter(tmp_path).write(
        image,
        image,
        result,
        frame_id="frame-2",
        source_name="mvs",
        recipe_name="recipe",
        timestamp="2026-08-06T01:02:03+00:00",
        metadata=metadata,
    )
    with open(paths["csv"], encoding="utf-8-sig", newline="") as stream:
        row = next(csv.DictReader(stream))
    assert row["platform_left_focus_status"] == "临界"
    assert row["stability_status"] == "稳定"
    assert row["measurement_fps"] == "2.00000000"
    payload = json.loads(Path(paths["result_json"]).read_text(encoding="utf-8"))
    assert payload["stability"]["stddev_deg"] == 0.02
    assert payload["runtime"]["exposure_us"] == 250000.0
