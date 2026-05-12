"""Verify geminate-deletion parity with l_us_ru1.c / ls_adju.c."""

from __future__ import annotations

import pytest

from dectalk.include.phoneme_codes import USPhoneme
from dectalk.lts.geminate import (
    ls_adju_del_phone,
    ls_adju_delgemphone,
    ls_adju_ins_phone,
    ls_adju_is_obs,
    ls_rule_delete_geminate_pairs,
)
from dectalk.lts.phone_list import SNONE, ls_rule_add_phone
from dectalk.lts.phone_predicates import ls_adju_is_cons
from dectalk.lts.structs import PFMORPH, Phone


def _build_chain(sphones: list[int]) -> list[Phone]:
    """Build a doubly-linked PHONE chain from ``sphones`` in forward order."""
    plist: list[Phone] = []
    for sphone in reversed(sphones):
        ls_rule_add_phone(plist, sph=sphone, uph=sphone)
    return plist


def _consonant() -> int:
    """Return a known consonant code (B), or skip if pfeat disagrees."""
    b = int(USPhoneme.B)
    if not ls_adju_is_cons(b):
        pytest.skip("USPhoneme.B is not flagged as consonant in pfeat")
    return b


def test_del_phone_unlinks_node() -> None:
    """Removing a middle PHONE re-wires its neighbours."""
    plist = _build_chain([1, 2, 3])
    head, mid, tail = plist
    ls_adju_del_phone(plist, mid)
    assert mid not in plist
    # head's forward link now points at tail.
    assert head.p_fp is tail
    assert tail.p_bp is head


def test_del_phone_removes_head() -> None:
    """Removing the head PHONE makes the next one the new head."""
    plist = _build_chain([1, 2, 3])
    head, mid, _tail = plist
    ls_adju_del_phone(plist, head)
    assert plist[0] is mid
    assert mid.p_bp is None


def test_delgemphone_merges_flags_and_stress() -> None:
    """delgemphone overwrites sphone, ORs flags, takes stronger stress."""
    plist = _build_chain([1, 2])
    bp, pp = plist[0], plist[1]
    bp.p_flag = 0x01
    bp.p_stress = 3
    pp.p_flag = 0x04
    pp.p_stress = 1
    ls_adju_delgemphone(plist, pp, ph=99)
    # bp was deleted.
    assert bp not in plist
    # pp's sphone is now 99, flags OR'd, stress raised to bp's.
    assert pp.p_sphone == 99
    assert pp.p_flag == (0x01 | 0x04)
    assert pp.p_stress == 3


def test_delete_geminate_el_then_ll_preserves_el() -> None:
    """Forward ``EL`` → ``LL`` chain: pp1=LL with pp1.p_bp=EL → branch1 matches.

    The C source matches via ``ph1==US_LL && ph2==US_EL`` where
    ``ph2`` is the backward neighbour, so the forward chain is
    EL-LL (EL precedes LL). The collapsed PHONE keeps ``EL`` as
    the new ``p_sphone``.
    """
    plist = _build_chain([int(USPhoneme.EL), int(USPhoneme.LL)])
    ls_rule_delete_geminate_pairs(plist)
    assert len(plist) == 1
    assert plist[0].p_sphone == int(USPhoneme.EL)


def test_delete_geminate_ll_then_el_buggy_typo_preserves_pair() -> None:
    """C-source bug: ``ph1==EL && ph1==LL`` typo never matches.

    The symmetric ``LL`` → ``EL`` case (LL first, EL second) is NOT
    collapsed because the C source has a typo: the second branch
    checks ``ph1==US_LL`` instead of ``ph2==US_LL``. We preserve
    this behaviour for bit-for-bit binary parity.
    """
    plist = _build_chain([int(USPhoneme.LL), int(USPhoneme.EL)])
    ls_rule_delete_geminate_pairs(plist)
    # Both PHONEs survive because the buggy branch never fires.
    assert len(plist) == 2


def test_delete_geminate_t_th_within_morpheme() -> None:
    """``[t][T]`` collapses to ``[T]`` when not across a morpheme boundary."""
    plist = _build_chain([int(USPhoneme.T), int(USPhoneme.TH)])
    ls_rule_delete_geminate_pairs(plist)
    assert len(plist) == 1
    assert plist[0].p_sphone == int(USPhoneme.TH)


def test_delete_geminate_morpheme_boundary_blocks_t_th() -> None:
    """A PFMORPH bit on the second PHONE blocks the [t][T] collapse."""
    plist = _build_chain([int(USPhoneme.T), int(USPhoneme.TH)])
    plist[1].p_flag |= PFMORPH
    ls_rule_delete_geminate_pairs(plist)
    # Pair is preserved.
    assert len(plist) == 2


def test_delete_geminate_s_sh_within_morpheme() -> None:
    """``[s][S]`` collapses to ``[S]`` (Sh) when within a morpheme."""
    plist = _build_chain([int(USPhoneme.S), int(USPhoneme.SH)])
    ls_rule_delete_geminate_pairs(plist)
    assert len(plist) == 1
    assert plist[0].p_sphone == int(USPhoneme.SH)


def test_delete_geminate_identical_consonants() -> None:
    """Two identical consonants (e.g. [B][B]) collapse to one."""
    b = _consonant()
    plist = _build_chain([b, b])
    ls_rule_delete_geminate_pairs(plist)
    assert len(plist) == 1
    assert plist[0].p_sphone == b


def test_delete_geminate_non_consonant_pair_preserved() -> None:
    """Two identical vowels are NOT collapsed (only consonants are)."""
    aa = int(USPhoneme.AA)
    plist = _build_chain([aa, aa])
    ls_rule_delete_geminate_pairs(plist)
    assert len(plist) == 2


def test_delete_geminate_no_change_on_distinct_phones() -> None:
    """Distinct non-geminate phones are unchanged."""
    b = _consonant()
    aa = int(USPhoneme.AA)
    plist = _build_chain([b, aa, b])
    ls_rule_delete_geminate_pairs(plist)
    assert len(plist) == 3


# ---- ls_adju_ins_phone ----


def test_ins_phone_inserts_before_target() -> None:
    """ls_adju_ins_phone inserts a new PHONE before the given one."""
    plist = _build_chain([1, 2, 3])
    head, mid, tail = plist
    mid.p_flag = 0x0F  # flags will be forwarded to the new PHONE
    mid.p_stress = 5

    result = ls_adju_ins_phone(plist, mid, sph=99, uph=98, stress=7)
    assert result is True
    # Now the chain should be: head, new, mid, tail
    assert len(plist) == 4
    new = plist[1]
    assert new.p_sphone == 99
    assert new.p_uphone == 98
    assert new.p_stress == 7
    assert new.p_flag == 0x0F  # forwarded from mid
    # mid's flag and stress are cleared.
    assert mid.p_flag == 0
    assert mid.p_stress == SNONE
    # Linked-list pointers are correct.
    assert head.p_fp is new
    assert new.p_bp is head
    assert new.p_fp is mid
    assert mid.p_bp is new
    assert mid.p_fp is tail


# ---- ls_adju_is_obs ----


def test_is_obs_for_obstruent() -> None:
    """T (stop, obstruent) returns True."""
    assert ls_adju_is_obs(int(USPhoneme.T)) is True


def test_is_obs_for_vowel() -> None:
    """A vowel (e.g. AA) is not an obstruent."""
    assert ls_adju_is_obs(int(USPhoneme.AA)) is False
