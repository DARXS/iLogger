"""Session: fonte única de verdade do estado (sem UI).

A camada web/CLI assina eventos; exports leem daqui.
"""

from __future__ import annotations

from collections.abc import Callable

from ..domain.models import VehicleProfile
from ..domain.pipeline import FilterConfig
from .processing import ProcessingService
from .run_view import RunView


class Session:
    def __init__(self, profile: VehicleProfile | None = None):
        self.profile = profile or VehicleProfile()
        self.processing = ProcessingService()
        self.runs: list[RunView] = []
        self.filter: FilterConfig = FilterConfig()
        self.setup_info: dict[str, str] = {}
        self.observations: str = ""
        self._subs: list[Callable[[str], None]] = []

    def subscribe(self, cb: Callable[[str], None]) -> None:
        self._subs.append(cb)

    def _emit(self, event: str) -> None:
        for cb in list(self._subs):
            cb(event)

    def set_runs(self, runs: list[RunView]) -> None:
        self.runs = list(runs)
        self._emit("runs")

    def clear(self) -> None:
        self.runs = []
        self.processing.cache.clear()
        self._emit("runs")

    def set_filter(self, cfg: FilterConfig) -> None:
        cfg.validate(self.profile.sensor.sample_rate_hz)
        self.filter = cfg
        self._emit("filter")

    def set_profile(self, profile: VehicleProfile) -> None:
        self.profile = profile
        self.processing.cache.clear()
        self._emit("profile")
