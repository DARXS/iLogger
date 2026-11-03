"""Casos de uso de análise. Funções *puras* sobre `ProcessedRun`: seguras em threads de fundo."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

from ..domain import channels as ch
from ..domain.analyzers.compare import Correlation, WelchResult, pearson, welch_compare
from ..domain.analyzers.cvt import analyze_cvt, estimate_gear_ratios
from ..domain.analyzers.phases import detect_phases, phase_summary
from ..domain.models import VehicleProfile
from ..domain.rules import Finding, compare_stats, evaluate_run
from ..domain.stats import DISPLAY_LABELS
from .run_view import RunView

AUTO_CORRELATIONS = [
    (ch.VEL, ch.RPM, "Velocidade × RPM"),
    (ch.ACEL, ch.RPM, "Aceleração × RPM"),
    (ch.VEL, ch.ACEL, "Velocidade × Aceleração"),
]


def generate_stats(runs: Sequence[RunView], fs: Mapping[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Tabelas de métricas e variação % vs. base (1ª run). Também aplica `fs` às views."""
    if not runs:
        return pd.DataFrame(), pd.DataFrame()
    for r in runs:
        r.apply_filters_and_recalculate(fs)
    metrics = pd.DataFrame([r.stats for r in runs]).set_index("Arquivo").round(2)
    variations = pd.DataFrame()
    if len(metrics) > 1:
        base = metrics.iloc[0]
        variations = metrics.iloc[1:].apply(lambda row: ((row - base) / base.replace(0, 1e-9)) * 100,
                                            axis=1).round(2)
    return metrics, variations


def compute_correlation_matrix(runs: Sequence[RunView], fs: Mapping[str, Any],
                               keys: Sequence[str] | None = None) -> dict[str, pd.DataFrame]:
    keys = list(keys or [ch.KEY_VEL_KMH_FILT, ch.KEY_RPM_FILT, ch.KEY_ACEL_MS2_FILT, ch.KEY_DIST_M])
    out = {}
    for r in runs:
        r.apply_filters_and_recalculate(fs)
        cols = {k: r.get_channel(k) for k in keys if r.get_channel(k).size}
        if len(cols) >= 2:
            n = min(a.size for a in cols.values())
            out[r.file_name] = pd.DataFrame({k: v[:n] for k, v in cols.items()}).corr(method="pearson").round(4)
    return out


def compute_phase_summary_all(runs: Sequence[RunView], fs: Mapping[str, Any]) -> dict[str, dict]:
    out = {}
    for r in runs:
        r.apply_filters_and_recalculate(fs)
        out[r.file_name] = r.phase_summary()
    return out


def full_analysis(runs: Sequence[RunView], fs: Mapping[str, Any], profile: VehicleProfile) -> dict[str, Any]:
    """Insights + correlações + marchas + fases + CVT. Não muta as views (thread-safe)."""
    insights: list[Finding] = []
    correlations: dict[str, list[Correlation]] = {}
    gear_data: dict[str, dict] = {}
    phase_data: dict[str, dict] = {}
    cvt_data: dict[str, Any] = {}
    rules = profile.rules
    processed = [(r, r.processed_for(fs)) for r in runs]

    for r, p in processed:
        insights.extend(evaluate_run(r.run, p, profile))
        series = {ch.VEL: p.vel_kmh, ch.RPM: p.rpm, ch.ACEL: p.acel, ch.DIST: p.dist}
        correlations[r.file_name] = [c for ka, kb, lb in AUTO_CORRELATIONS
                                     if (c := pearson(series[ka], series[kb], ka, kb, lb))]
        gear_data[r.file_name] = estimate_gear_ratios(p.vel_kmh, p.rpm)
        phase_data[r.file_name] = phase_summary(
            detect_phases(p.acel, p.time_s, p.vel_kmh, p.dist, rules.phase_accel_thr, rules.phase_brake_thr),
            r.run.duration_s)
        cvt_data[r.file_name] = analyze_cvt(p.vel_kmh, p.rpm, p.acel, rules.cvt_min_speed_kmh)

    if len(processed) > 1:
        base = processed[0][1].stats
        for _, p in processed[1:]:
            insights.extend(compare_stats(base, p.stats))
    return {"insights": insights, "correlations": correlations, "gear_data": gear_data,
            "phase_data": phase_data, "cvt_data": cvt_data}


def compare_setups(runs: Sequence[RunView], fs: Mapping[str, Any], setup_key: str,
                   metric_id: str = "vel_max") -> dict[str, Any]:
    """Agrupa runs por `meta.setup[setup_key]` e compara o 1º grupo com os demais (Welch)."""
    if metric_id not in DISPLAY_LABELS:
        raise KeyError(metric_id)
    groups: dict[str, list[float]] = {}
    for r in runs:
        label = r.meta.setup.get(setup_key)
        if label is None or str(label).strip() == "":
            continue
        groups.setdefault(str(label), []).append(r.processed_for(fs).stats.metric(metric_id))
    names = list(groups)
    tests: dict[str, WelchResult | None] = {n: welch_compare(groups[names[0]], groups[n]) for n in names[1:]}
    return {"metric": metric_id, "setup_key": setup_key, "groups": groups, "baseline": names[0] if names else None,
            "tests": tests, "summary": {n: (float(np.mean(v)), float(np.std(v, ddof=1)) if len(v) > 1 else 0.0, len(v))
                                        for n, v in groups.items()}}
