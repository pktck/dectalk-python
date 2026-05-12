"""Verify USP_* font-encoded codes match p_all_ph.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.include import usp_codes
from dectalk.include.cmd_codes import PSFONT
from dectalk.include.phoneme_codes import PFUSA, USPhoneme

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/ph/p_all_ph.h")
_DEFINE_RE: re.Pattern[str] = re.compile(
    r"^#define\s+USP_([A-Z0-9_]+)\s+\(\(\s*PFUSA\s*<<\s*PSFONT\s*\)\s*\|\s*US_([A-Z0-9_]+)\s*\)",
)


def _parse_c_defines() -> dict[str, str]:
    """Extract ``USP_<name> => US_<name>`` mappings from p_all_ph.h."""
    out: dict[str, str] = {}
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    for line in text.splitlines():
        match = _DEFINE_RE.match(line)
        if match:
            out[match.group(1)] = match.group(2)
    return out


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_all_usp_codes_match_c_source() -> None:
    """Every ``USP_*`` we export matches the C-source bit-shift."""
    expected = _parse_c_defines()
    font = PFUSA << PSFONT
    for usp_name, us_name in expected.items():
        # USP_YX in C maps to US_Y (the C source renames Y -> YX in the
        # font-encoded namespace to disambiguate the IntEnum value).
        if us_name == "Y":
            us_enum = USPhoneme.Y
        elif us_name == "OR":
            us_enum = USPhoneme.OR_
        else:
            us_enum = getattr(USPhoneme, us_name)
        expected_value = font | int(us_enum)
        python_name = f"USP_{usp_name}"
        assert hasattr(usp_codes, python_name), f"missing {python_name}"
        assert getattr(usp_codes, python_name) == expected_value, (
            f"{python_name} should be 0x{expected_value:04X}"
        )


def test_usp_p_value() -> None:
    """``USP_P`` is ``(0x1E << 8) | 45`` = 0x1E2D."""
    expected = (PFUSA << PSFONT) | int(USPhoneme.P)
    assert expected == usp_codes.USP_P
    assert usp_codes.USP_P == 0x1E2D


def test_usp_iy_low_byte() -> None:
    """``USP_IY`` has low byte 1 (US_IY = 1)."""
    assert usp_codes.USP_IY & 0xFF == 1
    assert usp_codes.USP_IY == ((PFUSA << PSFONT) | 1)


def test_usp_codes_distinct() -> None:
    """All 70 exported USP_* values are pairwise distinct."""
    values = {
        getattr(usp_codes, n)
        for n in dir(usp_codes)
        if n.startswith("USP_") and not n.startswith("USP__")
    }
    # 70 USP_* names in p_all_ph.h.
    assert len(values) == 70
