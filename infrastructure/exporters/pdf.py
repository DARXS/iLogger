"""Relatório PDF (reportlab platypus): capa, resumo executivo, comparação, páginas por run, proveniência."""

from __future__ import annotations

import io
import os
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, KeepTogether, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle,
)

from ...application.report_model import ReportModel, provenance_digest
from ...domain import channels as ch
from ...domain.stats import DISPLAY_LABELS
from . import charts

def _register_fonts() -> tuple[str, str, str]:
    """DejaVu Sans (vem com o matplotlib) cobre ≈ Δ σ etc. Fallback: Helvetica."""
    try:
        import matplotlib
        base = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
        for name, f in (("DV", "DejaVuSans.ttf"), ("DV-Bold", "DejaVuSans-Bold.ttf"), ("DV-Mono", "DejaVuSansMono.ttf")):
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, os.path.join(base, f)))
        pdfmetrics.registerFontFamily("DV", normal="DV", bold="DV-Bold", italic="DV", boldItalic="DV-Bold")
        return "DV", "DV-Bold", "DV-Mono"
    except Exception:
        return FONT, FONT_B, FONT_M


FONT, FONT_B, FONT_M = _register_fonts()
ACC, INK, MUT, LINE = colors.HexColor("#0b7285"), colors.HexColor("#212529"), colors.HexColor("#6c757d"), colors.HexColor("#dee2e6")
LEVEL = {"critical": colors.HexColor("#c92a2a"), "warning": colors.HexColor("#e67700"),
         "good": colors.HexColor("#2b8a3e"), "info": ACC}
W = A4[0] - 36 * mm


def _styles() -> dict[str, ParagraphStyle]:
    b = getSampleStyleSheet()["BodyText"]
    return {
        "body": ParagraphStyle("body", parent=b, fontSize=9.5, leading=13, textColor=INK, alignment=TA_LEFT),
        "small": ParagraphStyle("small", parent=b, fontSize=8, leading=10.5, textColor=MUT),
        "h1": ParagraphStyle("h1", fontName=FONT_B, fontSize=24, leading=28, textColor=INK, spaceAfter=4),
        "h2": ParagraphStyle("h2", fontName=FONT_B, fontSize=14, leading=18, textColor=ACC, spaceBefore=10, spaceAfter=6),
        "h3": ParagraphStyle("h3", fontName=FONT_B, fontSize=10.5, leading=14, textColor=INK, spaceBefore=6, spaceAfter=3),
    }


def _img(png: bytes | None, width: float = W) -> Image | None:
    if not png:
        return None
    iw, ih = ImageReader(io.BytesIO(png)).getSize()
    return Image(io.BytesIO(png), width=width, height=width * ih / iw)


def _fmt(v: float) -> str:
    return f"{v:,.0f}".replace(",", " ") if abs(v) >= 1000 else f"{v:.2f}"


def _footer(model: ReportModel):
    sig = provenance_digest(model)

    def draw(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(LINE)
        canvas.line(18 * mm, 14 * mm, A4[0] - 18 * mm, 14 * mm)
        canvas.setFont(FONT, 7.5)
        canvas.setFillColor(MUT)
        canvas.drawString(18 * mm, 9.5 * mm, f"{model.title} · mangue-logger {model.app_version} · assinatura {sig}")
        canvas.drawRightString(A4[0] - 18 * mm, 9.5 * mm, f"Página {doc.page}")
        canvas.restoreState()
    return draw


def _metrics_table(model: ReportModel, st) -> Table:
    head = ["Métrica"] + [r.name for r in model.runs]
    rows = [head]
    for mid, label in DISPLAY_LABELS.items():
        row = [label]
        for i, r in enumerate(model.runs):
            txt = _fmt(r.stats[mid])
            if i > 0 and r.name in model.variations:
                txt += f"  ({model.variations[r.name][mid]:+.1f}%)"
            row.append(txt)
        rows.append(row)
    n = len(model.runs)
    t = Table(rows, colWidths=[W * 0.28] + [W * 0.72 / n] * n, repeatRows=1)
    style = [("FONT", (0, 0), (-1, 0), FONT_B, 8), ("TEXTCOLOR", (0, 0), (-1, 0), MUT),
             ("FONT", (0, 1), (-1, -1), FONT, 8.5), ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
             ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE), ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 4)]
    for ri in range(1, len(rows)):  # colore variações
        for ci in range(2, n + 1):
            txt = rows[ri][ci]
            if "(" in txt:
                d = float(txt.split("(")[1].rstrip("%)"))
                if abs(d) > 1:
                    style.append(("TEXTCOLOR", (ci, ri), (ci, ri), LEVEL["good"] if d > 0 else LEVEL["critical"]))
    t.setStyle(TableStyle(style))
    return t


