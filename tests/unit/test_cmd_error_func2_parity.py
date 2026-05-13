"""C-source parity test for ``ERROR_func2`` against par_pars1.c.

Asserts the C body is just ``return;`` and the Python port is a
no-op that leaves every passed-in argument unchanged.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.error_func2 import ERROR_func2, error_func2
from dectalk.cmd.par_structs import IndexData, MatchArrays, RangeValue, ReturnValue

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/par_pars1.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_par_pars1_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    """Locate the ``ERROR_func2`` body in par_pars1.c.

    The parameter list spans an ``#ifndef GERMAN_COMPOUND_NOUNS`` /
    ``#endif`` block, so a simple ``[^;{]+?`` pattern can't cross
    the cpp directives. We walk to the opening brace manually and
    then track brace depth to extract the body.
    """
    text = _read_par_pars1_c()
    decl = re.search(r"void\s+ERROR_func2\s*\(", text)
    assert decl is not None, "ERROR_func2 declaration not found"
    brace_start = text.index("{", decl.end())
    depth = 1
    i = brace_start + 1
    while i < len(text) and depth > 0:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    return text[brace_start + 1 : i - 1]


def test_body_is_just_return() -> None:
    """The C body has no statements other than a single ``return;``."""
    body = _extract_body()
    # Strip leading/trailing whitespace; the body should be just ``return;``.
    stripped = body.strip()
    assert stripped == "return;", f"unexpected body: {stripped!r}"


def test_python_does_not_mutate_output() -> None:
    """The Python no-op leaves output_array untouched."""
    output = bytearray(b"\x01" * 16)
    ret = ReturnValue(output_pos=4, output_offset=8)
    error_func2(
        b"",
        b"",
        output,
        [IndexData() for _ in range(16)],
        [IndexData() for _ in range(16)],
        MatchArrays(),
        ret,
        RangeValue(),
        0,
        0,
        0,
        0,
    )
    assert output == bytearray(b"\x01" * 16)


def test_python_does_not_mutate_ret_value() -> None:
    """The Python no-op leaves the ret_value cursors untouched."""
    ret = ReturnValue(output_pos=4, output_offset=8, value=99)
    error_func2(
        b"",
        b"",
        bytearray(),
        [],
        [],
        MatchArrays(),
        ret,
        RangeValue(),
        0,
        0,
        0,
        0,
    )
    assert ret.output_pos == 4
    assert ret.output_offset == 8
    assert ret.value == 99


def test_python_returns_none() -> None:
    """The Python no-op returns ``None`` (the C ``void`` analogue)."""
    ret = ReturnValue()
    result = error_func2(
        b"",
        b"",
        bytearray(),
        [],
        [],
        MatchArrays(),
        ret,
        RangeValue(),
        0,
        0,
        0,
        0,
    )
    assert result is None


def test_python_c_style_alias_is_callable() -> None:
    """The ``ERROR_func2`` C-style alias points at the Python implementation."""
    assert ERROR_func2 is error_func2
