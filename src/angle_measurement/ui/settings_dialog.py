from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from .widgets import WheelSafeDoubleSpinBox


@dataclass(frozen=True)
class SettingsValues:
    exposure_us: float
    gain_db: float
    recipe_path: str
    recipe_action: str
    calibration_path: str
    height_difference_mm: float | None
    output_path: str


class SettingsDialog(QDialog):
    def __init__(
        self,
        values: SettingsValues,
        calibration_status: str,
        camera_status: str,
        parent=None,  # noqa: ANN001
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setModal(True)
        self.setMinimumWidth(620)
        self._recipe_action = values.recipe_action

        camera_group = QGroupBox("相机")
        camera_form = QFormLayout(camera_group)
        camera_form.addRow("状态", QLabel(camera_status))
        self.exposure = self._spin(15, 10_000_000, 2, " µs", values.exposure_us)
        self.gain = self._spin(0, 24, 2, " dB", values.gain_db)
        camera_form.addRow("曝光", self.exposure)
        camera_form.addRow("增益", self.gain)

        config_group = QGroupBox("配方与标定")
        config_form = QFormLayout(config_group)
        self.recipe_path = QLineEdit(values.recipe_path)
        self.recipe_path.setReadOnly(True)
        recipe_row = QHBoxLayout()
        recipe_row.addWidget(self.recipe_path, 1)
        load_recipe = QPushButton("加载…")
        save_recipe = QPushButton("另存当前配方…")
        load_recipe.clicked.connect(self._choose_recipe)
        save_recipe.clicked.connect(self._choose_recipe_save)
        recipe_row.addWidget(load_recipe)
        recipe_row.addWidget(save_recipe)
        config_form.addRow("配方", recipe_row)
        self.calibration_path = QLineEdit(values.calibration_path)
        self.calibration_path.setReadOnly(True)
        calibration_row = QHBoxLayout()
        calibration_row.addWidget(self.calibration_path, 1)
        choose_calibration = QPushButton("加载…")
        choose_calibration.clicked.connect(self._choose_calibration)
        calibration_row.addWidget(choose_calibration)
        config_form.addRow("标定文件", calibration_row)
        config_form.addRow("标定状态", QLabel(calibration_status))
        self.height_difference = self._spin(-1, 1000, 3, " mm", -1)
        self.height_difference.setSpecialValueText("未设置")
        self.height_difference.setValue(
            -1 if values.height_difference_mm is None else values.height_difference_mm
        )
        config_form.addRow("狭缝高度差", self.height_difference)

        output_group = QGroupBox("结果保存")
        output_form = QFormLayout(output_group)
        self.output_path = QLineEdit(values.output_path)
        output_row = QHBoxLayout()
        output_row.addWidget(self.output_path, 1)
        choose_output = QPushButton("浏览…")
        choose_output.clicked.connect(self._choose_output)
        output_row.addWidget(choose_output)
        output_form.addRow("保存目录", output_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("应用")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(camera_group)
        layout.addWidget(config_group)
        layout.addWidget(output_group)
        layout.addWidget(buttons)

    @staticmethod
    def _spin(
        minimum: float, maximum: float, decimals: int, suffix: str, value: float
    ) -> WheelSafeDoubleSpinBox:
        spin = WheelSafeDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(decimals)
        spin.setSuffix(suffix)
        spin.setValue(value)
        return spin

    def _choose_recipe(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "加载测量配方", "configs", "JSON (*.json)")
        if path:
            self.recipe_path.setText(path)
            self._recipe_action = "load"

    def _choose_recipe_save(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "保存测量配方", self.recipe_path.text(), "JSON (*.json)"
        )
        if path:
            self.recipe_path.setText(path)
            self._recipe_action = "save"

    def _choose_calibration(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "加载标定文件", "calibration", "JSON (*.json)"
        )
        if path:
            self.calibration_path.setText(path)

    def _choose_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择结果保存目录", self.output_path.text())
        if path:
            self.output_path.setText(path)

    def accept(self) -> None:
        if self._recipe_action == "load" and not Path(self.recipe_path.text()).is_file():
            QMessageBox.warning(self, "设置无效", "所选配方文件不存在")
            return
        calibration = self.calibration_path.text().strip()
        if calibration and not Path(calibration).is_file():
            QMessageBox.warning(self, "设置无效", "所选标定文件不存在")
            return
        output = self.output_path.text().strip()
        if not output:
            QMessageBox.warning(self, "设置无效", "保存目录不能为空")
            return
        destination = Path(output)
        writable_target = destination if destination.is_dir() else destination.parent
        if not writable_target.exists() or not os.access(writable_target, os.W_OK):
            QMessageBox.warning(self, "设置无效", "保存目录不存在或不可写")
            return
        super().accept()

    def values(self) -> SettingsValues:
        return SettingsValues(
            exposure_us=self.exposure.value(),
            gain_db=self.gain.value(),
            recipe_path=self.recipe_path.text(),
            recipe_action=self._recipe_action,
            calibration_path=self.calibration_path.text(),
            height_difference_mm=(
                None
                if self.height_difference.value() < 0
                else self.height_difference.value()
            ),
            output_path=self.output_path.text(),
        )
