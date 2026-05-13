"""Verify nasal-zero coefficient tables match vtmtable.h."""

from __future__ import annotations

import re
from itertools import pairwise
from pathlib import Path

import pytest

from dectalk.vtm import nasal_zero_tables as nzt

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/vtm/vtmtable.h")


def _parse_array(name: str) -> list[int] | None:
    """Return the integers in ``const S16 <name>[N] = { ... };``."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"const\s+S16\s+{re.escape(name)}\s*\[\s*\d+\s*\]\s*=\s*\{{([^}}]+)\}}"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return None
    body = re.sub(r"/\*.*?\*/", "", match.group(1), flags=re.DOTALL)
    return [int(tok) for tok in re.findall(r"-?\d+", body)]


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_azero_tab_matches_c() -> None:
    """``azero_tab`` is byte-identical to the C array."""
    c_values = _parse_array("azero_tab")
    assert c_values is not None
    assert tuple(c_values) == nzt.azero_tab
    assert len(nzt.azero_tab) == 35


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_bzero_tab_matches_c() -> None:
    """``bzero_tab`` is byte-identical to the C array (all negative)."""
    c_values = _parse_array("bzero_tab")
    assert c_values is not None
    assert tuple(c_values) == nzt.bzero_tab
    assert len(nzt.bzero_tab) == 35
    assert all(v < 0 for v in nzt.bzero_tab)


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_czero_tab_matches_c() -> None:
    """``czero_tab`` is byte-identical to the C array."""
    c_values = _parse_array("czero_tab")
    assert c_values is not None
    assert tuple(c_values) == nzt.czero_tab
    assert len(nzt.czero_tab) == 35


def test_constants_match_c_formulas() -> None:
    """The derived constants match the C-source formulas."""
    assert nzt.NASAL_BW == 80.0
    assert nzt.NASAL_T == 1.0 / 10000.0
    expected_c = int(2 * nzt.NASAL_BW) - 4096
    assert expected_c == nzt.NASAL_C


def test_azero_descends_monotonically() -> None:
    """``azero_tab`` is strictly decreasing across the FZ grid."""
    for prev, curr in pairwise(nzt.azero_tab):
        assert prev > curr


def test_czero_descends_monotonically() -> None:
    """``czero_tab`` is strictly decreasing across the FZ grid."""
    for prev, curr in pairwise(nzt.czero_tab):
        assert prev > curr


def test_bzero_ascends_monotonically() -> None:
    """``bzero_tab`` (negative values) is strictly increasing toward 0."""
    for prev, curr in pairwise(nzt.bzero_tab):
        assert prev < curr
