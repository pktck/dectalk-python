"""Verify the LTS character-feature tables match the C source byte-for-byte.

Re-parses ``src/dapi/src/include/{ls_fold,ls_lower,ls_upper,ls_feat}.tab``
at test time and asserts each Python ``bytes`` in
:mod:`dectalk.lts.char_features` equals the C-source-derived bytes
exactly. Also exercises the IS_* helper functions on a fixed set of
inputs.

Skips when ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.lts import char_features as cf

_INCLUDE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/include"

_CFEAT_NAMES = {
    "CFEAT_null": cf.CFEAT_null,
    "CFEAT_lower": cf.CFEAT_lower,
    "CFEAT_upper": cf.CFEAT_upper,
    "CFEAT_punct": cf.CFEAT_punct,
    "CFEAT_non_alpha": cf.CFEAT_non_alpha,
    "CFEAT_digit": cf.CFEAT_digit,
    "CFEAT_cons": cf.CFEAT_cons,
    "CFEAT_vowel": cf.CFEAT_vowel,
}

_C_ESCAPES = {"\\'": 0x27, "\\\\": 0x5C, "\\0": 0, "\\n": 10, "\\t": 9, "\\r": 13, '\\"': 0x22}

pytestmark = pytest.mark.skipif(
    not _INCLUDE.is_dir(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _eval_expr(expr: str) -> int:
    """Evaluate a single ``.tab`` cell expression.

    Handles: ``0xff``, decimal, ``'X'`` char literal, ``(unsigned char)'X'``
    cast, and bitwise-OR / additive combinations of ``CFEAT_*`` symbols.
    """
    expr = expr.strip()
    expr = re.sub(r"\(\s*unsigned\s+char\s*\)\s*", "", expr).strip()
    if expr.startswith("'") and expr.endswith("'"):
        inner = expr[1:-1]
        return _C_ESCAPES.get(inner, ord(inner[-1])) if inner.startswith("\\") else ord(inner)
    if re.fullmatch(r"0[xX][0-9a-fA-F]+", expr):
        return int(expr, 16)
    if re.fullmatch(r"\d+", expr):
        return int(expr)
    val = 0
    for raw_tok in re.split(r"\s*[|+]\s*", expr):
        tok = raw_tok.strip()
        if tok not in _CFEAT_NAMES:
            raise ValueError(f"unrecognised token in .tab expression: {tok!r}")
        val |= _CFEAT_NAMES[tok]
    return val


def _parse_tab(name: str) -> bytes:
    """Read ``include/<name>.tab`` and return the raw byte array."""
    text = (_INCLUDE / f"{name}.tab").read_text(encoding="latin-1")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//.*", "", text)
    return bytes(_eval_expr(x) for x in (cell.strip() for cell in text.split(",")) if x)


# ----- Table parity -------------------------------------------------------


@pytest.mark.parametrize(
    ("py_table", "c_name", "expected_size"),
    [
        (cf.ls_fold, "ls_fold", 256),
        (cf.ls_lower, "ls_lower", 256),
        (cf.ls_upper, "ls_upper", 256),
        # ls_feat.tab has 2 trailing CFEAT_null entries beyond index 255.
        (cf.ls_char_feat, "ls_feat", 258),
    ],
)
def test_table_matches_c_source(py_table: bytes, c_name: str, expected_size: int) -> None:
    """Python bytes literal byte-for-byte equals the C ``.tab`` content."""
    c_bytes = _parse_tab(c_name)
    assert len(c_bytes) == expected_size, (
        f"C {c_name}.tab parsed to {len(c_bytes)} bytes; expected {expected_size}"
    )
    assert len(py_table) == expected_size
    assert py_table == c_bytes


# ----- IS_* helper functions ----------------------------------------------


@pytest.mark.parametrize(
    ("char", "expected"),
    [
        ("a", True),
        ("z", True),
        ("A", False),
        ("0", False),
        (" ", False),
        (".", False),
    ],
)
def test_is_lower(char: str, expected: bool) -> None:
    assert cf.is_lower(ord(char)) is expected


@pytest.mark.parametrize(
    ("char", "expected"),
    [
        ("A", True),
        ("Z", True),
        ("a", False),
        ("0", False),
        (" ", False),
        (".", False),
    ],
)
def test_is_upper(char: str, expected: bool) -> None:
    assert cf.is_upper(ord(char)) is expected


@pytest.mark.parametrize(
    ("char", "expected"),
    [
        ("a", True),
        ("Z", True),
        ("0", False),
        (" ", False),
        (".", False),
    ],
)
def test_is_alpha(char: str, expected: bool) -> None:
    assert cf.is_alpha(ord(char)) is expected


@pytest.mark.parametrize(
    ("char", "expected"),
    [
        ("0", True),
        ("5", True),
        ("9", True),
        ("a", False),
        (" ", False),
    ],
)
def test_is_digit(char: str, expected: bool) -> None:
    assert cf.is_digit(ord(char)) is expected


@pytest.mark.parametrize(
    ("char", "expected"),
    [
        (".", True),
        (",", True),
        ("?", True),
        ("!", True),
        ("a", False),
        ("0", False),
    ],
)
def test_is_punct(char: str, expected: bool) -> None:
    assert cf.is_punct(ord(char)) is expected


@pytest.mark.parametrize("char", "aeiouAEIOU")
def test_is_vowel_ascii(char: str) -> None:
    """All English vowels (both cases) are flagged as vowels."""
    assert cf.is_vowel(ord(char)) is True


@pytest.mark.parametrize("char", "bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ")
def test_is_cons_ascii(char: str) -> None:
    """All English consonants (both cases) are flagged as consonants."""
    assert cf.is_cons(ord(char)) is True


# ----- Folding tables -----------------------------------------------------


@pytest.mark.parametrize(
    ("inp", "expected"),
    [
        ("A", "a"),
        ("Z", "z"),
        ("M", "m"),
        ("a", "a"),
        ("z", "z"),
        ("0", "0"),
        (".", "."),
    ],
)
def test_ls_lower_ascii(inp: str, expected: str) -> None:
    assert cf.ls_lower[ord(inp)] == ord(expected)


@pytest.mark.parametrize(
    ("inp", "expected"),
    [
        ("a", "A"),
        ("z", "Z"),
        ("m", "M"),
        ("A", "A"),
        ("Z", "Z"),
        ("0", "0"),
        (".", "."),
    ],
)
def test_ls_upper_ascii(inp: str, expected: str) -> None:
    assert cf.ls_upper[ord(inp)] == ord(expected)


def test_ls_fold_strips_diacritics() -> None:
    """``ls_fold`` reduces accented latin-1 letters to ASCII equivalents.

    These mappings are baked into the C source (see ``ls_fold.tab``)
    and used by the lexicon for accent-insensitive lookups.
    """
    # À (0xC0) and à (0xE0) both fold to 'a'.
    assert cf.ls_fold[0xC0] == ord("a")
    assert cf.ls_fold[0xE0] == ord("a")
    # É (0xC9) folds to 'e'.
    assert cf.ls_fold[0xC9] == ord("e")
    # Ñ (0xD1) folds to 'n'.
    assert cf.ls_fold[0xD1] == ord("n")


def test_cfeat_constants_match_c_header() -> None:
    """The ``CFEAT_*`` numeric values are the bit positions used in the table."""
    assert cf.CFEAT_null == 0x00
    assert cf.CFEAT_lower == 0x01
    assert cf.CFEAT_upper == 0x02
    assert cf.CFEAT_punct == 0x04
    assert cf.CFEAT_non_alpha == 0x08
    assert cf.CFEAT_digit == 0x10
    assert cf.CFEAT_cons == 0x20
    assert cf.CFEAT_vowel == 0x40
