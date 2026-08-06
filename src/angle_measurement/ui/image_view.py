from __future__ import annotations

import cv2
import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import (
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from angle_measurement.recipe import MeasurementRecipe

from .roi_item import EditableRoiItem


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


class SyncedGraphicsView(QGraphicsView):
    view_changed = Signal(object, object)

    def __init__(self, scene: QGraphicsScene, parent=None) -> None:  # noqa: ANN001
        super().__init__(scene, parent)
        self._suppress_sync = False
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setBackgroundBrush(QColor(35, 38, 43))
        self.setFrameShape(QGraphicsView.NoFrame)

    def _emit_view(self) -> None:
        if self._suppress_sync:
            return
        center = self.mapToScene(self.viewport().rect().center())
        self.view_changed.emit(self.transform(), center)

    def wheelEvent(self, event) -> None:  # noqa: ANN001
        if self.scene() is None or self.scene().sceneRect().isEmpty():
            super().wheelEvent(event)
            return
        factor = 1.2 if event.angleDelta().y() > 0 else 1.0 / 1.2
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.scale(factor, factor)
        self._emit_view()
        event.accept()

    def scrollContentsBy(self, dx: int, dy: int) -> None:
        super().scrollContentsBy(dx, dy)
        self._emit_view()

    def apply_view_state(self, transform, center) -> None:  # noqa: ANN001
        self._suppress_sync = True
        self.setTransform(transform)
        self.centerOn(center)
        self._suppress_sync = False

    def fit_scene(self) -> None:
        if self.scene() is not None and not self.scene().sceneRect().isEmpty():
            self.fitInView(self.scene().sceneRect(), Qt.KeepAspectRatio)
            self._emit_view()

    def actual_pixels(self) -> None:
        self.resetTransform()
        self._emit_view()


class DualImagePanel(QWidget):
    roi_selected = Signal(str)
    roi_changed = Signal(str, object)
    roi_drag_started = Signal(str)
    roi_drag_finished = Signal(str, object)

    def __init__(self, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.raw_scene = QGraphicsScene(self)
        self.result_scene = QGraphicsScene(self)
        self.raw_view = SyncedGraphicsView(self.raw_scene)
        self.result_view = SyncedGraphicsView(self.result_scene)
        self.raw_pixmap = QGraphicsPixmapItem()
        self.result_pixmap = QGraphicsPixmapItem()
        self.raw_scene.addItem(self.raw_pixmap)
        self.result_scene.addItem(self.result_pixmap)
        self._roi_items: dict[str, EditableRoiItem] = {}
        self._syncing = False
        self._image_size: tuple[int, int] | None = None
        self.raw_view.view_changed.connect(
            lambda transform, center: self._sync_view(self.result_view, transform, center)
        )
        self.result_view.view_changed.connect(
            lambda transform, center: self._sync_view(self.raw_view, transform, center)
        )

        splitter = QSplitter(Qt.Horizontal)
        self.raw_group = self._view_group("原始采集图", self.raw_view)
        self.result_group = self._view_group("测量结果图", self.result_view)
        splitter.addWidget(self.raw_group)
        splitter.addWidget(self.result_group)
        splitter.setChildrenCollapsible(False)
        splitter.setSizes([700, 700])
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

    @staticmethod
    def _view_group(title: str, view: QGraphicsView) -> QGroupBox:
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(4, 8, 4, 4)
        layout.addWidget(view)
        return group

    def _sync_view(self, target: SyncedGraphicsView, transform, center) -> None:  # noqa: ANN001
        if self._syncing:
            return
        self._syncing = True
        target.apply_view_state(transform, center)
        self._syncing = False

    def set_images(self, raw: np.ndarray, processed: np.ndarray | None = None) -> None:
        processed = raw if processed is None else processed
        size = (int(raw.shape[1]), int(raw.shape[0]))
        first_or_resized = self._image_size != size
        self.raw_pixmap.setPixmap(QPixmap.fromImage(array_to_qimage(raw)))
        self.result_pixmap.setPixmap(QPixmap.fromImage(array_to_qimage(processed)))
        rect = self.raw_pixmap.boundingRect()
        self.raw_scene.setSceneRect(rect)
        self.result_scene.setSceneRect(rect)
        self._image_size = size
        if first_or_resized:
            self.raw_view.fit_scene()

    def set_processed_image(self, processed: np.ndarray) -> None:
        self.result_pixmap.setPixmap(QPixmap.fromImage(array_to_qimage(processed)))

    def set_raw_image(self, raw: np.ndarray) -> None:
        size = (int(raw.shape[1]), int(raw.shape[0]))
        if self._image_size != size or self.result_pixmap.pixmap().isNull():
            self.set_images(raw)
            return
        self.raw_pixmap.setPixmap(QPixmap.fromImage(array_to_qimage(raw)))

    def set_raw_context(self, frame_id: str) -> None:
        self.raw_group.setTitle(f"原始采集图 · 帧 {frame_id}")

    def set_result_context(self, frame_id: str, timestamp: str) -> None:
        clock = timestamp.split("T")[-1].split("+")[0].replace("Z", "")
        self.result_group.setTitle(f"测量结果图 · 帧 {frame_id} · {clock}")

    def set_recipe(self, recipe: MeasurementRecipe) -> None:
        definitions = (
            ("slit_center", recipe.slit_center, QColor(255, 150, 0)),
            ("platform_left", recipe.platform_left, QColor(0, 210, 255)),
            ("platform_right", recipe.platform_right, QColor(200, 80, 220)),
        )
        for name, band, color in definitions:
            item = self._roi_items.get(name)
            if item is None:
                item = EditableRoiItem(name, band.roi, color)
                item.roi_selected.connect(self.roi_selected)
                item.roi_moved.connect(self.roi_changed)
                item.roi_changed.connect(self.roi_changed)
                item.drag_started.connect(self.roi_drag_started)
                item.drag_finished.connect(self.roi_drag_finished)
                self.result_scene.addItem(item)
                self._roi_items[name] = item
            else:
                item.set_roi(band.roi)

    def select_roi(self, name: str) -> None:
        item = self._roi_items.get(name)
        if item is not None:
            item.setSelected(True)

    def set_roi_visible(self, visible: bool) -> None:
        for item in self._roi_items.values():
            item.setVisible(visible)

    def fit_views(self) -> None:
        self.raw_view.fit_scene()

    def actual_pixels(self) -> None:
        self.raw_view.actual_pixels()

    def roi(self, name: str):  # noqa: ANN201
        return self._roi_items[name].to_roi()
