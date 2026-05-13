"""Verify arpabet_lang_flags / arpabet_lang_fonts match usa_init.c."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.cmd.language_lookup import language_prefixes
from dectalk.include.phoneme_codes import PFFR, PFGR, PFLA, PFSP, PFUK, PFUSA
from dectalk.kernel import arpabet_lang_tables as alt
from dectalk.kernel.lang_codes import (
    LANG_british,
    LANG_english,
    LANG_french,
    LANG_german,
    LANG_latin_american,
    LANG_spanish,
)

_C_FILE: Path = Path("/tmp/dectalk-src/src/dapi/src/kernel/usa_init.c")


def _parse_array(name: str) -> list[str] | None:
    """Return the comma-separated entries of ``const ... <name>[] = { ... };``."""
    if not _C_FILE.exists():
        return None
    text = _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"\b{re.escape(name)}\[\]\s*=\s*\{{([^}}]+)\}}"
    match = re.search(pattern, text)
    if not match:
        return None
    body = re.sub(r"/\*.*?\*/", "", match.group(1), flags=re.DOTALL)
    return [tok.strip() for tok in body.split(",") if tok.strip()]


@pytest.mark.skipif(not _C_FILE.exists(), reason="C source not available")
def test_arpabet_lang_flags_matches_c() -> None:
    """``arpabet_lang_flags`` matches the C array entry-for-entry."""
    entries = _parse_array("arpabet_lang_flags")
    assert entries is not None
    expected = [
        "LANG_english",
        "LANG_british",
        "LANG_spanish",
        "LANG_german",
        "LANG_latin_american",
        "LANG_french",
    ]
    assert entries == expected
    py_expected = (
        LANG_english,
        LANG_british,
        LANG_spanish,
        LANG_german,
        LANG_latin_american,
        LANG_french,
    )
    assert alt.arpabet_lang_flags == py_expected


@pytest.mark.skipif(not _C_FILE.exists(), reason="C source not available")
def test_arpabet_lang_fonts_matches_c() -> None:
    """``arpabet_lang_fonts`` matches the C array entry-for-entry."""
    entries = _parse_array("arpabet_lang_fonts")
    assert entries is not None
    expected = ["PFUSA", "PFUK", "PFSP", "PFGR", "PFLA", "PFFR"]
    assert entries == expected
    assert alt.arpabet_lang_fonts == (PFUSA, PFUK, PFSP, PFGR, PFLA, PFFR)


def test_arpabet_tables_align_with_language_prefixes() -> None:
    """Both arrays have one entry per language slot in ``language_prefixes``."""
    n_slots = len(language_prefixes) // 2
    assert len(alt.arpabet_lang_flags) == n_slots
    assert len(alt.arpabet_lang_fonts) == n_slots
    assert n_slots == 6


def test_flags_and_fonts_disjoint() -> None:
    """Each flag and font value appears exactly once."""
    assert len(set(alt.arpabet_lang_flags)) == len(alt.arpabet_lang_flags)
    assert len(set(alt.arpabet_lang_fonts)) == len(alt.arpabet_lang_fonts)


def test_us_slot_is_english_pfusa() -> None:
    """Slot 0 (``us``) maps to LANG_english + PFUSA."""
    assert alt.arpabet_lang_flags[0] == LANG_english
    assert alt.arpabet_lang_fonts[0] == PFUSA


def test_pfusa_is_highest_font() -> None:
    """``PFUSA`` (0x1E) is the largest font code in the table."""
    fonts = alt.arpabet_lang_fonts
    assert fonts[0] == 0x1E
    assert max(fonts) == fonts[0]
    assert min(fonts) == PFFR == 0x19
