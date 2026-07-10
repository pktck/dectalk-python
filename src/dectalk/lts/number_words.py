"""Number-to-words helpers from l_us_pr1.c.

Translated from ``src/dapi/src/lts/l_us_pr1.c``:

- :func:`speak_2_digits` — return the phoneme sequence for a 2-digit
  number (00..99) with leading-zero spell behaviour.
- :func:`speak_3_digits` — return the phoneme sequence for a 3-digit
  number, handling the X00 → ``X hundred`` and XYY → ``X hundred YY``
  forms.

These are pure functions that return a flat list of phoneme codes
with embedded WBOUND separators. The C source emits via
``ls_util_send_phone_list``; the Python port lets callers route
the codes however they like.
"""

from __future__ import annotations

from dectalk.include.phoneme_codes import WBOUND, USPhoneme
from dectalk.lts.phone_list import iter_phone_list_until_sil
from dectalk.lts.phoneme_words import (
    pand,
    phundred,
    pordin,
    pteens,
    ptens,
    pthousand,
    punits,
)

_US_IX: int = int(USPhoneme.IX)
_US_TH: int = int(USPhoneme.TH)

_WBOUND: int = WBOUND


def _list_until_sil(byte_string: bytes) -> list[int]:
    """Return phoneme bytes up to (but not including) SIL."""
    return iter_phone_list_until_sil(byte_string)


def speak_2_digits(d1: int, d2: int) -> list[int] | None:
    """Return the phoneme sequence for a 2-digit number.

    Faithful translation of:

    .. code-block:: c

        void ls_proc_do_2_digits(LPTTS_HANDLE_T phTTS, LETTER *lp) {
            if (lp->l_ch == '0')
                ls_spel_spell(phTTS, lp, lp+2);   // spell each digit
            else if (lp->l_ch == '1')
                ls_util_send_phone_list(phTTS, pteens[(lp+1)->l_ch-'0']);
            else {
                ls_util_send_phone_list(phTTS, ptens[lp->l_ch-'0']);
                if ((lp+1)->l_ch != '0') {
                    ls_util_send_phone(phTTS, WBOUND);
                    ls_util_send_phone_list(phTTS, punits[(lp+1)->l_ch-'0']);
                }
            }
        }

    The Python port returns ``None`` for the leading-zero case
    (callers should fall back to spelling each digit individually
    via :func:`spell_or_say.say_it`).

    Args:
        d1: Tens digit (0..9).
        d2: Units digit (0..9).

    Returns:
        A list of phoneme codes, with WBOUND separating the
        tens-word from the units-word (e.g. ``twenty WBOUND one``).
        Returns ``None`` if ``d1 == 0`` (caller should spell).
    """
    if d1 == 0:
        return None
    if d1 == 1:
        return _list_until_sil(pteens[d2])
    # X2..X9 — use ptens[d1-2] for the tens word.
    out = _list_until_sil(ptens[d1 - 2])
    if d2 != 0:
        out.append(_WBOUND)
        out.extend(_list_until_sil(punits[d2]))
    return out


def speak_3_digits(d1: int, d2: int, d3: int) -> list[int] | None:
    """Return the phoneme sequence for a 3-digit number.

    Faithful translation of:

    .. code-block:: c

        void ls_proc_do_3_digits(LPTTS_HANDLE_T phTTS, LETTER *lp) {
            if (lp->l_ch == '0')
                ls_spel_spell(...);                  // spell each digit
            else {
                ls_util_send_phone_list(phTTS, upunits[lp->l_ch-'0']);
                ls_util_send_phone(phTTS, WBOUND);
                if ((lp+1)->l_ch=='0' && (lp+2)->l_ch=='0')
                    ls_util_send_phone_list(phTTS, phundred);
                else
                    ls_proc_do_2_digits(phTTS, lp+1);
            }
        }

    The C doc comment is explicit on the format:
    ``0XX → spell``, ``X00 → "X hundred"``, ``XYY → "X YY"``
    (note: XYY does NOT say "hundred and YY" — just "X YY").
    The "hundred and..." form lives in :func:`speak_digit_group`.

    Args:
        d1: Hundreds digit (0..9).
        d2: Tens digit (0..9).
        d3: Units digit (0..9).

    Returns:
        A list of phoneme codes. Returns ``None`` if ``d1 == 0``
        (caller should spell each digit).
    """
    if d1 == 0:
        return None
    # Stressed punits: the C source's upunits branch is guarded by
    # #if defined(HLSYN) || defined(CHANGES_AFTER_V43); the shipped
    # oracle binary defines neither (docs/PARITY-METHOD.md §3), so
    # the active variant is the stressed form.
    out = _list_until_sil(punits[d1])
    out.append(_WBOUND)
    if d2 == 0 and d3 == 0:
        # X00 → "X hundred"
        out.extend(_list_until_sil(phundred))
        return out
    # XYY → "X YY" (the 2-digit form handles leading-zero like 03 via spell)
    two = speak_2_digits(d2, d3)
    if two is not None:
        out.extend(two)
    return out


