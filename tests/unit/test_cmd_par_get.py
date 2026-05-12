"""Verify ``par_get_char_type`` / ``par_get_state`` / ``par_convert_to_new``.

Re-parses the C source in ``src/dapi/src/cmd/par_def.h`` to confirm
every constant we ship matches the original ``#define``, then
exercises the dispatch functions against the constant set.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd import par_get as pg
from dectalk.cmd import rule_states as rs


def _src_path() -> Path | None:
    """Locate ``par_def.h`` in the local C source clone, if present."""
    root_env = os.environ.get("DECTALK_SRC")
    candidates = [
        Path(root_env) if root_env else None,
        Path("/tmp/dectalk-src/src"),
    ]
    for root in candidates:
        if root is None:
            continue
        for sub in ("dapi/src/cmd", "cmd"):
            p = root / sub / "par_def.h"
            if p.exists():
                return p
    return None


def _read_par_def() -> str:
    """Read ``par_def.h`` and return text with CRLF normalised."""
    path = _src_path()
    if path is None:
        pytest.skip("par_def.h not available on this host")
    return path.read_bytes().decode("latin-1").replace("\r\n", "\n")


def _extract_define(src: str, name: str) -> str:
    """Return the raw ``#define`` body for ``name`` (without the name itself)."""
    m = re.search(rf"^#define\s+{re.escape(name)}\s+(.+?)$", src, re.MULTILINE)
    if not m:
        msg = f"#define {name} not found in par_def.h"
        raise ValueError(msg)
    return m.group(1).split("/*")[0].strip().rstrip(",")


_C_ESCAPES = {
    "n": ord("\n"),
    "r": ord("\r"),
    "t": ord("\t"),
    "'": ord("'"),
    "\\": ord("\\"),
}


def _parse_char_literal(raw: str) -> int:
    """Parse a C character literal like ``'A'`` or ``'\\''``."""
    body = raw.strip()
    if body.startswith("'") and body.endswith("'"):
        inner = body[1:-1]
        if inner.startswith("\\"):
            return _C_ESCAPES[inner[1]]
        return ord(inner)
    return int(body, 0)


# ---- DELIM constants match C source ----


@pytest.mark.parametrize(
    ("name", "constant"),
    [
        ("DIGIT_CHAR_DELIM", rs.DIGIT_CHAR_DELIM),
        ("UPPER_CHAR_DELIM", rs.UPPER_CHAR_DELIM),
        ("ANY_ALPHA_CHAR_DELIM", rs.ANY_ALPHA_CHAR_DELIM),
        ("ANY_CHAR_CHAR_DELIM", rs.ANY_CHAR_CHAR_DELIM),
        ("WHITE_CHAR_DELIM", rs.WHITE_CHAR_DELIM),
        ("PUNCT_CHAR_DELIM", rs.PUNCT_CHAR_DELIM),
        ("LOWER_CHAR_DELIM", rs.LOWER_CHAR_DELIM),
        ("NON_ALPHA_CHAR_DELIM", rs.NON_ALPHA_CHAR_DELIM),
        ("SET_CHAR_DELIM", rs.SET_CHAR_DELIM),
        ("VOWEL_CHAR_DELIM", rs.VOWEL_CHAR_DELIM),
        ("CONSONANT_CHAR_DELIM", rs.CONSONANT_CHAR_DELIM),
        ("NUMBER_CHAR_DELIM", rs.NUMBER_CHAR_DELIM),
        ("CLAUSE_CHAR_DELIM", rs.CLAUSE_CHAR_DELIM),
        ("ALPHA_NUM_DELIM", rs.ALPHA_NUM_DELIM),
        ("VOWEL_NON_Y_DELIM", rs.VOWEL_NON_Y_DELIM),
        ("SOME_PUNCT_DELIM", rs.SOME_PUNCT_DELIM),
        ("EXACT_CHAR_DELIM", rs.EXACT_CHAR_DELIM),
        ("EXACT_CASE_DELIM", rs.EXACT_CASE_DELIM),
        ("HEXADECIMAL_DELIM", rs.HEXADECIMAL_DELIM),
        ("NO_LOOKAHEAD", rs.NO_LOOKAHEAD),
        ("COPY_DELIMITER", rs.COPY_DELIMITER),
        ("REPLACE_DELIMITER", rs.REPLACE_DELIMITER),
        ("DELETE_DELIMITER", rs.DELETE_DELIMITER),
        ("INSERT_DELIMITER", rs.INSERT_DELIMITER),
        ("INSERT_AFTER_DELIM", rs.INSERT_AFTER_DELIM),
        ("INSERT_BEFORE_DELIM", rs.INSERT_BEFORE_DELIM),
        ("OPTIONAL_DELIMITER", rs.OPTIONAL_DELIMITER),
        ("MACRO_DELIMITER", rs.MACRO_DELIMITER),
        ("DICTIONARY_STATE_DELIM", rs.DICTIONARY_STATE_DELIM),
        ("WORD_STATE_DELIM", rs.WORD_STATE_DELIM),
        ("STATUS_STATE_DELIM", rs.STATUS_STATE_DELIM),
        ("START_SAVE_STATE", rs.START_SAVE_STATE),
        ("SAVE_DELIMITER", rs.SAVE_DELIMITER),
    ],
)
def test_delimiter_matches_c_source(name: str, constant: int) -> None:
    """Each delimiter byte equals its #define from par_def.h."""
    src = _read_par_def()
    expected = _parse_char_literal(_extract_define(src, name))
    assert expected == constant, f"{name}: expected {expected}, got {constant}"


