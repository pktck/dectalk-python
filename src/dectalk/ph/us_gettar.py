# ruff: noqa: PLR2004, SIM102, SIM108, SIM114, PLR5501, PLR1730 -- faithful translation of branchy C source
"""``us_gettar`` -- US-English per-parameter target lookup from p_us_st0.c.

Translated from ``src/dapi/src/ph/p_us_st0.c`` line 67 (~240 lines).

**Variant note (issue #269).** ``ph_sttr1.c`` picks the US settar
implementation via ``#if defined(ENGLISH_US) && defined(OLD_SETTAR)``;
the active klsyn build (``dectalkf_klsyn.h`` defines ``OLD_SETTAR``
whenever ``VOICE_ROM_DECTALK_1996M_43F`` is selected) compiles
``p_us_st0.c``, NOT ``p_us_st1.c``. An earlier port of this module
followed p_us_st1.c and inherited five wrong-variant behaviours: the
removed ``tartemp == -1`` fallback chain, ``-12`` dummy-vowel AV
reduction (st0: ``-7``), ``56`` HX aspiration before back vowels
(st0: ``60``), ``10`` dummy-vowel TILT (st0: ``20``), and a front-
vowel TILT bias of ``+6``-else-``+3`` with no sex split (st0:
``+6`` female / ``+3`` male, nothing otherwise).

``us_gettar`` resolves the target value of one Klatt voice parameter
for one phone position in a clause. It is the leaf of the
``getbegtar`` / ``getendtar`` / ``gettar`` dispatch chain that
:func:`phsettar` walks for every parameter on every phoneme. The
return value is the "raw" target before forward/backward smoothing
and coarticulation -- subsequent rules add to or override it.

The function branches on ``pDphsettar->par_type`` (the partyp entry
for the current parameter, as set by :func:`phsettar`):

- ``par_type > 2`` (form-frequency or bandwidth — F1, F2, F3, B1,
  B2, B3): reads ``p_tar[phone + pphotr]`` then applies four
  position/phoneme-specific tweaks (vowel-fricative F1 raise,
  ``USP_N``/``USP_EN`` B2 nudge before non-front-vowel,
  ``USP_N``/``USP_EN``/``USP_NX`` B3 clamp adjacent to
  high-front vowels).
- ``par_type == 1`` (nasal-zero frequency — FZ): ``NASAL_ZERO_CONS``
  during a nasal murmur, else ``NON_NASAL_ZERO``.
- ``par_type == 0`` (voicing/aspiration amplitude — AV, AP): reads
  ``p_tar`` for AV with phoneme-specific corrections (glottal-stop
  attenuation at slow rates, dummy-vowel reduction, plosive
  devoicing if previous segment is voiceless, ``USP_HX`` voicing
  rules, unstressed-segment reduction). AP is 0 except for
  ``USP_HX`` (53, or 56 before back vowels).
- ``par_type == 2`` (parallel formant amplitudes — A2-A6, AB, TILT):
  reads ``ptram``-indexed ``p_amp`` entries based on the next-phone
  beginning type, with dummy-vowel correction. TILT has its own
  small switch with several feature-driven biases.

The function reads (but does not write) per-parameter state through
``pDphsettar->np`` (current parameter index, ``F1``..``TILT``).
"""

from __future__ import annotations

from typing import cast

from dectalk.include.cmd_codes import PVALUE
from dectalk.include.phoneme_codes import US_TOT_ALLOPHONES
from dectalk.include.usp_codes import (
    USP_EN,
    USP_HX,
    USP_JH,
    USP_N,
    USP_NX,
    USP_Q,
)
from dectalk.kernel.ksd_t import KsdT
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import FDUMMY_VOWEL, FSTRESS, FSTRESS_1
from dectalk.ph.get_phone import get_phone
from dectalk.ph.numeric_constants import (
    A2,
    AV,
    B2,
    B3,
    F1,
    FEMALE,
    FZ,
    TILT,
)
from dectalk.ph.parameter_tables import parini, partyp
from dectalk.ph.phoneme_features import (
    F2BACKF,
    F2BACKI,
    FNASAL,
    FOBST,
    FPLOSV,
    FSTOP,
    FSYLL,
    FVOICD,
)
from dectalk.ph.rom_tables import us_place
from dectalk.ph.timing import begtyp, endtyp, phone_feature, ptram
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.utterance_constants import (
    GEN_SIL,
    NASAL_ZERO_CONS,
    NON_NASAL_ZERO,
)

