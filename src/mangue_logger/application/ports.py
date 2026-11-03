"""Portas (Protocols): o que a aplicação precisa do mundo externo. Sem Qt, sem I/O concreto."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..domain.models import Run


class RunReader(Protocol):
    def read(self, path: str) -> Run: ...


@dataclass
class ReportContext:
    """Tudo que um exporter precisa — independente de UI."""

    runs: list[Any]                       # list[RunView]
    filter_settings: dict
    setup_info: dict = field(default_factory=dict)
    observations: str = ""
    figures: dict = field(default_factory=dict)   # nome -> bytes PNG (opcional)


class Exporter(Protocol):
    name: str
    extension: str

    def export(self, ctx: ReportContext, path: str) -> None: ...


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
