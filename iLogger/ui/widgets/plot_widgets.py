# iLogger/ui/widgets/plot_widgets.py

import pyqtgraph as pg
from pyqtgraph import exporters
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QScrollArea
from PyQt6.QtCore import Qt
from config import *
from .filter_control_panel import FilterControlPanel
import math

class BasePlotWidget(QWidget):
    """
    Classe base para widgets de plotagem. Gerencia seu próprio estado de filtro
    e reprocessa os dados sob demanda.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.app_state = None
        self.plot_item = None
        self.filter_settings = {}
        
        layout = QHBoxLayout(self)
        self.filter_controls = FilterControlPanel()
        self.filter_controls.setFixedWidth(250)
        
        self.plot_widget = pg.PlotWidget()
        
        layout.addWidget(self.plot_widget)
        layout.addWidget(self.filter_controls)
        
        self.filter_controls.filter_changed.connect(self._on_filter_changed)

    def link_state(self, app_state):
        self.app_state = app_state
        self.app_state.data_loaded.connect(self.update_plot)
        self.filter_settings = self.filter_controls.get_settings()
        self.update_plot()

    def _on_filter_changed(self, settings: dict):
        self.filter_settings = settings
        self.update_plot()

    def update_plot(self):
        # Este método DEVE ser implementado pelas subclasses
        raise NotImplementedError("Subclasses devem implementar 'update_plot'")
        
    def get_figure_for_report(self):
        if self.plot_item:
            exporter = exporters.ImageExporter(self.plot_item.scene())
            return exporter.export(toBytes=True)
        return None


class TimeSeriesPlotWidget(BasePlotWidget):
    """Widget para plotar séries temporais (ex: RPM x Tempo)."""
    def __init__(self, title: str, y_label: str, raw_key: str, filt_key: str):
        super().__init__()
        self.title = title
        self.y_label = y_label
        self.raw_key = raw_key
        self.filt_key = filt_key

        self.plot_item = self.plot_widget.getPlotItem()
        self.plot_item.setTitle(title, size='14pt')
        self.plot_item.setLabel('bottom', 'Tempo (s)')
        self.plot_item.setLabel('left', y_label)
        self.plot_item.showGrid(x=True, y=True, alpha=0.3)
        self.legend = self.plot_item.addLegend()

    def update_plot(self):
        self.plot_item.clear()
        if not self.app_state or not self.app_state.raw_runs:
            self.plot_item.addItem(pg.TextItem("Sem dados para exibir", anchor=(0.5, 0.5)))
            return
            
        pens = [pg.mkPen(color=c, width=2) for c in ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']]
        pens_raw = [pg.mkPen(color=c, style=Qt.PenStyle.DotLine) for c in ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']]

        for i, run in enumerate(self.app_state.raw_runs):
            run.apply_filters_and_recalculate(self.filter_settings)

            time_data = run.time_s
            raw_data = run.get_data_for_custom_plot(self.raw_key)
            filt_data = run.get_data_for_custom_plot(self.filt_key)

            if time_data.size > 0:
                self.plot_item.plot(time_data, filt_data, pen=pens[i % len(pens)], name=f"Filt - {run.file_name}")
                if self.raw_key != self.filt_key:
                    self.plot_item.plot(time_data, raw_data, pen=pens_raw[i % len(pens_raw)], name=f"Raw - {run.file_name}")


class AccelerationPlotWidget(BasePlotWidget):
    """Widget para o gráfico de Aceleração."""
    def __init__(self):
        super().__init__()
        self.plot_item = self.plot_widget.getPlotItem()
        self.plot_item.setTitle("Aceleração", size='14pt')
        self.plot_item.setLabel('bottom', 'Tempo (s)')
        self.plot_item.setLabel('left', 'Aceleração (m/s²)')
        self.plot_item.showGrid(x=True, y=True, alpha=0.3)
        self.legend = self.plot_item.addLegend()

    def update_plot(self):
        self.plot_item.clear()
        if not self.app_state or not self.app_state.raw_runs: return
        
        pens = [pg.mkPen(color=c, width=2) for c in ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']]
        for i, run in enumerate(self.app_state.raw_runs):
            run.apply_filters_and_recalculate(self.filter_settings)
            if run.time_s.size > 0 and run.acceleration_filtered_ms2.size > 0:
                self.plot_item.plot(run.time_s, run.acceleration_filtered_ms2, pen=pens[i % len(pens)], name=run.file_name)


class RelationPlotWidget(BasePlotWidget):
    """Widget para o gráfico de Relação RPM x Velocidade."""
    def __init__(self):
        super().__init__()
        self.plot_item = self.plot_widget.getPlotItem()
        self.plot_item.setTitle("Relação RPM x Velocidade", size='14pt')
        self.plot_item.setLabel('bottom', 'Velocidade (Km/h)')
        self.plot_item.setLabel('left', 'RPM')
        self.plot_item.showGrid(x=True, y=True, alpha=0.3)
        self.legend = self.plot_item.addLegend()

    def update_plot(self):
        self.plot_item.clear()
        if not self.app_state or not self.app_state.raw_runs: return

        pens = [pg.mkPen(color=c, width=2) for c in ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']]
        for i, run in enumerate(self.app_state.raw_runs):
            run.apply_filters_and_recalculate(self.filter_settings)
            if run.velocity_filtered_kmh.size > 0 and run.rpm_filtered.size > 0:
                self.plot_item.plot(run.velocity_filtered_kmh, run.rpm_filtered, pen=pens[i % len(pens)], name=run.file_name)


class ComparisonPlotWidget(QWidget):
    """
    Widget para o gráfico de barras comparativo de métricas.
    Mostra um gráfico de barras separado para cada métrica.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.metrics_df = None
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        
        self.graphics_layout = pg.GraphicsLayoutWidget()
        self.scroll_area.setWidget(self.graphics_layout)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.scroll_area)
    
    def update_plot(self, metrics_df):
        self.metrics_df = metrics_df
        self.graphics_layout.clear()

        if self.metrics_df is None or self.metrics_df.empty:
            return

        df_plot = self.metrics_df.copy()
        if 'Arquivo' in df_plot.columns:
            # Se 'Arquivo' for uma coluna, usamos como índice. Se já for índice, não faz nada.
            if df_plot.index.name != 'Arquivo':
                df_plot = df_plot.set_index('Arquivo')

        if df_plot.empty:
            return
            
        metrics = df_plot.columns.tolist()
        run_names = df_plot.index.tolist()
        num_runs = len(run_names)

        num_cols = 2
        num_rows = math.ceil(len(metrics) / num_cols)
        
        current_row, current_col = 0, 0
        
        for metric_name in metrics:
            p = self.graphics_layout.addPlot(row=current_row, col=current_col)
            p.setTitle(metric_name)

            y_values = df_plot[metric_name].values
            
            x_ticks = list(enumerate(run_names))
            axis = p.getAxis('bottom')
            axis.setTicks([x_ticks])
            # Rotaciona os labels se forem muito longos
            if any(len(name) > 15 for name in run_names):
                axis.setTickAngle(-30)
            
            bar_item = pg.BarGraphItem(
                x=range(num_runs), 
                height=y_values, 
                width=0.6, 
                brushes=[pg.intColor(i, hues=num_runs, sat=200) for i in range(num_runs)]
            )
            p.addItem(bar_item)
            
            min_val = min(0, y_values.min()) if y_values.size > 0 else 0
            max_val = y_values.max() if y_values.size > 0 else 0
            padding = (max_val - min_val) * 0.15
            p.setYRange(min_val, max_val + padding)
            
            current_col += 1
            if current_col >= num_cols:
                current_col = 0
                current_row += 1

    def get_figure_for_report(self):
        if self.metrics_df is not None and not self.metrics_df.empty:
            exporter = exporters.ImageExporter(self.graphics_layout.scene())
            return exporter.export(toBytes=True)
        return None