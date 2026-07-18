# Invariant: probe result reflects movability when no handle blocks the folder.
# Violation: a stale fixed-name probe folder causes a false blocked result.
# Predicted failure: probe_move reports the clean folder as immovable.
from __future__ import annotations

from pathlib import Path

from core.scanner import probe_move


def test_repro_probe_avoids_existing_probe_name(tmp_path: Path) -> None:
    root = tmp_path / "movable"
    root.mkdir()
    collision = root.with_name(root.name + ".pekku_probe")
    collision.mkdir()

    movable, message = probe_move(root)

    assert movable, message
    assert root.is_dir()
    assert collision.is_dir()
