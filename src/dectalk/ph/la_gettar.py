# ruff: noqa: PLR2004, SIM102, SIM108, PLR1730 -- faithful translation of branchy C source
"""``la_gettar`` -- Latin American Spanish per-parameter target lookup.

Translated from ``src/dapi/src/ph/p_la_st1.c`` line 76 (~250 lines).

``la_gettar`` is the LA Spanish leaf of the
``getbegtar`` / ``getendtar`` / ``gettar`` dispatch chain that
:func:`phsettar` walks for every parameter on every phoneme. The
return value is the "raw" target before forward/backward smoothing
and coarticulation -- subsequent rules add to or override it. This
function is the sibling of :func:`dectalk.ph.us_gettar.us_gettar`;
the two share the same dispatch shape but differ in their
phoneme-specific corrections:

- ``par_type > 2`` (form-frequency or bandwidth -- F1, F2, F3, B1,
  B2, B3): reads ``p_tar[phone + pphotr]`` then applies LA-specific
  tweaks: B3 clamp for ``LAP_N``/``LAP_NH``/``LAP_NX`` adjacent to
  high-front vowels (``tartemp = 300``, was 1600 pre-EDB 1996-12-10),
  B3 special for /i/ following /f/ (``tartemp = 90``), and F1
  reduction (``-100``) for /r/ or /rr/ after back vowels /o/ or /u/.
- ``par_type == 1`` (nasal-zero frequency -- FZ): ``NASAL_ZERO_BOUNDARY``
  (370) during a nasal murmur, else ``NON_NASAL_ZERO`` (290). The C
  uses ``NASAL_ZERO_BOUNDARY`` here, **not** ``NASAL_ZERO_CONS`` -- a
  deliberate difference from US English.
- ``par_type == 0`` (voicing/aspiration amplitude -- AV, AP): reads
  ``p_tar`` for AV with LA-specific corrections (glottal-stop drop
  ``-20`` at slow rates, dummy-vowel zero, unstressed reduction
  ``-3``, then a "+10 hack" for any nonzero AV). AP uses fixed
  per-phoneme aspiration amplitudes for /r/ /rr/ (33), /ll/ (10),
  and /j/ (25).
- ``par_type == 2`` (parallel formant amplitudes -- A2-A6, AB, TILT):
  reads ``ptram``-indexed ``p_amp`` entries based on the next-phone
  beginning type. TILT has LA-specific rules: voiced-plosive obstruents
  hit 12 (not 40), trill /r/ /rr/ hit 24, voiced fricatives /dh/-/gh/
  hit 24, nasals 6, obstruents 7, sonorant boundaries +5 (female) or
  +3 (male). Dummy-vowel-next reduction is ``-6`` (not ``-4``).

The function reads (but does not write) per-parameter state through
``pDphsettar->np`` (current parameter index, ``F1``..``TILT``).
"""

from __future__ import annotations

from typing import cast

from dectalk.include.cmd_codes import PVALUE
from dectalk.include.lap_codes import (
    LAP_DH,
    LAP_F,
    LAP_GH,
    LAP_J,
    LAP_LL,
    LAP_N,
    LAP_NH,
    LAP_NX,
    LAP_O,
    LAP_R,
    LAP_RR,
    LAP_U,
    LAP_YH,
)
from dectalk.include.usp_codes import USP_Q
from dectalk.kernel.ksd_t import KsdT
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import FDUMMY_VOWEL, FSTRESS
from dectalk.ph.get_phone import get_phone
from dectalk.ph.numeric_constants import (
    A2,
    AV,
    B3,
    F1,
    FEMALE,
    FZ,
    TILT,
)
from dectalk.ph.parameter_tables import partyp
from dectalk.ph.phoneme_features import (
    F2BACKI,
    FNASAL,
    FOBST,
    FPLOSV,
    FVOICD,
)
from dectalk.ph.rom_tables import la_place
from dectalk.ph.sonor_classes import BACK_UNROUNDED_VOWEL, OBSTRUENT
from dectalk.ph.timing import begtyp, endtyp, phone_feature, ptram
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.utterance_constants import (
    GEN_SIL,
    NASAL_ZERO_BOUNDARY,
    NON_NASAL_ZERO,
)

