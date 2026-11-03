"""Janela principal. Só orquestra: trabalho pesado roda em `Worker`s; estado vive na `Session`."""

from __future__ import annotations

import logging
import os

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow, QMenu, QMessageBox, QPushButton,
    QStackedWidget, QStatusBar, QVBoxLayout, QWidget,
)

from .. import APP_NAME, __version__
from ..application.analysis import full_analysis
from ..application.loading import load_runs
from ..application.ports import ReportContext
from ..domain.errors import MangueLoggerError
from ..domain.models import VehicleProfile
from ..infrastructure.exporters import get_exporter
from ..infrastructure.readers.csv_reader import CsvRunReader
from ..infrastructure.readers.dll_reader import generate_csv_from_dll
from ..infrastructure.storage.project_file import load_project, save_project
from .app_state import AppState
from .controls_panel import ControlsPanel
from .panels.analysis_view import WS, AnalysisWidget
from .theme import Theme
from .workers import TaskManager

APP_VERSION = f"v{__version__}"
log = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, state: AppState, tasks: TaskManager | None = None):
        super().__init__()
        self.state = state
        self.tasks = tasks or TaskManager()
        self.setWindowTitle(f"{APP_NAME}  {APP_VERSION}")
        icon = os.path.join(os.path.dirname(__file__), "resources", "logo.ico")
        if os.path.isfile(icon):
            self.setWindowIcon(QIcon(icon))
        self.resize(1720, 960)
        self.setMinimumSize(1100, 640)
        self._build_status()
        self._build_ui()
        self._connect()

    # ── status bar ────────────────────────────────────────────────────────────
    def _build_status(self):
        sb = QStatusBar(self); sb.setFixedHeight(28); self.setStatusBar(sb)
        self._dot = QLabel("●")
        self._dot.setStyleSheet(f"color:{Theme.TEXT_DIM};font-size:11px;margin:0 8px;")
        sb.addPermanentWidget(self._dot)
        self._intel_lbl = QLabel("")
        self._intel_lbl.setStyleSheet(f"color:{Theme.ACCENT2};font-size:9px;margin:0 12px;font-family:{Theme.FONT_MONO};background:transparent;")
        sb.addPermanentWidget(self._intel_lbl)
        self._dt = QTimer(self); self._dt.setSingleShot(True)
        self._dt.timeout.connect(lambda: self._dot.setStyleSheet(f"color:{Theme.TEXT_DIM};font-size:11px;margin:0 8px;"))

    # ── UI ────────────────────────────────────────────────────────────────────


    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        root = QVBoxLayout(central); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        # Brand bar
        brand = QFrame(); brand.setFixedHeight(50); brand.setObjectName("BrandBar")
        hl = QHBoxLayout(brand); hl.setContentsMargins(18,0,18,0); hl.setSpacing(12)
        ico = QLabel("▲"); ico.setStyleSheet(f"color:{Theme.ACCENT};font-size:20px;font-weight:bold;background:transparent;"); hl.addWidget(ico)
        nm = QLabel(APP_NAME); nm.setStyleSheet(f"color:{Theme.TEXT_PRI};font-size:15px;font-weight:bold;letter-spacing:4px;background:transparent;"); hl.addWidget(nm)
        vr = QLabel(APP_VERSION); vr.setStyleSheet(f"color:{Theme.ACCENT_DIM};font-size:9px;background:transparent;margin-top:8px;letter-spacing:1px;border:1px solid {Theme.ACCENT_DIM};border-radius:3px;padding:1px 5px;"); hl.addWidget(vr)
        hl.addStretch()
        _bss = (f"QPushButton{{background:{Theme.BG_SURFACE};border:1px solid {Theme.BORDER_LT};border-radius:7px;color:{Theme.TEXT_SEC};padding:0 16px;font-size:11px;font-weight:bold;}}"
                f"QPushButton:hover{{background:{Theme.HOVER};color:{Theme.ACCENT};border-color:{Theme.ACCENT_DIM};}}")
        self._btn_pdf   = QPushButton("📄  PDF");   self._btn_pdf.setFixedHeight(32);   self._btn_pdf.setStyleSheet(_bss)
        self._btn_excel = QPushButton("📊  Excel"); self._btn_excel.setFixedHeight(32); self._btn_excel.setStyleSheet(_bss)
        self._btn_json  = QPushButton("{}  JSON");  self._btn_json.setFixedHeight(32);  self._btn_json.setStyleSheet(_bss)
        self._btn_csv   = QPushButton("⬇  CSV");   self._btn_csv.setFixedHeight(32);   self._btn_csv.setStyleSheet(_bss)
        self._btn_proj  = QPushButton("📁  Projeto"); self._btn_proj.setFixedHeight(32); self._btn_proj.setStyleSheet(_bss)
        self._btn_prof  = QPushButton("🚗  Perfil");  self._btn_prof.setFixedHeight(32); self._btn_prof.setStyleSheet(_bss)
        hl.addWidget(self._btn_proj); hl.addWidget(self._btn_prof)
        hl.addWidget(self._btn_pdf); hl.addWidget(self._btn_excel)
        hl.addWidget(self._btn_json); hl.addWidget(self._btn_csv)
        root.addWidget(brand)

        # Stack
        self._stack = QStackedWidget()
        self._ctrl  = ControlsPanel()
        self._anal  = AnalysisWidget()
        self._stack.addWidget(self._ctrl)
        self._stack.addWidget(self._anal)
        root.addWidget(self._stack, 1)

        # Tab bar
        tab = QFrame(); tab.setFixedHeight(42); tab.setObjectName("TabBar")
        thl = QHBoxLayout(tab); thl.setContentsMargins(0,0,0,0); thl.setSpacing(0)
        self._tabs: list[QPushButton] = []
        for i, name in enumerate(["  ⚙  Controles", "  📈  Análise"]):
            b = QPushButton(name); b.setObjectName("Tab"); b.setCheckable(True)
            b.setFixedHeight(42); b.setMinimumWidth(150)
            b.clicked.connect(lambda _, idx=i: self._select_tab(idx))
            self._tabs.append(b); thl.addWidget(b)
        thl.addStretch()
        root.addWidget(tab)
        self._select_tab(0)


    def _select_tab(self, idx: int):
        self._stack.setCurrentIndex(idx)
        for i, b in enumerate(self._tabs): b.setChecked(i == idx)


    # ── signals ───────────────────────────────────────────────────────────────

    def _connect(self):
        self._ctrl.analysis_requested.connect(self._run_analysis)
        self._ctrl.csv_generation_requested.connect(self._gen_csv)
        self.state.status_message.connect(self._on_status)
        self._anal.link_state(self.state)
        for btn, ext in ((self._btn_pdf, ".pdf"), (self._btn_excel, ".xlsx"),
                         (self._btn_json, ".json"), (self._btn_csv, ".csv")):
            btn.clicked.connect(lambda _=False, e=ext: self._export(e))
        menu = QMenu(self._btn_proj)
        menu.addAction("💾  Salvar projeto…", self._save_project)
        menu.addAction("📂  Abrir projeto…", self._open_project)
        self._btn_proj.setMenu(menu)
        self._btn_prof.clicked.connect(self._load_profile)

    def _on_status(self, msg: str, timeout: int):
        self.statusBar().showMessage(msg, timeout)
        color = Theme.ACCENT if timeout == 0 else Theme.SUCCESS
        self._dot.setStyleSheet(f"color:{color};font-size:11px;margin:0 8px;")
        if timeout > 0:
            self._dt.start(timeout)

    def _status(self, msg: str, timeout: int = 0):
        self.state.status_message.emit(msg, timeout)

    def _fail(self, title: str):
        def handler(msg: str, tb: str):
            log.error("%s: %s\n%s", title, msg, tb)
            self._status(f"✗  {title}", 6000)
            box = QMessageBox(QMessageBox.Icon.Critical, title, msg, parent=self)
            box.setDetailedText(tb)
            box.exec()
        return handler

    # ── análise ───────────────────────────────────────────────────────────────

    def _run_analysis(self, data: dict):
        paths = data.get("file_paths", [])
        if not paths:
            QMessageBox.warning(self, "Aviso", "Nenhum CSV selecionado.")
            return
        self._load_paths(paths)

    def _load_paths(self, paths: list[str]):
        sess = self.state.session
        reader = CsvRunReader(sess.profile.sensor)
        self._status("Carregando dados…", 0)
        self._ctrl.setEnabled(False)

        def job(progress, cancel):
            return load_runs(paths, reader, sess.processing, sess.profile, progress, cancel)

        self.tasks.submit(
            job, on_result=self._on_loaded, on_error=self._fail("Falha ao carregar"),
            on_progress=lambda d, n: self._status(f"Carregando dados… {d}/{n}", 0),
            on_finished=lambda: self._ctrl.setEnabled(True))

    def _on_loaded(self, result):
        if result.errors:
            QMessageBox.warning(self, "Avisos", "\n".join(result.errors))
        if not result.runs:
            QMessageBox.critical(self, "Erro", "Nenhum arquivo processado.")
            return
        quality = [f"{r.file_name}: {w}" for r in result.runs for w in r.run.quality.warnings]
        self.state.load(result.runs)
        self._select_tab(1)
        self._status(f"✓  {len(result.runs)} arquivo(s) carregado(s).", 6000)
        if quality:
            QMessageBox.information(self, "Qualidade dos dados", "\n".join(quality))
        self._bg_intel()

    def _bg_intel(self):
        sess = self.state.session
        if not sess.runs:
            return
        runs, fs, prof = list(sess.runs), self._anal.filter_settings, sess.profile

        def done(res):
            ins = res.get("insights", [])
            nw = sum(1 for i in ins if i.level in ("warning", "critical"))
            ng = sum(1 for i in ins if i.level == "good")
            self._intel_lbl.setText(f"🧠 {len(ins)} insights" + (f"  ⚠ {nw}" if nw else "") + (f"  ✅ {ng}" if ng else ""))

        self.tasks.submit(lambda progress, cancel: full_analysis(runs, fs, prof), on_result=done,
                          on_error=lambda m, tb: log.warning("[Intel] %s", m))

    # ── CSV via DLL ───────────────────────────────────────────────────────────

    def _gen_csv(self, d: dict):
        rn = d.get("run_num", "")
        if not all([d.get("run_dir"), rn, d.get("save_dir")]):
            QMessageBox.warning(self, "Inválido", "Preencha todos os campos.")
            return
        if not rn.isnumeric():
            QMessageBox.warning(self, "Inválido", "Número da RUN deve ser numérico.")
            return
        self._status(f"Gerando CSV da RUN {rn}…", 0)

        def job(progress, cancel):
            generate_csv_from_dll(d["run_dir"], d["save_dir"], rn)

        self.tasks.submit(job, on_result=lambda _: (self._status("✓  CSV gerado.", 5000),
                                                    QMessageBox.information(self, "Sucesso", f"CSV da RUN {rn} gerado em:\n{d['save_dir']}")),
                          on_error=self._fail("Erro ao gerar CSV"))

    # ── exportação (qualquer formato registrado) ──────────────────────────────

    def _export(self, ext: str):
        sess = self.state.session
        if not sess.runs:
            QMessageBox.warning(self, "Aviso", "Execute uma análise primeiro.")
            return
        exporter = get_exporter(ext)
        path, _ = QFileDialog.getSaveFileName(self, f"Exportar {exporter.name}", "", f"{exporter.name} (*{ext})")
        if not path:
            return
        rd = self._ctrl.get_report_data()
        figures = {}
        if ext == ".pdf":  # captura de widget precisa da thread da UI
            fig = self._anal.get_figure_for_report()
            if fig:
                figures["analise"] = fig
        ctx = ReportContext(runs=list(sess.runs), filter_settings=self._anal.filter_settings,
                            setup_info=rd["setup_info"], observations=rd["observations"], figures=figures)
        self._status(f"Gerando {exporter.name}…", 0)
        self.tasks.submit(lambda progress, cancel: exporter.export(ctx, path),
                          on_result=lambda _: self._status(f"✓  {exporter.name} salvo.", 5000),
                          on_error=self._fail(f"Erro ao exportar {exporter.name}"))

    # ── projeto / perfil ──────────────────────────────────────────────────────

    def _save_project(self):
        sess = self.state.session
        if not sess.runs:
            QMessageBox.warning(self, "Aviso", "Carregue runs antes de salvar o projeto.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Salvar projeto", "", "Projeto Mangue Logger (*.mlproj)")
        if not path:
            return
        rd = self._ctrl.get_report_data()
        sess.setup_info, sess.observations = rd["setup_info"], rd["observations"]
        sess.filter_settings = self._anal.filter_settings
        try:
            save_project(path, sess, [v.to_dict() for v in WS.list_virtuals()])
        except OSError as exc:
            QMessageBox.critical(self, "Erro", str(exc))
            return
        self._status("✓  Projeto salvo.", 5000)

    def _open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "Abrir projeto", "", "Projeto Mangue Logger (*.mlproj)")
        if not path:
            return
        try:
            proj = load_project(path)
        except (MangueLoggerError, OSError, ValueError) as exc:
            QMessageBox.critical(self, "Projeto inválido", str(exc))
            return
        from ..application.virtual_channels import VirtualChannel
        for d in proj.virtual_channels:
            try:
                WS.save_virtual(VirtualChannel.from_dict(d))
            except MangueLoggerError:
                log.warning("canal virtual do projeto ignorado: %r", d.get("name"))
        sess = self.state.session
        sess.set_profile(proj.profile)
        sess.setup_info, sess.observations = proj.setup_info, proj.observations
        self._ctrl.set_report_data(proj.setup_info, proj.observations)
        sess.set_filter(proj.filter_settings or sess.filter_settings)
        notes = []
        if proj.missing:
            notes.append("Arquivos não encontrados:\n  " + "\n  ".join(proj.missing))
        if proj.changed:
            notes.append("Arquivos modificados desde que o projeto foi salvo:\n  " + "\n  ".join(proj.changed))
        if notes:
            QMessageBox.warning(self, "Projeto", "\n\n".join(notes))
        if proj.run_paths:
            self._load_paths(proj.run_paths)

    def _load_profile(self):
        path, _ = QFileDialog.getOpenFileName(self, "Carregar perfil do veículo", "", "Perfil (*.json)")
        if not path:
            return
        import json
        try:
            with open(path, encoding="utf-8") as f:
                profile = VehicleProfile.from_dict(json.load(f))
        except (MangueLoggerError, OSError, ValueError) as exc:
            QMessageBox.critical(self, "Perfil inválido", str(exc))
            return
        self.state.session.set_profile(profile)
        self._status(f"✓  Perfil “{profile.name}” ativo. Recarregue os CSVs para aplicar o sensor.", 7000)
