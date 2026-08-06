from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import QComboBox, QFormLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

from angle_measurement.models import EdgePolarity, RotatedRoi
from angle_measurement.recipe import BandConfig, BrightBandConfig, MeasurementRecipe

from .widgets import WheelSafeDoubleSpinBox


class RoiInspector(QWidget):
    roi_selected = Signal(str)
    band_updated = Signal(str, object)

    def __init__(self, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self._recipe: MeasurementRecipe | None = None
        self._loading = False
        self.title = QLabel("ROI 参数")
        self.title.setStyleSheet("font-size: 15px; font-weight: 700")
        self.selector = QComboBox()
        self.selector.addItem("亮狭缝中心线", "slit_center")
        self.selector.addItem("平台长边 1", "platform_left")
        self.selector.addItem("平台长边 2", "platform_right")
        self.selector.currentIndexChanged.connect(self._selection_changed)

        group = QGroupBox()
        form = QFormLayout(group)
        form.setVerticalSpacing(6)
        self.center_x = self._spin(-100000, 100000, 2)
        self.center_y = self._spin(-100000, 100000, 2)
        self.roi_length = self._spin(10, 10000, 2)
        self.roi_width = self._spin(4, 2000, 2)
        self.angle = self._spin(-180, 180, 3, "°")
        self.polarity = QComboBox()
        self.polarity.addItem("自动", EdgePolarity.AUTO.value)
        self.polarity.addItem("暗到亮", EdgePolarity.DARK_TO_LIGHT.value)
        self.polarity.addItem("亮到暗", EdgePolarity.LIGHT_TO_DARK.value)
        self.min_contrast = self._spin(0, 255, 2)
        self.min_width = self._spin(0.1, 1000, 2, " px")
        self.max_width = self._spin(0.2, 2000, 2, " px")
        for label, control in (
            ("中心 X", self.center_x),
            ("中心 Y", self.center_y),
            ("长度", self.roi_length),
            ("宽度", self.roi_width),
            ("角度", self.angle),
            ("边缘极性", self.polarity),
            ("亮线最小对比", self.min_contrast),
            ("亮线最小宽度", self.min_width),
            ("亮线最大宽度", self.max_width),
        ):
            form.addRow(label, control)
        for control in (
            self.center_x,
            self.center_y,
            self.roi_length,
            self.roi_width,
            self.angle,
            self.min_contrast,
            self.min_width,
            self.max_width,
        ):
            control.valueChanged.connect(self._emit_update)
        self.polarity.currentIndexChanged.connect(self._emit_update)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.title)
        layout.addWidget(self.selector)
        layout.addWidget(group)

    @staticmethod
    def _spin(
        minimum: float,
        maximum: float,
        decimals: int,
        suffix: str = "",
    ) -> WheelSafeDoubleSpinBox:
        spin = WheelSafeDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(decimals)
        spin.setSuffix(suffix)
        return spin

    @property
    def current_name(self) -> str:
        return str(self.selector.currentData())

    def set_recipe(self, recipe: MeasurementRecipe) -> None:
        self._recipe = recipe
        self._load_controls()

    def set_current_roi(self, name: str) -> None:
        index = self.selector.findData(name)
        if index >= 0 and index != self.selector.currentIndex():
            blocker = QSignalBlocker(self.selector)
            self.selector.setCurrentIndex(index)
            del blocker
        self._load_controls()

    def _selection_changed(self) -> None:
        self._load_controls()
        self.roi_selected.emit(self.current_name)

    def _load_controls(self) -> None:
        if self._recipe is None:
            return
        self._loading = True
        band = getattr(self._recipe, self.current_name)
        controls = (
            self.center_x,
            self.center_y,
            self.roi_length,
            self.roi_width,
            self.angle,
            self.polarity,
            self.min_contrast,
            self.min_width,
            self.max_width,
        )
        blockers = [QSignalBlocker(control) for control in controls]
        self.center_x.setValue(band.roi.center_x)
        self.center_y.setValue(band.roi.center_y)
        self.roi_length.setValue(band.roi.length)
        self.roi_width.setValue(band.roi.width)
        self.angle.setValue(band.roi.angle_deg)
        is_bright = isinstance(band, BrightBandConfig)
        self.polarity.setEnabled(not is_bright)
        self.min_contrast.setEnabled(is_bright)
        self.min_width.setEnabled(is_bright)
        self.max_width.setEnabled(is_bright)
        if is_bright:
            self.min_contrast.setValue(band.bright.min_contrast)
            self.min_width.setValue(band.bright.min_width_px)
            self.max_width.setValue(band.bright.max_width_px)
        else:
            self.polarity.setCurrentIndex(
                max(0, self.polarity.findData(band.edge.polarity.value))
            )
        del blockers
        self._loading = False

    def _emit_update(self) -> None:
        if self._loading or self._recipe is None:
            return
        name = self.current_name
        band = getattr(self._recipe, name)
        roi = RotatedRoi(
            self.center_x.value(),
            self.center_y.value(),
            self.roi_length.value(),
            self.roi_width.value(),
            self.angle.value(),
        )
        if isinstance(band, BrightBandConfig):
            if self.max_width.value() <= self.min_width.value():
                return
            updated = replace(
                band,
                roi=roi,
                bright=replace(
                    band.bright,
                    min_contrast=self.min_contrast.value(),
                    min_width_px=self.min_width.value(),
                    max_width_px=self.max_width.value(),
                ),
            )
        else:
            updated = replace(
                band,
                roi=roi,
                edge=replace(
                    band.edge, polarity=EdgePolarity(str(self.polarity.currentData()))
                ),
            )
        self._recipe = replace(self._recipe, **{name: updated})
        self.band_updated.emit(name, updated)
