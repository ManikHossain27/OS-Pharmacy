"""Structured logging.

Console + rotating file handler under ``logs/``.  Never logs secrets - callers
must pass already-safe strings (see ``utils.helpers.mask_secret``).
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from config import settings

_FMT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"
_configured = False


def _configure_root() -> None:
    global _configured
    if _configured:
        return
    settings.ensure_dirs()

    root = logging.getLogger("pms")
    root.setLevel(logging.DEBUG)

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(_FMT, _DATEFMT))
    root.addHandler(console)

    file_handler = RotatingFileHandler(
        settings.logs_dir / "pms-automation.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(_FMT, _DATEFMT))
    root.addHandler(file_handler)

    root.propagate = False
    _configured = True


def get_logger(name: str) -> logging.Logger:
    _configure_root()
    return logging.getLogger(f"pms.{name}")
