"""Geração de CSV a partir do log binário via DLL (somente Windows). Sem Qt: erros são exceções."""

from __future__ import annotations

import ctypes
import os
from pathlib import Path

from ...domain.errors import MangueLoggerError

DLL_NAME = "libshared_read_object.dll"
ENV_VAR = "MANGUE_LOGGER_DLL"


class DllError(MangueLoggerError):
    pass


def find_dll(explicit: str | None = None) -> Path:
    """Ordem de busca: argumento → variável de ambiente → ao lado do pacote → cwd."""
    candidates = [explicit, os.environ.get(ENV_VAR), Path(__file__).resolve().parents[2] / DLL_NAME,
                  Path.cwd() / DLL_NAME]
    for c in candidates:
        if c and Path(c).is_file():
            return Path(c).resolve()
    tried = [str(c) for c in candidates if c]
    raise DllError(f"{DLL_NAME} não encontrada. Procurado em: {tried or '(nenhum caminho)'}. "
                   f"Defina {ENV_VAR} ou coloque a DLL ao lado do aplicativo.")


def generate_csv_from_dll(run_dir: str, save_dir: str, run_number: int | str, dll_path: str | None = None) -> None:
    try:
        n = int(run_number)
    except (TypeError, ValueError) as exc:
        raise DllError(f"número da RUN inválido: {run_number!r}") from exc
    if not os.path.isdir(run_dir):
        raise DllError(f"diretório das RUNs não existe: {run_dir}")
    os.makedirs(save_dir, exist_ok=True)
    path = find_dll(dll_path)
    try:
        lib = ctypes.CDLL(str(path))
        lib.read_struct.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
        lib.read_struct(run_dir.encode("utf8"), save_dir.encode("utf8"), n)
    except (OSError, AttributeError) as exc:  # DLL de outra plataforma/arquitetura ou sem o símbolo
        raise DllError(f"falha ao carregar/chamar {path.name}: {exc}") from exc
