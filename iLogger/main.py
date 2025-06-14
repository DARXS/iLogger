# iLogger/main.py

import sys
from PyQt6.QtWidgets import QApplication
import pyqtgraph as pg
from qt_material import apply_stylesheet

# Importações da nova estrutura
from config import DEFAULT_THEME
from state.app_state import AppState
from ui.main_window import MainWindow

# Configurações globais do pyqtgraph para uma aparência mais limpa
pg.setConfigOption('background', (240, 240, 240)) # Cor de fundo cinza claro
pg.setConfigOption('foreground', 'k')             # Cor da fonte preta
pg.setConfigOption('antialias', True)             # Habilita anti-aliasing para gráficos mais suaves


if __name__ == '__main__':
    """
    Ponto de entrada principal da aplicação iLogger.
    Cria a aplicação, o gestor de estado e a janela principal.
    """
    app = QApplication(sys.argv)
    
    try:
        apply_stylesheet(app, theme=DEFAULT_THEME, invert_secondary=True)
    except Exception as e:
        print(f"Erro ao aplicar o tema: {e}. A aplicação continuará com o tema padrão.")

    # 1. Cria a instância do gestor de estado
    app_state = AppState()
    
    # 2. Cria a janela principal e injeta a instância do estado nela
    window = MainWindow(app_state)
    window.show()
    
    # Inicia o loop de eventos da aplicação
    sys.exit(app.exec())