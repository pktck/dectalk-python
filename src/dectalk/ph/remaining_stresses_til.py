"""``remaining_stresses_til`` helper from ph_aloph1.c (active variant).

Translated from ``src/dapi/src/ph/ph_aloph1.c`` lines 1566-1590 — the
``#ifndef ENGLISH_UK`` (active ``ENGLISH_US``) body, which counts only
**primary** stresses (``FSTRESS_1``). The ``ph_aloph2.c``/UK variant
this module previously mirrored counts any ``FSTRESS`` (primary or
secondary); that difference moves the ``FHAT_ENDS`` hat-fall marker off
the last *primary*-stressed syllable whenever a secondary-stressed
syllable follows it (e.g. ``listen down``, ``... the bedroom``), which
mistimed the whole clause-final F0 fall (issue #297).

Counts the number of primary-stressed syllables remaining in the
``sentstruc[]`` / ``phonemes[]`` arrays starting from ``msym + 1``
and ending when either:

- a boundary at level ``>= b_type`` is hit, or
- a ``GEN_SIL`` (clause silence) is reached.

Used by the allophone-substitution pass to place hat rise/fall markers
and decide whether a secondary stress should be promoted.
"""

from __future__ import annotations

from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import FBOUNDARY, FSTRESS_1
from dectalk.ph.phoneme_features import FSYLL
from dectalk.ph.timing import phone_feature
from dectalk.ph.utterance_constants import GEN_SIL


def remaining_stresses_til(p_dph_t: DphT, msym: int, b_type: int) -> int:
    """Count primary-stressed syllables in ``[msym + 1, boundary or GEN_SIL)``.

    Faithful translation of (active ``#ifndef ENGLISH_UK`` body; the
    UK/aloph2 variant masks with ``FSTRESS`` instead):

    .. code-block:: c

        static short remaining_stresses_til(PDPH_T pDph_t, short msym,
                                            short b_type) {
            count = 0;
            for (m = msym; m < pDph_t->nphonetot; m++) {
                if (m != msym
                    && (pDph_t->sentstruc[m] & FSTRESS_1) IS_PLUS
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
        Count of primary-stressed syllable phonemes encountered after
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
            and (sentstruc[m] & FSTRESS_1) != 0
            and (phone_feature(phonemes[m]) & FSYLL) != 0
        ):
            count += 1
        if (sentstruc[m] & FBOUNDARY) >= b_type or phonemes[m] == GEN_SIL:
            return count
    return count


__all__ = ["remaining_stresses_til"]
