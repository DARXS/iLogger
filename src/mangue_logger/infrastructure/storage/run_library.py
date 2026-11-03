"""Biblioteca de runs em SQLite: busca por nome, tag, setup e período."""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from ...domain.models import Run
from ...domain.stats import RunStats

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class RunRecord:
    sha256: str
    name: str
    path: str
    added_at: float
    duration_s: float
    vel_max: float
    rpm_max: float
    tags: tuple[str, ...]
    setup: dict[str, str]
    notes: str


class RunLibrary:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._keep = sqlite3.connect(self.db_path) if self.db_path == ":memory:" else None
        with self._conn() as c:
            ver = c.execute("PRAGMA user_version").fetchone()[0]
            if ver == 0:
                c.executescript("""
                    CREATE TABLE runs(
                        sha256 TEXT PRIMARY KEY, name TEXT NOT NULL, path TEXT NOT NULL,
                        added_at REAL NOT NULL, duration_s REAL, vel_max REAL, rpm_max REAL,
                        tags TEXT NOT NULL DEFAULT '[]', setup TEXT NOT NULL DEFAULT '{}', notes TEXT DEFAULT '');
                    CREATE INDEX idx_runs_name ON runs(name);
                """)
                c.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = self._keep or sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            if self._keep is None:
                conn.close()

    def add(self, run: Run, stats: RunStats) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO runs(sha256,name,path,added_at,duration_s,vel_max,rpm_max,tags,setup,notes) "
                "VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(sha256) DO UPDATE SET path=excluded.path, "
                "name=excluded.name, tags=excluded.tags, setup=excluded.setup, notes=excluded.notes",
                (run.source_sha256, run.name, run.path, time.time(), stats.duration, stats.vel_max, stats.rpm_max,
                 json.dumps(list(run.meta.tags)), json.dumps(dict(run.meta.setup)), run.meta.notes))

    def search(self, text: str = "", tag: str | None = None, setup: dict[str, str] | None = None,
               since: float | None = None, limit: int = 200) -> list[RunRecord]:
        sql, args = "SELECT sha256,name,path,added_at,duration_s,vel_max,rpm_max,tags,setup,notes FROM runs WHERE 1=1", []
        if text:
            sql += " AND (name LIKE ? OR notes LIKE ?)"
            args += [f"%{text}%", f"%{text}%"]
        if since is not None:
            sql += " AND added_at >= ?"
            args.append(since)
        sql += " ORDER BY added_at DESC LIMIT ?"
        args.append(limit * 5 if (tag or setup) else limit)
        with self._conn() as c:
            rows = c.execute(sql, args).fetchall()
        out = []
        for sha, name, path, ts, dur, vmax, rmax, tags, st, notes in rows:
            tg, sd = tuple(json.loads(tags)), dict(json.loads(st))
            if tag and tag not in tg:
                continue
            if setup and any(sd.get(k) != v for k, v in setup.items()):
                continue
            out.append(RunRecord(sha, name, path, ts, dur or 0.0, vmax or 0.0, rmax or 0.0, tg, sd, notes or ""))
        return out[:limit]
