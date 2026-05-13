"""``remaining_stresses_til`` helper from ph_aloph2.c.

Translated from ``src/dapi/src/ph/ph_aloph2.c`` lines 1716-1742.

Counts the number of stressed syllables remaining in the
``sentstruc[]`` / ``phonemes[]`` arrays starting from ``msym + 1``
and ending when either:

- a boundary at level ``>= b_type`` is hit, or
- a ``GEN_SIL`` (clause silence) is reached.

Used by the allophone-substitution pass to decide whether a
secondary stress should be promoted.
"""

from __future__ import annotations

from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import FBOUNDARY, FSTRESS
from dectalk.ph.phoneme_features import FSYLL
from dectalk.ph.timing import phone_feature
from dectalk.ph.utterance_constants import GEN_SIL


def remaining_stresses_til(p_dph_t: DphT, msym: int, b_type: int) -> int:
    """Count stressed syllables in ``[msym + 1, boundary or GEN_SIL)``.

    Faithful translation of:

    .. code-block:: c

        static short remaining_stresses_til(PDPH_T pDph_t, short msym,
                                            short b_type) {
            count = 0;
            for (m = msym; m < pDph_t->nphonetot; m++) {
                if (m != msym
                    && (pDph_t->sentstruc[m] & FSTRESS) IS_PLUS
                    && (phone_feature(pDph_t, pDph_t->phonemes[m])
                         & FSYLL) IS_PLUS) {
                    count++;
                }
                if ((pDph_t->sentstruc[m] & FBOUNDARY) >= b_type
                    || pDph_t->phonemes[m] == GEN_SIL) {
                    return count;
                }
            }
            return count;
        }

    The C source's loop never visits ``m = msym`` for the count
    increment but uses it for the boundary check — preserved exactly.

    Args:
        p_dph_t: PH thread state.
        msym: Starting index into ``phonemes`` / ``sentstruc``.
        b_type: Boundary threshold; the loop stops when
            ``sentstruc[m] & FBOUNDARY >= b_type``.

    Returns:
        Count of stressed syllable phonemes encountered after
        ``msym`` and before the boundary or :data:`GEN_SIL`.
    """
    if p_dph_t.sentstruc is None or p_dph_t.phonemes is None:
        return 0
    sentstruc = p_dph_t.sentstruc
    phonemes = p_dph_t.phonemes
    count = 0
    for m in range(msym, p_dph_t.nphonetot):
        if (
            m != msym
            and (sentstruc[m] & FSTRESS) != 0
            and (phone_feature(phonemes[m]) & FSYLL) != 0
        ):
            count += 1
        if (sentstruc[m] & FBOUNDARY) >= b_type or phonemes[m] == GEN_SIL:
            return count
    return count


__all__ = ["remaining_stresses_til"]
