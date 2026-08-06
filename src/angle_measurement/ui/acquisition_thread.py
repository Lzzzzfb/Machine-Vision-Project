from __future__ import annotations

import threading
import time

from PySide6.QtCore import QThread, Signal

from angle_measurement.acquisition import MvsCameraSource


class CameraAcquisitionThread(QThread):
    frame_ready = Signal(object)
    camera_connected = Signal()
    camera_disconnected = Signal()
    acquisition_failed = Signal(str)
    frame_rate_changed = Signal(float)

    def __init__(self, exposure_us: float, gain_db: float, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.exposure_us = float(exposure_us)
        self.gain_db = float(gain_db)
        self._stop_requested = threading.Event()

    def request_stop(self) -> None:
        self._stop_requested.set()

    def run(self) -> None:
        source = MvsCameraSource(exposure_us=self.exposure_us, gain_db=self.gain_db)
        frame_times: list[float] = []
        try:
            source.open()
            self.camera_connected.emit()
            timeout_ms = max(1500, int(self.exposure_us / 1000.0) + 750)
            while not self._stop_requested.is_set():
                frame = source.read(timeout_ms)
                now = time.monotonic()
                frame_times.append(now)
                frame_times = [stamp for stamp in frame_times if now - stamp <= 2.0]
                if len(frame_times) >= 2:
                    duration = frame_times[-1] - frame_times[0]
                    if duration > 0:
                        self.frame_rate_changed.emit((len(frame_times) - 1) / duration)
                self.frame_ready.emit(frame)
        except Exception as exc:
            if not self._stop_requested.is_set():
                self.acquisition_failed.emit(str(exc))
        finally:
            try:
                source.close()
            finally:
                self.camera_disconnected.emit()
