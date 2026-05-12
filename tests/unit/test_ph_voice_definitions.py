"""Verify the per-voice tables in voice_definitions.py match p_us_vdf.c.

Re-parses each ``const short NAME[SPDEF]`` (or ``[]``) voice
initialiser from ``src/dapi/src/ph/p_us_vdf.c`` for the 10 modern
US-English voices (paul, chris, betty, harry, frank, kit, ursula,
rita, wendy, dennis — *not* the older _8 variants) and asserts the
Python literal matches byte-for-byte.

Skips when ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.ph import voice_definitions as vd

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / ("src/dapi/src/ph/p_us_vdf.c")

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


def _strip_fp_vtm(body: str) -> str:
    """Drop lines inside #ifdef FP_VTM blocks; keep #ifndef FP_VTM bodies."""
    out: list[str] = []
    skip_depth = 0
    in_ifndef_fp_vtm = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#ifndef FP_VTM"):
            in_ifndef_fp_vtm = True
            continue
        if stripped.startswith("#ifdef FP_VTM") or (
            stripped.startswith("#if") and "FP_VTM" in stripped and "ndef" not in stripped
        ):
            skip_depth += 1
            continue
        if stripped.startswith("#else") and in_ifndef_fp_vtm and skip_depth == 0:
            skip_depth += 1
            in_ifndef_fp_vtm = False
            continue
        if stripped.startswith("#endif"):
            if skip_depth > 0:
                skip_depth -= 1
            elif in_ifndef_fp_vtm:
                in_ifndef_fp_vtm = False
            continue
        if skip_depth > 0:
            continue
        if stripped.startswith("#"):
            continue
        out.append(line)
    return "\n".join(out)


def _eval_field(expr: str) -> int:
    """Resolve a C field expression with symbolic constants."""
    expr = expr.strip()
    for name, value in _NAMES.items():
        expr = re.sub(r"\b" + name + r"\b", str(value), expr)
    return int(eval(expr))


def _parse_voice(name: str) -> tuple[int, ...]:
    """Parse the FIRST ``const short NAME[...]`` block matching ``name``.

    The C source has both ``NAME_8`` (older 8 kHz variant) and ``NAME``
    (modern 11025 Hz). We want the modern one — the first declaration
    whose array name exactly matches ``name`` (not ``name_8``).
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
    stripped = _strip_fp_vtm(body)
    fields = [f.strip() for f in stripped.split(",") if f.strip()]
    return tuple(_eval_field(f) for f in fields)


_VOICES: tuple[tuple[str, tuple[int, ...]], ...] = (
    ("paul", vd.voice_paul),
    ("chris", vd.voice_chris),
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
    """Each voice's parameter array matches the C source initialiser."""
    expected = _parse_voice(name)
    assert py_voice == expected


def test_all_voices_have_33_entries() -> None:
    """Every modern voice initialises 33 of the 39 SPDEF fields (rest zero)."""
    expected_len = 33
    for _name, voice in _VOICES:
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
    voice_map = dict(_VOICES)
    for name, sex in expected.items():
        assert voice_map[name][0] == sex, f"{name} should be sex={sex}"


def test_voices_tuple_indexed_by_speaker_id() -> None:
    """``vd.voices[i]`` matches the i-th voice (matches voice_names order)."""
    assert vd.voices[0] is vd.voice_paul
    assert vd.voices[1] is vd.voice_chris
    assert vd.voices[2] is vd.voice_betty


def test_paul_pitch_is_average() -> None:
    """Paul (the reference voice) has AP=100 Hz."""
    expected_ap = 100
    ap_index = 3
    assert vd.voice_paul[ap_index] == expected_ap


def test_kit_pitch_is_higher_than_paul() -> None:
    """Kit the Kid has a higher pitch than Perfect Paul."""
    ap_index = 3
    assert vd.voice_kit[ap_index] > vd.voice_paul[ap_index]


def test_dennis_assertiveness_high() -> None:
    """Doctor Dennis is assertive — AS (field 2) at full 100."""
    expected_as = 100
    as_index = 2
    assert vd.voice_dennis[as_index] == expected_as
