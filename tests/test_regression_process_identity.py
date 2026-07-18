# Invariant: a kill target remains the same process observed by the scan.
# Violation: PID reuse lets a replacement process receive terminate.
# Predicted failure: the fake replacement process is terminated.
from __future__ import annotations

from datetime import datetime

import core.scanner as scanner


def test_repro_stale_process_identity_is_rejected(monkeypatch) -> None:
    holder = scanner.LockHolder(
        pid=4242,
        name="original.exe",
        started=datetime.fromtimestamp(100),
        cmdline="original.exe",
        reasons=(scanner.LockReason("cwd", "N:\\target"),),
    )

    class FakeProcess:
        pid = 4242
        terminated = False

        def name(self) -> str:
            return "replacement.exe"

        def create_time(self) -> float:
            return 200.0

        def terminate(self) -> None:
            self.terminated = True

    replacement = FakeProcess()
    monkeypatch.setattr(scanner.psutil, "Process", lambda _pid: replacement)
    monkeypatch.setattr(
        scanner.psutil,
        "wait_procs",
        lambda waiting, timeout: (list(waiting), []),
    )

    results = scanner.kill_processes([holder])

    assert not replacement.terminated, "a reused PID received terminate"
    assert results[0].outcome == "changed"
