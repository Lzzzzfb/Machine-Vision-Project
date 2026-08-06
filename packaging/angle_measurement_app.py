from __future__ import annotations

import os
import sys
from pathlib import Path


def _configure_frozen_runtime() -> None:
    if not getattr(sys, "frozen", False):
        return

    executable_dir = Path(sys.executable).resolve().parent
    bundle_dir = Path(getattr(sys, "_MEIPASS", executable_dir))
    mvs_python_dir = bundle_dir / "mvs_sdk"

    # Relative recipe/output paths must resolve beside the delivered executable,
    # regardless of whether it was launched from Explorer or a shortcut.
    os.chdir(executable_dir)
    os.environ.setdefault("HIKROBOT_MVS_PYTHON_PATH", str(mvs_python_dir))
    os.environ["PATH"] = f"{executable_dir}{os.pathsep}{os.environ.get('PATH', '')}"
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(str(executable_dir))


def main() -> int:
    _configure_frozen_runtime()
    if getattr(sys, "frozen", False):
        from PySide6.QtCore import QSettings

        settings = QSettings("Lzzzzfb", "HikrobotAngleMeasurement")
        if settings.value("paths/recipe") is None:
            settings.setValue("paths/recipe", "configs/backlight_recipe.json")
    from angle_measurement.ui.launcher import main as launch_gui

    return launch_gui()


if __name__ == "__main__":
    raise SystemExit(main())
