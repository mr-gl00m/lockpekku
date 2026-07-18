from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType
from typing import Type

from core.config import user_data_dir

_active_handler: RotatingFileHandler | None = None


def configure_logging(
    app_name: str,
    level: int = logging.INFO,
    *,
    logs_dir: Path | None = None,
) -> logging.Logger:
    target_dir = logs_dir if logs_dir is not None else user_data_dir(app_name) / "logs"
    target_dir.mkdir(parents=True, exist_ok=True)
    log_path: Path = target_dir / f"{app_name.lower()}.log"

    # the handler goes on the root logger: module loggers (core.*, ui.*)
    # propagate to root, not to the app-named logger, so attaching anywhere
    # else silently drops every record they emit; only the handler this module
    # added is replaced, foreign root handlers (test harnesses) stay untouched
    global _active_handler
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    if _active_handler is not None:
        root_logger.removeHandler(_active_handler)
        _active_handler.close()
        _active_handler = None

    handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    _active_handler = handler

    app_logger = logging.getLogger(app_name)

    def _excepthook(
        exc_type: Type[BaseException],
        exc_value: BaseException,
        exc_tb: TracebackType | None,
    ) -> None:
        app_logger.critical(
            "Uncaught exception", exc_info=(exc_type, exc_value, exc_tb)
        )

    sys.excepthook = _excepthook
    return app_logger