# ---- TYPE numeric constants match C source ----


@pytest.mark.parametrize(
    ("name", "constant"),
    [
        ("NULL_TYPE", rs.NULL_TYPE),
        ("SET_CHAR_TYPE", rs.SET_CHAR_TYPE),
        ("EXACT_CHAR_TYPE", rs.EXACT_CHAR_TYPE),
        ("EXACT_CASE_TYPE", rs.EXACT_CASE_TYPE),
        ("HEXADECIMAL_TYPE", rs.HEXADECIMAL_TYPE),
        ("SAVE_CHAR_TYPE", rs.SAVE_CHAR_TYPE),
    ],
)
def test_non_bit_type_constants_match(name: str, constant: int) -> None:
    """The non-bit-encoded TYPE_* constants are literal integers."""
    src = _read_par_def()
    raw = _extract_define(src, name)
    assert int(raw) == constant, f"{name}: expected {raw}, got {constant}"


# ---- TYPE2 zero-based indices match C source ----


@pytest.mark.parametrize(
    ("name", "constant"),
    [
        ("DIGIT_CHAR_TYPE2", rs.DIGIT_CHAR_TYPE2),
        ("UPPER_CHAR_TYPE2", rs.UPPER_CHAR_TYPE2),
        ("LOWER_CHAR_TYPE2", rs.LOWER_CHAR_TYPE2),
        ("ANY_ALPHA_CHAR_TYPE2", rs.ANY_ALPHA_CHAR_TYPE2),
        ("ANY_CHAR_CHAR_TYPE2", rs.ANY_CHAR_CHAR_TYPE2),
        ("WHITE_CHAR_TYPE2", rs.WHITE_CHAR_TYPE2),
        ("PUNCT_CHAR_TYPE2", rs.PUNCT_CHAR_TYPE2),
        ("NON_ALPHA_CHAR_TYPE2", rs.NON_ALPHA_CHAR_TYPE2),
        ("VOWEL_CHAR_TYPE2", rs.VOWEL_CHAR_TYPE2),
        ("CONSONANT_CHAR_TYPE2", rs.CONSONANT_CHAR_TYPE2),
        ("NUMBER_CHAR_TYPE2", rs.NUMBER_CHAR_TYPE2),
        ("CLAUSE_CHAR_TYPE2", rs.CLAUSE_CHAR_TYPE2),
        ("ALPHA_NUM_CHAR_TYPE2", rs.ALPHA_NUM_CHAR_TYPE2),
        ("VOWEL_NON_Y_TYPE2", rs.VOWEL_NON_Y_TYPE2),
        ("SOME_PUNCT_TYPE2", rs.SOME_PUNCT_TYPE2),
        ("SET_CHAR_TYPE2", rs.SET_CHAR_TYPE2),
        ("EXACT_CHAR_TYPE2", rs.EXACT_CHAR_TYPE2),
        ("EXACT_CASE_TYPE2", rs.EXACT_CASE_TYPE2),
        ("HEXADECIMAL_TYPE2", rs.HEXADECIMAL_TYPE2),
        ("SAVE_CHAR_TYPE2", rs.SAVE_CHAR_TYPE2),
    ],
)
def test_type2_indices_match(name: str, constant: int) -> None:
    """Each TYPE2 zero-based index matches the par_def.h value."""
    src = _read_par_def()
    raw = _extract_define(src, name)
    assert int(raw) == constant, f"{name}: expected {raw}, got {constant}"


