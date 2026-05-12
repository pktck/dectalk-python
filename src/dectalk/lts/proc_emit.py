"""State-mutating ``do_*`` emit functions from l_us_pr1.c.

Translated from ``src/dapi/src/lts/l_us_pr1.c``. These functions
all push phonemes into the LTS pipeline; in Python they take an
:class:`LtsEmitter` and append to it.

- :func:`ls_proc_do_sign` — emit the phoneme sequence for ``-`` or
  ``+`` sign characters, with a WBOUND separator.
- :func:`ls_proc_do_2_digits` — wrapper around
  :func:`speak_2_digits` that emits into an emitter.
- :func:`ls_proc_do_3_digits` — same for 3-digit numbers.
- :func:`ls_proc_do_4_digits` — same for 4-digit numbers.

The C source's third "dictionary case" branch in
``ls_proc_do_sign`` calls ``ls_util_lookup`` to look up special
characters (``$``, ``%``, etc.) in the user dictionary. That path
needs full LTS thread state; for now :func:`ls_proc_do_sign` returns
``False`` for unknown signs (matching the C behaviour for signs
that the dictionary doesn't recognise).
"""

from __future__ import annotations

from dectalk.include.phoneme_codes import WBOUND, USPhoneme
from dectalk.lts.emitter import LtsEmitter
from dectalk.lts.number_words import (
    speak_2_digits,
    speak_3_digits,
    speak_4_digits,
)
from dectalk.lts.phoneme_words import pminus, pplus

_US_EY: int = int(USPhoneme.EY)


def ls_proc_do_sign_full(emitter: LtsEmitter, sign: int) -> None:
    """``ls_proc_do_sign`` with the dictionary-lookup fallback wired up.

    The C source's third branch looks up the bare sign character in
    the user dictionary; if it MISSes, the C source emits ``US_EY``
    (the letter A's vowel) plus WBOUND. This Python port skips the
    dictionary lookup and goes straight to the ``US_EY + WBOUND``
    fallback, which matches the C behaviour for unknown signs.

    Args:
        emitter: The LTS emitter state.
        sign: The sign character.
    """
    if sign == 0:
        return
    if ls_proc_do_sign(emitter, sign):
        return
    # Dictionary-lookup branch: skipped, fall straight to MISS path.
    emitter.send_phone(_US_EY)
    emitter.send_phone(WBOUND)


def ls_proc_do_sign(emitter: LtsEmitter, sign: int) -> bool:
    """Emit the phoneme sequence for a sign character.

    Faithful translation of:

    .. code-block:: c

        void ls_proc_do_sign(LPTTS_HANDLE_T phTTS, int sign) {
            LETTER lbuf[2];
            if (sign == '-') {
                ls_util_send_phone_list(phTTS, pminus);
                ls_util_send_phone(phTTS, WBOUND);
            } else if (sign == '+') {
                ls_util_send_phone_list(phTTS, pplus);
                ls_util_send_phone(phTTS, WBOUND);
            } else if (sign != 0) {
                // Dictionary lookup of the bare sign character.
                lbuf[0].l_ch = ' ';
                lbuf[1].l_ch = sign;
                if (ls_util_lookup(phTTS, &lbuf[0], &lbuf[2], FIRST) == MISS)
                    ls_util_send_phone(phTTS, US_EY);
                ls_util_send_phone(phTTS, WBOUND);
            }
        }

    Args:
        emitter: The LTS emitter state to push phonemes into.
        sign: The sign character (``'-'``, ``'+'``, or other byte).

    Returns:
        ``True`` if a known sign was emitted (minus / plus);
        ``False`` for the dictionary-lookup path (caller must
        handle that branch when state is wired up).
    """
    if sign == ord("-"):
        emitter.send_phone_list(pminus)
        emitter.send_phone(WBOUND)
        return True
    if sign == ord("+"):
        emitter.send_phone_list(pplus)
        emitter.send_phone(WBOUND)
        return True
    return False


def ls_proc_do_2_digits(emitter: LtsEmitter, d1: int, d2: int) -> None:
    """Emit the phoneme sequence for a 2-digit number.

    Wraps :func:`speak_2_digits` to push the result into the emitter.
    Leading-zero forms (``0X``) return None from ``speak_2_digits``;
    callers needing the C-faithful spell-each-digit behaviour should
    use :func:`ls_proc_do_2_digits_full` instead.

    Args:
        emitter: The LTS emitter state.
        d1: Tens digit.
        d2: Units digit.
    """
    phones = speak_2_digits(d1, d2)
    if phones is not None:
        for p in phones:
            emitter.send_phone(p)


def ls_proc_do_2_digits_full(emitter: LtsEmitter, d1: int, d2: int) -> None:
    """``ls_proc_do_2_digits`` with the leading-zero spell-out wired up.

    Faithful translation of the full C ``ls_proc_do_2_digits``:

    .. code-block:: c

        if (lp->l_ch == '0')
            ls_spel_spell(phTTS, lp, lp+2);   // spell each digit
        else ... // normal 2-digit reading

    Uses :func:`ls_spel_spell` for the leading-zero case.

    Args:
        emitter: The LTS emitter state.
        d1: Tens digit.
        d2: Units digit.
    """
    from dectalk.lts.spell_emit import ls_spel_spell  # noqa: PLC0415 — cycle break

    if d1 == 0:
        digits = bytes([ord("0") + d1, ord("0") + d2])
        ls_spel_spell(emitter, digits)
        return
    ls_proc_do_2_digits(emitter, d1, d2)


def ls_proc_do_3_digits(emitter: LtsEmitter, d1: int, d2: int, d3: int) -> None:
    """Emit the phoneme sequence for a 3-digit number.

    Args:
        emitter: The LTS emitter state.
        d1: Hundreds digit.
        d2: Tens digit.
        d3: Units digit.
    """
    phones = speak_3_digits(d1, d2, d3)
    if phones is not None:
        for p in phones:
            emitter.send_phone(p)


def ls_proc_do_4_digits(
    emitter: LtsEmitter,
    d1: int,
    d2: int,
    d3: int,
    d4: int,
) -> None:
    """Emit the phoneme sequence for a 4-digit number.

    Args:
        emitter: The LTS emitter state.
        d1: Thousands digit.
        d2: Hundreds digit.
        d3: Tens digit.
        d4: Units digit.
    """
    phones = speak_4_digits(d1, d2, d3, d4)
    if phones is not None:
        for p in phones:
            emitter.send_phone(p)


__all__ = [
    "ls_proc_do_2_digits",
    "ls_proc_do_2_digits_full",
    "ls_proc_do_3_digits",
    "ls_proc_do_4_digits",
    "ls_proc_do_sign",
    "ls_proc_do_sign_full",
]
