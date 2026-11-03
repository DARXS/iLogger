"""Modelos de domínio imutáveis: sensor, perfil do veículo, run e relatório de qualidade."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, fields
from typing import Any

import numpy as np

from .errors import ValidationError


def _check(cond: bool, msg: str) -> None:
    if not cond:
        raise ValidationError(msg)


def _from_dict(cls: Any, data: Mapping[str, Any], what: str) -> Any:
    """Constrói dataclass a partir de dict rejeitando chaves desconhecidas."""
    _check(isinstance(data, Mapping), f"{what}: esperado objeto JSON")
    unknown = set(data) - {f.name for f in fields(cls)}
    _check(not unknown, f"{what}: chaves desconhecidas {sorted(unknown)}")
    try:
        return cls(**data)
    except TypeError as exc:
        raise ValidationError(f"{what}: {exc}") from exc


# ── Sensor / perfil ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SensorConfig:
    """Como contagens de pulso (f1/f2) viram RPM e velocidade.

    Todas as suposições antes "escondidas" no código (janela de 10 amostras, dt = 50 ms,
    raio do pneu, furos do disco) ficam explícitas e validadas aqui.
    """

    tire_radius_m: float = 0.29
    disc_holes: int = 12
    window_samples: int = 10      # amostras brutas somadas por ponto de saída
    window_dt_s: float = 0.05     # duração de cada janela agregada
    rpm_pulses_per_rev: float = 1.0

    def __post_init__(self) -> None:
        _check(self.tire_radius_m > 0, "tire_radius_m deve ser > 0")
        _check(self.disc_holes >= 1, "disc_holes deve ser >= 1")
        _check(self.window_samples >= 1, "window_samples deve ser >= 1")
        _check(self.window_dt_s > 0, "window_dt_s deve ser > 0")
        _check(self.rpm_pulses_per_rev > 0, "rpm_pulses_per_rev deve ser > 0")

    @property
    def sample_rate_hz(self) -> float:
        return 1.0 / self.window_dt_s

    def rpm_from_counts(self, counts: np.ndarray) -> np.ndarray:
        return counts * (60.0 / (self.window_dt_s * self.rpm_pulses_per_rev))

    def speed_kmh_from_counts(self, counts: np.ndarray) -> np.ndarray:
        revs = counts / self.disc_holes
        return revs * (2.0 * math.pi * self.tire_radius_m) / self.window_dt_s * 3.6

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()[:16]


@dataclass(frozen=True)
class RuleThresholds:
    """Limiares das regras de insight (antes fixos no código)."""

    hard_brake_ms2: float = -8.0
    hard_accel_ms2: float = 6.0
    rpm_util_good: float = 0.60
    rpm_spike: float = 500.0
    rpm_spike_count: int = 10
    anomaly_z: float = 3.5
    phase_accel_thr: float = 1.0
    phase_brake_thr: float = -1.0
    cvt_hold_cv_warn_pct: float = 8.0   # CV% do RPM em aceleração plena acima disso => CVT não segura RPM
    cvt_min_speed_kmh: float = 5.0

    def __post_init__(self) -> None:
        _check(self.hard_brake_ms2 < 0, "hard_brake_ms2 deve ser negativo")
        _check(self.hard_accel_ms2 > 0, "hard_accel_ms2 deve ser positivo")
        _check(0 < self.rpm_util_good <= 1, "rpm_util_good deve estar em (0, 1]")
        _check(self.phase_brake_thr < self.phase_accel_thr, "limiares de fase inconsistentes")


@dataclass(frozen=True)
class VehicleProfile:
    name: str = "Mangue Baja (padrão)"
    sensor: SensorConfig = field(default_factory=SensorConfig)
    rules: RuleThresholds = field(default_factory=RuleThresholds)
    # Faixa de RPM de interesse do motor (ex.: faixa de potência). None = análise desativada.
    power_band_rpm: tuple[float, float] | None = None

    def __post_init__(self) -> None:
        if self.power_band_rpm is not None:
            lo, hi = self.power_band_rpm
            _check(0 <= lo < hi, "power_band_rpm deve ser (min, max) com min < max")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["power_band_rpm"] = list(self.power_band_rpm) if self.power_band_rpm else None
        d["schema_version"] = 1
        return d

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> VehicleProfile:
        _check(isinstance(data, Mapping), "perfil: esperado objeto JSON")
        unknown = set(data) - {"name", "sensor", "rules", "power_band_rpm", "schema_version"}
        _check(not unknown, f"perfil: chaves desconhecidas {sorted(unknown)}")
        band = data.get("power_band_rpm")
        if band is not None:
            _check(isinstance(band, (list, tuple)) and len(band) == 2, "power_band_rpm: use [min, max]")
            band = (float(band[0]), float(band[1]))
        return cls(
            name=str(data.get("name", "Mangue Baja (padrão)")),
            sensor=_from_dict(SensorConfig, data.get("sensor", {}), "sensor"),
            rules=_from_dict(RuleThresholds, data.get("rules", {}), "rules"),
            power_band_rpm=band,
        )


# ── Qualidade de dados ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DataQualityReport:
    n_rows: int = 0
    n_samples: int = 0
    dropped_tail_rows: int = 0
    nan_f1: int = 0
    nan_f2: int = 0
    negative_values: int = 0
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.warnings

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["warnings"] = list(self.warnings)
        return d


# ── Run ───────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RunMeta:
    """Metadados da run (setup do veículo, observações, tags). Persistidos junto à run."""

    setup: Mapping[str, str] = field(default_factory=dict)
    notes: str = ""
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"setup": dict(self.setup), "notes": self.notes, "tags": list(self.tags)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RunMeta:
        _check(isinstance(data, Mapping), "meta: esperado objeto JSON")
        setup = data.get("setup", {})
        _check(isinstance(setup, Mapping), "meta.setup deve ser objeto")
        return cls(
            setup={str(k): str(v) for k, v in setup.items()},
            notes=str(data.get("notes", "")),
            tags=tuple(str(t) for t in data.get("tags", ())),
        )


@dataclass(frozen=True, eq=False)
class Run:
    """Run bruta e imutável. Dados derivados vivem em `ProcessedRun`, nunca aqui."""

    path: str
    name: str
    time_s: np.ndarray
    rpm_raw: np.ndarray
    vel_raw_kmh: np.ndarray
    sensor: SensorConfig
    source_sha256: str
    quality: DataQualityReport = field(default_factory=DataQualityReport)
    meta: RunMeta = field(default_factory=RunMeta)

    def __post_init__(self) -> None:
        n = self.time_s.size
        _check(self.rpm_raw.size == n and self.vel_raw_kmh.size == n, "canais com tamanhos diferentes")
        for arr in (self.time_s, self.rpm_raw, self.vel_raw_kmh):
            arr.setflags(write=False)

    @property
    def n_samples(self) -> int:
        return int(self.time_s.size)

    @property
    def duration_s(self) -> float:
        return float(self.time_s[-1]) if self.time_s.size else 0.0

    @property
    def sample_rate_hz(self) -> float:
        return self.sensor.sample_rate_hz

    @property
    def content_hash(self) -> str:
        """Identidade dos dados: bytes do arquivo + configuração do sensor.

        É a chave do cache de processamento. Na v6 a chave dependia só do filtro, então
        duas runs diferentes compartilhavam o mesmo resultado (bug crítico).
        """
        return f"{self.source_sha256[:24]}:{self.sensor.digest()}"
