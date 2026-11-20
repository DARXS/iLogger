import json
import sys
import time

import pytest

from mangue_logger.application.loading import load_runs
from mangue_logger.application.ports import Cancelled, CancelToken
from mangue_logger.application.session import Session
from mangue_logger.application.virtual_channels import VirtualChannel
from mangue_logger.domain.errors import ExpressionError, ValidationError
from mangue_logger.domain.models import VehicleProfile
from mangue_logger.domain.pipeline import FilterConfig
from mangue_logger.infrastructure.exporters import get_exporter
from mangue_logger.infrastructure.readers import dll_reader
from mangue_logger.infrastructure.readers.csv_reader import CsvRunReader
from mangue_logger.infrastructure.storage.project_file import load_project, save_project
from mangue_logger.infrastructure.storage.run_library import RunLibrary
from mangue_logger.infrastructure.storage.workspace import WorkspaceManager


# ── loading ──────────────────────────────────────────────────────────────────
def test_load_runs_preserves_order_and_isolates_errors(csv_a, csv_b, tmp_path, profile):
    bad = tmp_path / "bad.csv"; bad.write_text("x,y\n1,2\n")
    sess, progress = Session(profile), []
    res = load_runs([csv_b, str(bad), csv_a], CsvRunReader(), sess.processing, profile,
                    on_progress=lambda d, n: progress.append((d, n)))
    assert [r.file_name for r in res.runs] == ["b.csv", "a.csv"] and len(res.errors) == 1
    assert progress[-1] == (3, 3)


def test_load_runs_cancel(csv_a, profile):
    tok = CancelToken(); tok.cancel()
    with pytest.raises(Cancelled):
        load_runs([csv_a] * 3, CsvRunReader(), Session().processing, profile, cancel=tok)


# ── workspace ────────────────────────────────────────────────────────────────
def test_workspace_has_no_import_side_effects(tmp_path):
    base = tmp_path / "ws"
    WorkspaceManager(base)
    assert not base.exists()                       # a v6 criava diretórios ao importar


def test_workspace_roundtrip_and_atomic_files(tmp_path):
    ws = WorkspaceManager(tmp_path / "ws")
    ws.save_preset("suave", {"type": "median"}); ws.save_layout("L1", {"x": 1})
    vc = VirtualChannel("ratio", "rpm / (vel + 1)", "rpm/kmh"); ws.save_virtual(vc)
    ws2 = WorkspaceManager(tmp_path / "ws")
    assert ws2.get_preset("suave") == {"type": "median"} and ws2.load_layout("L1")["x"] == 1
    assert [v.name for v in ws2.list_virtuals()] == ["ratio"]
    assert not list((tmp_path / "ws").glob("*.tmp"))


def test_workspace_rejects_unsafe_virtual_channel(tmp_path):
    ws = WorkspaceManager(tmp_path / "ws")
    with pytest.raises(ExpressionError):
        ws.save_virtual(VirtualChannel("evil", "__import__('os').system('x')"))


def test_import_drops_malicious_expressions_but_keeps_good_ones(tmp_path):
    f = tmp_path / "shared.json"
    f.write_text(json.dumps({"layouts": [], "presets": [], "virtuals": [
        {"name": "ok", "expression": "vel * 2"},
        {"name": "evil", "expression": "().__class__.__bases__"},
        {"name": "", "expression": "vel"}, "lixo"]}))
    ws = WorkspaceManager(tmp_path / "ws")
    assert ws.import_all(str(f)) == (0, 0, 1) and ws.last_import_skipped == 3
    assert [v.name for v in ws.list_virtuals()] == ["ok"]


def test_corrupt_workspace_file_does_not_crash(tmp_path):
    base = tmp_path / "ws"; base.mkdir(); (base / "presets.json").write_text("{{{")
    assert WorkspaceManager(base).list_presets() == []


def test_virtual_channel_cache_follows_filter(views):
    vc = VirtualChannel("v", "vel * 1")
    a = vc.evaluate(views[0], {"type": "butterworth", "butter_cutoff": 0.1})
    b = vc.evaluate(views[0], {"type": "butterworth", "butter_cutoff": 0.4})
    assert a is not None and b is not None and not (a == b).all()
    assert vc.evaluate(views[0], {"type": "butterworth", "butter_cutoff": 0.4}) is b


# ── projeto ──────────────────────────────────────────────────────────────────
def test_project_roundtrip_detects_missing_and_changed(views, tmp_path, csv_a):
    sess = Session(); sess.set_runs(views); sess.setup_info = {"peso_cvt": "40"}; sess.observations = "seco"
    sess.set_filter(FilterConfig(kind="median", kernel=7))
    proj = tmp_path / "p.mlproj"; save_project(str(proj), sess, [{"name": "v", "expression": "vel"}])
    ok = load_project(str(proj))
    assert ok.setup_info == {"peso_cvt": "40"} and ok.filter.kind == "median" and ok.filter.kernel == 7
    assert len(ok.run_paths) == 2 and not ok.missing and not ok.changed
    open(csv_a, "a").write("9,9\n")
    assert load_project(str(proj)).changed == [csv_a]
    import os; os.remove(csv_a)
    assert load_project(str(proj)).missing == [csv_a]


