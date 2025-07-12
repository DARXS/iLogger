# iLogger/services/processing_service.py

import pandas as pd
from data.run_data import RunData
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import *

def process_run_files(file_paths: list) -> (list[RunData], list[str]):
    """
    Processa uma lista de arquivos de RUN em paralelo para acelerar a inicialização.
    Utiliza um ThreadPoolExecutor para carregar e realizar os cálculos brutos
    de múltiplos arquivos simultaneamente.
    """
    runs = []
    errors = []

    # Otimização: Usa um pool de threads para processar arquivos em paralelo.
    with ThreadPoolExecutor() as executor:
        # Mapeia cada future (operação assíncrona) ao seu respectivo path de arquivo.
        future_to_path = {executor.submit(RunData, path): path for path in file_paths}
        
        # Coleta os resultados à medida que são concluídos.
        for future in as_completed(future_to_path):
            path = future_to_path[future]
            try:
                run = future.result()
                runs.append(run)
            except Exception as e:
                errors.append(f"Erro ao processar {path}: {e}")

    # Garante que a ordem das runs seja a mesma da seleção de arquivos original.
    runs.sort(key=lambda r: file_paths.index(r.file_path))
    return runs, errors

def generate_statistics(runs: list[RunData], filter_settings: dict) -> (pd.DataFrame, pd.DataFrame):
    """
    Gera as tabelas de métricas e variações aplicando um conjunto de filtros específico.
    """
    if not runs:
        return pd.DataFrame(), pd.DataFrame()

    all_stats = []
    for run in runs:
        # Aplica o filtro desejado e recalcula as estatísticas internas da run.
        run.apply_filters_and_recalculate(filter_settings)
        all_stats.append(run.stats)

    if not all_stats:
        return pd.DataFrame(), pd.DataFrame()

    metrics_df = pd.DataFrame(all_stats)
    metrics_df = metrics_df.set_index('Arquivo')
    
    for col in metrics_df.columns:
        if metrics_df[col].dtype == 'float64':
            metrics_df[col] = metrics_df[col].round(2)

    variations_df = pd.DataFrame()
    if len(metrics_df) > 1:
        base_run = metrics_df.iloc[0]
        variations_df = metrics_df.iloc[1:].apply(
            lambda row: ((row - base_run) / base_run.replace(0, 1e-9)) * 100, axis=1
        ).round(2)

    return metrics_df, variations_df