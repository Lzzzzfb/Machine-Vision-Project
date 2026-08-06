import os
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2
import numpy as np
from PySide6.QtWidgets import QApplication

from angle_measurement.acquisition import Frame
from angle_measurement.recipe import MeasurementRecipe
from angle_measurement.ui.main_window import MainWindow


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _wait_until(app: QApplication, condition, timeout_seconds: float = 3.0) -> None:  # noqa: ANN001
    deadline = time.monotonic() + timeout_seconds
    while not condition() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert condition()


def test_two_sequential_measurement_tasks_keep_signals_alive():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.recipe = MeasurementRecipe.load(PROJECT_ROOT / "configs/synthetic-demo.json")
    window._recipe_changed()
    encoded = np.fromfile(PROJECT_ROOT / "examples/synthetic-20deg.png", dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE)
    assert image is not None

    first = Frame(image, "first")
    window.current_frame = first
    window.live_controller.on_frame(first)
    window.measure_current()
    _wait_until(app, lambda: window.last_measured_frame is first)
    assert window._measurement_task is None

    second = Frame(image, "second")
    window.current_frame = second
    window.live_controller.on_frame(second)
    window.measure_current()
    _wait_until(app, lambda: window.last_measured_frame is second)
    assert window._measurement_task is None
    assert not window.live_controller.busy

    window.close()
    app.processEvents()
