"""Verify named character constants match iso_char.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.include import iso_char as ic

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/include/iso_char.h")


def _parse_c_defines() -> dict[str, int]:
    """Return ``{name: value}`` for every ``#define C_<NAME> 0x..``."""
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    out: dict[str, int] = {}
    for line in text.splitlines():
        match = re.match(
            r"^\s*#define\s+(C_[A-Za-z0-9_]+)\s+(0[xX][0-9A-Fa-f]+|\d+)\b",
            line,
        )
        if match:
            name = match.group(1)
            raw = match.group(2)
            value = int(raw, 16) if raw.lower().startswith("0x") else int(raw)
            out[name] = value
    return out


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_every_c_define_is_ported() -> None:
    """All ``C_*`` ``#define``s in iso_char.h appear in the Python module."""
    c_defines = _parse_c_defines()
    missing: list[str] = []
    mismatched: list[tuple[str, int, int]] = []
    for name, c_value in c_defines.items():
        py_value = getattr(ic, name, None)
        if py_value is None:
            missing.append(name)
        elif py_value != c_value:
            mismatched.append((name, c_value, py_value))
    assert missing == [], f"Missing: {missing}"
    assert mismatched == [], f"Mismatched: {mismatched}"


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_total_c_defines_count() -> None:
    """The header has the expected number of ``C_*`` constants."""
    c_defines = _parse_c_defines()
    # 95 ASCII printables (0x20..0x7E) + 96 Latin-1 high-bit codes.
    assert len(c_defines) == 191


def test_ascii_digit_codes_dense() -> None:
    """``C_0``..``C_9`` cover ``0x30..0x39``."""
    digits = [ic.C_0, ic.C_1, ic.C_2, ic.C_3, ic.C_4, ic.C_5, ic.C_6, ic.C_7, ic.C_8, ic.C_9]
    assert digits == list(range(0x30, 0x3A))


def test_ascii_uppercase_letters_dense() -> None:
    """``C_A``..``C_Z`` cover ``0x41..0x5A``."""
    letters = [ic.C_A, ic.C_B, ic.C_C, ic.C_D, ic.C_E, ic.C_F, ic.C_G]
    assert letters == [0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47]
    assert ic.C_Z == 0x5A


def test_ascii_lowercase_letters_dense() -> None:
    """``C_a``..``C_z`` cover ``0x61..0x7A``."""
    assert ic.C_a == 0x61
    assert ic.C_z == 0x7A


def test_s3_and_aca_alias() -> None:
    """``C_S3`` and ``C_ACA`` collide on ``0xB3`` (matching the C header)."""
    assert ic.C_S3 == 0xB3
    assert ic.C_ACA == 0xB3


def test_fractions_match_graphic_codes() -> None:
    """``C_F14`` and ``C_F12`` agree with :mod:`dectalk.include.graphic_codes`."""
    from dectalk.include import graphic_codes as gc  # noqa: PLC0415

    assert ic.C_F14 == gc.FOURTH
    assert ic.C_F12 == gc.HALF


def test_punctuation_byte_values() -> None:
    """Selected punctuation codes match ASCII."""
    assert ic.C_SPACE == 0x20
    assert ord(",") == ic.C_COMMA
    assert ord(".") == ic.C_PERIOD
    assert ord("?") == ic.C_QUEST
    assert ord("!") == ic.C_EXCL
    assert ord("@") == ic.C_AT


def test_latin1_currency_signs() -> None:
    """Currency-sign bytes match Latin-1."""
    assert bytes([ic.C_CENT]).decode("latin-1") == "¢"
    assert bytes([ic.C_POUN]).decode("latin-1") == "£"
    assert bytes([ic.C_YEN]).decode("latin-1") == "¥"
    assert bytes([ic.C_SECT]).decode("latin-1") == "§"
