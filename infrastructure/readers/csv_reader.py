"""Leitor de CSV (colunas configuráveis; padrão f1 = RPM, f2 = velocidade) com relatório de qualidade — sem `fillna(0)` silencioso."""

from __future__ import annotations

import hashlib
import io
import json
import os

import numpy as np
import pandas as pd

from ...domain.errors import ReaderError, ValidationError
from ...domain.models import DataQualityReport, Run, RunMeta, SensorConfig


class CsvRunReader:
    """Converte contagens de pulso em RPM/velocidade segundo o `SensorConfig`.

    Metadados opcionais: se existir ``<arquivo>.meta.json`` ao lado do CSV, ele é lido
    (setup do veículo, notas, tags) e acompanha a run.
    """

    def __init__(self, sensor: SensorConfig | None = None):
        self.sensor = sensor or SensorConfig()

    def read(self, path: str) -> Run:
        if not os.path.isfile(path):
            raise ReaderError(f"Não encontrado: {path}")
        raw = open(path, "rb").read()  # noqa: SIM115 - lido uma vez: hash + parse
        sha = hashlib.sha256(raw).hexdigest()
        try:
            df = pd.read_csv(io.BytesIO(raw), engine="c")
        except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as exc:
            raise ReaderError(f"{os.path.basename(path)}: CSV ilegível ({exc})") from exc
        name = os.path.basename(path)
        s = self.sensor
        rc, sc = s.rpm_column, s.speed_column
        if not {rc, sc}.issubset(df.columns):
            raise ReaderError(f"{name}: colunas {rc}/{sc} ausentes (encontradas: {list(df.columns)[:6]}).")

        rpm_c = pd.to_numeric(df[rc], errors="coerce").to_numpy(dtype=np.float64)
        spd_c = pd.to_numeric(df[sc], errors="coerce").to_numpy(dtype=np.float64)
        nan_rpm, nan_spd = int(np.isnan(rpm_c).sum()), int(np.isnan(spd_c).sum())
        neg = int(((rpm_c < 0) | (spd_c < 0)).sum())
        # Contagem de pulsos ausente = nenhum pulso observado; mantemos 0, mas AVISAMOS.
        rpm_c, spd_c = np.nan_to_num(rpm_c, nan=0.0), np.nan_to_num(spd_c, nan=0.0)
        rpm_c, spd_c = np.clip(rpm_c, 0, None), np.clip(spd_c, 0, None)

        w = s.window_samples
        n_rows = len(rpm_c)
        g = n_rows // w
        if g < 2:
            raise ReaderError(f"{name}: dados insuficientes ({n_rows} linhas; mínimo {2 * w}).")
        dropped = n_rows - g * w
        s_rpm = rpm_c[: g * w].reshape(g, w).sum(axis=1)
        s_spd = spd_c[: g * w].reshape(g, w).sum(axis=1)

        warnings: list[str] = []
        if nan_rpm or nan_spd:
            warnings.append(f"{nan_rpm + nan_spd} valores não numéricos em {rc}/{sc} tratados como 0 pulsos.")
        if neg:
            warnings.append(f"{neg} contagens negativas truncadas em 0.")
        if dropped:
            warnings.append(f"{dropped} linhas finais descartadas (não completam uma janela de {w}).")
        if not s_spd.any():
            warnings.append(f"{sc} (velocidade) é zero em toda a run — sensor desconectado?")
        if not s_rpm.any():
            warnings.append(f"{rc} (RPM) é zero em toda a run — sensor desconectado?")
        zero_run = _longest_zero_run(s_spd + s_rpm)
        if zero_run * s.window_dt_s >= 2.0 and s_spd.any():
            warnings.append(f"Sequência de {zero_run * s.window_dt_s:.1f} s sem nenhum pulso (parada ou perda de sinal).")

        quality = DataQualityReport(n_rows, g, dropped, nan_rpm, nan_spd, neg, tuple(warnings))
        return Run(
            path=path, name=name,
            time_s=np.arange(g, dtype=np.float64) * s.window_dt_s,
            rpm_raw=s.rpm_from_counts(s_rpm), vel_raw_kmh=s.speed_kmh_from_counts(s_spd),
            sensor=s, source_sha256=sha, quality=quality, meta=_read_meta(path),
        )


def _longest_zero_run(x: np.ndarray) -> int:
    z = np.concatenate([[0], (x == 0).astype(np.int8), [0]])
    d = np.diff(z)
    starts, ends = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
    return int((ends - starts).max()) if starts.size else 0


def _read_meta(csv_path: str) -> RunMeta:
    side = csv_path + ".meta.json"
    if not os.path.isfile(side):
        return RunMeta()
    try:
        with open(side, encoding="utf-8") as f:
            return RunMeta.from_dict(json.load(f))
    except (OSError, json.JSONDecodeError, ValidationError):
        return RunMeta()
