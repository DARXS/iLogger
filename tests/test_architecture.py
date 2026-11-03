"""Impõe as regras de dependência: o núcleo nunca conhece UI nem I/O concreto."""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "mangue_logger"
QT = ("PyQt6", "PyQt5", "PySide6", "pyqtgraph")


def imports(pkg: str) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for f in (SRC / pkg).rglob("*.py"):
        mods: set[str] = set()
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Import):
                mods |= {a.name for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                mods.add(("." * n.level) + (n.module or ""))
        out[str(f.relative_to(SRC))] = mods
    return out


def offenders(pkg: str, forbidden_abs: tuple[str, ...], forbidden_rel: tuple[str, ...]):
    bad = []
    for f, mods in imports(pkg).items():
        for m in mods:
            top = m.lstrip(".").split(".")[0]
            if (not m.startswith(".") and top in forbidden_abs) or (m.startswith("..") and top in forbidden_rel):
                bad.append((f, m))
    return bad


def test_domain_is_pure():
    assert offenders("domain", QT + ("matplotlib", "reportlab", "xlsxwriter"), ("application", "infrastructure", "presentation")) == []


def test_application_has_no_ui_or_concrete_io():
    assert offenders("application", QT, ("infrastructure", "presentation")) == []


def test_infrastructure_has_no_ui():
    assert offenders("infrastructure", QT, ("presentation",)) == []


def test_no_legacy_module_imports_left():
    for pkg in ("domain", "application", "infrastructure", "presentation"):
        for f, mods in imports(pkg).items():
            assert not mods & {"config", "engine", "exporters", "processing_core"}, f


def test_no_eval_or_exec_in_package():
    for f in SRC.rglob("*.py"):
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in {"eval", "exec"}:
                raise AssertionError(f"{f}: {n.func.id}()")
