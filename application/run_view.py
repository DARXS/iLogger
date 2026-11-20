"""RunView — fachada de transição (strangler fig) com a API da `RunData` da v6.

Os painéis legados e exportadores continuam chamando ``apply_filters_and_recalculate`` /
``get_channel`` etc., mas por baixo tudo é o novo núcleo imutável: `Run` + `Pipeline` + cache.
O estado derivado é um único `ProcessedRun` trocado atomicamente (seguro entre threads).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from ..domain import channels as ch
from ..domain import spectral
from ..domain.analyzers import cvt as cvt_mod
from ..domain.analyzers import phases as phases_mod
from ..domain.models import Run, RunMeta, VehicleProfile
from ..domain.pipeline import FilterConfig, ProcessedRun
from ..domain.stats import extended_stats
from .processing import ProcessingService

_EMPTY = np.empty(0)


class RunView:
    def __init__(self, run: Run, service: ProcessingService, profile: VehicleProfile):
        self.run = run
        self._service = service
        self._profile = profile
        self._processed: ProcessedRun | None = None

    # ── identidade / dados brutos ─────────────────────────────────────────────
    @property
    def file_path(self) -> str: return self.run.path
    @property
    def file_name(self) -> str: return self.run.name
    @property
    def meta(self) -> RunMeta: return self.run.meta
    @property
    def time_s(self) -> np.ndarray: return self.run.time_s
    @property
    def rpm_raw(self) -> np.ndarray: return self.run.rpm_raw
    @property
    def velocity_raw_kmh(self) -> np.ndarray: return self.run.vel_raw_kmh

    # ── processamento ─────────────────────────────────────────────────────────
    def config_for(self, fs: Mapping[str, Any] | FilterConfig | None) -> FilterConfig:
        if isinstance(fs, FilterConfig):
            return fs
        return FilterConfig.from_legacy(fs, self.run.sample_rate_hz)

    def processed_for(self, fs: Mapping[str, Any] | FilterConfig | None) -> ProcessedRun:
        """Pura (não muta a view): é o que análises em background devem usar."""
        return self._service.process(self.run, self.config_for(fs))

    def apply_filters_and_recalculate(self, fs: Mapping[str, Any] | FilterConfig | None) -> None:
        if self.run.n_samples == 0:
            return
        self._processed = self.processed_for(fs)

    @property
    def state_key(self) -> tuple[str, str] | None:
        return self._processed.key if self._processed else None

    # ── canais derivados (vazios até o primeiro apply) ────────────────────────
    def _arr(self, name: str) -> np.ndarray:
        p = self._processed
        return getattr(p, name) if p else _EMPTY

    @property
    def rpm_filtered(self) -> np.ndarray: return self._arr("rpm")
    @property
    def velocity_filtered_ms(self) -> np.ndarray: return self._arr("vel_ms")
    @property
    def velocity_filtered_kmh(self) -> np.ndarray: return self._arr("vel_kmh")
    @property
    def acceleration_filtered_ms2(self) -> np.ndarray: return self._arr("acel")
    @property
    def distance_m(self) -> np.ndarray: return self._arr("dist")

    @property
    def stats(self) -> dict:
        return self._processed.stats.to_display_dict() if self._processed else {}

    def get_channel(self, key: str) -> np.ndarray:
        c = ch.DEFAULT_CHANNELS.find(key)
        if c is None:
            return _EMPTY
        return {ch.TIME: self.time_s, ch.RPM: self.rpm_filtered, ch.VEL: self.velocity_filtered_kmh,
                ch.ACEL: self.acceleration_filtered_ms2, ch.DIST: self.distance_m,
                ch.RPM_RAW: self.rpm_raw, ch.VEL_RAW: self.velocity_raw_kmh}[c.id]

    get_data_for_custom_plot = get_channel  # alias v5

    def as_dataframe(self) -> pd.DataFrame:
        L = ch.DEFAULT_CHANNELS
        return pd.DataFrame({
            L.get(ch.TIME).label: self.time_s, L.get(ch.RPM_RAW).label: self.rpm_raw,
            L.get(ch.VEL_RAW).label: self.velocity_raw_kmh, L.get(ch.RPM).label: self.rpm_filtered,
            L.get(ch.VEL).label: self.velocity_filtered_kmh, L.get(ch.ACEL).label: self.acceleration_filtered_ms2,
            L.get(ch.DIST).label: self.distance_m,
        })

    # ── análises ──────────────────────────────────────────────────────────────
    def compute_histogram_data(self, key: str, bins: int = 50):
        return spectral.histogram(self.get_channel(key), bins)

    def compute_fft(self, key: str):
        return spectral.fft(self.get_channel(key), self.time_s)

    def compute_extended_stats(self, key: str) -> dict:
        return extended_stats(self.get_channel(key), key)

    def detect_phases(self) -> pd.DataFrame:
        r = self._profile.rules
        return phases_mod.detect_phases(self.acceleration_filtered_ms2, self.time_s, self.velocity_filtered_kmh,
                                        self.distance_m, r.phase_accel_thr, r.phase_brake_thr)

    def phase_summary(self) -> dict:
        return phases_mod.phase_summary(self.detect_phases(), self.run.duration_s)

    def estimate_gear_ratios(self, n_gears: int = 5, min_vel: float = 5.0) -> dict:
        return cvt_mod.estimate_gear_ratios(self.velocity_filtered_kmh, self.rpm_filtered, n_gears, min_vel)

    def analyze_cvt(self):
        return cvt_mod.analyze_cvt(self.velocity_filtered_kmh, self.rpm_filtered, self.acceleration_filtered_ms2,
                                   self._profile.rules.cvt_min_speed_kmh)
