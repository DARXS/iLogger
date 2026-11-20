"""API HTTP: carga, séries, delta de tempo, motor, setups, biblioteca, relatórios, projeto."""

import json
import warnings

import numpy as np
import pytest

warnings.filterwarnings("ignore")
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from conftest import write_run_csv  # noqa: E402
from mangue_logger.web.server import create_app  # noqa: E402
from mangue_logger.web.state import AppService  # noqa: E402


@pytest.fixture
def svc(tmp_path):
    return AppService(tmp_path / "data")


@pytest.fixture
def client(svc):
    return TestClient(create_app(svc))


@pytest.fixture
def loaded(client, csv_a, csv_b):
    r = client.post("/api/load", json={"paths": [csv_a, csv_b]})
    assert r.status_code == 200, r.text
    return [x["id"] for x in r.json()["state"]["runs"]]


def test_serves_frontend(client):
    r = client.get("/")
    assert r.status_code == 200 and "Mangue Logger" in r.text
    for asset in ("/static/css/app.css", "/static/js/main.js", "/static/js/chart.js", "/static/js/views/overview.js"):
        assert client.get(asset).status_code == 200, asset


def test_state_empty_then_loaded(client, loaded):
    st = client.get("/api/state").json()
    assert [r["name"] for r in st["runs"]] == ["a.csv", "b.csv"]
    assert st["runs"][0]["color"] != st["runs"][1]["color"] and st["nyquist_hz"] == 10.0
    assert st["filter"]["kind"] == "butterworth" and st["profile"]["sensor"]["rpm_column"] == "f1"


def test_load_validates_paths_and_dedupes(client, csv_a, tmp_path):
    assert client.post("/api/load", json={"paths": [str(tmp_path / "nope.csv")]}).status_code == 422
    (tmp_path / "x.txt").write_text("a")
    assert client.post("/api/load", json={"paths": [str(tmp_path / "x.txt")]}).status_code == 422
    first = client.post("/api/load", json={"paths": [csv_a]}).json()
    again = client.post("/api/load", json={"paths": [csv_a]}).json()
    assert len(first["added"]) == 1 and again["added"] == [] and again["duplicates"] == ["a.csv"]


def test_upload_with_sidecar_meta_and_bad_file(client, csv_a, tmp_path):
    data = open(csv_a, "rb").read()
    meta = json.dumps({"setup": {"mola": "A"}, "tags": ["t"]}).encode()
    r = client.post("/api/upload", files=[("files", ("up.csv", data, "text/csv")), ("files", ("up.csv.meta.json", meta, "application/json"))])
    assert r.status_code == 200, r.text
    run = r.json()["state"]["runs"][0]
    assert run["meta"]["setup"] == {"mola": "A"} and run["meta"]["tags"] == ["t"]
    bad = client.post("/api/upload", files=[("files", ("evil.exe", b"MZ", "application/octet-stream"))])
    assert bad.status_code == 422
    r = client.post("/api/upload", files=[("files", ("../../etc/x.csv", b"f1,f2\n1,2\n", "text/csv"))])
    assert r.status_code == 200 and r.json()["errors"]          # nome sanitizado; conteúdo curto vira erro de leitura


def test_series_decimation_window_and_validation(client, loaded):
    r = client.get("/api/series", params={"runs": ",".join(loaded), "channels": "vel,rpm,acel", "max_points": 300}).json()
    d = r["runs"][loaded[0]]
    assert len(d["x"]) <= 400 and set(d) == {"x", "vel", "rpm", "acel"} and d["x"] == sorted(d["x"])
    w = client.get("/api/series", params={"runs": loaded[0], "channels": "vel", "x0": 5, "x1": 8, "max_points": 5000}).json()["runs"][loaded[0]]
    assert w["x"][0] <= 5.1 and w["x"][-1] >= 7.9 and w["x"][-1] < 8.2
    assert client.get("/api/series", params={"runs": loaded[0], "channels": "bogus"}).status_code == 422
    assert client.get("/api/series", params={"runs": "naoexiste", "channels": "vel"}).status_code == 404


