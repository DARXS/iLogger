"""Execução de tarefas pesadas fora da thread da UI (QThreadPool), com progresso, cancelamento e erro."""

from __future__ import annotations

import logging
import traceback
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal

from ..application.ports import Cancelled, CancelToken

log = logging.getLogger(__name__)


class _Signals(QObject):
    progress = pyqtSignal(int, int)
    result = pyqtSignal(object)
    error = pyqtSignal(str, str)       # mensagem curta, traceback
    cancelled = pyqtSignal()
    finished = pyqtSignal()


class Worker(QRunnable):
    """Executa ``fn(progress, cancel)`` numa thread do pool. Slots conectados rodam na thread da UI."""

    def __init__(self, fn: Callable[[Callable[[int, int], None], CancelToken], Any]):
        super().__init__()
        self.fn = fn
        self.cancel_token = CancelToken()
        self.signals = _Signals()
        self.setAutoDelete(False)  # o TaskManager guarda a referência até terminar

    def run(self) -> None:
        try:
            res = self.fn(self.signals.progress.emit, self.cancel_token)
            self.signals.result.emit(res)
        except Cancelled:
            self.signals.cancelled.emit()
        except Exception as exc:
            log.exception("tarefa em background falhou")
            self.signals.error.emit(f"{type(exc).__name__}: {exc}", traceback.format_exc())
        finally:
            self.signals.finished.emit()


class TaskManager(QObject):
    """Mantém referências vivas e expõe `submit`."""

    def __init__(self, pool: QThreadPool | None = None):
        super().__init__()
        self._pool = pool or QThreadPool.globalInstance()
        self._alive: set[Worker] = set()

    def submit(self, fn, on_result=None, on_error=None, on_progress=None, on_finished=None) -> Worker:
        w = Worker(fn)
        self._alive.add(w)
        if on_result:
            w.signals.result.connect(on_result)
        if on_error:
            w.signals.error.connect(on_error)
        if on_progress:
            w.signals.progress.connect(on_progress)

        def done() -> None:
            self._alive.discard(w)
            if on_finished:
                on_finished()
        w.signals.finished.connect(done)
        self._pool.start(w)
        return w

    def wait_all(self, timeout_ms: int = 10000) -> bool:
        return self._pool.waitForDone(timeout_ms)
