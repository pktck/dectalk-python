"""Verify language ID codes from kernel.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.kernel import lang_codes as lc

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/include/kernel.h")


def _parse_define(name: str) -> int | None:
    """Return the int value of a ``#define <name> 0xN``."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"^#define\s+{re.escape(name)}\s+0x([0-9A-Fa-f]+)\b"
    for line in text.splitlines():
        match = re.match(pattern, line)
        if match:
            return int(match.group(1), 16)
    return None


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
@pytest.mark.parametrize(
    ("py_attr", "c_name", "expected"),
    [
        ("LANG_english", "LANG_english", 0x0000),
        ("LANG_french", "LANG_french", 0x0001),
        ("LANG_german", "LANG_german", 0x0002),
        ("LANG_spanish", "LANG_spanish", 0x0003),
        ("LANG_japanese", "LANG_japanese", 0x0004),
        ("LANG_british", "LANG_british", 0x0005),
        ("LANG_latin_american", "LANG_latin_american", 0x0006),
        ("LANG_italian", "LANG_italian", 0x0007),
        ("LANG_none", "LANG_none", 0xFFFF),
        ("LANG_lts_ready", "LANG_lts_ready", 0x1),
    ],
)
def test_lang_code(py_attr: str, c_name: str, expected: int) -> None:
    """Each LANG_ code matches kernel.h."""
    c_value = _parse_define(c_name)
    assert c_value is not None
    assert c_value == expected
    assert getattr(lc, py_attr) == expected


def test_lang_codes_dense_0_to_7() -> None:
    """The 8 actual languages (excluding none and lts_ready) are 0..7."""
    codes = {
        lc.LANG_english,
        lc.LANG_french,
        lc.LANG_german,
        lc.LANG_spanish,
        lc.LANG_japanese,
        lc.LANG_british,
        lc.LANG_latin_american,
        lc.LANG_italian,
    }
    assert codes == set(range(8))


def test_lang_none_sentinel() -> None:
    """LANG_none is the 16-bit ``0xFFFF`` sentinel."""
    assert lc.LANG_none == 0xFFFF


def test_ready_flags() -> None:
    """LTS / PH / map ready signal bits."""
    assert lc.LANG_lts_ready == 0x1
    assert lc.LANG_ph_ready == 0x2
    assert lc.LANG_map_ready == 0x4
    assert lc.LANG_tables_ready == 0x4  # alias of map_ready
    # "Both ready" is the OR of the three.
    assert lc.LANG_both_ready == 0x7
    assert lc.LANG_both_ready == (lc.LANG_lts_ready | lc.LANG_ph_ready | lc.LANG_map_ready)
