"""Unit tests for the phoneme → Klatt frame mapping."""

from __future__ import annotations

import pytest

from dectalk.ph.phoneme_frames import _VOWEL_FORMANTS, get_frames


def test_vowel_returns_single_frame() -> None:
    frames = get_frames("AH")
    assert len(frames) == 1
    f = frames[0]
    assert f.AV > 0
    assert f.F0 > 0
    assert _VOWEL_FORMANTS["AH"][0] == f.F1
    assert _VOWEL_FORMANTS["AH"][2] == f.F2


def test_diphthong_returns_two_frames() -> None:
    frames = get_frames("AY")
    assert len(frames) == 2
    # AY = AA -> IH; the start should have higher F1 than the end.
    assert frames[0].F1 > frames[1].F1


def test_voiceless_consonant_has_no_voicing() -> None:
    frames = get_frames("S")
    assert len(frames) == 1
    assert frames[0].AV == 0
    assert frames[0].Af > 0  # frication active


def test_voiced_consonant_has_voicing() -> None:
    frames = get_frames("Z")
    assert len(frames) == 1
    assert frames[0].AV > 0


def test_nasal_has_voicing_and_nasal_pole() -> None:
    frames = get_frames("M")
    assert frames[0].AV > 0
    assert frames[0].FNP > 0
    assert frames[0].FNZ > 0


def test_silence_returns_silent_frame() -> None:
    frames = get_frames("SIL")
    assert len(frames) == 1
    assert frames[0].F0 == 0
    assert frames[0].AV == 0


def test_stress_digits_are_stripped() -> None:
    a = get_frames("AH")
    b = get_frames("AH1")
    assert a == b


def test_unknown_phoneme_raises() -> None:
    with pytest.raises(KeyError):
        get_frames("XX")
