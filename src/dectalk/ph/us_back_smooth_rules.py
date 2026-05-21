"""``us_back_smooth_rules`` -- backward-smoothing helper from p_us_st1.c.

Translated from ``src/dapi/src/ph/p_us_st1.c`` line 888 (~380 lines).

Symmetric counterpart to :func:`us_forw_smooth_rules`. Called once
per parameter from :func:`phsettar`'s main loop after the per-parameter
target lookup. Decides ``bouval`` (boundary value at phone end) and
``durtran`` (transition duration) based on the combination of
current-segment + next-segment feature flags, plus phoneme-specific
tweaks. Writes ``np_param.tbacktr`` at the end.
"""

from __future__ import annotations

# ruff: noqa: PLR2004, SIM102 -- C-literal magic numbers and nested ifs kept
from typing import cast

from dectalk.include.usp_codes import (
    USP_CH,
    USP_DH,
    USP_EN,
    USP_F,
    USP_HX,
    USP_JH,
    USP_LL,
    USP_N,
    USP_P,
    USP_S,
    USP_SH,
    USP_TH,
    USP_V,
    USP_Z,
    USP_ZH,
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
    NF64MS,
    NF70MS,
    NF75MS,
    NF80MS,
    NF100MS,
    NF130MS,
)
from dectalk.ph.math_helpers import mlsh1
from dectalk.ph.numeric_constants import (
    AP,
    AV,
    B1,
    B2,
    B3,
    F1,
    F3,
    FEMALE,
    TILT,
)
from dectalk.ph.phoneme_features import (
    FNASAL,
    FOBST,
    FPLOSV,
    FSONCON,
    FSONOR,
    FSTOP,
    FSYLL,
    FVOICD,
)
from dectalk.ph.setloc import setloc
from dectalk.ph.timing import begtyp, endtyp
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.utterance_constants import GEN_SIL, NASAL_ZERO_BOUNDARY

_PARTYPE_AV_OR_AH: int = 0
_PARTYPE_NASAL_ZERO_FREQ: int = 1
_PARTYPE_FORM_FREQ: int = 3
_PARTYPE_FORM_BW: int = 4


