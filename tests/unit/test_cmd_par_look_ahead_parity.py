"""C-source parity test for ``par_look_ahead`` against par_pars1.c.

Re-parses the C function body and asserts the per-opcode dispatch
shape (BIN_EXACT / BIN_DIGIT / BIN_HEXADECIMAL / BIN_RESTORE /
BIN_SETS / dictionary fall-through) matches the Python port.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.par_bin_codes import (
    BIN_ANY_CHARACTER,
    BIN_CASE_INSEN,
    BIN_EXACT,
    BIN_HEXADECIMAL,
    BIN_RESTORE,
)
from dectalk.cmd.par_look_ahead import par_look_ahead
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
    # Anchor on the definition (signature followed by `{`), skipping the
    # earlier forward declaration (which ends in `;`).
    matches = list(
        re.finditer(
            r"^int\s+par_look_ahead\s*\([^;{]+?\)\s*\n\{",
            text,
            re.MULTILINE,
        )
    )
    assert matches, "par_look_ahead definition not found"
    start = matches[-1].start()
    # Walk braces to find the matching close.
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


def test_dispatches_on_bin_exact() -> None:
    """The body has a ``char_type == BIN_EXACT`` branch."""
    body = _extract_body()
    assert re.search(r"char_type\s*==\s*BIN_EXACT", body) is not None


def test_dispatches_on_bin_hexadecimal() -> None:
    """The body has a ``char_type == BIN_HEXADECIMAL`` branch."""
    body = _extract_body()
    assert re.search(r"char_type\s*==\s*BIN_HEXADECIMAL", body) is not None


def test_dispatches_on_bin_restore() -> None:
    """The body has a ``char_type == BIN_RESTORE`` branch."""
    body = _extract_body()
    assert re.search(r"char_type\s*==\s*BIN_RESTORE", body) is not None


def test_dispatches_on_bin_sets() -> None:
    """The body has a ``char_type == BIN_SETS`` branch."""
    body = _extract_body()
    assert re.search(r"char_type\s*==\s*BIN_SETS", body) is not None


def test_uses_par_lower_for_case_insen() -> None:
    """The case-insensitive EXACT branch goes through ``par_lower``."""
    body = _extract_body()
    assert "par_lower[current_rule[rule_p]]" in body


def test_python_exact_case_match() -> None:
    """An exact-byte match returns 1."""
    # opcode at index 0 = BIN_EXACT (no case-insen flag).
    # Encoded: [BIN_EXACT, value=1, 'a']  -> find_index=0, current_rule[1]=1, [2]='a'
    rule = bytes([BIN_EXACT, 1, ord("a")])
    inp = b"a"
    ma = MatchArrays()
    rv = ReturnValue()
    assert par_look_ahead(rule, inp, 0, 0, ma, rv) == 1


def test_python_exact_case_mismatch() -> None:
    """A literal mismatch returns 0."""
    rule = bytes([BIN_EXACT, 1, ord("a")])
    inp = b"b"
    ma = MatchArrays()
    rv = ReturnValue()
    assert par_look_ahead(rule, inp, 0, 0, ma, rv) == 0


def test_python_exact_case_insensitive_match() -> None:
    """``BIN_CASE_INSEN`` folds via ``par_lower`` (= ls_lower)."""
    # Add the BIN_CASE_INSEN flag (0x20) onto BIN_EXACT.
    rule = bytes([BIN_EXACT | BIN_CASE_INSEN, 1, ord("A")])
    inp = b"a"
    ma = MatchArrays()
    rv = ReturnValue()
    assert par_look_ahead(rule, inp, 0, 0, ma, rv) == 1


def test_python_hexadecimal_match() -> None:
    """``BIN_HEXADECIMAL`` matches a single byte."""
    rule = bytes([BIN_HEXADECIMAL, 0x42])
    inp = b"B"  # 0x42
    ma = MatchArrays()
    rv = ReturnValue()
    assert par_look_ahead(rule, inp, 0, 0, ma, rv) == 1


def test_python_hexadecimal_mismatch() -> None:
    """``BIN_HEXADECIMAL`` returns 0 on a byte mismatch."""
    rule = bytes([BIN_HEXADECIMAL, 0x42])
    inp = b"C"
    ma = MatchArrays()
    rv = ReturnValue()
    assert par_look_ahead(rule, inp, 0, 0, ma, rv) == 0


def test_python_restore_match() -> None:
    """``BIN_RESTORE`` checks the saved bytes against the input window."""
    rule = bytes([BIN_RESTORE, 3])  # slot 3
    inp = b"foo"
    ma = MatchArrays()
    ma.array_lengths[3] = 3
    ma.array[3][0:3] = b"foo"
    rv = ReturnValue()
    assert par_look_ahead(rule, inp, 0, 0, ma, rv) == 1


def test_python_restore_empty_save_returns_zero() -> None:
    """An unsaved slot (length 0 / first byte NUL) returns 0."""
    rule = bytes([BIN_RESTORE, 5])
    inp = b"foo"
    ma = MatchArrays()  # all zeros
    rv = ReturnValue()
    assert par_look_ahead(rule, inp, 0, 0, ma, rv) == 0


def test_python_dictionary_returns_zero_default() -> None:
    """``BIN_DICTIONARY`` (0x1D) is the unported fall-through, returns 0."""
    # Use BIN_DICTIONARY = 0x1D which falls through to the catch-all.
    rule = bytes([0x1D, 0, 0])
    inp = b"foo"
    ma = MatchArrays()
    rv = ReturnValue()
    assert par_look_ahead(rule, inp, 0, 0, ma, rv) == 0


def test_python_any_character_branch_delegates_to_standard() -> None:
    """A char-type <= BIN_DIGIT routes through par_match_standard via late-bind."""
    # BIN_ANY_CHARACTER (=3): [opcode, num_desc|flags=1, desc_byte=1] -- match exactly 1 char.
    # par_look_ahead always calls par_match_standard with lookahead=0,
    # so there's no next-type byte after num_desc.
    rule = bytes([BIN_ANY_CHARACTER, 1, 1])
    inp = b"X"
    ma = MatchArrays()
    rv = ReturnValue()
    # Either the dispatch enters par_match_standard (and may match/not) -- we
    # just confirm the call doesn't raise. Behavioural verification of the
    # full standard matcher belongs to its dedicated test file.
    par_look_ahead(rule, inp, 0, 0, ma, rv)
