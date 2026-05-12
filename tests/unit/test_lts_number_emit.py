"""Verify ``ls_proc_do_number`` parity with l_us_pr1.c."""

from __future__ import annotations

from dectalk.include.phoneme_codes import WBOUND, USPhoneme
from dectalk.lts.emitter import LtsEmitter
from dectalk.lts.number_emit import ls_proc_do_number
from dectalk.lts.phone_list import iter_phone_list_until_sil
from dectalk.lts.phoneme_words import (
    pbillion,
    pmillion,
    pthousand,
    punits,
)


def test_single_digit() -> None:
    """``5`` reads as 'five' (units form)."""
    e = LtsEmitter()
    plural = ls_proc_do_number(e, b"5")
    expected = iter_phone_list_until_sil(punits[5])
    assert e.phones == expected
    assert plural is True


def test_one_singular() -> None:
    """``1`` is singular."""
    e = LtsEmitter()
    plural = ls_proc_do_number(e, b"1")
    assert plural is False


def test_zero() -> None:
    """``0`` reads as 'zero'."""
    e = LtsEmitter()
    ls_proc_do_number(e, b"0")
    expected = iter_phone_list_until_sil(punits[0])
    assert e.phones == expected


def test_one_thousand() -> None:
    """``1000`` emits 'one thousand'."""
    e = LtsEmitter()
    ls_proc_do_number(e, b"1000")
    # Should contain the thousand token.
    thousand_first = iter_phone_list_until_sil(pthousand)[0]
    assert thousand_first in e.phones


def test_one_million() -> None:
    """``1000000`` emits 'one million'."""
    e = LtsEmitter()
    ls_proc_do_number(e, b"1000000")
    million_first = iter_phone_list_until_sil(pmillion)[0]
    assert million_first in e.phones


def test_one_billion() -> None:
    """``1000000000`` emits 'one billion'."""
    e = LtsEmitter()
    ls_proc_do_number(e, b"1000000000")
    billion_first = iter_phone_list_until_sil(pbillion)[0]
    assert billion_first in e.phones


def test_ordinal_appends_th() -> None:
    """oflag=True appends US_TH at the end of a magnitude-only number."""
    e = LtsEmitter()
    ls_proc_do_number(e, b"1000", oflag=True)
    assert e.phones[-1] == int(USPhoneme.TH)


def test_complex_number_has_wbounds() -> None:
    """A multi-magnitude number has WBOUND between groups."""
    e = LtsEmitter()
    ls_proc_do_number(e, b"123456789")
    assert WBOUND in e.phones


def test_too_long_returns_false() -> None:
    """A number >18 digits returns False without emitting."""
    e = LtsEmitter()
    result = ls_proc_do_number(e, b"1" * 19)
    assert result is False
    assert e.phones == []


def test_non_digit_input_returns_false() -> None:
    """Non-digit input returns False without emitting."""
    e = LtsEmitter()
    result = ls_proc_do_number(e, b"abc")
    assert result is False
    assert e.phones == []
