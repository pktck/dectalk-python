"""Verify default_tune / fr_default_tune match ph_vdefi.c."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.include.cmd_codes import SPDEF
from dectalk.ph.default_tune import default_tune, fr_default_tune

_C_FILE: Path = Path("/tmp/dectalk-src/src/dapi/src/ph/ph_vdefi.c")


def _parse_table(name: str) -> list[int] | None:
    """Return the integers in ``const short <name>[SPDEF] = { ... };``."""
    if not _C_FILE.exists():
        return None
    text = _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"const\s+short\s+{re.escape(name)}\s*\[\s*SPDEF\s*\]\s*=\s*\{{([^}}]+)\}};"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return None
    body = match.group(1)
    body = re.sub(r"#ifdef.*?#endif", "", body, flags=re.DOTALL)
    body = re.sub(r"#ifndef.*?#endif", "", body, flags=re.DOTALL)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    return [int(t) for t in re.findall(r"-?\d+", body)]


@pytest.mark.skipif(not _C_FILE.exists(), reason="C source not available")
def test_default_tune_matches_c() -> None:
    """Every C literal is 0 — the rest of ``SPDEF`` defaults to 0 by C rules."""
    c_values = _parse_table("default_tune")
    assert c_values is not None
    # The C source initialises 37-38 entries explicitly; the C standard
    # zero-fills the remainder of a partially-initialised array. The
    # Python port spells out all ``SPDEF`` zeros for clarity.
    assert 1 <= len(c_values) <= SPDEF
    assert all(v == 0 for v in c_values)
    # And our Python tuple is the full ``SPDEF`` zeros.
    assert default_tune == (0,) * SPDEF


def test_default_tune_length_is_spdef() -> None:
    """``default_tune`` has ``SPDEF`` (39) entries."""
    assert len(default_tune) == SPDEF == 39


def test_default_tune_all_zero() -> None:
    """``default_tune`` is the neutral all-zero starting point."""
    assert all(v == 0 for v in default_tune)


def test_fr_default_tune_matches_default_tune() -> None:
    """French variant is identical to default on the Linux build (all zero)."""
    assert fr_default_tune == default_tune
    assert len(fr_default_tune) == SPDEF
