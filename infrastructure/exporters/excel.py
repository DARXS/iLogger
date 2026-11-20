"""Relatório Excel (xlsxwriter) com gráficos nativos, formatação condicional e proveniência."""

from __future__ import annotations

import re

import numpy as np
import xlsxwriter

from ...application.report_model import ReportModel, provenance_digest
from ...domain import channels as ch
from ...domain.stats import DISPLAY_LABELS
from .charts import decimate

MAX_ROWS = 20000
_LEVEL_COLOR = {"critical": "#C92A2A", "warning": "#E67700", "good": "#2B8A3E", "info": "#0B7285"}


def _sheet_name(name: str, used: set[str]) -> str:
    base = re.sub(r"[\[\]:*?/\\]", "_", name)[:28] or "Run"
    cand, i = base, 2
    while cand.lower() in used:
        cand = f"{base[:25]}_{i}"
        i += 1
    used.add(cand.lower())
    return cand


def render_excel(m: ReportModel, path: str) -> None:
    wb = xlsxwriter.Workbook(path, {"nan_inf_to_errors": True})
    wb.set_properties({"title": m.title, "author": "Mangue Logger", "comments": f"assinatura {provenance_digest(m)}"})
    F = {
        "title": wb.add_format({"bold": True, "font_size": 16, "font_color": "#0B7285"}),
        "h": wb.add_format({"bold": True, "bg_color": "#0B7285", "font_color": "white", "border": 1, "align": "center", "valign": "vcenter"}),
        "lbl": wb.add_format({"bold": True, "bg_color": "#F1F3F5", "border": 1}),
        "num": wb.add_format({"num_format": "#,##0.00", "border": 1}),
        "int": wb.add_format({"num_format": "#,##0", "border": 1}),
        "pct": wb.add_format({"num_format": '+0.0"%";-0.0"%";0.0"%"', "border": 1}),
        "txt": wb.add_format({"border": 1, "text_wrap": True, "valign": "top"}),
        "mut": wb.add_format({"font_color": "#6C757D", "italic": True}),
        "mono": wb.add_format({"font_name": "Consolas", "font_size": 8, "border": 1}),
    }
    used: set[str] = set()

    # ── Resumo ────────────────────────────────────────────────────────────────
    ws = wb.add_worksheet(_sheet_name("Resumo", used))
    ws.hide_gridlines(2)
    ws.set_column(0, 0, 30)
    ws.set_column(1, 12, 16)
    ws.write(0, 0, m.title, F["title"])
    ws.write(1, 0, f"{m.generated_at} · perfil {m.profile_name} · filtro: {m.filter_description}", F["mut"])
    r0 = 3
    for p in m.summary_points:
        ws.write(r0, 0, "• " + p)
        r0 += 1
    r0 += 1
    ws.write(r0, 0, "Métrica", F["h"])
    for j, r in enumerate(m.runs):
        ws.write(r0, 1 + j, r.name, F["h"])
    first_metric_row = r0 + 1
    for i, (mid, label) in enumerate(DISPLAY_LABELS.items()):
        ws.write(first_metric_row + i, 0, label, F["lbl"])
        for j, r in enumerate(m.runs):
            ws.write_number(first_metric_row + i, 1 + j, r.stats[mid], F["num"])
    if len(m.runs) > 1:
        vr = first_metric_row + len(DISPLAY_LABELS) + 2
        ws.write(vr - 1, 0, "Variação vs. base (%)", F["lbl"])
        for i, (mid, label) in enumerate(DISPLAY_LABELS.items()):
            ws.write(vr + i, 0, label, F["lbl"])
            for j, r in enumerate(m.runs[1:], start=1):
                ws.write_number(vr + i, j, m.variations[r.name][mid], F["pct"])
        rng = (vr, 2, vr + len(DISPLAY_LABELS) - 1, len(m.runs))
        ws.conditional_format(*rng, {"type": "cell", "criteria": ">", "value": 1, "format": wb.add_format({"font_color": "#2B8A3E"})})
        ws.conditional_format(*rng, {"type": "cell", "criteria": "<", "value": -1, "format": wb.add_format({"font_color": "#C92A2A"})})
    if m.runs:
        for k, (mid, title, anchor) in enumerate((("vel_max", "Velocidade máxima (km/h)", "H3"), ("rpm_max", "RPM máximo", "H19"))):
            row = first_metric_row + list(DISPLAY_LABELS).index(mid)
            c = wb.add_chart({"type": "column"})
            c.add_series({"name": title, "categories": [ws.name, r0, 1, r0, len(m.runs)], "values": [ws.name, row, 1, row, len(m.runs)],
                          "fill": {"color": "#0B7285"}, "data_labels": {"value": True, "num_format": "0.0"}})
            c.set_title({"name": title, "name_font": {"size": 11}})
            c.set_legend({"none": True})
            c.set_size({"width": 520, "height": 300})
            ws.insert_chart(anchor, c)
    if m.observations.strip():
        end = first_metric_row + len(DISPLAY_LABELS) * (2 if len(m.runs) > 1 else 1) + 4
        ws.write(end, 0, "Observações", F["lbl"])
        ws.merge_range(end + 1, 0, end + 4, 6, m.observations, F["txt"])

    # ── Insights ──────────────────────────────────────────────────────────────
    wi = wb.add_worksheet(_sheet_name("Insights", used))
    wi.set_column(0, 0, 11)
    wi.set_column(1, 1, 38)
    wi.set_column(2, 2, 95)
    for j, h in enumerate(("Nível", "Título", "Detalhe")):
        wi.write(0, j, h, F["h"])
    for i, f in enumerate(m.insights, start=1):
        lv = wb.add_format({"bold": True, "font_color": "white", "bg_color": _LEVEL_COLOR.get(f.level, "#0B7285"), "border": 1, "align": "center"})
        wi.write(i, 0, f.level, lv)
        wi.write(i, 1, f.title, F["txt"])
        wi.write(i, 2, f.body, F["txt"])
    wi.freeze_panes(1, 0)
    wi.autofilter(0, 0, max(1, len(m.insights)), 2)

    # ── Fases ─────────────────────────────────────────────────────────────────
    wp = wb.add_worksheet(_sheet_name("Fases", used))
    wp.set_column(0, 0, 30)
    wp.set_column(1, 8, 14)
    heads = ["Run", "Aceleração %", "Estabilização %", "Frenagem %", "Eventos acel.", "Eventos fren."]
    for j, h in enumerate(heads):
        wp.write(0, j, h, F["h"])
    runs_ph = [r for r in m.runs if r.phases]
    for i, r in enumerate(runs_ph, start=1):
        wp.write(i, 0, r.name, F["lbl"])
        wp.write_number(i, 1, r.phases["aceleração"]["percent_%"], F["num"])
        wp.write_number(i, 2, r.phases["estabilização"]["percent_%"], F["num"])
        wp.write_number(i, 3, r.phases["frenagem"]["percent_%"], F["num"])
        wp.write_number(i, 4, r.phases["aceleração"]["n_eventos"], F["int"])
        wp.write_number(i, 5, r.phases["frenagem"]["n_eventos"], F["int"])
    if runs_ph:
        c = wb.add_chart({"type": "bar", "subtype": "percent_stacked"})
        for j, color in ((1, "#2B8A3E"), (2, "#F08C00"), (3, "#C92A2A")):
            c.add_series({"name": [wp.name, 0, j], "categories": [wp.name, 1, 0, len(runs_ph), 0],
                          "values": [wp.name, 1, j, len(runs_ph), j], "fill": {"color": color}})
        c.set_title({"name": "Fases de condução"})
        c.set_size({"width": 620, "height": 280})
        wp.insert_chart("H2", c)

    # ── CVT ───────────────────────────────────────────────────────────────────
    wc = wb.add_worksheet(_sheet_name("CVT", used))
    wc.set_column(0, 0, 30)
    wc.set_column(1, 12, 15)
    for j, h in enumerate(("Run", "RPM de saída", "RPM sustentado", "CV sustentado %")):
        wc.write(0, j, h, F["h"])
    cvt_runs = [r for r in m.runs if r.cvt]
    for i, r in enumerate(cvt_runs, start=1):
        wc.write(i, 0, r.name, F["lbl"])
        for j, v in enumerate((r.cvt.launch_rpm, r.cvt.hold_rpm, r.cvt.hold_cv_pct), start=1):  # type: ignore[union-attr]
            (wc.write_number if v is not None else wc.write_blank)(i, j, v if v is not None else None, F["num"])
    if cvt_runs:
        base_row = len(cvt_runs) + 3
        chart = wb.add_chart({"type": "scatter", "subtype": "straight"})
        col = 0
        for k, r in enumerate(cvt_runs):
            cv = r.cvt
            ok = np.isfinite(cv.rpm_median)  # type: ignore[union-attr]
            xs, ys = cv.speed_centers_kmh[ok], cv.rpm_median[ok]  # type: ignore[union-attr]
            wc.write(base_row, col, f"{r.name} — km/h", F["h"])
            wc.write(base_row, col + 1, "RPM mediano", F["h"])
            for i, (x, y) in enumerate(zip(xs, ys, strict=True), start=1):
                wc.write_number(base_row + i, col, float(x), F["num"])
                wc.write_number(base_row + i, col + 1, float(y), F["num"])
            chart.add_series({"name": r.name, "categories": [wc.name, base_row + 1, col, base_row + len(xs), col],
                              "values": [wc.name, base_row + 1, col + 1, base_row + len(xs), col + 1]})
            col += 3
        chart.set_title({"name": "CVT — RPM mediano × velocidade"})
        chart.set_x_axis({"name": "km/h"})
        chart.set_y_axis({"name": "RPM"})
        chart.set_size({"width": 700, "height": 340})
        wc.insert_chart("F2", chart)

    # ── Qualidade ─────────────────────────────────────────────────────────────
    wq = wb.add_worksheet(_sheet_name("Qualidade", used))
    wq.set_column(0, 0, 30)
    wq.set_column(1, 1, 14)
    wq.set_column(2, 2, 110)
    for j, h in enumerate(("Run", "Amostras", "Avisos")):
        wq.write(0, j, h, F["h"])
    for i, r in enumerate(m.runs, start=1):
        wq.write(i, 0, r.name, F["lbl"])
        wq.write_number(i, 1, r.n_samples, F["int"])
        wq.write(i, 2, "; ".join(r.quality_warnings) or "OK", F["txt"])

    # ── Setups ────────────────────────────────────────────────────────────────
    sc = m.setup_comparison
    if sc:
        wsu = wb.add_worksheet(_sheet_name("Setups", used))
        wsu.set_column(0, 0, 26)
        wsu.set_column(1, 8, 14)
        for j, h in enumerate((sc.setup_key, "n", "Média", "Desvio", "Δ vs base", "IC95% inf", "IC95% sup", "p", "Cohen d")):
            wsu.write(0, j, h, F["h"])
        for i, (g, (mean, sd, n)) in enumerate(sc.summary.items(), start=1):
            wsu.write(i, 0, g, F["lbl"])
            wsu.write_number(i, 1, n, F["int"])
            wsu.write_number(i, 2, mean, F["num"])
            wsu.write_number(i, 3, sd, F["num"])
            t = sc.tests.get(g)
            if t is not None:
                for j, v in enumerate((t.diff, t.ci95[0], t.ci95[1], t.p, t.cohens_d), start=4):
                    wsu.write_number(i, j, v, F["num"])
        c = wb.add_chart({"type": "column"})
        c.add_series({"name": DISPLAY_LABELS[sc.metric], "categories": [wsu.name, 1, 0, len(sc.summary), 0],
                      "values": [wsu.name, 1, 2, len(sc.summary), 2], "fill": {"color": "#0B7285"},
                      "y_error_bars": {"type": "custom", "plus_values": [wsu.name, 1, 3, len(sc.summary), 3],
                                       "minus_values": [wsu.name, 1, 3, len(sc.summary), 3]}})
        c.set_title({"name": f"{DISPLAY_LABELS[sc.metric]} por {sc.setup_key} (média ± desvio)"})
        c.set_legend({"none": True})
        wsu.insert_chart("A12", c)

    # ── uma aba por run (dados + gráficos nativos) ────────────────────────────
    for r in m.runs:
        wr = wb.add_worksheet(_sheet_name(r.name, used))
        t = r.series[ch.TIME]
        cols = [(ch.TIME, "Tempo (s)"), (ch.VEL, "Velocidade (km/h)"), (ch.RPM, "RPM"), (ch.ACEL, "Aceleração (m/s²)"), (ch.DIST, "Distância (m)")]
        data = {}
        for cid, label in cols:
            if t.size > MAX_ROWS:
                _, y = decimate(t, r.series[cid], MAX_ROWS)
            else:
                y = r.series[cid]
            data[cid] = y
        n = data[ch.VEL].size
        if t.size > MAX_ROWS:
            data[ch.TIME] = decimate(t, r.series[ch.VEL], MAX_ROWS)[0]
            n = data[ch.TIME].size
            for cid, _ in cols[1:]:  # alinha todos nos mesmos índices decimados
                idx = np.searchsorted(t, data[ch.TIME])
                data[cid] = r.series[cid][np.clip(idx, 0, t.size - 1)]
        for j, (_, label) in enumerate(cols):
            wr.write(0, j, label, F["h"])
        wr.set_column(0, 4, 18)
        for j, (cid, _) in enumerate(cols):
            wr.write_column(1, j, np.round(data[cid][:n], 4).tolist())
        wr.freeze_panes(1, 0)
        for k, (cid_col, title, anchor, color) in enumerate(((1, "Velocidade (km/h)", "G2", "#0B7285"), (2, "RPM", "G18", "#E8590C"))):
            c = wb.add_chart({"type": "scatter", "subtype": "straight"})
            c.add_series({"name": title, "categories": [wr.name, 1, 0, n, 0], "values": [wr.name, 1, cid_col, n, cid_col],
                          "line": {"color": color, "width": 1.25}})
            c.set_title({"name": f"{r.name} — {title}", "name_font": {"size": 10}})
            c.set_x_axis({"name": "s"})
            c.set_legend({"none": True})
            c.set_size({"width": 760, "height": 300})
            wr.insert_chart(anchor, c)

    # ── Proveniência ──────────────────────────────────────────────────────────
    wv = wb.add_worksheet(_sheet_name("Proveniência", used))
    wv.set_column(0, 0, 30)
    wv.set_column(1, 1, 80)
    for i, (k, v) in enumerate([("Gerado em", m.generated_at), ("Versão", m.app_version), ("Perfil", m.profile_name),
                                ("Filtro", m.filter_description), ("Assinatura", provenance_digest(m))]):
        wv.write(i, 0, k, F["lbl"])
        wv.write(i, 1, v, F["txt"])
    base = 7
    wv.write(base, 0, "Arquivo", F["h"])
    wv.write(base, 1, "SHA-256", F["h"])
    for i, r in enumerate(m.runs, start=1):
        wv.write(base + i, 0, r.name, F["lbl"])
        wv.write(base + i, 1, r.sha256, F["mono"])
    wb.close()
