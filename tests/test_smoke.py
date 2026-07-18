from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from core.io import atomic_write_json, atomic_write_text, read_json, read_text
from core.scanner import _norm, _strictly_under, kill_processes, probe_move, scan


def test_atomic_write_text_roundtrip(tmp_path: Path) -> None:
    target = tmp_path / "note.md"
    atomic_write_text(target, "# hello\n")
    assert read_text(target) == "# hello\n"


def test_atomic_write_json_roundtrip(tmp_path: Path) -> None:
    target = tmp_path / "data.json"
    payload = {"accent": "#e0af68", "count": 3}
    atomic_write_json(target, payload)
    assert read_json(target) == payload


def test_scan_detects_cwd_holder(tmp_path: Path) -> None:
    held = tmp_path / "held"
    held.mkdir()
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        cwd=str(held),
    )
    try:
        time.sleep(0.5)
        holders = scan(tmp_path)
        match = [h for h in holders if h.pid == proc.pid]
        assert match, f"spawned pid {proc.pid} not detected under {tmp_path}"
        assert "cwd" in match[0].reason_summary
    finally:
        proc.kill()
        proc.wait()


def test_scan_detects_cwd_at_root_itself(tmp_path: Path) -> None:
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        cwd=str(tmp_path),
    )
    try:
        time.sleep(0.5)
        holders = scan(tmp_path)
        assert any(h.pid == proc.pid for h in holders)
    finally:
        proc.kill()
        proc.wait()


def test_strictly_under_excludes_drive_root_itself() -> None:
    root_norm = _norm("N:\\")
    assert not _strictly_under("N:\\", root_norm)
    assert not _strictly_under("N:/", root_norm)
    assert _strictly_under("N:\\proj_x", root_norm)


def test_probe_move_clean_folder(tmp_path: Path) -> None:
    target = tmp_path / "movable"
    target.mkdir()
    movable, message = probe_move(target)
    assert movable, message
    assert target.exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows share-mode semantics")
def test_probe_move_detects_held_file(tmp_path: Path) -> None:
    target = tmp_path / "held"
    target.mkdir()
    handle = open(target / "open.txt", "w", encoding="utf-8")
    try:
        movable, message = probe_move(target)
        assert not movable, message
        assert target.exists()
    finally:
        handle.close()


def test_probe_move_refuses_drive_root() -> None:
    movable, message = probe_move(Path("N:\\"))
    assert not movable
    assert "drive root" in message


def test_kill_processes(tmp_path: Path) -> None:
    held = tmp_path / "held"
    held.mkdir()
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        cwd=str(held),
    )
    try:
        time.sleep(0.5)
        results = kill_processes([proc.pid])
        outcomes = {r.outcome for r in results if r.pid == proc.pid}
        assert outcomes & {"terminated", "killed"}
        assert proc.wait(timeout=5) is not None
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
