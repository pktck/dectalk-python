"""Verify the per-voice tables in voice_definitions.py match the active C source.

Re-parses each ``const short NAME[SPDEF]`` (or ``[]``) voice
initialiser from ``src/dapi/src/ph/p_us_vdf_dectalk43.c`` -- the
*active* voice table the shipped binary links against (confirmed by
the build's ``ph_vdefi.d`` dependency list: ``VDF_DECTALK_43`` is
defined and ``HLSYN`` is not) -- for the 9 modern US-English voices
(paul, betty, harry, frank, kit, ursula, rita, wendy, dennis -- *not*
the older ``_8`` variants, which ``ph_vset.c:454-457`` only selects
below 8763 Hz; the US sample rate is 11025 Hz). ``chris`` has no row
of its own in the dectalk43 table and aliases ``paul``.

Each C row initialises 38 of the 39 ``SPDEF`` ints (indices 0..30 =
``SEX``..``SR``, index 31 = ``AGO``, indices 32..37 =
``agvo``/``aguo``/``unvow``/``chink``/``open_quo``/``OutputGainMult``).
The Python literals keep the 33-field convention (indices 0..31
verbatim plus the C output-gain multiplier at index 32). Because every
dectalk43 voice zeroes slots 32..37, the truncated row is
``c_row[0:32] + (c_row[37],)``.

Skips when ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.ph import voice_definitions as vd

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / (
    "src/dapi/src/ph/p_us_vdf_dectalk43.c"
)

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


# Constants used in the C initialisers.
_NAMES: dict[str, int] = {
    "MALE": 1,
    "FEMALE": 0,
    "SPDEF": 39,
    "ZAPF": 6000,  # PC_SAMPLE_RATE == 11025 branch.
    "ZAPB": 6000,
}

# C SPDEF slot count filled by the dectalk43 initialisers, and the
# index of the output-gain multiplier within that layout.
_C_ROW_LEN = 38
_C_OUTPUT_GAIN_IDX = 37


def _eval_field(expr: str) -> int:
    """Resolve a C field expression with symbolic constants."""
    expr = expr.strip()
    for name, value in _NAMES.items():
        expr = re.sub(r"\b" + name + r"\b", str(value), expr)
    return int(eval(expr))


def _parse_voice(name: str) -> tuple[int, ...]:
    """Parse the ``const short NAME[...]`` block matching ``name`` exactly.

    Returns the 33-field row in this module's convention:
    ``c_row[0:32] + (c_row[37],)`` -- the first 32 C slots verbatim plus
    the C output-gain multiplier folded into index 32.
    """
    text = _C_FILE.read_text(encoding="latin-1")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//.*", "", text)
    # Match `const short NAME[...] = { body };` where NAME exactly matches.
    pat = (
        rf"const\s+short\s+{re.escape(name)}\[\s*(?:SPDEF)?\s*\]\s*=\s*"
        r"\{([^}]+(?:\}[^}]*)*?)\}\s*;"
    )
    matches = list(re.finditer(pat, text, re.DOTALL))
    assert matches, f"could not find voice {name!r}"
    body = matches[0].group(1)
    fields = [_eval_field(f) for f in body.split(",") if f.strip()]
    assert len(fields) == _C_ROW_LEN, f"{name}: expected {_C_ROW_LEN} C fields, got {len(fields)}"
    return (*fields[:32], fields[_C_OUTPUT_GAIN_IDX])


# (name, python row). ``chris`` is excluded from the C-source compare
# because the dectalk43 table has no ``chris`` row; it is checked
# separately to equal ``paul``.
_VOICES: tuple[tuple[str, tuple[int, ...]], ...] = (
    ("paul", vd.voice_paul),
    ("betty", vd.voice_betty),
    ("harry", vd.voice_harry),
    ("frank", vd.voice_frank),
    ("kit", vd.voice_kit),
    ("ursula", vd.voice_ursula),
    ("rita", vd.voice_rita),
    ("wendy", vd.voice_wendy),
    ("dennis", vd.voice_dennis),
)


@pytest.mark.parametrize(("name", "py_voice"), _VOICES)
def test_voice_matches_c_source(name: str, py_voice: tuple[int, ...]) -> None:
    """Each voice's parameter array matches the active dectalk43 initialiser."""
    assert py_voice == _parse_voice(name)


def test_chris_aliases_paul() -> None:
    """Crusty Chris has no dectalk43 row of its own; it equals Paul."""
    assert vd.voice_chris == vd.voice_paul == _parse_voice("paul")


def test_all_voices_have_33_entries() -> None:
    """Every modern voice initialises 33 of the 39 SPDEF fields (rest zero)."""
    expected_len = 33
    for _name, voice in (*_VOICES, ("chris", vd.voice_chris)):
        assert len(voice) == expected_len


def test_sex_field_matches_canonical_genders() -> None:
    """Field 0 (SEX) matches the canonical male/female assignment for each voice."""
    male = 1
    female = 0
    expected = {
        "paul": male,
        "chris": male,
        "betty": female,
        "harry": male,
        "frank": male,
        "kit": female,
        "ursula": female,
        "rita": female,
        "wendy": female,
        "dennis": male,
    }
    voice_map = dict((*_VOICES, ("chris", vd.voice_chris)))
    for name, sex in expected.items():
        assert voice_map[name][0] == sex, f"{name} should be sex={sex}"


def test_voices_tuple_indexed_by_speaker_id() -> None:
    """``vd.voices[i]`` matches the i-th voice (matches voice_names order)."""
    assert vd.voices[0] is vd.voice_paul
    assert vd.voices[1] is vd.voice_chris
    assert vd.voices[2] is vd.voice_betty


def test_paul_pitch_is_average() -> None:
    """Paul (the reference voice) has AP=122 Hz (the active dectalk43 table)."""
    expected_ap = 122
    ap_index = 3
    assert vd.voice_paul[ap_index] == expected_ap


def test_paul_gains_match_active_table() -> None:
    """Paul's source-gain row is the active non-``_8`` dectalk43 row.

    These are the gains that feed synth amplitude. The retired
    ``p_us_vdf.c`` reference had GF=67 GH=67 GV=68 GN=72 G1=71 G3=50
    G4=67 LO=81 OS=-1; the active dectalk43 ``paul`` row (selected at
    >= 8763 Hz) is GF=70 GH=70 GV=65 GN=74 G1=68 G3=48 G4=64 LO=86
    OS=0.
    """
    # idx: 16 GF, 17 GH, 18 GV, 19 GN, 20 G1, 21 G2, 22 G3, 23 G4,
    #      24 LO, 32 OS
    assert vd.voice_paul[16] == 70  # GF
    assert vd.voice_paul[17] == 70  # GH
    assert vd.voice_paul[18] == 65  # GV
    assert vd.voice_paul[19] == 74  # GN
    assert vd.voice_paul[20] == 68  # G1
    assert vd.voice_paul[22] == 48  # G3
    assert vd.voice_paul[23] == 64  # G4
    assert vd.voice_paul[24] == 86  # LO
    assert vd.voice_paul[32] == 0  # OS (output gain multiplier)


def test_kit_pitch_is_higher_than_paul() -> None:
    """Kit the Kid has a higher pitch than Perfect Paul."""
    ap_index = 3
    assert vd.voice_kit[ap_index] > vd.voice_paul[ap_index]


def test_dennis_assertiveness_high() -> None:
    """Doctor Dennis is assertive — AS (field 2) at full 100."""
    expected_as = 100
    as_index = 2
    assert vd.voice_dennis[as_index] == expected_as
