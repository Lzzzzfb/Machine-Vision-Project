from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import QSignalBlocker, Qt, QThreadPool, QTimer
from PySide6.QtGui import QAction, QColor, QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from angle_measurement.acquisition import Frame, ImageFileSource, MvsCameraSource
from angle_measurement.calibration.model import CalibrationData
from angle_measurement.measurement.service import AngleMeasurementService
from angle_measurement.models import EdgePolarity, MeasurementResult, RotatedRoi
from angle_measurement.recipe import BandConfig, MeasurementRecipe, default_recipe
from angle_measurement.storage import ResultStorageError, ResultWriter

from .roi_item import EditableRoiItem
from .worker import CaptureMeasurementTask, MeasurementTask


def array_to_qimage(image: np.ndarray) -> QImage:
    if image.ndim == 2:
        contiguous = np.ascontiguousarray(image)
        result = QImage(
            contiguous.data,
            contiguous.shape[1],
            contiguous.shape[0],
            contiguous.strides[0],
            QImage.Format_Grayscale8,
        )
    else:
        if image.shape[2] == 4:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGRA2RGBA)
            image_format = QImage.Format_RGBA8888
        else:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            image_format = QImage.Format_RGB888
        contiguous = np.ascontiguousarray(rgb)
        result = QImage(
            contiguous.data,
            contiguous.shape[1],
            contiguous.shape[0],
            contiguous.strides[0],
            image_format,
        )
    return result.copy()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("狭缝与平台二维夹角测量")
        self.resize(1380, 860)
        self.recipe = default_recipe()
        self.calibration: CalibrationData | None = None
        self.current_frame: Frame | None = None
        self.camera_source: MvsCameraSource | None = None
        self._recipe_explicitly_loaded = False
        self._busy = False
        self._roi_items: dict[str, EditableRoiItem] = {}
        self.thread_pool = QThreadPool.globalInstance()
        self.continuous_timer = QTimer(self)
        self.continuous_timer.setInterval(350)
        self.continuous_timer.timeout.connect(self._continuous_tick)

        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHints(self.view.renderHints())
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.view.setBackgroundBrush(QColor(35, 38, 43))

        splitter = QSplitter()
        splitter.addWidget(self.view)
        splitter.addWidget(self._build_controls())
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 2)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setSizes([1000, 380])
        self.setCentralWidget(splitter)
        self._build_menu()
        self.statusBar().showMessage("打开本地图片或连接 MVS 相机")

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("文件")
        open_action = QAction("打开图片", self)
        open_action.triggered.connect(self.open_image)
        file_menu.addAction(open_action)
        load_action = QAction("加载配方", self)
        load_action.triggered.connect(self.load_recipe)
        file_menu.addAction(load_action)
        save_action = QAction("保存配方", self)
        save_action.triggered.connect(self.save_recipe)
        file_menu.addAction(save_action)

    def _build_controls(self) -> QWidget:
        body = QWidget()
        layout = QVBoxLayout(body)

        source_group = QGroupBox("图像源")
        source_form = QFormLayout(source_group)
        self.source_mode = QComboBox()
        self.source_mode.addItems(["本地图片", "MVS 相机"])
        source_form.addRow("模式", self.source_mode)
        open_button = QPushButton("打开图片")
        open_button.clicked.connect(self.open_image)
        source_form.addRow(open_button)
        self.exposure_spin = QDoubleSpinBox()
        self.exposure_spin.setRange(15, 10_000_000)
        self.exposure_spin.setValue(5000)
        self.exposure_spin.setSuffix(" µs")
        source_form.addRow("曝光", self.exposure_spin)
        self.gain_spin = QDoubleSpinBox()
        self.gain_spin.setRange(0, 24)
        self.gain_spin.setValue(0)
        self.gain_spin.setSuffix(" dB")
        source_form.addRow("增益", self.gain_spin)
        camera_buttons = QHBoxLayout()
        connect_button = QPushButton("连接 MVS")
        connect_button.clicked.connect(self.connect_camera)
        capture_button = QPushButton("采集并测量")
        capture_button.clicked.connect(self.capture_and_measure)
        camera_buttons.addWidget(connect_button)
        camera_buttons.addWidget(capture_button)
        source_form.addRow(camera_buttons)
        layout.addWidget(source_group)

        config_group = QGroupBox("配置与标定")
        config_form = QFormLayout(config_group)
        self.recipe_path = QLineEdit("configs/example_recipe.json")
        self.recipe_path.setReadOnly(True)
        config_form.addRow("配方", self.recipe_path)
        recipe_buttons = QHBoxLayout()
        load_recipe = QPushButton("加载")
        load_recipe.clicked.connect(self.load_recipe)
        save_recipe = QPushButton("另存")
        save_recipe.clicked.connect(self.save_recipe)
        recipe_buttons.addWidget(load_recipe)
        recipe_buttons.addWidget(save_recipe)
        config_form.addRow(recipe_buttons)
        self.calibration_label = QLabel("未标定")
        self.calibration_label.setStyleSheet("color: #ffb347")
        config_form.addRow("标定", self.calibration_label)
        load_calibration = QPushButton("加载标定文件")
        load_calibration.clicked.connect(self.load_calibration)
        config_form.addRow(load_calibration)
        layout.addWidget(config_group)

        roi_group = QGroupBox("测量带 ROI")
        roi_form = QFormLayout(roi_group)
        self.band_selector = QComboBox()
        self.band_selector.addItem("狭缝边缘", "slit")
        self.band_selector.addItem("平台边缘", "platform")
        self.band_selector.currentIndexChanged.connect(self._load_band_controls)
        roi_form.addRow("当前测量带", self.band_selector)
        self.roi_x = self._coordinate_spin()
        self.roi_y = self._coordinate_spin()
        self.roi_length = self._size_spin(10, 10000)
        self.roi_width = self._size_spin(4, 2000)
        self.roi_angle = QDoubleSpinBox()
        self.roi_angle.setRange(-180, 180)
        self.roi_angle.setDecimals(3)
        self.roi_angle.setSuffix("°")
        self.polarity = QComboBox()
        self.polarity.addItem("自动", EdgePolarity.AUTO.value)
        self.polarity.addItem("暗到亮", EdgePolarity.DARK_TO_LIGHT.value)
        self.polarity.addItem("亮到暗", EdgePolarity.LIGHT_TO_DARK.value)
        roi_form.addRow("中心 X", self.roi_x)
        roi_form.addRow("中心 Y", self.roi_y)
        roi_form.addRow("长度", self.roi_length)
        roi_form.addRow("宽度", self.roi_width)
        roi_form.addRow("角度", self.roi_angle)
        roi_form.addRow("边缘极性", self.polarity)
        apply_roi = QPushButton("应用 ROI 参数")
        apply_roi.clicked.connect(self._apply_band_controls)
        roi_form.addRow(apply_roi)
        layout.addWidget(roi_group)

        measurement_group = QGroupBox("测量")
        measurement_form = QFormLayout(measurement_group)
        measure_button = QPushButton("测量当前图像")
        measure_button.clicked.connect(self.measure_current)
        measurement_form.addRow(measure_button)
        self.continuous_check = QCheckBox("连续测量")
        self.continuous_check.toggled.connect(self._toggle_continuous)
        measurement_form.addRow(self.continuous_check)
        self.angle_label = QLabel("--")
        self.angle_label.setStyleSheet("font-size: 24px; font-weight: 700")
        measurement_form.addRow("夹角", self.angle_label)
        self.confidence_label = QLabel("--")
        measurement_form.addRow("置信度", self.confidence_label)
        self.quality_label = QLabel("等待测量")
        self.quality_label.setWordWrap(True)
        measurement_form.addRow("状态", self.quality_label)
        layout.addWidget(measurement_group)

        output_group = QGroupBox("结果保存")
        output_form = QFormLayout(output_group)
        self.auto_save = QCheckBox("自动保存原图、叠加图和 CSV")
        output_form.addRow(self.auto_save)
        self.output_path = QLineEdit("data/output")
        output_form.addRow("目录", self.output_path)
        browse_output = QPushButton("选择目录")
        browse_output.clicked.connect(self.choose_output)
        output_form.addRow(browse_output)
        layout.addWidget(output_group)
        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(350)
        scroll.setWidget(body)
        self._load_band_controls()
        return scroll

    @staticmethod
    def _coordinate_spin() -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(-100000, 100000)
        spin.setDecimals(2)
        return spin

    @staticmethod
    def _size_spin(minimum: float, maximum: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(2)
        return spin

    def _current_band_name(self) -> str:
        return str(self.band_selector.currentData())

    def _get_band(self, name: str) -> BandConfig:
        return self.recipe.slit if name == "slit" else self.recipe.platform

    def _set_band(self, name: str, band: BandConfig) -> None:
        self.recipe = replace(self.recipe, **{name: band})

    def _load_band_controls(self) -> None:
        if not hasattr(self, "roi_x"):
            return
        band = self._get_band(self._current_band_name())
        controls = [self.roi_x, self.roi_y, self.roi_length, self.roi_width, self.roi_angle]
        blockers = [QSignalBlocker(control) for control in controls]
        self.roi_x.setValue(band.roi.center_x)
        self.roi_y.setValue(band.roi.center_y)
        self.roi_length.setValue(band.roi.length)
        self.roi_width.setValue(band.roi.width)
        self.roi_angle.setValue(band.roi.angle_deg)
        index = self.polarity.findData(band.edge.polarity.value)
        self.polarity.setCurrentIndex(max(index, 0))
        del blockers

    def _apply_band_controls(self) -> None:
        name = self._current_band_name()
        band = self._get_band(name)
        roi = RotatedRoi(
            self.roi_x.value(),
            self.roi_y.value(),
            self.roi_length.value(),
            self.roi_width.value(),
            self.roi_angle.value(),
        )
        edge = replace(band.edge, polarity=EdgePolarity(self.polarity.currentData()))
        self._set_band(name, replace(band, roi=roi, edge=edge))
        if name in self._roi_items:
            self._roi_items[name].set_roi(roi)
        self.statusBar().showMessage("ROI 已更新；请保存配方")

    def _roi_item_changed(self, name: str, roi: RotatedRoi) -> None:
        band = self._get_band(name)
        self._set_band(name, replace(band, roi=roi))
        if self._current_band_name() == name:
            self._load_band_controls()

    def _display(self, image: np.ndarray) -> None:
        self.scene.clear()
        pixmap = QPixmap.fromImage(array_to_qimage(image))
        item = QGraphicsPixmapItem(pixmap)
        item.setZValue(0)
        self.scene.addItem(item)
        self.scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())
        self._roi_items = {}
        for name, band, color in (
            ("slit", self.recipe.slit, QColor(255, 150, 0)),
            ("platform", self.recipe.platform, QColor(0, 210, 255)),
        ):
            roi_item = EditableRoiItem(name, band.roi, color)
            roi_item.roi_changed.connect(self._roi_item_changed)
            self.scene.addItem(roi_item)
            self._roi_items[name] = roi_item
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    def open_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "打开测量图片",
            "data/input",
            "Images (*.png *.bmp *.jpg *.jpeg *.tif *.tiff)",
        )
        if not path:
            return
        try:
            source = ImageFileSource(path)
            source.open()
            frame = source.read()
            source.close()
        except Exception as exc:
            self._error(str(exc))
            return
        self.current_frame = frame
        if not self._recipe_explicitly_loaded:
            self.recipe = default_recipe(frame.image.shape[1], frame.image.shape[0])
        self._display(frame.image)
        self._load_band_controls()
        self.statusBar().showMessage(f"已打开 {path}")

    def load_recipe(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "加载测量配方", "configs", "JSON (*.json)")
        if not path:
            return
        try:
            self.recipe = MeasurementRecipe.load(path)
        except Exception as exc:
            self._error(f"加载配方失败: {exc}")
            return
        self._recipe_explicitly_loaded = True
        self.recipe_path.setText(path)
        self._load_band_controls()
        if self.current_frame is not None:
            self._display(self.current_frame.image)

    def save_recipe(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "保存测量配方",
            self.recipe_path.text(),
            "JSON (*.json)",
        )
        if not path:
            return
        try:
            self.recipe.save(path)
        except Exception as exc:
            self._error(f"保存配方失败: {exc}")
            return
        self.recipe_path.setText(path)
        self.statusBar().showMessage(f"配方已保存: {path}")

    def load_calibration(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "加载标定文件", "calibration", "JSON (*.json)")
        if not path:
            return
        try:
            self.calibration = CalibrationData.load(path)
        except Exception as exc:
            self._error(f"加载标定文件失败: {exc}")
            return
        self.calibration_label.setText(
            f"已标定 · RMS {self.calibration.rms_reprojection_error:.3f} px"
        )
        self.calibration_label.setStyleSheet("color: #66d17a")

    def connect_camera(self) -> None:
        if self.camera_source is not None:
            self.camera_source.close()
        source = MvsCameraSource(
            exposure_us=self.exposure_spin.value(),
            gain_db=self.gain_spin.value(),
        )
        try:
            source.open()
        except Exception as exc:
            self._error(str(exc))
            return
        self.camera_source = source
        self.source_mode.setCurrentIndex(1)
        self.statusBar().showMessage("MVS 相机已连接，Mono 8 / 软件触发")

    def _service(self) -> AngleMeasurementService:
        return AngleMeasurementService(self.recipe, self.calibration)

    def measure_current(self) -> None:
        if self.current_frame is None:
            self._error("请先打开图片或采集一帧")
            return
        if self._busy:
            return
        self._busy = True
        task = MeasurementTask(self.current_frame, self._service(), self.recipe)
        task.signals.completed.connect(self._measurement_completed)
        task.signals.failed.connect(self._worker_failed)
        self.thread_pool.start(task)

    def capture_and_measure(self) -> None:
        if self.camera_source is None:
            self._error("请先连接 MVS 相机")
            return
        if self._busy:
            return
        self._busy = True
        task = CaptureMeasurementTask(self.camera_source, self._service(), self.recipe)
        task.signals.completed.connect(self._measurement_completed)
        task.signals.failed.connect(self._worker_failed)
        self.thread_pool.start(task)

    def _measurement_completed(
        self,
        frame: Frame,
        result: MeasurementResult,
        overlay: np.ndarray,
    ) -> None:
        self._busy = False
        self.current_frame = frame
        self._display(overlay)
        if result.valid:
            self.angle_label.setText(f"{result.angle_deg:.4f}°")
            self.confidence_label.setText(f"{result.confidence:.3f}")
            calibration = "已标定" if result.calibrated else "未标定"
            self.quality_label.setText(f"有效 · {calibration}")
            self.quality_label.setStyleSheet("color: #66d17a")
        else:
            self.angle_label.setText("--")
            self.confidence_label.setText(f"{result.confidence:.3f}")
            self.quality_label.setText("无效 · " + "；".join(result.failure_reasons))
            self.quality_label.setStyleSheet("color: #ff6666")
        if self.auto_save.isChecked():
            try:
                ResultWriter(self.output_path.text()).write(
                    frame.image,
                    overlay,
                    result,
                    frame_id=frame.frame_id,
                    source_name=str(frame.metadata.get("source_path", frame.metadata.get("source_type", "unknown"))),
                    recipe_name=self.recipe.name,
                    timestamp=frame.timestamp,
                    metadata=frame.metadata,
                )
            except ResultStorageError as exc:
                self.statusBar().showMessage(str(exc))

    def _worker_failed(self, traceback_text: str) -> None:
        self._busy = False
        self._error(traceback_text.splitlines()[-1] if traceback_text else "后台任务失败")

    def _toggle_continuous(self, enabled: bool) -> None:
        if enabled:
            self.continuous_timer.start()
        else:
            self.continuous_timer.stop()

    def _continuous_tick(self) -> None:
        if self._busy:
            return
        if self.source_mode.currentIndex() == 1:
            self.capture_and_measure()
        else:
            self.measure_current()

    def choose_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择结果目录", self.output_path.text())
        if path:
            self.output_path.setText(path)

    def _error(self, message: str) -> None:
        self.statusBar().showMessage(message)
        QMessageBox.critical(self, "错误", message)

    def closeEvent(self, event) -> None:  # noqa: ANN001
        self.continuous_timer.stop()
        if self.camera_source is not None:
            self.camera_source.close()
        self.thread_pool.waitForDone(2000)
        super().closeEvent(event)
