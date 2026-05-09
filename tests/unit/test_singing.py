"""Tests for the singing-mode parser and renderer."""

from __future__ import annotations

import math

import numpy as np

from dectalk.api import sing
from dectalk.ph.singing import SingingNote, parse_singing, tone_to_hz


def test_parse_plain_phoneme_token() -> None:
    """Tokens without a <dur,tone> suffix should leave both overrides as None."""
    notes = parse_singing("HH AH")
    assert notes == [SingingNote(code="HH"), SingingNote(code="AH")]


def test_parse_singing_token_extracts_duration_and_tone() -> None:
    notes = parse_singing("HH<200,5> AH<300,7>")
    assert notes[0].code == "HH"
    assert notes[0].duration_ms == 200
    assert notes[0].pitch_hz is not None
    assert notes[1].duration_ms == 300


def test_tone_1_is_a2() -> None:
    """Per the documented base, tone 1 should be 110 Hz."""
    assert math.isclose(tone_to_hz(1), 110.0)


def test_tone_13_is_a3() -> None:
    """Twelve semitones up from A2 = A3 = 220 Hz."""
    assert math.isclose(tone_to_hz(13), 220.0, rel_tol=1e-6)


def test_sing_returns_int16_samples() -> None:
    samples = sing("HH<150,5> AH<150,7> L<150,8> OW<300,9>")
    assert samples.dtype == np.int16
    assert samples.size > 0


def test_sing_duration_overrides_default() -> None:
    """The total duration should reflect the explicit ms in the tokens."""
    short = sing("AH<100,5>")
    long_note = sing("AH<400,5>")
    assert long_note.size > short.size


def test_mixed_singing_and_plain_tokens() -> None:
    """Plain tokens should mix with singing tokens without raising."""
    samples = sing("HH AH<200,5> L OW<200,8>")
    assert samples.size > 0