def test_project_rejects_bad_schema(tmp_path):
    p = tmp_path / "x.mlproj"; p.write_text(json.dumps({"schema_version": 99}))
    with pytest.raises(ValidationError):
        load_project(str(p))
    p.write_text("[]")
    with pytest.raises(ValidationError):
        load_project(str(p))


# ── biblioteca SQLite ────────────────────────────────────────────────────────
def test_run_library_search(views, tmp_path):
    lib = RunLibrary(tmp_path / "lib.db")
    for v in views:
        lib.add(v.run, v.processed_for({}).stats)
    lib.add(views[0].run, views[0].processed_for({}).stats)       # upsert: sem duplicar
    assert len(lib.search()) == 2
    assert [r.name for r in lib.search(text="b.cs")] == ["b.csv"]
    assert lib.search(text="'; DROP TABLE runs;--") == [] and len(lib.search()) == 2   # parametrizado
    assert lib.search(tag="inexistente") == []


# ── DLL ──────────────────────────────────────────────────────────────────────
def test_dll_errors_are_exceptions_not_dialogs(tmp_path, monkeypatch):
    monkeypatch.delenv(dll_reader.ENV_VAR, raising=False)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(dll_reader.DllError, match="não encontrada"):
        dll_reader.find_dll()
    with pytest.raises(dll_reader.DllError, match="inválido"):
        dll_reader.generate_csv_from_dll(str(tmp_path), str(tmp_path), "abc")
    with pytest.raises(dll_reader.DllError, match="não existe"):
        dll_reader.generate_csv_from_dll(str(tmp_path / "nope"), str(tmp_path), 1)


def test_dll_env_var_and_wrong_platform_binary(tmp_path, monkeypatch):
    fake = tmp_path / dll_reader.DLL_NAME; fake.write_bytes(b"not a dll")
    monkeypatch.setenv(dll_reader.ENV_VAR, str(fake))
    assert dll_reader.find_dll() == fake.resolve()
    with pytest.raises(dll_reader.DllError, match="falha ao carregar"):
        dll_reader.generate_csv_from_dll(str(tmp_path), str(tmp_path / "out"), 1)


# ── relatórios (ReportModel → renderizadores, sem Qt) ────────────────────────
@pytest.fixture
def model(views):
    from mangue_logger.application.report_model import build_report
    return build_report(views, {"type": "butterworth"}, VehicleProfile(), {"peso_cvt": "40"}, "obs de teste")


@pytest.mark.parametrize("ext", [".xlsx", ".pdf", ".html", ".json", ".csv"])
def test_exporters_work_headless(model, tmp_path, ext):
    out = tmp_path / f"out{ext}"
    get_exporter(ext).export(model, str(out))
    assert out.stat().st_size > 200


def test_report_model_content(model):
    assert [r.name for r in model.runs] == ["a.csv", "b.csv"]
    assert model.runs[1].stats["vel_max"] > model.runs[0].stats["vel_max"]
    assert model.variations["b.csv"]["vel_max"] > 50
    assert model.insights == tuple(sorted(model.insights, key=lambda f: {"critical": 0, "warning": 1, "good": 2, "info": 3}[f.level]))
    assert "Butterworth" in model.filter_description and model.summary_points


def test_json_export_is_per_run_and_has_provenance(model, tmp_path):
    out = tmp_path / "o.json"
    get_exporter(".json").export(model, str(out))
    data = json.loads(out.read_text())
    assert data["runs"][0]["stats"]["Vel. Máx (Km/h)"] != data["runs"][1]["stats"]["Vel. Máx (Km/h)"]
    assert len(data["runs"][0]["sha256"]) == 64 and "series" not in data["runs"][0]


def test_html_is_self_contained_and_escapes(views, tmp_path):
    from mangue_logger.application.report_model import build_report
    m = build_report(views, {}, VehicleProfile(), {"x": "<script>alert(1)</script>"}, "<b>obs</b>")
    out = tmp_path / "r.html"; get_exporter(".html").export(m, str(out))
    html = out.read_text(encoding="utf-8")
    assert "<script>alert(1)" not in html and "&lt;script&gt;" in html and "data:image/png;base64" in html
    assert "http://" not in html.replace("http://www.w3.org", "")


