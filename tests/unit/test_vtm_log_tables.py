"""Verify logtab / loginv match vtmtable.h."""

from __future__ import annotations

import math
import re
from itertools import pairwise
from pathlib import Path

import pytest

from dectalk.vtm.log_tables import loginv, logtab

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/vtm/vtmtable.h")


def _parse_array(name: str) -> list[int] | None:
    """Return the integers in ``const short <name>[] = { ... };``."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"const\s+short\s+{re.escape(name)}\s*\[\s*\]\s*=\s*\{{(.*?)\}};"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return None
    body = re.sub(r"/\*.*?\*/", "", match.group(1), flags=re.DOTALL)
    return [int(tok) for tok in re.findall(r"-?\d+", body)]


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_logtab_matches_c() -> None:
    """Every logtab entry matches the C array."""
    c_values = _parse_array("logtab")
    assert c_values is not None
    assert tuple(c_values) == logtab


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_loginv_matches_c() -> None:
    """Every loginv entry matches the C array."""
    c_values = _parse_array("loginv")
    assert c_values is not None
    assert tuple(c_values) == loginv


def test_logtab_length_630() -> None:
    """``logtab`` is 630 entries (F=0..5032 step 8)."""
    assert len(logtab) == 630


def test_loginv_length_200() -> None:
    """``loginv`` is 200 entries (n=0..199)."""
    assert len(loginv) == 200


def test_logtab_zero_is_zero() -> None:
    """``logtab[0]`` = 0 (C-source documents this as ``log10(0)`` convention)."""
    assert logtab[0] == 0


def test_loginv_zero_is_full_scale() -> None:
    """``loginv[0]`` = 32767 — effectively 1.0 in Q15."""
    assert loginv[0] == 32767


def test_loginv_thirty_is_half_scale() -> None:
    """``loginv[30]`` ≈ 0.5 * 32768 — half-life every 30 args."""
    # The C-source comment says "loginv[30] = 0.5 of 32768"
    # The actual value is 16386 (0.500 * 32768 rounded)
    assert loginv[30] == 16386


def test_logtab_increases_thirty_per_doubling() -> None:
    """``logtab[2i] - logtab[i]`` ≈ 30 (doubling F adds 30 to log)."""
    # i and 2i: logtab[100] / logtab[200] should differ by ~30
    diff = logtab[200] - logtab[100]
    assert 27 <= diff <= 33


def test_loginv_strictly_descending() -> None:
    """``loginv`` strictly decreases (exponential decay)."""
    for prev, curr in pairwise(loginv):
        assert prev > curr


def test_loginv_matches_formula() -> None:
    """Sample 5 indices and check ``32768 * exp(n * -0.0231)`` formula."""
    for n in (0, 30, 60, 100, 199):
        expected = 32768 * math.exp(n * -0.0231)
        # Loginv values match the formula within ~1 due to rounding.
        assert abs(loginv[n] - expected) < 2
