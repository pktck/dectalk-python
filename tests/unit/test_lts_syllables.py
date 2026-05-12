"""Verify ``ls_adju_sylables`` syllable-boundary placement.

Builds small PHONE-list fixtures and checks that PFSYLAB and
PFLEFTC flags land in the expected positions after the function
runs.
"""

from __future__ import annotations

import pytest

from dectalk.include.phoneme_codes import USPhoneme
from dectalk.lts.phone_list import SNONE, ls_rule_add_phone
from dectalk.lts.phone_predicates import ls_adju_is_cons
from dectalk.lts.structs import PFLEFTC, PFSYLAB, Phone
from dectalk.lts.syllables import ls_adju_sylables


def _build_chain(sphone_seq: list[int]) -> tuple[Phone, list[Phone]]:
    """Build a doubly-linked PHONE chain from a sequence of sphones."""
    plist: list[Phone] = []
    # ls_rule_add_phone prepends, so iterate in reverse to get the
    # final order matching the input sequence.
    for sphone in reversed(sphone_seq):
        ls_rule_add_phone(plist, sph=sphone, uph=sphone)
    return plist[0], plist


def _skip_if_b_not_consonant() -> None:
    """Pre-condition guard for tests that rely on US.B being a consonant."""
    if not ls_adju_is_cons(int(USPhoneme.B)):
        pytest.skip("USPhoneme.B is not flagged as consonant in pfeat")


def test_single_vowel_no_syllable_marker() -> None:
    """A word with one PHONE and no PFSYLAB is unchanged.

    The C function walks until it finds a PFSYLAB; without one,
    the outer ``while`` returns early.
    """
    head, _ = _build_chain([10])
    head.p_stress = 1
    ls_adju_sylables(head, None)
    assert head.p_flag == 0
    assert head.p_stress == 1


def test_vc_split_basic_syllabification() -> None:
    """A VCV sequence with PFSYLAB on the second vowel.

    Algorithm walks back from the PFSYLAB vowel through the
    consonant cluster. With AA-B-AA (PFSYLAB on the last AA), the
    walk reaches fpp via the cluster, so the new PFSYLAB lands on
    plist[0] and the consonant traversal sets PFLEFTC on plist[0]
    too. plist[2]'s original PFSYLAB is preserved on this path
    (the C source only clears it via the gdansk-inner branch).
    """
    _skip_if_b_not_consonant()
    aa = int(USPhoneme.AA)
    b = int(USPhoneme.B)

    head, plist = _build_chain([aa, b, aa])
    plist[2].p_flag |= PFSYLAB

    ls_adju_sylables(head, None)

    # New PFSYLAB lands at plist[0] (start of word).
    assert plist[0].p_flag & PFSYLAB
    # plist[2]'s original PFSYLAB is preserved by this code path.
    assert plist[2].p_flag & PFSYLAB


def test_function_returns_none() -> None:
    """The function mutates in place; return value is None."""
    head, _ = _build_chain([5, 10, 15])
    result = ls_adju_sylables(head, None)
    assert result is None


def test_no_pfsylab_no_changes() -> None:
    """Without any PFSYLAB marker, no PFLEFTC bits are set."""
    head, plist = _build_chain([5, 10, 15])
    ls_adju_sylables(head, None)
    for p in plist:
        assert (p.p_flag & PFLEFTC) == 0


def test_initial_pfsylab_stress_is_preserved() -> None:
    """Stress originally on the PFSYLAB vowel is NOT moved by the inner loop.

    The C algorithm only transfers stress from consonants it walks
    back through, not from the starting (PFSYLAB-marked) vowel. With
    AA-B-AA(stress=3, PFSYLAB), the starting vowel's stress stays
    where it is.
    """
    _skip_if_b_not_consonant()
    aa = int(USPhoneme.AA)
    b = int(USPhoneme.B)

    head, plist = _build_chain([aa, b, aa])
    plist[2].p_flag |= PFSYLAB
    plist[2].p_stress = 3

    ls_adju_sylables(head, None)

    # Stress on the starting (PFSYLAB) vowel is preserved.
    assert plist[2].p_stress == 3
    # Stress is set on the new PFSYLAB target (plist[0]) — SNONE
    # because no consonant in the walk had non-SNONE stress.
    assert plist[0].p_stress == SNONE
