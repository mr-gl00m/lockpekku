from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from core.config import Config
import ui.main_window as window_module


def test_unc_root_is_rejected_before_filesystem_access(monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    filesystem_calls: list[str] = []

    class UncRoot:
        def __str__(self) -> str:
            return r"\\attacker.invalid\share"

        def exists(self) -> bool:
            filesystem_calls.append("exists")
            raise AssertionError("UNC root reached the filesystem")

    monkeypatch.setattr(window_module.MainWindow, "_root", lambda _self: UncRoot())
    monkeypatch.setattr(
        window_module,
        "scan",
        lambda _root: (_ for _ in ()).throw(AssertionError("UNC root reached scan")),
    )

    window = window_module.MainWindow(Config(default_root=r"\\attacker.invalid\share"))
    window._live_timer.stop()

    assert not filesystem_calls
    assert "network" in window.statusBar().currentMessage().casefold()
    window.close()
    assert app is not None
