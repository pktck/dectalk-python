"""Verify per-language allophone counts match l_all_ph.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.include import all_phon_counts as apc
from dectalk.include.phoneme_codes import US_TOT_ALLOPHONES

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/include/l_all_ph.h")


def _parse_define(name: str) -> int | None:
    """Return the int value of ``#define <name> <expr>`` accepting ``(N)``."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"^#define\s+{re.escape(name)}\s+\(?\s*(-?\d+)\s*\)?\s*$"
    for line in text.splitlines():
        match = re.match(pattern, line.split("/*")[0].split("//")[0])
        if match:
            return int(match.group(1))
    return None


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
@pytest.mark.parametrize(
    ("py_attr", "c_name", "expected"),
    [
        ("UK_TOT_ALLOPHONES", "UK_TOT_ALLOPHONES", 57),
        ("GR_TOT_ALLOPHONES", "GR_TOT_ALLOPHONES", 62),
        ("LA_TOT_ALLOPHONES", "LA_TOT_ALLOPHONES", 39),
        ("SP_TOT_ALLOPHONES", "SP_TOT_ALLOPHONES", 39),
        ("FR_TOT_ALLOPHONES", "FR_TOT_ALLOPHONES", 40),
        ("MAX_PHONES", "MAX_PHONES", 99),
    ],
)
def test_allophone_count_matches_c(py_attr: str, c_name: str, expected: int) -> None:
    """Each language's allophone count matches l_all_ph.h."""
    c_value = _parse_define(c_name)
    assert c_value is not None
    assert c_value == expected
    assert getattr(apc, py_attr) == expected


def test_novalid_equals_sp_tot_allophones() -> None:
    """``NOVALID`` is ``SP_TOT_ALLOPHONES + 0`` (the C source's expression)."""
    assert apc.NOVALID == apc.SP_TOT_ALLOPHONES


def test_us_largest_phoneme_inventory() -> None:
    """US English has the largest allophone inventory (71 codes)."""
    assert US_TOT_ALLOPHONES > apc.GR_TOT_ALLOPHONES
    assert US_TOT_ALLOPHONES > apc.UK_TOT_ALLOPHONES
    assert US_TOT_ALLOPHONES > apc.FR_TOT_ALLOPHONES
    assert US_TOT_ALLOPHONES > apc.LA_TOT_ALLOPHONES
    assert US_TOT_ALLOPHONES > apc.SP_TOT_ALLOPHONES


def test_max_phones_above_all_languages() -> None:
    """``MAX_PHONES`` (99) is an upper bound across all language inventories."""
    for count in (
        US_TOT_ALLOPHONES,
        apc.UK_TOT_ALLOPHONES,
        apc.GR_TOT_ALLOPHONES,
        apc.LA_TOT_ALLOPHONES,
        apc.SP_TOT_ALLOPHONES,
        apc.FR_TOT_ALLOPHONES,
    ):
        assert count < apc.MAX_PHONES


def test_spanish_variants_share_count() -> None:
    """Castilian (SP) and Latin American (LA) Spanish have the same count."""
    assert apc.SP_TOT_ALLOPHONES == apc.LA_TOT_ALLOPHONES
