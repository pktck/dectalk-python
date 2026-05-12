"""Verify ``bounftab`` matches ph_romi.c."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.ph import boundary_table as bt
from dectalk.ph.feature_bits import (
    FCBNEXT,
    FEXCLNEXT,
    FMBNEXT,
    FPERNEXT,
    FPPNEXT,
    FQUENEXT,
    FRELNEXT,
    FSYBNEXT,
    FVPNEXT,
    FWBNEXT,
)

_C_SOURCE: Path = Path("/tmp/dectalk-src/src/dapi/src/ph/ph_romi.c")


@pytest.mark.skipif(not _C_SOURCE.exists(), reason="C source not available")
def test_bounftab_matches_c_source() -> None:
    """The 11 bounftab entries match the C ``const short bounftab[]`` block."""
    text = _C_SOURCE.read_bytes().replace(b"\r", b"").decode("latin-1")
    # Find the const short bounftab[] block (non-SPANISH variant).
    match = re.search(
        r"const\s+short\s+bounftab\s*\[\s*\]\s*=\s*\{(.*?)\};",
        text,
        re.DOTALL,
    )
    assert match is not None
    body = match.group(1)
    # Match the symbolic names in order.
    names = re.findall(r"\bF[A-Z]+NEXT\b", body)
    assert len(names) == 11
    expected_lookup = {
        "FSYBNEXT": FSYBNEXT,
        "FMBNEXT": FMBNEXT,
        "FWBNEXT": FWBNEXT,
        "FPPNEXT": FPPNEXT,
        "FVPNEXT": FVPNEXT,
        "FRELNEXT": FRELNEXT,
        "FCBNEXT": FCBNEXT,
        "FPERNEXT": FPERNEXT,
        "FQUENEXT": FQUENEXT,
        "FEXCLNEXT": FEXCLNEXT,
    }
    expected = tuple(expected_lookup[name] for name in names)
    assert expected == bt.bounftab


def test_bounftab_size() -> None:
    """``bounftab`` has 11 entries (SBOUND..EXCLAIM)."""
    assert len(bt.bounftab) == 11


def test_bounftab_hyphen_aliases_mbound() -> None:
    """SBOUND and HYPHEN map to MBOUND (FMBNEXT) — both treated as morpheme bound."""
    # Index 1 is MBOUND, index 2 is HYPHEN — both should be FMBNEXT.
    assert bt.bounftab[1] == FMBNEXT
    assert bt.bounftab[2] == FMBNEXT
