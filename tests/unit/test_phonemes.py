"""Unit tests for the ARPABET phoneme inventory."""

from __future__ import annotations

import pytest

from dectalk.include.phonemes import PHONEMES, PhonemeKind, get_phoneme


def test_inventory_covers_canonical_arpabet() -> None:
    """Spot-check that the major English phoneme classes are present."""
    expected_codes = {
        # Vowels
        "AA",
        "AE",
        "AH",
        "AO",
        "EH",
        "ER",
        "IH",
        "IY",
        "UH",
        "UW",
        "AX",
        # Diphthongs
        "AY",
        "AW",
        "EY",
        "OW",
        "OY",
        # Stops
        "P",
        "B",
        "T",
        "D",
        "K",
        "G",
        # Fricatives
        "F",
        "V",
        "TH",
        "DH",
        "S",
        "Z",
        "SH",
        "ZH",
        "HH",
        # Affricates
        "CH",
        "JH",
        # Nasals
        "M",
        "N",
        "NG",
        # Liquids
        "L",
        "R",
        # Glides
        "W",
        "Y",
        # Silence
        "SIL",
    }
    assert expected_codes <= set(PHONEMES.keys())


def test_get_phoneme_strips_stress_digits() -> None:
    a = get_phoneme("AH")
    assert get_phoneme("AH0") is a
    assert get_phoneme("AH1") is a
    assert get_phoneme("AH2") is a


def test_get_phoneme_is_case_insensitive() -> None:
    assert get_phoneme("ah") is get_phoneme("AH")


def test_get_phoneme_raises_for_unknown() -> None:
    with pytest.raises(KeyError):
        get_phoneme("XX")


def test_voiced_classification() -> None:
    assert get_phoneme("AH").voiced is True  # vowel
    assert get_phoneme("M").voiced is True  # nasal
    assert get_phoneme("S").voiced is False  # voiceless fricative
    assert get_phoneme("Z").voiced is True  # voiced fricative
    assert get_phoneme("HH").voiced is False  # /h/


def test_durations_are_positive() -> None:
    for p in PHONEMES.values():
        assert p.duration_ms > 0


def test_kind_classification() -> None:
    assert get_phoneme("AH").kind is PhonemeKind.VOWEL
    assert get_phoneme("AY").kind is PhonemeKind.DIPHTHONG
    assert get_phoneme("P").kind is PhonemeKind.STOP
    assert get_phoneme("S").kind is PhonemeKind.FRICATIVE
    assert get_phoneme("CH").kind is PhonemeKind.AFFRICATE
    assert get_phoneme("M").kind is PhonemeKind.NASAL
    assert get_phoneme("L").kind is PhonemeKind.LIQUID
    assert get_phoneme("W").kind is PhonemeKind.GLIDE
    assert get_phoneme("SIL").kind is PhonemeKind.SILENCE
