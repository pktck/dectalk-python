"""Unstressed-syllable check from ls_adju.c.

Translated from ``src/dapi/src/lts/ls_adju.c``:

- :func:`syllable_cannot_take_stress` — given the head of a syllable
  (the first PHONE), walk past any leading consonants and check if
  the vowel is ``[L]`` (``US_EL``). The English ``[L]`` syllabic-L
  is the only allophone the C source flags as "cannot take primary
  stress" — function words like "table", "people" end on this and
  the dictionary lookup must skip stress assignment there.
"""

from __future__ import annotations

from dectalk.include.phoneme_codes import USPhoneme
from dectalk.lts.phone_predicates import ls_adju_is_cons
from dectalk.lts.structs import Phone

_US_EL: int = int(USPhoneme.EL)


def syllable_cannot_take_stress(syl_head: Phone) -> bool:
    """Return True iff the syllable starting at ``syl_head`` cannot be stressed.

    Faithful translation of:

    .. code-block:: c

        int ls_adju_unstressed(PLTS_T pLts_t, int n) {
            PHONE *pp = pLts_t->sylp[n];
            int sphone;
            while (ls_adju_is_cons(pp) != FALSE)
                pp = pp->p_fp;
            sphone = pp->p_sphone;
            if (sphone == US_EL)            // ENGLISH_US
                return TRUE;
            return FALSE;
        }

    The C source dereferences ``pLts_t->sylp[n]`` to find the head
    PHONE of the n-th syllable; the Python signature takes the
    PHONE directly so callers can wire it up however they like.

    Args:
        syl_head: First PHONE of the syllable.

    Returns:
        ``True`` iff the syllable's vowel is :attr:`USPhoneme.EL`
        (the syllabic-L); the syllable cannot bear primary stress.
    """
    pp: Phone | None = syl_head
    while pp is not None and ls_adju_is_cons(pp.p_sphone):
        pp = pp.p_fp
    if pp is None:
        return False
    return pp.p_sphone == _US_EL


__all__ = ["syllable_cannot_take_stress"]
