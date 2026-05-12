"""Verify ``notetab`` matches ph_romi.c byte-for-byte."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.ph import notetab as nt

_C_SOURCE: Path = Path("/tmp/dectalk-src/src/dapi/src/ph/ph_romi.c")


def _parse_notetab() -> list[int]:
    """Extract the 37 short values from the notetab[] initialiser."""
    text = _C_SOURCE.read_bytes().replace(b"\r", b"").decode("latin-1")
    # Find the initialiser block: const short notetab[] = { ... };
    match = re.search(
        r"const\s+short\s+notetab\s*\[\s*\]\s*=\s*\{(.*?)\};",
        text,
        re.DOTALL,
    )
    if match is None:
        return []
    body = match.group(1)
    # Strip comments before parsing values.
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    values = re.findall(r"\b\d+\b", body)
    return [int(v) for v in values]


@pytest.mark.skipif(not _C_SOURCE.exists(), reason="C source not available")
def test_notetab_matches_c_source() -> None:
    """All 37 entries match ph_romi.c."""
    c_values = _parse_notetab()
    assert len(c_values) == 37
    assert tuple(c_values) == nt.notetab


def test_notetab_size() -> None:
    """37 entries covering C2..C5."""
    assert len(nt.notetab) == nt.NOTETAB_SIZE == 37


def test_notetab_monotonically_increasing() -> None:
    """Each note's F0 is higher than the previous (notes go C2 → C5)."""
    for i in range(1, len(nt.notetab)):
        assert nt.notetab[i] > nt.notetab[i - 1], (
            f"note {i + 1} ({nt.notetab[i]}) <= note {i} ({nt.notetab[i - 1]})"
        )


def test_octave_doubling() -> None:
    """C3 (note 13) ~ 2 * C2 (note 1); C4 (note 25) ~ 4 * C2."""
    c2 = nt.notetab[0]  # note 1
    c3 = nt.notetab[12]  # note 13
    c4 = nt.notetab[24]  # note 25
    c5 = nt.notetab[36]  # note 37
    # Pure octave doubling within a few percent (the integer rounding
    # introduces ~0.5% error).
    assert abs(c3 - 2 * c2) / c3 < 0.005
    assert abs(c4 - 4 * c2) / c4 < 0.005
    assert abs(c5 - 8 * c2) / c5 < 0.005
