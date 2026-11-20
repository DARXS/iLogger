"""Regressão do bug crítico da v6: runs diferentes compartilhavam o resultado em cache."""

import numpy as np

from mangue_logger.application.analysis import generate_stats


def test_different_runs_get_different_results(views):
    a, b = views
    fs = {"type": "butterworth"}
    a.apply_filters_and_recalculate(fs)
    b.apply_filters_and_recalculate(fs)
    assert not np.allclose(a.velocity_filtered_kmh, b.velocity_filtered_kmh)
    assert b.velocity_filtered_kmh.max() > 2 * a.velocity_filtered_kmh.max()


def test_stats_and_variations_reflect_each_run(views):
    metrics, variations = generate_stats(views, {"type": "butterworth"})
    assert metrics.loc["b.csv", "Vel. Máx (Km/h)"] > metrics.loc["a.csv", "Vel. Máx (Km/h)"]
    assert (variations["Vel. Máx (Km/h)"] > 50).all()  # v6 dava 0%


def test_cache_is_hit_for_same_run_and_filter(views):
    a, _ = views
    svc = a._service
    a.processed_for({"type": "butterworth"}); a.processed_for({"type": "butterworth"})
    assert svc.cache.hits == 1 and svc.cache.misses == 1


def test_cache_miss_when_filter_changes(views):
    a, _ = views
    p1 = a.processed_for({"type": "butterworth", "butter_cutoff": 0.1})
    p2 = a.processed_for({"type": "butterworth", "butter_cutoff": 0.3})
    assert p1 is not p2 and not np.allclose(p1.vel_kmh, p2.vel_kmh)


def test_processed_arrays_are_read_only(views):
    p = views[0].processed_for({})
    assert not p.vel_kmh.flags.writeable
