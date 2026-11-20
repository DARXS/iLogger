"""Detecção de fases de condução (aceleração / frenagem / estabilização), 100% vetorizada."""

from __future__ import annotations

import numpy as np
import pandas as pd

PHASES = ("aceleração", "frenagem", "estabilização")


def detect_phases(acel: np.ndarray, time: np.ndarray, vel: np.ndarray, dist: np.ndarray,
                  accel_thr: float = 1.0, brake_thr: float = -1.0, min_samples: int = 3) -> pd.DataFrame:
    if acel.size < 10:
        return pd.DataFrame()
    labels = np.where(acel > accel_thr, 0, np.where(acel < brake_thr, 1, 2))
    change = np.flatnonzero(labels[:-1] != labels[1:])
    starts = np.concatenate([[0], change + 1])
    ends = np.concatenate([change + 1, [labels.size]])  # exclusivo

    # Estatísticas por segmento via reduceat: sem loop Python sobre segmentos.
    seg_mean = np.add.reduceat(acel, starts) / (ends - starts)
    seg_max = np.maximum.reduceat(acel, starts)
    seg_min = np.minimum.reduceat(acel, starts)

    keep = (ends - starts) >= min_samples
    if not keep.any():
        return pd.DataFrame()
    s, e = starts[keep], ends[keep] - 1  # e = último índice inclusivo
    return pd.DataFrame({
        "Fase": np.array(PHASES)[labels[s]],
        "Início (s)": np.round(time[s], 3),
        "Fim (s)": np.round(time[e], 3),
        "Duração (s)": np.round(time[e] - time[s], 3),
        "Vel. Inicial (km/h)": np.round(vel[s], 2),
        "Vel. Final (km/h)": np.round(vel[e], 2),
        "ΔVel (km/h)": np.round(vel[e] - vel[s], 2),
        "Acel. Média (m/s²)": np.round(seg_mean[keep], 3),
        "Acel. Pico (m/s²)": np.round(seg_max[keep], 3),
        "Acel. Mín (m/s²)": np.round(seg_min[keep], 3),
        "Dist. Parcial (m)": np.round(dist[e] - dist[s], 2),
    })


def phase_summary(df: pd.DataFrame, total_time: float) -> dict:
    if df.empty or total_time <= 0:
        return {}
    out = {}
    for phase in PHASES:
        sub = df[df["Fase"] == phase]
        dur = float(sub["Duração (s)"].sum()) if not sub.empty else 0.0
        out[phase] = {"duração_s": round(dur, 2), "percent_%": round(dur / total_time * 100, 1),
                      "n_eventos": len(sub)}
    return out
