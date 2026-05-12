"""Verify language-independent utterance / F0-command constants from ph_defs.h.

Re-parses the relevant ``#define`` directives in
``src/dapi/src/ph/ph_defs.h`` and asserts each Python literal matches.

Skips when ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.ph import utterance_constants as uc

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / ("src/dapi/src/ph/ph_defs.h")

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _parse_define(text: str, name: str) -> int:
    """Parse `#define NAME VALUE` returning the integer."""
    pat = rf"^#define\s+{re.escape(name)}\s+(.+?)\s*(?://|/\*|$)"
    m = re.search(pat, text, re.MULTILINE)
    assert m is not None, f"missing #define {name}"
    expr = m.group(1).strip()
    if expr.startswith("0x"):
        return int(expr, 16)
    return int(expr)


@pytest.mark.parametrize(
    "name",
    [
        "GEN_SIL",
        "DECLARATIVE",
        "COMMACLAUSE",
        "EXCLAIMCLAUSE",
        "QUESTION",
        "USER",
        "IMPULSE",
        "STEP",
        "F0_RESET",
        "GLOTTAL",
        "GLIDE",
        "SHORTIMPULSE",
        "F2max",
        "F3max",
        "NON_NASAL_ZERO",
        "NASAL_ZERO_BOUNDARY",
        "NASAL_ZERO_CONS",
    ],
)
def test_utterance_constant_matches_c(name: str) -> None:
    """Each utterance-type / F0-command / formant-limit constant matches the C source."""
    text = _C_FILE.read_text(encoding="latin-1")
    expected = _parse_define(text, name)
    assert getattr(uc, name) == expected


def test_utterance_type_codes_are_ordered() -> None:
    """The 4 utterance types are 0..3 in declarative order."""
    assert uc.DECLARATIVE == 0
    assert uc.COMMACLAUSE == 1
    assert uc.EXCLAIMCLAUSE == 2
    assert uc.QUESTION == 3


def test_f0_command_types_are_distinct() -> None:
    """The 7 F0-command type codes are pairwise distinct."""
    codes = {uc.USER, uc.IMPULSE, uc.STEP, uc.F0_RESET, uc.GLOTTAL, uc.GLIDE, uc.SHORTIMPULSE}
    expected_count = 7
    assert len(codes) == expected_count


def test_formant_clipping_limits_ordered() -> None:
    """F3max > F2max — F3 sits above F2 in the formant ladder."""
    assert uc.F3max > uc.F2max


def test_nasal_zeros_ordered() -> None:
    """Nasal zero targets ascend from non-nasal → boundary → consonant."""
    assert uc.NON_NASAL_ZERO < uc.NASAL_ZERO_BOUNDARY
    assert uc.NASAL_ZERO_BOUNDARY < uc.NASAL_ZERO_CONS


def test_gen_sil_is_pfusa_shifted() -> None:
    """GEN_SIL = PFUSA << 8 (the font-shifted silence marker)."""
    expected = 0x1E << 8
    assert expected == uc.GEN_SIL
