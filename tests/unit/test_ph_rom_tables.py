"""Verify the PH ROM tables match p_us_rom.c byte-for-byte.

Re-parses every ``const short us_*[]`` array in
``src/dapi/src/ph/p_us_rom.c`` and asserts our Python literal matches.
This is the bulky bit: 21 tables totalling ~6700 short ints that the
PH module consumes when producing Klatt-frame targets.

Skips when ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.ph import rom_tables as rt

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / ("src/dapi/src/ph/p_us_rom.c")

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _parse_rom_table(name: str) -> tuple[int, ...]:
    """Parse a ``const short NAME[]? = { ... };`` initialiser."""
    text = _C_FILE.read_text(encoding="latin-1")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//.*", "", text)
    m = re.search(
        rf"const\s+short\s+{re.escape(name)}\s*\[\d*\]\s*=\s*\{{(.+?)\}};",
        text,
        re.DOTALL,
    )
    assert m is not None, f"could not find {name}"
    return tuple(int(v) for v in re.findall(r"-?\d+", m.group(1)))


_TABLES: tuple[str, ...] = (
    "us_inhdr", "us_mindur", "us_burdr", "us_f0segtars",
    "us_begtyp", "us_endtyp", "us_place", "us_featb",
    "us_maltar", "us_femtar", "us_maldip", "us_femdip",
    "us_ptram", "us_malamp", "us_femamp", "us_plocu",
    "us_maleloc", "us_femloc",
    "us_f0glstp", "us_f0_phrase_position", "us_f0_stress_level",
)  # fmt: skip


@pytest.mark.parametrize("name", _TABLES)
def test_rom_table_matches_c(name: str) -> None:
    """Each ``us_*`` ROM table matches the C source initialiser."""
    expected = _parse_rom_table(name)
    assert getattr(rt, name) == expected, f"{name} mismatch"


def test_per_phoneme_tables_have_71_entries() -> None:
    """The simple per-allophone tables all have 71 entries."""
    expected = 71
    for name in ("us_inhdr", "us_mindur", "us_burdr", "us_f0segtars",
                 "us_begtyp", "us_endtyp", "us_place", "us_ptram"):  # fmt: skip
        assert len(getattr(rt, name)) == expected, name


def test_global_prosody_tables_size() -> None:
    """Global prosody tables have their published sizes."""
    glottal_step_count = 6
    phrase_positions = 8
    stress_levels = 8
    assert len(rt.us_f0glstp) == glottal_step_count
    assert len(rt.us_f0_phrase_position) == phrase_positions
    assert len(rt.us_f0_stress_level) == stress_levels


def test_rom_tables_contain_no_garbage() -> None:
    """All values fit in a signed short (-32768 .. 32767)."""
    int16_min = -32768
    int16_max = 32767
    for name in _TABLES:
        for i, v in enumerate(getattr(rt, name)):
            assert int16_min <= v <= int16_max, f"{name}[{i}]={v}"
