from __future__ import annotations

import traceback

import numpy as np
from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from angle_measurement.acquisition import Frame, FrameSource
from angle_measurement.measurement.overlay import draw_measurement_overlay
from angle_measurement.measurement.service import AngleMeasurementService
from angle_measurement.recipe import MeasurementRecipe


class WorkerSignals(QObject):
    completed = Signal(object, object, object)
    failed = Signal(str)


class MeasurementTask(QRunnable):
    def __init__(
        self,
        frame: Frame,
        service: AngleMeasurementService,
        recipe: MeasurementRecipe,
    ) -> None:
        super().__init__()
        self.frame = frame
        self.service = service
        self.recipe = recipe
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.service.measure(np.array(self.frame.image, copy=True))
            overlay = draw_measurement_overlay(self.frame.image, self.recipe, result)
            self.signals.completed.emit(self.frame, result, overlay)
        except Exception:
            self.signals.failed.emit(traceback.format_exc())


class CaptureMeasurementTask(QRunnable):
    def __init__(
        self,
        source: FrameSource,
        service: AngleMeasurementService,
        recipe: MeasurementRecipe,
        timeout_ms: int = 1500,
    ) -> None:
        super().__init__()
        self.source = source
        self.service = service
        self.recipe = recipe
        self.timeout_ms = timeout_ms
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            frame = self.source.read(self.timeout_ms)
            result = self.service.measure(frame.image)
            overlay = draw_measurement_overlay(frame.image, self.recipe, result)
            self.signals.completed.emit(frame, result, overlay)
        except Exception:
            self.signals.failed.emit(traceback.format_exc())
