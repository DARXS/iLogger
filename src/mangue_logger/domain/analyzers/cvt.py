"""Análise de CVT, faixa de potência, marchas (legado) e anomalias.

Um Baja usa CVT: a relação RPM/velocidade varia continuamente. Por isso, além do
`estimate_gear_ratios` (herdado da v6, útil para câmbio fixo), há `analyze_cvt`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import signal


@dataclass(frozen=True)
class CvtAnalysis:
    speed_centers_kmh: np.ndarray   # centros dos bins de velocidade
    rpm_median: np.ndarray          # RPM mediano por bin (NaN se bin vazio)
    rpm_p10: np.ndarray
    rpm_p90: np.ndarray
    ratio_median: np.ndarray        # RPM por km/h, mediano por bin
    launch_rpm: float | None        # RPM mediano na saída (baixa velocidade, acelerando)
    hold_rpm: float | None          # RPM mediano em aceleração plena a alta velocidade
    hold_cv_pct: float | None       # dispersão desse RPM: baixo = CVT segura o RPM
    n_samples: int


def analyze_cvt(vel_kmh: np.ndarray, rpm: np.ndarray, acel: np.ndarray, min_speed: float = 5.0,
                bins: int = 20) -> CvtAnalysis | None:
    n = min(vel_kmh.size, rpm.size, acel.size)
    if n < 50:
        return None
    v, r, a = vel_kmh[:n], rpm[:n], acel[:n]
    moving = (v > min_speed) & (r > 500)
    if moving.sum() < 30:
        return None

    vm, rm = v[moving], r[moving]
    edges = np.linspace(vm.min(), vm.max(), bins + 1)
    idx = np.clip(np.digitize(vm, edges) - 1, 0, bins - 1)
    med, p10, p90, ratio = (np.full(bins, np.nan) for _ in range(4))
    for b in range(bins):  # `bins` é pequeno (~20); o custo está nas operações por bin, vetorizadas
        sel = idx == b
        if sel.sum() >= 3:
            med[b] = np.median(rm[sel])
            p10[b] = np.percentile(rm[sel], 10)
            p90[b] = np.percentile(rm[sel], 90)
            ratio[b] = np.median(rm[sel] / vm[sel])

    accelerating = a > 0.5
    vmax = float(v.max())
    launch = accelerating & (v > 1.0) & (v < max(10.0, 0.15 * vmax)) & (r > 500)
    hold = accelerating & (v > 0.5 * vmax) & (r > 500)
    launch_rpm = float(np.median(r[launch])) if launch.sum() >= 5 else None
    hold_rpm = hold_cv = None
    if hold.sum() >= 10:
        hold_rpm = float(np.median(r[hold]))
        mean = float(r[hold].mean())
        hold_cv = float(r[hold].std() / mean * 100.0) if mean > 0 else None
    return CvtAnalysis((edges[:-1] + edges[1:]) * 0.5, med, p10, p90, ratio,
                       launch_rpm, hold_rpm, hold_cv, int(moving.sum()))


@dataclass(frozen=True)
class PowerBandUsage:
    band: tuple[float, float]
    pct_time_total: float
    pct_time_accelerating: float | None


def power_band_usage(rpm: np.ndarray, acel: np.ndarray, band: tuple[float, float]) -> PowerBandUsage | None:
    if rpm.size < 20:
        return None
    n = min(rpm.size, acel.size)
    r, a = rpm[:n], acel[:n]
    inb = (r >= band[0]) & (r <= band[1])
    acc = a > 0.5
    pct_acc = float(inb[acc].mean() * 100.0) if acc.sum() >= 10 else None
    return PowerBandUsage(band, float(inb.mean() * 100.0), pct_acc)


def estimate_gear_ratios(vel: np.ndarray, rpm: np.ndarray, n_gears: int = 5, min_vel: float = 5.0) -> dict:
    """Picos no histograma de RPM/Vel (herdado da v6; só faz sentido para câmbio de marchas)."""
    if vel.size < 50:
        return {}
    mask = (vel > min_vel) & (rpm > 500)
    vf, rf = vel[mask], rpm[mask]
    if vf.size < 20:
        return {}
    ratio = rf / (vf + 1e-6)
    counts, edges = np.histogram(ratio, bins=200)
    smooth = np.convolve(counts, np.ones(5) / 5, mode="same")
    peaks, _ = signal.find_peaks(smooth, height=smooth.max() * 0.04, distance=8,
                                 prominence=smooth.max() * 0.02)
    if not peaks.size:
        return {}
    peak_ratios = sorted(((edges[p] + edges[p + 1]) * 0.5 for p in peaks), reverse=True)
    gears = {}
    for i, r in enumerate(peak_ratios[:n_gears], 1):
        tol = r * 0.10
        n_samp = int(np.sum((ratio >= r - tol) & (ratio <= r + tol)))
        gears[f"Marcha {i}"] = {
            "ratio_rpm_kmh": round(float(r), 2),
            "vel_por_1000rpm": round(float(1000.0 / r) if r > 0 else 0.0, 1),
            "amostras": n_samp, "freq_%": round(n_samp / len(ratio) * 100.0, 1),
        }
    return gears


def robust_zscore_anomalies(arr: np.ndarray, thr: float = 3.5) -> np.ndarray:
    """Índices com |z robusto (MAD)| > thr."""
    if arr.size < 10:
        return np.empty(0, dtype=int)
    med = np.median(arr)
    mad = np.median(np.abs(arr - med))
    if mad == 0.0:
        return np.empty(0, dtype=int)
    return np.flatnonzero(np.abs(0.6745 * (arr - med) / mad) > thr)
