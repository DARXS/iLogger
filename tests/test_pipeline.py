import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from mangue_logger.domain.errors import ValidationError
from mangue_logger.domain.models import Run, SensorConfig
from mangue_logger.domain.pipeline import FILTER_KINDS, FilterConfig, Pipeline


def make_run(vel_kmh, rpm=None, dt=0.05):
    n = len(vel_kmh)
    return Run("x.csv", "x.csv", np.arange(n) * dt, np.asarray(rpm if rpm is not None else np.full(n, 3000.0)),
               np.asarray(vel_kmh, float), SensorConfig(window_dt_s=dt), "0" * 64)


def test_distance_trapezoid_exact_for_constant_speed():
    run = make_run(np.full(200, 36.0))                       # 10 m/s
    p = Pipeline(FilterConfig(kind="moving_average", window=3)).apply(run)
    assert p.dist[-1] == pytest.approx(10.0 * run.time_s[-1], rel=1e-6)


def test_cutoff_is_in_hz_and_validated():
    with pytest.raises(ValidationError):
        FilterConfig(cutoff_hz=15.0).validate(20.0)         # > Nyquist (10 Hz)
    FilterConfig(cutoff_hz=2.0).validate(20.0)


def test_legacy_conversion_roundtrip():
    cfg = FilterConfig.from_legacy({"type": "butterworth", "butter_order": 3, "butter_cutoff": 0.2}, 20.0)
    assert cfg.order == 3 and cfg.cutoff_hz == pytest.approx(2.0)
    assert cfg.to_legacy(20.0)["butter_cutoff"] == pytest.approx(0.2)


def test_lowpass_attenuates_high_frequency_noise():
    t = np.arange(2000) * 0.05
    clean = 30 + 10 * np.sin(2 * np.pi * 0.1 * t)
    noisy = clean + 5 * np.sin(2 * np.pi * 8.0 * t)
    p = Pipeline(FilterConfig(cutoff_hz=1.0)).apply(make_run(noisy))
    assert np.abs(p.vel_kmh[100:-100] - clean[100:-100]).max() < 1.0


def test_moving_average_has_no_edge_dip():
    p = Pipeline(FilterConfig(kind="moving_average", window=9)).apply(make_run(np.full(100, 50.0)))
    assert p.vel_kmh[0] == pytest.approx(50.0) and p.vel_kmh[-1] == pytest.approx(50.0)  # v6 caía para ~25


def test_short_signal_does_not_crash():
    for n in (0, 1, 2, 5):
        run = make_run(np.full(n, 10.0))
        Pipeline(FilterConfig()).apply(run)


@settings(deadline=None, max_examples=30)
@given(kind=st.sampled_from(FILTER_KINDS), n=st.integers(0, 300),
       vals=st.lists(st.floats(0, 200, allow_nan=False), min_size=0, max_size=300))
def test_any_filter_preserves_shape_and_finiteness(kind, n, vals):
    run = make_run(vals)
    p = Pipeline(FilterConfig(kind=kind)).apply(run)
    assert p.vel_kmh.shape == p.rpm.shape == p.acel.shape == p.dist.shape == (len(vals),)
    assert np.isfinite(p.vel_kmh).all() and np.isfinite(p.dist).all()


def test_sensor_matches_v6_formulas():
    s, counts = SensorConfig(), np.array([0.0, 12.0, 30.0])
    v6 = counts * (2.0 * 0.29 * 3.1415926535 * 20.0 * 3.6) / 12
    assert np.allclose(s.speed_kmh_from_counts(counts), v6, rtol=1e-8)
    assert np.allclose(s.rpm_from_counts(counts), counts * 1200.0)
