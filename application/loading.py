"""Caso de uso: carregar várias runs em paralelo, com progresso e cancelamento."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from ..domain.models import VehicleProfile
from .ports import Cancelled, CancelToken, ProgressCallback, RunReader
from .processing import ProcessingService
from .run_view import RunView

log = logging.getLogger(__name__)


@dataclass
class LoadResult:
    runs: list[RunView] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def load_runs(paths: list[str], reader: RunReader, service: ProcessingService, profile: VehicleProfile,
              on_progress: ProgressCallback | None = None, cancel: CancelToken | None = None,
              max_workers: int | None = None) -> LoadResult:
    """Lê `paths` em paralelo preservando a ordem pedida (a 1ª run é a base de comparação)."""
    result = LoadResult()
    slots: list[RunView | None] = [None] * len(paths)
    done = 0
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(reader.read, p): i for i, p in enumerate(paths)}
        for fut in as_completed(futures):
            if cancel and cancel.cancelled:
                for f in futures:
                    f.cancel()
                raise Cancelled()
            i = futures[fut]
            try:
                slots[i] = RunView(fut.result(), service, profile)
            except Exception as exc:  # erro por arquivo não derruba o lote
                log.warning("falha ao ler %s: %s", paths[i], exc)
                result.errors.append(f"{paths[i]} — {exc}")
            done += 1
            if on_progress:
                on_progress(done, len(paths))
    result.runs = [s for s in slots if s is not None]
    return result
