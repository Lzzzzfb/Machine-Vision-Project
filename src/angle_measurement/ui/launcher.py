from __future__ import annotations

import sys
from pathlib import Path


def configure_application_font(app) -> None:  # noqa: ANN001
    from PySide6.QtGui import QFont, QFontDatabase

    candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(candidate))
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            app.setFont(QFont(families[0], 9))
            return


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication

        from .main_window import MainWindow
    except ImportError as exc:
        print("未安装 PySide6。请运行: python -m pip install -e \".[gui]\"")
        print(exc)
        return 2
    app = QApplication.instance() or QApplication(sys.argv)
    configure_application_font(app)
    window = MainWindow()
    window.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
