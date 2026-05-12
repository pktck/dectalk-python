"""Verify the US English F0 intonation tables match ph_inton2.c.

Re-parses the four ``const short us_f0_*[]`` initialisers from
``src/dapi/src/ph/ph_inton2.c`` (selecting the non-POETRY branch for
``us_f0_mphrase_position``) and asserts every entry matches our
Python literal.

Skips when ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.ph import f0_intonation as f0

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / ("src/dapi/src/ph/ph_inton2.c")

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _parse_table(name: str) -> tuple[int, ...]:
    """Parse ``const short NAME[] = { ... };`` from the C source.

    For ``us_f0_mphrase_position`` we want the non-POETRY branch (the
    Linux build's #else clause).
    """
    text = _C_FILE.read_text(encoding="latin-1")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//.*", "", text)
    # For us_f0_mphrase_position there's a #ifdef POETRY / #else split.
    # Match the FIRST occurrence; if that's inside #ifdef POETRY, jump
    # to the second one (the #else branch).
    pat = rf"const\s+short\s+{re.escape(name)}\s*\[\]\s*=\s*\{{(.+?)\}}\s*;"
    matches = list(re.finditer(pat, text, re.DOTALL))
    assert matches, f"missing {name}"
    if name == "us_f0_mphrase_position":
        # Skip the POETRY block (first match if it's inside #ifdef POETRY).
        match = matches[-1] if len(matches) > 1 else matches[0]
    else:
        match = matches[0]
    body = match.group(1)
    out: list[int] = []
    for tok in body.split(","):
        t = tok.strip()
        if re.fullmatch(r"-?\d+", t):
            out.append(int(t))
    return tuple(out)


def test_us_f0_mphrase_position_matches_c() -> None:
    """Male F0 phrase-position table (non-POETRY branch)."""
    assert f0.us_f0_mphrase_position == _parse_table("us_f0_mphrase_position")


def test_us_f0_mstress_level_matches_c() -> None:
    """Male F0 stress-level table."""
    assert f0.us_f0_mstress_level == _parse_table("us_f0_mstress_level")


def test_us_f0_fphrase_position_matches_c() -> None:
    """Female F0 phrase-position table."""
    assert f0.us_f0_fphrase_position == _parse_table("us_f0_fphrase_position")


def test_us_f0_fstress_level_matches_c() -> None:
    """Female F0 stress-level table."""
    assert f0.us_f0_fstress_level == _parse_table("us_f0_fstress_level")


def test_phrase_position_tables_have_8_entries() -> None:
    """Each phrase-position table covers 1st..8th accent in a clause."""
    expected = 8
    assert len(f0.us_f0_mphrase_position) == expected
    assert len(f0.us_f0_fphrase_position) == expected


def test_stress_level_tables_have_4_entries() -> None:
    """Each stress-level table covers unstr, primary, secondary, emphasis."""
    expected = 4
    assert len(f0.us_f0_mstress_level) == expected
    assert len(f0.us_f0_fstress_level) == expected


def test_first_phrase_position_is_largest_male() -> None:
    """Male: 1st-accent F0 rise is the biggest in the sequence."""
    assert f0.us_f0_mphrase_position[0] == max(f0.us_f0_mphrase_position)


def test_first_phrase_position_is_largest_female() -> None:
    """Female: 1st-accent F0 rise is the biggest in the sequence."""
    assert f0.us_f0_fphrase_position[0] == max(f0.us_f0_fphrase_position)


def test_emphatic_stress_largest() -> None:
    """Emphatic stress (index 3) produces the largest F0 rise."""
    male_emphatic_index = 3
    female_emphatic_index = 3
    assert f0.us_f0_mstress_level[male_emphatic_index] == max(f0.us_f0_mstress_level)
    assert f0.us_f0_fstress_level[female_emphatic_index] == max(f0.us_f0_fstress_level)
