# iLogger/config.py

# --- Constantes da Aplicação ---
APP_NAME = "MANGUE LOGGER"
APP_VERSION = "v2.0"
DEFAULT_THEME = 'dark_teal.xml'
LIGHT_THEME = 'light_teal.xml'
WINDOW_ICON_PATH = 'ui/resources/logo.ico'
REPORT_COVER_PATH = 'ui/resources/report_cover.png'

# --- Constantes Físicas e do Veículo ---
RAIO_PNEU_M = 0.29  # Raio do pneu em metros (9 polegadas)
PI = 3.1415926535
FUROS_DISCO_FREIO = 12

# --- Padrões de Filtro ---
# Valores padrão para os filtros, usados na inicialização dos controles
BUTTERWORTH_ORDER = 4
BUTTERWORTH_CUTOFF = 0.1
SAVGOL_WINDOW = 11
SAVGOL_POLYORDER = 2
CHEBY1_ORDER = 4
CHEBY1_RP = 1
CHEBY1_CUTOFF = 0.1
BESSEL_ORDER = 4
BESSEL_CUTOFF = 0.1
MEDIAN_KERNEL_SIZE = 5
MOVING_AVG_WINDOW = 5

# --- Chaves de Dados (para acesso consistente em dicionários e DataFrames) ---
KEY_TEMPO_S = 'Tempo (s)'
KEY_RPM_RAW = 'RPM (Bruto)'
KEY_RPM_FILT = 'RPM (Filtrado)'
KEY_VEL_KMH_RAW = 'Velocidade (Km/h - Bruto)'
KEY_VEL_KMH_FILT = 'Velocidade (Km/h - Filtrado)'
KEY_ACEL_MS2_FILT = 'Aceleração (m/s² - Filtrado)'
KEY_JERK_MS3 = 'Jerk (m/s³)' # Mantido para cálculo interno, mas removido da UI
KEY_DIST_M = 'Distância (m)'

# --- Opções para Gráfico Personalizado ---
# Removido Jerk e adicionada Distância
CUSTOM_PLOT_AXES_OPTIONS = [
    KEY_TEMPO_S,
    KEY_RPM_FILT,
    KEY_VEL_KMH_FILT,
    KEY_ACEL_MS2_FILT,
    KEY_DIST_M,
    KEY_RPM_RAW,
    KEY_VEL_KMH_RAW,
]