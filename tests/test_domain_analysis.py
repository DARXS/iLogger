import numpy as np
import pytest

from mangue_logger.application.analysis import compare_setups, full_analysis
from mangue_logger.domain.analyzers.compare import welch_compare
from mangue_logger.domain.analyzers.cvt import analyze_cvt, power_band_usage
from mangue_logger.domain.analyzers.phases import detect_phases, phase_summary
from mangue_logger.domain.errors import ValidationError
from mangue_logger.domain.models import RuleThresholds, SensorConfig, VehicleProfile
from mangue_logger.domain.rules import compare_stats


def test_phases_vectorized_matches_expected_segments():
    acel = np.concatenate([np.full(20, 2.0), np.full(15, 0.0), np.full(10, -3.0)])
    t = np.arange(acel.size) * 0.05
    df = detect_phases(acel, t, np.linspace(0, 30, acel.size), np.cumsum(np.ones(acel.size)))
    assert list(df["Fase"]) == ["aceleração", "estabilização", "frenagem"]
    s = phase_summary(df, float(t[-1]))
    assert s["aceleração"]["n_eventos"] == 1 and s["frenagem"]["n_eventos"] == 1
    assert df["Acel. Média (m/s²)"].iloc[0] == pytest.approx(2.0)


def test_cvt_detects_stable_rpm_when_cvt_holds():
    n = 600
    vel = np.linspace(0, 60, n); acel = np.full(n, 2.0)
    rpm = 3300 + np.random.default_rng(0).normal(0, 20, n)
    c = analyze_cvt(vel, rpm, acel)
    assert c is not None and c.hold_cv_pct < 2 and c.hold_rpm == pytest.approx(3300, abs=50)
    drifting = np.linspace(1500, 3800, n)           # RPM sobe junto com a velocidade (sem CVT)
    assert analyze_cvt(vel, drifting, acel).hold_cv_pct > 8


def test_cvt_none_on_insufficient_data():
    assert analyze_cvt(np.zeros(10), np.zeros(10), np.zeros(10)) is None


def test_power_band():
    rpm = np.concatenate([np.full(50, 3000.0), np.full(50, 1000.0)])
    pb = power_band_usage(rpm, np.full(100, 1.0), (2800, 3800))
    assert pb.pct_time_total == pytest.approx(50.0)


def test_welch_detects_real_difference_and_handles_edge_cases():
    r = welch_compare([40.1, 40.5, 39.8, 40.3], [43.0, 43.4, 42.8, 43.2])
    assert r.significant and r.diff == pytest.approx(2.95, abs=0.1) and r.ci95[0] > 0
    assert welch_compare([1.0], [2.0, 3.0]) is None
    same = welch_compare([5, 5, 5], [5, 5, 5])
    assert same.p == 1.0


def test_findings_and_thresholds_from_profile(views):
    strict = VehicleProfile(rules=RuleThresholds(hard_accel_ms2=0.5))
    loose = VehicleProfile(rules=RuleThresholds(hard_accel_ms2=500))
    titles = lambda prof: [f.title for f in full_analysis(views, {}, prof)["insights"]]
    assert any("Aceleração violenta" in t for t in titles(strict))
    assert not any("Aceleração violenta" in t for t in titles(loose))


def test_full_analysis_does_not_mutate_views(views):
    before = [v.state_key for v in views]
    full_analysis(views, {"type": "median"}, VehicleProfile())
    assert [v.state_key for v in views] == before == [None, None]


def test_compare_uses_ids_not_ui_labels(views):
    a, b = (v.processed_for({}).stats for v in views)
    assert any("Vel. máx" in f.title for f in compare_stats(a, b))


def test_compare_setups(views, csv_a, tmp_path):
    from conftest import write_run_csv
    from mangue_logger.application.run_view import RunView
    from mangue_logger.domain.models import RunMeta
    from mangue_logger.infrastructure.readers.csv_reader import CsvRunReader
    reader, svc, prof, runs = CsvRunReader(), views[0]._service, VehicleProfile(), []
    for i, (scale, label) in enumerate([(1.0, "leve"), (1.02, "leve"), (1.5, "pesado"), (1.52, "pesado")]):
        run = reader.read(write_run_csv(tmp_path / f"r{i}.csv", scale, seed=i))
        object.__setattr__(run, "meta", RunMeta(setup={"peso": label}))
        runs.append(RunView(run, svc, prof))
    out = compare_setups(runs, {}, "peso", "vel_max")
    assert out["baseline"] == "leve" and out["tests"]["pesado"].diff > 0
    assert out["summary"]["leve"][2] == 2


def test_profile_validation_and_roundtrip():
    p = VehicleProfile(sensor=SensorConfig(tire_radius_m=0.3), power_band_rpm=(2800, 3800))
    assert VehicleProfile.from_dict(p.to_dict()) == p
    for bad in ({"sensor": {"tire_radius_m": -1}}, {"sensor": {"nope": 1}}, {"zzz": 1},
                {"power_band_rpm": [5, 1]}, {"rules": {"hard_brake_ms2": 3}}):
        with pytest.raises(ValidationError):
            VehicleProfile.from_dict(bad)
