# iLogger/ui/widgets/controls_panel.py

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QListWidget, QTextEdit, QGroupBox, QGridLayout, QMessageBox
)
from PyQt6.QtCore import QSettings, pyqtSignal

class ControlsPanel(QWidget):
    """
    Widget principal da primeira tela (Controles). Coleta todas as
    informações de entrada e emite sinais para iniciar as ações.
    """
    analysis_requested = pyqtSignal(dict)
    csv_generation_requested = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        
        main_layout = QVBoxLayout(self)
        
        # Layout superior com 3 colunas de grupos
        top_layout = QHBoxLayout()
        top_layout.addWidget(self._create_setup_group(), stretch=2)
        top_layout.addWidget(self._create_analysis_files_group(), stretch=3)
        
        main_layout.addLayout(top_layout)
        
        # Layout inferior 
        bottom_layout = QHBoxLayout()
        bottom_layout.addWidget(self._create_file_management_group())
        bottom_layout.addWidget(self._create_observations_group(), stretch=1)
        
        main_layout.addLayout(bottom_layout)

    def _create_setup_group(self):
        group = QGroupBox("Setup do Veículo")
        layout = QGridLayout(group)
        self.setup_inputs = {}
        inputs_labels = {
            "rpm_baixa": "RPM do Motor (Baixa):", "rpm_alta": "RPM do Motor (Alta):",
            "peso_cvt": "Peso na CVT (gramas):", "const_mola": "Constante da Mola (N/m):",
            "ang_rampa": "Angulação da Rampa (graus):", "data": "Data:"
        }
        for i, (key, label_text) in enumerate(inputs_labels.items()):
            self.setup_inputs[key] = QLineEdit()
            layout.addWidget(QLabel(label_text), i, 0)
            layout.addWidget(self.setup_inputs[key], i, 1)
        return group

    def _create_file_management_group(self):
        group = QGroupBox("Gerenciamento de CSV (Opcional)")
        layout = QGridLayout(group)

        self.txt_run_dir = QLineEdit()
        self.txt_save_dir = QLineEdit()
        self.txt_run_num = QLineEdit()
        btn_run_dir = QPushButton("Procurar")
        btn_save_dir = QPushButton("Procurar")
        self.btn_generate_csv = QPushButton("Gerar CSV Processado")
        
        btn_run_dir.clicked.connect(lambda: self._select_directory(self.txt_run_dir, "last_run_directory"))
        btn_save_dir.clicked.connect(lambda: self._select_directory(self.txt_save_dir, "last_save_directory"))
        self.btn_generate_csv.clicked.connect(self._on_generate_csv_clicked)

        layout.addWidget(QLabel("Diretório das RUNs:"), 0, 0)
        layout.addWidget(self.txt_run_dir, 0, 1)
        layout.addWidget(btn_run_dir, 0, 2)
        layout.addWidget(QLabel("Diretório de Salvamento:"), 1, 0)
        layout.addWidget(self.txt_save_dir, 1, 1)
        layout.addWidget(btn_save_dir, 1, 2)
        layout.addWidget(QLabel("Número da RUN:"), 2, 0)
        layout.addWidget(self.txt_run_num, 2, 1)
        layout.addWidget(self.btn_generate_csv, 3, 0, 1, 3)
        return group

    def _create_analysis_files_group(self):
        group = QGroupBox("Arquivos para Análise")
        layout = QVBoxLayout(group)
        self.list_files = QListWidget()
        self.btn_select_files = QPushButton("Selecionar Arquivos CSV para Análise")
        
        self.btn_run_analysis = QPushButton("Rodar Análise")
        font = self.btn_run_analysis.font()
        font.setBold(True)
        self.btn_run_analysis.setFont(font)
        
        self.btn_select_files.clicked.connect(self._select_analysis_files)
        self.btn_run_analysis.clicked.connect(self._on_run_analysis_clicked)

        layout.addWidget(self.btn_select_files)
        layout.addWidget(self.list_files)
        layout.addWidget(self.btn_run_analysis)
        return group
    
    def _create_observations_group(self):
        group = QGroupBox("Observações para o Relatório")
        layout = QVBoxLayout(group)
        self.txt_observation = QTextEdit()
        self.txt_observation.setPlaceholderText("Insira observações sobre os testes aqui...")
        layout.addWidget(self.txt_observation)
        return group

    def _select_directory(self, line_edit, settings_key):
        settings = QSettings("MangueBaja", "iLogger")
        last_dir = settings.value(settings_key, os.path.expanduser("~"))
        directory = QFileDialog.getExistingDirectory(self, "Selecione o diretório", last_dir)
        if directory:
            line_edit.setText(directory)
            settings.setValue(settings_key, directory)

    def _select_analysis_files(self):
        settings = QSettings("MangueBaja", "iLogger")
        last_dir = settings.value("last_plot_directory", os.path.expanduser("~"))
        filenames, _ = QFileDialog.getOpenFileNames(self, "Selecione os arquivos de RUN para análise", last_dir, "CSV files (*.csv)")
        if filenames:
            self.list_files.clear()
            self.list_files.addItems(filenames)
            settings.setValue("last_plot_directory", os.path.dirname(filenames[0]))
    
    def _on_generate_csv_clicked(self):
        self.csv_generation_requested.emit({
            "run_dir": self.txt_run_dir.text(),
            "run_num": self.txt_run_num.text(),
            "save_dir": self.txt_save_dir.text()
        })

    def _on_run_analysis_clicked(self):
        file_paths = [self.list_files.item(i).text() for i in range(self.list_files.count())]
        
        if not file_paths:
            QMessageBox.warning(self, "Aviso", "Nenhum arquivo selecionado para análise.")
            return

        # O painel de filtros não está mais aqui, então não precisamos buscar suas configurações
        analysis_data = { "file_paths": file_paths }
        self.analysis_requested.emit(analysis_data)
        
    def get_report_data(self):
        return {
            "setup_info": {key: widget.text() for key, widget in self.setup_inputs.items()},
            "observations": self.txt_observation.toPlainText()
        }