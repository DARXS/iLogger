"""Serviço de processamento: dono do cache. Um por sessão — nunca global."""

from __future__ import annotations

from ..domain.models import Run
from ..domain.pipeline import FilterConfig, Pipeline, ProcessedRun, ProcessingCache


class ProcessingService:
    def __init__(self, max_entries: int = 64):
        self.cache = ProcessingCache(max_entries)

    def process(self, run: Run, config: FilterConfig) -> ProcessedRun:
        key = (run.content_hash, config.digest())
        return self.cache.get_or_compute(key, lambda: Pipeline(config).apply(run))
