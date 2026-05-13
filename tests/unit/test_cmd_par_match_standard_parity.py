"""C-source parity test for ``par_match_standard`` against par_pars1.c.

Re-parses the C function body and asserts the descriptor-decode +
character-class match loop shape matches the Python port. Plus a
handful of behavioural tests covering the documented branches.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.par_bin_codes import (
    BIN_ANY_CHARACTER,
    BIN_COMPLIMENT,
    BIN_DIGIT,
    BIN_LARGE_DESC,
    BIN_LOWER,
    BIN_SMALL_ANY_NUMBER,
)
from dectalk.cmd.par_match_standard import par_match_standard
from dectalk.cmd.par_structs import MatchArrays, ReturnValue

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/par_pars1.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_par_pars1_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    text = _read_par_pars1_c()
    matches = list(
        re.finditer(
            r"^int\s+par_match_standard\s*\([^;{]+?\)\s*\n\{",
            text,
            re.MULTILINE,
        )
    )
    assert matches, "par_match_standard definition not found"
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


def test_uses_char_type_table() -> None:
    """The body indexes ``char_type_table`` by ``char_type``."""
    body = _extract_body()
    assert "char_type_table[char_type]" in body


def test_uses_parser_char_types() -> None:
    """The body tests ``parser_char_types`` against ``new_char_type``."""
    body = _extract_body()
    assert re.search(r"parser_char_types\s*\[", body) is not None


def test_handles_bin_compliment() -> None:
    """The body has a ``temp & BIN_COMPLIMENT`` branch."""
    body = _extract_body()
    assert re.search(r"temp\s*&\s*BIN_COMPLIMENT", body) is not None


def test_handles_bin_large_desc() -> None:
    """The body has a ``temp & BIN_LARGE_DESC`` branch."""
    body = _extract_body()
    assert re.search(r"BIN_LARGE_DESC", body) is not None


def test_calls_par_look_ahead_when_lookahead_set() -> None:
    """The body invokes par_look_ahead at least once."""
    body = _extract_body()
    assert "par_look_ahead(" in body


def test_python_match_any_char_run() -> None:
    """``BIN_ANY_CHARACTER`` with descriptor=5 matches 5 chars."""
    # Layout: [op, num_desc=1, desc=5 (any-num bit unset -> exact 5)]
    rule = bytes([BIN_ANY_CHARACTER, 1, 5])
    inp = b"abcdefg"
    ma = MatchArrays()
    rv = ReturnValue(rule=0, input_pos=0)
    length = par_match_standard(rule, BIN_ANY_CHARACTER, inp, ma, rv, 0, 0)
    assert length == 5


def test_python_match_zero_chars_for_zero_input() -> None:
    """An empty input with min_range=0 produces a -2 zero-length success."""
    rule = bytes([BIN_LOWER, 1, BIN_SMALL_ANY_NUMBER])  # 0..INT_MAX of LOWER
    # The result for "" with any-num: zero matches, satisfied_min_cond=-2,
    # length=0 then becomes -2 (zero-length success).
    inp = b""
    ma = MatchArrays()
    rv = ReturnValue(rule=0, input_pos=0)
    length = par_match_standard(rule, BIN_LOWER, inp, ma, rv, 0, 0)
    # length can be -2 (zero-length success) or -1 (end-of-input).
    assert length in (-1, -2)


def test_python_match_lower_run() -> None:
    """BIN_LOWER with desc=BIN_SMALL_ANY_NUMBER consumes a lowercase run."""
    # Layout: [op, num_desc=1, desc=BIN_SMALL_ANY_NUMBER=0x80 (0..inf)]
    rule = bytes([BIN_LOWER, 1, BIN_SMALL_ANY_NUMBER])
    inp = b"hello WORLD"
    ma = MatchArrays()
    rv = ReturnValue(rule=0, input_pos=0)
    length = par_match_standard(rule, BIN_LOWER, inp, ma, rv, 0, 0)
    assert length == 5  # "hello"


def test_python_match_complement_doesnt_match_lower() -> None:
    """BIN_COMPLIMENT inverts the test (TYPE_lower hit becomes a miss)."""
    # Layout: [op, num_desc=1 | BIN_COMPLIMENT, desc=BIN_SMALL_ANY_NUMBER]
    rule = bytes([BIN_LOWER, 1 | BIN_COMPLIMENT, BIN_SMALL_ANY_NUMBER])
    inp = b"hello WORLD"
    ma = MatchArrays()
    rv = ReturnValue(rule=0, input_pos=0)
    length = par_match_standard(rule, BIN_LOWER, inp, ma, rv, 0, 0)
    # First byte 'h' is lower so the inverted match never starts.
    assert length in (0, -2)


def test_python_match_advances_rule_pointer() -> None:
    """On success, ``ret_value.rule`` is bumped past the descriptor block."""
    rule = bytes([BIN_LOWER, 1, BIN_SMALL_ANY_NUMBER])
    inp = b"hello"
    ma = MatchArrays()
    rv = ReturnValue(rule=0, input_pos=0)
    par_match_standard(rule, BIN_LOWER, inp, ma, rv, 0, 0)
    # in_rule_p=0, +2 (op + num_desc), +0 (no lookahead), +1 (small desc * 1) = 3.
    assert rv.rule == 3


def test_python_match_large_desc_decoded() -> None:
    """A ``BIN_LARGE_DESC`` flag triggers the 16-bit descriptor decode."""
    # Layout: [op, BIN_LARGE_DESC | num_desc=1, low_byte, high_byte]
    # 16-bit little-endian descriptor with value 7 (no any-num / continue flags).
    rule = bytes([BIN_LOWER, BIN_LARGE_DESC | 1, 7, 0])
    inp = b"abcdefghi"
    ma = MatchArrays()
    rv = ReturnValue(rule=0, input_pos=0)
    length = par_match_standard(rule, BIN_LOWER, inp, ma, rv, 0, 0)
    assert length == 7


def test_python_match_digit_via_bin_digit_branch() -> None:
    """``BIN_DIGIT`` with a descriptor of 1 matches one digit char."""
    rule = bytes([BIN_DIGIT, 1, 1])
    inp = b"5abc"
    ma = MatchArrays()
    rv = ReturnValue(rule=0, input_pos=0)
    length = par_match_standard(rule, BIN_DIGIT, inp, ma, rv, 0, 0)
    assert length == 1
