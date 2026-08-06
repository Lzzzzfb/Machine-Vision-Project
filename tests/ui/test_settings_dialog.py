import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDoubleSpinBox

from angle_measurement.ui.settings_dialog import SettingsDialog, SettingsValues
from angle_measurement.ui.widgets import WheelSafeDoubleSpinBox


def test_settings_dialog_uses_only_wheel_safe_numeric_inputs(tmp_path):
    app = QApplication.instance() or QApplication([])
    dialog = SettingsDialog(
        SettingsValues(5000, 0, "configs/example_recipe.json", "none", "", None, str(tmp_path)),
        "未标定",
        "未连接",
    )
    numeric_inputs = dialog.findChildren(QDoubleSpinBox)
    assert len(numeric_inputs) == 3
    assert all(isinstance(control, WheelSafeDoubleSpinBox) for control in numeric_inputs)
    values = dialog.values()
    assert values.exposure_us == 5000
    assert values.height_difference_mm is None
    dialog.close()
    app.processEvents()