# ---- par_get_char_type ----


@pytest.mark.parametrize(
    ("delim", "expected"),
    [
        (rs.DIGIT_CHAR_DELIM, rs.DIGIT_CHAR_TYPE),
        (rs.UPPER_CHAR_DELIM, rs.UPPER_CHAR_TYPE),
        (rs.ANY_ALPHA_CHAR_DELIM, rs.ANY_ALPHA_CHAR_TYPE),
        (rs.ANY_CHAR_CHAR_DELIM, rs.ANY_CHAR_CHAR_TYPE),
        (rs.WHITE_CHAR_DELIM, rs.WHITE_CHAR_TYPE),
        (rs.PUNCT_CHAR_DELIM, rs.PUNCT_CHAR_TYPE),
        (rs.LOWER_CHAR_DELIM, rs.LOWER_CHAR_TYPE),
        (rs.NON_ALPHA_CHAR_DELIM, rs.NON_ALPHA_CHAR_TYPE),
        (rs.SET_CHAR_DELIM, rs.SET_CHAR_TYPE),
        (rs.VOWEL_CHAR_DELIM, rs.VOWEL_CHAR_TYPE),
        (rs.CONSONANT_CHAR_DELIM, rs.CONSONANT_CHAR_TYPE),
        (rs.NUMBER_CHAR_DELIM, rs.NUMBER_CHAR_TYPE),
        (rs.CLAUSE_CHAR_DELIM, rs.CLAUSE_CHAR_TYPE),
        (rs.ALPHA_NUM_DELIM, rs.ALPHA_NUM_CHAR_TYPE),
        (rs.VOWEL_NON_Y_DELIM, rs.VOWEL_NON_Y_TYPE),
        (rs.SOME_PUNCT_DELIM, rs.SOME_PUNCT_TYPE),
        (rs.EXACT_CHAR_DELIM, rs.EXACT_CHAR_TYPE),
        (rs.EXACT_CASE_DELIM, rs.EXACT_CASE_TYPE),
        (rs.HEXADECIMAL_DELIM, rs.HEXADECIMAL_TYPE),
        (rs.SAVE_DELIMITER, rs.SAVE_CHAR_TYPE),
        (rs.NO_LOOKAHEAD, rs.NO_LOOKAHEAD),
    ],
)
def test_get_char_type_dispatches(delim: int, expected: int) -> None:
    """Each delimiter byte maps to its TYPE_* constant."""
    assert pg.par_get_char_type(delim) == expected


@pytest.mark.parametrize("c", [0, ord("z"), ord("Q"), ord(" "), 200])
def test_get_char_type_unknown_returns_null(c: int) -> None:
    """Unrecognised bytes return NULL_TYPE."""
    assert pg.par_get_char_type(c) == rs.NULL_TYPE


# ---- par_get_state ----


