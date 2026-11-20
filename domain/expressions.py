"""Avaliador seguro de expressões para canais virtuais.

Substitui o ``eval`` da v6. Aqui a expressão é *interpretada* a partir da AST com uma
lista fechada de nós, funções e variáveis: sem acesso a atributos arbitrários, imports,
lambdas, comprehensions ou builtins. Constantes viram float64, então potências gigantes
estouram para ``inf`` em vez de travar o processo.
"""

from __future__ import annotations

import ast
import operator as op
from collections.abc import Callable, Mapping
from typing import Any

import numpy as np

from .errors import ExpressionError

MAX_LEN = 500
MAX_NODES = 200

_BIN: dict[type, Callable[[Any, Any], Any]] = {
    ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv,
    ast.Mod: op.mod, ast.Pow: np.power, ast.BitAnd: op.and_, ast.BitOr: op.or_,
}
_UN: dict[type, Callable[[Any], Any]] = {ast.USub: op.neg, ast.UAdd: op.pos, ast.Invert: np.invert}
_CMP: dict[type, Callable[[Any, Any], Any]] = {
    ast.Lt: op.lt, ast.LtE: op.le, ast.Gt: op.gt, ast.GtE: op.ge, ast.Eq: op.eq, ast.NotEq: op.ne,
}

FUNCTIONS: dict[str, Callable[..., Any]] = {
    "abs": np.abs, "sqrt": np.sqrt, "log": np.log, "log10": np.log10, "exp": np.exp,
    "sin": np.sin, "cos": np.cos, "tan": np.tan, "arctan": np.arctan, "arctan2": np.arctan2,
    "mean": np.mean, "median": np.median, "std": np.std, "min": np.min, "max": np.max, "sum": np.sum,
    "clip": np.clip, "grad": np.gradient, "gradient": np.gradient, "cumsum": np.cumsum, "diff": np.diff,
    "interp": np.interp, "where": np.where, "minimum": np.minimum, "maximum": np.maximum,
    "sign": np.sign, "fft": np.fft.rfft, "ifft": np.fft.irfft,
}
CONSTANTS = {"pi": float(np.pi), "e": float(np.e)}
VARIABLES = ("tempo", "vel", "rpm", "acel", "dist", "rpm_raw", "vel_raw")


def _fail(msg: str) -> ExpressionError:
    return ExpressionError(msg)


def parse(expression: str) -> ast.Expression:
    """Valida sintaxe + lista branca de nós. Levanta ExpressionError."""
    if not expression or not expression.strip():
        raise _fail("expressão vazia")
    if len(expression) > MAX_LEN:
        raise _fail(f"expressão maior que {MAX_LEN} caracteres")
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as exc:
        raise _fail(f"sintaxe inválida: {exc.msg}") from exc
    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_NODES:
        raise _fail("expressão complexa demais")
    for n in nodes:
        _check_node(n)
    return tree


def _check_node(n: ast.AST) -> None:
    if isinstance(n, (ast.Expression, ast.Load, ast.Slice, ast.Tuple, ast.operator, ast.unaryop, ast.cmpop)):
        return  # operadores são validados no nó pai (BinOp/UnaryOp/Compare)
    if isinstance(n, ast.BinOp):
        if type(n.op) not in _BIN:
            raise _fail(f"operador não permitido: {type(n.op).__name__}")
    elif isinstance(n, ast.UnaryOp):
        if type(n.op) not in _UN:
            raise _fail(f"operador não permitido: {type(n.op).__name__}")
    elif isinstance(n, ast.Compare):
        if any(type(o) not in _CMP for o in n.ops):
            raise _fail("comparação não permitida")
    elif isinstance(n, ast.Constant):
        if isinstance(n.value, bool) or not isinstance(n.value, (int, float)):
            raise _fail("apenas constantes numéricas são permitidas")
    elif isinstance(n, ast.Name):
        if n.id not in VARIABLES and n.id not in FUNCTIONS and n.id not in CONSTANTS and n.id != "np":
            raise _fail(f"nome desconhecido: {n.id!r}")
    elif isinstance(n, ast.Attribute):
        if not (isinstance(n.value, ast.Name) and n.value.id == "np" and n.attr in FUNCTIONS | CONSTANTS):
            raise _fail("acesso a atributos só é permitido como np.<função>")
    elif isinstance(n, ast.Call):
        if not isinstance(n.func, (ast.Name, ast.Attribute)):
            raise _fail("chamada inválida")
        if any(k.arg is None for k in n.keywords):
            raise _fail("**kwargs não permitido")
    elif isinstance(n, (ast.keyword, ast.Subscript)):
        return
    else:
        raise _fail(f"construção não permitida: {type(n).__name__}")


