"""C-source parity test for ``par_match_string`` against par_pars1.c.

Re-parses the C function body and asserts the per-opcode dispatch
(BIN_DIGIT / BIN_EXACT / BIN_HEXADECIMAL / BIN_RESTORE / BIN_SETS)
matches the Python port.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.par_bin_codes import (
    BIN_CASE_INSEN,
    BIN_DIGIT,
    BIN_DIGIT_RANGE,
    BIN_EXACT,
    BIN_HEXADECIMAL,
    BIN_LOWER,
    BIN_RESTORE,
    BIN_SMALL_ANY_NUMBER,
)
from dectalk.cmd.par_match_string import par_match_string
from dectalk.cmd.par_structs import MatchArrays, RangeValue, ReturnValue
from dectalk.cmd.rule_states import FAIL, OPT_FAIL, SUCCESS

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
            r"^int\s+par_match_string\s*\(\s*register\s+unsigned\s+char\s*\*\s*current_rule"
            r"[^;{]+?\)\s*\n\{",
            text,
            re.MULTILINE,
        )
    )
    assert matches, "par_match_string definition not found"
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


def test_dispatches_on_bin_digit() -> None:
    """The body has a ``char_type <= BIN_DIGIT`` branch."""
    body = _extract_body()
    assert re.search(r"char_type\s*<=\s*BIN_DIGIT", body) is not None


def test_dispatches_on_bin_exact() -> None:
    """The body has a ``char_type == BIN_EXACT`` branch."""
    body = _extract_body()
    assert re.search(r"char_type\s*==\s*BIN_EXACT", body) is not None


def test_dispatches_on_bin_hexadecimal() -> None:
    """The body has a ``char_type <= BIN_HEXADECIMAL`` branch."""
    body = _extract_body()
    assert re.search(r"char_type\s*<=\s*BIN_HEXADECIMAL", body) is not None


def test_dispatches_on_bin_restore() -> None:
    """The body has a ``char_type == BIN_RESTORE`` branch."""
    body = _extract_body()
    assert re.search(r"char_type\s*==\s*BIN_RESTORE", body) is not None


def test_calls_par_match_digits() -> None:
    """The body calls ``par_match_digits`` for digit-range types."""
    body = _extract_body()
    assert "par_match_digits(" in body


def test_calls_par_match_standard() -> None:
    """The body calls ``par_match_standard`` for non-digit char types."""
    body = _extract_body()
    assert "par_match_standard(" in body


def test_calls_par_match_sets_with_ranges() -> None:
    """The body calls ``par_match_sets_with_ranges`` for BIN_SETS."""
    body = _extract_body()
    assert "par_match_sets_with_ranges(" in body


def test_uses_par_lower_for_case_insen() -> None:
    """The case-insensitive BIN_EXACT branch folds via ``par_lower``."""
    body = _extract_body()
    assert "par_lower[" in body


def test_python_exact_match_succeeds() -> None:
    """BIN_EXACT with value=3 'cat' matches input 'cat'."""
    rule = bytes([BIN_EXACT, 3, ord("c"), ord("a"), ord("t")])
    inp = b"cat"
    ma = MatchArrays()
    rv = ReturnValue(rule=0, input_pos=0, value=SUCCESS)
    rng = RangeValue()
    length = par_match_string(rule, BIN_EXACT, inp, ma, rv, rng, 0, 0)
    assert length == 3


def test_python_exact_mismatch_sets_fail() -> None:
    """BIN_EXACT 'cat' fails on input 'dog'."""
    rule = bytes([BIN_EXACT, 3, ord("c"), ord("a"), ord("t")])
    inp = b"dog"
    ma = MatchArrays()
    rv = ReturnValue(rule=0, input_pos=0, value=SUCCESS)
    rng = RangeValue()
    length = par_match_string(rule, BIN_EXACT, inp, ma, rv, rng, 0, 0)
    assert length == 0
    assert rv.value == FAIL


def test_python_exact_optional_sets_opt_fail() -> None:
    """BIN_EXACT mismatch with ``optional=1`` reports ``OPT_FAIL``."""
    rule = bytes([BIN_EXACT, 3, ord("c"), ord("a"), ord("t")])
    inp = b"dog"
    ma = MatchArrays()
    rv = ReturnValue(rule=0, input_pos=0, value=SUCCESS, optional=1)
    rng = RangeValue()
    par_match_string(rule, BIN_EXACT, inp, ma, rv, rng, 0, 0)
    assert rv.value == OPT_FAIL


def test_python_exact_case_insensitive_match() -> None:
    """BIN_EXACT with BIN_CASE_INSEN folds case via par_lower."""
    rule = bytes([BIN_EXACT | BIN_CASE_INSEN, 3, ord("C"), ord("a"), ord("T")])
    inp = b"cAt"
    ma = MatchArrays()
    rv = ReturnValue(rule=0, input_pos=0, value=SUCCESS)
    rng = RangeValue()
    length = par_match_string(rule, BIN_EXACT, inp, ma, rv, rng, 0, 0)
    assert length == 3


def test_python_hexadecimal_match() -> None:
    """BIN_HEXADECIMAL matches a single byte."""
    rule = bytes([BIN_HEXADECIMAL, 0x41])
    inp = b"A"  # 0x41
    ma = MatchArrays()
    rv = ReturnValue(rule=0, input_pos=0, value=SUCCESS)
    rng = RangeValue()
    length = par_match_string(rule, BIN_HEXADECIMAL, inp, ma, rv, rng, 0, 0)
    assert length == 1


def test_python_hexadecimal_mismatch() -> None:
    """BIN_HEXADECIMAL fails on a byte mismatch."""
    rule = bytes([BIN_HEXADECIMAL, 0x41])
    inp = b"B"
    ma = MatchArrays()
    rv = ReturnValue(rule=0, input_pos=0, value=SUCCESS)
    rng = RangeValue()
    length = par_match_string(rule, BIN_HEXADECIMAL, inp, ma, rv, rng, 0, 0)
    assert length == 0
    assert rv.value == FAIL


def test_python_restore_matches_saved() -> None:
    """BIN_RESTORE replays bytes from ``match_array.array[N]``."""
    rule = bytes([BIN_RESTORE, 3])
    inp = b"foo"
    ma = MatchArrays()
    ma.array_lengths[3] = 3
    ma.array[3][0:3] = b"foo"
    rv = ReturnValue(rule=0, input_pos=0, value=SUCCESS)
    rng = RangeValue()
    length = par_match_string(rule, BIN_RESTORE, inp, ma, rv, rng, 0, 0)
    assert length == 3


def test_python_restore_mismatch() -> None:
    """BIN_RESTORE fails when the saved bytes don't match the input."""
    rule = bytes([BIN_RESTORE, 3])
    inp = b"bar"
    ma = MatchArrays()
    ma.array_lengths[3] = 3
    ma.array[3][0:3] = b"foo"
    rv = ReturnValue(rule=0, input_pos=0, value=SUCCESS)
    rng = RangeValue()
    length = par_match_string(rule, BIN_RESTORE, inp, ma, rv, rng, 0, 0)
    assert length == 0
    assert rv.value == FAIL