# LA_TOT_ALLOPHONES is the inner-table stride; one row per parameter.
# p_la_st1.c line 88 multiplies by LA_TOT_ALLOPHONES = 39 (see
# include/l_all_ph.h line 352).
_LA_TOT_ALLOPHONES: int = 39

# par_type encoding from ph_defs.h IS_* macros (same as US):
#   IS_AV_OR_AH         == 0
#   IS_NASAL_ZERO_FREQ  == 1
#   IS_PARALLEL_FORM_AMP== 2
#   IS_FORM_FREQ_OR_BW   > 2  (covers FORM_FREQ == 3 and FORM_BW == 4)
_PARTYPE_AV_OR_AH: int = 0
_PARTYPE_NASAL_ZERO_FREQ: int = 1
_PARTYPE_PARALLEL_FORM_AMP: int = 2


def la_gettar(phTTS: TtsHandle, nphone_temp: int) -> int:  # noqa: N803, PLR0912, PLR0915 -- faithful 250-line C function
    """Resolve the LA Spanish target for one parameter at one phone slot.

    Faithful translation of:

    .. code-block:: c

        short la_gettar(LPTTS_HANDLE_T phTTS, int nphone_temp);

    The C source's flow:

    1. Compute ``npar = np - PF1`` and ``pphotr = npar * 39`` (or
       ``(npar - 1) * 39`` for ``np >= PFZ``, since there's no PAP
       table row).
    2. Look up the three surrounding phone codes via :func:`get_phone`.
    3. Cache ``phone_feat = phone_feature(phone_temp)``.
    4. Dispatch on ``partyp[npar]`` (cached into
       ``pDphsettar->par_type``).
    5. Within each branch, read the per-parameter table
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

    # npar = pDphsettar->np - &PF1 -- pointer arithmetic over param[].
    npar = p_dphsettar.np - F1
    if p_dphsettar.np < FZ:
        pphotr = npar * _LA_TOT_ALLOPHONES
    else:
        # No table row for PAP; subsequent parameters shift down by 1.
        pphotr = (npar - 1) * _LA_TOT_ALLOPHONES

    phlas_temp = get_phone(p_dph_t, nphone_temp - 1)
    phone_temp = get_phone(p_dph_t, nphone_temp)
    phnex_temp = get_phone(p_dph_t, nphone_temp + 1)

    # The C source has a #ifdef GETITOUTAHERE block here for nasal
    # assimilation (m, n -> following obstruent) -- compiled out
    # because the feature was unfinished. We skip it here as well.

    phone_feat = phone_feature(phone_temp)

    p_dphsettar.par_type = partyp[npar]
    tartemp = 0

    p_tar = cast(list[int], p_dph_t.p_tar)

    if p_dphsettar.par_type > _PARTYPE_PARALLEL_FORM_AMP:
        # FORM_FREQ_OR_BW: F1, F2, F3, B1, B2, B3.
        tartemp = p_tar[(phone_temp & PVALUE) + pphotr]
        if tartemp < -1:
            # Diphthong sentinel: target -2 means "first entry of
            # p_diph[2]", etc. Return the sentinel so the caller
            # (getbegtar/getendtar) can dereference it.
            return tartemp

        # Special rule for B3 of /n/, /nh/, /nx/ adjacent to /i/ (front).
        # 12/10/1996 EDB: was 1600, now 300.
        if (
            npar == (B3 - F1)
            and phone_temp in (LAP_N, LAP_NH, LAP_NX)
            and (
                (la_place[phnex_temp & PVALUE] & F2BACKI) != 0
                or (la_place[phlas_temp & PVALUE] & F2BACKI) != 0
            )
        ):
            tartemp = 300

        # Special rule for B3 of /i/ (front vowel) following /f/.
        if (
            npar == (B3 - F1)
            and (la_place[phone_temp & PVALUE] & F2BACKI) != 0
            and phlas_temp == LAP_F
        ):
            tartemp = 90

        # Special rule for /r/ and /rr/ after "back" vowel /o/ or /u/
        # (8-Jul-86): reduce F1 target by 100.
        if phone_temp in (LAP_R, LAP_RR) and phlas_temp in (LAP_O, LAP_U):
            if npar == (F1 - F1):
                tartemp -= 100

    elif p_dphsettar.par_type == _PARTYPE_AV_OR_AH:
        # AV or AP (npar == 7 for AV, 8 for AP relative to F1=1).
        if npar == AV - 1:
            tartemp = p_tar[(phone_temp & PVALUE) + pphotr]

            # BATS 660 EAB 5/11/98: glottal stop drops further at slow
            # speech rates. (Note: C uses USP_Q here, not LAP_Q -- the
            # comparison is against the US-font glottal stop code.)
            if p_ksd_t.sprate < 100 and phone_temp == USP_Q:
                tartemp -= 20

            # No voicing for stop-release dummy vowels (30-Jul-86).
            if (p_dph_t.allofeats[nphone_temp] & FDUMMY_VOWEL) != 0:
                tartemp = 0

            # Reduce amplitudes if unstressed (12/10/96 EDB: was -1, now -3).
            if (p_dph_t.allofeats[nphone_temp] & FSTRESS) == 0:
                tartemp -= 3
                if tartemp < 0:
                    tartemp = 0

            # EAB HACK: bump nonzero AV by +10 ("LETS FIX IT LATER HELPME").
            if tartemp:
                tartemp += 10
        else:
            # AP: fixed per-phoneme aspiration amplitudes.
            tartemp = 0
            if phone_temp in (LAP_R, LAP_RR):
                tartemp = 33
            if phone_temp == LAP_LL:
                tartemp = 10
            if phone_temp == LAP_J:
                # 10/23/1998 EAB: stronger /j/ for Castilian flavour.
                tartemp = 25

    elif p_dphsettar.par_type == _PARTYPE_PARALLEL_FORM_AMP:
        # PARALLEL_FORM_AMP: A2-A6, AB, TILT.
        p_amp = cast(list[int], p_dph_t.p_amp)
        if p_dphsettar.np == TILT:
            # Source spectral tilt -- LA-specific cascade.
            # (Voiced obstruents are special case, set F1=0 for voicebar.)
            tartemp = 3
            if phone_temp == GEN_SIL:
                tartemp = 3  # eab
            elif (phone_feat & (FVOICD | FPLOSV)) == (FVOICD | FPLOSV) and (
                phone_temp != LAP_DH or phone_temp == LAP_YH
            ):
                # Voiced plosives (excluding /dh/, but including /yh/).
                tartemp = 12
            elif begtyp(phone_temp) == 1 or endtyp(phone_temp) == 1:
                # Sonorant boundaries: extra tilt for female voice.
                if p_dph_t.malfem == FEMALE:
                    tartemp += 5
                else:
                    tartemp += 3
            elif phone_temp in (LAP_R, LAP_RR):
                # 7-Jul-86 (MM): tilt boost for trill.
                tartemp = 24
            elif LAP_DH <= phone_temp <= LAP_GH:
                # Voicebar pseudo-voicing for /dh/-/gh/ band.
                tartemp = 24
            elif (phone_feat & FNASAL) != 0:
                tartemp = 6
            elif (phone_feat & FOBST) != 0:
                tartemp = 7
        else:
            # If ptram > 0, it indexes into the obstruent amp array.
            tartemp = ptram(phone_temp)
            if tartemp > 0:
                begtypnex = begtyp(phnex_temp) - 1
                if phnex_temp == GEN_SIL:
                    begtypnex = endtyp(phlas_temp) - 1
                if begtypnex == OBSTRUENT:
                    begtypnex = BACK_UNROUNDED_VOWEL
                tartemp += npar - A2 + 1 + (6 * begtypnex)
                tartemp = p_amp[tartemp]

        # Reduce amplitudes if dummy vowel next (30-Jul-86).
        # This is applied to *both* TILT and non-TILT in the C source.
        if (p_dph_t.allofeats[nphone_temp + 1] & FDUMMY_VOWEL) != 0:
            tartemp -= 6
            if tartemp < 0:
                tartemp = 0

    elif p_dphsettar.par_type == _PARTYPE_NASAL_ZERO_FREQ:
        # FZ: NASAL_ZERO_BOUNDARY during nasal murmur, else NON_NASAL_ZERO.
        # Note: LA uses NASAL_ZERO_BOUNDARY (370), not NASAL_ZERO_CONS (400).
        tartemp = NON_NASAL_ZERO
        if (phone_feat & FNASAL) != 0:
            tartemp = NASAL_ZERO_BOUNDARY

    return tartemp


__all__ = ["la_gettar"]
