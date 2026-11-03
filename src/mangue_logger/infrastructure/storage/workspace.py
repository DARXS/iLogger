"""WorkspaceManager: layouts, presets, canais virtuais, recentes, tema.

Sem efeitos colaterais no import (a v6 criava ~/.mangue_logger ao importar o módulo).
Diretórios nascem na primeira escrita; tudo é validado ao importar de terceiros.
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Any

from ...application.virtual_channels import VirtualChannel
from ...domain.errors import ExpressionError
from ._atomic import read_json, write_json

log = logging.getLogger(__name__)


def default_dir() -> Path:
    return Path.home() / ".mangue_logger"


def _safe_name(name: str) -> str:
    return re.sub(r"[^\w \-]", "_", name, flags=re.UNICODE).strip() or "layout"


class WorkspaceManager:
    def __init__(self, base_dir: Path | None = None):
        self.base = Path(base_dir) if base_dir else default_dir()
        self.last_import_skipped = 0
        self._presets: list[dict] = self._load_list(self.base / "presets.json")
        self._recent: list[dict] = self._load_list(self.base / "recent.json")
        self._virtuals: list[VirtualChannel] = []
        for d in self._load_list(self.base / "virtual_channels.json"):
            self._add_virtual_from_dict(d)

    # ── util ──────────────────────────────────────────────────────────────────
    @staticmethod
    def _load_list(path: Path) -> list:
        if not path.exists():
            return []
        try:
            data = read_json(path)
            return data if isinstance(data, list) else []
        except (OSError, ValueError) as exc:
            log.warning("não foi possível ler %s: %s", path, exc)
            return []

    def _add_virtual_from_dict(self, d: Any) -> bool:
        if not isinstance(d, dict):
            return False
        vc = VirtualChannel.from_dict(d)
        try:
            vc.validate()
        except ExpressionError as exc:
            log.warning("canal virtual %r rejeitado: %s", vc.name, exc)
            return False
        if not vc.name:
            return False
        self._virtuals = [v for v in self._virtuals if v.name != vc.name] + [vc]
        return True

    @property
    def _layouts_dir(self) -> Path:
        return self.base / "layouts"

    # ── layouts ───────────────────────────────────────────────────────────────
    def save_layout(self, name: str, data: dict) -> None:
        data = {**data, "name": name, "ts": time.time()}
        write_json(self._layouts_dir / f"{_safe_name(name)}.json", data)

    def _iter_layouts(self):
        if not self._layouts_dir.exists():
            return
        for p in sorted(self._layouts_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                d = read_json(p)
            except (OSError, ValueError):
                continue
            if isinstance(d, dict):
                yield p, d

    def list_layouts(self) -> list[str]:
        return [d.get("name", p.stem) for p, d in self._iter_layouts()]

    def load_layout(self, name: str) -> dict | None:
        return next((d for _, d in self._iter_layouts() if d.get("name") == name), None)

    def delete_layout(self, name: str) -> None:
        for p, d in self._iter_layouts():
            if d.get("name") == name:
                p.unlink()
                return

    # ── presets de filtro ─────────────────────────────────────────────────────
    def list_presets(self) -> list[str]:
        return [p["name"] for p in self._presets]

    def get_preset(self, name: str) -> dict | None:
        return next((p["settings"] for p in self._presets if p["name"] == name), None)

    def save_preset(self, name: str, settings: dict) -> None:
        self._presets = [p for p in self._presets if p["name"] != name]
        self._presets.append({"name": name, "settings": settings, "ts": time.time()})
        write_json(self.base / "presets.json", self._presets)

    def delete_preset(self, name: str) -> None:
        self._presets = [p for p in self._presets if p["name"] != name]
        write_json(self.base / "presets.json", self._presets)

    # ── canais virtuais ───────────────────────────────────────────────────────
    def list_virtuals(self) -> list[VirtualChannel]:
        return list(self._virtuals)

    def save_virtual(self, vc: VirtualChannel) -> None:
        vc.validate()  # levanta ExpressionError: a UI mostra a mensagem
        self._virtuals = [v for v in self._virtuals if v.name != vc.name] + [vc]
        write_json(self.base / "virtual_channels.json", [v.to_dict() for v in self._virtuals])

    def delete_virtual(self, name: str) -> None:
        self._virtuals = [v for v in self._virtuals if v.name != name]
        write_json(self.base / "virtual_channels.json", [v.to_dict() for v in self._virtuals])

    # ── recentes / tema ───────────────────────────────────────────────────────
    def push_recent(self, paths: list[str]) -> None:
        self._recent = [r for r in self._recent if set(r.get("paths", [])) != set(paths)]
        self._recent.insert(0, {"paths": paths, "ts": time.time()})
        self._recent = self._recent[:12]
        write_json(self.base / "recent.json", self._recent)

    def get_recent(self) -> list[dict]:
        return list(self._recent)

    def save_theme(self, data: dict) -> None:
        write_json(self.base / "theme.json", data)

    def load_theme(self) -> dict | None:
        p = self.base / "theme.json"
        try:
            return read_json(p) if p.exists() else None
        except (OSError, ValueError):
            return None

    # ── export / import ───────────────────────────────────────────────────────
    def export_all(self, path: str) -> None:
        write_json(Path(path), {
            "version": "7.0", "exported_at": time.time(),
            "layouts": [d for _, d in self._iter_layouts()],
            "presets": self._presets, "virtuals": [v.to_dict() for v in self._virtuals],
        })

    def import_all(self, path: str) -> tuple[int, int, int]:
        """Importa de terceiros. Expressões inseguras/ inválidas são descartadas (ver `last_import_skipped`)."""
        data = read_json(Path(path))
        if not isinstance(data, dict):
            raise ValueError("arquivo de workspace inválido")
        self.last_import_skipped = 0
        n_l = n_p = n_v = 0
        for d in data.get("layouts", []):
            if isinstance(d, dict):
                self.save_layout(str(d.get("name", "Importado")), d)
                n_l += 1
        for d in data.get("presets", []):
            if isinstance(d, dict) and "name" in d and isinstance(d.get("settings"), dict):
                self.save_preset(str(d["name"]), d["settings"])
                n_p += 1
        for d in data.get("virtuals", []):
            if self._add_virtual_from_dict(d):
                n_v += 1
            else:
                self.last_import_skipped += 1
        write_json(self.base / "virtual_channels.json", [v.to_dict() for v in self._virtuals])
        return n_l, n_p, n_v
