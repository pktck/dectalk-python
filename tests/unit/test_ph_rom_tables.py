"""Verify the PH ROM tables match the active C source ROM byte-for-byte.

The active voice ROM in the C build is selected by
``dectalkf_klsyn.h:296`` -- ``#define VOICE_ROM_DECTALK_1996M_43F``.
That gates ``ph_romi.c:69`` to ``#include "p_us_rom_dectalk_1996m_43f.c"``
rather than ``p_us_rom.c``. The two files differ in the per-allophone
``us_inhdr`` / ``us_mindur`` tables (and others); the Python port must
mirror the active table set for byte-identical PH-stage durations.

Re-parses ``us_inhdr`` and ``us_mindur`` from the active ROM file and
asserts our Python literals match. Other tables (formant targets,
amplitudes, etc.) are not yet re-aligned to this ROM; see issue
backlog for the full retable work. Skips when ``DECTALK_SRC`` is
absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.ph import rom_tables as rt

_SRC_ROOT = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
# Active ROM per dectalkf_klsyn.h:296 (#define VOICE_ROM_DECTALK_1996M_43F).
_C_FILE = _SRC_ROOT / "src/dapi/src/ph/p_us_rom_dectalk_1996m_43f.c"
# Reference/legacy ROM file -- used for the table set we haven't yet
# moved over to the 1996m_43f values (formant targets, amplitudes, etc.).
_C_FILE_REF = _SRC_ROOT / "src/dapi/src/ph/p_us_rom.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file() or not _C_FILE_REF.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _parse_rom_table(name: str, path: Path) -> tuple[int, ...]:
    """Parse a ``[const ]short NAME[]? = { ... };`` initialiser."""
    text = path.read_text(encoding="latin-1")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//.*", "", text)
    m = re.search(
        rf"(?:const\s+)?short\s+{re.escape(name)}\s*\[\d*\]\s*=\s*\{{(.+?)\}};",
        text,
        re.DOTALL,
    )
    assert m is not None, f"could not find {name} in {path.name}"
    return tuple(int(v) for v in re.findall(r"-?\d+", m.group(1)))


# Tables sourced from the active ROM (VOICE_ROM_DECTALK_1996M_43F).
# Only ``us_inhdr`` and ``us_mindur`` have been re-aligned so far --
# the rest still mirror p_us_rom.c (the legacy reference) and are
# pending a full re-port. Closing the formant-amplitude tables is a
# separate task (issue backlog).
_TABLES_ACTIVE_ROM: tuple[str, ...] = (
    "us_inhdr", "us_mindur",
)  # fmt: skip

_TABLES_REF_ROM: tuple[str, ...] = (
    "us_burdr", "us_f0segtars",
    "us_begtyp", "us_endtyp", "us_place", "us_featb",
    "us_maltar", "us_femtar", "us_maldip", "us_femdip",
    "us_ptram", "us_malamp", "us_femamp", "us_plocu",
    "us_maleloc", "us_femloc",
    "us_f0glstp", "us_f0_phrase_position", "us_f0_stress_level",
)  # fmt: skip

_TABLES: tuple[str, ...] = _TABLES_ACTIVE_ROM + _TABLES_REF_ROM


@pytest.mark.parametrize("name", _TABLES_ACTIVE_ROM)
def test_active_rom_table_matches_c(name: str) -> None:
    """Each ``us_*`` table mirrors the active VOICE_ROM_DECTALK_1996M_43F file.

    The trailing zeros (indices 67..70) in the Python literal are
    sentinel padding -- the C array stops at index 66 (``DF``) and any
    higher allophone code returns ``us_*[code]`` which is undefined
    behaviour in C. The Python port keeps the table at 71 entries to
    match the rest of the per-allophone table family.
    """
    expected = _parse_rom_table(name, _C_FILE)
    pyvals = getattr(rt, name)
    # Compare only the C-defined prefix; Python tail is sentinel padding.
    assert pyvals[: len(expected)] == expected, f"{name} mismatch in active prefix"


@pytest.mark.parametrize("name", _TABLES_REF_ROM)
def test_reference_rom_table_matches_c(name: str) -> None:
    """Each ``us_*`` table (still on the legacy ROM) matches p_us_rom.c."""
    expected = _parse_rom_table(name, _C_FILE_REF)
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
