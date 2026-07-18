from __future__ import annotations

from pathlib import Path

import core.scanner as scanner


def test_scan_redacts_secret_option_values(monkeypatch, tmp_path: Path) -> None:
    class FakeProcess:
        info = {
            "pid": 4242,
            "name": "worker.exe",
            "exe": None,
            "cmdline": [
                "worker.exe",
                "--api-key=alpha-secret",
                "--password",
                "bravo-secret",
                "--mode",
                "scan",
            ],
            "create_time": 100.0,
            "cwd": str(tmp_path),
        }

    monkeypatch.setattr(scanner.os, "getpid", lambda: 1)
    monkeypatch.setattr(
        scanner.psutil,
        "process_iter",
        lambda **_kwargs: [FakeProcess()],
    )

    holders = scanner.scan(tmp_path)

    assert len(holders) == 1
    command_line = holders[0].cmdline
    assert "alpha-secret" not in command_line
    assert "bravo-secret" not in command_line
    assert "--api-key=<redacted>" in command_line
    assert "--password <redacted>" in command_line
    assert "--mode scan" in command_line
