"""Part-number emission from l_us_pr1.c::ls_proc_do_part_number.

Translated from ``src/dapi/src/lts/l_us_pr1.c``:

- :func:`ls_proc_do_part_number` — emit the phoneme sequence for a
  DECtalk-style part number (e.g. ``ABC-123-XYZ`` or ``A1B2C3``).

The C source handles three kinds of chunks:

* ``-`` / ``/`` — spelled separators (each separator becomes its
  own glyph if not in FAA-spell mode).
* digit runs — read as numbers via the 2/3/4-digit functions, or
  spelled if 5+ digits.
* alphabetic / part-id runs — looked up in the user dictionary
  (``ls_util_lookup``); spelled if the dictionary doesn't match
  or the run is short (< 3 chars).

The dictionary-lookup branch needs full LTS state; this Python
port handles the separators and digit runs, leaving the
alphabetic-lookup branch to a caller-supplied fallback.
"""

from __future__ import annotations

from collections.abc import Callable

from dectalk.include.phoneme_codes import WBOUND
from dectalk.lts.char_features import is_digit
from dectalk.lts.emitter import LtsEmitter
from dectalk.lts.proc_emit import (
    ls_proc_do_2_digits,
    ls_proc_do_3_digits,
    ls_proc_do_4_digits,
)
from dectalk.lts.spell_emit import ls_spel_spell

_DIGIT_RUN_2 = 2
_DIGIT_RUN_3 = 3
_DIGIT_RUN_4 = 4


def ls_proc_do_part_number(  # noqa: PLR0912 — mirrors C state machine
    emitter: LtsEmitter,
    word: bytes,
    *,
    spell_separator: Callable[[LtsEmitter, int], None] | None = None,
    speak_letters: Callable[[LtsEmitter, bytes], None] | None = None,
) -> None:
    """Emit the phoneme sequence for a part-number word.

    Faithful translation of:

    .. code-block:: c

        void ls_proc_do_part_number(LPTTS_HANDLE_T phTTS,
                                     LETTER *llp, LETTER *rlp) {
            while (llp != rlp) {
                blp = llp; ++llp;
                if (blp->l_ch=='-' || blp->l_ch=='/') {
                    ls_spel_spell(phTTS, blp, llp);
                    if (llp != rlp) ls_util_send_phone(phTTS, WBOUND);
                } else if (digit) {
                    // scan digit run; speak as 2/3/4-digit or spell
                } else {
                    // alphabetic run — try dict lookup, else spell
                }
            }
        }

    The C source uses ``ls_spel_spell`` and ``ls_util_lookup`` for
    the separator-spell and dictionary-lookup branches; the Python
    port takes optional callbacks for those so callers can wire up
    their own (a no-op default is fine for tests).

    Args:
        emitter: The LTS emitter state.
        word: The part-number word as bytes.
        spell_separator: Optional callback ``(emitter, char_int)``
            invoked for each ``-`` or ``/`` separator. Defaults to
            a no-op (matching the FAA-mode branch in the C source).
        speak_letters: Optional callback ``(emitter, run)`` invoked
            for each alphabetic / mixed run. Defaults to a no-op.
    """
    i = 0
    n = len(word)
    while i < n:
        c = word[i]
        # Separator: '-' or '/'.
        if c in (ord("-"), ord("/")):
            if spell_separator is not None:
                spell_separator(emitter, c)
            i += 1
            if i < n:
                emitter.send_phone(WBOUND)
            continue
        # Digit run.
        if is_digit(c):
            j = i
            while j < n and is_digit(word[j]):
                j += 1
            nd = j - i
            d = [word[k] - ord("0") for k in range(i, j)]
            if nd == _DIGIT_RUN_2:
                ls_proc_do_2_digits(emitter, d[0], d[1])
            elif nd == _DIGIT_RUN_3:
                ls_proc_do_3_digits(emitter, d[0], d[1], d[2])
            elif nd == _DIGIT_RUN_4:
                ls_proc_do_4_digits(emitter, d[0], d[1], d[2], d[3])
            elif speak_letters is not None:
                # 1 digit or 5+ digits — spell each.
                speak_letters(emitter, word[i:j])
            i = j
            if i < n:
                emitter.send_phone(WBOUND)
            continue
        # Alphabetic / other run.
        j = i
        while j < n and word[j] not in (ord("-"), ord("/")) and not is_digit(word[j]):
            j += 1
        if speak_letters is not None:
            speak_letters(emitter, word[i:j])
        i = j
        if i < n:
            emitter.send_phone(WBOUND)


def ls_proc_do_part_number_full(emitter: LtsEmitter, word: bytes) -> None:
    """Convenience wrapper using :func:`ls_spel_spell` for letter runs.

    Wires the part-number reader to the real spell-out helper so a
    word like ``b"R2D2-X1"`` is read as ``"R two D two dash X one"``.

    Args:
        emitter: The LTS emitter state.
        word: The part-number word as bytes.
    """

    def _spell_separator(em: LtsEmitter, c: int) -> None:
        ls_spel_spell(em, bytes([c]))

    def _spell_letters(em: LtsEmitter, run: bytes) -> None:
        ls_spel_spell(em, run)

    ls_proc_do_part_number(
        emitter,
        word,
        spell_separator=_spell_separator,
        speak_letters=_spell_letters,
    )


__all__ = ["ls_proc_do_part_number", "ls_proc_do_part_number_full"]
