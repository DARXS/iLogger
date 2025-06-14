# iLogger/ui/widgets/custom_plot_widget.py

import pyqtgraph as pg
from pyqtgraph import exporters
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QComboBox, QPushButton, QLabel, QGridLayout
from PyQt6.QtCore import Qt
from config import CUSTOM_PLOT_AXES_OPTIONS
import numpy as np

class CustomPlotWidget(QWidget):
    """
    Widget para a aba de Gráfico Personalizado, usando pyqtgraph
    e suportando um segundo eixo Y.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.app_state = None
        
        main_layout = QVBoxLayout(self)
        controls_layout = QGridLayout()

        # --- Controles ---
        axes_options_with_none = [""] + CUSTOM_PLOT_AXES_OPTIONS
        self.combo_x = QComboBox()
        self.combo_y1 = QComboBox()
        self.combo_y2 = QComboBox()
        self.combo_x.addItems(CUSTOM_PLOT_AXES_OPTIONS)
        self.combo_y1.addItems(CUSTOM_PLOT_AXES_OPTIONS)
        self.combo_y2.addItems(axes_options_with_none)
        self.btn_update = QPushButton("Atualizar Gráfico")

        # --- Layout dos Controles ---
        controls_layout.addWidget(QLabel("Eixo X:"), 0, 0)
        controls_layout.addWidget(self.combo_x, 0, 1)
        controls_layout.addWidget(QLabel("Eixo Y (Primário):"), 1, 0)
        controls_layout.addWidget(self.combo_y1, 1, 1)
        controls_layout.addWidget(QLabel("Eixo Y (Secundário - Opcional):"), 2, 0)
        controls_layout.addWidget(self.combo_y2, 2, 1)
        controls_layout.addWidget(self.btn_update, 3, 0, 1, 2)
        
        # --- Widget de Gráfico (pyqtgraph) ---
        self.plot_widget = pg.PlotWidget()
        
        # --- OTIMIZAÇÃO DE RENDERIZAÇÃO ---
        self.plot_widget.getPlotItem().setDownsampling(mode='peak')
        self.plot_widget.getPlotItem().setClipToView(True)
        # ---------------------------------
        
        self.p1 = self.plot_widget.getPlotItem()
        self.legend = self.p1.addLegend()
        
        # Configuração do segundo eixo Y
        self.p2 = pg.ViewBox()
        self.p1.showAxis('right')
        self.p1.scene().addItem(self.p2)
        self.p1.getAxis('right').linkToView(self.p2)
        self.p2.setXLink(self.p1)
        
        main_layout.addLayout(controls_layout)
        main_layout.addWidget(self.plot_widget)
        
        self.btn_update.clicked.connect(self.update_plot)
        self.p1.vb.sigResized.connect(self._update_views)

    def _update_views(self):
        """Sincroniza a geometria da ViewBox secundária com a primária."""
        self.p2.setGeometry(self.p1.vb.sceneBoundingRect())
        self.p2.linkedViewChanged(self.p1.vb, self.p2.XAxis)

    def link_state(self, app_state):
        self.app_state = app_state
        
    def update_plot(self):
        if not self.app_state: return

        self._clear_plots()
        x_key, y1_key, y2_key = self.combo_x.currentText(), self.combo_y1.currentText(), self.combo_y2.currentText()
        
        self.p1.setLabel('bottom', x_key)
        self.p1.setLabel('left', y1_key)
        self.p1.setTitle(f"Gráfico Personalizado", size='14pt')
        self.p1.showGrid(x=True, y=True, alpha=0.3)
        
        if not self.app_state.raw_runs:
            self.p1.addItem(pg.TextItem("Sem dados para exibir", anchor=(0.5, 0.5), color='k'))
            return
        
        pens = [pg.mkPen(color=c, width=2) for c in ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']]
        
        for i, run in enumerate(self.app_state.raw_runs):
            x_data, y_data = run.get_data_for_custom_plot(x_key), run.get_data_for_custom_plot(y1_key)
            min_len = min(len(x_data), len(y_data))
            if min_len > 0:
                self.p1.plot(x_data[:min_len], y_data[:min_len], pen=pens[i % len(pens)], name=f"{y1_key} ({run.file_name})")
        
        if y2_key:
            self.p1.getAxis('right').show()
            self.p1.setLabel('right', y2_key)
            self.p2.setVisible(True)

            for i, run in enumerate(self.app_state.raw_runs):
                x_data, y_data = run.get_data_for_custom_plot(x_key), run.get_data_for_custom_plot(y2_key)
                min_len = min(len(x_data), len(y_data))
                if min_len > 0:
                    item = pg.PlotDataItem(x_data[:min_len], y_data[:min_len], pen=pg.mkPen(pens[i % len(pens)], style=Qt.PenStyle.DashLine), name=f"{y2_key} ({run.file_name})")
                    self.p2.addItem(item)
        else:
            self.p1.getAxis('right').hide()
            self.p2.setVisible(False)
        
        self._update_views()

    def _clear_plots(self):
        self.p1.clear()
        self.p2.clear()
        if self.legend:
            self.legend.clear()

    def get_figure_for_report(self):
        """Exporta o layout gráfico atual como uma imagem."""
        exporter = exporters.ImageExporter(self.plot_widget.scene())
        return exporter.export(toBytes=True)