def test_python_digit_range_routes_via_match_digits() -> None:
    """BIN_DIGIT with the digit-range flag dispatches to par_match_digits."""
    # Construct an opcode with BIN_DIGIT and the BIN_DIGIT_RANGE flag set
    # (= 0x0F | 0x20 = 0x2F).  The rule is structured for par_match_digits:
    # [op, num_desc=1, descriptor=9].  Input '9' matches range [9,9].
    rule = bytes([BIN_DIGIT | BIN_DIGIT_RANGE, 1, 9])
    inp = b"9"
    ma = MatchArrays()
    rv = ReturnValue(rule=0, input_pos=0, value=SUCCESS)
    rng = RangeValue()
    length = par_match_string(rule, BIN_DIGIT, inp, ma, rv, rng, 0, 0)
    assert length == 1


def test_python_lower_routes_via_match_standard() -> None:
    """BIN_LOWER (no digit-range flag) dispatches to par_match_standard."""
    rule = bytes([BIN_LOWER, 1, BIN_SMALL_ANY_NUMBER])
    inp = b"hello WORLD"
    ma = MatchArrays()
    rv = ReturnValue(rule=0, input_pos=0, value=SUCCESS)
    rng = RangeValue()
    length = par_match_string(rule, BIN_LOWER, inp, ma, rv, rng, 0, 0)
    assert length == 5  # "hello"


def test_python_zero_length_match_collapsed() -> None:
    """A `-2` return from one of the matchers is rewritten to 0."""
    # Empty input with BIN_LOWER and any-number descriptor (min 0) yields
    # -2 (zero-length success). par_match_string collapses that to 0.
    rule = bytes([BIN_LOWER, 1, BIN_SMALL_ANY_NUMBER])
    inp = b"X"  # Uppercase; not lower -> zero matches.
    ma = MatchArrays()
    rv = ReturnValue(rule=0, input_pos=0, value=SUCCESS)
    rng = RangeValue()
    length = par_match_string(rule, BIN_LOWER, inp, ma, rv, rng, 0, 0)
    assert length == 0
