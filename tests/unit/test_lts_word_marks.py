"""Verify the LTS word-level MARK_* and FC_* constants match ls_dict.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.lts import word_marks

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/lts/ls_dict.h")
_DEFINE_RE: re.Pattern[str] = re.compile(
    r"^#define\s+(MARK_[a-z_]+|FC_[A-Z]+)\s+(0[xX][0-9A-Fa-f]+)L?\b",
)


def _parse_c_defines() -> dict[str, int]:
    """Extract the MARK_* and FC_* constants from ls_dict.h."""
    out: dict[str, int] = {}
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    for line in text.splitlines():
        match = _DEFINE_RE.match(line)
        if match:
            out.setdefault(match.group(1), int(match.group(2), 16))
    return out


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_word_marks_match_c_source() -> None:
    """Each word-level MARK_* / FC_* constant matches the C header."""
    expected = _parse_c_defines()
    # Sanity: at least 16 MARK_* + 2 FC_* defines parsed.
    mark_count = sum(1 for name in expected if name.startswith("MARK_"))
    fc_count = sum(1 for name in expected if name.startswith("FC_"))
    assert mark_count == 17, "expected 17 MARK_* values in ls_dict.h"
    assert fc_count == 5, "expected 5 FC_* values in ls_dict.h"
    for name, value in expected.items():
        if not hasattr(word_marks, name):
            continue  # composite FC_ALWAYS et al. omitted (defined elsewhere)
        assert getattr(word_marks, name) == value, f"{name} should be 0x{value:08X} per ls_dict.h"


def test_mark_null_is_zero() -> None:
    """``MARK_null`` is the no-feature placeholder, value 0."""
    assert word_marks.MARK_null == 0


def test_mark_bits_form_powers_of_two() -> None:
    """Each non-null MARK_* is a distinct single-bit flag (powers of two)."""
    flags = [
        word_marks.MARK_start,
        word_marks.MARK_end,
        word_marks.MARK_comma,
        word_marks.MARK_first_upper,
        word_marks.MARK_vowel,
        word_marks.MARK_upper,
        word_marks.MARK_cons,
        word_marks.MARK_digit,
        word_marks.MARK_hyphen,
        word_marks.MARK_ques_excl,
        word_marks.MARK_non_alpha,
        word_marks.MARK_slash,
        word_marks.MARK_numeric,
        word_marks.MARK_period,
        word_marks.MARK_dquote,
        word_marks.MARK_squote,
    ]
    for f in flags:
        assert f > 0
        assert (f & (f - 1)) == 0, f"{f:#x} is not a single-bit flag"
    # Distinct bits.
    assert len(set(flags)) == len(flags)


def test_fc_consider_and_keep_partition_word() -> None:
    """``FC_CONSIDER`` (low 24) and ``FC_KEEP`` (high 8) partition 32 bits."""
    assert word_marks.FC_CONSIDER | word_marks.FC_KEEP == word_marks.FC_TARGET
    assert word_marks.FC_CONSIDER & word_marks.FC_KEEP == 0
