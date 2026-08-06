from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QSettings, QSignalBlocker, QThreadPool, QTimer, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from angle_measurement.acquisition import Frame, ImageFileSource
from angle_measurement.calibration.model import CalibrationData
from angle_measurement.measurement.overlay import draw_measurement_overlay
from angle_measurement.measurement.service import AngleMeasurementService
from angle_measurement.models import MeasurementResult, RotatedRoi
from angle_measurement.recipe import BandConfig, BrightBandConfig, MeasurementRecipe, default_recipe
from angle_measurement.storage import ResultStorageError, ResultWriter

from .acquisition_thread import CameraAcquisitionThread
from .image_view import DualImagePanel
from .live_controller import LiveMeasurementController
from .measurement_summary import MeasurementSummary
from .roi_inspector import RoiInspector
from .settings_dialog import SettingsDialog, SettingsValues
from .worker import MeasurementTask


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("狭缝与平台二维夹角测量")
        self.resize(1680, 920)
        self.setMinimumSize(1180, 700)
        self.app_settings = QSettings("Lzzzzfb", "HikrobotAngleMeasurement")
        self.recipe_path = str(
            self.app_settings.value("paths/recipe", "configs/example_recipe.json")
        )
        self.calibration_path = str(self.app_settings.value("paths/calibration", ""))
        self.output_path = str(self.app_settings.value("paths/output", "data/output"))
        self.exposure_us = float(self.app_settings.value("camera/exposure_us", 5000.0))
        self.gain_db = float(self.app_settings.value("camera/gain_db", 0.0))
        self.recipe = self._load_initial_recipe()
        self.calibration = self._load_initial_calibration()
        self.current_frame: Frame | None = None
        self.last_measured_frame: Frame | None = None
        self.last_result: MeasurementResult | None = None
        self.last_measurement_recipe: MeasurementRecipe | None = None
        self.last_overlay = None
        self.acquisition_thread: CameraAcquisitionThread | None = None
        self._camera_connected = False
        self._resume_live_after_connect = False
        self._camera_rollback: tuple[float, float, bool] | None = None
        self._restart_after_failure = False
        self._measurement_completed_times: list[float] = []
        self._recipe_revision = 0
        self._actual_camera_fps = 0.0
        self._actual_measurement_fps = 0.0
        self.thread_pool = QThreadPool.globalInstance()

        self.image_panel = DualImagePanel()
        self.roi_inspector = RoiInspector()
        self.summary = MeasurementSummary()
        self.live_controller = LiveMeasurementController(self.recipe.quality, parent=self)
        self._build_actions()
        self._build_toolbar()
        self._build_central_layout()
        self._build_menu()
        self._connect_signals()
        self.image_panel.set_recipe(self.recipe)
        self.roi_inspector.set_recipe(self.recipe)
        self.summary.set_stability(self.live_controller.stability)
        self._build_status_widgets()
        self._update_action_states()
        self.statusBar().showMessage("打开本地图片或连接 MVS 相机")

    def _load_initial_recipe(self) -> MeasurementRecipe:
        path = Path(self.recipe_path)
        if path.is_file():
            try:
                return MeasurementRecipe.load(path)
            except Exception:
                pass
        return default_recipe()

    def _load_initial_calibration(self) -> CalibrationData | None:
        path = Path(self.calibration_path)
        if path.is_file():
            try:
                return CalibrationData.load(path)
            except Exception:
                pass
        return None

    def _build_actions(self) -> None:
        self.open_action = QAction("打开图片", self)
        self.open_action.setShortcut(QKeySequence.Open)
        self.connect_action = QAction("连接相机", self)
        self.measure_action = QAction("单次测量", self)
        self.measure_action.setShortcut("F5")
        self.live_action = QAction("实时测量", self)
        self.live_action.setCheckable(True)
        self.save_action = QAction("保存当前结果", self)
        self.save_action.setShortcut(QKeySequence.Save)
        self.show_roi_action = QAction("显示 ROI", self)
        self.show_roi_action.setCheckable(True)
        self.show_roi_action.setChecked(
            self.app_settings.value("view/show_roi", True, type=bool)
        )
        self.show_aux_action = QAction("显示辅助线", self)
        self.show_aux_action.setCheckable(True)
        self.show_aux_action.setChecked(
            self.app_settings.value("view/show_auxiliary", True, type=bool)
        )
        self.fit_action = QAction("适合窗口", self)
        self.actual_action = QAction("100%", self)
        self.settings_action = QAction("设置", self)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("主工具栏", self)
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextOnly)
        for action in (
            self.open_action,
            self.connect_action,
            self.measure_action,
            self.live_action,
            self.save_action,
        ):
            toolbar.addAction(action)
        toolbar.addSeparator()
        for action in (
            self.show_roi_action,
            self.show_aux_action,
            self.fit_action,
            self.actual_action,
        ):
            toolbar.addAction(action)
        toolbar.addSeparator()
        toolbar.addAction(self.settings_action)
        self.addToolBar(toolbar)

    def _build_central_layout(self) -> None:
        side = QWidget()
        side.setMinimumWidth(315)
        side.setMaximumWidth(370)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(8, 0, 0, 0)
        side_layout.setSpacing(8)
        side_layout.addWidget(self.roi_inspector)
        side_layout.addWidget(self.summary)
        side_layout.addStretch(1)
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(6, 6, 6, 4)
        layout.setSpacing(6)
        layout.addWidget(self.image_panel, 1)
        layout.addWidget(side)
        self.setCentralWidget(central)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("文件")
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.save_action)
        file_menu.addSeparator()
        file_menu.addAction(self.settings_action)
        file_menu.addSeparator()
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def _build_status_widgets(self) -> None:
        self.camera_status = QLabel("相机：未连接")
        self.fps_status = QLabel("采集：-- fps　测量：-- Hz")
        self.measurement_status = QLabel("状态：等待")
        self.save_status = QLabel("最近保存：--")
        for label in (
            self.camera_status,
            self.fps_status,
            self.measurement_status,
            self.save_status,
        ):
            self.statusBar().addPermanentWidget(label)

    def _connect_signals(self) -> None:
        self.open_action.triggered.connect(self.open_image)
        self.connect_action.triggered.connect(self.toggle_camera)
        self.measure_action.triggered.connect(self.measure_current)
        self.live_action.toggled.connect(self._toggle_live)
        self.save_action.triggered.connect(self.save_current_result)
        self.show_roi_action.toggled.connect(self._toggle_roi_visibility)
        self.show_aux_action.toggled.connect(self._toggle_auxiliary_visibility)
        self.fit_action.triggered.connect(self.image_panel.fit_views)
        self.actual_action.triggered.connect(self.image_panel.actual_pixels)
        self.settings_action.triggered.connect(self.show_settings)
        self.image_panel.roi_selected.connect(self._select_roi)
        self.image_panel.roi_changed.connect(self._roi_from_scene)
        self.image_panel.roi_drag_started.connect(self._roi_drag_started)
        self.image_panel.roi_drag_finished.connect(self._roi_drag_finished)
        self.roi_inspector.roi_selected.connect(self._select_roi_from_inspector)
        self.roi_inspector.band_updated.connect(self._band_from_inspector)
        self.live_controller.measurement_requested.connect(self._start_measurement)
        self.live_controller.stability_changed.connect(self.summary.set_stability)
        self.live_controller.live_state_changed.connect(self._live_state_changed)
        self.image_panel.set_roi_visible(self.show_roi_action.isChecked())

    def open_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "打开测量图片",
            "data/input",
            "Images (*.png *.bmp *.jpg *.jpeg *.tif *.tiff)",
        )
        if not path:
            return
        self.disconnect_camera()
        try:
            source = ImageFileSource(path)
            source.open()
            frame = source.read()
            source.close()
        except Exception as exc:
            self._error(str(exc))
            return
        if self.recipe.slit_center.roi.center_x > frame.image.shape[1] * 1.5:
            self.recipe = default_recipe(frame.image.shape[1], frame.image.shape[0])
            self._recipe_changed()
        self._clear_measurement_state()
        self.current_frame = frame
        self.live_controller.on_frame(frame)
        self.image_panel.set_images(frame.image)
        self.image_panel.set_raw_context(frame.frame_id)
        self.image_panel.set_recipe(self.recipe)
        self.camera_status.setText("来源：本地图片")
        self.statusBar().showMessage(f"已打开 {path}")
        self._update_action_states()

    def toggle_camera(self) -> None:
        if self.acquisition_thread is not None:
            self.disconnect_camera()
        else:
            self._start_camera()

    def _start_camera(self) -> None:
        if self.acquisition_thread is not None:
            return
        self._clear_measurement_state()
        thread = CameraAcquisitionThread(self.exposure_us, self.gain_db, self)
        thread.camera_connected.connect(self._camera_opened)
        thread.camera_disconnected.connect(self._camera_closed)
        thread.frame_ready.connect(self._frame_received)
        thread.frame_rate_changed.connect(self._camera_fps_changed)
        thread.acquisition_failed.connect(self._acquisition_failed)
        thread.finished.connect(self._acquisition_finished)
        self.acquisition_thread = thread
        self.connect_action.setEnabled(False)
        self.camera_status.setText("相机：连接中…")
        thread.start()

    def disconnect_camera(self) -> None:
        self.live_controller.stop()
        blocker = QSignalBlocker(self.live_action)
        self.live_action.setChecked(False)
        del blocker
        thread = self.acquisition_thread
        if thread is not None:
            thread.request_stop()
            timeout_ms = max(3000, int(self.exposure_us / 1000.0) + 2500)
            thread.wait(timeout_ms)
            self.acquisition_thread = None
            thread.deleteLater()
        self._camera_connected = False
        self.connect_action.setText("连接相机")
        self.connect_action.setEnabled(True)
        self.camera_status.setText("相机：未连接")
        self._update_action_states()

    def _camera_opened(self) -> None:
        self._camera_connected = True
        self.connect_action.setEnabled(True)
        self.connect_action.setText("断开相机")
        self.camera_status.setText("相机：已连接")
        if self._camera_rollback is not None:
            self._camera_rollback = None
        if self._resume_live_after_connect:
            self._resume_live_after_connect = False
            self.live_action.setChecked(True)
        self._update_action_states()

    def _camera_closed(self) -> None:
        self._camera_connected = False
        self.connect_action.setText("连接相机")
        self.camera_status.setText("相机：未连接")
        self._update_action_states()

    def _acquisition_finished(self) -> None:
        thread = self.sender()
        if self.acquisition_thread is thread:
            self.acquisition_thread = None
        self.connect_action.setEnabled(True)
        if self._restart_after_failure:
            self._restart_after_failure = False
            QTimer.singleShot(0, self._start_camera)

    def _acquisition_failed(self, message: str) -> None:
        self.live_controller.stop()
        blocker = QSignalBlocker(self.live_action)
        self.live_action.setChecked(False)
        del blocker
        if self._camera_rollback is not None:
            old_exposure, old_gain, was_live = self._camera_rollback
            self._camera_rollback = None
            self.exposure_us = old_exposure
            self.gain_db = old_gain
            self._resume_live_after_connect = was_live
            self._restart_after_failure = True
            self._persist_settings()
            QMessageBox.warning(
                self,
                "相机设置未应用",
                f"新曝光或增益应用失败，正在恢复旧设置。\n{message}",
            )
            return
        self._error(message)

    def _frame_received(self, frame: Frame) -> None:
        first = self.current_frame is None or self.current_frame.image.shape != frame.image.shape
        self.current_frame = frame
        self.live_controller.on_frame(frame)
        self.image_panel.set_raw_context(frame.frame_id)
        if first or self.last_result is None:
            self.image_panel.set_images(frame.image)
            self.image_panel.set_recipe(self.recipe)
        else:
            self.image_panel.set_raw_image(frame.image)
        self._update_action_states()

    def _camera_fps_changed(self, fps: float) -> None:
        self._actual_camera_fps = float(fps)
        self._update_fps_status()

    def measure_current(self) -> None:
        if self.current_frame is None:
            self._error("请先打开图片或连接相机等待一帧")
            return
        self.live_controller.on_frame(self.current_frame)
        if not self.live_controller.request_now(force=True):
            self.statusBar().showMessage("测量任务正在运行，已使用最新帧排队一次重测")
        self._update_action_states()

    def _start_measurement(self, frame: Frame) -> None:
        recipe_snapshot = self.recipe
        recipe_revision = self._recipe_revision
        task = MeasurementTask(
            frame,
            AngleMeasurementService(recipe_snapshot, self.calibration),
            recipe_snapshot,
            show_auxiliary=self.show_aux_action.isChecked(),
        )
        task.signals.completed.connect(
            lambda measured_frame, result, overlay, recipe=recipe_snapshot, revision=recipe_revision: self._measurement_completed(
                measured_frame, result, overlay, recipe, revision
            )
        )
        task.signals.failed.connect(self._measurement_worker_failed)
        self.measurement_status.setText("状态：测量中")
        self.thread_pool.start(task)
        self._update_action_states()

    def _measurement_completed(
        self,
        frame: Frame,
        result: MeasurementResult,
        overlay,
        recipe_snapshot: MeasurementRecipe,
        recipe_revision: int,
    ) -> None:
        if recipe_revision != self._recipe_revision:
            self.live_controller.measurement_discarded()
            self._update_action_states()
            return
        self.live_controller.measurement_completed(result)
        self.last_measured_frame = frame
        self.last_result = result
        self.last_measurement_recipe = recipe_snapshot
        self.last_overlay = overlay
        self.image_panel.set_processed_image(overlay)
        self.image_panel.set_result_context(frame.frame_id, frame.timestamp)
        self.summary.set_result(result)
        self._record_measurement_rate()
        state = "有效" if result.valid else "无效"
        self.measurement_status.setText(f"状态：{state} · 帧 {frame.frame_id}")
        self._update_action_states()

    def _measurement_worker_failed(self, traceback_text: str) -> None:
        self.live_controller.measurement_failed()
        message = traceback_text.splitlines()[-1] if traceback_text else "测量线程异常"
        self.measurement_status.setText("状态：测量线程异常")
        if not self.live_controller.live:
            self._error(message)
        self._update_action_states()

    def _record_measurement_rate(self) -> None:
        now = time.monotonic()
        self._measurement_completed_times.append(now)
        self._measurement_completed_times = [
            stamp for stamp in self._measurement_completed_times if now - stamp <= 3.0
        ]
        if len(self._measurement_completed_times) >= 2:
            duration = self._measurement_completed_times[-1] - self._measurement_completed_times[0]
            if duration > 0:
                self._actual_measurement_fps = (
                    len(self._measurement_completed_times) - 1
                ) / duration
        self._update_fps_status()

    def _toggle_live(self, enabled: bool) -> None:
        if enabled:
            if not self._camera_connected:
                blocker = QSignalBlocker(self.live_action)
                self.live_action.setChecked(False)
                del blocker
                self._error("请先连接 MVS 相机")
                return
            self.live_controller.start()
        else:
            self.live_controller.stop()

    def _live_state_changed(self, enabled: bool) -> None:
        self.live_action.setText("停止实时" if enabled else "实时测量")
        self.measurement_status.setText("状态：实时测量中" if enabled else "状态：等待")

    def _select_roi(self, name: str) -> None:
        self.roi_inspector.set_current_roi(name)

    def _select_roi_from_inspector(self, name: str) -> None:
        self.image_panel.select_roi(name)

    def _roi_from_scene(self, name: str, roi: RotatedRoi) -> None:
        band = getattr(self.recipe, name)
        updates = {name: replace(band, roi=roi)}
        if name == "platform_right":
            updates["platform_right_confirmed"] = True
        self.recipe = replace(self.recipe, **updates)
        self._recipe_revision += 1
        self.roi_inspector.set_recipe(self.recipe)
        self.roi_inspector.set_current_roi(name)

    def _roi_drag_started(self, name: str) -> None:
        self._select_roi(name)
        self.live_controller.begin_roi_drag()
        self.measurement_status.setText("状态：ROI 调整中，测量已暂停")

    def _roi_drag_finished(self, name: str, roi: RotatedRoi) -> None:
        self._roi_from_scene(name, roi)
        self.live_controller.end_roi_drag()
        self.measurement_status.setText("状态：ROI 已更新，立即重测")

    def _band_from_inspector(
        self, name: str, band: BandConfig | BrightBandConfig
    ) -> None:
        updates = {name: band}
        if name == "platform_right":
            updates["platform_right_confirmed"] = True
        self.recipe = replace(self.recipe, **updates)
        self._recipe_revision += 1
        self.image_panel.set_recipe(self.recipe)
        self.live_controller.reset_stability()
        if self.current_frame is not None:
            self.live_controller.request_now(force=True)

    def _toggle_roi_visibility(self, visible: bool) -> None:
        self.image_panel.set_roi_visible(visible)
        self.app_settings.setValue("view/show_roi", visible)

    def _toggle_auxiliary_visibility(self, visible: bool) -> None:
        self.app_settings.setValue("view/show_auxiliary", visible)
        if self.last_result is not None and self.last_measured_frame is not None:
            recipe = self.last_measurement_recipe or self.recipe
            self.last_overlay = draw_measurement_overlay(
                self.last_measured_frame.image,
                recipe,
                self.last_result,
                show_rois=False,
                show_auxiliary=visible,
            )
            self.image_panel.set_processed_image(self.last_overlay)

    def show_settings(self) -> None:
        dialog = SettingsDialog(
            SettingsValues(
                self.exposure_us,
                self.gain_db,
                self.recipe_path,
                "none",
                self.calibration_path,
                self.recipe.height_difference_mm,
                self.output_path,
            ),
            self._calibration_status_text(),
            "已连接" if self._camera_connected else "未连接",
            self,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        values = dialog.values()
        try:
            new_recipe = self.recipe
            if values.recipe_action == "load":
                new_recipe = MeasurementRecipe.load(values.recipe_path)
            new_recipe = replace(
                new_recipe, height_difference_mm=values.height_difference_mm
            )
            new_calibration = self.calibration
            if values.calibration_path:
                new_calibration = CalibrationData.load(values.calibration_path)
            if values.recipe_action == "save":
                new_recipe.save(values.recipe_path)
        except Exception as exc:
            self._error(f"设置应用失败: {exc}")
            return

        camera_changed = (
            values.exposure_us != self.exposure_us or values.gain_db != self.gain_db
        )
        was_connected = self.acquisition_thread is not None
        was_live = self.live_controller.live
        old_exposure, old_gain = self.exposure_us, self.gain_db
        if camera_changed and was_connected:
            self.disconnect_camera()
            self._camera_rollback = (old_exposure, old_gain, was_live)
        self.exposure_us = values.exposure_us
        self.gain_db = values.gain_db
        self.recipe = new_recipe
        self.calibration = new_calibration
        self.recipe_path = values.recipe_path
        self.calibration_path = values.calibration_path
        self.output_path = values.output_path
        self._recipe_changed()
        self._persist_settings()
        if camera_changed and was_connected:
            self._resume_live_after_connect = was_live
            self._start_camera()
        self.statusBar().showMessage("设置已应用")

    def _recipe_changed(self) -> None:
        self._recipe_revision += 1
        self.image_panel.set_recipe(self.recipe)
        self.roi_inspector.set_recipe(self.recipe)
        self.live_controller.configure(self.recipe.quality)
        self.last_result = None
        self.last_measured_frame = None
        self.last_overlay = None
        if self.current_frame is not None:
            self.image_panel.set_images(self.current_frame.image)
        self._update_action_states()

    def _calibration_status_text(self) -> str:
        if self.calibration is None:
            return "未标定"
        pose = self.calibration.platform_pose
        if pose is None:
            return f"内参 RMS {self.calibration.rms_reprojection_error:.3f} px；缺少平台姿态"
        return (
            f"内参 RMS {self.calibration.rms_reprojection_error:.3f} px；"
            f"平台姿态 RMS {pose.reprojection_error_px:.3f} px"
        )

    def save_current_result(self) -> None:
        if (
            self.last_measured_frame is None
            or self.last_result is None
            or self.last_measurement_recipe is None
        ):
            self._error("没有可保存的测量结果")
            return
        overlay = draw_measurement_overlay(
            self.last_measured_frame.image,
            self.last_measurement_recipe,
            self.last_result,
            show_rois=self.show_roi_action.isChecked(),
            show_auxiliary=self.show_aux_action.isChecked(),
        )
        metadata = dict(self.last_measured_frame.metadata)
        metadata.update(
            {
                "stability": self.live_controller.stability.to_dict(),
                "camera_fps": self._actual_camera_fps,
                "measurement_fps": self._actual_measurement_fps,
                "exposure_us": self.exposure_us,
                "gain_db": self.gain_db,
            }
        )
        try:
            ResultWriter(self.output_path).write(
                self.last_measured_frame.image,
                overlay,
                self.last_result,
                frame_id=self.last_measured_frame.frame_id,
                source_name=str(
                    self.last_measured_frame.metadata.get(
                        "source_path",
                        self.last_measured_frame.metadata.get("source_type", "unknown"),
                    )
                ),
                recipe_name=self.last_measurement_recipe.name,
                timestamp=self.last_measured_frame.timestamp,
                metadata=metadata,
            )
        except ResultStorageError as exc:
            self._error(str(exc))
            return
        timestamp = time.strftime("%H:%M:%S")
        self.save_status.setText(f"最近保存：{timestamp}")
        self.statusBar().showMessage(f"结果已保存到 {self.output_path}")

    def _clear_measurement_state(self) -> None:
        self.current_frame = None
        self.last_measured_frame = None
        self.last_result = None
        self.last_measurement_recipe = None
        self.last_overlay = None
        self._measurement_completed_times.clear()
        self._actual_measurement_fps = 0.0
        self.live_controller.reset_stability()

    def _update_action_states(self) -> None:
        has_frame = self.current_frame is not None
        self.measure_action.setEnabled(has_frame)
        self.save_action.setEnabled(
            self.last_result is not None and not self.live_controller.busy
        )
        self.live_action.setEnabled(self._camera_connected)

    def _update_fps_status(self) -> None:
        camera = "--" if self._actual_camera_fps <= 0 else f"{self._actual_camera_fps:.1f}"
        measurement = (
            "--" if self._actual_measurement_fps <= 0 else f"{self._actual_measurement_fps:.1f}"
        )
        self.fps_status.setText(f"采集：{camera} fps　测量：{measurement} Hz")

    def _persist_settings(self) -> None:
        self.app_settings.setValue("paths/recipe", self.recipe_path)
        self.app_settings.setValue("paths/calibration", self.calibration_path)
        self.app_settings.setValue("paths/output", self.output_path)
        self.app_settings.setValue("camera/exposure_us", self.exposure_us)
        self.app_settings.setValue("camera/gain_db", self.gain_db)
        self.app_settings.setValue("view/show_roi", self.show_roi_action.isChecked())
        self.app_settings.setValue(
            "view/show_auxiliary", self.show_aux_action.isChecked()
        )
        self.app_settings.sync()

    def _error(self, message: str) -> None:
        self.statusBar().showMessage(message)
        QMessageBox.critical(self, "错误", message)

    def closeEvent(self, event) -> None:  # noqa: ANN001
        self.live_controller.stop()
        self.disconnect_camera()
        self.thread_pool.waitForDone(3000)
        self._persist_settings()
        super().closeEvent(event)
