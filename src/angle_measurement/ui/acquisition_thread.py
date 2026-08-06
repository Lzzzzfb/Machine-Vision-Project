from __future__ import annotations

import threading
import time

from PySide6.QtCore import QThread, Signal

from angle_measurement.acquisition import Frame, MvsCameraSource


class CameraAcquisitionThread(QThread):
    frame_available = Signal()
    camera_connected = Signal()
    camera_disconnected = Signal()
    acquisition_failed = Signal(str)
    frame_rate_changed = Signal(float)

    def __init__(self, exposure_us: float, gain_db: float, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.exposure_us = float(exposure_us)
        self.gain_db = float(gain_db)
        self._stop_requested = threading.Event()
        self._frame_lock = threading.Lock()
        self._latest_frame: Frame | None = None
        self._notification_pending = False
        self._last_fps_emit_at: float | None = None

    def request_stop(self) -> None:
        self._stop_requested.set()

    def take_latest_frame(self) -> Frame | None:
        """Take the newest frame and allow one subsequent availability notification."""

        with self._frame_lock:
            frame = self._latest_frame
            self._latest_frame = None
            self._notification_pending = False
            return frame

    def _publish_frame(self, frame: Frame) -> None:
        should_notify = False
        with self._frame_lock:
            self._latest_frame = frame
            if not self._notification_pending:
                self._notification_pending = True
                should_notify = True
        if should_notify:
            self.frame_available.emit()

    def _should_emit_frame_rate(self, now: float) -> bool:
        if self._last_fps_emit_at is None or now - self._last_fps_emit_at >= 0.5:
            self._last_fps_emit_at = now
            return True
        return False

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
                    if duration > 0 and self._should_emit_frame_rate(now):
                        self.frame_rate_changed.emit((len(frame_times) - 1) / duration)
                self._publish_frame(frame)
        except Exception as exc:
            if not self._stop_requested.is_set():
                self.acquisition_failed.emit(str(exc))
        finally:
            try:
                source.close()
            finally:
                self.camera_disconnected.emit()
