"""``init_med_final`` helper from ph_sort2.c.

Translated from ``src/dapi/src/ph/ph_sort2.c`` lines 57-107.

Classifies the *current* output syllable as one of ``FMONOSYL`` /
``FFIRSTSYL`` / ``FMEDIALSYL`` / ``FFINALSYL`` based on whether
other syllables precede and / or follow it within the current word,
then OR's the resulting class flag onto the current output
phoneme's ``sentstruc[]`` entry.

The classification walks two ranges:

1. Backward through ``phonemes[]`` from ``CURRPHONE - 1`` to ``1``,
   looking for a prior syllable in the same word. The walk stops
   at the first ``FBOUNDARY``-tagged ``sentstruc[m] >= FWBNEXT``
   (a word or stronger boundary). Any ``FSYLL`` phone seen along
   the way flips the classification from ``FMONOSYL`` to
   ``FFINALSYL``.
2. Forward through the *input* ``symbols[]`` stream from
   ``msym + 1``, looking for a following syllable in the same word.
   The walk stops at the first symbol in ``[WBOUND, EXCLAIM]``
   (a word or stronger boundary). Any ``FSYLL`` phone seen along
   the way upgrades the class:

   - ``FFINALSYL`` → ``FMEDIALSYL`` (syllables both before and
     after).
   - ``FMONOSYL`` → ``FFIRSTSYL`` (no priors but at least one
     follower).

   When the boundary is found, if the class is not still
   ``FMONOSYL`` (i.e. some classification has been made),
   :func:`add_feature` writes the class flag to the current output
   phoneme's slot.

Used by the PH sort pass during stress assignment to tag the
current syllable's position within its word, which downstream rules
(F0 hat targets, vowel reduction, etc.) consult.
"""

from __future__ import annotations

from dectalk.include.phoneme_codes import EXCLAIM, WBOUND
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import (
    FBOUNDARY,
    FFINALSYL,
    FFIRSTSYL,
    FMEDIALSYL,
    FMONOSYL,
    FWBNEXT,
)
from dectalk.ph.make_phone import add_feature
from dectalk.ph.phoneme_features import FSYLL
from dectalk.ph.timing import phone_feature


def init_med_final(p_dph_t: DphT, msym: int) -> None:
    """Classify and tag the current syllable's word-position.

    Faithful translation of:

    .. code-block:: c

        static void init_med_final(LPTTS_HANDLE_T phTTS, short msym) {
            PDPH_T pDph_t = phTTS->pPHThreadData;
            short m, sylltype;

            sylltype = FMONOSYL;  /* Assume curr word is monosyllabic */

            /* Examine output string to see if any sylls at beg. of word */
            for (m = CURRPHONE - 1; m > 0; m--) {
                if ((pDph_t->sentstruc[m] & FBOUNDARY) >= FWBNEXT) {
                    break;          /* Beginning of word found */
                }
                else if ((phone_feature(pDph_t, pDph_t->phonemes[m])
                          & FSYLL) IS_PLUS) {
                    sylltype = FFINALSYL;
                }
            }
            /* Examine input string for any sylls in remainder of word */
            for (m = msym + 1; m < pDph_t->nsymbtot; m++) {
                if ((pDph_t->symbols[m] >= WBOUND)
                 && (pDph_t->symbols[m] <= EXCLAIM)) {
                    if (sylltype != FMONOSYL) {
                        add_feature(pDph_t, sylltype,
                                    (short)(CURRPHONE));
                    }
                    return;
                }
                else if ((phone_feature(pDph_t, pDph_t->symbols[m])
                          & FSYLL) IS_PLUS) {
                    if (sylltype == FFINALSYL)
                        sylltype = FMEDIALSYL;
                    if (sylltype == FMONOSYL)
                        sylltype = FFIRSTSYL;
                }
            }
        }

    Notes on faithful detail:

    - ``CURRPHONE`` is the ``ph_sort.c`` per-file macro
      ``pDph_t->nphonetot - 1``.
    - The first loop reads from the **output** stream
      (``phonemes`` / ``sentstruc``); the second reads from the
      **input** stream (``symbols``).
    - The backward loop's exclusive lower bound (``m > 0``)
      preserves the C source's off-by-one: index 0 is never
      inspected.
    - The forward loop's range check ``[WBOUND, EXCLAIM]``
      includes all word-or-stronger boundary codes (111..118).
    - ``IS_PLUS`` is the C ``!= 0`` macro.
    - The body falls through silently (no ``add_feature``) if the
      forward loop reaches ``nsymbtot`` without seeing a boundary —
      matching the C source.

    Args:
        p_dph_t: PH thread state.
        msym: Index of the current input symbol — forward scan
            starts from ``msym + 1``.
    """
    sylltype = FMONOSYL  # Assume current word is monosyllabic.

    # Walk backward through output stream looking for prior syllable.
    sentstruc = p_dph_t.sentstruc
    phonemes = p_dph_t.phonemes
    currphone = p_dph_t.nphonetot - 1
    for m in range(currphone - 1, 0, -1):
        # Boundary check — bail out when we cross a word boundary.
        if (
            sentstruc is not None
            and 0 <= m < len(sentstruc)
            and (sentstruc[m] & FBOUNDARY) >= FWBNEXT
        ):
            break
        # FSYLL on a prior phone means this isn't the first syllable.
        if (
            phonemes is not None
            and 0 <= m < len(phonemes)
            and (phone_feature(phonemes[m]) & FSYLL) != 0
        ):
            sylltype = FFINALSYL

    # Walk forward through input stream looking for following syllable.
    symbols = p_dph_t.symbols
    for m in range(msym + 1, p_dph_t.nsymbtot):
        if m >= len(symbols):
            break
        sym = symbols[m]
        if WBOUND <= sym <= EXCLAIM:
            # Found the next word-or-stronger boundary — commit.
            if sylltype != FMONOSYL:
                add_feature(p_dph_t, sylltype, currphone)
            return
        # FSYLL on a following phone upgrades the classification.
        if (phone_feature(sym) & FSYLL) != 0:
            if sylltype == FFINALSYL:
                sylltype = FMEDIALSYL
            if sylltype == FMONOSYL:
                sylltype = FFIRSTSYL


__all__ = ["init_med_final"]
