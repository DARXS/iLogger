"""Pipeline de processamento: FilterConfig (validado, em Hz) → ProcessedRun imutável.

Diferenças em relação à v6 (todas intencionais):
  * cutoff em **Hz** (a v6 usava fração do Nyquist, cujo significado mudava com a taxa);
  * distância por integração trapezoidal (a v6 usava soma retangular, com viés);
  * média móvel e mediana com bordas "nearest" (a v6 usava zero-padding, que derrubava as pontas);
  * resultados read-only e cache com chave (dados da run, configuração).
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections import OrderedDict
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from scipy import integrate, ndimage, signal

from .errors import ValidationError
from .models import Run
from .stats import RunStats, compute_run_stats

FILTER_KINDS = ("butterworth", "savitzky_golay", "chebyshev_type_i", "bessel", "median", "moving_average")


@dataclass(frozen=True)
class FilterConfig:
    kind: str = "butterworth"
    order: int = 4
    cutoff_hz: float = 1.0
    ripple_db: float = 1.0       # Chebyshev I
    window: int = 11             # Savitzky-Golay / média móvel (amostras)
    polyorder: int = 2           # Savitzky-Golay
    kernel: int = 5              # mediana (amostras)
    accel_cutoff_hz: float = 1.0  # suavização da aceleração derivada
    accel_order: int = 4

    def validate(self, sample_rate_hz: float) -> None:
        nyq = sample_rate_hz / 2.0
        if self.kind not in FILTER_KINDS:
            raise ValidationError(f"filtro desconhecido: {self.kind!r}")
        if not 1 <= self.order <= 10:
            raise ValidationError("order deve estar entre 1 e 10")
        if not 0 < self.cutoff_hz < nyq:
            raise ValidationError(f"cutoff_hz deve estar em (0, {nyq:g}) Hz para fs={sample_rate_hz:g} Hz")
        if not 0 < self.accel_cutoff_hz < nyq:
            raise ValidationError(f"accel_cutoff_hz deve estar em (0, {nyq:g}) Hz")
        if self.ripple_db <= 0:
            raise ValidationError("ripple_db deve ser > 0")
        if self.window < 2 or self.kernel < 1 or self.polyorder < 0:
            raise ValidationError("window/kernel/polyorder inválidos")

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()[:16]

    # ── compatibilidade com o dict da UI/workspaces v6 (cutoff normalizado) ──
    @classmethod
    def from_legacy(cls, fs: Mapping[str, Any] | None, sample_rate_hz: float = 20.0) -> FilterConfig:
        fs = fs or {}
        nyq = sample_rate_hz / 2.0

        def hz(norm: float) -> float:
            return float(min(max(norm, 0.001), 0.99) * nyq)

        kind = fs.get("type", "butterworth")
        kw: dict[str, Any] = {"kind": kind, "accel_cutoff_hz": hz(0.1)}
        if kind == "butterworth":
            kw.update(order=int(fs.get("butter_order", 4)), cutoff_hz=hz(fs.get("butter_cutoff", 0.1)))
        elif kind == "chebyshev_type_i":
            kw.update(order=int(fs.get("cheby1_order", 4)), ripple_db=float(fs.get("cheby1_rp", 1)),
                      cutoff_hz=hz(fs.get("cheby1_cutoff", 0.1)))
        elif kind == "bessel":
            kw.update(order=int(fs.get("bessel_order", 4)), cutoff_hz=hz(fs.get("bessel_cutoff", 0.1)))
        elif kind == "savitzky_golay":
            kw.update(window=int(fs.get("savgol_window", 11)), polyorder=int(fs.get("savgol_polyorder", 2)))
        elif kind == "median":
            kw.update(kernel=int(fs.get("median_kernel", 5)))
        elif kind == "moving_average":
            kw.update(window=int(fs.get("moving_avg_window", 5)))
        return cls(**kw)

    def to_legacy(self, sample_rate_hz: float = 20.0) -> dict[str, Any]:
        nyq = sample_rate_hz / 2.0
        s: dict[str, Any] = {"type": self.kind}
        if self.kind == "butterworth":
            s.update(butter_order=self.order, butter_cutoff=self.cutoff_hz / nyq)
        elif self.kind == "chebyshev_type_i":
            s.update(cheby1_order=self.order, cheby1_rp=self.ripple_db, cheby1_cutoff=self.cutoff_hz / nyq)
        elif self.kind == "bessel":
            s.update(bessel_order=self.order, bessel_cutoff=self.cutoff_hz / nyq)
        elif self.kind == "savitzky_golay":
            s.update(savgol_window=self.window, savgol_polyorder=self.polyorder)
        elif self.kind == "median":
            s.update(median_kernel=self.kernel)
        elif self.kind == "moving_average":
            s.update(moving_avg_window=self.window)
        return s


def _odd(k: int) -> int:
    return k if k % 2 else k + 1


def _safe_filtfilt(b: np.ndarray, a: np.ndarray, x: np.ndarray) -> np.ndarray:
    """filtfilt zero-phase; devolve cópia se o sinal for curto demais (exigência do SciPy)."""
    if x.size <= 3 * max(len(a), len(b)) + 1:
        return x.copy()
    return np.asarray(signal.filtfilt(b, a, x))


def _filter_1d(x: np.ndarray, cfg: FilterConfig, fs_hz: float) -> np.ndarray:
    nyq = fs_hz / 2.0
    if cfg.kind == "savitzky_golay":
        w = _odd(cfg.window)
        if x.size <= w:
            return x.copy()
        return np.asarray(signal.savgol_filter(x, w, min(cfg.polyorder, w - 1)))
    if cfg.kind == "median":
        return np.asarray(ndimage.median_filter(x, size=_odd(cfg.kernel), mode="nearest"))
    if cfg.kind == "moving_average":
        return np.asarray(ndimage.uniform_filter1d(x, size=max(2, cfg.window), mode="nearest"))
    wn = cfg.cutoff_hz / nyq
    if cfg.kind == "chebyshev_type_i":
        b, a = signal.cheby1(cfg.order, cfg.ripple_db, wn, btype="low")
    elif cfg.kind == "bessel":
        b, a = signal.bessel(cfg.order, wn, btype="low", norm="phase")
    else:
        b, a = signal.butter(cfg.order, wn)
    return _safe_filtfilt(b, a, x)


@dataclass(frozen=True, eq=False)
class ProcessedRun:
    """Resultado imutável do pipeline para (run, config)."""

    run_hash: str
    config: FilterConfig
    time_s: np.ndarray
    rpm: np.ndarray
    vel_ms: np.ndarray
    vel_kmh: np.ndarray
    acel: np.ndarray
    dist: np.ndarray
    stats: RunStats

    @property
    def key(self) -> tuple[str, str]:
        return (self.run_hash, self.config.digest())


class Pipeline:
    def __init__(self, config: FilterConfig):
        self.config = config

    def apply(self, run: Run) -> ProcessedRun:
        cfg, fs_hz = self.config, run.sample_rate_hz
        cfg.validate(fs_hz)
        t = run.time_s
        vel_ms_raw = run.vel_raw_kmh * (5.0 / 18.0)

        rpm = _filter_1d(run.rpm_raw, cfg, fs_hz)
        vel_ms = _filter_1d(vel_ms_raw, cfg, fs_hz)

        if t.size >= 3:
            acel_raw = np.gradient(vel_ms, t, edge_order=2)
            b, a = signal.butter(cfg.accel_order, cfg.accel_cutoff_hz / (fs_hz / 2.0))
            acel = _safe_filtfilt(b, a, acel_raw)
        else:
            acel = np.zeros_like(vel_ms)
        dist = integrate.cumulative_trapezoid(vel_ms, t, initial=0.0) if t.size else np.empty(0)

        vel_kmh = vel_ms * 3.6
        arrays = (rpm, vel_ms, vel_kmh, acel, dist)
        for arr in arrays:
            arr.setflags(write=False)
        stats = compute_run_stats(run.name, t, vel_kmh, rpm, acel, dist)
        return ProcessedRun(run.content_hash, cfg, t, rpm, vel_ms, vel_kmh, acel, dist, stats)


class ProcessingCache:
    """LRU thread-safe. Chave = (hash dos dados da run, hash da configuração)."""

    def __init__(self, max_entries: int = 64):
        self._store: OrderedDict[tuple[str, str], ProcessedRun] = OrderedDict()
        self._lock = threading.RLock()
        self._max = max_entries
        self.hits = 0
        self.misses = 0

    def get_or_compute(self, key: tuple[str, str], factory: Callable[[], ProcessedRun]) -> ProcessedRun:
        with self._lock:
            hit = self._store.get(key)
            if hit is not None:
                self._store.move_to_end(key)
                self.hits += 1
                return hit
            self.misses += 1
        value = factory()  # fora do lock: cálculo pesado não bloqueia outras threads
        with self._lock:
            self._store[key] = value
            self._store.move_to_end(key)
            while len(self._store) > self._max:
                self._store.popitem(last=False)
        return value

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)
