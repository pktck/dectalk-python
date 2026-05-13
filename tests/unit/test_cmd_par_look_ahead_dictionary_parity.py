"""C-source parity test for ``par_look_ahead_dictionary`` against par_pars1.c.

Re-parses the C function body (lines 3627-3650) via brace-depth
tracking and asserts the wrapper structure -- the delegation to
``par_match_rule(..., BIN_DICTIONARY, ...)`` and the
``ret_value->value == SUCCESS`` -> ``return(1)`` / fall-through
``return(0)`` shape -- matches the Python stub's contract.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.par_look_ahead_dictionary import par_look_ahead_dictionary
from dectalk.cmd.par_structs import MatchArrays, ReturnValue
from dectalk.cmd.rule_states import FAIL, SUCCESS

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/par_pars1.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_par_pars1_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    """Locate the ``par_look_ahead_dictionary`` definition body via brace depth."""
    text = _read_par_pars1_c()
    matches = list(
        re.finditer(
            r"int\s+par_look_ahead_dictionary\s*\([^;{]+?\)\s*\n\{",
            text,
            re.MULTILINE,
        )
    )
    assert matches, "par_look_ahead_dictionary definition not found"
    start = matches[-1].start()
    body_start = text.index("{", start)
    depth = 1
    i = body_start + 1
    while i < len(text) and depth > 0:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    return text[start:i]


# --------------------------------------------------------------------------
# C-source structural tests.
# --------------------------------------------------------------------------


def test_signature_matches() -> None:
    """The C signature carries the expected four parameters."""
    text = _read_par_pars1_c()
    assert re.search(
        r"int\s+par_look_ahead_dictionary\s*\(\s*"
        r"unsigned\s+char\s*\*\s*current_rule\s*,\s*"
        r"unsigned\s+char\s*\*\s*input_array\s*,\s*"
        r"pmatch_arrays_t\s+match_array\s*,\s*"
        r"preturn_value_t\s+ret_value\s*\)",
        text,
    )


def test_allocates_100_byte_scratch_buffers() -> None:
    """The body declares a 100-byte ``temp_output`` and 100-entry ``temp_indexes``."""
    body = _extract_body()
    assert re.search(r"unsigned\s+char\s+temp_output\s*\[\s*100\s*\]\s*;", body)
    assert re.search(r"index_data_t\s+temp_indexes\s*\[\s*100\s*\]\s*;", body)


def test_zeros_ret_value_output_cursor() -> None:
    """``ret_value->output_pos`` / ``output_offset`` are zeroed at function entry."""
    body = _extract_body()
    assert re.search(r"ret_value\s*->\s*output_pos\s*=\s*0\s*;", body)
    assert re.search(r"ret_value\s*->\s*output_offset\s*=\s*0\s*;", body)


def test_primes_ret_value_to_success() -> None:
    """``ret_value->value = SUCCESS`` is set before the rule-match call."""
    body = _extract_body()
    assert re.search(r"ret_value\s*->\s*value\s*=\s*SUCCESS\s*;", body)


def test_delegates_to_par_match_rule_with_bin_dictionary() -> None:
    """The body calls ``par_match_rule(current_rule, BIN_DICTIONARY, ...)``."""
    body = _extract_body()
    assert "par_match_rule" in body
    assert "BIN_DICTIONARY" in body
    # The opcode appears as the second positional argument.
    assert re.search(
        r"par_match_rule\s*\(\s*current_rule\s*,\s*BIN_DICTIONARY\b",
        body,
    )


def test_success_branch_returns_one() -> None:
    """``if (ret_value->value == SUCCESS) return(1)`` is present."""
    body = _extract_body()
    assert re.search(r"ret_value\s*->\s*value\s*==\s*SUCCESS", body)
    assert re.search(r"return\s*\(\s*1\s*\)\s*;", body)


def test_fall_through_returns_zero() -> None:
    """The fall-through path is ``return(0)``."""
    body = _extract_body()
    assert re.search(r"return\s*\(\s*0\s*\)\s*;", body)


# --------------------------------------------------------------------------
# Behavioural tests for the Python stub.
# --------------------------------------------------------------------------


def test_stub_returns_zero() -> None:
    """The stub reports no dictionary match (par_match_rule isn't ported)."""
    ret = ReturnValue()
    result = par_look_ahead_dictionary(b"", bytearray(b""), MatchArrays(), ret)
    assert result == 0


def test_stub_primes_ret_value_to_success() -> None:
    """``ret_value.value`` is set to :data:`SUCCESS` (mirroring the C pre-state)."""
    ret = ReturnValue(value=FAIL)
    par_look_ahead_dictionary(b"", bytearray(b""), MatchArrays(), ret)
    assert ret.value == SUCCESS


def test_stub_zeros_output_cursor() -> None:
    """``ret_value.output_pos`` / ``output_offset`` are zeroed at entry."""
    ret = ReturnValue(output_pos=7, output_offset=13)
    par_look_ahead_dictionary(b"", bytearray(b""), MatchArrays(), ret)
    assert ret.output_pos == 0
    assert ret.output_offset == 0


def test_stub_does_not_mutate_input_array() -> None:
    """The stub leaves the caller's input buffer untouched."""
    inp = bytearray(b"hello world")
    snapshot = bytes(inp)
    par_look_ahead_dictionary(b"\x1d", inp, MatchArrays(), ReturnValue())
    assert bytes(inp) == snapshot


def test_stub_ignores_match_array_state() -> None:
    """Match-array buffers aren't touched by the stub."""
    ma = MatchArrays()
    ma.array_lengths[3] = 5
    ma.array[3][:5] = b"JOHN!"
    par_look_ahead_dictionary(b"", bytearray(b""), ma, ReturnValue())
    assert ma.array_lengths[3] == 5
    assert bytes(ma.array[3][:5]) == b"JOHN!"
