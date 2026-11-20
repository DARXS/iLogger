"""Relatório HTML autocontido (um arquivo; gráficos embutidos; imprime bem)."""

from __future__ import annotations

import base64
from html import escape

from ...application.report_model import ReportModel, provenance_digest
from ...domain import channels as ch
from ...domain.stats import DISPLAY_LABELS
from . import charts

_CSS = """
:root{--bg:#f8f9fa;--card:#fff;--ink:#212529;--mut:#6c757d;--line:#dee2e6;--acc:#0b7285;--crit:#c92a2a;--warn:#e67700;--good:#2b8a3e}
@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--card:#131920;--ink:#e8f1fc;--mut:#8aa0b8;--line:#243347;--acc:#3bc9db;--crit:#ff6b6b;--warn:#ffc078;--good:#69db7c}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,Segoe UI,sans-serif}
main{max-width:1000px;margin:0 auto;padding:28px 20px}h1{margin:0 0 4px;font-size:26px}h2{margin:34px 0 10px;font-size:18px;border-bottom:2px solid var(--acc);padding-bottom:4px}
h3{margin:18px 0 6px;font-size:15px}.mut{color:var(--mut)}.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:10px 0}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:6px 10px;border-bottom:1px solid var(--line);text-align:right}th:first-child,td:first-child{text-align:left}
th{color:var(--mut);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.04em}img{max-width:100%;height:auto;border-radius:6px;background:#fff}
.f{border-left:4px solid var(--mut);padding:8px 12px;margin:6px 0;background:var(--card);border-radius:0 8px 8px 0}.f b{display:block}
.f.critical{border-color:var(--crit)}.f.warning{border-color:var(--warn)}.f.good{border-color:var(--good)}.f.info{border-color:var(--acc)}
.pos{color:var(--good)}.neg{color:var(--crit)}.tag{display:inline-block;padding:1px 8px;border-radius:99px;background:var(--line);font-size:11px;margin-right:4px}
@media print{body{background:#fff}.card{break-inside:avoid}h2{break-after:avoid}}
"""


def _img(png: bytes | None, alt: str) -> str:
    if not png:
        return ""
    return f'<img alt="{escape(alt)}" src="data:image/png;base64,{base64.b64encode(png).decode()}">'


def _fmt(v: float) -> str:
    return f"{v:,.0f}".replace(",", " ") if abs(v) >= 1000 else f"{v:.2f}"


def render_html(m: ReportModel) -> str:
    o: list[str] = [f"<!doctype html><html lang='pt-BR'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                    f"<title>{escape(m.title)}</title><style>{_CSS}</style><main>"]
    o.append(f"<h1>{escape(m.title)}</h1><div class='mut'>{escape(m.generated_at)} · perfil <b>{escape(m.profile_name)}</b> · "
             f"filtro: {escape(m.filter_description)} · mangue-logger {escape(m.app_version)}</div>")

    o.append("<h2>Resumo</h2><div class='card'><ul>" + "".join(f"<li>{escape(p)}</li>" for p in m.summary_points) + "</ul></div>")
    if m.setup_info and any(m.setup_info.values()):
        o.append("<div class='card'><table><tr><th>Setup do veículo</th><th>Valor</th></tr>" +
                 "".join(f"<tr><td>{escape(k)}</td><td>{escape(str(v))}</td></tr>" for k, v in m.setup_info.items() if str(v).strip()) +
                 "</table></div>")
    if m.observations.strip():
        o.append(f"<div class='card'><b>Observações</b><br>{escape(m.observations).replace(chr(10), '<br>')}</div>")

    if m.runs:
        o.append("<h2>Métricas</h2><div class='card' style='overflow-x:auto'><table><tr><th>Métrica</th>" +
                 "".join(f"<th>{escape(r.name)}</th>" for r in m.runs) + "</tr>")
        for mid, label in DISPLAY_LABELS.items():
            cells = []
            for i, r in enumerate(m.runs):
                txt = _fmt(r.stats[mid])
                if i > 0 and r.name in m.variations:
                    d = m.variations[r.name][mid]
                    cls = "pos" if d > 1 else "neg" if d < -1 else "mut"
                    txt += f" <small class='{cls}'>({d:+.1f}%)</small>"
                cells.append(f"<td>{txt}</td>")
            o.append(f"<tr><td>{escape(label)}</td>{''.join(cells)}</tr>")
        o.append("</table></div>")
        o.append(_img(charts.kpi_bars(m), "KPIs"))
        o.append(_img(charts.overlay(m, ch.VEL, "km/h", "Velocidade"), "Velocidade"))
        o.append(_img(charts.overlay(m, ch.RPM, "RPM", "RPM"), "RPM"))
        o.append(_img(charts.phases_chart(m), "Fases"))

    if m.insights:
        o.append("<h2>Insights</h2>")
        for f in (x for x in m.insights if x.level != "info"):
            o.append(f"<div class='f {escape(f.level)}'><b>{escape(f.title)}</b>{escape(f.body)}</div>")
        infos = [x for x in m.insights if x.level == "info"]
        if infos:
            o.append(f"<details class='card'><summary>Informações complementares ({len(infos)})</summary>" +
                     "".join(f"<p><b>{escape(f.title)}</b> — {escape(f.body)}</p>" for f in infos) + "</details>")

    if m.setup_comparison:
        sc = m.setup_comparison
        label = DISPLAY_LABELS[sc.metric]
        o.append(f"<h2>Comparação por {escape(sc.setup_key)}</h2><div class='card'><table><tr><th>Grupo</th><th>n</th><th>Média</th><th>Desvio</th></tr>")
        for g, (mean, sd, n) in sc.summary.items():
            o.append(f"<tr><td>{escape(g)}</td><td>{n}</td><td>{mean:.2f}</td><td>{sd:.2f}</td></tr>")
        o.append("</table>")
        for g, t in sc.tests.items():
            if t is None:
                o.append(f"<p class='mut'>{escape(sc.baseline or '')} × {escape(g)}: repetições insuficientes (n ≥ 2 por grupo).</p>")
            else:
                o.append(f"<p>{escape(sc.baseline or '')} × {escape(g)}: Δ = <b>{t.diff:+.2f}</b> (IC95% [{t.ci95[0]:+.2f}, {t.ci95[1]:+.2f}]), "
                         f"p = {t.p:.4f}, d = {t.cohens_d:+.2f} — <b>{'significativo' if t.significant else 'não significativo'}</b></p>")
        o.append("</div>" + _img(charts.setup_chart(sc, label), "Setups"))

    for r in m.runs:
        o.append(f"<h2>Run — {escape(r.name)}</h2>")
        tags = "".join(f"<span class='tag'>{escape(t)}</span>" for t in r.tags)
        setup = ", ".join(f"{escape(k)}={escape(v)}" for k, v in r.meta_setup.items())
        o.append(f"<div class='mut'>{r.n_samples} amostras {tags}{' · ' + setup if setup else ''}</div>")
        for w in r.quality_warnings:
            o.append(f"<div class='f warning'><b>Qualidade dos dados</b>{escape(w)}</div>")
        o.append(_img(charts.run_overview(r), r.name))
        o.append(_img(charts.cvt_chart(r), "CVT"))

    o.append("<h2>Proveniência</h2><div class='card'><table><tr><th>Arquivo</th><th>SHA-256</th></tr>" +
             "".join(f"<tr><td>{escape(r.name)}</td><td style='font-family:monospace;font-size:11px'>{r.sha256}</td></tr>" for r in m.runs) +
             f"</table><p class='mut'>Assinatura do relatório: {provenance_digest(m)}</p></div></main></html>")
    return "".join(o)
