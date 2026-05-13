"""C-source parity test for ``par_status_string`` against par_pars1.c.

Re-parses the C function body and asserts structural patterns
match the Python port:

- the call into :func:`par_build_string_from_rule` with
  ``BIN_STATUS``,
- the ``ret_value->parser_flag = atoi(buf)`` assignment.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.par_bin_codes import BIN_EXACT
from dectalk.cmd.par_limits import PAR_MAX_OUTPUT_ARRAY
from dectalk.cmd.par_status_string import par_status_string
from dectalk.cmd.par_structs import IndexData, MatchArrays, RangeValue, ReturnValue
from dectalk.cmd.rule_states import FATAL_FAIL

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/par_pars1.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_par_pars1_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    text = _read_par_pars1_c()
    # par_status_string appears twice: once as a forward declaration (ends in
    # `;`) and once as a definition (ends in `{`). The signature also spans a
    # GERMAN_COMPOUND_NOUNS `#ifndef/#else/#endif` block, so we can't use a
    # simple paren-balanced regex. Find every occurrence of the function name
    # by name; for each, walk forward looking for either `;` (forward decl,
    # skip) or `{` (definition, return body).
    for match in re.finditer(r"void\s+par_status_string\s*\(", text):
        # Walk forward until we hit either `;` (forward decl) or `{` (body).
        i = match.end()
        while i < len(text) and text[i] not in ";{":
            i += 1
        if i >= len(text) or text[i] == ";":
            continue
        # Found a `{` — walk the body until brace depth hits 0.
        start = i + 1
        depth = 1
        i = start
        while i < len(text) and depth > 0:
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        body = text[start:i]
        if "par_build_string_from_rule" in body:
            return body
    raise AssertionError("par_status_string body not found")


def _empty_indexes(n: int = PAR_MAX_OUTPUT_ARRAY) -> list[IndexData]:
    return [IndexData() for _ in range(n)]


# --------------------------------------------------------------------------
# C-source structural tests.
# --------------------------------------------------------------------------


def test_signature_present() -> None:
    """The C signature exists in the source."""
    text = _read_par_pars1_c()
    assert re.search(
        r"void\s+par_status_string\s*\(\s*unsigned\s+char\s*\*\s*current_rule",
        text,
    )


def test_calls_par_build_string_with_bin_status() -> None:
    """The body invokes ``par_build_string_from_rule(...BIN_STATUS, &length, in_rule_index)``.

    The Python port forwards the same final three arguments — the
    ``&length`` C pointer becomes a ``list[int]`` length-box. The
    Python port substitutes :func:`par_convert_number_new2` for the
    C-side :c:func:`atoi`; the two are byte-equivalent on the purely
    decimal, NUL-terminated buffers the C source produces.
    """
    body = _extract_body()
    assert "par_build_string_from_rule" in body
    assert "BIN_STATUS" in body
    assert re.search(
        r"par_build_string_from_rule\s*\([^;]*BIN_STATUS\s*,\s*&\s*length\s*,\s*in_rule_index\s*\)",
        body,
    )


def test_parser_flag_set_from_atoi_of_buf() -> None:
    """``ret_value->parser_flag = atoi(buf)`` is the final assignment.

    The Python port stores the converted value in ``ret_value.parser_flag``
    using :func:`par_convert_number_new2` instead of :c:func:`atoi`.
    """
    body = _extract_body()
    assert re.search(
        r"ret_value\s*->\s*parser_flag\s*=\s*atoi\s*\(\s*buf\s*\)",
        body,
    )


def test_buf_is_10_byte_stack_buffer() -> None:
    """``unsigned char buf[10]`` is the local buffer size."""
    body = _extract_body()
    assert re.search(r"unsigned\s+char\s+buf\s*\[\s*10\s*\]", body)


# --------------------------------------------------------------------------
# Behavioural tests for the Python port.
# --------------------------------------------------------------------------


def test_decimal_status_lands_in_parser_flag() -> None:
    """A BIN_EXACT body of ``"42"`` makes parser_flag == 42.

    Also confirms the void return (None) and that the success path
    does NOT touch ``ret_value.value`` (i.e. it is not FATAL_FAIL).
    """
    rule = bytearray(20)
    rule[0] = 0x1E  # BIN_STATUS
    rule[2] = 7
    rule[4] = BIN_EXACT
    rule[5] = 2
    rule[6] = ord("4")
    rule[7] = ord("2")
    ret = ReturnValue(rule=4)
    result = par_status_string(
        bytes(rule),
        bytearray(),
        bytearray(b"\x00" * 50),
        _empty_indexes(),
        _empty_indexes(),
        MatchArrays(),
        ret,
        RangeValue(),
        0,
        0,
        0,
        0,
    )
    assert result is None  # C function is `void`.
    assert ret.parser_flag == 42
    assert ret.value != FATAL_FAIL


def test_zero_status_is_zero() -> None:
    """A BIN_EXACT body of ``"0"`` leaves parser_flag at 0."""
    rule = bytearray(20)
    rule[0] = 0x1E
    rule[2] = 6
    rule[4] = BIN_EXACT
    rule[5] = 1
    rule[6] = ord("0")
    ret = ReturnValue(rule=4)
    par_status_string(
        bytes(rule),
        bytearray(),
        bytearray(b"\x00" * 50),
        _empty_indexes(),
        _empty_indexes(),
        MatchArrays(),
        ret,
        RangeValue(),
        0,
        0,
        0,
        0,
    )
    assert ret.parser_flag == 0


def test_multi_digit_status_parses_correctly() -> None:
    """A BIN_EXACT body of ``"123"`` makes parser_flag == 123."""
    rule = bytearray(20)
    rule[0] = 0x1E
    rule[2] = 8
    rule[4] = BIN_EXACT
    rule[5] = 3
    rule[6:9] = b"123"
    ret = ReturnValue(rule=4)
    par_status_string(
        bytes(rule),
        bytearray(),
        bytearray(b"\x00" * 50),
        _empty_indexes(),
        _empty_indexes(),
        MatchArrays(),
        ret,
        RangeValue(),
        0,
        0,
        0,
        0,
    )
    assert ret.parser_flag == 123
