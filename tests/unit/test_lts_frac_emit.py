"""Verify ``ls_proc_do_frac`` parity with l_us_pr1.c."""

from __future__ import annotations

from dectalk.include.phoneme_codes import WBOUND, USPhoneme
from dectalk.lts.emitter import LtsEmitter
from dectalk.lts.frac_emit import ls_proc_do_frac
from dectalk.lts.phone_list import iter_phone_list_until_sil
from dectalk.lts.phoneme_words import phalf, phalves, ppercent


def test_one_half() -> None:
    """``1/2`` emits 'one half' (singular)."""
    e = LtsEmitter()
    ls_proc_do_frac(e, b"1/2")
    expected_half = iter_phone_list_until_sil(phalf)
    # Half appears at the end.
    assert e.phones[-len(expected_half) :] == expected_half


def test_three_halves() -> None:
    """``3/2`` emits 'three halves' (plural — 3 > 1)."""
    e = LtsEmitter()
    ls_proc_do_frac(e, b"3/2")
    expected_halves = iter_phone_list_until_sil(phalves)
    assert e.phones[-len(expected_halves) :] == expected_halves


def test_one_fourth() -> None:
    """``1/4`` emits 'one fourth' (singular: no plural S)."""
    e = LtsEmitter()
    ls_proc_do_frac(e, b"1/4")
    # Singular — should NOT end with S phoneme.
    assert e.phones[-1] != int(USPhoneme.S)


def test_three_fourths_plural_s() -> None:
    """``3/4`` emits 'three fourths' (plural: ends with S)."""
    e = LtsEmitter()
    ls_proc_do_frac(e, b"3/4")
    assert e.phones[-1] == int(USPhoneme.S)


def test_two_thirds_plural_z() -> None:
    """``2/3`` emits 'two thirds' (plural: ends with Z, since '3' uses Z)."""
    e = LtsEmitter()
    ls_proc_do_frac(e, b"2/3")
    assert e.phones[-1] == int(USPhoneme.Z)


def test_percent_appended() -> None:
    """``50/100%`` ends with the percent token."""
    e = LtsEmitter()
    ls_proc_do_frac(e, b"50/100%")
    expected_pct = iter_phone_list_until_sil(ppercent)
    # ppercent starts with WBOUND, so use [WBOUND, ...] subsearch.
    joined = bytes(e.phones)
    assert bytes(expected_pct) in joined


def test_wbound_between_num_denom() -> None:
    """A WBOUND separates the numerator from the denominator."""
    e = LtsEmitter()
    ls_proc_do_frac(e, b"1/4")
    assert WBOUND in e.phones


def test_no_slash_no_emit() -> None:
    """No '/' present — nothing emitted."""
    e = LtsEmitter()
    ls_proc_do_frac(e, b"abc")
    assert e.phones == []
