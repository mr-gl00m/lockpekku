from __future__ import annotations

from pathlib import Path

import core.scanner as scanner


def test_probe_move_never_renames_the_selected_tree(
    monkeypatch, tmp_path: Path
) -> None:
    root = tmp_path / "selected"
    root.mkdir()

    def fail_rename(_source: Path, _destination: Path) -> None:
        raise AssertionError("probe_move changed the directory namespace")

    monkeypatch.setattr(scanner.os, "rename", fail_rename)

    movable, message = scanner.probe_move(root)

    assert movable, message
    assert root.is_dir()