@pytest.mark.parametrize(
    ("delim", "expected"),
    [
        (rs.COPY_DELIMITER, rs.COPY_STATE),
        (rs.REPLACE_DELIMITER, rs.REPLACE_STATE),
        (rs.DELETE_DELIMITER, rs.DELETE_STATE),
        (rs.INSERT_DELIMITER, rs.INSERT_STATE),
        (rs.INSERT_AFTER_DELIM, rs.INSERT_AFTER_STATE),
        (rs.INSERT_BEFORE_DELIM, rs.INSERT_BEFORE_STATE),
        (rs.OPTIONAL_DELIMITER, rs.OPTIONAL_STATE),
        (rs.START_SAVE_STATE, rs.SAVE_STATE),
        (rs.MACRO_DELIMITER, rs.MACRO_STATE),
        (rs.DICTIONARY_STATE_DELIM, rs.DICTIONARY_STATE),
        (rs.WORD_STATE_DELIM, rs.WORD_STATE),
        (rs.STATUS_STATE_DELIM, rs.STATUS_STATE),
    ],
)
def test_get_state_dispatches(delim: int, expected: int) -> None:
    """Each state delimiter maps to its STATE constant."""
    assert pg.par_get_state(delim) == expected


@pytest.mark.parametrize("c", [0, ord("Z"), ord("D"), ord(" "), 200])
def test_get_state_unknown_returns_null(c: int) -> None:
    """Unrecognised bytes return NULL_STATE."""
    assert pg.par_get_state(c) == rs.NULL_STATE


# ---- par_convert_to_new ----


@pytest.mark.parametrize(
    ("type_code", "expected_type2"),
    [
        (rs.DIGIT_CHAR_TYPE, rs.DIGIT_CHAR_TYPE2),
        (rs.UPPER_CHAR_TYPE, rs.UPPER_CHAR_TYPE2),
        (rs.LOWER_CHAR_TYPE, rs.LOWER_CHAR_TYPE2),
        (rs.ANY_ALPHA_CHAR_TYPE, rs.ANY_ALPHA_CHAR_TYPE2),
        (rs.ANY_CHAR_CHAR_TYPE, rs.ANY_CHAR_CHAR_TYPE2),
        (rs.WHITE_CHAR_TYPE, rs.WHITE_CHAR_TYPE2),
        (rs.PUNCT_CHAR_TYPE, rs.PUNCT_CHAR_TYPE2),
        (rs.NON_ALPHA_CHAR_TYPE, rs.NON_ALPHA_CHAR_TYPE2),
        (rs.VOWEL_CHAR_TYPE, rs.VOWEL_CHAR_TYPE2),
        (rs.CONSONANT_CHAR_TYPE, rs.CONSONANT_CHAR_TYPE2),
        (rs.NUMBER_CHAR_TYPE, rs.NUMBER_CHAR_TYPE2),
        (rs.CLAUSE_CHAR_TYPE, rs.CLAUSE_CHAR_TYPE2),
        (rs.ALPHA_NUM_CHAR_TYPE, rs.ALPHA_NUM_CHAR_TYPE2),
        (rs.VOWEL_NON_Y_TYPE, rs.VOWEL_NON_Y_TYPE2),
        (rs.SOME_PUNCT_TYPE, rs.SOME_PUNCT_TYPE2),
        (rs.SET_CHAR_TYPE, rs.SET_CHAR_TYPE2),
        (rs.EXACT_CHAR_TYPE, rs.EXACT_CHAR_TYPE2),
        (rs.EXACT_CASE_TYPE, rs.EXACT_CASE_TYPE2),
        (rs.HEXADECIMAL_TYPE, rs.HEXADECIMAL_TYPE2),
        (rs.SAVE_CHAR_TYPE, rs.SAVE_CHAR_TYPE2),
    ],
)
def test_convert_to_new_dispatches(type_code: int, expected_type2: int) -> None:
    """Each TYPE_* maps to its zero-based TYPE2 index."""
    assert pg.par_convert_to_new(type_code) == expected_type2


@pytest.mark.parametrize("bad", [0, -1, 9912, 9999])
def test_convert_to_new_unknown_returns_negative_one(bad: int) -> None:
    """Unrecognised inputs return -1 (matches C default branch)."""
    assert pg.par_convert_to_new(bad) == -1