def speak_4_digits(d1: int, d2: int, d3: int, d4: int) -> list[int] | None:
    """Return the phoneme sequence for a 4-digit number.

    Faithful translation of:

    .. code-block:: c

        void ls_proc_do_4_digits(LPTTS_HANDLE_T phTTS, LETTER *lp) {
            if (lp->l_ch == '0')
                ls_spel_spell(...);                  // spell each digit
            else if ((lp+2)->l_ch=='0' && (lp+3)->l_ch=='0') {
                if ((lp+1)->l_ch == '0') {
                    // X000 — "X thousand"
                    ls_util_send_phone_list(phTTS, upunits[lp->l_ch-'0']);
                    ls_util_send_phone(phTTS, WBOUND);
                    ls_util_send_phone_list(phTTS, pthousand);
                } else {
                    // XY00 — "XY hundred"
                    ls_proc_do_2_digits(phTTS, lp);
                    ls_util_send_phone(phTTS, WBOUND);
                    ls_util_send_phone_list(phTTS, phundred);
                }
            } else {
                // XXYY — "XX YY" (year-style)
                ls_proc_do_2_digits(phTTS, lp+0);
                ls_util_send_phone(phTTS, WBOUND);
                ls_proc_do_2_digits(phTTS, lp+2);
            }
        }

    Three forms:

    * ``X000`` → ``punits[X] thousand``. The C source's ``upunits``
      variant is guarded by ``#if defined(HLSYN) ||
      defined(CHANGES_AFTER_V43)``; the shipped oracle binary defines
      neither, so the stressed ``punits`` branch is the active one
      (docs/PARITY-METHOD.md §3 — the binary wins).
    * ``XY00`` → ``2-digit(XY) hundred``.
    * ``XXYY`` → ``2-digit(XX) WBOUND 2-digit(YY)`` (year-style).

    Args:
        d1: Thousands digit (0..9).
        d2: Hundreds digit.
        d3: Tens digit.
        d4: Units digit.

    Returns:
        Phoneme code list, or ``None`` if ``d1 == 0`` (caller spells).
    """
    if d1 == 0:
        return None
    if d3 == 0 and d4 == 0:
        if d2 == 0:
            # X000 — "X thousand". Stressed punits — the binary has
            # no HLSYN/CHANGES_AFTER_V43, so upunits is dead code.
            out = list(iter_phone_list_until_sil(punits[d1]))
            out.append(_WBOUND)
            out.extend(iter_phone_list_until_sil(pthousand))
            return out
        # XY00 — "XY hundred"
        two = speak_2_digits(d1, d2)
        if two is None:
            return None
        out = list(two)
        out.append(_WBOUND)
        out.extend(iter_phone_list_until_sil(phundred))
        return out
    # XXYY — year-style: spoken as two 2-digit numbers
    top = speak_2_digits(d1, d2)
    bot = speak_2_digits(d3, d4)
    if top is None:
        return None
    out = list(top)
    out.append(_WBOUND)
    if bot is not None:
        out.extend(bot)
    return out


def speak_digit_group(d1: int, d2: int, d3: int, *, ordinal: bool = False) -> list[int]:
    """Return the phoneme sequence for a 3-digit group (000..999).

    Faithful translation of:

    .. code-block:: c

        void ls_proc_do_digit_group(LPTTS_HANDLE_T phTTS,
                                     unsigned char buf[3], int oflag) {
            if (buf[0] != '0') {
                ls_util_send_phone_list(phTTS, upunits[buf[0]-'0']);
                ls_util_send_phone(phTTS, WBOUND);
                ls_util_send_phone_list(phTTS, phundred);
                if (buf[1]=='0' && buf[2]=='0') {
                    if (oflag) ls_util_send_phone(phTTS, US_TH);
                    return;
                }
                ls_util_send_phone_list(phTTS, pand);
            }
            if (buf[1] == '1') {
                ls_util_send_phone_list(phTTS, pteens[buf[2]-'0']);
                if (oflag) ls_util_send_phone(phTTS, US_TH);
                return;
            }
            if (buf[1] != '0') {
                ls_util_send_phone_list(phTTS, ptens[buf[1]-'0']);
                if (buf[2] == '0') {
                    if (oflag) {
                        ls_util_send_phone(phTTS, US_IX);
                        ls_util_send_phone(phTTS, US_TH);
                    }
                    return;
                }
                ls_util_send_phone(phTTS, WBOUND);
            }
            if (oflag) ls_util_send_phone_list(phTTS, pordin[buf[2]-'0']);
            else       ls_util_send_phone_list(phTTS, punits[buf[2]-'0']);
        }

    Used for both bare 3-digit groups and as a building block for
    larger numbers (read in thousand/million groups).

    Args:
        d1: Hundreds digit (0..9).
        d2: Tens digit.
        d3: Units digit.
        ordinal: If True, render as an ordinal (``hundredth``,
            ``thirtieth``, ``second``, etc.).

    Returns:
        Phoneme code list. Always returns a list (never None) — the
        leading-zero case is handled by the caller upstream of
        ``do_digit_group``.
    """
    out: list[int] = []
    if d1 != 0:
        # Stressed punits: the C ``upunits`` alternative is inside
        # #if defined(HLSYN) || defined(CHANGES_AFTER_V43), which the
        # shipped oracle binary does not define ("one hundred" carries
        # S1 in convert_to_phonemes output for e.g. "103rd").
        out.extend(_list_until_sil(punits[d1]))
        out.append(_WBOUND)
        out.extend(_list_until_sil(phundred))
        if d2 == 0 and d3 == 0:
            if ordinal:
                out.append(_US_TH)
            return out
        out.extend(_list_until_sil(pand))
    if d2 == 1:
        out.extend(_list_until_sil(pteens[d3]))
        if ordinal:
            out.append(_US_TH)
        return out
    if d2 != 0:
        out.extend(_list_until_sil(ptens[d2 - 2]))
        if d3 == 0:
            if ordinal:
                out.append(_US_IX)
                out.append(_US_TH)
            return out
        out.append(_WBOUND)
    if ordinal:
        out.extend(_list_until_sil(pordin[d3]))
    else:
        out.extend(_list_until_sil(punits[d3]))
    return out


__all__ = ["speak_2_digits", "speak_3_digits", "speak_4_digits", "speak_digit_group"]
