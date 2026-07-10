"""Verify remaining_stresses_til matches the active ph_aloph1.c variant.

The active ``#ifndef ENGLISH_UK`` body counts **primary** stresses only
(``FSTRESS_1``); the ph_aloph2.c/UK variant this suite previously
pinned counts any ``FSTRESS`` — the wrong-variant port mistimed the
clause-final hat fall whenever a secondary stress trailed the last
primary (issue #297).
"""

from __future__ import annotations

from dectalk.include.phoneme_codes import PFUSA, USPhoneme
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import FCBNEXT, FNOSTRESS, FSTRESS_1, FSTRESS_2
from dectalk.ph.remaining_stresses_til import remaining_stresses_til


def _us(code: int | USPhoneme) -> int:
    """Build a font-encoded US phoneme code."""
    return (PFUSA << 8) | int(code)


def test_empty_state_returns_zero() -> None:
    """A DphT with phonemes / sentstruc unset returns 0."""
    state = DphT()
    assert remaining_stresses_til(state, 0, FCBNEXT) == 0


def test_no_stressed_syllables_returns_zero() -> None:
    """An array of unstressed phonemes counts zero."""
    state = DphT()
    state.phonemes = [_us(USPhoneme.IY)] * 5
    state.sentstruc = [FNOSTRESS] * 5
    state.nphonetot = 5
    assert remaining_stresses_til(state, 0, FCBNEXT) == 0


def test_skips_msym_itself() -> None:
    """``msym`` is excluded from the count even if stressed."""
    state = DphT()
    state.phonemes = [_us(USPhoneme.IY), _us(USPhoneme.IY)]
    state.sentstruc = [FSTRESS_1, FSTRESS_1]
    state.nphonetot = 2
    # msym=0 with FSTRESS_1, but skip msym itself → count msym=1 only.
    count = remaining_stresses_til(state, 0, FCBNEXT)
    assert count == 1  # IY at index 1 is syllabic.


def test_boundary_stops_walk() -> None:
    """``FCBNEXT`` boundary halts further counting."""
    state = DphT()
    state.phonemes = [_us(USPhoneme.IY)] * 5
    # Indices 1, 3 stressed; index 2 carries clause-comma boundary.
    state.sentstruc = [FNOSTRESS, FSTRESS_1, FCBNEXT, FSTRESS_1, FSTRESS_1]
    state.nphonetot = 5
    # From msym=0: index 1 counted (1 stressed), index 2 hits boundary.
    count = remaining_stresses_til(state, 0, FCBNEXT)
    assert count == 1


def test_secondary_stress_does_not_count() -> None:
    """FSTRESS_2-only syllables are excluded by the FSTRESS_1 mask.

    The active ph_aloph1.c body masks with ``FSTRESS_1``; a trailing
    secondary stress (e.g. ``down`` in ``listen down``) must NOT hold
    the hat open past the last primary stress (issue #297).
    """
    state = DphT()
    state.phonemes = [_us(USPhoneme.IY), _us(USPhoneme.IY)]
    state.sentstruc = [FNOSTRESS, FSTRESS_2]
    state.nphonetot = 2
    assert remaining_stresses_til(state, 0, FCBNEXT) == 0


def test_walks_to_end_when_no_boundary() -> None:
    """If no boundary or GEN_SIL, walks the full sentstruc.

    Only the two FSTRESS_1 entries count; the FSTRESS_2 entry is
    excluded by the active primary-only mask.
    """
    state = DphT()
    state.phonemes = [_us(USPhoneme.IY)] * 4
    state.sentstruc = [FNOSTRESS, FSTRESS_1, FSTRESS_2, FSTRESS_1]
    state.nphonetot = 4
    assert remaining_stresses_til(state, 0, FCBNEXT) == 2
