from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from core.config import Config
from core.scanner import LockHolder, LockReason
import ui.main_window as window_module


def test_editing_root_clears_prior_kill_targets(monkeypatch, tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    original_root = tmp_path / "original"
    replacement_root = tmp_path / "replacement"
    original_root.mkdir()
    replacement_root.mkdir()
    holder = LockHolder(
        pid=4242,
        name="editor.exe",
        started=datetime.fromtimestamp(100),
        cmdline="editor.exe",
        reasons=(LockReason("cwd", str(original_root)),),
    )
    monkeypatch.setattr(window_module, "scan", lambda _root: [holder])

    window = window_module.MainWindow(Config(default_root=str(original_root)))
    window._live_timer.stop()
    assert window._holders == [holder]
    assert window._table.rowCount() == 1

    window._root_edit.setText(str(replacement_root))

    assert window._holders == []
    assert window._table.rowCount() == 0
    window.close()
    assert app is not None
