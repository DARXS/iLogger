"""Logging em arquivo rotativo + hook de exceções não tratadas."""

from __future__ import annotations

import logging
import sys
import threading
from collections.abc import Callable
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .storage.workspace import default_dir


def setup_logging(level: int = logging.INFO, log_dir: Path | None = None) -> Path:
    log_dir = log_dir or default_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / "mangue_logger.log"
    root = logging.getLogger()
    root.setLevel(level)
    if not any(isinstance(h, RotatingFileHandler) and h.baseFilename == str(path) for h in root.handlers):
        fh = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
        root.addHandler(fh)
    return path


def install_excepthook(on_error: Callable[[str], None] | None = None) -> None:
    """Registra exceções não tratadas no log e (opcionalmente) avisa o usuário."""
    log = logging.getLogger("uncaught")

    def hook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        log.critical("exceção não tratada", exc_info=(exc_type, exc, tb))
        if on_error:
            on_error(f"{exc_type.__name__}: {exc}")

    sys.excepthook = hook
    threading.excepthook = lambda a: hook(a.exc_type, a.exc_value, a.exc_traceback)
