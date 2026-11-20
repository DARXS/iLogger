"""FFT e histograma (vetorizados)."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def fft(data: np.ndarray, time_s: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """FFT real com janela de Hann. Retorna (freqs_hz, magnitude)."""
    if data.size < 16 or time_s.size < 16:
        return np.empty(0), np.empty(0)
    dt = float(np.mean(np.diff(time_s)))
    if dt <= 0.0:
        return np.empty(0), np.empty(0)
    sig = data - data.mean()
    spec = np.fft.rfft(sig * np.hanning(sig.size))
    return np.fft.rfftfreq(sig.size, d=dt), np.abs(spec) * (2.0 / sig.size)


def histogram(data: np.ndarray, bins: int = 50) -> tuple[np.ndarray, np.ndarray]:
    if data.size == 0:
        return np.empty(0), np.empty(0)
    counts, edges = np.histogram(data, bins=bins)
    return (edges[:-1] + edges[1:]) * 0.5, counts.astype(np.float64)


def decimate(x: np.ndarray, y: np.ndarray, max_points: int = 1800) -> tuple[np.ndarray, np.ndarray]:
    """Decimação min/max por bloco: reduz pontos preservando os picos (importante em telemetria)."""
    n = y.size
    if n <= max_points or max_points < 4:
        return x, y
    bins = max_points // 2
    k = n // bins
    yb = y[: bins * k].reshape(bins, k)
    base = np.arange(bins) * k
    idx = np.sort(np.concatenate([base + yb.argmin(axis=1), base + yb.argmax(axis=1)]))
    return x[idx], y[idx]


def decimate_indices(arrays: Sequence[np.ndarray], max_points: int) -> np.ndarray:
    """Índices comuns a vários canais: união dos mín/máx por bloco de cada canal (mantém todos os picos)."""
    n = arrays[0].size if arrays else 0
    if n <= max_points or max_points < 8:
        return np.arange(n)
    bins = max(2, max_points // (2 * max(1, len(arrays))))
    k = n // bins
    base = np.arange(bins) * k
    parts = [np.array([0, n - 1])]
    for a in arrays:
        blk = a[: bins * k].reshape(bins, k)
        parts += [base + blk.argmin(axis=1), base + blk.argmax(axis=1)]
    return np.unique(np.concatenate(parts))