def test_series_preserves_peaks(svc, client, tmp_path):
    p = write_run_csv(tmp_path / "pk.csv", 1.0, n=20000, seed=3)
    rid = client.post("/api/load", json={"paths": [p]}).json()["added"][0]
    full = client.get("/api/series", params={"runs": rid, "channels": "vel", "max_points": 20000}).json()["runs"][rid]["vel"]
    dec = client.get("/api/series", params={"runs": rid, "channels": "vel", "max_points": 400}).json()["runs"][rid]["vel"]
    assert len(dec) < len(full) and max(dec) == pytest.approx(max(full), abs=1e-3)


def test_compare_delta_sectors(client, loaded):
    r = client.get("/api/compare", params={"runs": ",".join(loaded), "sectors": 12}).json()
    ref = next(x for x in r["runs"] if x["id"] == r["ref"])
    assert ref["final_delta"] == 0 and set(ref["delta"]) == {0.0}
    other = next(x for x in r["runs"] if x["id"] != r["ref"])
    assert len(other["sector_colors"]) == 12 and set(other["sector_colors"]) <= {"purple", "green", "yellow"}
    # b é mais rápida (escala 3×): chega antes à mesma distância → delta negativo e setores melhores
    assert other["final_delta"] < 0 and other["sector_colors"].count("purple") >= 6
    assert len(r["dist"]) == len(other["delta"])
    assert client.get("/api/compare", params={"runs": ""}).status_code in (200, 422)


def test_compare_needs_distance(client, svc, tmp_path):
    import pandas as pd
    p = tmp_path / "still.csv"
    pd.DataFrame({"f1": [3] * 100, "f2": [0] * 100}).to_csv(p, index=False)
    client.post("/api/load", json={"paths": [str(p)]})
    assert client.get("/api/compare").status_code == 422


def test_engine_phases_overview_math(client, loaded):
    e = client.get(f"/api/engine/{loaded[0]}").json()
    assert {"scatter", "cvt", "rpm_hist", "vel_hist", "rpm_fft", "gears", "power_band"} <= set(e)
    assert len(e["rpm_hist"]["centers"]) == len(e["rpm_hist"]["seconds"]) == 40
    ph = client.get(f"/api/phases/{loaded[0]}").json()
    assert ph and {"phase", "t0", "t1"} <= set(ph[0])
    ov = client.get("/api/overview").json()
    assert len(ov["runs"]) == 2 and ov["runs"][0]["color"] and ov["runs"][0]["spark"]["t"] and ov["insights"]
    m = client.post("/api/math", json={"runs": loaded, "expression": "rpm / (vel + 1)"})
    assert m.status_code == 200 and len(m.json()["runs"][loaded[0]]["y"]) > 10
    evil = client.post("/api/math", json={"runs": loaded, "expression": "__import__('os').system('x')"})
    assert evil.status_code == 422


def test_filter_and_profile_updates_change_results(client, loaded):
    before = client.get("/api/overview").json()["runs"][0]["stats_by_id"]["vel_max"]
    r = client.put("/api/filter", json={"kind": "median", "kernel": 9})
    assert r.status_code == 200 and r.json()["filter"]["kind"] == "median"
    after = client.get("/api/overview").json()["runs"][0]["stats_by_id"]["vel_max"]
    assert after != before
    assert client.put("/api/filter", json={"kind": "butterworth", "cutoff_hz": 15}).status_code == 422   # > Nyquist
    assert client.put("/api/filter", json={"kind": "nope"}).status_code == 422
    prof = client.get("/api/state").json()["profile"]
    prof["sensor"]["tire_radius_m"] = 0.58                                    # dobra o raio → dobra a velocidade
    st = client.put("/api/profile", json=prof).json()
    assert st["runs"][0]["stats"]["vel_max"] > 1.5 * before and len(st["runs"]) == 2
    prof["sensor"]["rpm_column"] = prof["sensor"]["speed_column"]
    assert client.put("/api/profile", json=prof).status_code == 422


