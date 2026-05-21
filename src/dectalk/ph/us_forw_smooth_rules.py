"""``us_forw_smooth_rules`` -- forward-smoothing helper from p_us_st1.c.

Translated from ``src/dapi/src/ph/p_us_st1.c`` line 493 (~370 lines).

Called once per parameter from :func:`phsettar`'s main loop after
the per-parameter target lookup. Decides ``bouval`` (boundary value
at phone start) and ``durtran`` (transition duration) based on the
combination of previous-segment + current-segment feature flags,
plus phoneme-specific tweaks.

Branches:

- ``par_type == FORM_FREQ`` (F1, F2, F3): big tree on sonorant /
  obstruent / nasal transitions, with :func:`setloc` calls for the
  obstruent-sonorant locus, USP_HX / USP_LL / USP_R / USP_N /
  USP_EN / USP_M phoneme-specific corrections, and a final shrink
  of the transition duration via :func:`mlsh1` if the current
  segment is a short sonorant.
- ``par_type == NASAL_ZERO_FREQ`` (FZ): jumps to NASAL_ZERO_BOUNDARY
  with NF80MS transition when leaving a nasal.
- ``par_type == FORM_BW`` (B1, B2, B3): default NF40MS, with
  silence-boundary cushion, nasal-trail widening on B1/B2, and a
  zero-transition clamp inside a current nasal segment.
- ``par_type == AV_OR_AH`` (AV, AP): onset/offset detection,
  voicing-gradient rules, plosive-onset abruptness, breathy offset
  into voiceless openings, CH/JH gradual A3 buildup, TILT jump
  near stops/silence.

Final clamp: ``durtran`` capped at ``min(durfon, NF130MS)``,
``bouval`` capped at zero from below.
"""

from __future__ import annotations

# ruff: noqa: SIM102 -- C-literal magic numbers and branching kept
from typing import cast

from dectalk.include.usp_codes import (
    USP_CH,
    USP_EN,
    USP_F,
    USP_HX,
    USP_JH,
    USP_LL,
    USP_N,
    USP_R,
    USP_S,
    USP_SH,
    USP_TH,
)
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import FDUMMY_VOWEL
from dectalk.ph.frame_counts import (
    NF15MS,
    NF20MS,
    NF25MS,
    NF30MS,
    NF40MS,
    NF45MS,
    NF50MS,
    NF60MS,
    NF70MS,
    NF80MS,
    NF100MS,
    NF130MS,
)
from dectalk.ph.math_helpers import mlsh1
from dectalk.ph.numeric_constants import A3, AP, AV, B1, B2, B3, F1, TILT
from dectalk.ph.param_indices import OUT_TLT
from dectalk.ph.phoneme_features import (
    FNASAL,
    FOBST,
    FPLOSV,
    FSONCON,
    FSONOR,
    FSTOP,
    FVOICD,
)
from dectalk.ph.setloc import setloc
from dectalk.ph.sonor_classes import OBSTRUENT
from dectalk.ph.timing import begtyp, endtyp, phone_feature
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.utterance_constants import GEN_SIL, NASAL_ZERO_BOUNDARY

_PARTYPE_AV_OR_AH: int = 0
_PARTYPE_NASAL_ZERO_FREQ: int = 1
_PARTYPE_FORM_FREQ: int = 3
_PARTYPE_FORM_BW: int = 4


