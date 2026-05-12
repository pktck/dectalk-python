"""Syllable-scan results from ls_adju.c.

Translated from ``src/dapi/src/lts/ls_adju.c``:

- :class:`SyllabicWord` — captures the state that the C source's
  ``pLts_t`` holds during the syllable-scan passes: ``nsyl`` (count),
  ``rsyl`` (first stressed syllable), ``psyl`` (primary-stress
  syllable), and ``sylp`` (PHONE pointer per syllable).
- :func:`ls_adju_suffixscan` — walk the PHONE list left-to-right,
  populating a :class:`SyllabicWord` with syllable bookkeeping.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from dectalk.lts.phone_list import SNONE
from dectalk.lts.structs import PFSYLAB, Phone


def _empty_phone_list() -> list[Phone]:
    """Factory for the default ``sylp`` list."""
    return []

NSYL: Final[int] = 10
"""Maximum number of syllables per English word (matches the C ``#define``)."""

SPRI: Final[int] = SNONE + 3
"""Primary stress code: ``PHO_SYM_TOT + 3`` per ls_defs.h.

The Python port uses :data:`SNONE` (= ``PHO_SYM_TOT``) as the base; the C
source defines ``SPRI`` as ``PHO_SYM_TOT + 3``.
"""


@dataclass(slots=True)
class SyllabicWord:
    """State container for syllable-aware LTS passes.

    Holds the bookkeeping that the C source stores on ``pLts_t``:

    Attributes:
        nsyl: Number of syllables found.
        rsyl: Index of the first stressed syllable (rightmost root
            syllable), or ``-1`` if none.
        psyl: Index of the syllable forced to take primary stress,
            or ``-1`` if none.
        sylp: One PHONE per syllable (the syllable's onset start).
    """

    nsyl: int = 0
    rsyl: int = -1
    psyl: int = -1
    sylp: list[Phone] = field(default_factory=_empty_phone_list)


def ls_adju_suffixscan(fpp: Phone, lpp: Phone | None) -> SyllabicWord | None:
    """Scan the PHONE list and populate a :class:`SyllabicWord` summary.

    Faithful translation of:

    .. code-block:: c

        int ls_adju_suffixscan(PLTS_T pLts_t, PHONE *fpp, PHONE *lpp) {
            PHONE *pp;
            pLts_t->nsyl = 0;
            pLts_t->rsyl = -1;
            pLts_t->psyl = -1;
            pp = fpp;
            while (pp != lpp) {
                if ((pp->p_flag & PFSYLAB) != 0) {
                    if (pLts_t->nsyl >= NSYL) return FALSE;
                    if (pp->p_stress != SNONE) {
                        if (pLts_t->rsyl < 0) pLts_t->rsyl = pLts_t->nsyl;
                        if (pLts_t->psyl<0 && pp->p_stress>=SPRI)
                            pLts_t->psyl = pLts_t->nsyl;
                    }
                    pLts_t->sylp[pLts_t->nsyl++] = pp;
                }
                pp = pp->p_fp;
            }
            if (pLts_t->rsyl < 0) pLts_t->rsyl = pLts_t->nsyl;
            return TRUE;
        }

    The C source mutates ``pLts_t`` in place; the Python port
    returns a fresh :class:`SyllabicWord` or ``None`` if the
    PHONE list has more than :data:`NSYL` syllables (matching the
    C return ``FALSE`` overflow case).

    Args:
        fpp: First PHONE in the word.
        lpp: Sentinel (one past the last PHONE), or ``None``.

    Returns:
        A :class:`SyllabicWord` with the scan results, or ``None``
        if the syllable count exceeded :data:`NSYL`.
    """
    word = SyllabicWord()
    pp: Phone | None = fpp
    while pp is not None and pp is not lpp:
        if (pp.p_flag & PFSYLAB) != 0:
            if word.nsyl >= NSYL:
                return None
            if pp.p_stress != SNONE:
                if word.rsyl < 0:
                    word.rsyl = word.nsyl
                if word.psyl < 0 and pp.p_stress >= SPRI:
                    word.psyl = word.nsyl
            word.sylp.append(pp)
            word.nsyl += 1
        pp = pp.p_fp
    if word.rsyl < 0:
        word.rsyl = word.nsyl
    return word


__all__ = ["NSYL", "SPRI", "SyllabicWord", "ls_adju_suffixscan"]
