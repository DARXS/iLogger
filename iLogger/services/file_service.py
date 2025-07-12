# iLogger/services/file_service.py

import os
import glob
import pandas as pd
import traceback
from PyQt6.QtWidgets import QMessageBox
from data.run_data import RunData
from config import *

# --- FUNÇÕES AUXILIARES PARA CRIAÇÃO DE GRÁFICOS ---

def _create_timeseries_chart(workbook, data_sheet_name, run_names, rows_per_run, time_col, value_col, title, y_title):
    """Cria um gráfico de linha (série temporal) comparativo."""
    chart = workbook.add_chart({'type': 'line'})
    row_offset = 2
    for i, run_name in enumerate(run_names):
        start = row_offset
        end = row_offset + rows_per_run[i] - 1
        chart.add_series({
            'name':       run_name,
            'categories': f"='{data_sheet_name}'!${time_col}${start}:${time_col}${end}",
            'values':     f"='{data_sheet_name}'!${value_col}${start}:${value_col}${end}",
            'line':       {'width': 1.25},
        })
        row_offset += rows_per_run[i]
    chart.set_title({'name': title})
    chart.set_x_axis({'name': 'Tempo (s)'})
    chart.set_y_axis({'name': y_title, 'major_gridlines': {'visible': False}})
    chart.set_legend({'position': 'top'})
    chart.set_size({'width': 720, 'height': 420})
    return chart

def _create_scatter_chart(workbook, data_sheet_name, run_names, rows_per_run, x_col, y_col, title, x_title, y_title):
    """Cria um gráfico de dispersão (XY) comparativo."""
    chart = workbook.add_chart({'type': 'scatter'})
    row_offset = 2
    for i, run_name in enumerate(run_names):
        start = row_offset
        end = row_offset + rows_per_run[i] - 1
        chart.add_series({
            'name':       run_name,
            'categories': f"='{data_sheet_name}'!${x_col}${start}:${x_col}${end}",
            'values':     f"='{data_sheet_name}'!${y_col}${start}:${y_col}${end}",
            'marker':     {'type': 'circle', 'size': 3},
            'line':       {'none': True},
        })
        row_offset += rows_per_run[i]
    chart.set_title({'name': title})
    chart.set_x_axis({'name': x_title})
    chart.set_y_axis({'name': y_title})
    chart.set_legend({'position': 'top'})
    chart.set_size({'width': 720, 'height': 420})
    return chart

# A função _create_bar_chart foi removida por não ser mais necessária.

# --- FUNÇÃO PRINCIPAL DE EXPORTAÇÃO ---

