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
from dectalk.lts.number_emit import ls_proc_do_number_full
from dectalk.lts.phoneme_words import phalf, phalves, ppercent

_US_S: int = int(USPhoneme.S)
_US_Z: int = int(USPhoneme.Z)


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

    Numerator and denominator go through the full C number reader
    (:func:`~dectalk.lts.number_emit.ls_proc_do_number_full`) exactly
    as the C source calls ``ls_proc_do_number`` — the numerator as a
    cardinal, the denominator as an ordinal.

    Args:
        emitter: The LTS emitter state.
        word: The fraction word as bytes (e.g. ``b"3/4%"``).
    """
    slash = word.find(b"/")
    if slash < 0:
        return

    # Numerator: word[0:slash]
    plural = ls_proc_do_number_full(emitter, word[:slash])
    emitter.send_phone(WBOUND)

    # Denominator: word[slash+1 .. percent-or-end]
    rest = word[slash + 1 :]
    percent = rest.find(b"%")
    denom = rest[:percent] if percent >= 0 else rest

    # Special case: denominator is exactly "2" — use "half"/"halves".
    if denom == b"2":
        emitter.send_phone_list(phalves if plural else phalf)
    else:
        ls_proc_do_number_full(emitter, denom, oflag=True)
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
