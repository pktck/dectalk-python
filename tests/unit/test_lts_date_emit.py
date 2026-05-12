"""Verify ``ls_proc_do_date`` parity with l_us_pr1.c."""

from __future__ import annotations

from dectalk.include.phoneme_codes import COMMA, WBOUND
from dectalk.lts.date_emit import ls_proc_do_date
from dectalk.lts.emitter import LtsEmitter
from dectalk.lts.phone_list import iter_phone_list_until_sil
from dectalk.lts.phoneme_words import pmonths, pof, pthe


def test_us_date_short_form() -> None:
    """``23-aug`` emits the month then day-ordinal."""
    e = LtsEmitter()
    ls_proc_do_date(e, b"23-aug")
    assert len(e.phones) > 0
    # First emission is the month bytes.
    aug = iter_phone_list_until_sil(pmonths[7])  # Aug is index 7
    assert e.phones[: len(aug)] == aug


def test_us_date_with_year() -> None:
    """``23-aug-84`` adds a COMMA then the year."""
    e = LtsEmitter()
    ls_proc_do_date(e, b"23-aug-84")
    assert COMMA in e.phones
    # The COMMA must appear after the date proper, before the year.
    comma_idx = e.phones.index(COMMA)
    # There should be more phones after the comma (the year).
    assert comma_idx < len(e.phones) - 1


def test_europe_date_form() -> None:
    """Europe mode emits 'the X of MONTH'."""
    e = LtsEmitter()
    ls_proc_do_date(e, b"23-aug", europe_mode=True)
    # Should contain the 'the' bytes and the 'of' bytes.
    the = iter_phone_list_until_sil(pthe)
    of = iter_phone_list_until_sil(pof)
    # Walk the result and check 'the' appears before 'of'.
    joined = bytes(e.phones)
    assert bytes(the) in joined
    assert bytes(of) in joined
    assert joined.index(bytes(the)) < joined.index(bytes(of))


def test_leading_zero_day_skipped() -> None:
    """``01-jan`` strips the leading 0 (per the C source's check)."""
    e = LtsEmitter()
    ls_proc_do_date(e, b"01-jan")
    # Result has the same length / structure as "1-jan".
    e2 = LtsEmitter()
    ls_proc_do_date(e2, b"1-jan")
    assert e.phones == e2.phones


def test_invalid_month_returns() -> None:
    """A non-3-letter-month abbreviation results in no emit."""
    e = LtsEmitter()
    ls_proc_do_date(e, b"23-xxx")
    assert e.phones == []


def test_no_dash_returns() -> None:
    """Input without a dash separator emits nothing."""
    e = LtsEmitter()
    ls_proc_do_date(e, b"hello")
    assert e.phones == []


def test_4_digit_year() -> None:
    """``23-aug-1984`` emits the full year."""
    e = LtsEmitter()
    ls_proc_do_date(e, b"23-aug-1984")
    assert COMMA in e.phones
    # The result has at least one WBOUND (separator before year).
    assert WBOUND in e.phones


def test_year_with_zero_pattern() -> None:
    """``1-jan-2005`` emits via the 20XY → 'two-oh-five' pattern."""
    from dectalk.lts.phoneme_words import pOH  # noqa: PLC0415

    e = LtsEmitter()
    ls_proc_do_date(e, b"1-jan-2005")
    # The pOH bytes must appear since we're in the 20X form.
    poh = iter_phone_list_until_sil(pOH)
    if poh:
        joined = bytes(e.phones)
        assert bytes(poh) in joined
