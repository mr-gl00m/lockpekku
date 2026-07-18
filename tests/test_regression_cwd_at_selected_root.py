# Invariant: scan reports a process whose cwd blocks moving the selected folder.
# Violation: cwd equal to a non-drive root is excluded from results.
# Predicted failure: no holder is returned for the blocking process.
from __future__ import annotations

from pathlib import Path

import core.scanner as scanner


def test_repro_cwd_equal_to_selected_folder_is_reported(
    monkeypatch, tmp_path: Path
) -> None:
    root = tmp_path / "selected"
    root.mkdir()

    class FakeProcess:
        info = {
            "pid": 4242,
            "name": "worker.exe",
            "exe": None,
            "cmdline": [],
            "create_time": 100.0,
            "cwd": str(root),
        }

    monkeypatch.setattr(scanner.os, "getpid", lambda: 1)
    monkeypatch.setattr(
        scanner.psutil,
        "process_iter",
        lambda **_kwargs: [FakeProcess()],
    )

    holders = scanner.scan(root)

    assert [holder.pid for holder in holders] == [4242]
    assert holders[0].reason_summary == "cwd"
