from __future__ import annotations

from PySide6.QtCore import QRectF, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QStyle,
    QStyleOptionGraphicsItem,
    QWidget,
)

from angle_measurement.models import RotatedRoi


class EditableRoiItem(QGraphicsObject):
    roi_changed = Signal(str, object)

    def __init__(self, name: str, roi: RotatedRoi, color: QColor) -> None:
        super().__init__()
        self.name = name
        self._length = roi.length
        self._width = roi.width
        self._color = color
        self.setPos(roi.center_x, roi.center_y)
        self.setRotation(roi.angle_deg)
        self.setFlags(
            QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setZValue(10)

    def boundingRect(self) -> QRectF:
        margin = 5.0
        return QRectF(
            -self._length / 2.0 - margin,
            -self._width / 2.0 - margin,
            self._length + 2 * margin,
            self._width + 2 * margin,
        )

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        del widget
        color = QColor(0, 255, 120) if option.state & QStyle.State_Selected else self._color
        pen = QPen(color, 2.0)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(QColor(color.red(), color.green(), color.blue(), 25))
        painter.drawRect(
            QRectF(-self._length / 2.0, -self._width / 2.0, self._length, self._width)
        )
        painter.drawLine(
            -self._length / 2.0,
            0.0,
            self._length / 2.0,
            0.0,
        )

    def set_roi(self, roi: RotatedRoi) -> None:
        self.prepareGeometryChange()
        self._length = roi.length
        self._width = roi.width
        self.setPos(roi.center_x, roi.center_y)
        self.setRotation(roi.angle_deg)
        self.update()

    def to_roi(self) -> RotatedRoi:
        return RotatedRoi(
            center_x=self.pos().x(),
            center_y=self.pos().y(),
            length=self._length,
            width=self._width,
            angle_deg=self.rotation(),
        )

    def mouseReleaseEvent(self, event) -> None:  # noqa: ANN001
        super().mouseReleaseEvent(event)
        self.roi_changed.emit(self.name, self.to_roi())
