# Invariant: reconfiguring logging closes the handler it previously added.
# Violation: replacing without closing leaves the prior log stream open.
# Predicted failure: the first handler still owns an open stream.
from __future__ import annotations

import logging
import sys
from pathlib import Path

import core.logging_setup as logging_setup


def test_repro_reconfigure_closes_previous_handler(tmp_path: Path) -> None:
    previous_hook = sys.excepthook
    logging_setup.configure_logging("LockpekkuRepro", logs_dir=tmp_path)
    first_handler = logging_setup._active_handler
    assert first_handler is not None
    logging_setup.configure_logging("LockpekkuRepro", logs_dir=tmp_path)

    try:
        assert first_handler.stream is None or first_handler.stream.closed
    finally:
        first_handler.close()
        if logging_setup._active_handler is not None:
            logging.getLogger().removeHandler(logging_setup._active_handler)
            logging_setup._active_handler.close()
            logging_setup._active_handler = None
        sys.excepthook = previous_hook


def test_module_logger_records_reach_the_file(tmp_path: Path) -> None:
    previous_hook = sys.excepthook
    logging_setup.configure_logging("LockpekkuPropagation", logs_dir=tmp_path)
    try:
        logging.getLogger("core.scanner").info("propagation-check")
        handler = logging_setup._active_handler
        assert handler is not None
        handler.flush()
        content = Path(handler.baseFilename).read_text(encoding="utf-8")
        assert "propagation-check" in content
    finally:
        if logging_setup._active_handler is not None:
            logging.getLogger().removeHandler(logging_setup._active_handler)
            logging_setup._active_handler.close()
            logging_setup._active_handler = None
        sys.excepthook = previous_hook