# US_TOT_ALLOPHONES is the inner-table stride; one row per parameter.
# The active voice ROM (VOICE_ROM_DECTALK_1996M_43F) lays out
# us_maltar / us_femtar in 57-phone blocks, so the stride is 57
# (l_all_ph.h, gated on the VOICE_ROM_DECTALK_43/1996M_43F define).
# Sourced from phoneme_codes so the stride and the table layout never
# drift apart.
_US_TOT_ALLOPHONES: int = US_TOT_ALLOPHONES

# par_type encoding from ph_defs.h IS_* macros:
#   IS_AV_OR_AH         == 0
#   IS_NASAL_ZERO_FREQ  == 1
#   IS_PARALLEL_FORM_AMP== 2
#   IS_FORM_FREQ_OR_BW   > 2  (covers FORM_FREQ == 3 and FORM_BW == 4)
_PARTYPE_AV_OR_AH: int = 0
_PARTYPE_NASAL_ZERO_FREQ: int = 1
_PARTYPE_PARALLEL_FORM_AMP: int = 2


def us_gettar(phTTS: TtsHandle, nphone_temp: int) -> int:  # noqa: N803, PLR0912, PLR0915 -- faithful 290-line C function
    """Resolve the US-English target for one parameter at one phone slot.

    Faithful translation of:

    .. code-block:: c

        short us_gettar(LPTTS_HANDLE_T phTTS, int nphone_temp);

    The C source's flow:

    1. Look up the three surrounding phone codes via :func:`get_phone`.
    2. Compute ``npar = np - PF1`` and ``pphotr = npar *
       US_TOT_ALLOPHONES`` (or ``(npar - 1) * US_TOT_ALLOPHONES`` for
       ``np >= PFZ``, since there's no PAP table row).
       ``US_TOT_ALLOPHONES`` is 57 for the active voice ROM.
    3. Dispatch on ``partyp[npar]`` (cached into
       ``pDphsettar->par_type``).
    4. Within each branch, read the per-parameter table
       (``p_tar`` / ``p_amp``) and apply phoneme-specific corrections.

    Args:
        phTTS: Two-pointer engine handle. ``p_ph_thread_data`` must
            be a populated :class:`~dectalk.ph.dph_t.DphT` with
            ``pSTphsettar`` set and ``param[np]`` indexed by the
            caller; ``p_kernel_share_data`` must be a
            :class:`~dectalk.kernel.ksd_t.KsdT`.
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
        pphotr = npar * _US_TOT_ALLOPHONES
    else:
        # No table row for PAP; subsequent parameters shift down by 1.
        pphotr = (npar - 1) * _US_TOT_ALLOPHONES

    p_dphsettar.par_type = partyp[npar]
    tartemp = 0

    p_tar = cast(list[int], p_dph_t.p_tar)

    if p_dphsettar.par_type > _PARTYPE_PARALLEL_FORM_AMP:
        # FORM_FREQ_OR_BW: F1, F2, F3, B1, B2, B3.
        tartemp = p_tar[(phone_temp & PVALUE) + pphotr]
        if tartemp < -1:
            # Diphthong sentinel: target -2 means "first entry of
            # p_diph[2]", and so on. Return the sentinel so the
            # caller (getbegtar/getendtar) can dereference it.
            return tartemp
        if tartemp == -1:
            # p_us_st0.c lines 93-118: target undefined -- fall back
            # to the next segment, then the second-next, then the
            # previous (resolving a diph pointer to its LAST value),
            # then the parameter's parini[] default. The p_us_st1.c
            # rewrite (BATS 982) removed this chain and let the
            # gettar() wrapper walk candidates instead; the active
            # OLD_SETTAR build resolves it right here, so the phone's
            # own context (phone_temp) still drives the tweak rules
            # below.
            tartemp = p_tar[(phnex_temp & PVALUE) + pphotr]
            if tartemp == -1:
                tartemp = p_tar[(get_phone(p_dph_t, nphone_temp + 2) & PVALUE) + pphotr]
                if tartemp == -1:
                    tartemp = p_tar[(phlas_temp & PVALUE) + pphotr]
                    if tartemp < -1:
                        # Diphthongised seg: use its last target value.
                        p_diph = cast(list[int], p_dph_t.p_diph)
                        while p_diph[-tartemp] != -1:
                            tartemp -= 1
                        tartemp = p_diph[-tartemp - 1]
                    if tartemp == -1:
                        tartemp = parini[npar]
        if tartemp < -1:
            # A diph pointer picked up from the phnex/phnex2 fallback
            # levels above resolves to its FIRST value (st0 line 121).
            p_diph = cast(list[int], p_dph_t.p_diph)
            tartemp = p_diph[-tartemp]

        # Fricatives have higher F1 if preceded by a vowel.
        if (
            npar == F1 - 1
            and (phone_feature(phone_temp) & FOBST) != 0
            and (phone_feature(phone_temp) & FSTOP) == 0
            and (phone_feature(phlas_temp) & FSYLL) != 0
        ):
            tartemp += 40

        # B2 of /n/ before non-front vowels: nudge target up.
        if phone_temp in (USP_N, USP_EN) and npar == B2 - 1:
            if begtyp(phnex_temp) != 1:
                tartemp += 60

        # B3 of /n/ adjacent to high-front vowels: clamp to 1600.
        if phone_temp in (USP_N, USP_EN, USP_NX) and npar == B3 - 1:
            if (us_place[phnex_temp & PVALUE] & F2BACKI) != 0 or (
                us_place[phlas_temp & PVALUE] & F2BACKF
            ) != 0:
                tartemp = 1600

    elif p_dphsettar.par_type == _PARTYPE_NASAL_ZERO_FREQ:
        # FZ: NASAL_ZERO_CONS during nasal murmur, else NON_NASAL_ZERO.
        tartemp = NON_NASAL_ZERO
        if (phone_feature(phone_temp) & FNASAL) != 0:
            tartemp = NASAL_ZERO_CONS

    elif p_dphsettar.par_type == _PARTYPE_AV_OR_AH:
        # AV or AP (npar == 7 for AV, 8 for AP relative to F1=1).
        if npar == AV - 1:
            tartemp = p_tar[(phone_temp & PVALUE) + pphotr]

            # Glottal stop drops further at slow speech rates.
            if p_ksd_t.sprate < 100 and phone_temp == USP_Q:
                tartemp -= 30

            # Dummy vowel has less intensity (st0: -7; st1 used -12).
            if (p_dph_t.allofeats[nphone_temp] & FDUMMY_VOWEL) != 0:
                tartemp -= 7

            # Voiced stop devoiced if previous segment was voiceless.
            if (phone_feature(phone_temp) & FPLOSV) != 0 and (
                phone_feature(phlas_temp) & FVOICD
            ) == 0:
                tartemp = 0

            # /hx/ voiced when unstressed and preceded by voiced.
            if (
                phone_temp == USP_HX
                and (phone_feature(phlas_temp) & FVOICD) != 0
                and (p_dph_t.allofeats[nphone_temp] & FSTRESS_1) == 0
            ):
                tartemp = 54

            # Reduce AV on unstressed segments (no negative output).
            if (p_dph_t.allofeats[nphone_temp] & FSTRESS) == 0:
                tartemp -= 4
                if tartemp < 0:
                    tartemp = 0
        else:
            # AP: only /hx/ has aspiration; stronger before back vowels
            # (st0: 60; st1 used 56).
            if phone_temp == USP_HX:
                tartemp = 53
                if begtyp(phnex_temp) != 1:
                    tartemp = 60
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
                if begtypnex == 4:
                    begtypnex = 2
                tartemp += npar - A2 + 1 + (6 * begtypnex)
                tartemp = p_amp[tartemp]

                # Burst loses intensity before a dummy vowel.
                if (p_dph_t.allofeats[nphone_temp + 1] & FDUMMY_VOWEL) != 0:
                    if tartemp >= 4:
                        tartemp -= 4

        if p_dphsettar.np == TILT:
            # Spectral tilt: high for obstruents, low for vowels.
            # st0 form: the GEN_SIL / HX tests are sequential ``if``s
            # (not chained), the dummy-vowel tilt is 20 (st1: 10), and
            # the front-vowel bias is +6 female / +3 male with NO
            # catch-all else (st1 added +6-else-+3 with no sex split).
            tartemp = 0
            if phone_temp == GEN_SIL:
                tartemp = 0
            if phone_temp == USP_HX:
                tartemp = 20
            elif (p_dph_t.allofeats[nphone_temp] & FDUMMY_VOWEL) != 0:
                tartemp = 20
            elif (phone_feature(phone_temp) & FOBST) != 0:
                tartemp = 7
                if (phone_feature(phone_temp) & FVOICD) != 0 and (
                    (phone_feature(phone_temp) & FPLOSV) != 0 or p_dphsettar.phcur == USP_JH
                ):
                    tartemp = 40
            elif (phone_feature(phone_temp) & FNASAL) != 0:
                tartemp = 6
            elif begtyp(phone_temp) == 1 or endtyp(phone_temp) == 1:
                # Female front vowels tilted down slightly; males less.
                if p_dph_t.malfem == FEMALE:
                    tartemp += 6
                else:
                    tartemp += 3

    return tartemp


__all__ = ["us_gettar"]
