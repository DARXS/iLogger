import json

import pandas as pd
import pytest

from conftest import write_run_csv
from mangue_logger.domain.errors import ReaderError
from mangue_logger.infrastructure.readers.csv_reader import CsvRunReader


def test_reads_valid_csv(csv_a):
    run = CsvRunReader().read(csv_a)
    assert run.n_samples == 200 and run.quality.ok
    assert run.time_s[1] == pytest.approx(0.05)
    assert not run.rpm_raw.flags.writeable


def test_content_hash_differs_between_files(csv_a, csv_b):
    r = CsvRunReader()
    assert r.read(csv_a).content_hash != r.read(csv_b).content_hash


def test_missing_columns_and_file(tmp_path):
    p = tmp_path / "bad.csv"; pd.DataFrame({"x": [1, 2]}).to_csv(p, index=False)
    with pytest.raises(ReaderError, match="f1/f2"):
        CsvRunReader().read(str(p))
    with pytest.raises(ReaderError):
        CsvRunReader().read(str(tmp_path / "nope.csv"))


def test_too_short(tmp_path):
    p = tmp_path / "s.csv"; pd.DataFrame({"f1": [1] * 5, "f2": [1] * 5}).to_csv(p, index=False)
    with pytest.raises(ReaderError, match="insuficientes"):
        CsvRunReader().read(str(p))


def test_nan_is_reported_not_silent(tmp_path):
    p = tmp_path / "n.csv"
    pd.DataFrame({"f1": [1.0, None, "abc"] + [1] * 97, "f2": [2] * 100}).to_csv(p, index=False)
    q = CsvRunReader().read(str(p)).quality
    assert q.nan_f1 == 2 and not q.ok and any("não numéricos" in w for w in q.warnings)


def test_trailing_rows_and_dead_sensor_and_gap_warnings(tmp_path):
    p = tmp_path / "d.csv"
    pd.DataFrame({"f1": [0] * 105, "f2": [3] * 105}).to_csv(p, index=False)
    w = " ".join(CsvRunReader().read(str(p)).quality.warnings)
    assert "descartadas" in w and "f1" in w
    g = write_run_csv(tmp_path / "g.csv", 1.0, stop_s=3.0)
    assert any("sem nenhum pulso" in x for x in CsvRunReader().read(g).quality.warnings)


def test_sidecar_meta(csv_a):
    with open(csv_a + ".meta.json", "w") as f:
        json.dump({"setup": {"peso_cvt": "42"}, "notes": "seco", "tags": ["cvt-a"]}, f)
    m = CsvRunReader().read(csv_a).meta
    assert m.setup["peso_cvt"] == "42" and m.tags == ("cvt-a",)


def test_corrupt_sidecar_is_ignored(csv_a):
    open(csv_a + ".meta.json", "w").write("{not json")
    assert CsvRunReader().read(csv_a).meta.setup == {}
