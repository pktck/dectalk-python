"""``set_tglst`` helper from ph_drwt02.c.

Translated from ``src/dapi/src/ph/ph_drwt02.c`` lines 2270-2358.

Per-frame timer-and-trigger helper for the glottal-stop gesture
(``tglstp`` / ``tglstn``). Called from ``pht0draw`` once per frame
to:

1. Tick the segment-duration accumulator (``nframg`` / ``segdrg``).
2. When the current segment ends, advance to the next segment
   (``++npg``), cancel any in-progress glottal stop, and decide
   whether to schedule a glottal stop at the upcoming segment
   boundary (writing ``tglstn = segdrg`` or ``-200``).
3. When the gesture is mid-frame (frame 8 of an at-least-8-long
   segment, or the final frame), promote ``tglstn`` to ``tglstp``
   so the next pass starts the new gesture.

The decision rules consult phoneme features (``FVOWEL``, ``FSYLL``,
``FPLOSV``, ``FGLOTTAL``) and boundary flags (``FBOUNDARY``,
``FWBNEXT``, ``FVPNEXT``, ``FSTRESS_1``), plus per-phone exemptions
for the function-word vowels ``a`` and ``an`` and the diphthong
``/YU/`` (which Dectalk does *not* glottalise even at a strong
boundary).
"""

from __future__ import annotations

from dectalk.include.usp_codes import USP_AX, USP_DX, USP_EH, USP_N, USP_YU
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import (
    F_FUNC,
    FBOUNDARY,
    FFINALSYL,
    FMEDIALSYL,
    FSTRESS_1,
    FVPNEXT,
    FWBNEXT,
)
from dectalk.ph.phoneme_features import FGLOTTAL, FPLOSV, FSYLL, FVOWEL
from dectalk.ph.timing import phone_feature, place

_TGLST_CANCEL: int = -200
# Mid-segment promotion frame: the C source literally compares
# ``pDphsettar->nframg == 8`` (eight frames into the segment) before
# promoting ``tglstn`` into ``tglstp`` — a half-segment-ish trigger.
_TGLST_PROMOTE_FRAME: int = 8


