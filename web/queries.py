"""Consultas que alimentam o front-end: séries decimadas, delta de tempo (estilo F1), motor/CVT, visão geral."""

from __future__ import annotations

from typing import Any

import numpy as np

from ..application.analysis import compare_setups
from ..application.report_model import ReportModel, build_report
from ..domain import expressions
from ..domain import spectral as sp
from ..domain.analyzers.cvt import analyze_cvt, estimate_gear_ratios, power_band_usage
from ..domain.analyzers.phases import detect_phases
from ..domain.errors import ValidationError
from ..domain.pipeline import ProcessedRun
from .state import AppService, run_id

CHANNEL_INFO = {
    "time": ("Tempo", "s"), "dist": ("Distância", "m"), "vel": ("Velocidade", "km/h"), "rpm": ("RPM", "rpm"),
    "acel": ("Aceleração", "m/s²"), "vel_raw": ("Velocidade (bruta)", "km/h"), "rpm_raw": ("RPM (bruto)", "rpm"),
}


def _r(a: np.ndarray, nd: int = 3) -> list[float]:
    return np.round(a, nd).tolist()


def _arrays(svc: AppService, rv) -> dict[str, np.ndarray]:
    p: ProcessedRun = rv.processed_for(svc.session.filter)
    return {"time": p.time_s, "dist": p.dist, "vel": p.vel_kmh, "rpm": p.rpm, "acel": p.acel,
            "vel_raw": rv.run.vel_raw_kmh, "rpm_raw": rv.run.rpm_raw}


def channels() -> list[dict[str, str]]:
    return [{"id": k, "label": v[0], "unit": v[1]} for k, v in CHANNEL_INFO.items()]


# ── séries ────────────────────────────────────────────────────────────────────
def series(svc: AppService, ids: list[str], chans: list[str], x_axis: str = "time", x0: float | None = None,
           x1: float | None = None, max_points: int = 1800) -> dict[str, Any]:
    bad = [c for c in chans if c not in CHANNEL_INFO]
    if bad or x_axis not in ("time", "dist"):
        raise ValidationError(f"canal/eixo inválido: {bad or x_axis}")
    max_points = int(min(max(max_points, 100), 20000))
    out: dict[str, Any] = {}
    for rv in svc.many(ids):
        arr = _arrays(svc, rv)
        x = arr[x_axis]
        lo = 0 if x0 is None else max(0, int(np.searchsorted(x, x0, side="left")) - 1)
        hi = x.size if x1 is None else min(x.size, int(np.searchsorted(x, x1, side="right")) + 1)
        if hi - lo < 2:
            lo, hi = 0, x.size
        idx = sp.decimate_indices([arr[c][lo:hi] for c in chans], max_points) + lo
        out[run_id(rv)] = {"x": _r(x[idx]), **{c: _r(arr[c][idx]) for c in chans}}
    return {"x_axis": x_axis, "unit": CHANNEL_INFO[x_axis][1], "runs": out}


def math_series(svc: AppService, ids: list[str], expression: str, x_axis: str = "time", max_points: int = 1800) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for rv in svc.many(ids):
        arr = _arrays(svc, rv)
        variables = {"tempo": arr["time"], "vel": arr["vel"], "rpm": arr["rpm"], "acel": arr["acel"], "dist": arr["dist"],
                     "rpm_raw": arr["rpm_raw"], "vel_raw": arr["vel_raw"]}
        y = expressions.evaluate(expression, variables)
        x = arr[x_axis]
        idx = sp.decimate_indices([y], int(max_points))
        out[run_id(rv)] = {"x": _r(x[idx]), "y": _r(y[idx], 4)}
    return {"x_axis": x_axis, "runs": out}


# ── comparação estilo F1 ──────────────────────────────────────────────────────
def compare(svc: AppService, ids: list[str], ref: str | None, sectors: int = 20, points: int = 700) -> dict[str, Any]:
    runs = svc.many(ids)
    if len(runs) < 1:
        raise ValidationError("selecione ao menos uma run")
    ref_id = ref or run_id(runs[0])
    ref_rv = svc.get(ref_id)
    if ref_rv not in runs:
        runs = [ref_rv, *runs]
    data = {}
    for rv in runs:
        a = _arrays(svc, rv)
        d = np.maximum.accumulate(a["dist"])
        data[run_id(rv)] = (a, d)
    dmax = min(float(d[-1]) for _, d in data.values())
    if dmax <= 1.0:
        raise ValidationError("distância percorrida insuficiente para comparar")
    sectors = int(min(max(sectors, 3), 60))
    grid = np.linspace(0.0, dmax, int(points))
    edges = np.linspace(0.0, dmax, sectors + 1)

    def t_at(rid: str, at: np.ndarray) -> np.ndarray:
        a, d = data[rid]
        return np.interp(at, d, a["time"])

    t_ref = t_at(ref_id, grid)
    sector_t = {rid: np.diff(t_at(rid, edges)) for rid in data}
    best = np.argmin(np.vstack([sector_t[r] for r in data]), axis=0)
    order = list(data)
    res = []
    for rid in data:
        a, _ = data[rid]
        st = sector_t[rid]
        rt = sector_t[ref_id]
        colors = []
        for i in range(sectors):
            if order[int(best[i])] == rid:
                colors.append("purple")           # melhor tempo do setor entre todas as runs
            elif st[i] < rt[i] - 1e-9:
                colors.append("green")            # mais rápida que a referência
            else:
                colors.append("yellow")
        res.append({
            "id": rid, "delta": _r(t_at(rid, grid) - t_ref, 4), "speed": _r(np.interp(grid, data[rid][1], a["vel"]), 2),
            "rpm": _r(np.interp(grid, data[rid][1], a["rpm"]), 0), "sector_times": _r(st, 4), "sector_colors": colors,
            "final_delta": float(t_at(rid, np.array([dmax]))[0] - t_ref[-1]), "time_at_end": float(t_at(rid, np.array([dmax]))[0]),
        })
    return {"ref": ref_id, "dist": _r(grid, 2), "dist_total": dmax, "sectors": sectors, "sector_edges": _r(edges, 2), "runs": res}


