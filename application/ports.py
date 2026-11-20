"""Portas (Protocols): o que a aplicação precisa do mundo externo. Sem Qt, sem I/O concreto."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Protocol

from ..domain.models import Run
from .report_model import ReportModel


class RunReader(Protocol):
    def read(self, path: str) -> Run: ...


class Exporter(Protocol):
    """Renderizador de relatório: lê um `ReportModel`, escreve um arquivo."""

    name: str
    extension: str

    def export(self, model: ReportModel, path: str) -> None: ...


class CancelToken:
    """Cancelamento cooperativo entre UI e tarefas em background."""

    def __init__(self) -> None:
        self._ev = threading.Event()

    def cancel(self) -> None:
        self._ev.set()

    @property
    def cancelled(self) -> bool:
        return self._ev.is_set()


class Cancelled(Exception):
    pass


ProgressCallback = Callable[[int, int], None]
