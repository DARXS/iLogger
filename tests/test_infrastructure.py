import json
import sys
import time

import pytest

from mangue_logger.application.loading import load_runs
from mangue_logger.application.ports import Cancelled, CancelToken, ReportContext
from mangue_logger.application.session import Session
from mangue_logger.application.virtual_channels import VirtualChannel
from mangue_logger.domain.errors import ExpressionError, ValidationError
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
    sess.set_filter({"type": "median", "median_kernel": 7})
    proj = tmp_path / "p.mlproj"; save_project(str(proj), sess, [{"name": "v", "expression": "vel"}])
    ok = load_project(str(proj))
    assert ok.setup_info == {"peso_cvt": "40"} and ok.filter_settings["median_kernel"] == 7
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


# ── exporters (sem Qt) ───────────────────────────────────────────────────────
@pytest.mark.parametrize("ext", [".xlsx", ".pdf", ".json", ".csv"])
def test_exporters_work_headless(views, tmp_path, ext):
    ctx = ReportContext(runs=views, filter_settings={"type": "butterworth"},
                        setup_info={"peso_cvt": "40"}, observations="teste")
    out = tmp_path / f"out{ext}"
    get_exporter(ext).export(ctx, str(out))
    assert out.stat().st_size > 200


def test_json_export_content_is_per_run(views, tmp_path):
    out = tmp_path / "o.json"
    get_exporter(".json").export(ReportContext(views, {"type": "butterworth"}), str(out))
    runs = json.loads(out.read_text())["runs"]
    assert runs[0]["stats"]["Vel. Máx (Km/h)"] != runs[1]["stats"]["Vel. Máx (Km/h)"]


def test_exporter_errors_propagate(views, tmp_path):
    with pytest.raises(OSError):
        get_exporter(".json").export(ReportContext(views, {}), str(tmp_path / "no" / "dir" / "x.json"))
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
