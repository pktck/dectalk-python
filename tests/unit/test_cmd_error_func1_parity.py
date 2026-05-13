"""C-source parity test for ``ERROR_func1`` against par_pars1.c.

Asserts the diagnostic marker literal and the
``ret_value->output_offset`` assignment are preserved, plus the
Python port writes the marker bytes-for-bytes.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.error_func1 import ERROR_func1, error_func1
from dectalk.cmd.par_structs import IndexData, MatchArrays, RangeValue, ReturnValue

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/par_pars1.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_par_pars1_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    """Locate the ``ERROR_func1`` body in par_pars1.c.

    The parameter list spans an ``#ifndef GERMAN_COMPOUND_NOUNS`` /
    ``#endif`` block, so the simple ``[^;{]+?`` pattern fails. We
    walk forward from the function name to the matching ``{`` and
    then track brace depth to extract the body.
    """
    text = _read_par_pars1_c()
    decl = re.search(r"void\s+ERROR_func1\s*\(", text)
    assert decl is not None, "ERROR_func1 declaration not found"
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


def test_writes_pud_fart_marker() -> None:
    """The C body calls ``strcpy(output_array + output_pos, "I am a pud-fart. ")``."""
    body = _extract_body()
    pattern = (
        r"strcpy\s*\(\s*output_array\s*\+\s*ret_value\s*->\s*output_pos\s*,"
        r'\s*"I am a pud-fart\. "\s*\)'
    )
    assert re.search(pattern, body)


def test_sets_output_offset_to_marker_length() -> None:
    """The C body sets ``output_offset = strlen("I am a pud-fart. ")``."""
    body = _extract_body()
    assert re.search(
        r'ret_value\s*->\s*output_offset\s*=\s*strlen\s*\(\s*"I am a pud-fart\. "\s*\)',
        body,
    )


def test_marker_literal_length_is_17() -> None:
    """The visible marker text has 17 bytes (strcpy adds a trailing NUL)."""
    assert len("I am a pud-fart. ") == 17


def test_python_writes_marker_at_output_pos() -> None:
    """Python writes the 17-byte marker starting at ``ret_value.output_pos``."""
    output = bytearray(64)
    ret = ReturnValue(output_pos=5)
    error_func1(
        b"",
        b"",
        output,
        [IndexData() for _ in range(64)],
        [IndexData() for _ in range(64)],
        MatchArrays(),
        ret,
        RangeValue(),
        0,
        0,
        0,
        0,
    )
    assert bytes(output[5:22]) == b"I am a pud-fart. "
    # The C strcpy writes the trailing NUL too.
    assert output[22] == 0
    # Bytes before the write are untouched.
    assert bytes(output[:5]) == b"\x00" * 5


def test_python_sets_output_offset_to_17() -> None:
    """Python sets ``ret_value.output_offset`` to the marker length (17)."""
    output = bytearray(64)
    ret = ReturnValue(output_pos=0, output_offset=99)
    error_func1(
        b"",
        b"",
        output,
        [IndexData() for _ in range(64)],
        [IndexData() for _ in range(64)],
        MatchArrays(),
        ret,
        RangeValue(),
        0,
        0,
        0,
        0,
    )
    assert ret.output_offset == 17


def test_python_c_style_alias_is_callable() -> None:
    """The ``ERROR_func1`` C-style alias points at the Python implementation."""
    assert ERROR_func1 is error_func1


def test_python_handles_output_pos_at_array_end() -> None:
    """The output buffer grows if ``output_pos`` is near its end."""
    output = bytearray(5)
    ret = ReturnValue(output_pos=2)
    error_func1(
        b"",
        b"",
        output,
        [IndexData() for _ in range(64)],
        [IndexData() for _ in range(64)],
        MatchArrays(),
        ret,
        RangeValue(),
        0,
        0,
        0,
        0,
    )
    assert bytes(output[2:19]) == b"I am a pud-fart. "
    assert output[19] == 0
