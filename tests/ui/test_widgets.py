import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication

from angle_measurement.ui.widgets import WheelSafeDoubleSpinBox, WheelSafeSpinBox


def _send_wheel(widget):
    event = QWheelEvent(
        QPointF(5, 5),
        QPointF(5, 5),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.NoButton,
        Qt.NoModifier,
        Qt.ScrollUpdate,
        False,
    )
    QApplication.sendEvent(widget, event)


def test_wheel_does_not_change_numeric_inputs():
    app = QApplication.instance() or QApplication([])
    for widget in (WheelSafeDoubleSpinBox(), WheelSafeSpinBox()):
        widget.setRange(0, 100)
        widget.setValue(50)
        widget.setFocus()
        _send_wheel(widget)
        assert widget.value() == 50
    app.processEvents()
