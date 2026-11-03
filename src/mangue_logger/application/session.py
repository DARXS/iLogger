"""Session: fonte única de verdade do estado (sem Qt).

A UI assina eventos; exports/CLI leem daqui — nunca de widgets.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..domain.models import VehicleProfile
from .processing import ProcessingService
from .run_view import RunView

DEFAULT_FILTER: dict[str, Any] = {"type": "butterworth", "butter_order": 4, "butter_cutoff": 0.1}


class Session:
    def __init__(self, profile: VehicleProfile | None = None):
        self.profile = profile or VehicleProfile()
        self.processing = ProcessingService()
        self.runs: list[RunView] = []
        self.filter_settings: dict[str, Any] = dict(DEFAULT_FILTER)
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

    def set_filter(self, fs: dict[str, Any]) -> None:
        self.filter_settings = dict(fs)
        self._emit("filter")

    def set_profile(self, profile: VehicleProfile) -> None:
        self.profile = profile
        self._emit("profile")