# ── motor / CVT ───────────────────────────────────────────────────────────────
def engine(svc: AppService, rid: str, bins: int = 40) -> dict[str, Any]:
    rv = svc.get(rid)
    a = _arrays(svc, rv)
    prof = svc.session.profile
    cvt = analyze_cvt(a["vel"], a["rpm"], a["acel"], prof.rules.cvt_min_speed_kmh)
    n = a["vel"].size
    step = max(1, n // 3500)
    out: dict[str, Any] = {"scatter": {"vel": _r(a["vel"][::step], 2), "rpm": _r(a["rpm"][::step], 0)}, "cvt": None}
    if cvt is not None:
        ok = np.isfinite(cvt.rpm_median)
        out["cvt"] = {"speed": _r(cvt.speed_centers_kmh[ok], 2), "median": _r(cvt.rpm_median[ok], 0),
                      "p10": _r(cvt.rpm_p10[ok], 0), "p90": _r(cvt.rpm_p90[ok], 0), "launch_rpm": cvt.launch_rpm,
                      "hold_rpm": cvt.hold_rpm, "hold_cv_pct": cvt.hold_cv_pct}
    dt = float(np.mean(np.diff(a["time"]))) if n > 1 else 0.0
    for key, label in (("rpm", "rpm"), ("vel", "vel")):
        centers, counts = sp.histogram(a[key], bins)
        out[f"{label}_hist"] = {"centers": _r(centers, 1), "seconds": _r(counts * dt, 2)}
    f, m = sp.fft(a["rpm"], a["time"])
    keep = f <= 5.0
    out["rpm_fft"] = {"freq": _r(f[keep], 3), "mag": _r(m[keep], 2)}
    out["gears"] = estimate_gear_ratios(a["vel"], a["rpm"])
    band = prof.power_band_rpm
    out["power_band"] = None
    if band:
        pb = power_band_usage(a["rpm"], a["acel"], band)
        out["power_band"] = {"band": list(band), "pct_total": pb.pct_time_total if pb else None,
                             "pct_accel": pb.pct_time_accelerating if pb else None}
    return out


def phases(svc: AppService, rid: str) -> list[dict[str, Any]]:
    rv = svc.get(rid)
    a = _arrays(svc, rv)
    r = svc.session.profile.rules
    df = detect_phases(a["acel"], a["time"], a["vel"], a["dist"], r.phase_accel_thr, r.phase_brake_thr)
    if df.empty:
        return []
    return [{"phase": row["Fase"], "t0": row["Início (s)"], "t1": row["Fim (s)"], "acel": row["Acel. Média (m/s²)"],
             "dist": row["Dist. Parcial (m)"]} for _, row in df.iterrows()]


# ── visão geral / relatório ───────────────────────────────────────────────────
def build_model(svc: AppService, title: str = "Relatório de Telemetria", setup_key: str | None = None,
                metric: str = "vel_max") -> ReportModel:
    s = svc.session
    return build_report(s.runs, s.filter, s.profile, s.setup_info, s.observations, setup_key=setup_key or None,
                        metric=metric, title=title)


def overview(svc: AppService) -> dict[str, Any]:
    model = build_model(svc)
    data = model.to_jsonable()
    runs = {run_id(r): r for r in svc.runs}
    for jr, sec in zip(data["runs"], model.runs, strict=True):
        rid = sec.sha256[:12]
        rv = runs[rid]
        t, v = sec.series["time"], sec.series["vel"]
        idx = sp.decimate_indices([v], 160)
        jr["id"], jr["color"], jr["spark"] = rid, svc.color_of(rid), {"t": _r(t[idx], 2), "v": _r(v[idx], 2)}
        jr["phases_list"] = phases(svc, rid)
        jr["duration_s"] = rv.run.duration_s
    return data


def setups(svc: AppService, key: str, metric: str) -> dict[str, Any]:
    raw = compare_setups(svc.runs, svc.session.filter, key, metric)
    return {
        "key": key, "metric": metric, "baseline": raw["baseline"], "groups": raw["groups"],
        "summary": {g: {"mean": m, "std": s, "n": n} for g, (m, s, n) in raw["summary"].items()},
        "tests": {g: (None if t is None else {"diff": t.diff, "p": t.p, "ci95": list(t.ci95), "cohens_d": t.cohens_d,
                                              "t": t.t, "dof": t.dof, "significant": t.significant, "n_a": t.n_a, "n_b": t.n_b})
                  for g, t in raw["tests"].items()},
    }
