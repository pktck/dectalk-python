"""``set_tglst`` helper from ph_drwt01.c (active variant).

Translated from ``src/dapi/src/ph/ph_drwt01.c`` lines 3118-3202 — the
**second** ``set_tglst`` definition, the one the active US
``pht0draw`` (ph_drwt01.c:2381, non-HLSYN ``OLD_INTONATION_AND_TIMING``
build) calls at line 2777. (The first definition at line 2015 belongs
to the NWSNOAA/UK variant; the ``ph_drwt02.c:2270`` definition this
module previously mirrored is the HLSYN build's.)

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
``FWBNEXT``, ``FVPNEXT``, ``FSTRESS_1``), plus an exemption for the
diphthong ``/YU/`` (which DECtalk does *not* glottalise even at a
strong boundary).

Differences vs the HLSYN ``ph_drwt02.c:2270`` variant this module
previously carried (issue #297; both mattered on real prompts):

- **No function-word "a"/"an" bail-outs.** The ``F_FUNC`` early
  ``return`` block is HLSYN-only code; the active build has no such
  exemption.
- **The consonant branch is live.** For a non-plosive, non-flap
  consonant followed by a primary-stressed vowel across a word
  boundary, the active build *does* schedule the gesture
  (``tglstn = segdrg``); the HLSYN file carries that assignment
  commented out. (E.g. the letter boundary in ``MRI`` — M into
  primary-stressed AR — glottalises in the shipped binary.)
"""

from __future__ import annotations

from dectalk.include.usp_codes import USP_DX, USP_YU
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import (
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


def set_tglst(p_dph_t: DphT) -> None:
    """Tick / trigger the glottal-stop gesture timer.

    Branch count exceeds Ruff's PLR0912 threshold; the cascade
    mirrors the C source's rule structure and splitting it would
    obscure per-line parity with ph_drwt01.c.

    Faithful translation of the active variant (ph_drwt01.c:3118,
    ``ENGLISH`` defined, ``GERMAN`` undefined):

    .. code-block:: c

        static void set_tglst (PDPH_T pDph_t) {
            PDPHSETTAR_ST pDphsettar = pDph_t->pSTphsettar;
            if (pDphsettar->nframg >= pDphsettar->segdrg) {
                pDphsettar->nframg -= pDphsettar->segdrg;
                pDphsettar->segdrg = pDph_t->allodurs[++(pDphsettar->npg)];
                /* Cancel glottal stop gesture that occurred at last phone onset */
                if (pDphsettar->tglstp == 0)
                    pDphsettar->tglstp = -200;
                /* Start second half of glottal stop gesture */
                if (pDphsettar->tglstp > 0)
                    pDphsettar->tglstp = 0;
                /* BATS 674 EAB 5/13/98 This code needs to be outside of ifdef */
                pDphsettar->tglstn = -200;
                /* Insert glottal stop after cur seg */
                if (((phone_feature(pDph_t, pDph_t->allophons[pDphsettar->npg + 1])
                      & FVOWEL) IS_PLUS)
                    && ((pDph_t->allofeats[pDphsettar->npg + 1]
                         & (FMEDIALSYL & FFINALSYL)) IS_MINUS)
                    && ((pDph_t->allofeats[pDphsettar->npg]
                         & FBOUNDARY) >= FWBNEXT)
                    && (pDph_t->allophons[pDphsettar->npg + 1] != USP_YU)) {
                    /* If cur seg is vowel, don't do it unless vowel ident, or pbound */
                    if ((phone_feature(pDph_t, pDph_t->allophons[pDphsettar->npg])
                         & FSYLL) IS_PLUS) {
                        if (((pDph_t->allophons[pDphsettar->npg]
                              == pDph_t->allophons[pDphsettar->npg + 1])
                            && ((pDph_t->allofeats[pDphsettar->npg + 1]
                                 & FSTRESS_1) IS_PLUS))
                            || ((pDph_t->allofeats[pDphsettar->npg]
                                 & FBOUNDARY) >= FVPNEXT)) {
                            pDphsettar->tglstn = pDphsettar->segdrg;
                        }
                    }
                    /* If next segment primary stressed,
                     * and if curr seg a consonant other than a plosive, do it
                     */
                    else if (((phone_feature(pDph_t,
                                pDph_t->allophons[pDphsettar->npg]) & FPLOSV) IS_MINUS)
                        && (pDph_t->allophons[pDphsettar->npg] != USP_DX)
                        && ((pDph_t->allofeats[pDphsettar->npg + 1]
                             & FSTRESS_1) IS_PLUS)) {
                        pDphsettar->tglstn = pDphsettar->segdrg;
                    }
                }
                /* And at beginning and end of glottalized segs TQ and Q */
                if ((us_place[pDph_t->allophons[pDphsettar->npg + 1] & PVALUE]
                     & FGLOTTAL) IS_PLUS) {
                    pDphsettar->tglstn = pDphsettar->segdrg;
                }
                if ((us_place[pDph_t->allophons[pDphsettar->npg] & PVALUE]
                     & FGLOTTAL) IS_PLUS) {
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
    - The consonant ``else if`` branch is **live** in the active
      ph_drwt01.c variant (the HLSYN ph_drwt02.c carries the same
      assignment commented out — the previous wrong-variant port
      never glottalised consonant→stressed-vowel word onsets).
    - The active variant has **no** function-word "a"/"an" early
      returns (those are ph_drwt02.c-only).
    - The C reads ``allophons[npg + 1]`` unguarded; the Python port
      adds list-bounds guards so a one-past-end walk reads the
      zero-filled tail of the preallocated arrays instead of
      raising ``IndexError`` (and never negative-indexes).

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
            # Otherwise (current is a consonant): if the next segment
            # is primary-stressed and the current is a non-plosive,
            # non-flap consonant, schedule the gesture. LIVE in the
            # active ph_drwt01.c variant (ph_drwt02.c carries this
            # assignment commented out — the old wrong-variant port
            # silently skipped it; issue #297, e.g. the M→AR letter
            # boundary in "MRI").
            elif (
                cur_phone_in_range
                and (phone_feature(allophons[npg]) & FPLOSV) == 0
                and allophons[npg] != USP_DX
                and (allofeats[npg + 1] & FSTRESS_1) != 0
            ):
                pdphsettar.tglstn = pdphsettar.segdrg

        # Also glottalise when the *next* phone has a glottal place
        # of articulation (TQ, Q). The active C indexes allophons
        # [npg + 1] unguarded; the list-bounds check below only
        # prevents an IndexError past the preallocated tail.
        if 0 <= npg + 1 < len(allophons) and (place(allophons[npg + 1]) & FGLOTTAL) != 0:
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
