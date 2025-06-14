# iLogger/ui/widgets/navigation_panel.py

from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QSizePolicy
from PyQt6.QtCore import pyqtSignal, QSize
from PyQt6.QtGui import QIcon

class NavigationPanel(QListWidget):
    """
    Painel de navegação lateral com tamanho fixo para selecionar a visualização principal.
    """
    
    view_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Define um tamanho fixo para a barra lateral
        self.setFixedWidth(220)
        
        # Configurações de estilo e comportamento
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self.setViewMode(QListWidget.ViewMode.ListMode) # Modo de lista para mostrar texto e ícone
        self.setIconSize(QSize(24, 24)) # Ícones um pouco menores para um visual mais limpo
        self.setSpacing(5)
        self.setCursor(self.cursor())
        
        # Conecta o sinal de mudança de item para emitir nosso sinal customizado
        self.currentRowChanged.connect(self.view_selected.emit)

    def add_view(self, name: str, icon_path: str = None):
        """Adiciona um novo item (uma nova tela) ao painel de navegação."""
        item = QListWidgetItem(name)
        if icon_path:
            item.setIcon(QIcon(icon_path))
        self.addItem(item)
    