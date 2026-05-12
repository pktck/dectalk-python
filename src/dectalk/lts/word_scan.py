"""Word-boundary scanning helpers from ls_task.c.

Translated from ``src/dapi/src/lts/ls_task.c``:

- :func:`ls_task_find_end_of_word` — walk a LETTER stream from a
  left bound until the first EOS, returning the right bound.
- :func:`wlookup` — pure variant of ``ls_task_wlookup``: walks a
  case-folded LETTER prefix against a packed-table of
  ``length, key..., EOS, phonemes...`` records and returns the
  matched phoneme byte string (or ``None``).
"""

from __future__ import annotations

from dectalk.lts.char_features import ls_lower
from dectalk.lts.phone_list import EOS
from dectalk.lts.structs import Letter


def ls_task_find_end_of_word(letters: list[Letter], left: int = 0) -> int:
    """Return the index of the EOS terminator in ``letters[left:]``.

    Faithful translation of:

    .. code-block:: c

        void ls_task_find_end_of_word(LETTER *llp, LETTER **rlp,
                                       LETTER **elp) {
            (*elp) = llp;
            while ((*elp)->l_ch != EOS)
                ++(*elp);
            (*rlp) = (*elp);
        }

    The C version returns the right/end pointers via out-params.
    The Python version returns the integer index of the EOS so the
    caller can slice ``letters[left:end]`` cleanly.

    Args:
        letters: LETTER list, EOS-terminated.
        left: Starting index (default 0).

    Returns:
        The index of the EOS sentinel, or ``len(letters)`` if none
        found.
    """
    i = left
    n = len(letters)
    while i < n and letters[i].l_ch != EOS:
        i += 1
    return i


def wlookup(
    word: list[Letter],
    table: bytes,
    left: int = 0,
) -> bytes | None:
    """Return the phoneme byte string for ``word`` looked up in ``table``.

    Faithful translation (with side-effects removed) of:

    .. code-block:: c

        char *ls_task_wlookup(PLTS_T pLts_t, LETTER word[],
                               unsigned char table[]) {
            LETTER *lp; unsigned char *cp, *tp; int c, len;
            tp = &table[0];
            while ((len = *tp++) != 0) {
                lp = &word[0]; cp = tp;
                for (;;) {
                    c = ls_lower[lp->l_ch];        // case-fold
                    if (c != *cp++) break;
                    if (c == EOS) return (cp);     // match → phonemes
                    ++lp;
                }
                tp += len;
            }
            return NULL;
        }

    The C version had a side-effect that set ``form_class`` for
    English function words "to", "and", "for". That branch is
    omitted from this pure helper; the form-class assignment
    will live in the caller once we model the LTS thread state.

    Table layout: each record is ``len, key_byte..., EOS,
    phoneme_byte..., 0_terminator``. The trailing 0 byte after
    the phoneme run is the loop's stop condition.

    Args:
        word: LETTER list (EOS-terminated) to look up.
        table: Packed lookup table (see layout above).
        left: Starting index in ``word`` (default 0).

    Returns:
        The phoneme byte run that follows the matched key, or
        ``None`` if no entry matches.
    """
    tp = 0
    while tp < len(table):
        record_len = table[tp]
        if record_len == 0:
            break
        tp += 1
        # Match the case-folded LETTER word against the record key.
        lp = left
        cp = tp
        word_len = len(word)
        while True:
            ch = word[lp].l_ch if lp < word_len else EOS
            c = ls_lower[ch] if 0 <= ch < len(ls_lower) else ch
            entry_byte = table[cp] if cp < len(table) else 0
            cp += 1
            if c != entry_byte:
                # Mismatch — try next record.
                break
            if c == EOS:
                # Both sides hit EOS together. The C source returns
                # the byte position immediately after the matched
                # EOS, which is where the phoneme run starts.
                return _read_phoneme_run(table, cp)
            lp += 1
        # Skip ``record_len`` bytes (the C source records this
        # so the loop can step past the whole record on mismatch).
        tp += record_len
    return None


def _read_phoneme_run(table: bytes, start: int) -> bytes:
    """Return bytes from ``start`` up to (but not including) the next NUL."""
    end = start
    while end < len(table) and table[end] != 0:
        end += 1
    return bytes(table[start:end])


__all__ = ["ls_task_find_end_of_word", "wlookup"]
