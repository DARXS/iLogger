# iLogger/state/app_state.py

import pandas as pd
from PyQt6.QtCore import QObject, pyqtSignal

class AppState(QObject):
    """
    Mantém o estado da aplicação.
    Versão Refatorada: Não armazena mais o estado do filtro global.
    A responsabilidade do filtro agora é de cada widget de plotagem.
    """
    # Sinal emitido quando um novo conjunto de dados brutos é carregado
    data_loaded = pyqtSignal()
    # Sinal emitido para mensagens na barra de status
    status_message_changed = pyqtSignal(str, int)

    def __init__(self):
        super().__init__()
        self.raw_runs = []

    def update_analysis_results(self, runs: list):
        """
        Atualiza o estado com os dados brutos de uma nova análise.
        """
        self.raw_runs = runs
        self.data_loaded.emit() # Emite o sinal de que novos dados brutos estão prontos

    def clear_data(self):
        """Limpa todos os dados da análise atual."""
        self.raw_runs = []
        self.data_loaded.emit()