def test_excel_structure_and_native_charts(model, tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    out = tmp_path / "r.xlsx"; get_exporter(".xlsx").export(model, str(out))
    wb = openpyxl.load_workbook(out)
    assert {"Resumo", "Insights", "Fases", "CVT", "Qualidade", "Proveniência", "a.csv", "b.csv"} <= set(wb.sheetnames)
    assert len(wb["Resumo"]._charts) >= 1 and len(wb["a.csv"]._charts) == 2


def test_report_with_setup_comparison(tmp_path):
    from conftest import write_run_csv
    from mangue_logger.application.processing import ProcessingService
    from mangue_logger.application.report_model import build_report
    from mangue_logger.application.run_view import RunView
    from mangue_logger.domain.models import RunMeta
    svc, prof, runs = ProcessingService(), VehicleProfile(), []
    for i, (sc, lab) in enumerate([(1.0, "A"), (1.02, "A"), (1.6, "B"), (1.62, "B")]):
        run = CsvRunReader().read(write_run_csv(tmp_path / f"s{i}.csv", sc, seed=i))
        object.__setattr__(run, "meta", RunMeta(setup={"mola": lab}))
        runs.append(RunView(run, svc, prof))
    m = build_report(runs, {}, prof, setup_key="mola", metric="vel_mean")
    assert m.setup_comparison and m.setup_comparison.tests["B"].diff > 0
    for ext in (".pdf", ".html", ".xlsx"):
        get_exporter(ext).export(m, str(tmp_path / f"c{ext}"))
    assert "setup_comparison" in m.to_jsonable()


def test_csv_tidy_has_all_runs(model, tmp_path):
    import pandas as pd
    out = tmp_path / "t.csv"; get_exporter(".csv").export(model, str(out))
    df = pd.read_csv(out)
    assert set(df["run"]) == {"a.csv", "b.csv"} and {"tempo_s", "vel_kmh", "rpm"} <= set(df.columns)


def test_chart_decimation_preserves_peaks():
    import numpy as np
    from mangue_logger.infrastructure.exporters.charts import decimate
    y = np.zeros(100_000); y[54_321] = 99.0
    x, yy = decimate(np.arange(y.size, dtype=float), y, 1000)
    assert yy.size <= 1000 and yy.max() == 99.0


def test_exporter_errors_propagate(model, tmp_path):
    with pytest.raises(OSError):
        get_exporter(".json").export(model, str(tmp_path / "no" / "dir" / "x.json"))
    with pytest.raises(KeyError):
        get_exporter(".docx")


# ── CLI ──────────────────────────────────────────────────────────────────────
def test_cli_analyze_and_quality(csv_a, csv_b, tmp_path, capsys):
    from mangue_logger.cli import main
    out = tmp_path / "r.json"
    assert main(["analyze", csv_a, csv_b, "--json", str(out), "--cutoff-hz", "1.5"]) == 0
    printed = capsys.readouterr().out
    assert "Variação vs. base" in printed and out.exists()
    assert main(["quality", csv_a]) == 0
    assert main(["analyze", str(tmp_path / "nada.csv")]) == 2


def test_cli_group_by(tmp_path, capsys):
    from conftest import write_run_csv
    from mangue_logger.cli import main
    files = []
    for i, (sc, lab) in enumerate([(1.0, "A"), (1.02, "A"), (1.6, "B"), (1.62, "B")]):
        p = write_run_csv(tmp_path / f"c{i}.csv", sc, seed=i)
        (tmp_path / f"c{i}.csv.meta.json").write_text(json.dumps({"setup": {"mola": lab}}))
        files.append(p)
    assert main(["analyze", *files, "--group-by", "mola"]) == 0
    assert "IC95%" in capsys.readouterr().out


# ── logging ──────────────────────────────────────────────────────────────────
def test_logging_setup_and_excepthook(tmp_path):
    import logging

    from mangue_logger.infrastructure import logging_setup as ls
    path = ls.setup_logging(log_dir=tmp_path)
    seen = []
    old = sys.excepthook
    try:
        ls.install_excepthook(seen.append)
        sys.excepthook(ValueError, ValueError("boom"), None)
    finally:
        sys.excepthook = old
    for h in logging.getLogger().handlers[:]:
        h.flush()
    assert seen == ["ValueError: boom"] and "boom" in path.read_text()
    time.sleep(0)


def test_project_v1_legacy_filter_still_opens(tmp_path, csv_a):
    """Projetos salvos pela v6/v7.0 (cutoff normalizado) devem abrir, convertidos para Hz."""
    p = tmp_path / "old.mlproj"
    p.write_text(json.dumps({"schema_version": 1, "profile": VehicleProfile().to_dict(), "runs": [],
                             "filter_settings": {"type": "butterworth", "butter_order": 3, "butter_cutoff": 0.2}}))
    proj = load_project(str(p))
    assert proj.filter.order == 3 and proj.filter.cutoff_hz == pytest.approx(2.0)          # 0,2 × Nyquist(10 Hz)


def test_project_rejects_invalid_filter(tmp_path):
    p = tmp_path / "bad.mlproj"
    p.write_text(json.dumps({"schema_version": 2, "profile": VehicleProfile().to_dict(), "runs": [],
                             "filter": {"kind": "butterworth", "cutoff_hz": 99.0}}))
    with pytest.raises(ValidationError, match="filtro"):
        load_project(str(p))
