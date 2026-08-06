from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal

from angle_measurement.acquisition import Frame
from angle_measurement.models import MeasurementResult, QualityConfig
from angle_measurement.stability import StabilitySnapshot, StabilityTracker


class LiveMeasurementController(QObject):
    measurement_requested = Signal(object)
    stability_changed = Signal(object)
    live_state_changed = Signal(bool)

    def __init__(self, quality: QualityConfig, interval_ms: int = 500, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.interval_ms = int(interval_ms)
        self._timer = QTimer(self)
        self._timer.setInterval(self.interval_ms)
        self._timer.timeout.connect(self._timer_tick)
        self._latest_frame: Frame | None = None
        self._last_requested_frame_id: str | None = None
        self._busy = False
        self._live = False
        self._roi_dragging = False
        self._pending_force = False
        self._tracker = StabilityTracker(
            quality.stability_window_size, quality.stability_std_max_deg
        )

    @property
    def live(self) -> bool:
        return self._live

    @property
    def busy(self) -> bool:
        return self._busy

    @property
    def latest_frame(self) -> Frame | None:
        return self._latest_frame

    @property
    def stability(self) -> StabilitySnapshot:
        return self._tracker.snapshot()

    def configure(self, quality: QualityConfig) -> None:
        self._tracker = StabilityTracker(
            quality.stability_window_size, quality.stability_std_max_deg
        )
        self.stability_changed.emit(self._tracker.snapshot())

    def on_frame(self, frame: Frame) -> None:
        self._latest_frame = frame

    def start(self) -> None:
        if self._live:
            return
        self._live = True
        self._timer.start()
        self.live_state_changed.emit(True)
        self.request_now()

    def stop(self) -> None:
        if not self._live:
            return
        self._live = False
        self._timer.stop()
        self._pending_force = False
        self.live_state_changed.emit(False)

    def reset_stability(self) -> None:
        self.stability_changed.emit(self._tracker.reset())

    def begin_roi_drag(self) -> None:
        self._roi_dragging = True

    def end_roi_drag(self) -> None:
        self._roi_dragging = False
        self.reset_stability()
        self.request_now(force=True)

    def request_now(self, force: bool = False) -> bool:
        frame = self._latest_frame
        if frame is None or self._roi_dragging:
            return False
        if self._busy:
            self._pending_force = self._pending_force or force
            return False
        if not force and frame.frame_id == self._last_requested_frame_id:
            return False
        self._busy = True
        self._last_requested_frame_id = frame.frame_id
        self.measurement_requested.emit(frame)
        return True

    def measurement_completed(self, result: MeasurementResult) -> StabilitySnapshot:
        self._busy = False
        snapshot = self._tracker.add(result)
        self.stability_changed.emit(snapshot)
        if self._pending_force:
            self._pending_force = False
            self.request_now(force=True)
        return snapshot

    def measurement_failed(self) -> None:
        self._busy = False
        invalid = MeasurementResult(False, False, failure_reasons=["测量线程异常"])
        snapshot = self._tracker.add(invalid)
        self.stability_changed.emit(snapshot)
        if self._pending_force:
            self._pending_force = False
            self.request_now(force=True)

    def measurement_discarded(self) -> None:
        self._busy = False
        if self._pending_force:
            self._pending_force = False
            self.request_now(force=True)

    def _timer_tick(self) -> None:
        if self._live:
            self.request_now()
