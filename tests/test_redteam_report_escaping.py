from __future__ import annotations

from datetime import datetime
from pathlib import Path

from core.scanner import LockHolder, LockReason, report_markdown


def test_report_neutralizes_table_and_discord_injection() -> None:
    injected = "N:\\safe` | forged |\n@everyone"
    holder = LockHolder(
        pid=4242,
        name="@everyone.exe",
        started=datetime.fromtimestamp(100),
        cmdline="worker.exe",
        reasons=(LockReason("cmdline", injected),),
    )

    report = report_markdown(Path(injected), [holder])

    assert "@everyone" not in report
    assert "| forged |" not in report
    assert "\n@" not in report
    assert "&#124;" in report
    assert "@\u200beveryone" in report
    assert "N:\\safe'" in report
