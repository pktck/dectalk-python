"""``promote_last_2`` helper from ph_aloph2.c.

Translated from ``src/dapi/src/ph/ph_aloph2.c`` lines 1759-1791.

Walks ``sentstruc[]`` from ``msym`` looking for the *last*
secondary-stress (``FSTRESS_2``) on a syllabic phoneme before a
clause boundary or ``GEN_SIL``. If found, promotes that syllable's
stress to primary (``FSTRESS_1``).

Used in the allophonic-substitution pass to make patterns like
``J'ohn ) is h`im`` promote ``him`` (the last secondary stress) to
primary stress.
"""

from __future__ import annotations

from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import FBOUNDARY, FCBNEXT, FSTRESS, FSTRESS_1, FSTRESS_2
from dectalk.ph.phoneme_features import FSYLL
from dectalk.ph.timing import phone_feature
from dectalk.ph.utterance_constants import GEN_SIL


def promote_last_2(p_dph_t: DphT, msym: int) -> bool:
    """Promote the last secondary stress before a boundary to primary.

    Faithful translation of:

    .. code-block:: c

        static short promote_last_2(PDPH_T pDph_t, short msym) {
            done_it = 0;
            for (m = msym; m < pDph_t->nphonetot; m++) {
                if (m != msym
                    && (pDph_t->sentstruc[m] & FSTRESS) == FSTRESS_2
                    && (phone_feature(pDph_t, pDph_t->phonemes[m])
                         & FSYLL) IS_PLUS) {
                    done_it = m;
                }
                if ((pDph_t->sentstruc[m] & FBOUNDARY) >= FCBNEXT
                    || pDph_t->phonemes[m] == GEN_SIL) {
                    if (done_it != 0) {
                        pDph_t->sentstruc[done_it] &= ~FSTRESS_2;
                        pDph_t->sentstruc[done_it] |= FSTRESS_1;
                        return TRUE;
                    }
                }
            }
            return FALSE;
        }

    The ``done_it`` zero-vs-non-zero gate is preserved verbatim —
    the C source's ``if (done_it != 0)`` means ``msym == 0`` can
    never become the promotion target.

    Args:
        p_dph_t: PH thread state.
        msym: Starting index into ``phonemes`` / ``sentstruc``.

    Returns:
        ``True`` if a promotion was performed; ``False`` otherwise.
    """
    if p_dph_t.sentstruc is None or p_dph_t.phonemes is None:
        return False
    sentstruc = p_dph_t.sentstruc
    phonemes = p_dph_t.phonemes
    done_it = 0
    int_mask = 0xFFFFFFFF  # C unsigned int complement.
    for m in range(msym, p_dph_t.nphonetot):
        if (
            m != msym
            and (sentstruc[m] & FSTRESS) == FSTRESS_2
            and (phone_feature(phonemes[m]) & FSYLL) != 0
        ):
            done_it = m  # Pointer to last secondary stress.
        if ((sentstruc[m] & FBOUNDARY) >= FCBNEXT or phonemes[m] == GEN_SIL) and done_it != 0:
            sentstruc[done_it] &= (~FSTRESS_2) & int_mask
            sentstruc[done_it] |= FSTRESS_1
            return True
    return False


__all__ = ["promote_last_2"]
