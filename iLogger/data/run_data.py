# iLogger/data/run_data.py

import os
import numpy as np
import pandas as pd
from scipy import signal
from config import *
import json

class RunData:
    """
    Encapsula os dados de uma única RUN. Agora separa o cálculo dos dados brutos
    da aplicação dos filtros e implementa um cache para resultados de filtragem.
    """
    def __init__(self, file_path: str):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

        self.file_path = file_path # Armazena o path original
        self.file_name = os.path.basename(file_path)
        
        self.df_raw = self._load_data(file_path)
        self.time_s = np.array([])
        self.rpm_raw = np.array([])
        self.velocity_raw_kmh = np.array([])
        
        self.rpm_filtered = np.array([])
        self.velocity_filtered_ms = np.array([])
        self.velocity_filtered_kmh = np.array([])
        self.acceleration_filtered_ms2 = np.array([])
        self.jerk_ms3 = np.array([])
        self.distance_m = np.array([])
        self.stats = {}
        
        # Cache para armazenar os resultados dos cálculos de filtro
        self._filter_cache = {}
        
        self._calculate_raw_data()

    def _load_data(self, file_path: str) -> pd.DataFrame:
        # ... (código existente sem alterações)
        df = pd.read_csv(file_path, engine='c')
        required_cols = {'f1', 'f2'}
        if not required_cols.issubset(df.columns):
            raise ValueError(f"Arquivo {self.file_name} inválido: colunas 'f1' e 'f2' são obrigatórias.")
        
        df['f1'] = pd.to_numeric(df['f1'], errors='coerce')
        df['f2'] = pd.to_numeric(df['f2'], errors='coerce')
        df[['f1', 'f2']] = df[['f1', 'f2']].fillna(0)
        return df

    def _calculate_raw_data(self):
        # ... (código existente sem alterações)
        f1 = self.df_raw['f1'].values.astype(float)
        f2 = self.df_raw['f2'].values.astype(float)

        num_points = (len(f1) // 10) * 10
        if num_points < 10: return

        f1 = f1[:num_points]
        f2 = f2[:num_points]

        grouped_len = num_points // 10
        
        f1_sum_grouped = np.sum(f1.reshape(-1, 10), axis=1)
        f2_sum_grouped = np.sum(f2.reshape(-1, 10), axis=1)

        self.time_s = np.linspace(0, 0.05 * grouped_len, grouped_len, endpoint=False)
        self.rpm_raw = f2_sum_grouped * 1200
        vel_factor = (2 * RAIO_PNEU_M * PI * 20 * 3.6) / FUROS_DISCO_FREIO
        self.velocity_raw_kmh = f1_sum_grouped * vel_factor


    def apply_filters_and_recalculate(self, filter_settings: dict):
        if self.time_s.size == 0: return

        # Cria uma chave de cache imutável a partir das configurações do filtro
        cache_key = json.dumps(filter_settings, sort_keys=True)

        # Se o resultado para esta configuração de filtro já estiver no cache, use-o
        if cache_key in self._filter_cache:
            cached_data = self._filter_cache[cache_key]
            self.rpm_filtered = cached_data['rpm_filtered']
            self.velocity_filtered_ms = cached_data['velocity_filtered_ms']
            self.velocity_filtered_kmh = cached_data['velocity_filtered_kmh']
            self.acceleration_filtered_ms2 = cached_data['acceleration_filtered_ms2']
            self.jerk_ms3 = cached_data['jerk_ms3']
            self.distance_m = cached_data['distance_m']
            self._calculate_statistics()
            return

        # --- Se não estiver no cache, realize os cálculos ---
        vel_ms = self.velocity_raw_kmh * (5 / 18)
        filter_type = filter_settings.get('type', 'butterworth')

        # ... (lógica de filtragem existente, sem alterações)
        savgol_window = filter_settings.get('savgol_window', SAVGOL_WINDOW)
        if filter_type == 'savitzky_golay' and len(self.rpm_raw) <= savgol_window:
            return

        b, a = None, None
        
        if filter_type == 'savitzky_golay':
            poly = filter_settings.get('savgol_polyorder', SAVGOL_POLYORDER)
            self.rpm_filtered = signal.savgol_filter(self.rpm_raw, savgol_window, poly)
            self.velocity_filtered_ms = signal.savgol_filter(vel_ms, savgol_window, poly)
        elif filter_type == 'median':
            kernel = filter_settings.get('median_kernel', MEDIAN_KERNEL_SIZE)
            self.rpm_filtered = signal.medfilt(self.rpm_raw, kernel_size=kernel)
            self.velocity_filtered_ms = signal.medfilt(vel_ms, kernel_size=kernel)
        elif filter_type == 'moving_average':
            window = filter_settings.get('moving_avg_window', MOVING_AVG_WINDOW)
            self.rpm_filtered = np.convolve(self.rpm_raw, np.ones(window)/window, mode='same')
            self.velocity_filtered_ms = np.convolve(vel_ms, np.ones(window)/window, mode='same')
        else:
            if filter_type == 'chebyshev_type_i':
                order = filter_settings.get('cheby1_order', CHEBY1_ORDER)
                rp = filter_settings.get('cheby1_rp', CHEBY1_RP)
                cutoff = filter_settings.get('cheby1_cutoff', CHEBY1_CUTOFF)
                b, a = signal.cheby1(order, rp, cutoff, btype='low', analog=False)
            elif filter_type == 'bessel':
                order = filter_settings.get('bessel_order', BESSEL_ORDER)
                cutoff = filter_settings.get('bessel_cutoff', BESSEL_CUTOFF)
                b, a = signal.bessel(order, cutoff, btype='low', analog=False, norm='phase')
            else: # Butterworth (padrão)
                order = filter_settings.get('butter_order', BUTTERWORTH_ORDER)
                cutoff = filter_settings.get('butter_cutoff', BUTTERWORTH_CUTOFF)
                b, a = signal.butter(order, cutoff, analog=False)
            
            self.rpm_filtered = signal.filtfilt(b, a, self.rpm_raw)
            self.velocity_filtered_ms = signal.filtfilt(b, a, vel_ms)

        self.velocity_filtered_kmh = self.velocity_filtered_ms * (18 / 5)
        
        acceleration_ms2 = np.gradient(self.velocity_filtered_ms, self.time_s, edge_order=2)
        b_accel, a_accel = signal.butter(4, 0.1, analog=False)
        self.acceleration_filtered_ms2 = signal.filtfilt(b_accel, a_accel, acceleration_ms2)

        self.jerk_ms3 = np.gradient(self.acceleration_filtered_ms2, self.time_s, edge_order=2)
        
        dt = np.diff(self.time_s, prepend=0)
        self.distance_m = np.cumsum(self.velocity_filtered_ms * dt)
        
        # Armazena os novos resultados no cache
        self._filter_cache[cache_key] = {
            'rpm_filtered': self.rpm_filtered,
            'velocity_filtered_ms': self.velocity_filtered_ms,
            'velocity_filtered_kmh': self.velocity_filtered_kmh,
            'acceleration_filtered_ms2': self.acceleration_filtered_ms2,
            'jerk_ms3': self.jerk_ms3,
            'distance_m': self.distance_m
        }
        
        self._calculate_statistics()
    
    # ... (resto do arquivo sem alterações)
    def _calculate_statistics(self):
        """Recalcula as estatísticas com base nos dados filtrados mais recentes."""
        vel_kmh = self.velocity_filtered_kmh
        rpm = self.rpm_filtered
        acel = self.acceleration_filtered_ms2
        dist = self.distance_m
        
        self.stats = {
            'Arquivo': self.file_name,
            'Vel. Máx (Km/h)': np.max(vel_kmh) if vel_kmh.size > 0 else 0,
            'Vel. Média (Km/h)': np.mean(vel_kmh) if vel_kmh.size > 0 else 0,
            'RPM Máx': np.max(rpm) if rpm.size > 0 else 0,
            'RPM Médio': np.mean(rpm) if rpm.size > 0 else 0,
            'Acel. Máx (m/s²)': np.max(acel) if acel.size > 0 else 0,
            'Distância Total (m)': dist[-1] if dist.size > 0 else 0
        }

    def get_data_for_custom_plot(self, key: str):
        data_map = {
            KEY_TEMPO_S: self.time_s, KEY_RPM_FILT: self.rpm_filtered, KEY_VEL_KMH_FILT: self.velocity_filtered_kmh,
            KEY_ACEL_MS2_FILT: self.acceleration_filtered_ms2, KEY_DIST_M: self.distance_m,
            KEY_RPM_RAW: self.rpm_raw, KEY_VEL_KMH_RAW: self.velocity_raw_kmh
        }
        return data_map.get(key, np.array([]))

    def get_processed_data_as_dataframe(self) -> pd.DataFrame:
        data = {
            KEY_TEMPO_S: self.time_s,
            KEY_RPM_RAW: self.rpm_raw,
            KEY_VEL_KMH_RAW: self.velocity_raw_kmh,
            KEY_RPM_FILT: self.rpm_filtered,
            KEY_VEL_KMH_FILT: self.velocity_filtered_kmh,
            KEY_ACEL_MS2_FILT: self.acceleration_filtered_ms2,
            KEY_DIST_M: self.distance_m
        }
        return pd.DataFrame(data)