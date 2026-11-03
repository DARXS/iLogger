"""Painel de controles (setup, geração de CSV, seleção de arquivos)."""

from __future__ import annotations

import os

from PyQt6.QtCore import QSettings, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .theme import Theme

SETTINGS_ORG = "MangueBaja"
SETTINGS_APP = "MangueLogger"


class ControlsPanel(QWidget):
    analysis_requested      = pyqtSignal(dict)
    csv_generation_requested = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QHBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        left = QVBoxLayout(); left.setSpacing(14)
        left.addWidget(self._card_setup())
        left.addWidget(self._card_csv())
        left.addStretch()
        root.addLayout(left, 3)

        right = QVBoxLayout(); right.setSpacing(14)
        right.addWidget(self._card_files(), 1)
        right.addWidget(self._card_obs())
        root.addLayout(right, 4)

    # ── cards ─────────────────────────────────────────────────────────────────

    def _card_setup(self) -> QGroupBox:
        g = QGroupBox("Setup do Veículo")
        vl = QVBoxLayout(g); vl.setSpacing(8)
        self._setup: dict[str, QLineEdit] = {}
        for key, lbl in [("rpm_baixa","RPM motor (baixa)"),("rpm_alta","RPM motor (alta)"),
                          ("peso_cvt","Peso CVT (g)"),("const_mola","Constante mola (N/m)"),
                          ("ang_rampa","Angulação rampa (°)"),("data","Data")]:
            inp = QLineEdit(); inp.setPlaceholderText("—")
            self._setup[key] = inp
            row = QHBoxLayout()
            lbl_w = QLabel(lbl); lbl_w.setFixedWidth(195)
            lbl_w.setStyleSheet(f"color:{Theme.TEXT_SEC};font-size:10px;background:transparent;")
            row.addWidget(lbl_w); row.addWidget(inp, 1); vl.addLayout(row)
        return g

    def _card_csv(self) -> QGroupBox:
        g = QGroupBox("Geração de CSV (DLL)")
        vl = QVBoxLayout(g); vl.setSpacing(8)

        def dir_row(attr, lbl_txt, setting):
            inp = QLineEdit(); inp.setPlaceholderText("Selecionar diretório…")
            setattr(self, attr, inp)
            btn = QPushButton("Procurar"); btn.setFixedHeight(28)
            btn.clicked.connect(lambda: self._pick_dir(inp, setting))
            row = QHBoxLayout()
            lb = QLabel(lbl_txt); lb.setFixedWidth(195)
            lb.setStyleSheet(f"color:{Theme.TEXT_SEC};font-size:10px;background:transparent;")
            row.addWidget(lb); row.addWidget(inp,1); row.addWidget(btn); vl.addLayout(row)

        dir_row("_run_dir",  "Diretório das RUNs",    "last_run_dir")
        dir_row("_save_dir", "Diretório de saída",     "last_save_dir")

        self._run_num = QLineEdit(); self._run_num.setPlaceholderText("ex: 42")
        row = QHBoxLayout()
        rn_lb = QLabel("Número da RUN"); rn_lb.setFixedWidth(195)
        rn_lb.setStyleSheet(f"color:{Theme.TEXT_SEC};font-size:10px;background:transparent;")
        row.addWidget(rn_lb); row.addWidget(self._run_num,1); vl.addLayout(row)

        btn = QPushButton("⚙  Gerar CSV"); btn.setObjectName("CTA"); btn.setFixedHeight(34)
        btn.clicked.connect(self._on_csv); vl.addWidget(btn)
        return g

    def _card_files(self) -> QGroupBox:
        g = QGroupBox("Arquivos para Análise")
        vl = QVBoxLayout(g); vl.setSpacing(8)
        btn_sel = QPushButton("+ Selecionar arquivos CSV"); btn_sel.setFixedHeight(30)
        btn_sel.clicked.connect(self._pick_files); vl.addWidget(btn_sel)
        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self._list.setToolTip("Arraste para reordenar. Primeira run = base de comparação.")
        vl.addWidget(self._list, 1)
        bot = QHBoxLayout()
        self._cnt = QLabel("0 arquivos"); self._cnt.setStyleSheet(f"color:{Theme.TEXT_DIM};font-size:10px;background:transparent;")
        bot.addWidget(self._cnt); bot.addStretch()
        btn_run = QPushButton("▶  Rodar Análise"); btn_run.setObjectName("CTA")
        btn_run.setFixedHeight(36); btn_run.setMinimumWidth(160)
        btn_run.clicked.connect(self._on_run); bot.addWidget(btn_run); vl.addLayout(bot)
        self._list.model().rowsInserted.connect(self._upd_cnt)
        self._list.model().rowsRemoved.connect(self._upd_cnt)
        return g

    def _card_obs(self) -> QGroupBox:
        g = QGroupBox("Observações do Relatório"); g.setMaximumHeight(160)
        vl = QVBoxLayout(g)
        self._obs = QTextEdit(); self._obs.setPlaceholderText("Condições do teste, ajustes, etc…")
        self._obs.setMinimumHeight(80); vl.addWidget(self._obs)
        return g

    # ── helpers ───────────────────────────────────────────────────────────────

    def _pick_dir(self, inp: QLineEdit, setting: str):
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        d = QFileDialog.getExistingDirectory(self, "Selecionar", s.value(setting, os.path.expanduser("~")))
        if d: inp.setText(d); s.setValue(setting, d)

    def _pick_files(self):
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        files, _ = QFileDialog.getOpenFileNames(self,"Selecionar CSVs",s.value("last_plot_dir","~"),"CSV (*.csv)")
        if files:
            self._list.clear(); self._list.addItems(files)
            s.setValue("last_plot_dir", os.path.dirname(files[0]))

    def _upd_cnt(self):
        n = self._list.count()
        self._cnt.setText("Nenhum arquivo" if n == 0 else f"{n} arquivo{'s' if n>1 else ''}")

    def _on_csv(self):
        self.csv_generation_requested.emit({
            "run_dir":  self._run_dir.text(),
            "run_num":  self._run_num.text(),
            "save_dir": self._save_dir.text(),
        })

    def _on_run(self):
        paths = [self._list.item(i).text() for i in range(self._list.count())]
        if not paths: QMessageBox.warning(self,"Aviso","Nenhum arquivo selecionado."); return
        self.analysis_requested.emit({"file_paths": paths})

    def get_report_data(self) -> dict:
        return {"setup_info": {k: w.text() for k, w in self._setup.items()},
                "observations": self._obs.toPlainText()}



    def set_report_data(self, setup_info: dict, observations: str) -> None:
        for k, w in self._setup.items():
            w.setText(str(setup_info.get(k, "")))
        self._obs.setPlainText(observations or "")

