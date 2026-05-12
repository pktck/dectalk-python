"""Verify ``syllable_cannot_take_stress`` parity with ls_adju.c."""

from __future__ import annotations

import pytest

from dectalk.include.phoneme_codes import USPhoneme
from dectalk.lts.phone_list import ls_rule_add_phone
from dectalk.lts.phone_predicates import ls_adju_is_cons
from dectalk.lts.structs import Phone
from dectalk.lts.unstressed_check import syllable_cannot_take_stress


def _build_chain(sphones: list[int]) -> Phone:
    """Build a doubly-linked PHONE chain and return its head."""
    plist: list[Phone] = []
    for sphone in reversed(sphones):
        ls_rule_add_phone(plist, sph=sphone, uph=sphone)
    return plist[0]


def _consonant() -> int:
    """Return a known consonant code (B), or skip if pfeat disagrees."""
    b = int(USPhoneme.B)
    if not ls_adju_is_cons(b):
        pytest.skip("USPhoneme.B is not flagged as consonant in pfeat")
    return b


def test_syllable_ending_in_el_cannot_take_stress() -> None:
    """A syllable ending on ``[L]`` (US_EL) cannot bear primary stress."""
    el = int(USPhoneme.EL)
    b = _consonant()
    head = _build_chain([b, el])  # CL  e.g. 'b-l' as in "table"
    assert syllable_cannot_take_stress(head) is True


def test_syllable_ending_in_other_vowel_can_take_stress() -> None:
    """A syllable ending on a normal vowel (e.g. AA) can take stress."""
    aa = int(USPhoneme.AA)
    b = _consonant()
    head = _build_chain([b, aa])
    assert syllable_cannot_take_stress(head) is False


def test_syllable_with_no_consonants() -> None:
    """A vowel-only syllable: check the vowel directly."""
    el = int(USPhoneme.EL)
    head = _build_chain([el])
    assert syllable_cannot_take_stress(head) is True


def test_long_onset_with_el_terminator() -> None:
    """Multi-consonant onset followed by [L] still cannot take stress."""
    b = _consonant()
    el = int(USPhoneme.EL)
    head = _build_chain([b, b, b, el])  # CCCL
    assert syllable_cannot_take_stress(head) is True
