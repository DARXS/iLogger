"""FFT e histograma (vetorizados)."""

from __future__ import annotations

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
