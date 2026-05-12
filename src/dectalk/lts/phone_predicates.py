"""Per-phoneme feature predicates from ls_adju.c.

Translated from ``src/dapi/src/lts/ls_adju.c``:

- :func:`ls_adju_is_cons` — return True iff the phoneme has the
  :data:`PCONS` (consonant) feature.
- :func:`ls_adju_is_voc` — return True iff the phoneme has the
  :data:`PVOC` (vowel/voiced-sonorant) feature.

Both functions look up :data:`pfeat` indexed by the phoneme's
``p_sphone`` byte. The Python port takes the byte directly rather
than a PHONE struct pointer.
"""

from __future__ import annotations

from dectalk.lts.grapheme_features import PCONS, PVOC, pfeat


def ls_adju_is_cons(p_sphone: int) -> bool:
    """Return True iff the phoneme has the :data:`PCONS` feature.

    Faithful translation of:

    .. code-block:: c

        int ls_adju_is_cons(PHONE *pp) {
            if ((pfeat[pp->p_sphone] & PCONS) != 0)
                return TRUE;
            return FALSE;
        }

    Args:
        p_sphone: The ``p_sphone`` byte from a PHONE struct.

    Returns:
        ``True`` iff ``pfeat[p_sphone]`` has bit :data:`PCONS` set.
    """
    return bool(pfeat[p_sphone] & PCONS)


def ls_adju_is_voc(p_sphone: int) -> bool:
    """Return True iff the phoneme has the :data:`PVOC` feature.

    Faithful translation of:

    .. code-block:: c

        int ls_adju_is_voc(PHONE *pp) {
            if ((pfeat[pp->p_sphone] & PVOC) != 0)
                return TRUE;
            return FALSE;
        }

    Args:
        p_sphone: The ``p_sphone`` byte from a PHONE struct.

    Returns:
        ``True`` iff ``pfeat[p_sphone]`` has bit :data:`PVOC` set.
    """
    return bool(pfeat[p_sphone] & PVOC)


__all__ = ["ls_adju_is_cons", "ls_adju_is_voc"]
