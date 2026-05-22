# ruff: noqa: PLR2004, SIM102, SIM108, PLR5501, PLR1730 -- faithful translation of branchy C source
"""``gr_gettar`` -- German per-parameter target lookup from p_gr_st1.c.

Translated from ``src/dapi/src/ph/p_gr_st1.c`` line 85 (~330 lines).

``gr_gettar`` is the German sibling of :func:`us_gettar` -- the leaf
of the ``getbegtar`` / ``getendtar`` / ``gettar`` dispatch chain that
:func:`phsettar` walks for every parameter on every German phoneme. The
return value is the "raw" target before forward/backward smoothing
and coarticulation -- subsequent rules add to or override it.

The function branches on ``pDphsettar->par_type`` (the partyp entry
for the current parameter, as set by :func:`phsettar`):

- ``par_type > 2`` (form-frequency or bandwidth -- F1, F2, F3, B1,
  B2, B3): reads ``p_tar[phone + pphotr]`` then applies German-
  specific tweaks (``GRP_KH`` formant inheritance, F2 drop, F1
  fricative raise, B2/B3 special cases for /n/).
- ``par_type == 1`` (nasal-zero frequency -- FZ): German nasalised
  vowels (``GRP_AN``/``GRP_IM``/``GRP_UM``/``GRP_ON``) get 350;
  nasal murmur uses :data:`NASAL_ZERO_BOUNDARY` (370).
- ``par_type == 0`` (voicing/aspiration amplitude -- AV, AP): per-
  language /h/ and /kh/ aspiration; German uses two-level stress
  (FSTRESS_2) and a -7 dummy-vowel reduction (vs US's -12).
- ``par_type == 2`` (parallel formant amplitudes -- A2-A6, AB,
  TILT): German-specific TILT biases for /u/ and /l/, the GRP_DJ
  voiced-obstruent rule, and a 5 -> 1 begtypnex remap.
"""

from __future__ import annotations

from typing import cast

from dectalk.include.cmd_codes import PVALUE
from dectalk.include.grp_codes import (
    GR_TOT_ALLOPHONES,
    GRP_AN,
    GRP_DJ,
    GRP_EN,
    GRP_H,
    GRP_IH,
    GRP_IM,
    GRP_KH,
    GRP_L,
    GRP_N,
    GRP_ON,
    GRP_U,
    GRP_UM,
)
from dectalk.include.phoneme_codes import WBOUND
from dectalk.include.usp_codes import USP_Q
from dectalk.kernel.ksd_t import KsdT
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import (
    FDUMMY_VOWEL,
    FSTRESS,
    FSTRESS_2,
)
from dectalk.ph.get_phone import get_phone
from dectalk.ph.numeric_constants import (
    A2,
    AV,
    B2,
    B3,
    F1,
    F2,
    FEMALE,
    FZ,
    TILT,
)
from dectalk.ph.parameter_tables import partyp
from dectalk.ph.phoneme_features import (
    FNASAL,
    FOBST,
    FPLOSV,
    FSTOP,
    FSYLL,
    FVOICD,
)
from dectalk.ph.timing import begtyp, endtyp, phone_feature, ptram
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.utterance_constants import (
    GEN_SIL,
    NASAL_ZERO_BOUNDARY,
    NON_NASAL_ZERO,
)

# par_type encoding from ph_defs.h IS_* macros (same as us_gettar):
_PARTYPE_AV_OR_AH: int = 0
_PARTYPE_NASAL_ZERO_FREQ: int = 1
_PARTYPE_PARALLEL_FORM_AMP: int = 2

# German nasalised vowels (GRP_AN, GRP_IM, GRP_UM, GRP_ON) get FZ=350.
_GR_NASAL_VOWEL_FZ: int = 350


