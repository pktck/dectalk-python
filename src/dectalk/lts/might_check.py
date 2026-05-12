"""Next-item "might" predicate from ls_util.c.

Translated from ``src/dapi/src/lts/ls_util.c``:

- :func:`ls_util_is_might` — pure variant of the predicate that
  asks whether a *next-item* word would be word-internal-keepable
  (BACKUP / ALWAYS / MIGHT character types in ``lsctype``). The C
  source pulls the next ITEM via ``ls_util_next_item`` and checks
  its first word's character class; the Python port takes the
  candidate next-item's first word directly.
"""

from __future__ import annotations

from dectalk.include.cmd_codes import PFASCII, PFONT, PSFONT, PVALUE
from dectalk.lts.char_class import ALWAYS, BACKUP, MIGHT, TYPE, lsctype

_PFASCII_BITS = PFASCII << PSFONT


def ls_util_is_might(i_word0: int) -> bool:
    """Return True iff a font-encoded value would be kept word-internally.

    Faithful translation of:

    .. code-block:: c

        int ls_util_is_might(LPTTS_HANDLE_T phTTS) {
            ls_util_next_item(phTTS);
            if ((pLts_t->nitem.i_word[0] & PFONT) == (PFASCII<<PSFONT)) {
                t = lsctype[pLts_t->nitem.i_word[0] & PVALUE] & TYPE;
                if (t == BACKUP || t == ALWAYS || t == MIGHT)
                    return TRUE;
            }
            return FALSE;
        }

    The C source mutates state via ``ls_util_next_item`` (it pulls
    the next item from the input pipe) and then checks the new
    item's first word. The Python port takes the candidate
    ``i_word[0]`` directly so callers handle the pipe pull
    separately.

    Args:
        i_word0: First word of the next ITEM (16-bit font-encoded).

    Returns:
        ``True`` iff ``i_word0``'s font is PFASCII AND its low-byte
        value has lsctype TYPE bits equal to BACKUP, ALWAYS, or
        MIGHT.
    """
    if (i_word0 & PFONT) != _PFASCII_BITS:
        return False
    value = i_word0 & PVALUE
    t = lsctype[value] & TYPE
    return t in (BACKUP, ALWAYS, MIGHT)


__all__ = ["ls_util_is_might"]
