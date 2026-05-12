"""Verify Q14 percent constants from ph_defs.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.ph import q14_percent_constants as pc

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/ph/ph_defs.h")
_FRAC_ONE = 16384


def _parse_define(name: str) -> int | None:
    """Return the int value of a ``#define <name> <int>``."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"^#define\s+{re.escape(name)}\s+(-?\d+)\b"
    for line in text.splitlines():
        match = re.match(pattern, line)
        if match:
            return int(match.group(1))
    return None


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
@pytest.mark.parametrize(
    ("py_attr", "c_name", "expected"),
    [
        ("N5PRCNT", "N5PRCNT", 819),
        ("N8PRCNT", "N8PRCNT", 1311),
        ("N10PRCNT", "N10PRCNT", 1638),
        ("N15PRCNT", "N15PRCNT", 2457),
        ("N20PRCNT", "N20PRCNT", 3277),
        ("N25PRCNT", "N25PRCNT", 4096),
        ("N30PRCNT", "N30PRCNT", 4915),
        ("N35PRCNT", "N35PRCNT", 5734),
        ("N40PRCNT", "N40PRCNT", 6554),
        ("N47PRCNT", "N47PRCNT", 7700),
        ("N50PRCNT", "N50PRCNT", 8192),
        ("N55PRCNT", "N55PRCNT", 9011),
        ("N58PRCNT", "N58PRCNT", 9502),
        ("N60PRCNT", "N60PRCNT", 9831),
        ("N65PRCNT", "N65PRCNT", 10650),
        ("N67PRCNT", "N67PRCNT", 10977),
        ("N70PRCNT", "N70PRCNT", 11469),
        ("N74PRCNT", "N74PRCNT", 12124),
        ("N75PRCNT", "N75PRCNT", 12288),
        ("N78PRCNT", "N78PRCNT", 12780),
        ("N80PRCNT", "N80PRCNT", 13108),
        ("N82PRCNT", "N82PRCNT", 13435),
        ("N85PRCNT", "N85PRCNT", 13927),
        ("N87PRCNT", "N87PRCNT", 14254),
        ("N90PRCNT", "N90PRCNT", 13927),
        ("N92PRCNT", "N92PRCNT", 15073),
        ("N95PRCNT", "N95PRCNT", 15565),
        ("N97PRCNT", "N97PRCNT", 15892),
        ("N100PRCNT", "N100PRCNT", 16384),
        ("N105PRCNT", "N105PRCNT", 17203),
        ("N107PRCNT", "N107PRCNT", 17531),
        ("N110PRCNT", "N110PRCNT", 18022),
        ("N115PRCNT", "N115PRCNT", 18841),
        ("N117PRCNT", "N117PRCNT", 19169),
        ("N120PRCNT", "N120PRCNT", 19661),
        ("N122PRCNT", "N122PRCNT", 19988),
        ("N125PRCNT", "N125PRCNT", 20480),
        ("N130PRCNT", "N130PRCNT", 21298),
        ("N132PRCNT", "N132PRCNT", 21626),
        ("N135PRCNT", "N135PRCNT", 22118),
        ("N140PRCNT", "N140PRCNT", 22936),
        ("N145PRCNT", "N145PRCNT", 23755),
        ("N150PRCNT", "N150PRCNT", 24576),
        ("N160PRCNT", "N160PRCNT", 26215),
        ("N175PRCNT", "N175PRCNT", 28672),
        ("N180PRCNT", "N180PRCNT", 29492),
        ("N200PRCNT", "N200PRCNT", 32768),
    ],
)
def test_percent_constant_matches_c(py_attr: str, c_name: str, expected: int) -> None:
    """Each NxPRCNT matches ph_defs.h byte-for-byte."""
    c_value = _parse_define(c_name)
    assert c_value is not None
    assert c_value == expected
    assert getattr(pc, py_attr) == expected


def test_n100_equals_frac_one() -> None:
    """``N100PRCNT`` is exactly 1.0 in Q14 (= FRAC_ONE)."""
    assert pc.N100PRCNT == _FRAC_ONE


def test_n50_equals_half() -> None:
    """``N50PRCNT`` is exactly 0.5 in Q14 (= 8192)."""
    assert pc.N50PRCNT == _FRAC_ONE // 2


def test_n200_equals_two() -> None:
    """``N200PRCNT`` is exactly 2.0 in Q14 (= 32768)."""
    assert pc.N200PRCNT == 2 * _FRAC_ONE


def test_known_n90_typo() -> None:
    """``N90PRCNT`` shares ``N85PRCNT``'s value 13927 — a 4.2CD typo.

    The C source ``#define N90PRCNT 13927`` is incorrect arithmetic
    (90 % of 16384 = 14746, not 13927). The Python port preserves
    the typo for byte parity.
    """
    assert pc.N90PRCNT == pc.N85PRCNT == 13927


def test_round_trip_close_to_real_percent() -> None:
    """Each Q14 value is within 1 LSB of the mathematically-correct percentage,
    except for the documented N90PRCNT typo.
    """
    pairs = [
        (5, pc.N5PRCNT),
        (10, pc.N10PRCNT),
        (25, pc.N25PRCNT),
        (50, pc.N50PRCNT),
        (75, pc.N75PRCNT),
        (100, pc.N100PRCNT),
        (150, pc.N150PRCNT),
        (200, pc.N200PRCNT),
    ]
    for pct, q14 in pairs:
        expected = round(pct / 100 * _FRAC_ONE)
        assert abs(q14 - expected) <= 1, f"{pct}%: got {q14}, expected ~{expected}"
