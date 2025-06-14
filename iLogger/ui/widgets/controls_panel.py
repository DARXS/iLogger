# iLogger/ui/widgets/controls_panel.py

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QGroupBox, QLabel,
    QLineEdit, QPushButton, QFileDialog, QMessageBox, QHBoxLayout, QStyle
)
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QIcon
from services import file_service

class ControlsPanel(QWidget):
    analysis_requested = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.file_paths = []
        self._init_ui()
        self.setStyleSheet(self._get_compact_stylesheet())

    def _get_compact_stylesheet(self):
        """Retorna um QSS para um estilo compacto e moderno."""
        return """
        QWidget {
            font-size: 9pt;
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid #C8C8C8;
            border-radius: 5px;
            margin-top: 8px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 4px 0 4px;
            left: 10px;
        }
        QLineEdit {
            border: 1px solid #C8C8C8;
            padding: 3px;
            border-radius: 3px;
        }
        QLineEdit:read-only {
            background-color: #EFEFEF;
        }
        QPushButton {
            border: 1px solid #C8C8C8;
            padding: 3px 10px 3px 10px;
            border-radius: 3px;
            background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                            stop: 0 #F8F8F8, stop: 1 #E8E8E8);
        }
        QPushButton:hover {
            background-color: #E0E0E0;
        }
        #PrimaryButton {
            background-color: #0078D7;
            color: white;
            font-weight: bold;
            border: none;
        }
        #PrimaryButton:hover {
            background-color: #005A9E;
        }
        """

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # --- Grupo de Setup Geral ---
        setup_group = QGroupBox("Setup Geral e Condições")
        setup_layout = QGridLayout()
        self.line_edit_piloto = QLineEdit()
        self.line_edit_pista = QLineEdit()
        setup_layout.addWidget(QLabel("Piloto:"), 0, 0)
        setup_layout.addWidget(self.line_edit_piloto, 0, 1)
        setup_layout.addWidget(QLabel("Pista:"), 0, 2)
        setup_layout.addWidget(self.line_edit_pista, 0, 3)
        setup_layout.setColumnStretch(1, 1)
        setup_layout.setColumnStretch(3, 1)
        setup_group.setLayout(setup_layout)
        main_layout.addWidget(setup_group)

        # --- Grupo de Setup do CVT ---
        cvt_group = QGroupBox("Setup do CVT (Opcional)")
        cvt_layout = QGridLayout()
        self.le_mola_constante = QLineEdit("0")
        self.le_pesos_roletes = QLineEdit("0")
        self.le_rampa_angulo = QLineEdit("0")
        self.le_rpm_engate = QLineEdit("0")
        self.le_rpm_final = QLineEdit("0")
        cvt_layout.addWidget(QLabel("Mola (k):"), 0, 0)
        cvt_layout.addWidget(self.le_mola_constante, 0, 1)
        cvt_layout.addWidget(QLabel("Roletes (g):"), 0, 2)
        cvt_layout.addWidget(self.le_pesos_roletes, 0, 3)
        cvt_layout.addWidget(QLabel("Rampa (°):"), 1, 0)
        cvt_layout.addWidget(self.le_rampa_angulo, 1, 1)
        cvt_layout.addWidget(QLabel("RPM Engate:"), 1, 2)
        cvt_layout.addWidget(self.le_rpm_engate, 1, 3)
        cvt_layout.addWidget(QLabel("RPM Final:"), 2, 0)
        cvt_layout.addWidget(self.le_rpm_final, 2, 1)
        cvt_group.setLayout(cvt_layout)
        main_layout.addWidget(cvt_group)

        # --- Layout Horizontal para as Ações ---
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(10)

        # --- Grupo de Análise Principal ---
        analysis_group = QGroupBox("Análise Completa")
        analysis_v_layout = QVBoxLayout()
        
        file_selection_layout = QHBoxLayout()
        self.btn_select_files = QPushButton("Selecionar RUNs")
        self.btn_select_files.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        self.selected_files_display = QLineEdit()
        self.selected_files_display.setPlaceholderText("Nenhum arquivo selecionado")
        self.selected_files_display.setReadOnly(True)
        file_selection_layout.addWidget(self.btn_select_files)
        file_selection_layout.addWidget(self.selected_files_display)
        
        self.btn_run_analysis = QPushButton("Executar Análise e Salvar no Histórico")
        self.btn_run_analysis.setObjectName("PrimaryButton")
        self.btn_run_analysis.setIcon(QIcon.fromTheme("document-save", self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)))

        analysis_v_layout.addLayout(file_selection_layout)
        analysis_v_layout.addWidget(self.btn_run_analysis)
        analysis_group.setLayout(analysis_v_layout)
        actions_layout.addWidget(analysis_group)

        # --- Grupo para Gerar CSV único ---
        csv_export_group = QGroupBox("Exportar CSV de RUN única")
        csv_export_layout = QGridLayout()
        self.le_run_dir = QLineEdit()
        self.le_run_num = QLineEdit()
        self.le_save_dir = QLineEdit()
        btn_browse_run_dir = QPushButton("...")
        btn_browse_save_dir = QPushButton("...")
        btn_generate_csv = QPushButton("Gerar")
        csv_export_layout.addWidget(QLabel("Dir. RUNs:"), 0, 0)
        csv_export_layout.addWidget(self.le_run_dir, 0, 1)
        csv_export_layout.addWidget(btn_browse_run_dir, 0, 2)
        csv_export_layout.addWidget(QLabel("Salvar em:"), 1, 0)
        csv_export_layout.addWidget(self.le_save_dir, 1, 1)
        csv_export_layout.addWidget(btn_browse_save_dir, 1, 2)
        csv_export_layout.addWidget(QLabel("Nº da RUN:"), 2, 0)
        csv_export_layout.addWidget(self.le_run_num, 2, 1)
        csv_export_layout.addWidget(btn_generate_csv, 2, 2)
        csv_export_group.setLayout(csv_export_layout)
        actions_layout.addWidget(csv_export_group)

        main_layout.addLayout(actions_layout)
        main_layout.addStretch()

        # Conectar Sinais
        self.btn_select_files.clicked.connect(self.select_files)
        self.btn_run_analysis.clicked.connect(self.run_analysis)
        btn_browse_run_dir.clicked.connect(self.browse_run_dir)
        btn_browse_save_dir.clicked.connect(self.browse_save_dir)
        btn_generate_csv.clicked.connect(self.generate_single_csv)

    def browse_run_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "Selecione o Diretório das RUNs")
        if directory: self.le_run_dir.setText(directory)

    def browse_save_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "Selecione o Diretório para Salvar")
        if directory: self.le_save_dir.setText(directory)

    def generate_single_csv(self):
        if not all([self.le_run_dir.text(), self.le_run_num.text(), self.le_save_dir.text()]):
            QMessageBox.warning(self, "Dados Incompletos", "Preencha todos os campos para gerar o CSV.")
            return
        file_service.generate_processed_csv(self.le_run_dir.text(), self.le_run_num.text(), self.le_save_dir.text())

    def select_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Selecione os arquivos de RUN", "", "CSV Files (*.csv)")
        if files:
            self.file_paths = files
            self.selected_files_display.setText(", ".join(os.path.basename(f) for f in files))
    
    def run_analysis(self):
        if not self.file_paths:
            QMessageBox.warning(self, "Aviso", "Nenhum arquivo CSV selecionado.")
            return
        self.analysis_requested.emit({
            "file_paths": self.file_paths,
            "setup_info": self.get_report_data()['setup_info']
        })
    
    def is_float(self, value_str: str):
        try:
            float(value_str)
            return True
        except (ValueError, TypeError):
            return False
            
    def _get_float_from_le(self, line_edit, default_value=0.0):
        text = line_edit.text().replace(',', '.').strip()
        return float(text) if self.is_float(text) else default_value

    def get_report_data(self):
        setup_info = {
            "Piloto": self.line_edit_piloto.text(),
            "Pista": self.line_edit_pista.text(),
            "Mola_k (N/mm)": self._get_float_from_le(self.le_mola_constante),
            "Roletes (g)": self._get_float_from_le(self.le_pesos_roletes),
            "Rampa (°)": self._get_float_from_le(self.le_rampa_angulo),
            "RPM_Engate": self._get_float_from_le(self.le_rpm_engate),
            "RPM_Final": self._get_float_from_le(self.le_rpm_final)
        }
        return {"setup_info": setup_info}