def export_to_dashboard_excel(runs: list[RunData], save_path: str, metrics_df: pd.DataFrame, variations_df: pd.DataFrame, filter_settings: dict, setup_info: dict, observations: str):
    """Exporta um relatório avançado para Excel com Dashboard, dados prontos para IA e instruções."""
    try:
        # 1. Preparar os dados filtrados em formato "Tidy"
        tidy_data_list = []
        rows_per_run = []
        run_names = [run.file_name for run in runs]

        for run in runs:
            run.apply_filters_and_recalculate(filter_settings)
            filtered_df = run.get_processed_data_as_dataframe()
            analysis_df = filtered_df[[KEY_TEMPO_S, KEY_VEL_KMH_FILT, KEY_RPM_FILT, KEY_ACEL_MS2_FILT, KEY_DIST_M]].rename(columns={
                KEY_TEMPO_S: 'Tempo (s)', KEY_VEL_KMH_FILT: 'Velocidade (km/h)', KEY_RPM_FILT: 'RPM',
                KEY_ACEL_MS2_FILT: 'Aceleração (m/s²)', KEY_DIST_M: 'Distância (m)'
            })
            tidy_data_list.append(analysis_df)
            rows_per_run.append(len(analysis_df))
        tidy_df = pd.concat(tidy_data_list, keys=run_names, names=['Run', 'Index']).reset_index(level='Run')

        # 2. Escrever o arquivo Excel
        with pd.ExcelWriter(save_path, engine='xlsxwriter') as writer:
            workbook = writer.book
            
            # Formatos
            bold_format = workbook.add_format({'bold': True})
            title_format = workbook.add_format({'bold': True, 'font_size': 14, 'bottom': 1, 'font_color': '#333333'})
            header_format = workbook.add_format({'bold': True, 'bg_color': '#DDEBF7', 'border': 1, 'font_color': '#002060'})

            # -- Criação das Abas na Ordem Correta --
            sheet1 = workbook.add_worksheet('Instrucoes')
            sheet2 = workbook.add_worksheet('Dados Gerais e Setup')
            sheet3 = workbook.add_worksheet('Dashboard de Gráficos')
            
            # -- Aba 1: Instruções --
            sheet1.set_column('A:A', 25)
            sheet1.set_column('B:B', 60)
            sheet1.write('A1', 'Guia de Utilização do Relatório', title_format)
            sheet1.write('A3', 'Estrutura do Arquivo', header_format)
            sheet1.write('B3', 'Descrição', header_format)
            sheet1.write('A4', 'Dados Gerais e Setup', bold_format)
            sheet1.write('B4', 'Informações de setup do veículo e tabelas com as métricas principais da análise.')
            sheet1.write('A5', 'Dashboard de Gráficos', bold_format)
            sheet1.write('B5', 'Painel visual com todos os gráficos comparativos da análise. Os gráficos são interativos.')
            sheet1.write('A6', 'Dados para Análise', bold_format)
            sheet1.write('B6', 'Tabela com os dados filtrados em formato otimizado ("tidy data"), ideal para importação em ferramentas de BI (PowerBI, Tableau) ou para análise por IA.')
            sheet1.write('A7', 'Dados_RUN_...', bold_format)
            sheet1.write('B7', 'Abas individuais contendo os dados processados completos para cada uma das corridas analisadas.')

            # -- Aba 2: Dados Gerais e Setup --
            sheet2.set_column('A:A', 25)
            sheet2.set_column('B:Z', 15)
            sheet2.write('A1', 'Setup do Veículo', title_format)
            row = 2
            if setup_info:
                for key, value in setup_info.items():
                    sheet2.write_string(row, 0, key, bold_format)
                    sheet2.write_string(row, 1, str(value))
                    row += 1
            row += 2
            metrics_start_row = row
            sheet2.write(metrics_start_row, 0, 'Métricas Principais', title_format)
            metrics_df.to_excel(writer, sheet_name='Dados Gerais e Setup', startrow=metrics_start_row + 1)
            variations_start_row = metrics_start_row + len(metrics_df) + 4
            sheet2.write(variations_start_row, 0, 'Variações Percentuais (%)', title_format)
            variations_df.to_excel(writer, sheet_name='Dados Gerais e Setup', startrow=variations_start_row + 1)

            # -- Aba 4: Dados para Análise (Tidy) --
            tidy_df.to_excel(writer, sheet_name='Dados para Análise', index=False)

            # -- Abas de Dados por Run (Raw) --
            for run in runs:
                sheet_name = f"Dados_{run.file_name.replace('.csv', '')[:25]}"
                run.get_processed_data_as_dataframe().to_excel(writer, sheet_name=sheet_name, index=False)

            # 3. Criar os Gráficos Nativos
            charts = {}
            data_sheet_name = 'Dados para Análise'
            charts['vel'] = _create_timeseries_chart(workbook, data_sheet_name, run_names, rows_per_run, 'B', 'C', 'Velocidade Comparativa', 'Velocidade (km/h)')
            charts['rpm'] = _create_timeseries_chart(workbook, data_sheet_name, run_names, rows_per_run, 'B', 'D', 'RPM Comparativo', 'RPM')
            charts['acel'] = _create_timeseries_chart(workbook, data_sheet_name, run_names, rows_per_run, 'B', 'E', 'Aceleração Comparativa', 'Aceleração (m/s²)')
            charts['dist'] = _create_timeseries_chart(workbook, data_sheet_name, run_names, rows_per_run, 'B', 'F', 'Distância Percorrida', 'Distância (m)')
            # CORREÇÃO: Eixos do gráfico de CVT (RPM x Velocidade) invertidos conforme solicitado.
            charts['rpm_vel'] = _create_scatter_chart(workbook, data_sheet_name, run_names, rows_per_run, 'C', 'D', 'Relação RPM x Velocidade', 'Velocidade (km/h)', 'RPM')
            # O gráfico de barras foi removido.
            
            # 4. Montar o Dashboard
            sheet3.write('A1', 'Dashboard de Análise de Desempenho', workbook.add_format({'bold': True, 'font_size': 20, 'font_color': '#333333'}))
            
            # Posiciona os gráficos em um grid
            sheet3.insert_chart('B2',  charts['vel'])
            sheet3.insert_chart('L2',  charts['rpm'])
            sheet3.insert_chart('B23', charts['acel'])
            sheet3.insert_chart('L23', charts['dist'])
            sheet3.insert_chart('B44', charts['rpm_vel'])
            
        QMessageBox.information(None, "Sucesso", f"Dashboard Excel salvo com sucesso em:\n{save_path}")

    except Exception as e:
        error_details = traceback.format_exc()
        QMessageBox.critical(None, "Erro ao Exportar Dashboard", f"Ocorreu um erro inesperado: {e}\n\nDetalhes:\n{error_details}")

def generate_processed_csv(run_directory: str, run_number: str, save_directory: str):
    """Função legada para exportar um único CSV processado."""
    run_files = glob.glob(os.path.join(run_directory, f"*RUN{run_number}*.csv"))
    if not run_files:
        QMessageBox.warning(None, "Arquivo não Encontrado", f"Nenhum arquivo encontrado para a RUN {run_number} em '{run_directory}'.")
        return
    try:
        df = pd.read_csv(run_files[0])
        save_path = os.path.join(save_directory, f"RUN{run_number}_processed.csv")
        df.to_csv(save_path, index=False)
        QMessageBox.information(None, "Sucesso", f"Arquivo CSV processado e salvo em:\n{save_path}")
    except Exception as e:
        QMessageBox.critical(None, "Erro ao Gerar CSV", f"Ocorreu um erro inesperado: {str(e)}")