"""Persistência dos metadados da run em ``<arquivo>.csv.meta.json`` (escrita atômica)."""

from __future__ import annotations

from pathlib import Path

from ...domain.models import RunMeta
from ..storage._atomic import write_json


def meta_path(csv_path: str) -> Path:
    return Path(csv_path + ".meta.json")


def write_run_meta(csv_path: str, meta: RunMeta) -> Path:
    path = meta_path(csv_path)
    write_json(path, meta.to_dict())
    return path
