"""Verify the state-mutating ``ls_proc_do_*`` emit wrappers."""

from __future__ import annotations

from dectalk.include.phoneme_codes import WBOUND
from dectalk.lts.emitter import LtsEmitter
from dectalk.lts.phone_list import iter_phone_list_until_sil
from dectalk.lts.phoneme_words import p11, pminus, pplus
from dectalk.lts.proc_emit import (
    ls_proc_do_2_digits,
    ls_proc_do_3_digits,
    ls_proc_do_4_digits,
    ls_proc_do_sign,
)


def test_do_sign_minus_emits_pminus_plus_wbound() -> None:
    """``-`` emits pminus followed by WBOUND."""
    e = LtsEmitter()
    matched = ls_proc_do_sign(e, ord("-"))
    assert matched is True
    expected = [*iter_phone_list_until_sil(pminus), WBOUND]
    assert e.phones == expected
    assert e.lphone == WBOUND


def test_do_sign_plus_emits_pplus_plus_wbound() -> None:
    """``+`` emits pplus followed by WBOUND."""
    e = LtsEmitter()
    matched = ls_proc_do_sign(e, ord("+"))
    assert matched is True
    expected = [*iter_phone_list_until_sil(pplus), WBOUND]
    assert e.phones == expected


def test_do_sign_unknown_returns_false_no_emit() -> None:
    """An unknown sign returns False and emits nothing."""
    e = LtsEmitter()
    matched = ls_proc_do_sign(e, ord("$"))
    assert matched is False
    assert e.phones == []


def test_do_2_digits_eleven_emits_p11() -> None:
    """``11`` emits the p11 phoneme list."""
    e = LtsEmitter()
    ls_proc_do_2_digits(e, 1, 1)
    assert e.phones == list(iter_phone_list_until_sil(p11))


def test_do_2_digits_zero_emits_nothing() -> None:
    """``0X`` (leading zero) emits nothing — caller spells the digits."""
    e = LtsEmitter()
    ls_proc_do_2_digits(e, 0, 5)
    assert e.phones == []


def test_do_3_digits_two_hundred() -> None:
    """``200`` emits the three-hundred form."""
    e = LtsEmitter()
    ls_proc_do_3_digits(e, 2, 0, 0)
    assert len(e.phones) > 0
    assert WBOUND in e.phones


def test_do_4_digits_thousand_round() -> None:
    """``5000`` emits ``five thousand`` form."""
    e = LtsEmitter()
    ls_proc_do_4_digits(e, 5, 0, 0, 0)
    assert len(e.phones) > 0
    assert WBOUND in e.phones


def test_emitter_chaining() -> None:
    """Multiple do_* calls in sequence accumulate correctly."""
    e = LtsEmitter()
    ls_proc_do_sign(e, ord("-"))
    initial_len = len(e.phones)
    ls_proc_do_2_digits(e, 4, 2)
    # The post-do_2_digits phones list contains everything from
    # do_sign plus the 42-phonemes.
    assert len(e.phones) > initial_len
