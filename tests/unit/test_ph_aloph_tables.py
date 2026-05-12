"""Verify the hphone / sphone allophone-emission tables match ph_aloph2.c."""

from __future__ import annotations

from dectalk.include.phoneme_codes import HAT_FALL, HAT_RF, HAT_RISE, S1, S2, SEMPH
from dectalk.ph.aloph_tables import hphone, sphone
from dectalk.ph.utterance_constants import GEN_SIL


def test_hphone_layout() -> None:
    """4 entries, in C-source order: SIL, RISE, FALL, RF."""
    assert hphone == (GEN_SIL, HAT_RISE, HAT_FALL, HAT_RF)


def test_sphone_layout() -> None:
    """4 entries, in C-source order: SIL, S1, S2, SEMPH."""
    assert sphone == (GEN_SIL, S1, S2, SEMPH)


def test_zero_index_is_silence_for_both() -> None:
    """Index 0 is the no-boundary filler ``GEN_SIL`` in both tables."""
    assert hphone[0] == GEN_SIL
    assert sphone[0] == GEN_SIL