def gr_gettar(phTTS: TtsHandle, nphone_temp: int) -> int:  # noqa: N803, PLR0912, PLR0915 -- faithful 330-line C function
    """Resolve the German target for one parameter at one phone slot.

    Faithful translation of:

    .. code-block:: c

        short gr_gettar(LPTTS_HANDLE_T phTTS, int nphone_temp);

    Args:
        phTTS: Two-pointer engine handle. ``p_ph_thread_data`` must
            be a populated :class:`~dectalk.ph.dph_t.DphT` with
            ``pSTphsettar`` set and ``param[np]`` indexed by the
            caller; ``p_kernel_share_data`` must be a
            :class:`~dectalk.kernel.ksd_t.KsdT`. ``p_tar`` / ``p_amp``
            must already point to the German per-voice ROM tables
            (the table swap happens upstream in :func:`gettar`).
        nphone_temp: Index into ``allophons[]`` for the target phone.

    Returns:
        The raw target value (``short`` in C; an arbitrary-precision
        ``int`` here).
    """
    p_dph_t = cast(DphT, phTTS.p_ph_thread_data)
    p_ksd_t = cast(KsdT, phTTS.p_kernel_share_data)
    p_dphsettar = cast(DphSettarSt, p_dph_t.pSTphsettar)

    phlas_temp = get_phone(p_dph_t, nphone_temp - 1)
    phone_temp = get_phone(p_dph_t, nphone_temp)
    phnex_temp = get_phone(p_dph_t, nphone_temp + 1)

    # npar = pDphsettar->np - &PF1 -- pointer arithmetic over param[].
    npar = p_dphsettar.np - F1
    if p_dphsettar.np < FZ:
        pphotr = npar * GR_TOT_ALLOPHONES
    else:
        # No table row for PAP; subsequent parameters shift down by 1.
        pphotr = (npar - 1) * GR_TOT_ALLOPHONES

    p_dphsettar.par_type = partyp[npar]
    tartemp = 0

    p_tar = cast(list[int], p_dph_t.p_tar)

    if p_dphsettar.par_type > _PARTYPE_PARALLEL_FORM_AMP:
        # FORM_FREQ_OR_BW: F1, F2, F3, B1, B2, B3.

        # German /ch/ /ax/ allophone (GRP_KH) is a "big hammer" cheat:
        # it follows the formants of the *previous* vowel.
        if phone_temp == GRP_KH:
            phone_temp = phlas_temp

        tartemp = p_tar[(phone_temp & PVALUE) + pphotr]
        if tartemp < -1:
            # Diphthong sentinel: return verbatim for caller to deref.
            return tartemp

        # F2 for GRP_KH: drop by 600 Hz (only fires when phlas was KH).
        if npar == F2 - 1 and phone_temp == GRP_KH:
            tartemp -= 600

        # Fricatives have higher F1 if preceded by a vowel.
        if (
            npar == F1 - 1
            and (phone_feature(phone_temp) & FOBST) != 0
            and (phone_feature(phone_temp) & FSTOP) == 0
            and (phone_feature(phlas_temp) & FSYLL) != 0
        ):
            tartemp += 40

        # B2 of /n/ before non-front vowels: nudge target up.
        if phone_temp in (GRP_N, GRP_EN) and npar == B2 - 1:
            if begtyp(phnex_temp) != 1:
                tartemp += 60

        # B3 of /n/ before /i/: clamp to 800 Hz.
        if phone_temp == GRP_N and npar == B3 - 1:
            if phnex_temp == GRP_IH:
                tartemp = 800

    elif p_dphsettar.par_type == _PARTYPE_NASAL_ZERO_FREQ:
        # FZ: German nasalised vowels get 350; nasal murmur uses
        # NASAL_ZERO_BOUNDARY (370).
        tartemp = NON_NASAL_ZERO
        if phone_temp in (GRP_AN, GRP_IM, GRP_UM, GRP_ON):
            tartemp = _GR_NASAL_VOWEL_FZ
        elif (phone_feature(phone_temp) & FNASAL) != 0:
            tartemp = NASAL_ZERO_BOUNDARY

    elif p_dphsettar.par_type == _PARTYPE_AV_OR_AH:
        # AV or AP (npar == 7 for AV, 8 for AP relative to F1=1).
        if npar == AV - 1:
            tartemp = p_tar[(phone_temp & PVALUE) + pphotr]

            # Glottal stop at slow rates (C compares against USP_Q).
            if p_ksd_t.sprate < 100 and phone_temp == USP_Q:
                tartemp -= 30

            # Dummy vowel has less intensity (German uses -7).
            if (p_dph_t.allofeats[nphone_temp] & FDUMMY_VOWEL) != 0:
                tartemp -= 7

            # Reduce amplitudes if unstressed (improv330: two stress levels).
            if (p_dph_t.allofeats[nphone_temp] & FSTRESS_2) != 0:
                tartemp -= 1
            elif (p_dph_t.allofeats[nphone_temp] & FSTRESS) == 0:
                tartemp -= 2

            if tartemp < 0:
                tartemp = 0
            if tartemp:
                # EAB's "FIX IT LATER HELPME" hack: +5 to positive AV.
                tartemp += 5
        else:
            # AP: only /h/ and /kh/ have aspiration.
            if phone_temp == GRP_H:
                tartemp = 52
                if begtyp(phnex_temp) != 1:
                    tartemp = 55  # Stronger asp before +back
                if p_dph_t.allophons[p_dph_t.nphone + 1] == GEN_SIL:
                    tartemp -= 12
            elif phone_temp == GRP_KH:
                tartemp = 42
                if begtyp(phnex_temp) != 1:
                    tartemp = 44
            else:
                tartemp = 0

    elif p_dphsettar.par_type == _PARTYPE_PARALLEL_FORM_AMP:
        # PARALLEL_FORM_AMP: A2-A6, AB, TILT.
        p_amp = cast(list[int], p_dph_t.p_amp)
        if p_dphsettar.np != TILT:
            tartemp = ptram(phone_temp)
            if tartemp > 0:
                begtypnex = begtyp(phnex_temp) - 1
                if phnex_temp == GEN_SIL:
                    begtypnex = endtyp(phlas_temp) - 1
                # German remap: 5 -> 1 (vs US's 4 -> 2).
                if begtypnex == 5:
                    begtypnex = 1
                tartemp += npar - A2 + 1 + (6 * begtypnex)
                tartemp = p_amp[tartemp]

                # Word-final burst attenuation (German: less than US).
                if (p_dph_t.allofeats[nphone_temp + 1] & WBOUND) != 0:
                    if tartemp >= 4:
                        tartemp -= 1

                # Dummy-vowel burst attenuation.
                if (p_dph_t.allofeats[nphone_temp + 1] & FDUMMY_VOWEL) != 0:
                    if tartemp >= 4:
                        tartemp -= 4

        if p_dphsettar.np == TILT:
            # German-specific TILT rules.
            tartemp = 0
            if (phone_feature(phone_temp) & FNASAL) != 0:
                tartemp = 6
            if phone_temp == GEN_SIL:
                tartemp = 0
            elif (p_dph_t.allofeats[nphone_temp] & FDUMMY_VOWEL) != 0:
                tartemp = 20
            elif (phone_feature(phone_temp) & FOBST) != 0:
                tartemp = 7
                if (phone_feature(phone_temp) & FVOICD) != 0 and (
                    (phone_feature(phone_temp) & FPLOSV) != 0 or p_dphsettar.phcur == GRP_DJ
                ):
                    tartemp = 40  # Max tilt for [b, d, g]
            elif begtyp(phone_temp) == 1 or endtyp(phone_temp) == 1:
                if p_dph_t.malfem == FEMALE:
                    tartemp += 10

            if phone_temp == GRP_U:
                tartemp = 10
            if phone_temp == GRP_L:
                tartemp += 8

    return tartemp


__all__ = ["gr_gettar"]