def us_forw_smooth_rules(  # noqa: PLR0912, PLR0915
    phTTS: TtsHandle,  # noqa: N803
    shrif: int,
    pholas: int,
    fealas: int,
    feacur: int,
    struclas: int,
    struccur: int,
    feanex: int,
) -> None:
    """Determine forward-smoothing ``bouval`` / ``durtran``.

    Faithful translation of the C static helper. Writes
    ``p_dphsettar.bouval`` and ``p_dphsettar.durtran``.

    Args:
        phTTS: Two-pointer engine handle.
        shrif: Forward-transition shrink coefficient (from
            :func:`init_variables`).
        pholas: Previous phone code.
        fealas: Feature bitmask of the previous phone.
        feacur: Feature bitmask of the current phone.
        struclas: Allofeats of the previous phone.
        struccur: Allofeats of the current phone.
        feanex: Feature bitmask of the next phone.
    """
    p_dph_t = cast(DphT, phTTS.p_ph_thread_data)
    p_dphsettar = cast(DphSettarSt, p_dph_t.pSTphsettar)
    np_param = p_dph_t.param[p_dphsettar.np]

    par_type = p_dphsettar.par_type

    if par_type == _PARTYPE_FORM_FREQ:
        # FORWARD SMOOTH: F1, F2, F3
        # 0. Use default values for obst-obst transition
        if (feacur & FSONOR) != 0:
            if (feacur & FSONCON) == 0:
                p_dphsettar.durtran = NF45MS
                if (fealas & FSONCON) != 0:
                    # 1. Soncon-vowel transition, use 25-75% rule
                    p_dphsettar.bouval = (p_dphsettar.bouval + np_param.tarlas) >> 1
                    # Make F1 discontinuous for light /l/
                    if pholas == USP_LL and p_dphsettar.np == F1:
                        p_dphsettar.bouval += 80
                    # Make F3 & F2 transitions slower out of /r/
                    if pholas == USP_R and p_dphsettar.np != F1:
                        p_dphsettar.durtran = NF70MS
                # 2. Vowel-[vowel/h] transition; [h] init val tugged
                elif p_dphsettar.phcur == USP_HX:
                    p_dphsettar.bouval = (p_dphsettar.bouval + np_param.tarlas) >> 1
            # phcur is a sonorant conson
            elif (fealas & FSONCON) == 0:
                # 3. Vowel-soncon trans, use 75-25% rule
                p_dphsettar.bouval = (p_dphsettar.bouval + np_param.tarcur) >> 1
                p_dphsettar.durtran = NF30MS
            else:
                # 4. Soncon-soncon transition
                p_dphsettar.durtran = NF30MS

        # Bound value = previous target if current phone is sil.
        if p_dphsettar.phcur == GEN_SIL:
            if p_dph_t.nphone > 1:
                p_dphsettar.bouval = np_param.tarlas
            else:
                p_dphsettar.bouval = np_param.tarnex
            p_dphsettar.durtran = p_dph_t.durfon
        else:
            # 5. pholas=obst, phcur=sonor transition.
            setloc(
                phTTS,
                p_dph_t.nphone - 1,
                p_dph_t.nphone,
                "i",
                p_dph_t.nphone - 2,
                feanex,
            )
            # 6. pholas=sonor, phcur=obst transition.
            setloc(
                phTTS,
                p_dph_t.nphone,
                p_dph_t.nphone - 1,
                "f",
                p_dph_t.nphone + 1,
                feanex,
            )
            # Dummy vowel for final plosive release into silence: skipped
            # (the C source has a comment-out block here).

            # F1 += 100 at onset of voiceless plosive release.
            # SKIPPED on the libtts_us.so build target: the C source
            # at p_us_st1.c lines 587-595 guards this block with
            # ``#if (defined FAKE_HLSYN || !defined HLSYN)``, so the
            # HLSYN build (ours) compiles it out. The HLSyn-area-
            # based formant adjustment in hlframe.c (also un-ported)
            # is the C source's HLSYN replacement for this rule.

            # Transitions modified inside obstruents
            if (feacur & FOBST) != 0:
                p_dphsettar.durtran = NF30MS
                if p_dphsettar.np == F1:
                    p_dphsettar.durtran = NF20MS
                # Plosive transitions consume the full duration
                if (feacur & FPLOSV) != 0:
                    p_dphsettar.durtran = p_dph_t.durfon

            # Higher formant transitions slow inside a nasal. The C
            # source's "Lower F2 & F3 of [n]/[m] nasal murmur" sub-
            # branches below the outer if are FAKE_HLSYN-guarded
            # (p_us_st1.c lines 618-636) and SKIPPED on the HLSYN
            # build target. The outer if + F1-jump-to-0 is
            # unconditional in C, so it stays.
            if (feacur & FNASAL) != 0:
                p_dphsettar.durtran = p_dph_t.durfon
                # Except F1, which jumps to value above FNZRO
                if p_dphsettar.np == F1:
                    p_dphsettar.durtran = 0

        # Shrink transition dur inside sonor if sonor short.
        if (feacur & FOBST) == 0 and endtyp(pholas) != OBSTRUENT and p_dphsettar.durtran > 0:
            p_dphsettar.durtran = mlsh1(p_dphsettar.durtran, shrif) + 1

    elif par_type == _PARTYPE_NASAL_ZERO_FREQ:
        # FORWARD SMOOTH: FN (nasal-zero frequency)
        p_dphsettar.durtran = 0
        if (fealas & FNASAL) != 0 and (feacur & FNASAL) == 0:
            p_dphsettar.bouval = NASAL_ZERO_BOUNDARY
            p_dphsettar.durtran = NF80MS

    elif par_type == _PARTYPE_FORM_BW:
        # FORWARD SMOOTH: B1, B2, B3
        p_dphsettar.durtran = NF40MS

        # Widen first formant bw if preceding seg voiceless
        if (feacur & FVOICD) != 0:
            if p_dphsettar.np == B1 and (fealas & FVOICD) == 0:
                p_dphsettar.durtran = NF50MS
                # More increase for low vowels (F1 high)
                p_dphsettar.bouval = np_param.tarcur + (p_dph_t.param[F1].tarcur >> 3)
        else:
            p_dphsettar.durtran = NF20MS

        # Treat boundary with silence
        if pholas == GEN_SIL:
            p_dphsettar.bouval = np_param.tarcur + ((B3 - p_dphsettar.np) * 50)
            p_dphsettar.durtran = NF50MS
        elif p_dphsettar.phcur == GEN_SIL:
            p_dphsettar.bouval = np_param.tarlas + ((B3 - p_dphsettar.np) * 50)
            if (
                (phone_feature(p_dph_t.allophons[p_dph_t.nphone - 2]) & FVOICD) == 0
                and (struclas & FDUMMY_VOWEL) != 0
                and p_dphsettar.np == B1
            ):
                p_dphsettar.bouval = 300  # Kluge to avoid discontinuity
            p_dphsettar.durtran = NF50MS

        # BW1 widen, to nasalize transition out of previous nasal
        if (fealas & FNASAL) != 0:
            p_dphsettar.bouval = np_param.tarcur  # B2,B3 not influenced by nasal
            # Except F2 of [n], which is wider in a non-front vowel
            if (
                p_dphsettar.np == B2
                and pholas in (USP_N, USP_EN)
                and begtyp(p_dphsettar.phcur) != 1
            ):
                p_dphsettar.bouval += 60
                p_dphsettar.durtran = NF60MS
            if p_dphsettar.np == B1:
                p_dphsettar.durtran = NF100MS
                p_dphsettar.bouval += 70

        # Nasals have constant bandwidths at target values
        if (feacur & FNASAL) != 0:
            p_dphsettar.durtran = 0

    elif par_type == _PARTYPE_AV_OR_AH:
        # FORWARD SMOOTH: AV, AP, A2..A6, AB, TILT (the C source
        # lumps PARALLEL_FORM_AMP into this elif via a commented-out
        # condition; we follow suit and reach here for AV/AP only).
        # Default bouval is average of tarcur & tarend.

        # Onset detection: plosive or large source intensity increase.
        temp = np_param.tarcur - 10
        if p_dphsettar.bouval < temp or (fealas & FPLOSV) != 0 or pholas == USP_JH:
            p_dphsettar.bouval = temp
            if (feacur & FOBST) == 0:
                p_dphsettar.durtran = NF20MS
            # Voicing is special
            if p_dphsettar.np == AV:
                # Gradual buildup of voicing
                if pholas == GEN_SIL:
                    if (feacur & FVOICD) != 0:
                        p_dphsettar.durtran = NF45MS
                        p_dphsettar.bouval -= 8
                # Obstruent voicing onset is abrupt
                if (fealas & FOBST) != 0:
                    p_dphsettar.bouval = temp + 6
                # Plosive onset is abrupt (used mainly for [bdg])
                if (fealas & FPLOSV) != 0:
                    p_dphsettar.bouval = np_param.tarcur - 5

        # If last nasal, and source amp increased, abrupt onset.
        if (fealas & FNASAL) != 0 and (feacur & FVOICD) != 0:
            p_dphsettar.durtran = 0

        # Voicing source amp const in intervocalic nasal.
        if (feacur & FNASAL) != 0:
            if (fealas & FVOICD) != 0:
                if p_dphsettar.np == AV:
                    p_dphsettar.durtran = 0

        # Offset detection: source intensity decreasing.
        temp = np_param.tarlas - 10
        if p_dphsettar.bouval < temp:
            # Reduce bouval by 3 dB because bval time is onset of next phoneme.
            p_dphsettar.bouval = temp - 3
            # Source amplitudes fall gradually into silence.
            if p_dphsettar.phcur == GEN_SIL:
                p_dphsettar.durtran = NF70MS
            # Except voicing offset is abrupt.
            if p_dphsettar.np == AV:
                p_dphsettar.durtran = 0

        # Build up A3 gradually in [CH, JH].
        if p_dphsettar.np == A3:
            if p_dphsettar.phcur in (USP_CH, USP_JH):
                p_dphsettar.durtran = p_dph_t.durfon - NF15MS
                p_dphsettar.bouval = np_param.tarcur - 30

        # Offset of a vowel into voiceless open vocal tract is breathy.
        if p_dphsettar.np == AP:
            if p_dphsettar.phcur in (GEN_SIL, USP_F, USP_TH, USP_S, USP_SH):
                if (fealas & FVOICD) != 0 and (fealas & FOBST) == 0:
                    if p_dphsettar.phcur == GEN_SIL:
                        p_dphsettar.bouval = 52
                        p_dphsettar.durtran = NF80MS
                    else:
                        p_dphsettar.bouval = 48
                        p_dphsettar.durtran = NF45MS

        # FORWARD SMOOTH: TILT — jumps to target near stops/silence.
        if p_dphsettar.np == TILT:
            p_dphsettar.durtran = NF25MS
            if pholas == GEN_SIL:
                p_dphsettar.bouval = np_param.tarcur
            if p_dphsettar.phcur == GEN_SIL:
                # Reach into par buffer for actual previous value.
                p_dphsettar.bouval = p_dph_t.parstochip[OUT_TLT]
            if (fealas & FSTOP) != 0 or (feacur & FSTOP) != 0:
                p_dphsettar.durtran = 0

    # Truncate tran dur if exceeds duration of current phone.
    p_dphsettar.durtran = min(p_dphsettar.durtran, p_dph_t.durfon)
    # Or 20-frame absolute cap.
    p_dphsettar.durtran = min(p_dphsettar.durtran, NF130MS)
    # Do not allow amplitude value to go below zero.
    p_dphsettar.bouval = max(p_dphsettar.bouval, 0)


__all__ = ["us_forw_smooth_rules"]
