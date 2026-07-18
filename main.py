from __future__ import annotations

import ctypes
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from core.config import RESOURCES_DIR, Config
from core.logging_setup import configure_logging
from ui.main_window import MainWindow
from ui.theme import load_stylesheet


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    config = Config()
    logger = configure_logging(config.app_name)
    logger.info("Starting %s", config.app_name)

    if sys.platform == "win32":
        # without an explicit AppUserModelID Windows groups the window under
        # python.exe and shows the python icon in the taskbar
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("cid.lockpekku")

    app = QApplication(sys.argv)
    app.setApplicationName(config.app_name)
    app.setWindowIcon(QIcon(str(RESOURCES_DIR / "lockpekku.ico")))
    app.setStyleSheet(load_stylesheet(config.accent_hex))

    window = MainWindow(config)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
