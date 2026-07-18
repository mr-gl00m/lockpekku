# Invariant: live refresh displays fresh state and preserves checks by identity.
# Violation: PID-only keys hide replacement state and can transfer a check.
# Predicted failure: the table keeps the original process path.
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from core.config import Config
from core.scanner import LockHolder, LockReason
import ui.main_window as window_module


def test_repro_live_refresh_uses_full_process_identity(
    monkeypatch, tmp_path: Path
) -> None:
    app = QApplication.instance() or QApplication([])
    root = tmp_path / "root"
    root.mkdir()
    original = LockHolder(
        77,
        "worker.exe",
        datetime.fromtimestamp(100),
        "worker.exe old",
        (LockReason("cwd", str(root / "old")),),
    )
    replacement = LockHolder(
        77,
        "worker.exe",
        datetime.fromtimestamp(200),
        "worker.exe new",
        (LockReason("cwd", str(root / "new")),),
    )
    scans = iter([[original], [replacement]])
    monkeypatch.setattr(window_module, "scan", lambda _root: next(scans))

    window = window_module.MainWindow(Config(default_root=str(root)))
    window._live_timer.stop()
    window._table.item(0, window_module.COL_KILL).setCheckState(Qt.CheckState.Checked)
    window._live_tick()

    assert window._table.item(0, window_module.COL_PATH).text() == str(root / "new")
    assert window._table.item(0, window_module.COL_KILL).checkState() == Qt.CheckState.Unchecked
    window.close()
    assert app is not None
