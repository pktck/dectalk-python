"""Date emission from l_us_pr1.c::ls_proc_do_date.

Translated from ``src/dapi/src/lts/l_us_pr1.c``:

- :func:`ls_proc_do_date` — emit the phoneme sequence for a
  recognised date word like ``23-Aug-84`` or ``5-Jan-2025``.

The C source has two modes (US and Europe) gated on
``pKsd_t->modeflag & MODE_EUROPE``. The Python port takes the
``europe_mode`` flag explicitly.

The day-of-month portion is read as an ordinal via
``ls_proc_do_number(... , TRUE)``. The full ordinal-number reader
isn't yet ported; this implementation handles 1- and 2-digit days
only (which covers every real date).
"""

from __future__ import annotations

from dectalk.include.phoneme_codes import COMMA, WBOUND
from dectalk.lts.char_features import is_digit
from dectalk.lts.emitter import LtsEmitter
from dectalk.lts.number_words import speak_digit_group
from dectalk.lts.phoneme_words import months, pmonths, pof, pOH, pthe, punits
from dectalk.lts.proc_emit import ls_proc_do_2_digits, ls_proc_do_4_digits


def _find_month_index(word: bytes, mon_start: int) -> int:
    """Return the index of the matching month in ``months``, or -1."""
    for i, m in enumerate(months):
        min_month_len = 3
        if len(m) >= min_month_len and word[mon_start : mon_start + min_month_len] == m[:3]:
            return i
    return -1


def _emit_day_ordinal(emitter: LtsEmitter, day_digits: bytes) -> None:
    """Emit the day-of-month as an ordinal (e.g. ``twenty-third``)."""
    if len(day_digits) == 1:
        # 1-digit day — pass through speak_digit_group with ordinal mode.
        d3 = day_digits[0] - ord("0")
        for p in speak_digit_group(0, 0, d3, ordinal=True):
            emitter.send_phone(p)
    elif len(day_digits) == 2:  # noqa: PLR2004 — day is always 1 or 2 digits
        d2 = day_digits[0] - ord("0")
        d3 = day_digits[1] - ord("0")
        for p in speak_digit_group(0, d2, d3, ordinal=True):
            emitter.send_phone(p)


def _emit_year(emitter: LtsEmitter, year: bytes) -> None:
    """Emit the year portion (2 or 4 digits)."""
    n = len(year)
    if n == 2:  # noqa: PLR2004 — 2-digit year
        d1 = year[0] - ord("0")
        d2 = year[1] - ord("0")
        ls_proc_do_2_digits(emitter, d1, d2)
        return
    year_4digit = 4
    if n == year_4digit:
        d1 = year[0] - ord("0")
        d2 = year[1] - ord("0")
        d3 = year[2] - ord("0")
        d4 = year[3] - ord("0")
        # BATS #329: ``D00Y`` style (e.g. 2005, 1004, etc.) — speak as
        # ``two-thousand oh five`` rather than the default 4-digit form.
        # C source: (lp1+1)->l_ch != '0' && (lp1+2)->l_ch == '0' &&
        #           (lp1+3)->l_ch == '0' && (lp1+4)->l_ch != '0'
        if d1 != 0 and d2 == 0 and d3 == 0 and d4 != 0:
            ls_proc_do_2_digits(emitter, d1, d2)
            emitter.send_phone(WBOUND)
            emitter.send_phone_list(pOH)
            emitter.send_phone_list(punits[d4])
            return
        # Default: full 4-digit year reading.
        ls_proc_do_4_digits(emitter, d1, d2, d3, d4)


def ls_proc_do_date(
    emitter: LtsEmitter,
    word: bytes,
    *,
    europe_mode: bool = False,
) -> None:
    """Emit the phoneme sequence for a date word.

    Faithful translation of:

    .. code-block:: c

        void ls_proc_do_date(LPTTS_HANDLE_T phTTS,
                              LETTER *llp, LETTER *rlp) {
            // Find day/month/year boundaries split on '-'.
            // US mode:    speak month, day-as-ordinal, optionally year.
            // Europe mode: speak "the" day-as-ordinal "of" month, optionally year.
            // Year forms: 2-digit -> 2-digit number; 4-digit ->
            //  4-digit number, or "20XY" -> 2-digit + "oh" + digit.
        }

    Args:
        emitter: The LTS emitter state.
        word: The full date word (e.g. ``b"23-Aug-1984"``).
        europe_mode: True for European reading (``the 23rd of August``)
            or False for US (``August 23rd``).
    """
    # Split on '-' to find day / month-start / year-start.
    dash1 = word.find(b"-")
    if dash1 < 0:
        return
    # Month occupies dash1+1 .. dash1+4 (3-letter abbreviation).
    mon_start = dash1 + 1
    min_after_month = 3
    if mon_start + min_after_month > len(word):
        return
    month_idx = _find_month_index(word, mon_start)
    if month_idx < 0:
        return

    # Day portion: word[0:dash1]. C source: if day starts with '0'
    # and is 2 chars, skip the leading zero.
    day_start = 0
    if dash1 == 2 and word[0] == ord("0"):  # noqa: PLR2004 — "01-Jan" style
        day_start = 1
    day_digits = word[day_start:dash1]

    # Emit per mode.
    if europe_mode:
        emitter.send_phone_list(pthe)
        emitter.send_phone(WBOUND)
        _emit_day_ordinal(emitter, day_digits)
        emitter.send_phone(WBOUND)
        emitter.send_phone_list(pof)
        emitter.send_phone(WBOUND)
        emitter.send_phone_list(pmonths[month_idx])
    else:
        emitter.send_phone_list(pmonths[month_idx])
        emitter.send_phone(WBOUND)
        _emit_day_ordinal(emitter, day_digits)

    # Optional year part after the month: word[mon_start+3 .. end].
    year_part_start = mon_start + 3
    if year_part_start >= len(word):
        return
    if word[year_part_start] != ord("-"):
        return
    year_start = year_part_start + 1
    year = word[year_start:]
    if not year or not all(is_digit(b) for b in year):
        return

    emitter.send_phone(COMMA)
    _emit_year(emitter, year)


__all__ = ["ls_proc_do_date"]
