"""Correlações e comparações entre runs/setups (com significância estatística)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from scipy import stats as sp_stats

_STRENGTH = [(0.85, "muito forte"), (0.65, "forte"), (0.45, "moderada"), (0.25, "fraca"), (0.0, "desprezível")]


@dataclass(frozen=True)
class Correlation:
    key_a: str
    key_b: str
    label: str
    r: float
    p: float

    @property
    def strength(self) -> str:
        return next(s for thr, s in _STRENGTH if abs(self.r) >= thr)


def pearson(a: np.ndarray, b: np.ndarray, key_a: str, key_b: str, label: str) -> Correlation | None:
    n = min(a.size, b.size)
    if n < 20 or np.std(a[:n]) == 0 or np.std(b[:n]) == 0:
        return None
    r, p = sp_stats.pearsonr(a[:n], b[:n])
    return Correlation(key_a, key_b, label, float(r), float(p))


@dataclass(frozen=True)
class WelchResult:
    n_a: int
    n_b: int
    mean_a: float
    mean_b: float
    diff: float            # mean_b - mean_a
    t: float
    p: float
    dof: float
    ci95: tuple[float, float]
    cohens_d: float

    @property
    def significant(self) -> bool:
        return self.p < 0.05


def welch_compare(a: Sequence[float], b: Sequence[float]) -> WelchResult | None:
    """Teste t de Welch entre dois grupos de repetições (ex.: setup A × setup B)."""
    x, y = np.asarray(a, float), np.asarray(b, float)
    if x.size < 2 or y.size < 2:
        return None
    va, vb = x.var(ddof=1), y.var(ddof=1)
    se2 = va / x.size + vb / y.size
    diff = float(y.mean() - x.mean())
    if se2 == 0:
        return WelchResult(x.size, y.size, float(x.mean()), float(y.mean()), diff, math.inf if diff else 0.0,
                           0.0 if diff else 1.0, float(x.size + y.size - 2), (diff, diff), math.inf if diff else 0.0)
    t, p = sp_stats.ttest_ind(y, x, equal_var=False)
    dof = se2 ** 2 / ((va / x.size) ** 2 / (x.size - 1) + (vb / y.size) ** 2 / (y.size - 1))
    half = float(sp_stats.t.ppf(0.975, dof) * math.sqrt(se2))
    pooled = math.sqrt(((x.size - 1) * va + (y.size - 1) * vb) / (x.size + y.size - 2))
    d = diff / pooled if pooled > 0 else 0.0
    return WelchResult(x.size, y.size, float(x.mean()), float(y.mean()), diff, float(t), float(p),
                       float(dof), (diff - half, diff + half), float(d))