def us_back_smooth_rules(  # noqa: PLR0912, PLR0915
    phTTS: TtsHandle,  # noqa: N803
    shrib: int,
    feacur: int,
    feanex: int,
    strucnex: int,
) -> None:
    """Determine backward-smoothing ``bouval`` / ``durtran`` / ``tbacktr``.

    Faithful translation of the C static helper.
    """
    p_dph_t = cast(DphT, phTTS.p_ph_thread_data)
    p_dphsettar = cast(DphSettarSt, p_dph_t.pSTphsettar)
    np_param = p_dph_t.param[p_dphsettar.np]

    par_type = p_dphsettar.par_type

    # The C source has a `goto endbsmo` in the AV_OR_AH branch; we
    # honour it with an early exit to the final clamp logic via a
    # local flag.
    skip_to_endbsmo = False

    if par_type == _PARTYPE_FORM_FREQ:
        # BACKWARD SMOOTH: F1, F2, F3
        if (feacur & FSONOR) != 0:
            p_dphsettar.durtran = NF45MS
            if (feacur & FSONCON) == 0:
                if (feanex & FSONCON) != 0:
                    # 1. Vowel-soncon trans, 75-25%.
                    p_dphsettar.bouval = (p_dphsettar.bouval + np_param.tarnex) >> 1
                    # F3 transitions slower esp for [r,l].
                    if p_dphsettar.np == F3:
                        p_dphsettar.durtran = NF64MS
                    # First formant jumps down 80 Hz in /l/.
                    if p_dphsettar.phonex == USP_LL and p_dphsettar.np == F1:
                        p_dphsettar.bouval += 80
                # 2. Vowel-[vowel/h]: trailing [h] tugs bouval.
                elif p_dphsettar.phonex == USP_HX:
                    p_dphsettar.bouval = (p_dphsettar.bouval + np_param.tarend) >> 1
            else:
                p_dphsettar.durtran = NF40MS
                if (feanex & FSONCON) == 0:
                    # 3. Soncon-vowel trans, 25-75%.
                    p_dphsettar.bouval = (p_dphsettar.bouval + np_param.tarend) >> 1
                    p_dphsettar.durtran = NF20MS
                # else: 4. Soncon-soncon transition; use default.

        # No backward smoothing if next phone is silence.
        if p_dphsettar.phonex == GEN_SIL:
            p_dphsettar.durtran = 0
        else:
            # 5. phcur=sonor, phonex=obst transition.
            setloc(
                phTTS,
                p_dph_t.nphone + 1,
                p_dph_t.nphone,
                "f",
                p_dph_t.nphone + 2,
                feanex,
            )
            # 6. phcur=obst, phonex=sonor transition.
            setloc(
                phTTS,
                p_dph_t.nphone,
                p_dph_t.nphone + 1,
                "i",
                p_dph_t.nphone - 1,
                feanex,
            )
            # Transitions slow inside obstruents.
            if (feacur & FOBST) != 0:
                p_dphsettar.durtran = NF30MS
                if p_dphsettar.np == F1:
                    p_dphsettar.durtran = NF20MS
                if (feacur & FPLOSV) != 0:
                    p_dphsettar.durtran = p_dph_t.durfon
                    # F1 += 100 at offset of voiceless plosive.
                    # SKIPPED on the libtts_us.so build target: the C source
                    # at p_us_st1.c lines 975-980 guards this block with
                    # ``#if (defined FAKE_HLSYN || !defined HLSYN)``, so the
                    # HLSYN build (ours) compiles it out.

            # Higher formant transitions slow inside a nasal.
            # SKIPPED entirely on the libtts_us.so build target: the C source
            # at p_us_st1.c lines 984-1015 wraps the whole block (including
            # the outer ``if (feacur & FNASAL)``, durtran=durfon, the F1 jump
            # to 0, and all F2/F3/M sub-branches) in
            # ``#if (defined FAKE_HLSYN || !defined HLSYN)``, so the HLSYN
            # build (ours) compiles it out. The HLSyn-area-based formant
            # adjustment in hlframe.c (un-ported; wait for Phase E) is the
            # HLSYN replacement for these rules.

        # Shrink tran dur inside sonor if sonor short.
        if (feacur & FOBST) == 0 and begtyp(p_dphsettar.phonex) != 4 and p_dphsettar.durtran > 0:
            p_dphsettar.durtran = mlsh1(p_dphsettar.durtran, shrib) + 1

    elif par_type == _PARTYPE_NASAL_ZERO_FREQ:
        # BACKWARD SMOOTH: FN
        p_dphsettar.durtran = 0
        if (feanex & FNASAL) != 0 and (feacur & FNASAL) == 0:
            p_dphsettar.bouval = NASAL_ZERO_BOUNDARY
            p_dphsettar.durtran = NF80MS
            if p_dphsettar.phonex == USP_EN:
                p_dphsettar.durtran = NF130MS

    elif par_type == _PARTYPE_FORM_BW:
        # BACKWARD SMOOTH: B1, B2, B3
        p_dphsettar.durtran = NF40MS
        if (feacur & FVOICD) != 0:
            # Glottis opens early before -voice C, widen B1.
            if p_dphsettar.np == B1 and (feanex & FVOICD) == 0:
                p_dphsettar.durtran = NF50MS
                # More increase for low vowels (F1 high).
                p_dphsettar.bouval = np_param.tarend + (p_dph_t.param[F1].tarcur >> 3)
                if p_dph_t.malfem == FEMALE:
                    p_dphsettar.durtran = NF100MS
        else:
            p_dphsettar.durtran = NF20MS

        # Treat boundary with silence.
        if p_dphsettar.phonex == GEN_SIL:
            p_dphsettar.bouval = np_param.tarend + ((B3 - p_dphsettar.np) * 50)
            p_dphsettar.durtran = NF50MS
        elif p_dphsettar.phcur == GEN_SIL:
            p_dphsettar.bouval = np_param.tarnex + ((B3 - p_dphsettar.np) * 50)
            p_dphsettar.durtran = NF50MS

        # BW1 widen to nasalize transition into next nasal.
        if (feanex & FNASAL) != 0:
            p_dphsettar.bouval = np_param.tarend
            if (
                p_dphsettar.np == B2
                and p_dphsettar.phonex in (USP_N, USP_EN)
                and endtyp(p_dphsettar.phcur) != 1
            ):
                p_dphsettar.bouval += 60
                p_dphsettar.durtran = NF60MS
            if p_dphsettar.np == B1:
                p_dphsettar.durtran = NF100MS
                p_dphsettar.bouval += 100

        # Nasals have constant bandwidths at target values.
        if (feacur & FNASAL) != 0:
            p_dphsettar.durtran = 0

    elif par_type == _PARTYPE_AV_OR_AH:
        # BACKWARD SMOOTH: AV, AP, A2..A6, AB, TILT
        # Onset detection: source intensity increasing.
        temp = np_param.tarnex - 10
        if p_dphsettar.bouval < temp:
            p_dphsettar.bouval = temp
            if p_dphsettar.phcur == GEN_SIL:
                p_dphsettar.durtran = NF70MS

        # Voicing: onset abrupt unless voiced fricative.
        if (
            p_dphsettar.np == AV
            and p_dphsettar.bouval < np_param.tarnex
            and p_dphsettar.phcur not in (USP_V, USP_DH, USP_JH, USP_ZH, USP_Z)
        ):
            p_dphsettar.durtran = 0
            # Voicebar dies out in a voiced plosive.
            if (feacur & FPLOSV) != 0 or p_dphsettar.phcur == USP_CH:
                if (feacur & FVOICD) != 0:
                    p_dphsettar.bouval = np_param.tarend - 3
                    p_dphsettar.durtran = NF45MS
                else:
                    # Do not allow prevoicing in a voiceless plosive.
                    p_dphsettar.bouval = 0
                skip_to_endbsmo = True

        if not skip_to_endbsmo:
            # If next nasal & curr voiced, set AV const.
            if (feanex & FNASAL) != 0 and (feacur & FVOICD) != 0:
                p_dphsettar.durtran = 0

            # If curr nasal and next voiced non-obst, AV const.
            if (feacur & FNASAL) != 0:
                if (
                    (feanex & FVOICD) != 0
                    and (feanex & FOBST) == 0
                    and (strucnex & FDUMMY_VOWEL) == 0
                ):
                    p_dphsettar.durtran = 0
                else:
                    p_dphsettar.durtran = NF40MS

            # Offset detection: source intensity decreasing.
            temp = np_param.tarend - 10
            # Plosive burst not attenuated during offset.
            if p_dphsettar.phcur >= USP_P:
                p_dphsettar.durtran = NF15MS
                if p_dphsettar.phcur < USP_CH:
                    temp = np_param.tarend

            if p_dphsettar.bouval < temp:
                p_dphsettar.bouval = temp - 3
                p_dphsettar.durtran = NF20MS

            # Voicing amp falls gradually at end of phrase.
            if p_dphsettar.np == AV:
                if p_dphsettar.bouval < temp or (
                    temp > 0 and p_dphsettar.np == AV and (strucnex & FDUMMY_VOWEL) != 0
                ):
                    p_dphsettar.bouval = temp + 3
                    if p_dphsettar.phonex == GEN_SIL or (strucnex & FDUMMY_VOWEL) != 0:
                        p_dphsettar.durtran = NF75MS
                elif p_dphsettar.np == AP:
                    # The C source compares np==&PAV then sets bouval from
                    # PAP.tarend - 6 in the else; this elif is dead under
                    # the outer `if (np == &PAV)` but preserved verbatim.
                    p_dphsettar.bouval = p_dph_t.param[AP].tarend - 6

            # No smoothing of source amps if next segment has burst.
            if p_dphsettar.phonex >= USP_P and ((feacur & FNASAL) == 0 or p_dphsettar.np != AV):
                p_dphsettar.durtran = 0

            # Onset of a vowel from voiceless open vocal tract is breathy.
            if p_dphsettar.np == AP:
                if p_dphsettar.phcur in (USP_F, USP_TH, USP_S, USP_SH):
                    if (feanex & FVOICD) != 0 and (feanex & FOBST) == 0:
                        p_dphsettar.bouval = 52
                        p_dphsettar.durtran = NF40MS
                # Offset of a vowel into silence is breathy.
                if (feacur & FSYLL) != 0 and p_dphsettar.phonex == GEN_SIL:
                    p_dphsettar.bouval = 52
                    p_dphsettar.durtran = NF130MS

            # BACKWARD SMOOTH: TILT
            if p_dphsettar.np == TILT:
                p_dphsettar.durtran = NF25MS
                if p_dphsettar.phonex == GEN_SIL:
                    p_dphsettar.bouval = np_param.tarend
                if p_dphsettar.phcur == GEN_SIL:
                    p_dphsettar.bouval = np_param.tarnex
                if (feanex & FSTOP) != 0 or (feacur & FSTOP) != 0:
                    p_dphsettar.durtran = 0
                # Long breathy offset into silence.
                if (feacur & FVOICD) != 0 and (feacur & FNASAL) == 0:
                    if p_dphsettar.phonex == GEN_SIL:
                        p_dphsettar.bouval = 15
                        p_dphsettar.durtran = NF130MS

    # endbsmo label: final clamps.
    p_dphsettar.durtran = min(p_dphsettar.durtran, NF130MS)
    p_dphsettar.durtran = min(p_dphsettar.durtran, p_dph_t.durfon)
    np_param.tbacktr = p_dph_t.durfon - p_dphsettar.durtran
    p_dphsettar.bouval = max(p_dphsettar.bouval, 0)


__all__ = ["us_back_smooth_rules"]