def set_tglst(p_dph_t: DphT) -> None:  # noqa: PLR0912
    """Tick / trigger the glottal-stop gesture timer.

    Branch count exceeds Ruff's PLR0912 threshold; the cascade
    mirrors the C source's rule structure and splitting it would
    obscure per-line parity with ph_drwt02.c.

    Faithful translation of:

    .. code-block:: c

        static void set_tglst(PDPH_T pDph_t) {
            PDPHSETTAR_ST pDphsettar = pDph_t->pSTphsettar;
            if (pDphsettar->nframg >= pDphsettar->segdrg) {
                pDphsettar->nframg -= pDphsettar->segdrg;
                pDphsettar->segdrg = pDph_t->allodurs[++pDphsettar->npg];
                /* Cancel glottal stop gesture that occurred at last phone onset */
                if (pDphsettar->tglstp == 0)
                    pDphsettar->tglstp = -200;
                /* Start second half of glottal stop gesture */
                if (pDphsettar->tglstp > 0) {
                    pDphsettar->tglstp = 0;
                }
                /* Insert glottal stop after cur seg */
                pDphsettar->tglstn = -200;
                if (pDph_t->allofeats[pDphsettar->npg-1] & F_FUNC) {
                    // an
                    if (pDph_t->allophons[pDphsettar->npg] == USP_N
                        && pDph_t->allophons[pDphsettar->npg-1] == USP_EH
                        && (pDph_t->allofeats[pDphsettar->npg-1] & FBOUNDARY) >= FWBNEXT)
                            return;
                    // a
                    if (pDph_t->allophons[pDphsettar->npg] == USP_AX
                        && (pDph_t->allofeats[pDphsettar->npg] & FBOUNDARY) >= FWBNEXT)
                            return;
                }
                if (((phone_feature(pDph_t, pDph_t->allophons[pDphsettar->npg+1])
                      & FVOWEL) IS_PLUS)
                    && ((pDph_t->allofeats[pDphsettar->npg+1]
                         & (FMEDIALSYL & FFINALSYL)) IS_MINUS)
                    && ((pDph_t->allofeats[pDphsettar->npg]
                         & FBOUNDARY) >= FWBNEXT)
                    && (pDph_t->allophons[pDphsettar->npg+1] != USP_YU)) {
                    if ((phone_feature(pDph_t, pDph_t->allophons[pDphsettar->npg])
                         & FSYLL) IS_PLUS) {
                        if (((pDph_t->allophons[pDphsettar->npg]
                              == pDph_t->allophons[pDphsettar->npg+1])
                            && ((pDph_t->allofeats[pDphsettar->npg+1]
                                 & FSTRESS_1) IS_PLUS))
                            || ((pDph_t->allofeats[pDphsettar->npg]
                                 & FBOUNDARY) >= FVPNEXT)) {
                            pDphsettar->tglstn = pDphsettar->segdrg;
                        }
                    }
                    else if (((phone_feature(pDph_t,
                                pDph_t->allophons[pDphsettar->npg]) & FPLOSV) IS_MINUS)
                        && (pDph_t->allophons[pDphsettar->npg] != USP_DX)
                        && ((pDph_t->allofeats[pDphsettar->npg+1]
                             & FSTRESS_1) IS_PLUS)) {
                        // pDphsettar->tglstn = pDphsettar->segdrg;  (commented out)
                    }
                }
                if ((pDphsettar->npg + 1 <= pDph_t->nallotot)
                    && (place(pDph_t->allophons[pDphsettar->npg+1])
                        & FGLOTTAL) IS_PLUS) {
                    pDphsettar->tglstn = pDphsettar->segdrg;
                }
                if ((place(pDph_t->allophons[pDphsettar->npg]) & FGLOTTAL) IS_PLUS) {
                    pDphsettar->tglstn = pDphsettar->segdrg;
                }
            }
            /* Wait until current gl stop gesture over before setting time of next one */
            else if ((pDphsettar->nframg == 8)
                  || (pDphsettar->nframg == (pDphsettar->segdrg - 1))) {
                pDphsettar->tglstp = pDphsettar->tglstn;
            }
        }

    Notes on faithful detail:

    - ``IS_PLUS`` is C ``!= 0``; ``IS_MINUS`` is C ``== 0``.
    - The pre-increment ``allodurs[++npg]`` in C bumps ``npg``
      *before* the array read; the Python port mirrors this by
      incrementing first.
    - ``FMEDIALSYL & FFINALSYL`` is a literal bitwise-AND of the
      two constants (0o20 & 0o30 = 0o20). This looks like a C bug
      — the author likely meant ``FMEDIALSYL | FFINALSYL`` — but
      we preserve it for bit-parity.
    - The middle ``else if`` branch contains a commented-out
      assignment in the C source (see ``//pDphsettar->tglstn = ...``);
      we preserve the empty branch but it has no effect.
    - The ``USP_*`` constants mirror the C ``#define USP_N`` etc.
      values from ``ph_def.h``.
    - The ``pDphsettar->npg + 1 <= pDph_t->nallotot`` guard
      protects the ``allophons[npg+1]`` read in the FGLOTTAL test
      from running off the end of the allophone buffer.

    Args:
        p_dph_t: PH thread state (mutated in-place).
    """
    pdphsettar = p_dph_t.pSTphsettar
    if not isinstance(pdphsettar, DphSettarSt):
        return

    allodurs = p_dph_t.allodurs
    allophons = p_dph_t.allophons
    allofeats = p_dph_t.allofeats

    if pdphsettar.nframg >= pdphsettar.segdrg:
        pdphsettar.nframg -= pdphsettar.segdrg
        # ++npg — pre-increment, then index.
        pdphsettar.npg += 1
        npg = pdphsettar.npg
        if 0 <= npg < len(allodurs):
            pdphsettar.segdrg = allodurs[npg]

        # Cancel glottal stop gesture that occurred at last phone onset.
        if pdphsettar.tglstp == 0:
            pdphsettar.tglstp = _TGLST_CANCEL
        # Start second half of glottal stop gesture.
        if pdphsettar.tglstp > 0:  # noqa: PLR1730 — keep C `if x>0: x=0` shape for parity
            pdphsettar.tglstp = 0

        # Default: insert glottal stop after cur seg (will be flipped
        # to segdrg if any of the rules below fire).
        pdphsettar.tglstn = _TGLST_CANCEL

        # Bail-out cases for function-word vowels "a" and "an".
        if 0 <= npg - 1 < len(allofeats) and (allofeats[npg - 1] & F_FUNC) != 0:
            # "an" — N preceded by EH and a strong boundary on EH.
            if (
                0 <= npg < len(allophons)
                and 0 <= npg - 1 < len(allophons)
                and allophons[npg] == USP_N
                and allophons[npg - 1] == USP_EH
                and (allofeats[npg - 1] & FBOUNDARY) >= FWBNEXT
            ):
                return
            # "a" — AX with a strong boundary.
            if (
                0 <= npg < len(allophons)
                and 0 <= npg < len(allofeats)
                and allophons[npg] == USP_AX
                and (allofeats[npg] & FBOUNDARY) >= FWBNEXT
            ):
                return

        # Main glottal-stop-insertion rule. Triggers when the *next*
        # segment is a vowel, *not* in a medial/final syllable, the
        # current segment is followed by a word-or-stronger boundary,
        # and the next phone isn't the diphthong /YU/.
        next_phone_in_range = 0 <= npg + 1 < len(allophons)
        next_feat_in_range = 0 <= npg + 1 < len(allofeats)
        cur_feat_in_range = 0 <= npg < len(allofeats)
        cur_phone_in_range = 0 <= npg < len(allophons)
        if (
            next_phone_in_range
            and next_feat_in_range
            and cur_feat_in_range
            and (phone_feature(allophons[npg + 1]) & FVOWEL) != 0
            and (allofeats[npg + 1] & (FMEDIALSYL & FFINALSYL)) == 0
            and (allofeats[npg] & FBOUNDARY) >= FWBNEXT
            and allophons[npg + 1] != USP_YU
        ):
            # If current segment is itself a vowel, only fire when
            # current and next phones are identical (with stress on
            # the next) OR the current is followed by a phrase-or-
            # stronger boundary.
            if cur_phone_in_range and (phone_feature(allophons[npg]) & FSYLL) != 0:
                same_vowel_stressed = (
                    allophons[npg] == allophons[npg + 1] and (allofeats[npg + 1] & FSTRESS_1) != 0
                )
                strong_boundary = (allofeats[npg] & FBOUNDARY) >= FVPNEXT
                if same_vowel_stressed or strong_boundary:
                    pdphsettar.tglstn = pdphsettar.segdrg
            # Otherwise (current is a consonant): the C source has a
            # commented-out write here for the case of a non-plosive,
            # non-flap consonant followed by a primary-stressed
            # vowel. We preserve the branch but it has no effect.
            elif (
                cur_phone_in_range
                and (phone_feature(allophons[npg]) & FPLOSV) == 0
                and allophons[npg] != USP_DX
                and (allofeats[npg + 1] & FSTRESS_1) != 0
            ):
                # pdphsettar.tglstn = pdphsettar.segdrg  # commented out in C
                pass

        # Also glottalise when the *next* phone has a glottal place
        # of articulation (TQ, Q).
        if (
            npg + 1 <= p_dph_t.nallotot
            and 0 <= npg + 1 < len(allophons)
            and (place(allophons[npg + 1]) & FGLOTTAL) != 0
        ):
            pdphsettar.tglstn = pdphsettar.segdrg

        # And when the *current* phone has a glottal place of
        # articulation.
        if 0 <= npg < len(allophons) and (place(allophons[npg]) & FGLOTTAL) != 0:
            pdphsettar.tglstn = pdphsettar.segdrg

    # Mid-segment branch: promote tglstn to tglstp at frame 8 of an
    # at-least-8-long segment, or at the final frame.
    elif pdphsettar.nframg == _TGLST_PROMOTE_FRAME or pdphsettar.nframg == pdphsettar.segdrg - 1:
        pdphsettar.tglstp = pdphsettar.tglstn


__all__ = ["set_tglst"]
