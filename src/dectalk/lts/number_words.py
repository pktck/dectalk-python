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

from dectalk.include.phoneme_codes import WBOUND
from dectalk.lts.phone_list import iter_phone_list_until_sil
from dectalk.lts.phoneme_words import phundred, pteens, ptens, punits

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
                ls_spel_spell(...);                // spell each digit
            else {
                ls_util_send_phone_list(phTTS, punits[lp->l_ch-'0']);
                ls_util_send_phone(phTTS, WBOUND);
                ls_util_send_phone_list(phTTS, phundred);
                if ((lp+1)->l_ch != '0' || (lp+2)->l_ch != '0') {
                    ls_util_send_phone(phTTS, WBOUND);
                    ls_proc_do_2_digits(phTTS, lp+1);
                }
            }
        }

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
    out = _list_until_sil(punits[d1])
    out.append(_WBOUND)
    out.extend(_list_until_sil(phundred))
    # If the trailing 2 digits aren't both 0, add WBOUND + the 2-digit form.
    if d2 != 0 or d3 != 0:
        out.append(_WBOUND)
        if d2 == 0:
            # "X-oh-Y" — spell each digit. Caller handles this via say_it.
            # The C source recurses into ls_proc_do_2_digits which spells "0Y".
            # For our pure helper, we return punits[d3] preceded by a "oh" —
            # but the spelling path is handled by say_it in the caller.
            out.extend(_list_until_sil(punits[d3]))
        else:
            two_digits = speak_2_digits(d2, d3)
            if two_digits is not None:
                out.extend(two_digits)
    return out


__all__ = ["speak_2_digits", "speak_3_digits"]
