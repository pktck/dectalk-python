"""Spell-mode speed classifier from ls_spel.c.

Translated from ``src/dapi/src/lts/ls_spel.c``:

- :func:`ls_spel_spell_speed` — return :data:`FAST` if a slice of
  letters should be spelled quickly (single-letter words; abbreviations
  with ampersands like ``"AT&T"``, ``"FA&T"``, ``"R&B"``;
  three-letter or shorter strings); :data:`SLOW` otherwise.
- :data:`FAST` / :data:`SLOW` — the spell-mode constants from
  ``lts/ls_defs.h``.
"""

from __future__ import annotations

from typing import Final

from dectalk.lts.char_features import is_alpha, ls_lower

FAST: Final[int] = 0
"""Spell mode = fast (no per-letter pause)."""

SLOW: Final[int] = 1
"""Spell mode = slow (per-letter comma pause)."""

DASHNFAST: Final[int] = 2
"""Spell mode = fast and pronounce each separator as ``"dash"``."""


def ls_spel_spell_speed(word: str | bytes) -> int:
    """Classify a slice of letters as fast- or slow-spelled.

    Faithful translation of:

    .. code-block:: c

        int ls_spel_spell_speed(LETTER *llp, LETTER *rlp) {
            int c, nchar = 0, namper = 0;
            if (llp+1 == rlp)            // 1-letter words: always fast.
                return FAST;
            while (llp != rlp) {
                c = (llp++)->l_ch;
                ++nchar;
                if (c == '&') ++namper;
                else {
                    c = ls_lower[c];      // case-fold
                    if (!IS_ALPHA(c)) return SLOW;
                }
            }
            if (nchar < 4)               // short word: fast
                return FAST;
            if (nchar == 4 && namper == 1)  // "FA&T", "AT&T"
                return FAST;
            return SLOW;
        }

    Args:
        word: Slice of letters. ``str`` is Latin-1 encoded.

    Returns:
        :data:`FAST` (0) or :data:`SLOW` (1).
    """
    buf = word.encode("latin-1", errors="replace") if isinstance(word, str) else word
    if len(buf) == 1:
        return FAST

    nchar = 0
    namper = 0
    ampersand = ord("&")
    for c in buf:
        nchar += 1
        if c == ampersand:
            namper += 1
        else:
            lowered = ls_lower[c]
            if not is_alpha(lowered):
                return SLOW

    short_threshold = 4
    if nchar < short_threshold:
        return FAST
    if nchar == short_threshold and namper == 1:
        return FAST
    return SLOW


__all__ = ["DASHNFAST", "FAST", "SLOW", "ls_spel_spell_speed"]
