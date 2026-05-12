"""Fraction emission from l_us_pr1.c::ls_proc_do_frac.

Translated from ``src/dapi/src/lts/l_us_pr1.c``:

- :func:`ls_proc_do_frac` — emit the phoneme sequence for a
  fraction word like ``1/2``, ``3/4``, ``99/100%``.

Reads the numerator as a plain number, then the denominator as
an ordinal (e.g. ``1/4`` → "one quarter", ``3/8`` → "three eighths").
A trailing ``%`` is read as " percent".
"""

from __future__ import annotations

from dectalk.include.phoneme_codes import WBOUND, USPhoneme
from dectalk.lts.emitter import LtsEmitter
from dectalk.lts.number_words import speak_2_digits, speak_digit_group
from dectalk.lts.phoneme_words import phalf, phalves, ppercent, punits

_US_S: int = int(USPhoneme.S)
_US_Z: int = int(USPhoneme.Z)

_DENOM_3_DIGIT = 3


def _emit_number(emitter: LtsEmitter, digits: bytes) -> bool:
    """Emit the digits as a number; return True if plural (>1)."""
    if not digits:
        return False
    n = len(digits)
    if n == 1:
        d = digits[0] - ord("0")
        if d == 0:
            return False  # zero is singular
        emitter.send_phone_list(punits[d])
        return d > 1
    if n == 2:  # noqa: PLR2004 — 2-digit numerator
        d1 = digits[0] - ord("0")
        d2 = digits[1] - ord("0")
        # >1 if any non-(0,0) and not exactly 01.
        is_plural = not (d1 == 0 and d2 <= 1)
        phones = speak_2_digits(d1, d2)
        if phones is not None:
            for p in phones:
                emitter.send_phone(p)
        return is_plural
    return False


def _emit_denom_ordinal(emitter: LtsEmitter, digits: bytes) -> None:
    """Emit the denominator as an ordinal (e.g. fourth, hundredth)."""
    n = len(digits)
    if n == 1:
        d = digits[0] - ord("0")
        for p in speak_digit_group(0, 0, d, ordinal=True):
            emitter.send_phone(p)
    elif n == 2:  # noqa: PLR2004 — 2-digit denominator
        d2 = digits[0] - ord("0")
        d3 = digits[1] - ord("0")
        for p in speak_digit_group(0, d2, d3, ordinal=True):
            emitter.send_phone(p)
    elif n == _DENOM_3_DIGIT:  # 3-digit denominator (must be 100)
        d1 = digits[0] - ord("0")
        d2 = digits[1] - ord("0")
        d3 = digits[2] - ord("0")
        for p in speak_digit_group(d1, d2, d3, ordinal=True):
            emitter.send_phone(p)


def ls_proc_do_frac(emitter: LtsEmitter, word: bytes) -> None:
    """Emit the phoneme sequence for a fraction word.

    Faithful translation of:

    .. code-block:: c

        void ls_proc_do_frac(LPTTS_HANDLE_T phTTS,
                              LETTER *llp, LETTER *rlp) {
            // Scan to '/'. Emit numerator. WBOUND.
            // Skip '/'. Scan to '%' or end. Emit denominator.
            // If denominator is exactly "2", emit phalves/phalf
            //   depending on numerator plurality.
            // Else emit denominator as ordinal; if plural, append
            //   pluralising S or Z.
            // If trailing '%', emit ppercent.
        }

    The C source uses ls_proc_do_number for the numerator (which
    we don't have a full port of). This implementation supports
    1- and 2-digit numerators and 1-, 2-, or 3-digit denominators
    — the full set the C source's ``ls_proc_is_frac`` validator
    accepts.

    Args:
        emitter: The LTS emitter state.
        word: The fraction word as bytes (e.g. ``b"3/4%"``).
    """
    slash = word.find(b"/")
    if slash < 0:
        return

    # Numerator: word[0:slash]
    numerator = word[:slash]
    plural = _emit_number(emitter, numerator)
    emitter.send_phone(WBOUND)

    # Denominator: word[slash+1 .. percent-or-end]
    rest = word[slash + 1 :]
    percent = rest.find(b"%")
    denom = rest[:percent] if percent >= 0 else rest

    # Special case: denominator is exactly "2" — use "half"/"halves".
    if denom == b"2":
        emitter.send_phone_list(phalves if plural else phalf)
    else:
        _emit_denom_ordinal(emitter, denom)
        if plural:
            # The C source: ud = last digit of denom; if previous
            # digit is '1' (teen form), use '0' instead. Then
            # emit Z for 2/3 endings else S.
            last_d = denom[-1] if denom else ord("0")
            second_last = denom[-2] if len(denom) >= 2 else None  # noqa: PLR2004
            ud = ord("0") if second_last == ord("1") else last_d
            emitter.send_phone(_US_Z if ud in (ord("2"), ord("3")) else _US_S)

    # Optional trailing '%'.
    if percent >= 0:
        emitter.send_phone_list(ppercent)


__all__ = ["ls_proc_do_frac"]
