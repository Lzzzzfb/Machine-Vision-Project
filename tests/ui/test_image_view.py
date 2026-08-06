import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from angle_measurement.recipe import default_recipe
from angle_measurement.ui.image_view import DualImagePanel


def test_dual_panel_keeps_raw_scene_clean_and_syncs_views():
    app = QApplication.instance() or QApplication([])
    panel = DualImagePanel()
    image = np.full((480, 640), 100, dtype=np.uint8)
    panel.set_images(image)
    panel.set_recipe(default_recipe(640, 480))
    assert len(panel.raw_scene.items()) == 1
    assert len(panel.result_scene.items()) == 4
    panel.raw_view.scale(1.5, 1.5)
    panel.raw_view._emit_view()
    assert panel.result_view.transform().m11() == pytest.approx(
        panel.raw_view.transform().m11()
    )
    panel.set_roi_visible(False)
    assert all(not item.isVisible() for item in panel._roi_items.values())
    panel.close()
    app.processEvents()


def test_selecting_roi_emits_current_name():
    app = QApplication.instance() or QApplication([])
    panel = DualImagePanel()
    panel.set_images(np.full((480, 640), 100, dtype=np.uint8))
    panel.set_recipe(default_recipe(640, 480))
    selected = []
    panel.roi_selected.connect(selected.append)
    panel.select_roi("platform_right")
    assert selected[-1] == "platform_right"
    panel.close()
    app.processEvents()


def test_view_titles_identify_raw_and_processed_frames():
    app = QApplication.instance() or QApplication([])
    panel = DualImagePanel()
    panel.set_raw_context("mvs-00000012")
    panel.set_result_context("mvs-00000010", "2026-08-06T12:30:45+08:00")
    assert "mvs-00000012" in panel.raw_group.title()
    assert "mvs-00000010" in panel.result_group.title()
    assert "12:30:45" in panel.result_group.title()
    panel.close()
    app.processEvents()
