# iLogger/ui/widgets/dashboard_widget.py

import math
import pyqtgraph as pg
from pyqtgraph import exporters
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QCheckBox, QPushButton, QGroupBox, QHBoxLayout
)

from config import *
from .filter_control_panel import FilterControlPanel

class DashboardWidget(QWidget):
    """
    Widget para o Dashboard. Agora possui seu próprio painel de filtros
    e processa os dados sob demanda.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.app_state = None
        self.filter_settings = {}
        
        # --- Layout Principal ---
        main_layout = QHBoxLayout(self)
        
        # --- Área de Conteúdo (Seleção + Gráficos) ---
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        # --- Controles de Seleção de Gráfico ---
        selection_group = QGroupBox("Selecione os Gráficos para Exibir")
        selection_layout = QHBoxLayout(selection_group)
        
        self.checkboxes = {}
        self.plot_keys_map = {
            'rotacao': ("Rotação", KEY_RPM_FILT, "RPM"),
            'velocidade': ("Velocidade", KEY_VEL_KMH_FILT, "Km/h"),
            'aceleracao': ("Aceleração", KEY_ACEL_MS2_FILT, "m/s²"),
            'distancia': ("Distância", KEY_DIST_M, "m"),
        }
        
        for key, (name, _, _) in self.plot_keys_map.items():
            cb = QCheckBox(name)
            cb.setChecked(True)
            self.checkboxes[key] = cb
            selection_layout.addWidget(cb)
        
        # Botão para forçar a atualização, embora também atualize com o filtro
        self.btn_update = QPushButton("Atualizar Dashboard")
        
        content_layout.addWidget(selection_group)
        content_layout.addWidget(self.btn_update)
        
        # --- Área de Gráficos do Dashboard ---
        self.graphics_layout = pg.GraphicsLayoutWidget()
        content_layout.addWidget(self.graphics_layout)
        
        # --- Painel de Filtro ---
        self.filter_controls = FilterControlPanel()
        self.filter_controls.setFixedWidth(250)
        
        main_layout.addWidget(content_widget)
        main_layout.addWidget(self.filter_controls)

        # --- Conexões ---
        self.btn_update.clicked.connect(self.update_plot)
        self.filter_controls.filter_changed.connect(self._on_filter_changed)

    def link_state(self, app_state):
        """Recebe o AppState da MainWindow."""
        self.app_state = app_state
        self.app_state.data_loaded.connect(self.update_plot)
        self.filter_settings = self.filter_controls.get_settings()
        self.update_plot()

    def _on_filter_changed(self, settings: dict):
        self.filter_settings = settings
        self.update_plot()

    def update_plot(self):
        """Redesenha a grade do dashboard com os gráficos selecionados."""
        self.graphics_layout.clear()
        
        selected_keys = [key for key, cb in self.checkboxes.items() if cb.isChecked()]
        
        if not self.app_state or not self.app_state.raw_runs or not selected_keys:
            self.graphics_layout.addLabel("Sem dados para exibir.", row=0, col=0)
            return
            
        n = len(selected_keys)
        cols = int(math.ceil(math.sqrt(n))) if n > 0 else 1
        
        current_row, current_col = 0, 0
        pens = [pg.mkPen(color=c, width=2) for c in ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']]

        for run_idx, run in enumerate(self.app_state.raw_runs):
            # Aplica o filtro do dashboard na run
            run.apply_filters_and_recalculate(self.filter_settings)

        for key in selected_keys:
            if key in self.plot_keys_map:
                title, data_key, y_label = self.plot_keys_map[key]
                
                # Adiciona um novo plot na grade do dashboard
                p_new = self.graphics_layout.addPlot(row=current_row, col=current_col, title=title)
                p_new.setLabel('left', y_label)
                p_new.setLabel('bottom', 'Tempo (s)')
                p_new.showGrid(x=True, y=True, alpha=0.3)

                # Plota os dados de cada run neste mini-gráfico
                for run_idx, run in enumerate(self.app_state.raw_runs):
                    y_data = run.get_data_for_custom_plot(data_key)
                    if run.time_s.size > 0 and y_data.size > 0:
                        p_new.plot(run.time_s, y_data, pen=pens[run_idx % len(pens)])
                
                current_col += 1
                if current_col >= cols:
                    current_col = 0
                    current_row += 1

    def get_figure_for_report(self):
        """Exporta o layout gráfico atual como uma imagem."""
        if not self.graphics_layout.items():
            return None
        exporter = exporters.ImageExporter(self.graphics_layout.scene())
        return exporter.export(toBytes=True)