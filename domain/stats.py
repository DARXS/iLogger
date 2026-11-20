"""Estatísticas por run e por canal (vetorizadas)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats as sp_stats

# Rótulos históricos usados nas tabelas de exportação (apenas apresentação).
DISPLAY_LABELS = {
    "vel_max": "Vel. Máx (Km/h)", "vel_mean": "Vel. Média (Km/h)",
    "vel_median": "Vel. Mediana (Km/h)", "vel_std": "Vel. σ (Km/h)",
    "rpm_max": "RPM Máx", "rpm_mean": "RPM Médio", "rpm_median": "RPM Mediana",
    "acel_max": "Acel. Máx (m/s²)", "acel_min": "Acel. Mín (m/s²)",
    "dist_total": "Distância Total (m)", "duration": "Duração (s)",
}


@dataclass(frozen=True)
class RunStats:
    """Métricas de uma run, indexadas por id estável (não por texto de UI)."""

    name: str
    vel_max: float = 0.0
    vel_mean: float = 0.0
    vel_median: float = 0.0
    vel_std: float = 0.0
    rpm_max: float = 0.0
    rpm_mean: float = 0.0
    rpm_median: float = 0.0
    acel_max: float = 0.0
    acel_min: float = 0.0
    dist_total: float = 0.0
    duration: float = 0.0

    def metric(self, metric_id: str) -> float:
        if metric_id not in DISPLAY_LABELS:
            raise KeyError(metric_id)
        return float(getattr(self, metric_id))

    def to_display_dict(self) -> dict[str, float | str]:
        d: dict[str, float | str] = {"Arquivo": self.name}
        for mid, label in DISPLAY_LABELS.items():
            d[label] = self.metric(mid)
        return d


def _m(fn, arr: np.ndarray) -> float:
    return float(fn(arr)) if arr.size else 0.0


def compute_run_stats(name: str, time_s: np.ndarray, vel_kmh: np.ndarray, rpm: np.ndarray,
                      acel: np.ndarray, dist: np.ndarray) -> RunStats:
    return RunStats(
        name=name,
        vel_max=_m(np.max, vel_kmh), vel_mean=_m(np.mean, vel_kmh),
        vel_median=_m(np.median, vel_kmh), vel_std=_m(np.std, vel_kmh),
        rpm_max=_m(np.max, rpm), rpm_mean=_m(np.mean, rpm), rpm_median=_m(np.median, rpm),
        acel_max=_m(np.max, acel), acel_min=_m(np.min, acel),
        dist_total=float(dist[-1]) if dist.size else 0.0,
        duration=float(time_s[-1]) if time_s.size else 0.0,
    )


def extended_stats(data: np.ndarray, key: str = "") -> dict:
    """Percentis, assimetria, curtose, RMS e CV de um canal."""
    if data.size == 0:
        return {}
    p = np.percentile(data, [5, 10, 25, 50, 75, 90, 95])
    mean, std = float(data.mean()), float(data.std())
    return {
        "canal": key, "n": int(data.size),
        "min": float(data.min()), "max": float(data.max()),
        "amplitude": float(data.max() - data.min()),
        "mean": round(mean, 4), "std": round(std, 4),
        "cv_%": round(std / mean * 100.0, 2) if mean != 0.0 else 0.0,
        "rms": round(float(np.sqrt(np.mean(data ** 2))), 4),
        "skewness": round(float(sp_stats.skew(data)), 4),
        "kurtosis": round(float(sp_stats.kurtosis(data)), 4),
        "p5": float(p[0]), "p10": float(p[1]), "p25": float(p[2]), "p50": float(p[3]),
        "p75": float(p[4]), "p90": float(p[5]), "p95": float(p[6]),
        "iqr": round(float(p[4] - p[2]), 4),
    }
