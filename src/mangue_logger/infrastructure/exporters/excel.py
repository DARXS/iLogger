"""Exportação Excel (dashboard, estatísticas, fases, correlações). Sem Qt."""

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


log = logging.getLogger(__name__)


def _chart_line(wb, sheet, run_names, rows_per_run, time_col, val_col, title, y_title):
    chart = wb.add_chart({'type': 'line'})
    offset = 2
    for i, name in enumerate(run_names):
        end = offset + rows_per_run[i] - 1
        chart.add_series({'name': name,
                          'categories': f"='{sheet}'!${time_col}${offset}:${time_col}${end}",
                          'values':     f"='{sheet}'!${val_col}${offset}:${val_col}${end}",
                          'line': {'width': 1.25}})
        offset += rows_per_run[i]
    chart.set_title({'name': title})
    chart.set_x_axis({'name': 'Tempo (s)'})
    chart.set_y_axis({'name': y_title, 'major_gridlines': {'visible': False}})
    chart.set_legend({'position': 'top'})
    chart.set_size({'width': 720, 'height': 420})
    return chart


def _chart_scatter(wb, sheet, run_names, rows_per_run, x_col, y_col, title, x_t, y_t):
    chart = wb.add_chart({'type': 'scatter'})
    offset = 2
    for i, name in enumerate(run_names):
        end = offset + rows_per_run[i] - 1
        chart.add_series({'name': name,
                          'categories': f"='{sheet}'!${x_col}${offset}:${x_col}${end}",
                          'values':     f"='{sheet}'!${y_col}${offset}:${y_col}${end}",
                          'marker': {'type': 'circle', 'size': 3},
                          'line':   {'none': True}})
        offset += rows_per_run[i]
    chart.set_title({'name': title})
    chart.set_x_axis({'name': x_t})
    chart.set_y_axis({'name': y_t})
    chart.set_legend({'position': 'top'})
    chart.set_size({'width': 720, 'height': 420})
    return chart