def _finding(f, st) -> Table:
    p = Paragraph(f"<b>{escape(f.title)}</b><br/>{escape(f.body)}", st["body"])
    t = Table([[p]], colWidths=[W])
    t.setStyle(TableStyle([("LINEBEFORE", (0, 0), (0, 0), 3, LEVEL.get(f.level, ACC)), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                           ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return t


def render_pdf(model: ReportModel, path: str) -> None:
    st = _styles()
    doc = BaseDocTemplate(path, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=20 * mm,
                          title=model.title, author="Mangue Logger")
    doc.addPageTemplates([PageTemplate(id="p", frames=[Frame(18 * mm, 20 * mm, W, A4[1] - 36 * mm, id="f", leftPadding=0,
                                                              rightPadding=0, topPadding=0, bottomPadding=0)], onPage=_footer(model))])
    s: list = []

    # capa / resumo
    s += [Paragraph(escape(model.title), st["h1"]),
          Paragraph(f"{escape(model.generated_at)} · perfil <b>{escape(model.profile_name)}</b><br/>Filtro: {escape(model.filter_description)}", st["small"]),
          Spacer(1, 8), Paragraph("Resumo", st["h2"])]
    s += [Paragraph("• " + escape(p), st["body"]) for p in model.summary_points]
    info = [(k, v) for k, v in model.setup_info.items() if str(v).strip()]
    if info:
        t = Table([["Setup do veículo", ""]] + [[k, str(v)] for k, v in info], colWidths=[W * 0.4, W * 0.6])
        t.setStyle(TableStyle([("FONT", (0, 0), (-1, 0), FONT_B, 8), ("TEXTCOLOR", (0, 0), (-1, 0), MUT),
                               ("FONT", (0, 1), (-1, -1), FONT, 8.5), ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE)]))
        s += [Spacer(1, 8), t]
    if model.observations.strip():
        s += [Spacer(1, 6), Paragraph("Observações", st["h3"]), Paragraph(escape(model.observations).replace("\n", "<br/>"), st["body"])]

    if model.runs:
        s += [Paragraph("Métricas", st["h2"]), _metrics_table(model, st), Spacer(1, 6), _img(charts.kpi_bars(model))]
        s += [_img(charts.overlay(model, ch.VEL, "km/h", "Velocidade"))]
        s += [_img(charts.overlay(model, ch.RPM, "RPM", "RPM"))]
        s += [_img(charts.phases_chart(model))]

    if model.insights:
        s += [PageBreak(), Paragraph("Insights", st["h2"])]
        s += [_finding(f, st) for f in model.insights if f.level != "info"]
        infos = [f for f in model.insights if f.level == "info"]
        if infos:
            s += [Paragraph("Informações complementares", st["h3"])]
            s += [Paragraph(f"• <b>{escape(f.title)}</b> — {escape(f.body)}", st["small"]) for f in infos]

    sc = model.setup_comparison
    if sc:
        s += [PageBreak(), Paragraph(f"Comparação por {escape(sc.setup_key)}", st["h2"])]
        rows = [["Grupo", "n", "Média", "Desvio"]] + [[g, str(n), f"{m:.2f}", f"{sd:.2f}"] for g, (m, sd, n) in sc.summary.items()]
        t = Table(rows, colWidths=[W * 0.4, W * 0.15, W * 0.225, W * 0.225])
        t.setStyle(TableStyle([("FONT", (0, 0), (-1, 0), FONT_B, 8), ("FONT", (0, 1), (-1, -1), FONT, 8.5),
                               ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE)]))
        s += [t, Spacer(1, 6)]
        for g, tr in sc.tests.items():
            if tr is None:
                s.append(Paragraph(f"{escape(sc.baseline or '')} × {escape(g)}: repetições insuficientes (n ≥ 2 por grupo).", st["small"]))
            else:
                v = "significativo" if tr.significant else "não significativo"
                s.append(Paragraph(f"{escape(sc.baseline or '')} × {escape(g)}: Δ = <b>{tr.diff:+.2f}</b> "
                                   f"(IC95% [{tr.ci95[0]:+.2f}, {tr.ci95[1]:+.2f}]), p = {tr.p:.4f}, d = {tr.cohens_d:+.2f} — <b>{v}</b>", st["body"]))
        s += [Spacer(1, 6), _img(charts.setup_chart(sc, DISPLAY_LABELS[sc.metric]), W * 0.8)]

    for r in model.runs:
        block = [PageBreak(), Paragraph(f"Run — {escape(r.name)}", st["h2"])]
        meta = ", ".join(f"{k}={v}" for k, v in r.meta_setup.items())
        block.append(Paragraph(f"{r.n_samples} amostras" + (f" · {escape(meta)}" if meta else "") +
                               (f" · tags: {escape(', '.join(r.tags))}" if r.tags else ""), st["small"]))
        for w in r.quality_warnings:
            block.append(_finding(type("F", (), {"title": "Qualidade dos dados", "body": w, "level": "warning"}), st))
        block += [Spacer(1, 4), _img(charts.run_overview(r)), Spacer(1, 4), _img(charts.cvt_chart(r))]
        s += [b for b in block if b is not None]

    rows = [["Arquivo", "SHA-256"]] + [[r.name, r.sha256] for r in model.runs]
    t = Table(rows, colWidths=[W * 0.3, W * 0.7])
    t.setStyle(TableStyle([("FONT", (0, 0), (-1, 0), FONT_B, 8), ("FONT", (0, 1), (-1, -1), FONT_M, 6.5),
                           ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE)]))
    s += [PageBreak(), KeepTogether([Paragraph("Proveniência", st["h2"]), t])]
    doc.build([x for x in s if x is not None])
