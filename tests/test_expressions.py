import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from mangue_logger.domain import expressions as ex
from mangue_logger.domain.errors import ExpressionError

V = {"vel": np.linspace(0, 50, 100), "rpm": np.linspace(1000, 3500, 100), "tempo": np.arange(100) * 0.05,
     "acel": np.zeros(100), "dist": np.zeros(100), "rpm_raw": np.zeros(100), "vel_raw": np.zeros(100)}


def test_valid_expressions():
    assert np.allclose(ex.evaluate("rpm / (vel + 1)", V), V["rpm"] / (V["vel"] + 1))
    assert ex.evaluate("np.sqrt(vel) * 2", V).shape == (100,)
    assert ex.evaluate("clip(vel, 10, 40)", V).max() == 40
    assert ex.evaluate("diff(vel)", V).shape == (100,)           # repete o último ponto
    assert ex.evaluate("where(vel > 25, 1, 0)", V).sum() == 50
    assert ex.evaluate("vel[1:] * 1", V).shape == (100,)  # n-1 → repete último ponto


@pytest.mark.parametrize("bad", [
    "__import__('os').system('echo pwned')",
    "().__class__.__bases__[0].__subclasses__()",
    "vel.__class__", "open('/etc/passwd')", "eval('1')", "exec('x=1')",
    "(lambda: 1)()", "[x for x in vel]", "np.load('x.npy')", "np.fft.rfft(vel)",
    "vel if 1 else 2", "'a' + 'b'", "unknown_name + 1", "vel; vel", "", "   ",
    "x" * 600, "getattr(vel, 'T')", "vel.T", "{}", "[1,2]", "vel @ vel", "vel and rpm",
])
def test_unsafe_or_invalid_is_rejected(bad):
    with pytest.raises(ExpressionError):
        ex.evaluate(bad, V)


def test_huge_power_does_not_hang_or_crash():
    r = ex.evaluate("vel * 0 + 10 ** 10 ** 10", V)
    assert np.isinf(r).all()


def test_wrong_length_is_rejected():
    with pytest.raises(ExpressionError):
        ex.evaluate("vel[10:50]", V)


@settings(deadline=None, max_examples=200)
@given(st.text(max_size=80))
def test_fuzz_never_raises_anything_but_expression_error(text):
    try:
        ex.evaluate(text, V)
    except ExpressionError:
        pass
