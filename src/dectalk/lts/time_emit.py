"""Time-of-day emission from l_us_pr1.c::ls_proc_do_time.

Translated from ``src/dapi/src/lts/l_us_pr1.c``:

- :func:`ls_proc_do_time` — emit the phoneme sequence for a time
  string like ``12:34``, ``1:23``, ``12:34:56``, or ``12:34.5``.
"""

from __future__ import annotations

from dectalk.include.phoneme_codes import VPSTART, WBOUND
from dectalk.lts.char_features import is_digit
from dectalk.lts.emitter import LtsEmitter
from dectalk.lts.phoneme_words import ppoint, punits
from dectalk.lts.proc_emit import ls_proc_do_2_digits_full
from dectalk.lts.spell_emit import ls_spel_spell


def ls_proc_do_time(emitter: LtsEmitter, word: bytes) -> None:
    """Emit the phoneme sequence for a time-of-day word.

    Faithful translation of:

    .. code-block:: c

        void ls_proc_do_time(LPTTS_HANDLE_T phTTS, LETTER *llp, LETTER *rlp) {
            if ((llp+1)->l_ch == ':') {
                // Initial 1-digit hour: D:DD
                ls_util_send_phone_list(phTTS, punits[llp->l_ch-'0']);
                llp += 2;
            } else {
                // Initial 2-digit hour: DD:DD
                ls_proc_do_2_digits(phTTS, llp);
                llp += 3;
            }
            ls_util_send_phone(phTTS, VPSTART);
            if (!(llp->l_ch == '0' && (llp+1)->l_ch == '0'))
                ls_proc_do_2_digits(phTTS, llp);
            llp += 2;

            if (llp != rlp && llp->l_ch == ':') {
                ls_util_send_phone(phTTS, VPSTART);
                ls_proc_do_2_digits(phTTS, llp+1);
                llp += 3;
            }
            if (llp != rlp) {
                if (llp->l_ch == '.') {
                    ls_util_send_phone(phTTS, WBOUND);
                    ls_util_send_phone_list(phTTS, ppoint);
                    while (++llp != rlp) {
                        ls_util_send_phone(phTTS, WBOUND);
                        ls_util_send_phone_list(phTTS, punits[llp->l_ch-'0']);
                    }
                } else {
                    ls_spel_spell(phTTS, llp, rlp);
                }
            }
        }

    The C source emits the time as a sequence of digit groups
    separated by ``VPSTART`` (verbal-pause-start, treated as a
    phrase-internal pause by the prosody layer). Fractional seconds
    after a ``.`` are read as ``"point one two three"``.

    Leading-zero minute/second pairs go through the full C
    ``ls_proc_do_2_digits`` (``3:05`` spells the minutes as "zero
    five"); a non-``.`` trailing remainder is spelled out, both
    exactly as the C source.

    Args:
        emitter: The LTS emitter state.
        word: The time-of-day word as bytes (e.g. ``b"12:34"``).
    """
    n = len(word)
    if n < 4:  # noqa: PLR2004 — minimum "D:DD"
        return

    i = 0
    # Hour: 1 or 2 digits.
    if word[1] == ord(":"):
        # D:DD
        emitter.send_phone_list(punits[word[0] - ord("0")])
        i = 2  # past 'D:'
    else:
        # DD:DD
        ls_proc_do_2_digits_full(emitter, word[0] - ord("0"), word[1] - ord("0"))
        i = 3  # past 'DD:'

    emitter.send_phone(VPSTART)

    # Minutes: 2 digits. Skip emission if both are 0.
    if i + 1 < n and not (word[i] == ord("0") and word[i + 1] == ord("0")):
        ls_proc_do_2_digits_full(emitter, word[i] - ord("0"), word[i + 1] - ord("0"))
    i += 2

    # Optional :SS seconds.
    if i < n and word[i] == ord(":"):
        emitter.send_phone(VPSTART)
        if i + 2 < n:
            ls_proc_do_2_digits_full(
                emitter,
                word[i + 1] - ord("0"),
                word[i + 2] - ord("0"),
            )
        i += 3

    # Optional .FFF fractional seconds.
    if i < n and word[i] == ord("."):
        emitter.send_phone(WBOUND)
        emitter.send_phone_list(ppoint)
        i += 1
        while i < n and is_digit(word[i]):
            emitter.send_phone(WBOUND)
            emitter.send_phone_list(punits[word[i] - ord("0")])
            i += 1
    elif i < n:
        # Anything else: the C source spells the remainder out.
        ls_spel_spell(emitter, word[i:])


__all__ = ["ls_proc_do_time"]
