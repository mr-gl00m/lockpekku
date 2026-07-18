# Invariant: relative roots scan the same tree as their absolute equivalents.
# Violation: lexical normalization leaves a dot root unmatched to absolute paths.
# Predicted failure: the child cwd holder is absent from the scan.
from __future__ import annotations

from pathlib import Path

import core.scanner as scanner


def test_repro_scan_resolves_relative_root(monkeypatch, tmp_path: Path) -> None:
    held = tmp_path / "held"
    held.mkdir()

    class FakeProcess:
        info = {
            "pid": 4242,
            "name": "worker.exe",
            "exe": None,
            "cmdline": [],
            "create_time": 100.0,
            "cwd": str(held),
        }

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner.os, "getpid", lambda: 1)
    monkeypatch.setattr(
        scanner.psutil,
        "process_iter",
        lambda **_kwargs: [FakeProcess()],
    )

    holders = scanner.scan(Path("."))

    assert [holder.pid for holder in holders] == [4242]