def test_meta_roundtrip_and_setups(client, svc, tmp_path):
    from conftest import write_run_csv as w
    ids = []
    for i, (sc, lab) in enumerate([(1.0, "A"), (1.02, "A"), (1.6, "B"), (1.62, "B")]):
        ids.append(client.post("/api/load", json={"paths": [w(tmp_path / f"s{i}.csv", sc, seed=i)]}).json()["added"][0])
    for rid, lab in zip(ids, "AABB", strict=True):
        assert client.put(f"/api/runs/{rid}/meta", json={"setup": {"mola": lab}, "tags": ["x", " "], "notes": "n"}).status_code == 200
    st = client.get("/api/state").json()
    assert st["setup_keys"] == ["mola"] and st["runs"][0]["meta"]["tags"] == ["x"]
    s = client.get("/api/setups", params={"key": "mola", "metric": "vel_mean"}).json()
    assert s["baseline"] == "A" and s["tests"]["B"]["diff"] > 0 and s["summary"]["A"]["n"] == 2
    assert (tmp_path / "s0.csv.meta.json").exists()


def test_library_lifecycle(client, loaded, csv_a):
    lib = client.get("/api/library").json()
    assert lib["total"] == 2 and all(i["exists"] for i in lib["items"])
    assert len(client.get("/api/library", params={"q": "b.cs"}).json()["items"]) == 1
    assert client.get("/api/library", params={"q": "'; DROP TABLE runs;--"}).json()["items"] == []
    client.delete("/api/runs")
    opened = client.post("/api/library/open", json={"ids": [lib["items"][0]["id"]], "replace": True}).json()
    assert len(opened["state"]["runs"]) == 1
    client.delete(f"/api/library/{lib['items'][0]['id']}")
    assert client.get("/api/library").json()["total"] == 1
    assert client.post("/api/library/open", json={"ids": ["000000000000"]}).status_code == 422


@pytest.mark.parametrize("ext,magic", [(".pdf", b"%PDF"), (".xlsx", b"PK"), (".html", b"<!doctype"), (".json", b"{"), (".csv", b"run,")])
def test_report_downloads(client, loaded, ext, magic):
    r = client.get("/api/report", params={"format": ext, "title": "Meu Relatório"})
    assert r.status_code == 200 and r.content.startswith(magic) and "Meu_Relat" in r.headers["content-disposition"]


def test_report_errors_and_preview(client, loaded, svc):
    assert client.get("/api/report", params={"format": ".docx"}).status_code == 422
    html = client.get("/api/report/preview", params={"title": "<b>x</b>"}).text
    assert "&lt;b&gt;x&lt;/b&gt;" in html
    client.delete("/api/runs")
    assert client.get("/api/report").status_code == 422


def test_project_export_import(client, loaded, svc):
    client.put("/api/filter", json={"kind": "bessel", "order": 3, "cutoff_hz": 1.5})
    client.put("/api/session", json={"setup_info": {"peso": "42"}, "observations": "obs"})
    raw = client.get("/api/project").content
    client.delete("/api/runs")
    r = client.post("/api/project", files={"file": ("p.mlproj", raw, "application/json")}).json()
    assert len(r["state"]["runs"]) == 2 and r["state"]["filter"]["kind"] == "bessel" and r["state"]["setup_info"] == {"peso": "42"}
    assert client.post("/api/project", files={"file": ("p.mlproj", b"{not json", "application/json")}).status_code == 422


def test_demo_runs_are_realistic(client):
    st = client.post("/api/demo").json()["state"]
    assert len(st["runs"]) == 4 and all(r["quality"]["ok"] for r in st["runs"])
    vmax = [r["stats"]["vel_max"] for r in st["runs"]]
    assert all(40 < v < 90 for v in vmax)
    s = client.get("/api/setups", params={"key": "mola", "metric": "vel_mean"}).json()
    assert s["tests"]["dura"]["significant"]                                   # a demo precisa mostrar a feature de setups


def test_remove_and_clear(client, loaded):
    st = client.delete(f"/api/runs/{loaded[0]}").json()
    assert [r["id"] for r in st["runs"]] == [loaded[1]]
    assert client.delete("/api/runs/naoexiste").status_code == 404
    assert client.delete("/api/runs").json()["runs"] == []


def test_numpy_json_safe(client, loaded):                                      # nenhum NaN/Inf vaza para o JSON
    for path in ("/api/overview", f"/api/engine/{loaded[0]}"):
        txt = client.get(path).text
        assert "NaN" not in txt and "Infinity" not in txt
    _ = np
