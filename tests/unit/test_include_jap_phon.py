"""Verify Japanese phoneme codes match jap_phon.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.include import jap_phon as jp

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/include/jap_phon.h")


def _parse_define(name: str) -> int | None:
    """Return the int value of a ``#define <name> <int>``."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"^#define\s+{re.escape(name)}\s+(\d+)\b"
    for line in text.splitlines():
        match = re.match(pattern, line)
        if match:
            return int(match.group(1))
    return None


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_jap_allophones_dense() -> None:
    """The 41 ``JapPhoneme`` codes form a dense 0..40 set."""
    codes = {int(p) for p in jp.JapPhoneme}
    assert codes == set(range(41))


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
@pytest.mark.parametrize(
    ("py_name", "c_name", "expected"),
    [
        ("SIL", "SIL", 0),
        ("I", "I", 1),
        ("A", "A", 3),
        ("U", "U", 5),
        ("SH", "SH", 27),
        ("R", "R", 30),
        ("JH", "JH", 40),
    ],
)
def test_jap_allophone_value(py_name: str, c_name: str, expected: int) -> None:
    """Selected Japanese allophone codes match the C source."""
    c_value = _parse_define(c_name)
    assert c_value is not None
    assert c_value == expected
    assert int(getattr(jp.JapPhoneme, py_name)) == expected


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
@pytest.mark.parametrize(
    ("py_attr", "c_name", "expected"),
    [
        ("JAP_TOT_ALLOPHONES", "TOT_ALLOPHONES", 41),
        ("JAP_BLOCK_RULES", "BLOCK_RULES", 41),
        ("JAP_ACCENT_RISE", "ACCENT_RISE", 42),
        ("JAP_STRONG_RISE", "STRONG_RISE", 43),
        ("JAP_ACCENT_FALL", "ACCENT_FALL", 44),
        ("JAP_STRONG_FALL", "STRONG_FALL", 45),
        ("JAP_LONG_PHONE", "LONG_PHONE", 46),
        ("JAP_NEW_PARAGRAPH", "NEW_PARAGRAPH", 47),
        ("JAP_ABOUND", "ABOUND", 48),
        ("JAP_WBOUND", "WBOUND", 49),
        ("JAP_PBOUND", "PBOUND", 50),
        ("JAP_CBOUND", "CBOUND", 51),
        ("JAP_SBOUND", "SBOUND", 52),
        ("JAP_QBOUND", "QBOUND", 53),
        ("JAP_PHO_SYM_TOT", "PHO_SYM_TOT", 54),
    ],
)
def test_jap_control_code_matches_c(py_attr: str, c_name: str, expected: int) -> None:
    """Japanese control codes (41..54) match jap_phon.h."""
    c_value = _parse_define(c_name)
    assert c_value is not None
    assert c_value == expected
    assert getattr(jp, py_attr) == expected


def test_boundary_ladder() -> None:
    """Affix < Word < Phrase < Clause < Sentence."""
    assert (
        jp.JAP_ABOUND
        < jp.JAP_WBOUND
        < jp.JAP_PBOUND
        < jp.JAP_CBOUND
        < jp.JAP_SBOUND
        < jp.JAP_QBOUND
    )


def test_jap_pho_sym_tot_covers_all_codes() -> None:
    """``JAP_PHO_SYM_TOT`` is one past the highest code."""
    assert jp.JAP_PHO_SYM_TOT == jp.JAP_QBOUND + 1


def test_block_rules_collides_with_tot_allophones() -> None:
    """``BLOCK_RULES`` and ``TOT_ALLOPHONES`` share the slot 41 boundary.

    This is intentional in the C source — BLOCK_RULES is just past the last
    real allophone (JH = 40), so the rule engine treats it as an "all
    allophones" sentinel.
    """
    assert jp.JAP_BLOCK_RULES == jp.JAP_TOT_ALLOPHONES == 41