def evaluate(expression: str, variables: Mapping[str, np.ndarray]) -> np.ndarray:
    """Avalia a expressão e devolve um ndarray 1-D."""
    tree = parse(expression)
    env: dict[str, Any] = {k: v for k, v in variables.items() if k in VARIABLES}
    try:
        with np.errstate(all="ignore"):
            result = _eval(tree.body, env)
    except ExpressionError:
        raise
    except (ValueError, TypeError, IndexError, ZeroDivisionError, OverflowError, MemoryError) as exc:
        raise _fail(f"erro ao avaliar: {exc}") from exc
    arr = np.asarray(result)
    if arr.dtype == bool:
        arr = arr.astype(float)
    if np.iscomplexobj(arr):
        raise _fail("resultado complexo: use abs(fft(...))")
    ref = next(iter(env.values()), np.empty(0))
    if arr.ndim == 0:
        return np.full(ref.shape, float(arr))
    if arr.ndim != 1:
        raise _fail("resultado deve ser 1-D")
    if arr.size == ref.size - 1 and arr.size > 0:  # ex.: diff() — repete o último ponto
        arr = np.append(arr, arr[-1])
    if arr.size != ref.size:
        raise _fail(f"resultado com {arr.size} pontos; esperado {ref.size}")
    return arr.astype(np.float64, copy=False)


def _eval(n: ast.AST, env: Mapping[str, Any]) -> Any:
    if isinstance(n, ast.Constant):
        return np.float64(float(n.value))  # type: ignore[arg-type]  # _check_node garante int|float
    if isinstance(n, ast.Name):
        if n.id in env:
            return env[n.id]
        if n.id in CONSTANTS:
            return np.float64(CONSTANTS[n.id])
        if n.id in FUNCTIONS:
            return FUNCTIONS[n.id]
        raise _fail(f"nome desconhecido: {n.id!r}")
    if isinstance(n, ast.Attribute):
        return CONSTANTS.get(n.attr, FUNCTIONS.get(n.attr))
    if isinstance(n, ast.BinOp):
        return _BIN[type(n.op)](_eval(n.left, env), _eval(n.right, env))
    if isinstance(n, ast.UnaryOp):
        return _UN[type(n.op)](_eval(n.operand, env))
    if isinstance(n, ast.Compare):
        left, res = _eval(n.left, env), None
        for o, comp in zip(n.ops, n.comparators, strict=True):
            right = _eval(comp, env)
            cur = _CMP[type(o)](left, right)
            res = cur if res is None else (res & cur)
            left = right
        return res
    if isinstance(n, ast.Call):
        fn = _eval(n.func, env)
        if not callable(fn):
            raise _fail("chamada de valor não-função")
        args = [_eval(a, env) for a in n.args]
        kwargs = {k.arg: _eval(k.value, env) for k in n.keywords if k.arg}
        return fn(*args, **kwargs)
    if isinstance(n, ast.Subscript):
        return _eval(n.value, env)[_index(n.slice, env)]
    raise _fail(f"construção não permitida: {type(n).__name__}")


def _index(s: ast.AST, env: Mapping[str, Any]) -> Any:
    if isinstance(s, ast.Slice):
        def part(x: ast.AST | None) -> int | None:
            return None if x is None else _int(_eval(x, env))
        return slice(part(s.lower), part(s.upper), part(s.step))
    if isinstance(s, ast.Tuple):
        raise _fail("indexação multidimensional não permitida")
    return _int(_eval(s, env))


def _int(v: Any) -> int:
    f = float(v)
    if not f.is_integer():
        raise _fail("índices devem ser inteiros")
    return int(f)
