"""Verify partyp / parini / divtab tables match ph_romi.c."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.ph import parameter_tables as pt

_C_SOURCE: Path = Path("/tmp/dectalk-src/src/dapi/src/ph/ph_romi.c")


def _parse_table(name: str, decl: str) -> list[int]:
    """Extract the ``const <decl> <name>[] = { ... };`` initialiser."""
    text = _C_SOURCE.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"const\s+{re.escape(decl)}\s+{re.escape(name)}\s*\[\s*\]\s*=\s*\{{(.*?)\}};"
    match = re.search(pattern, text, re.DOTALL)
    if match is None:
        return []
    body = match.group(1)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    return [int(v) for v in re.findall(r"-?\d+", body)]


@pytest.mark.skipif(not _C_SOURCE.exists(), reason="C source not available")
def test_partyp_matches_c_source() -> None:
    """``partyp`` matches ph_romi.c — 16 entries, types 0..4."""
    c_values = _parse_table("partyp", "char")
    assert len(c_values) == 16
    assert tuple(c_values) == pt.partyp


@pytest.mark.skipif(not _C_SOURCE.exists(), reason="C source not available")
def test_parini_matches_c_source() -> None:
    """``parini`` matches ph_romi.c — 16 init values."""
    c_values = _parse_table("parini", "short")
    assert len(c_values) == 16
    assert tuple(c_values) == pt.parini


@pytest.mark.skipif(not _C_SOURCE.exists(), reason="C source not available")
def test_divtab_matches_c_source() -> None:
    """``divtab`` matches ph_romi.c — 50 entries."""
    c_values = _parse_table("divtab", "short")
    assert len(c_values) == 50
    assert tuple(c_values) == pt.divtab


def test_partyp_size() -> None:
    """``partyp`` has 16 entries (F1..TILT)."""
    assert len(pt.partyp) == 16


def test_parini_size() -> None:
    """``parini`` has 16 entries."""
    assert len(pt.parini) == 16


def test_divtab_size() -> None:
    """``divtab`` has 50 entries (n=0..49)."""
    assert len(pt.divtab) == 50


def test_divtab_identity_at_zero_and_one() -> None:
    """``divtab[0]`` and ``divtab[1]`` are both 16384 (Q14 1.0)."""
    assert pt.divtab[0] == 16384
    assert pt.divtab[1] == 16384


def test_divtab_approximates_q14_reciprocal() -> None:
    """For n >= 2, ``divtab[n] ~ 16384 // n`` (within rounding)."""
    for n in range(2, 50):
        expected = round(16384 / n)
        # Allow ±1 for the C source's rounding choice.
        assert abs(pt.divtab[n] - expected) <= 1


def test_parini_default_formants() -> None:
    """``parini`` defaults to Paul-ish 600/1600/2600 Hz formants."""
    assert pt.parini[0] == 600  # F1
    assert pt.parini[1] == 1600  # F2
    assert pt.parini[2] == 2600  # F3
    assert pt.parini[3] == 300  # FZ (nasal zero)
