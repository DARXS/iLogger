"""Executa os testes unitários JS (node --test) como parte do pytest."""

import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js não instalado")
def test_node_unit_tests():
    f = Path(__file__).parent / "js" / "util.test.mjs"
    r = subprocess.run(["node", "--test", str(f)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
