"""Ponte Qt ↔ Session: expõe a API de sinais que os painéis esperam."""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal

from ..application.run_view import RunView
from ..application.session import Session


class AppState(QObject):
    data_loaded = pyqtSignal()
    status_message = pyqtSignal(str, int)

    def __init__(self, session: Session | None = None):
        super().__init__()
        self.session = session or Session()

    @property
    def runs(self) -> list[RunView]:
        return self.session.runs

    def load(self, runs: list[RunView]) -> None:
        self.session.set_runs(runs)
        self.data_loaded.emit()

    def clear(self) -> None:
        self.session.clear()
        self.data_loaded.emit()
