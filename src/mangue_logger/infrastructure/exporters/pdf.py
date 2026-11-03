"""Relatório PDF (reportlab + matplotlib). Sem Qt."""

from __future__ import annotations

import json
import logging
from datetime import datetime

import numpy as np
import pandas as pd

from ...domain.channels import (
    KEY_ACEL_MS2_FILT, KEY_DIST_M, KEY_RPM_FILT, KEY_RPM_RAW, KEY_TEMPO_S,
    KEY_VEL_KMH_FILT, KEY_VEL_KMH_RAW,
)
from ...domain.channels import DEFAULT_CHANNELS

CHANNEL_UNITS = {c.label: c.unit for c in DEFAULT_CHANNELS}
from .charts import (  # noqa: F401
    _make_figure, _make_histogram_figure, _make_phase_bar_figure, _make_scatter_figure,
)

log = logging.getLogger(__name__)


def generate_pdf(save_path: str, setup_info: dict, observations: str,
                 filter_settings: dict, metrics_df: pd.DataFrame,
                 variations_df: pd.DataFrame, figures: dict,
                 runs=None):
    try:
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
            Image, Table, TableStyle, PageBreak)
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.units import cm
        from reportlab.lib import colors

        doc   = SimpleDocTemplate(save_path, rightMargin=2*cm, leftMargin=2*cm,
                                  topMargin=3*cm, bottomMargin=3*cm)
        story = []
        sty   = getSampleStyleSheet()
        s_ttl = ParagraphStyle('T', fontSize=22, alignment=TA_CENTER,
                               spaceAfter=cm, fontName='Helvetica-Bold')
        s_h1  = ParagraphStyle('H1', fontSize=16, leading=20, spaceBefore=14,
                               spaceAfter=10, fontName='Helvetica-Bold')
        s_h2  = ParagraphStyle('H2', fontSize=12, leading=16, spaceBefore=10,
                               spaceAfter=6, textColor=colors.darkblue,
                               fontName='Helvetica-Bold')
        s_b   = ParagraphStyle('B', fontSize=10, leading=14, spaceAfter=6)
        s_inf = ParagraphStyle('I', fontSize=10, leading=14,
                               leftIndent=cm, spaceBefore=5)
        s_cap = ParagraphStyle('C', fontSize=8, leading=12, spaceAfter=4,
                               textColor=colors.gray, alignment=TA_CENTER)

        def _df_table(df, bg=colors.lightblue, round_n=2):
            hdr = [Paragraph(f'<b>{c}</b>', s_b) for c in [''] + list(df.columns)]
            rows = [hdr]
            for idx, row_data in df.iterrows():
                row_cells = [Paragraph(f'<b>{idx}</b>', s_b)]
                for v in row_data.values:
                    row_cells.append(Paragraph(
                        str(round(v, round_n)) if isinstance(v, float) else str(v), s_b))
                rows.append(row_cells)
            t = Table(rows, hAlign='LEFT', repeatRows=1)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), bg),
                ('ALIGN',      (0, 0), (-1,-1), 'CENTER'),
                ('GRID',       (0, 0), (-1,-1), 0.5, colors.grey),
                ('FONTSIZE',   (0, 0), (-1,-1), 8),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f8fc')]),
            ]))
            return t

        def _img(img_bytes, w=16*cm, h=9*cm):
            if img_bytes is None:
                return None
            import io
            return Image(io.BytesIO(img_bytes), width=w, height=h, kind='proportional')

        # ── Capa ─────────────────────────────────────────────────────────────
        story += [Spacer(1, 4*cm), Paragraph("Relatório de Telemetria", s_ttl),
                  Paragraph("Mangue Logger v6", ParagraphStyle('sub', fontSize=12,
                  alignment=TA_CENTER, textColor=colors.gray)),
                  Spacer(1, cm),
                  Paragraph(datetime.now().strftime('%d/%m/%Y  %H:%M'), s_b)]
        if setup_info:
            rows = [[Paragraph(f"<b>{k}</b>", s_b), Paragraph(str(v), s_b)]
                    for k, v in setup_info.items() if v]
            if rows:
                t = Table(rows, colWidths=[5*cm, 10*cm])
                t.setStyle(TableStyle([('ALIGN',(0,0),(-1,-1),'LEFT'),
                                       ('VALIGN',(0,0),(-1,-1),'TOP'),
                                       ('ROWBACKGROUNDS',(0,0),(-1,-1),
                                        [colors.white, colors.HexColor('#f0f4f8')])]))
                story.append(t)
        story.append(PageBreak())

        # ── Filtros e Configuração ────────────────────────────────────────────
        story.append(Paragraph('1. Configurações de Filtro', s_h1))
        ft = filter_settings.get('type', 'N/A').replace('_', ' ').title()
        story.append(Paragraph(f"<b>Tipo:</b> {ft}", s_inf))
        for k, v in filter_settings.items():
            if k != 'type':
                story.append(Paragraph(f"<b>{k.replace('_',' ').title()}:</b> {v}", s_inf))
        if observations and observations.strip():
            story.append(Paragraph("Observações", s_h2))
            story.append(Paragraph(observations.replace('\n', '<br/>'), s_b))
        story.append(PageBreak())

        # ── Estatísticas ─────────────────────────────────────────────────────
        story.append(Paragraph('2. Análise Estatística', s_h1))
        story.append(Paragraph("Métricas Principais", s_h2))
        story.append(_df_table(metrics_df, colors.HexColor('#ddeeff')))
        story.append(Spacer(1, 0.5*cm))
        if not variations_df.empty:
            story.append(Paragraph("Variações Percentuais vs. Base (%)", s_h2))
            story.append(_df_table(variations_df, colors.HexColor('#ddffdd')))
        story.append(PageBreak())

        # ── Gráficos matplotlib (gerados aqui se runs disponíveis) ───────────
        story.append(Paragraph('3. Análise Gráfica Comparativa', s_h1))

        COLORS = ["#00e5ff","#ff6b2b","#00ff94","#ff2d7a","#aa44ff","#ffcc00"]
        mpl_colors = COLORS[:len(runs)] if runs else []

        if runs:
            chart_specs = [
                (KEY_TEMPO_S, KEY_VEL_KMH_FILT, 'Velocidade × Tempo', 'Tempo (s)', 'Velocidade (km/h)'),
                (KEY_TEMPO_S, KEY_RPM_FILT,      'RPM × Tempo',        'Tempo (s)', 'RPM'),
                (KEY_TEMPO_S, KEY_ACEL_MS2_FILT, 'Aceleração × Tempo', 'Tempo (s)', 'Aceleração (m/s²)'),
                (KEY_TEMPO_S, KEY_DIST_M,        'Distância × Tempo',  'Tempo (s)', 'Distância (m)'),
            ]
            for kx, ky, title, xl, yl in chart_specs:
                img_bytes = _make_figure(runs, kx, ky, title, xl, yl, mpl_colors)
                if img_bytes:
                    story.append(Paragraph(title, s_h2))
                    story.append(_img(img_bytes))
                    story.append(Paragraph(f"Figura: {title}", s_cap))
                    story.append(Spacer(1, 0.3*cm))

            # Scatter
            story.append(PageBreak())
            story.append(Paragraph('4. Diagramas de Dispersão', s_h1))
            scatter_specs = [
                (KEY_VEL_KMH_FILT, KEY_RPM_FILT,      'RPM × Velocidade',          'Velocidade (km/h)', 'RPM'),
                (KEY_VEL_KMH_FILT, KEY_ACEL_MS2_FILT, 'Aceleração × Velocidade',   'Velocidade (km/h)', 'Aceleração (m/s²)'),
                (KEY_RPM_FILT,     KEY_ACEL_MS2_FILT, 'Aceleração × RPM',          'RPM', 'Aceleração (m/s²)'),
            ]
            for kx, ky, title, xl, yl in scatter_specs:
                img_bytes = _make_scatter_figure(runs, kx, ky, title, xl, yl, mpl_colors)
                if img_bytes:
                    story.append(Paragraph(title, s_h2))
                    story.append(_img(img_bytes))
                    story.append(Paragraph(f"Dispersão: {title}", s_cap))
                    story.append(Spacer(1, 0.3*cm))

            # Histogramas
            story.append(PageBreak())
            story.append(Paragraph('5. Distribuições de Frequência', s_h1))
            for key, title in [(KEY_VEL_KMH_FILT, 'Histograma de Velocidade'),
                               (KEY_RPM_FILT,      'Histograma de RPM'),
                               (KEY_ACEL_MS2_FILT, 'Histograma de Aceleração')]:
                img_bytes = _make_histogram_figure(runs, key, title,
                                                   CHANNEL_UNITS.get(key,''), mpl_colors)
                if img_bytes:
                    story.append(Paragraph(title, s_h2))
                    story.append(_img(img_bytes))
                    story.append(Spacer(1, 0.3*cm))

            # Fases
            story.append(PageBreak())
            story.append(Paragraph('6. Análise de Fases de Condução', s_h1))
            from ...application.analysis import compute_phase_summary_all
            phase_data = compute_phase_summary_all(runs, filter_settings)
            img_bytes = _make_phase_bar_figure(phase_data)
            if img_bytes:
                story.append(Paragraph('Distribuição de Tempo por Fase', s_h2))
                story.append(_img(img_bytes, w=14*cm, h=8*cm))
                story.append(Spacer(1, 0.5*cm))
            for r in runs:
                df_ph = r.detect_phases()
                if not df_ph.empty:
                    story.append(Paragraph(f"Fases — {r.file_name}", s_h2))
                    ph_rows = [[Paragraph(f'<b>{c}</b>', s_b) for c in df_ph.columns]]
                    for _, row_data in df_ph.iterrows():
                        ph_rows.append([Paragraph(str(v), s_b) for v in row_data.values])
                    ph_t = Table(ph_rows, hAlign='LEFT', repeatRows=1)
                    ph_t.setStyle(TableStyle([
                        ('BACKGROUND', (0,0),(-1,0), colors.HexColor('#ccecff')),
                        ('GRID',       (0,0),(-1,-1), 0.5, colors.grey),
                        ('FONTSIZE',   (0,0),(-1,-1), 7),
                        ('ROWBACKGROUNDS', (0,1),(-1,-1),
                         [colors.white, colors.HexColor('#f8fcff')]),
                    ]))
                    story.append(ph_t)
                    story.append(Spacer(1, 0.4*cm))

        # Gráficos da janela (capturas de tela)
        if figures:
            story.append(PageBreak())
            story.append(Paragraph('7. Capturas da Interface', s_h1))
            for pk, img_bytes in figures.items():
                if img_bytes:
                    story.append(Paragraph(pk.replace('_', ' ').capitalize(), s_h2))
                    story.append(_img(img_bytes))
                    story.append(Spacer(1, 0.5*cm))

        doc.build(story)
    except Exception:
        log.exception("falha na exportação")
        raise


