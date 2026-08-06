import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtWidgets import QApplication

from angle_measurement.acquisition import Frame
from angle_measurement.models import MeasurementResult, QualityConfig
from angle_measurement.ui.live_controller import LiveMeasurementController


def _frame(number):
    return Frame(np.zeros((10, 10), dtype=np.uint8), f"frame-{number}")


def test_controller_requests_only_latest_frame_without_backlog():
    app = QApplication.instance() or QApplication([])
    controller = LiveMeasurementController(QualityConfig())
    requested = []
    controller.measurement_requested.connect(requested.append)
    controller.on_frame(_frame(1))
    controller.on_frame(_frame(2))
    assert controller.request_now()
    assert requested[-1].frame_id == "frame-2"
    controller.on_frame(_frame(3))
    assert not controller.request_now()
    controller.measurement_completed(MeasurementResult(True, False, angle_deg=1.0))
    assert controller.request_now()
    assert requested[-1].frame_id == "frame-3"
    app.processEvents()


def test_roi_drag_pauses_and_release_forces_measurement():
    app = QApplication.instance() or QApplication([])
    controller = LiveMeasurementController(QualityConfig())
    requested = []
    controller.measurement_requested.connect(requested.append)
    controller.on_frame(_frame(1))
    controller.begin_roi_drag()
    assert not controller.request_now()
    controller.end_roi_drag()
    assert requested[-1].frame_id == "frame-1"
    app.processEvents()


def test_pending_forced_measurement_survives_worker_failure():
    app = QApplication.instance() or QApplication([])
    controller = LiveMeasurementController(QualityConfig())
    requested = []
    controller.measurement_requested.connect(requested.append)
    controller.on_frame(_frame(1))
    assert controller.request_now()
    controller.on_frame(_frame(2))
    assert not controller.request_now(force=True)
    controller.measurement_failed()
    assert requested[-1].frame_id == "frame-2"
    assert controller.busy
    app.processEvents()
