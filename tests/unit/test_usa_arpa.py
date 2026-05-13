"""Verify usa_arpa matches usa_phon.tab."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.include.usa_arpa import usa_arpa

_C_SRC_ENV = "DECTALK_SRC"


def _c_source_path() -> Path | None:
    """Locate ``usa_phon.tab`` on the local checkout, if present."""
    root = os.environ.get(_C_SRC_ENV)
    candidate = Path("/tmp/dectalk-src") if root is None else Path(root)
    path = candidate / "src/dapi/src/include/usa_phon.tab"
    return path if path.is_file() else None


def _parse_usa_arpa(text: str) -> bytes:
    """Parse the C source's ``usa_arpa[]`` initializer into bytes."""
    match = re.search(
        r"const\s+unsigned\s+char\s+usa_arpa\[\]\s*=\s*\{(.*?)\};",
        text,
        re.DOTALL,
    )
    if match is None:
        msg = "usa_arpa[] not found in usa_phon.tab"
        raise AssertionError(msg)
    body = match.group(1)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    # Two token forms: 'X' (single-byte literal) or a bare 0.
    out = bytearray()
    for char_lit, zero_lit in re.findall(r"'(\\.|.)'|(\b0\b)", body):
        if zero_lit:
            out.append(0)
        else:
            c = char_lit
            if c.startswith("\\"):
                escape_map = {r"\\": "\\", r"\'": "'", r"\"": '"'}
                c = escape_map.get(c, c[1])
            assert c is not None
            out.append(ord(c))
    return bytes(out)


def test_usa_arpa_matches_c_source() -> None:
    """The Python ``usa_arpa`` matches the C source byte-for-byte."""
    src = _c_source_path()
    if src is None:
        pytest.skip("DECTALK_SRC not available")
    parsed = _parse_usa_arpa(src.read_text(encoding="latin-1"))
    assert parsed == usa_arpa


def test_usa_arpa_length_is_246() -> None:
    """The table has 246 bytes (123 2-byte slots, codes 0..122)."""
    assert len(usa_arpa) == 246


def test_silence_slot_is_underscore_space() -> None:
    """Code 0 (SIL) is rendered as ``_ ``."""
    assert usa_arpa[0:2] == b"_ "


def test_iy_slot_is_iy() -> None:
    """Code 1 (IY) is rendered as ``iy``."""
    assert usa_arpa[2:4] == b"iy"


def test_block_rules_slot_is_tilde_space() -> None:
    """Code 100 (BLOCK_RULES) is rendered as ``~ ``."""
    assert usa_arpa[200:202] == b"~ "


def test_s1_primary_stress_slot() -> None:
    """Code 103 (S1 primary stress) is rendered as ``' ``."""
    assert usa_arpa[206:208] == b"' "


def test_padding_slots_all_zero() -> None:
    """Codes 71-99 are zero-padded (no ASCII mapping)."""
    for code in range(71, 100):
        slot = usa_arpa[code * 2 : code * 2 + 2]
        assert slot == b"\x00\x00", f"code {code} unexpectedly non-zero: {slot!r}"