def export_excel(runs, save_path: str, metrics_df: pd.DataFrame,
                 variations_df: pd.DataFrame, filter_settings: dict,
                 setup_info: dict, observations: str):
    try:
        from ...application.analysis import compute_correlation_matrix, compute_phase_summary_all

        SERIES = ["#00e5ff","#ff6b2b","#00ff94","#ff2d7a","#aa44ff",
                  "#ffcc00","#44ffbb","#ff5533"]

        tidy_list, rows_per_run, names = [], [], [r.file_name for r in runs]
        for r in runs:
            r.apply_filters_and_recalculate(filter_settings)
            df = r.as_dataframe()[[KEY_TEMPO_S, KEY_VEL_KMH_FILT, KEY_RPM_FILT,
                                   KEY_ACEL_MS2_FILT, KEY_DIST_M]].rename(columns={
                KEY_TEMPO_S: 'Tempo (s)', KEY_VEL_KMH_FILT: 'Velocidade (km/h)',
                KEY_RPM_FILT: 'RPM', KEY_ACEL_MS2_FILT: 'Aceleração (m/s²)',
                KEY_DIST_M: 'Distância (m)'})
            tidy_list.append(df); rows_per_run.append(len(df))
        tidy = pd.concat(tidy_list, keys=names, names=['Run','Index']).reset_index(level='Run')

        with pd.ExcelWriter(save_path, engine='xlsxwriter') as writer:
            wb = writer.book

            # ── Formatos ──────────────────────────────────────────────────────
            bold   = wb.add_format({'bold': True})
            title  = wb.add_format({'bold': True, 'font_size': 14,
                                    'bottom': 1, 'font_color': '#333'})
            hdr    = wb.add_format({'bold': True, 'bg_color': '#DDEBF7',
                                    'border': 1, 'font_color': '#002060'})
            num_fmt = wb.add_format({'num_format': '0.00'})
            pct_fmt = wb.add_format({'num_format': '0.00"%"'})
            red_fmt = wb.add_format({'bg_color': '#FFCCCC', 'num_format': '0.00'})
            grn_fmt = wb.add_format({'bg_color': '#CCFFCC', 'num_format': '0.00'})
            sub_hdr = wb.add_format({'bold': True, 'bg_color': '#F2F2F2',
                                     'border': 1, 'font_color': '#444'})

            # ── Sheet 1: Setup e Métricas ─────────────────────────────────────
            sh1 = wb.add_worksheet('Setup e Métricas')
            sh1.set_column('A:A', 28); sh1.set_column('B:Z', 16)
            sh1.write('A1', 'Setup do Veículo', title)
            row = 2
            for k, v in (setup_info or {}).items():
                sh1.write_string(row, 0, k, bold)
                sh1.write_string(row, 1, str(v)); row += 1
            row += 2
            sh1.write(row, 0, 'Métricas Principais', title)
            metrics_df.to_excel(writer, sheet_name='Setup e Métricas', startrow=row + 1)
            # Conditional formatting for metrics
            n_rows = len(metrics_df); n_cols = len(metrics_df.columns)
            sh1.conditional_format(row+2, 1, row+1+n_rows, n_cols,
                {'type': '3_color_scale',
                 'min_color': '#FF6666', 'mid_color': '#FFFF66', 'max_color': '#66FF66'})

            row2 = row + len(metrics_df) + 5
            sh1.write(row2, 0, 'Variações vs. Base (%)', title)
            if not variations_df.empty:
                variations_df.to_excel(writer, sheet_name='Setup e Métricas', startrow=row2+1)
                nv = len(variations_df); nc = len(variations_df.columns)
                sh1.conditional_format(row2+2, 1, row2+1+nv, nc,
                    {'type': '3_color_scale',
                     'min_color': '#FF6666', 'mid_color': '#FFFFFF', 'max_color': '#66FF66'})

            if observations and observations.strip():
                row3 = row2 + len(variations_df) + 5 if not variations_df.empty else row2 + 3
                sh1.write(row3, 0, 'Observações', bold)
                sh1.write(row3+1, 0, observations)

            # ── Sheet 2: Dashboard ────────────────────────────────────────────
            sh2 = wb.add_worksheet('Dashboard')

            tidy.to_excel(writer, sheet_name='Dados', index=False)
            for r in runs:
                sn = f"RAW_{r.file_name.replace('.csv','')[:22]}"
                r.as_dataframe().to_excel(writer, sheet_name=sn, index=False)

            ds = 'Dados'
            charts = {
                'vel':     _chart_line(wb, ds, names, rows_per_run, 'B','C','Velocidade Comparativa','Velocidade (km/h)'),
                'rpm':     _chart_line(wb, ds, names, rows_per_run, 'B','D','RPM Comparativo','RPM'),
                'acel':    _chart_line(wb, ds, names, rows_per_run, 'B','E','Aceleração Comparativa','Aceleração (m/s²)'),
                'dist':    _chart_line(wb, ds, names, rows_per_run, 'B','F','Distância Percorrida','Distância (m)'),
                'rpm_vel': _chart_scatter(wb, ds, names, rows_per_run,'C','D','RPM × Velocidade','Velocidade (km/h)','RPM'),
                'acel_vel':_chart_scatter(wb, ds, names, rows_per_run,'C','E','Aceleração × Velocidade','Velocidade (km/h)','Aceleração (m/s²)'),
            }
            big_title_fmt = wb.add_format({'bold':True,'font_size':20,'font_color':'#002060'})
            sh2.write('A1', 'Dashboard de Análise', big_title_fmt)
            sh2.write('A2', f'Gerado em: {datetime.now().strftime("%d/%m/%Y %H:%M")}',
                      wb.add_format({'font_color':'#888888','italic':True}))
            sh2.insert_chart('B4',  charts['vel'])
            sh2.insert_chart('L4',  charts['rpm'])
            sh2.insert_chart('B25', charts['acel'])
            sh2.insert_chart('L25', charts['dist'])
            sh2.insert_chart('B46', charts['rpm_vel'])
            sh2.insert_chart('L46', charts['acel_vel'])

            # ── Sheet 3: Estatísticas Estendidas ──────────────────────────────
            sh3 = wb.add_worksheet('Estatísticas Estendidas')
            sh3.set_column('A:A', 30); sh3.set_column('B:Z', 14)
            sh3.write('A1', 'Estatísticas Estendidas por Canal', title)
            ext_row = 2
            keys_ext = [KEY_VEL_KMH_FILT, KEY_RPM_FILT, KEY_ACEL_MS2_FILT, KEY_DIST_M]
            stat_names = ['n', 'min', 'max', 'amplitude', 'mean', 'std',
                          'cv_%', 'rms', 'skewness', 'kurtosis',
                          'p5', 'p10', 'p25', 'p50', 'p75', 'p90', 'p95', 'iqr']
            for key in keys_ext:
                unit = CHANNEL_UNITS.get(key, '')
                sh3.write(ext_row, 0, f'{key} [{unit}]', bold)
                ext_row += 1
                # Header
                sh3.write(ext_row, 0, 'Estatística', hdr)
                for ci, rn in enumerate(names):
                    sh3.write(ext_row, ci+1, rn, hdr)
                ext_row += 1
                for sn in stat_names:
                    sh3.write(ext_row, 0, sn)
                    for ci, r in enumerate(runs):
                        es = r.compute_extended_stats(key)
                        sh3.write(ext_row, ci+1, round(es.get(sn, 0), 4), num_fmt)
                    ext_row += 1
                ext_row += 1

            # ── Sheet 4: Fases ────────────────────────────────────────────────
            sh4 = wb.add_worksheet('Fases de Condução')
            sh4.set_column('A:A', 20); sh4.set_column('B:M', 14)
            sh4.write('A1', 'Análise de Fases — Aceleração / Frenagem / Estabilização', title)
            phase_row = 2

            phase_colors = {
                'aceleração':    wb.add_format({'bg_color': '#CCFFCC', 'bold': True}),
                'frenagem':      wb.add_format({'bg_color': '#FFCCCC', 'bold': True}),
                'estabilização': wb.add_format({'bg_color': '#FFFFCC', 'bold': True}),
            }
            phase_sum = compute_phase_summary_all(runs, filter_settings)
            for rn, summ in phase_sum.items():
                sh4.write(phase_row, 0, f'RUN: {rn}', bold)
                phase_row += 1
                sh4.write(phase_row, 0, 'Fase', hdr)
                for ci, col in enumerate(['Duração (s)', 'Tempo (%)', 'Eventos']):
                    sh4.write(phase_row, ci+1, col, hdr)
                phase_row += 1
                for ph in ['aceleração', 'frenagem', 'estabilização']:
                    d = summ.get(ph, {})
                    fmt = phase_colors.get(ph, bold)
                    sh4.write(phase_row, 0, ph.capitalize(), fmt)
                    sh4.write(phase_row, 1, d.get('duração_s', 0), num_fmt)
                    sh4.write(phase_row, 2, d.get('percent_%', 0), num_fmt)
                    sh4.write(phase_row, 3, d.get('n_eventos', 0))
                    phase_row += 1

                # Detailed phase table for this run
                run_obj = next((r for r in runs if r.file_name == rn), None)
                if run_obj:
                    df_phases = run_obj.detect_phases()
                    if not df_phases.empty:
                        phase_row += 1
                        sh4.write(phase_row, 0, 'Detalhamento de Fases', sub_hdr)
                        phase_row += 1
                        df_phases.to_excel(writer, sheet_name='Fases de Condução',
                                           startrow=phase_row, index=False)
                        phase_row += len(df_phases) + 2
                phase_row += 1

            # ── Sheet 5: Correlações ──────────────────────────────────────────
            sh5 = wb.add_worksheet('Matriz de Correlação')
            sh5.set_column('A:A', 30); sh5.set_column('B:Z', 14)
            sh5.write('A1', 'Matriz de Correlação de Pearson', title)
            corr_row = 2
            corr_matrices = compute_correlation_matrix(runs, filter_settings)
            for rn, cmat in corr_matrices.items():
                sh5.write(corr_row, 0, f'RUN: {rn}', bold)
                corr_row += 1
                cmat.to_excel(writer, sheet_name='Matriz de Correlação', startrow=corr_row)
                n_c = len(cmat)
                sh5.conditional_format(corr_row+1, 1, corr_row+n_c, n_c,
                    {'type': '3_color_scale',
                     'min_value': -1, 'mid_value': 0, 'max_value': 1,
                     'min_color': '#FF4444', 'mid_color': '#FFFFFF', 'max_color': '#44FF44'})
                corr_row += n_c + 3

            # ── Sheet 6: Histogramas (tabela de frequência) ────────────────────
            sh6 = wb.add_worksheet('Histogramas')
            sh6.set_column('A:A', 24); sh6.set_column('B:Z', 14)
            sh6.write('A1', 'Distribuições de Frequência', title)
            hist_row = 2
            for key in [KEY_VEL_KMH_FILT, KEY_RPM_FILT, KEY_ACEL_MS2_FILT]:
                unit = CHANNEL_UNITS.get(key, '')
                sh6.write(hist_row, 0, f'{key} [{unit}]', bold)
                hist_row += 1
                sh6.write(hist_row, 0, 'Centro do Bin', hdr)
                for ci, rn in enumerate(names):
                    sh6.write(hist_row, ci+1, f'Contagem — {rn}', hdr)
                hist_row += 1
                run_hists = [r.compute_histogram_data(key) for r in runs]
                max_bins = max((len(c) for _, c in run_hists if len(c)), default=0)
                for bi in range(max_bins):
                    centers_0 = run_hists[0][0]
                    if bi < len(centers_0):
                        sh6.write(hist_row, 0, round(float(centers_0[bi]), 4), num_fmt)
                    for ci, (ctrs, cnts) in enumerate(run_hists):
                        if bi < len(cnts):
                            sh6.write(hist_row, ci+1, int(cnts[bi]))
                    hist_row += 1
                hist_row += 2

    except Exception:
        log.exception("falha na exportação")
        raise


