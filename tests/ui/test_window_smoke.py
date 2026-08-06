import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QScrollArea
import numpy as np

from angle_measurement.ui.main_window import MainWindow


def test_main_window_constructs_and_closes():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    assert "二维夹角测量" in window.windowTitle()
    assert window.recipe.name
    assert window.roi_inspector.selector.count() == 3
    assert not window.findChildren(QScrollArea)
    window.close()
    app.processEvents()


def test_zoom_does_not_change_roi_image_coordinates():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.image_panel.set_images(np.full((480, 640), 100, dtype=np.uint8))
    window.image_panel.set_recipe(window.recipe)
    before = window.image_panel.roi("slit_center")
    window.image_panel.raw_view.scale(2.0, 2.0)
    window.image_panel.raw_view.centerOn(200, 150)
    after = window.image_panel.roi("slit_center")
    assert after == before
    window.close()
    app.processEvents()


def test_scene_roi_selection_switches_inspector_and_live_position_updates():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.image_panel.select_roi("platform_right")
    assert window.roi_inspector.current_name == "platform_right"
    roi = window.image_panel.roi("platform_right")
    moved = type(roi)(roi.center_x + 12.5, roi.center_y - 3.0, roi.length, roi.width, roi.angle_deg)
    window._roi_from_scene("platform_right", moved)
    assert window.roi_inspector.center_x.value() == moved.center_x
    assert window.roi_inspector.center_y.value() == moved.center_y
    window.close()
    app.processEvents()
