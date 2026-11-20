"""Canais virtuais: definição persistível + avaliação segura com cache por (dados, filtro, expressão)."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from ..domain import expressions
from ..domain.errors import ExpressionError
from .run_view import RunView

log = logging.getLogger(__name__)


class VirtualChannel:
    def __init__(self, name: str = "", expression: str = "", unit: str = "", color: str = "#00e5ff"):
        self.name, self.expression, self.unit, self.color = name, expression, unit, color
        self.enabled = True
        self._cache: dict[tuple, np.ndarray] = {}

    def validate(self) -> None:
        expressions.parse(self.expression)

    def evaluate(self, run: RunView, fs: dict) -> np.ndarray | None:
        run.apply_filters_and_recalculate(fs)
        state = run.state_key
        key = (state, self.expression)
        if key in self._cache:
            return self._cache[key]
        variables = {
            "tempo": run.time_s, "vel": run.velocity_filtered_kmh, "rpm": run.rpm_filtered,
            "acel": run.acceleration_filtered_ms2, "dist": run.distance_m,
            "rpm_raw": run.rpm_raw, "vel_raw": run.velocity_raw_kmh,
        }
        try:
            result = expressions.evaluate(self.expression, variables)
        except ExpressionError as exc:
            log.warning("canal virtual %r: %s", self.name, exc)
            return None
        if len(self._cache) > 32:
            self._cache.clear()
        self._cache[key] = result
        return result

    def invalidate(self) -> None:
        self._cache.clear()

    def to_dict(self) -> dict[str, Any]:
        return dict(name=self.name, expression=self.expression, unit=self.unit, color=self.color,
                    enabled=self.enabled)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> VirtualChannel:
        vc = cls(str(d.get("name", "")), str(d.get("expression", "")), str(d.get("unit", "")),
                 str(d.get("color", "#00e5ff")))
        vc.enabled = bool(d.get("enabled", True))
        return vc
