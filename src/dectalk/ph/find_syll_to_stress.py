"""``find_syll_to_stress`` helper from ph_sort2.c.

Translated from ``src/dapi/src/ph/ph_sort2.c`` lines 125-169.

Invoked when the current clause contains no primary stresses. The
helper makes two passes to repair the deficit:

1. **Backward S2 promotion** (skipped for German). Walks from
   ``*locend - 1`` down to ``nstartphrase`` looking for the most
   recent secondary stress (``S2``); if found, upgrades it to
   ``S1`` in place and returns.
2. **Last-word vowel insertion**. If no ``S2`` was found, the
   function locates the last word boundary (``>= WBOUND``) at or
   before ``*locend``, then scans forward from that boundary
   inserting an ``S1`` marker before the first syllabic phoneme.
   ``insertphone`` shifts later symbols down; ``*locend`` is
   incremented to keep the caller's loop pointer aligned with the
   original end-of-clause position.

If neither pass succeeds the clause is left without a primary
stress — the C comment says "Else give up".
"""

from __future__ import annotations

from dectalk.include.phoneme_codes import S1, S2, WBOUND
from dectalk.kernel.ksd_t import KsdT
from dectalk.kernel.lang_codes import LANG_german
from dectalk.ph.dph_t import DphT
from dectalk.ph.insertphone import insertphone
from dectalk.ph.phoneme_features import FSYLL
from dectalk.ph.timing import phone_feature


def find_syll_to_stress(
    p_ksd_t: KsdT,
    p_dph_t: DphT,
    locend: list[int],
    nstartphrase: int,
) -> None:
    """Raise the last secondary stress or insert ``S1`` before the last vowel.

    Faithful translation of:

    .. code-block:: c

        static void find_syll_to_stress(LPTTS_HANDLE_T phTTS,
                                        short *locend,
                                        short nstartphrase) {
            short m, locbeg = 0;
            PKSD_T pKsd_t = phTTS->pKernelShareData;
            PDPH_T pDph_t = phTTS->pPHThreadData;
            if (pKsd_t->lang_curr != LANG_german) {
                for (m = *locend - 1; m >= nstartphrase; m--) {
                    if (pDph_t->symbols[m] == S2) {
                        pDph_t->symbols[m] = S1;
                        return;
                    }
                }
            }
            for (m = *locend - 1; m >= nstartphrase; m--) {
                if (pDph_t->symbols[m] >= WBOUND) {
                    locbeg = m;
                    break;
                }
            }
            for (m = locbeg; m < *locend; m++) {
                if ((phone_feature(pDph_t, pDph_t->symbols[m])
                     & FSYLL) IS_PLUS) {
                    insertphone(phTTS, m, S1);
                    (*locend)++;
                    return;
                }
            }
        }

    Args:
        p_ksd_t: Kernel shared-data struct (gates the S2-promotion
            pass on ``lang_curr`` and supplies the SPC chain to
            :func:`insertphone`).
        p_dph_t: PH thread state (mutated: ``symbols``, ``nsymbtot``,
            ``user_durs``, ``user_f0`` per :func:`insertphone`).
        locend: One-element list wrapping ``short *locend``. The
            value is *incremented* when ``insertphone`` runs to
            keep the caller's loop pointer aligned. Caller observes
            the new end via ``locend[0]``.
        nstartphrase: Phrase-start symbol index — backward scans
            terminate when ``m < nstartphrase``.
    """
    symbols = p_dph_t.symbols

    # Pass 1: backward S2 -> S1 promotion (English/French/Spanish/etc.,
    # but never for German per Dennis's note in the C source).
    if p_ksd_t.lang_curr != LANG_german:
        for m in range(locend[0] - 1, nstartphrase - 1, -1):
            if 0 <= m < len(symbols) and symbols[m] == S2:
                symbols[m] = S1
                return

    # Pass 2a: find the last word boundary (or earlier) before *locend.
    locbeg = 0
    for m in range(locend[0] - 1, nstartphrase - 1, -1):
        if 0 <= m < len(symbols) and symbols[m] >= WBOUND:
            locbeg = m
            break

    # Pass 2b: scan forward from locbeg for the first syllabic phoneme
    # and insert an S1 marker just before it.
    for m in range(locbeg, locend[0]):
        if m >= len(symbols):
            break
        if (phone_feature(symbols[m]) & FSYLL) != 0:
            insertphone(p_ksd_t, p_dph_t, m, S1)
            locend[0] += 1  # Move pointer in calling loop.
            return

    # Else give up — clause contains no primary stresses.


__all__ = ["find_syll_to_stress"]
