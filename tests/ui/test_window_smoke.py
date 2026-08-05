import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from angle_measurement.ui.main_window import MainWindow


def test_main_window_constructs_and_closes():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    assert "二维夹角测量" in window.windowTitle()
    assert window.recipe.name
    window.close()
    app.processEvents()
