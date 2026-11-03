from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from mangue_logger.application.processing import ProcessingService
from mangue_logger.application.run_view import RunView
from mangue_logger.domain.models import VehicleProfile
from mangue_logger.infrastructure.readers.csv_reader import CsvRunReader


def write_run_csv(path, scale: float, n: int = 2000, seed: int = 0, stop_s: float = 0.0):
    """Run sintética: aceleração gradual, contagens de pulso ~Poisson."""
    rng = np.random.default_rng(seed)
    ramp = np.linspace(0.2, 1.0, n)
    f1 = rng.poisson(scale * ramp * 0.3).astype(float)
    f2 = rng.poisson(scale * ramp * 2.0).astype(float)
    if stop_s:
        k = int(stop_s / 0.005)
        f1[100:100 + k] = 0; f2[100:100 + k] = 0
    pd.DataFrame({"f1": f1, "f2": f2}).to_csv(path, index=False)
    return str(path)


@pytest.fixture
def profile():
    return VehicleProfile()


@pytest.fixture
def csv_a(tmp_path):
    return write_run_csv(tmp_path / "a.csv", 1.0, seed=1)


@pytest.fixture
def csv_b(tmp_path):
    return write_run_csv(tmp_path / "b.csv", 3.0, seed=2)


@pytest.fixture
def views(csv_a, csv_b, profile):
    reader, svc = CsvRunReader(profile.sensor), ProcessingService()
    return [RunView(reader.read(p), svc, profile) for p in (csv_a, csv_b)]
