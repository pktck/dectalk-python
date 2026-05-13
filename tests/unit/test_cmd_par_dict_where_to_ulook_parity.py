"""C-source parity test for ``par_dict_where_to_ulook`` against par_dict.c.

Re-parses the function body from
``src/dapi/src/cmd/par_dict.c`` and asserts:

- The function signature matches the C declaration.
- The body matches the canonical pivot-char loop using
  ``par_upper[ent[i]]`` / ``par_upper[word[i]]``.
- The return path is ``LOOK_HIGHER`` if the upper-folded word
  byte exceeds the pivot, otherwise ``LOOK_LOWER``.

Then exercises the Python port against a handful of crafted
inputs covering exact match, prefix relations, and case
folding.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.par_dict_where_to_ulook import (
    LOOK_HIGHER,
    LOOK_LOWER,
    par_dict_where_to_ulook,
)

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/par_dict.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_par_dict_c() -> str:
    """Read par_dict.c with CRLF endings normalised."""
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_where_to_ulook_body() -> str:
    """Return the body of par_dict_where_to_ulook from the C source."""
    text = _read_par_dict_c()
    match = re.search(
        r"int\s+par_dict_where_to_ulook\s*\([^)]*\)\s*\n\{(.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "par_dict_where_to_ulook body not found in par_dict.c"
    return match.group(1)


# ---- Signature / body sanity checks ---------------------------------------


def test_signature_matches_c_source() -> None:
    """The C declaration is (char *ent, unsigned char *word)."""
    text = _read_par_dict_c()
    match = re.search(
        r"int\s+par_dict_where_to_ulook\s*\(\s*char\s*\*\s*ent\s*,\s*"
        r"unsigned\s+char\s*\*\s*word\s*\)",
        text,
    )
    assert match is not None, "par_dict_where_to_ulook signature did not match"


def test_loop_walks_word_until_nul() -> None:
    """The pivot loop terminates on ``word[i] == 0``."""
    body = _extract_where_to_ulook_body()
    assert re.search(r"for\s*\(\s*i\s*=\s*0\s*;\s*word\s*\[\s*i\s*\]\s*;\s*i\+\+", body)


def test_pivot_is_par_upper_of_ent() -> None:
    """``pivot_char = par_upper[(int)ent[i]];`` per iteration."""
    body = _extract_where_to_ulook_body()
    assert re.search(
        r"pivot_char\s*=\s*par_upper\s*\[\s*\(?\s*(int)?\s*\)?\s*ent\s*\[\s*i\s*\]\s*\]",
        body,
    )


def test_break_when_folded_chars_diverge() -> None:
    """``if (par_upper[word[i]] != pivot_char) break;``."""
    body = _extract_where_to_ulook_body()
    assert re.search(
        r"if\s*\(\s*par_upper\s*\[\s*word\s*\[\s*i\s*\]\s*\]\s*!=\s*pivot_char\s*\)\s*"
        r"\{?\s*break",
        body,
    )


def test_returns_look_higher_when_word_byte_exceeds_pivot() -> None:
    """``if (par_upper[word[i]] > pivot_char) return LOOK_HIGHER;``."""
    body = _extract_where_to_ulook_body()
    assert re.search(
        r"if\s*\(\s*par_upper\s*\[\s*word\s*\[\s*i\s*\]\s*\]\s*>\s*pivot_char\s*\)\s*"
        r"\{?\s*return\s*\(?\s*LOOK_HIGHER",
        body,
    )


def test_default_returns_look_lower() -> None:
    """The fall-through return is LOOK_LOWER (incl. exact match)."""
    body = _extract_where_to_ulook_body()
    assert re.search(r"return\s*\(?\s*LOOK_LOWER\s*\)?\s*;\s*$", body)


# ---- Algorithmic parity ---------------------------------------------------


def test_exact_match_returns_lower() -> None:
    """Equal strings -> LOOK_LOWER (no exact-match short-circuit here)."""
    assert par_dict_where_to_ulook(b"hello", b"hello") == LOOK_LOWER


def test_case_insensitive_equality_returns_lower() -> None:
    """Case-folded equality still returns LOOK_LOWER."""
    assert par_dict_where_to_ulook(b"HELLO", b"hello") == LOOK_LOWER
    assert par_dict_where_to_ulook(b"hello", b"HELLO") == LOOK_LOWER


def test_word_greater_than_entry_returns_higher() -> None:
    """``word`` sorts strictly greater (case-insensitive) -> LOOK_HIGHER."""
    assert par_dict_where_to_ulook(b"apple", b"banana") == LOOK_HIGHER


def test_word_less_than_entry_returns_lower() -> None:
    """``word`` sorts strictly less -> LOOK_LOWER."""
    assert par_dict_where_to_ulook(b"banana", b"apple") == LOOK_LOWER


def test_word_prefix_of_entry_returns_lower() -> None:
    """Word ends before entry; word_byte (0) < pivot_char -> LOOK_LOWER."""
    assert par_dict_where_to_ulook(b"hello", b"hel") == LOOK_LOWER


def test_entry_prefix_of_word_returns_higher() -> None:
    """Entry ends first; folded word_byte > 0 -> LOOK_HIGHER."""
    assert par_dict_where_to_ulook(b"hel", b"hello") == LOOK_HIGHER


@pytest.mark.parametrize(
    ("ent", "word", "expected"),
    [
        (b"apple", b"banana", "HIGHER"),
        (b"banana", b"apple", "LOWER"),
        (b"cat", b"cat", "LOWER"),  # exact match (NO short-circuit)
        (b"cat", b"car", "LOWER"),
        (b"car", b"cat", "HIGHER"),
        (b"zebra", b"aardvark", "LOWER"),
    ],
)
def test_alphabetical_ordering(ent: bytes, word: bytes, expected: str) -> None:
    """Function implements case-insensitive lex order; equality returns LOWER."""
    result = par_dict_where_to_ulook(ent, word)
    if expected == "HIGHER":
        assert result == LOOK_HIGHER
    else:
        assert result == LOOK_LOWER


def test_constants_match_c_source() -> None:
    """LOOK_HIGHER / LOOK_LOWER constants match par_dict.c #defines."""
    text = _read_par_dict_c()
    higher_match = re.search(r"#define\s+LOOK_HIGHER\s+(0x[0-9a-fA-F]+)", text)
    lower_match = re.search(r"#define\s+LOOK_LOWER\s+(0x[0-9a-fA-F]+)", text)
    assert higher_match is not None
    assert lower_match is not None
    assert int(higher_match.group(1), 16) == LOOK_HIGHER
    assert int(lower_match.group(1), 16) == LOOK_LOWER
