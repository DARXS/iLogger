# iLogger/ui/main_window.py

import sys
import pandas as pd
import traceback
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QMessageBox, QTextEdit, QToolBar, QApplication, QFileDialog,
    QStatusBar, QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
    QSplitter
)
from PyQt6.QtGui import QIcon, QAction, QPixmap
from qt_material import apply_stylesheet

from config import *
from state.app_state import AppState
from services import processing_service, report_service, file_service
from .widgets.navigation_panel import NavigationPanel
from .widgets.controls_panel import ControlsPanel
from .widgets.plot_widgets import (
    TimeSeriesPlotWidget, AccelerationPlotWidget, RelationPlotWidget, ComparisonPlotWidget
)
from .widgets.custom_plot_widget import CustomPlotWidget
from .widgets.dashboard_widget import DashboardWidget


class MainWindow(QMainWindow):
    def __init__(self, app_state: AppState):
        super().__init__()
        self.app_state = app_state
        self.setWindowTitle(f"{APP_NAME} - {APP_VERSION}")
        self.setWindowIcon(QIcon(WINDOW_ICON_PATH))
        self.resize(1600, 900)
        self.setStatusBar(QStatusBar(self))
        self.current_theme = DEFAULT_THEME

        self.reportable_widgets = {}

        self._init_ui()
        self._connect_signals()
        
        self.nav_panel.setCurrentRow(0)

    def _init_ui(self):
        self._create_toolbar()
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        self.nav_panel = NavigationPanel()
        self.view_stack = QStackedWidget()
        
        main_layout.addWidget(self.nav_panel)
        main_layout.addWidget(self.view_stack)
        main_layout.setStretch(1, 1)

        self._populate_views()

    def _populate_views(self):
        self.controls_panel = ControlsPanel()
        self._add_view(self.controls_panel, "Controles", key="controles")

        self._add_plot_view("Rotação", "rotacao", KEY_RPM_RAW, KEY_RPM_FILT)
        self._add_plot_view("Velocidade", "velocidade", KEY_VEL_KMH_RAW, KEY_VEL_KMH_FILT, y_label="Velocidade (Km/h)")
        
        accel_view = AccelerationPlotWidget()
        self._add_view(accel_view, "Aceleração / Força G", key="aceleracao")

        self._add_plot_view("Distância", "distancia", KEY_DIST_M, KEY_DIST_M, y_label="Distância (m)")

        relation_view = RelationPlotWidget()
        self._add_view(relation_view, "Relação RPM x Velocidade", key="relacao")

        # --- ABA DE ESTATÍSTICAS (COM SPLITTER) ---
        stats_view = QSplitter(Qt.Orientation.Horizontal)

        tables_container = QWidget()
        tables_layout = QVBoxLayout(tables_container)
        
        tables_layout.addWidget(QLabel("<h3>Tabela de Métricas Principais</h3>"))
        self.metrics_table = QTableWidget()
        tables_layout.addWidget(self.metrics_table)

        tables_layout.addWidget(QLabel("<h3>Variações Percentuais em Relação ao Primeiro Arquivo</h3>"))
        self.variations_table = QTableWidget()
        tables_layout.addWidget(self.variations_table)
        
        self.comparison_plot = ComparisonPlotWidget()

        stats_view.addWidget(tables_container)
        stats_view.addWidget(self.comparison_plot)
        stats_view.setSizes([400, 800])
        
        self._add_view(stats_view, "Estatísticas", key="estatisticas")
        self.reportable_widgets['comparativo'] = self.comparison_plot
        
        self.dashboard_widget = DashboardWidget()
        self._add_view(self.dashboard_widget, "Dashboard", key="dashboard")

        self.custom_plot_widget = CustomPlotWidget()
        self._add_view(self.custom_plot_widget, "Gráfico Personalizado", key="custom_plot")

    def _add_view(self, widget, name: str, key: str, icon_path: str = None):
        self.view_stack.addWidget(widget)
        self.nav_panel.add_view(name, icon_path)
        if hasattr(widget, 'get_figure_for_report'):
            self.reportable_widgets[key] = widget
    
    def _add_plot_view(self, name: str, key: str, raw_key: str, filt_key: str, y_label: str = None):
        if y_label is None: y_label = name
        plot_widget = TimeSeriesPlotWidget(name, y_label, raw_key, filt_key)
        self._add_view(plot_widget, name, key=key)
        
        if key == 'velocidade':
            plot_widget.filter_controls.filter_changed.connect(self.update_statistics_view)

    def _connect_signals(self):
        self.nav_panel.view_selected.connect(self.view_stack.setCurrentIndex)
        self.controls_panel.analysis_requested.connect(self.start_analysis)
        
        self.app_state.data_loaded.connect(self.update_statistics_view)
        self.app_state.status_message_changed.connect(self.statusBar().showMessage)
        
        for widget in self.reportable_widgets.values():
            if hasattr(widget, 'link_state'):
                widget.link_state(self.app_state)
        
        if 'custom_plot' in self.reportable_widgets:
             self.reportable_widgets['custom_plot'].link_state(self.app_state)


    def _create_toolbar(self):
        toolbar = QToolBar("Ações Gerais")
        self.addToolBar(toolbar)
        
        pdf_action = QAction("Salvar Relatório PDF", self)
        pdf_action.triggered.connect(self.save_report)
        toolbar.addAction(pdf_action)
        
        excel_action = QAction("Exportar para Excel", self)
        excel_action.triggered.connect(self.export_to_excel)
        toolbar.addAction(excel_action)

        theme_action = QAction("Alternar Tema", self)
        theme_action.triggered.connect(self.toggle_theme)
        toolbar.addAction(theme_action)

    def start_analysis(self, analysis_data: dict):
        file_paths = analysis_data.get("file_paths", [])
        if not file_paths:
            QMessageBox.warning(self, "Aviso", "Nenhum arquivo CSV selecionado para análise.")
            return

        self.app_state.status_message_changed.emit("Carregando dados...", 0)
        QApplication.processEvents()
        
        runs, errors = processing_service.process_run_files(file_paths)
        
        if errors: QMessageBox.warning(self, "Avisos durante o Processamento", "\\n".join(errors))
        if not runs:
            QMessageBox.critical(self, "Erro Fatal", "Nenhum arquivo pôde ser processado com sucesso.")
            return
            
        self.app_state.update_analysis_results(runs)
        self.view_stack.setCurrentIndex(1)
        self.app_state.status_message_changed.emit("Dados carregados. Filtros são independentes por gráfico.", 5000)
    
    def _populate_table(self, table_widget: QTableWidget, df: pd.DataFrame):
        table_widget.clear()
        if df.empty:
            table_widget.setRowCount(0)
            table_widget.setColumnCount(0)
            return

        table_widget.setRowCount(df.shape[0])
        table_widget.setColumnCount(df.shape[1])
        table_widget.setHorizontalHeaderLabels(df.columns)
        table_widget.setVerticalHeaderLabels(df.index.astype(str))

        for row in range(df.shape[0]):
            for col in range(df.shape[1]):
                value = df.iat[row, col]
                item = QTableWidgetItem(f"{value:.2f}")
                table_widget.setItem(row, col, item)
        
        header = table_widget.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table_widget.resizeRowsToContents()

    def update_statistics_view(self):
        if 'velocidade' in self.reportable_widgets and self.app_state.raw_runs:
            filter_settings = self.reportable_widgets['velocidade'].filter_settings
            metrics_df, variations_df = processing_service.generate_statistics(
                self.app_state.raw_runs, filter_settings
            )
            
            self._populate_table(self.metrics_table, metrics_df)
            self._populate_table(self.variations_table, variations_df)
            self.comparison_plot.update_plot(metrics_df)
        else:
            self._populate_table(self.metrics_table, pd.DataFrame())
            self._populate_table(self.variations_table, pd.DataFrame())
            self.comparison_plot.update_plot(pd.DataFrame())


    def _get_all_figures(self) -> dict:
        figures_pixmap = {}
        for key, widget in self.reportable_widgets.items():
            if hasattr(widget, 'get_figure_for_report'):
                fig_bytes = widget.get_figure_for_report()
                if fig_bytes:
                    pixmap = QPixmap()
                    pixmap.loadFromData(fig_bytes)
                    if not pixmap.isNull():
                        figures_pixmap[key] = pixmap
        return figures_pixmap

    def save_report(self):
        if not self.app_state.raw_runs:
            QMessageBox.warning(self, "Aviso", "Execute uma análise primeiro.")
            return
        
        save_path, _ = QFileDialog.getSaveFileName(self, "Salvar Relatório PDF", "", "PDF files (*.pdf)")
        if not save_path: return
        
        report_data = self.controls_panel.get_report_data()
        
        filter_settings = self.reportable_widgets['velocidade'].filter_settings
        metrics_df, variations_df = processing_service.generate_statistics(self.app_state.raw_runs, filter_settings)

        report_service.generate_pdf_report(
            save_path=save_path,
            setup_info=report_data['setup_info'],
            observations=report_data['observations'],
            filter_settings=filter_settings,
            metrics_df=metrics_df,
            variations_df=variations_df,
            figures=self._get_all_figures()
        )

    def export_to_excel(self):
        if not self.app_state.raw_runs:
            QMessageBox.warning(self, "Aviso", "Execute uma análise primeiro.")
            return

        save_path, _ = QFileDialog.getSaveFileName(self, "Salvar Dashboard em Excel", "", "Excel files (*.xlsx)")
        if not save_path:
            return

        self.app_state.status_message_changed.emit("Gerando Dashboard Excel...", 0)
        QApplication.processEvents()

        try:
            # Coleta todos os dados necessários para o relatório
            report_data = self.controls_panel.get_report_data()
            setup_info = report_data.get('setup_info', {})
            observations = report_data.get('observations', '')

            filter_settings = self.reportable_widgets['velocidade'].filter_settings
            metrics_df, variations_df = processing_service.generate_statistics(
                self.app_state.raw_runs, filter_settings
            )

            # Chama a nova função de exportação para criar o dashboard
            file_service.export_to_dashboard_excel(
                runs=self.app_state.raw_runs,
                save_path=save_path,
                metrics_df=metrics_df,
                variations_df=variations_df,
                filter_settings=filter_settings,
                setup_info=setup_info,
                observations=observations
            )
            # A mensagem de sucesso agora vem da própria função de exportação

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível gerar o Dashboard Excel.\nErro: {e}\n\n{traceback.format_exc()}")
            self.app_state.status_message_changed.emit("Falha ao gerar Dashboard.", 5000)


    def toggle_theme(self):
        new_theme = LIGHT_THEME if self.current_theme == DEFAULT_THEME else DEFAULT_THEME
        apply_stylesheet(QApplication.instance(), theme=new_theme)
        self.current_theme = new_theme