from __future__ import annotations

import logging
import sys
from pathlib import Path

import core.logging_setup as logging_setup


def test_default_logging_uses_local_application_data(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    previous_hook = sys.excepthook
    logging_setup.configure_logging("LockpekkuUserPath")

    try:
        handler = logging_setup._active_handler
        assert handler is not None
        expected = tmp_path / "LockpekkuUserPath" / "logs" / "lockpekkuuserpath.log"
        assert Path(handler.baseFilename) == expected
    finally:
        if logging_setup._active_handler is not None:
            logging.getLogger().removeHandler(logging_setup._active_handler)
            logging_setup._active_handler.close()
            logging_setup._active_handler = None
        sys.excepthook = previous_hook
