""".mlproj — projeto reprodutível: runs (com SHA-256), perfil do veículo, filtro, setup e canais virtuais."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ... import __version__
from ...application.session import Session
from ...domain.errors import ValidationError
from ...domain.models import VehicleProfile
from ._atomic import read_json, write_json

SCHEMA_VERSION = 1


@dataclass
class ProjectData:
    profile: VehicleProfile
    filter_settings: dict[str, Any]
    setup_info: dict[str, str]
    observations: str
    run_paths: list[str]
    virtual_channels: list[dict[str, Any]] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)       # caminhos que não existem mais
    changed: list[str] = field(default_factory=list)      # arquivos cujo conteúdo mudou desde que o projeto foi salvo


def save_project(path: str, session: Session, virtual_channels: list[dict[str, Any]] | None = None) -> None:
    write_json(Path(path), {
        "schema_version": SCHEMA_VERSION, "app_version": __version__, "saved_at": time.time(),
        "profile": session.profile.to_dict(), "filter_settings": session.filter_settings,
        "setup_info": session.setup_info, "observations": session.observations,
        "virtual_channels": virtual_channels or [],
        "runs": [{"path": r.file_path, "name": r.file_name, "sha256": r.run.source_sha256} for r in session.runs],
    })


def load_project(path: str) -> ProjectData:
    raw = read_json(Path(path))
    if not isinstance(raw, dict):
        raise ValidationError("projeto inválido: esperado objeto JSON")
    ver = raw.get("schema_version")
    if ver != SCHEMA_VERSION:
        raise ValidationError(f"versão de projeto não suportada: {ver!r} (esperado {SCHEMA_VERSION})")
    runs = raw.get("runs", [])
    if not isinstance(runs, list):
        raise ValidationError("projeto inválido: 'runs' deve ser lista")
    base = Path(path).resolve().parent
    paths, missing, changed = [], [], []
    import hashlib
    for r in runs:
        p = Path(r["path"])
        if not p.is_absolute() and not p.exists():
            p = base / p  # projeto movido junto com os CSVs
        if not p.is_file():
            missing.append(str(r["path"]))
            continue
        paths.append(str(p))
        if r.get("sha256") and hashlib.sha256(p.read_bytes()).hexdigest() != r["sha256"]:
            changed.append(str(p))
    return ProjectData(
        profile=VehicleProfile.from_dict(raw.get("profile", {})),
        filter_settings=dict(raw.get("filter_settings", {})),
        setup_info={str(k): str(v) for k, v in dict(raw.get("setup_info", {})).items()},
        observations=str(raw.get("observations", "")),
        run_paths=paths, virtual_channels=list(raw.get("virtual_channels", [])),
        missing=missing, changed=changed,
    )
