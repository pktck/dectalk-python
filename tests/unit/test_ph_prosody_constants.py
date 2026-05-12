"""Verify the US English prosody constants match ph_defs.h.

Re-parses the ``#ifdef ENGLISH_US`` block of
``src/dapi/src/ph/ph_defs.h`` and asserts each ``#define`` matches
our Python literal.

Skips when ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.ph import prosody_constants as pc

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / ("src/dapi/src/ph/ph_defs.h")

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _parse_us_block() -> dict[str, int]:
    """Parse #define lines inside the ENGLISH_US block of ph_defs.h.

    Returns a dict of name → resolved int value. Handles simple
    arithmetic like ``281-100``. For ``MAX_NRISES`` (gated by inner
    VOICE_ROM_BETA5), picks the BETA5 branch (7).
    """
    text = _C_FILE.read_text(encoding="latin-1")
    # Find the ENGLISH_US block that contains F0_QGesture1. The outer
    # #ifdef ENGLISH_US wraps an inner #if/#elif/#endif for VOICE_ROM_*.
    # Non-greedy ``#endif`` would stop at the inner one, so we slice
    # from "#ifdef ENGLISH_US" containing F0_QGesture1 up to the next
    # "#ifdef FRENCH" / "#ifdef ENGLISH_UK" marker.
    start_pat = re.compile(r"#ifdef\s+ENGLISH_US\s*\n")
    end_pat = re.compile(r"#ifdef\s+(FRENCH|ENGLISH_UK|SPANISH)\b")
    body = None
    for m in start_pat.finditer(text):
        next_marker = end_pat.search(text, m.end())
        candidate = text[m.end() : next_marker.start() if next_marker else len(text)]
        if "F0_QGesture1" in candidate:
            body = candidate
            break
    assert body is not None
    # Strip block comments
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    # Drop the VOICE_ROM #if/#elif/#else/#endif inner block, keeping the
    # BETA5 branch (#define MAX_NRISES 7).
    body = re.sub(
        r"#if\s+defined\(VOICE_ROM_1996\).*?#elif\s+defined\(VOICE_ROM_BETA5\)\s*"
        r"(#define\s+MAX_NRISES\s+\d+).*?#endif",
        r"\1",
        body,
        count=1,
        flags=re.DOTALL,
    )
    out: dict[str, int] = {}
    for m in re.finditer(r"#define\s+(\w+)\s+([^/\n]+?)\s*$", body, re.MULTILINE):
        name = m.group(1)
        expr = m.group(2).strip()
        try:
            out[name] = int(eval(expr))
        except (NameError, SyntaxError, TypeError):
            # Skip defines referring to undefined symbols (USP_*, etc.).
            continue
    return out


_NUMERIC_CONSTANTS: tuple[str, ...] = (
    "F0_QGesture1", "F0_QGesture2", "F0_CGesture1", "F0_CGesture2",
    "GEST_SHIFT", "MAX_NRISES", "F0_FINAL_FALL", "F0_NON_FINAL_FALL",
    "F0_COMMA_FALL", "F0_QSYLL_FALL", "F0_GLOTTALIZE", "Reduce_last",
)  # fmt: skip


@pytest.mark.parametrize("name", _NUMERIC_CONSTANTS)
def test_prosody_constant_matches_c(name: str) -> None:
    """Each numeric prosody constant matches the C source."""
    defs = _parse_us_block()
    assert name in defs, f"missing #define {name}"
    assert getattr(pc, name) == defs[name]


def test_max_nrises_is_beta5_branch() -> None:
    """MAX_NRISES = 7 because the build uses VOICE_ROM_BETA5 (p_us_rom.c)."""
    expected = 7
    assert expected == pc.MAX_NRISES


def test_qgesture_positive() -> None:
    """Question-mode F0 rises are positive (going up at end of question)."""
    assert pc.F0_QGesture1 > 0
    assert pc.F0_QGesture2 > pc.F0_QGesture1


def test_glottalize_is_negative() -> None:
    """Glottalisation drops F0 — sign is negative."""
    assert pc.F0_GLOTTALIZE < 0


def test_final_fall_largest_in_declarative() -> None:
    """Final-fall is larger than non-final and comma falls."""
    assert pc.F0_FINAL_FALL > pc.F0_NON_FINAL_FALL
    assert pc.F0_FINAL_FALL > pc.F0_COMMA_FALL


def test_f0_command_types() -> None:
    """USER..SHORTIMPULSE: seven F0 command type codes 0..6."""
    assert pc.USER == 0
    assert pc.IMPULSE == 1
    assert pc.STEP == 2
    assert pc.F0_RESET == 3
    assert pc.GLOTTAL == 4
    assert pc.GLIDE == 5
    assert pc.SHORTIMPULSE == 6
    # Dense 0..6.
    cmds = {pc.USER, pc.IMPULSE, pc.STEP, pc.F0_RESET, pc.GLOTTAL, pc.GLIDE, pc.SHORTIMPULSE}
    assert cmds == set(range(7))


def test_clause_type_codes() -> None:
    """Four clause types: DECLARATIVE=0, COMMACLAUSE=1, EXCLAIMCLAUSE=2, QUESTION=3."""
    assert pc.DECLARATIVE == 0
    assert pc.COMMACLAUSE == 1
    assert pc.EXCLAIMCLAUSE == 2
    assert pc.QUESTION == 3


def test_f0_cbound_pulse() -> None:
    """``F0_CBOUND_PULSE`` matches ph_defs.h (700 for US/UK/SP)."""
    assert pc.F0_CBOUND_PULSE == 700


def test_nasal_zero_defaults() -> None:
    """Three nasal-zero defaults from ph_defs.h."""
    assert pc.NON_NASAL_ZERO == 290
    assert pc.NASAL_ZERO_BOUNDARY == 370
    assert pc.NASAL_ZERO_CONS == 400
