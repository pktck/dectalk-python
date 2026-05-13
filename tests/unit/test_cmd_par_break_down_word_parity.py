"""C-source parity test for ``par_break_down_word`` against par_pars1.c.

Asserts the function's early-failure path (gated by
``par_find_word_in_dict`` returning 0) is preserved.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.par_break_down_word import par_break_down_word

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/par_pars1.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_par_pars1_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    text = _read_par_pars1_c()
    match = re.search(
        r"int\s+par_break_down_word\s*\([^)]*\)\s*\n\{(.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "par_break_down_word body not found"
    return match.group(1)


def test_returns_minus_1_on_no_match() -> None:
    """``if (result == 0) return -1;`` short-circuit."""
    body = _extract_body()
    assert re.search(
        r"if\s*\(\s*result\s*==\s*0\s*\)",
        body,
    )
    assert re.search(r"return\s*\(?\s*-\s*1\s*\)?\s*;", body)


def test_calls_par_find_word_in_dict() -> None:
    """The function dispatches to ``par_find_word_in_dict``."""
    body = _extract_body()
    assert "par_find_word_in_dict" in body


def test_python_returns_minus_one_on_us_build() -> None:
    """The US build's permanent state has the noun dict empty -> ``-1``."""
    output = bytearray(100)
    assert par_break_down_word(b"compound", output) == -1


def test_python_does_not_mutate_output() -> None:
    """On the early-fail path, the output buffer stays untouched."""
    output = bytearray(b"\x01" * 10)
    par_break_down_word(b"anything", output)
    assert output == b"\x01" * 10
