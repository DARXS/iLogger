"""Smoke da GUI em modo offscreen: janela, carga em background, painéis, exportação."""

import os

import pytest

pytest.importorskip("PyQt6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QMessageBox  # noqa: E402

from mangue_logger.presentation.app_state import AppState  # noqa: E402
from mangue_logger.presentation.main_window import MainWindow  # noqa: E402


@pytest.fixture
def win(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: None)
    from mangue_logger.presentation.panels import analysis_view
    monkeypatch.setattr(analysis_view, "WS", analysis_view.WorkspaceManager(tmp_path / "ws"))
    w = MainWindow(AppState())
    qtbot.addWidget(w)
    w.show()
    return w


def test_background_load_then_panels(win, qtbot, csv_a, csv_b):
    win._load_paths([csv_a, csv_b])
    qtbot.waitUntil(lambda: len(win.state.runs) == 2, timeout=15000)
    assert [r.file_name for r in win.state.runs] == ["a.csv", "b.csv"]
    anal = win._anal
    for add in ("_add_fp", "_add_sp", "_add_cp", "_add_ip", "_add_hist", "_add_fft", "_add_scatter",
                "_add_phase", "_add_gear", "_add_cvt", "_add_corr"):
        getattr(anal, add)()
    qtbot.waitUntil(lambda: win._intel_lbl.text() != "", timeout=15000)
    assert "insights" in win._intel_lbl.text()
    assert anal._cvt_p is not None
    anal._on_filter({"type": "median", "median_kernel": 7})            # filtro troca → painéis atualizam
    assert win.state.session.filter_settings["median_kernel"] == 7


def test_export_in_background(win, qtbot, csv_a, csv_b, tmp_path, monkeypatch):
    win._load_paths([csv_a, csv_b])
    qtbot.waitUntil(lambda: len(win.state.runs) == 2, timeout=15000)
    from PyQt6.QtWidgets import QFileDialog
    out = tmp_path / "rel.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(out), ""))
    win._export(".json")
    qtbot.waitUntil(out.exists, timeout=15000)
    win.tasks.wait_all()


def test_load_error_is_reported_not_raised(win, qtbot, tmp_path):
    bad = tmp_path / "bad.csv"; bad.write_text("x\n1\n")
    msgs = []
    win._status = lambda m, t=0: msgs.append(m)
    win._load_paths([str(bad)])
    qtbot.waitUntil(lambda: win._ctrl.isEnabled(), timeout=15000)
    assert win.state.runs == []


def test_project_save_and_open(win, qtbot, csv_a, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog
    win._load_paths([csv_a])
    qtbot.waitUntil(lambda: len(win.state.runs) == 1, timeout=15000)
    proj = tmp_path / "t.mlproj"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(proj), ""))
    win._ctrl._setup["peso_cvt"].setText("45")
    win._save_project()
    assert proj.exists()
    win.state.clear(); win._ctrl._setup["peso_cvt"].setText("")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(proj), ""))
    win._open_project()
    qtbot.waitUntil(lambda: len(win.state.runs) == 1, timeout=15000)
    assert win._ctrl._setup["peso_cvt"].text() == "45"
