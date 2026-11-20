"""Gráficos para relatórios (matplotlib Agg, sem pyplot → seguro em threads). Entrada: `ReportModel`."""

from __future__ import annotations

import io

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from ...application.report_model import ReportModel, RunSection, SetupComparison
from ...domain import channels as ch
from ...domain.spectral import decimate

PALETTE = ["#0b7285", "#e8590c", "#2b8a3e", "#c2255c", "#5f3dc4", "#e67700", "#1971c2", "#868e96"]
_INK, _GRID = "#343a40", "#dee2e6"


def _png(fig: Figure, dpi: int = 150) -> bytes:
    buf = io.BytesIO()
    FigureCanvasAgg(fig)
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor="white")
    return buf.getvalue()


def _style(ax, xlabel: str = "", ylabel: str = "", title: str = "") -> None:
    ax.set_facecolor("white")
    ax.grid(True, color=_GRID, linewidth=0.6)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#adb5bd")
    ax.tick_params(colors=_INK, labelsize=8)
    if xlabel:
        ax.set_xlabel(xlabel, color=_INK, fontsize=8)
    if ylabel:
        ax.set_ylabel(ylabel, color=_INK, fontsize=8)
    if title:
        ax.set_title(title, color=_INK, fontsize=9, fontweight="bold", loc="left")


def run_overview(run: RunSection) -> bytes:
    fig = Figure(figsize=(8.2, 5.2))
    rows = [(ch.VEL, "Velocidade (km/h)", PALETTE[0]), (ch.RPM, "RPM", PALETTE[1]), (ch.ACEL, "Aceleração (m/s²)", PALETTE[2])]
    axes = fig.subplots(3, 1, sharex=True)
    t = run.series[ch.TIME]
    for ax, (cid, label, color) in zip(axes, rows, strict=True):
        x, y = decimate(t, run.series[cid])
        ax.plot(x, y, color=color, linewidth=0.9)
        _style(ax, ylabel=label)
    axes[-1].set_xlabel("Tempo (s)", color=_INK, fontsize=8)
    fig.suptitle(run.name, color=_INK, fontsize=10, fontweight="bold", x=0.01, ha="left")
    fig.tight_layout()
    return _png(fig)


def overlay(model: ReportModel, channel_id: str, ylabel: str, title: str) -> bytes:
    fig = Figure(figsize=(8.2, 3.2))
    ax = fig.subplots()
    for i, r in enumerate(model.runs):
        x, y = decimate(r.series[ch.TIME], r.series[channel_id])
        ax.plot(x, y, color=PALETTE[i % len(PALETTE)], linewidth=0.9, label=r.name)
    _style(ax, "Tempo (s)", ylabel, title)
    if len(model.runs) > 1:
        ax.legend(fontsize=7, frameon=False, ncol=min(4, len(model.runs)))
    fig.tight_layout()
    return _png(fig)


def kpi_bars(model: ReportModel) -> bytes:
    items = [("vel_max", "Vel. máx (km/h)"), ("rpm_max", "RPM máx"), ("acel_max", "Acel. máx (m/s²)"), ("dist_total", "Distância (m)")]
    fig = Figure(figsize=(8.2, 2.9))
    axes = fig.subplots(1, 4)
    names = [r.name for r in model.runs]
    colors = [PALETTE[i % len(PALETTE)] for i in range(len(names))]
    for ax, (mid, label) in zip(axes, items, strict=True):
        vals = [r.stats[mid] for r in model.runs]
        ax.bar(range(len(vals)), vals, color=colors, width=0.7)
        ax.set_xticks(range(len(vals)), [n[:10] for n in names], rotation=35, ha="right")
        _style(ax, title=label)
        ax.grid(False, axis="x")
        for k, v in enumerate(vals):
            ax.text(k, v, f"{v:.0f}" if v >= 100 else f"{v:.1f}", ha="center", va="bottom", fontsize=6.5, color=_INK)
    fig.tight_layout()
    return _png(fig)


def cvt_chart(run: RunSection) -> bytes | None:
    c = run.cvt
    if c is None:
        return None
    fig = Figure(figsize=(8.2, 3.6))
    ax = fig.subplots()
    v, r = run.series[ch.VEL], run.series[ch.RPM]
    step = max(1, v.size // 6000)
    ax.scatter(v[::step], r[::step], s=2, color=PALETTE[0], alpha=0.25, linewidths=0)
    ok = np.isfinite(c.rpm_median)
    ax.fill_between(c.speed_centers_kmh[ok], c.rpm_p10[ok], c.rpm_p90[ok], color=PALETTE[2], alpha=0.22, label="P10–P90")
    ax.plot(c.speed_centers_kmh[ok], c.rpm_median[ok], color=PALETTE[1], linewidth=2, label="RPM mediano")
    _style(ax, "Velocidade (km/h)", "RPM", f"CVT — {run.name}")
    ax.legend(fontsize=7, frameon=False)
    fig.tight_layout()
    return _png(fig)


def phases_chart(model: ReportModel) -> bytes | None:
    runs = [r for r in model.runs if r.phases]
    if not runs:
        return None
    fig = Figure(figsize=(8.2, 0.8 + 0.55 * len(runs)))
    ax = fig.subplots()
    left = np.zeros(len(runs))
    for phase, color in (("aceleração", "#2b8a3e"), ("estabilização", "#f08c00"), ("frenagem", "#c92a2a")):
        vals = np.array([r.phases.get(phase, {}).get("percent_%", 0.0) for r in runs])
        ax.barh(range(len(runs)), vals, left=left, color=color, label=phase, height=0.6)
        left += vals
    ax.set_yticks(range(len(runs)), [r.name for r in runs])
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    _style(ax, "% do tempo", title="Fases de condução")
    ax.grid(False, axis="y")
    ax.legend(fontsize=7, frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.28))
    fig.tight_layout()
    return _png(fig)


def setup_chart(sc: SetupComparison, label: str) -> bytes:
    fig = Figure(figsize=(6.4, 3.2))
    ax = fig.subplots()
    names = list(sc.groups)
    for i, g in enumerate(names):
        vals = np.asarray(sc.groups[g])
        jitter = (np.arange(vals.size) - (vals.size - 1) / 2) * 0.05
        ax.scatter(np.full(vals.size, i) + jitter, vals, color=PALETTE[i % len(PALETTE)], s=28, zorder=3)
        m, s, _ = sc.summary[g]
        ax.errorbar(i, m, yerr=s, color=_INK, capsize=5, linewidth=1.4, zorder=4)
        ax.hlines(m, i - 0.22, i + 0.22, color=_INK, linewidth=2, zorder=4)
    ax.set_xticks(range(len(names)), names)
    ax.set_xlim(-0.6, len(names) - 0.4)
    _style(ax, sc.setup_key, label, f"{label} por {sc.setup_key} (média ± desvio)")
    fig.tight_layout()
    return _png(fig)
