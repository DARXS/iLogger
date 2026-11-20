"""ReportModel: o relatório como *dado*. Renderizadores (PDF/Excel/HTML/JSON/CSV) só leem isto.

Construído por `build_report` a partir das runs; não depende de Qt nem de formato de saída.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np

from .. import __version__
from ..domain import channels as ch
from ..domain.analyzers.cvt import CvtAnalysis, analyze_cvt, estimate_gear_ratios
from ..domain.analyzers.phases import detect_phases, phase_summary
from ..domain.models import VehicleProfile
from ..domain.pipeline import FilterConfig
from ..domain.rules import Finding, compare_stats, evaluate_run
from ..domain.stats import DISPLAY_LABELS
from .analysis import compare_setups
from .run_view import RunView

LEVEL_ORDER = {"critical": 0, "warning": 1, "good": 2, "info": 3}
KPI_IDS = ("vel_max", "vel_mean", "rpm_max", "rpm_mean", "acel_max", "acel_min", "dist_total", "duration")


@dataclass(frozen=True)
class RunSection:
    name: str
    sha256: str
    meta_setup: Mapping[str, str]
    notes: str
    tags: tuple[str, ...]
    quality_warnings: tuple[str, ...]
    n_samples: int
    stats: Mapping[str, float]                 # id de métrica -> valor
    phases: Mapping[str, Any]
    cvt: CvtAnalysis | None
    gears: Mapping[str, Any]
    findings: tuple[Finding, ...]
    series: Mapping[str, np.ndarray]           # id de canal -> array (referências read-only, resolução total)


@dataclass(frozen=True)
class SetupComparison:
    setup_key: str
    metric: str
    summary: Mapping[str, tuple[float, float, int]]   # grupo -> (média, desvio, n)
    groups: Mapping[str, list[float]]
    baseline: str | None
    tests: Mapping[str, Any]                          # grupo -> WelchResult | None


@dataclass(frozen=True)
class ReportModel:
    title: str
    generated_at: str
    app_version: str
    profile_name: str
    filter_description: str
    setup_info: Mapping[str, str]
    observations: str
    runs: tuple[RunSection, ...]
    insights: tuple[Finding, ...]
    variations: Mapping[str, Mapping[str, float]] = field(default_factory=dict)   # run -> métrica -> Δ% vs base
    summary_points: tuple[str, ...] = ()
    setup_comparison: SetupComparison | None = None
    attachments: Mapping[str, bytes] = field(default_factory=dict)                # ex.: captura de tela do workspace

    @property
    def base_run(self) -> RunSection | None:
        return self.runs[0] if self.runs else None

    def to_jsonable(self, include_series: bool = False) -> dict[str, Any]:
        def finding(f: Finding) -> dict[str, Any]:
            return {"level": f.level, "title": f.title, "body": f.body, "metric": f.metric, "value": f.value}
        runs = []
        for r in self.runs:
            d: dict[str, Any] = {
                "name": r.name, "sha256": r.sha256, "n_samples": r.n_samples,
                "setup": dict(r.meta_setup), "notes": r.notes, "tags": list(r.tags),
                "quality_warnings": list(r.quality_warnings),
                "stats": {DISPLAY_LABELS[k]: v for k, v in r.stats.items()},
                "stats_by_id": dict(r.stats), "phases": dict(r.phases), "gears": dict(r.gears),
                "findings": [finding(f) for f in r.findings],
            }
            if r.cvt is not None:
                d["cvt"] = {"launch_rpm": r.cvt.launch_rpm, "hold_rpm": r.cvt.hold_rpm, "hold_cv_pct": r.cvt.hold_cv_pct}
            if include_series:
                d["series"] = {k: np.round(v, 4).tolist() for k, v in r.series.items()}
            runs.append(d)
        out: dict[str, Any] = {
            "title": self.title, "generated_at": self.generated_at, "app_version": self.app_version,
            "profile": self.profile_name, "filter": self.filter_description,
            "setup_info": dict(self.setup_info), "observations": self.observations,
            "summary": list(self.summary_points), "insights": [finding(f) for f in self.insights],
            "variations_pct": {k: dict(v) for k, v in self.variations.items()}, "runs": runs,
        }
        if self.setup_comparison:
            sc = self.setup_comparison
            out["setup_comparison"] = {
                "setup_key": sc.setup_key, "metric": sc.metric, "baseline": sc.baseline,
                "summary": {g: {"mean": m, "std": s, "n": n} for g, (m, s, n) in sc.summary.items()},
                "tests": {g: (None if t is None else {"diff": t.diff, "p": t.p, "ci95": list(t.ci95),
                                                      "cohens_d": t.cohens_d, "significant": t.significant})
                          for g, t in sc.tests.items()},
            }
        return out

    def to_json(self, include_series: bool = False) -> str:
        return json.dumps(self.to_jsonable(include_series), ensure_ascii=False, indent=2)


def describe_filter(fs: Mapping[str, Any] | FilterConfig | None, sample_rate_hz: float) -> str:
    c = fs if isinstance(fs, FilterConfig) else FilterConfig.from_legacy(fs, sample_rate_hz)
    names = {"butterworth": "Butterworth", "bessel": "Bessel", "chebyshev_type_i": "Chebyshev I",
             "savitzky_golay": "Savitzky-Golay", "median": "Mediana", "moving_average": "Média móvel"}
    n = names.get(c.kind, c.kind)
    if c.kind in ("butterworth", "bessel"):
        return f"{n} ordem {c.order}, corte {c.cutoff_hz:.2f} Hz (fs = {sample_rate_hz:g} Hz)"
    if c.kind == "chebyshev_type_i":
        return f"{n} ordem {c.order}, ripple {c.ripple_db:g} dB, corte {c.cutoff_hz:.2f} Hz"
    if c.kind == "savitzky_golay":
        return f"{n}, janela {c.window}, polinômio {c.polyorder}"
    if c.kind == "median":
        return f"{n}, kernel {c.kernel}"
    return f"{n}, janela {c.window}"


def _summary_points(runs: Sequence[RunSection], insights: Sequence[Finding]) -> tuple[str, ...]:
    pts: list[str] = []
    if not runs:
        return ()
    best_v = max(runs, key=lambda r: r.stats["vel_max"])
    pts.append(f"{len(runs)} run(s) analisada(s); maior velocidade máxima: {best_v.name} "
               f"({best_v.stats['vel_max']:.1f} km/h).")
    if len(runs) > 1:
        best_d = max(runs, key=lambda r: r.stats["vel_mean"])
        pts.append(f"Maior velocidade média: {best_d.name} ({best_d.stats['vel_mean']:.1f} km/h).")
    crit = sum(1 for f in insights if f.level == "critical")
    warn = sum(1 for f in insights if f.level == "warning")
    pts.append(f"{crit} alerta(s) crítico(s) e {warn} aviso(s) nos insights automáticos." if crit or warn
               else "Nenhum alerta crítico ou aviso nos insights automáticos.")
    qual = [r.name for r in runs if r.quality_warnings]
    if qual:
        pts.append("Atenção à qualidade dos dados em: " + ", ".join(qual) + ".")
    cvt_cv = [(r.name, r.cvt.hold_cv_pct) for r in runs if r.cvt and r.cvt.hold_cv_pct is not None]
    if cvt_cv:
        name, cv = min(cvt_cv, key=lambda x: x[1])
        pts.append(f"CVT mais estável em aceleração plena: {name} (CV do RPM {cv:.1f}%).")
    return tuple(pts)


def build_report(runs: Sequence[RunView], fs: Mapping[str, Any] | FilterConfig | None, profile: VehicleProfile,
                 setup_info: Mapping[str, str] | None = None, observations: str = "",
                 setup_key: str | None = None, metric: str = "vel_max", title: str = "Relatório de Telemetria",
                 attachments: Mapping[str, bytes] | None = None) -> ReportModel:
    rules = profile.rules
    sections: list[RunSection] = []
    insights: list[Finding] = []
    processed = [(r, r.processed_for(fs)) for r in runs]
    for r, p in processed:
        findings = evaluate_run(r.run, p, profile)
        insights.extend(findings)
        ph = phase_summary(detect_phases(p.acel, p.time_s, p.vel_kmh, p.dist, rules.phase_accel_thr,
                                         rules.phase_brake_thr), r.run.duration_s)
        sections.append(RunSection(
            name=r.file_name, sha256=r.run.source_sha256, meta_setup=dict(r.meta.setup), notes=r.meta.notes,
            tags=r.meta.tags, quality_warnings=r.run.quality.warnings, n_samples=r.run.n_samples,
            stats={k: p.stats.metric(k) for k in DISPLAY_LABELS}, phases=ph,
            cvt=analyze_cvt(p.vel_kmh, p.rpm, p.acel, rules.cvt_min_speed_kmh),
            gears=estimate_gear_ratios(p.vel_kmh, p.rpm), findings=tuple(findings),
            series={ch.TIME: p.time_s, ch.VEL: p.vel_kmh, ch.RPM: p.rpm, ch.ACEL: p.acel, ch.DIST: p.dist,
                    ch.VEL_RAW: r.run.vel_raw_kmh, ch.RPM_RAW: r.run.rpm_raw}))

    variations: dict[str, dict[str, float]] = {}
    if len(processed) > 1:
        base = processed[0][1].stats
        for _, p in processed[1:]:
            insights.extend(compare_stats(base, p.stats))
            variations[p.stats.name] = {
                mid: 100.0 * (p.stats.metric(mid) - base.metric(mid)) / (abs(base.metric(mid)) or 1e-9)
                for mid in DISPLAY_LABELS}
    insights.sort(key=lambda f: LEVEL_ORDER.get(f.level, 9))

    cmp_: SetupComparison | None = None
    if setup_key:
        raw = compare_setups(list(runs), fs, setup_key, metric)
        if raw["groups"]:
            cmp_ = SetupComparison(setup_key, metric, raw["summary"], raw["groups"], raw["baseline"], raw["tests"])

    rate = runs[0].run.sample_rate_hz if runs else profile.sensor.sample_rate_hz
    return ReportModel(
        title=title, generated_at=datetime.now().strftime("%d/%m/%Y %H:%M"), app_version=__version__,
        profile_name=profile.name, filter_description=describe_filter(fs, rate), setup_info=dict(setup_info or {}),
        observations=observations, runs=tuple(sections), insights=tuple(insights), variations=variations,
        summary_points=_summary_points(sections, insights), setup_comparison=cmp_,
        attachments=dict(attachments or {}),
    )


def provenance_digest(model: ReportModel) -> str:
    """Hash curto das entradas do relatório (para citar no rodapé)."""
    h = hashlib.sha256("".join(r.sha256 for r in model.runs).encode())
    h.update(model.filter_description.encode())
    return h.hexdigest()[:12]
