import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
import numpy as np

from angle_measurement.ui.main_window import MainWindow


def test_main_window_constructs_and_closes():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    assert "二维夹角测量" in window.windowTitle()
    assert window.recipe.name
    assert window.band_selector.count() == 3
    window.close()
    app.processEvents()


def test_zoom_does_not_change_roi_image_coordinates():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window._display(np.full((480, 640), 100, dtype=np.uint8))
    before = window._roi_items["slit_center"].to_roi()
    window.view.zoom_by(2.0)
    window.view.centerOn(200, 150)
    after = window._roi_items["slit_center"].to_roi()
    assert after == before
    window.close()
    app.processEvents()
