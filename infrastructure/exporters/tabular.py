"""JSON (modelo completo) e CSV tidy (uma linha por amostra)."""

from __future__ import annotations

import pandas as pd

from ...application.report_model import ReportModel
from ...domain import channels as ch


def render_json(m: ReportModel, path: str, include_series: bool = False) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(m.to_json(include_series))


def render_csv(m: ReportModel, path: str) -> None:
    frames = []
    for r in m.runs:
        df = pd.DataFrame({
            "run": r.name, "tempo_s": r.series[ch.TIME], "vel_kmh": r.series[ch.VEL], "rpm": r.series[ch.RPM],
            "acel_ms2": r.series[ch.ACEL], "dist_m": r.series[ch.DIST],
            "vel_bruta_kmh": r.series[ch.VEL_RAW], "rpm_bruto": r.series[ch.RPM_RAW],
        })
        frames.append(df)
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    out.to_csv(path, index=False, encoding="utf-8")
