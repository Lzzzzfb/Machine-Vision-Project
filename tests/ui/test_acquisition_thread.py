import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtWidgets import QApplication

from angle_measurement.acquisition import Frame
from angle_measurement.ui.acquisition_thread import CameraAcquisitionThread
from angle_measurement.ui.main_window import MainWindow


def _frame(number: int) -> Frame:
    return Frame(np.full((20, 30), number % 255, dtype=np.uint8), f"frame-{number}")


def test_burst_publishes_one_notification_and_take_returns_newest_frame():
    app = QApplication.instance() or QApplication([])
    thread = CameraAcquisitionThread(5000, 0)
    notifications: list[bool] = []
    thread.frame_available.connect(lambda: notifications.append(True))

    for number in range(1, 101):
        thread._publish_frame(_frame(number))

    assert len(notifications) == 1
    assert thread.take_latest_frame().frame_id == "frame-100"
    assert thread.take_latest_frame() is None

    thread._publish_frame(_frame(101))
    assert len(notifications) == 2
    assert thread.take_latest_frame().frame_id == "frame-101"
    app.processEvents()


def test_frame_rate_status_is_limited_to_two_updates_per_second():
    thread = CameraAcquisitionThread(5000, 0)
    assert thread._should_emit_frame_rate(10.0)
    assert not thread._should_emit_frame_rate(10.1)
    assert not thread._should_emit_frame_rate(10.49)
    assert thread._should_emit_frame_rate(10.5)


def test_main_window_ignores_late_frame_from_old_acquisition_thread():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    old_thread = CameraAcquisitionThread(5000, 0, window)
    current_thread = CameraAcquisitionThread(5000, 0, window)
    old_thread.frame_available.connect(window._frame_available)
    current_thread.frame_available.connect(window._frame_available)
    window.acquisition_thread = current_thread

    old_thread._publish_frame(_frame(1))
    assert window.current_frame is None
    current_thread._publish_frame(_frame(2))
    assert window.current_frame.frame_id == "frame-2"

    window.acquisition_thread = None
    window.close()
    app.processEvents()
