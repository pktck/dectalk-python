"""Verify ``ls_proc_do_time`` parity with l_us_pr1.c."""

from __future__ import annotations

from dectalk.include.phoneme_codes import VPSTART, WBOUND
from dectalk.lts.emitter import LtsEmitter
from dectalk.lts.time_emit import ls_proc_do_time


def test_simple_d_dd() -> None:
    """``1:23`` emits ``one`` VPSTART ``twenty-three``."""
    e = LtsEmitter()
    ls_proc_do_time(e, b"1:23")
    assert len(e.phones) > 0
    assert VPSTART in e.phones


def test_two_digit_hours_dd_dd() -> None:
    """``12:34`` emits ``twelve`` VPSTART ``thirty-four``."""
    e = LtsEmitter()
    ls_proc_do_time(e, b"12:34")
    assert VPSTART in e.phones


def test_round_minutes_skipped() -> None:
    """``12:00`` skips emitting the minutes (no '0 0' word)."""
    e = LtsEmitter()
    ls_proc_do_time(e, b"12:00")
    # Should contain exactly one VPSTART (the separator) but no
    # 2-digit minute phonemes after it.
    assert e.phones.count(VPSTART) == 1


def test_with_seconds() -> None:
    """``12:34:56`` emits 3 number groups with VPSTART separators."""
    e = LtsEmitter()
    ls_proc_do_time(e, b"12:34:56")
    # Two VPSTART separators (after hours, after minutes).
    assert e.phones.count(VPSTART) == 2


def test_with_fractional_seconds() -> None:
    """``12:34.5`` emits the minutes then 'point five'."""
    e = LtsEmitter()
    ls_proc_do_time(e, b"12:34.5")
    # WBOUND appears before 'point' and before each fractional digit.
    assert WBOUND in e.phones


def test_short_input_no_emit() -> None:
    """Inputs shorter than D:DD emit nothing."""
    e = LtsEmitter()
    ls_proc_do_time(e, b"1:2")
    assert e.phones == []
