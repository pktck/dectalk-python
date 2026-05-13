"""``is_wboundary`` predicate from ph_sort.c.

Translated from ``src/dapi/src/ph/ph_sort.c`` lines 1822-1829.

A tiny range check the PH sort/intonation passes use to decide
whether a symbol is a word-or-greater boundary. The codes 111
(WBOUND) through 118 (EXCLAIM) cover word boundary, punctuation
markers (PPSTART, VPSTART, RELSTART, COMMA, PERIOD, QUEST,
EXCLAIM) and the C source's predicate returns TRUE for all of
them.
"""

from __future__ import annotations

from dectalk.include.phoneme_codes import EXCLAIM, WBOUND


def is_wboundary(symb: int) -> bool:
    """Return ``True`` iff ``symb`` is in ``[WBOUND, EXCLAIM]``.

    Faithful translation of:

    .. code-block:: c

        static int is_wboundary(short symb) {
            if ((symb >= WBOUND) && (symb <= EXCLAIM)) return TRUE;
            return FALSE;
        }

    Args:
        symb: Phoneme / boundary code.

    Returns:
        ``True`` if ``WBOUND <= symb <= EXCLAIM``.
    """
    return WBOUND <= symb <= EXCLAIM


__all__ = ["is_wboundary"]
