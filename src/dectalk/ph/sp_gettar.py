# ruff: noqa: PLR2004, SIM102, SIM108, SIM114, PLR5501, PLR1730 -- faithful translation of branchy C source
"""``sp_gettar`` -- Castilian Spanish per-parameter target lookup from p_sp_st1.c.

Translated from ``src/dapi/src/ph/p_sp_st1.c`` line 76 (~250 lines).

``sp_gettar`` resolves the target value of one Klatt voice parameter
for one phone position in a clause when the phone's font is
``PFSP`` (Castilian Spanish). It is the Spanish leaf of the
``getbegtar`` / ``getendtar`` / ``gettar`` dispatch chain that
:func:`phsettar` walks for every parameter on every phoneme. The
return value is the "raw" target before forward/backward smoothing
and coarticulation -- subsequent rules add to or override it.

Like its US sibling :func:`~dectalk.ph.us_gettar.us_gettar`, the
function branches on ``pDphsettar->par_type`` (the partyp entry for
the current parameter):

- ``par_type > 2`` (form-frequency or bandwidth -- F1, F2, F3, B1,
  B2, B3): reads ``p_tar[phone + pphotr]`` then applies four
  Spanish-specific tweaks (B3 of /n/, /nh/, /nx/ adjacent to /i/,
  B3 of /i/ following /f/, F1 of /r//rr/ after /o//u/).
- ``par_type == 1`` (nasal-zero frequency -- FZ):
  ``NASAL_ZERO_BOUNDARY`` during a nasal murmur, else ``NON_NASAL_ZERO``.
- ``par_type == 0`` (voicing/aspiration amplitude -- AV, AP): reads
  ``p_tar`` for AV with the dummy-vowel-zero / unstressed-reduce /
  +10-finishing-touch corrections. AP is 0 except for /r/, /rr/
  (33), /ll/ (10), and /j/ (25).
- ``par_type == 2`` (parallel formant amplitudes -- A2..A6, AB, TILT):
  reads ``ptram``-indexed ``p_amp`` entries based on the next-phone
  beginning type, with dummy-vowel correction. TILT has its own
  cascade (voiced-plosive 12, front-vowel +5/+3 by sex, /r//rr/ 24,
  /dh/..gh/ 24, nasal 6, obstruent 7, default 3).

The function reads (but does not write) per-parameter state through
``pDphsettar->np`` (current parameter index, ``F1``..``TILT``).
"""

from __future__ import annotations

from typing import cast

from dectalk.include.cmd_codes import PVALUE
from dectalk.include.spp_codes import (
    SPP_DH,
    SPP_F,
    SPP_GH,
    SPP_J,
    SPP_LL,
    SPP_N,
    SPP_NH,
    SPP_NX,
    SPP_O,
    SPP_R,
    SPP_RR,
    SPP_U,
    SPP_YH,
    SP_TOT_ALLOPHONES,
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
from dectalk.ph.rom_tables import sp_place
from dectalk.ph.timing import begtyp, endtyp, phone_feature, ptram
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.utterance_constants import (
    GEN_SIL,
    NASAL_ZERO_BOUNDARY,
    NON_NASAL_ZERO,
)

# par_type encoding from ph_defs.h IS_* macros (same as US):
#   IS_AV_OR_AH         == 0
#   IS_NASAL_ZERO_FREQ  == 1
#   IS_PARALLEL_FORM_AMP== 2
#   IS_FORM_FREQ_OR_BW   > 2  (covers FORM_FREQ == 3 and FORM_BW == 4)
_PARTYPE_AV_OR_AH: int = 0
_PARTYPE_NASAL_ZERO_FREQ: int = 1
_PARTYPE_PARALLEL_FORM_AMP: int = 2

# ph_setar.c #define BACK_UNROUNDED_VOWEL 2 / #define OBSTRUENT 4
_OBSTRUENT: int = 4
_BACK_UNROUNDED_VOWEL: int = 2


def sp_gettar(phTTS: TtsHandle, nphone_temp: int) -> int:  # noqa: N803, PLR0912, PLR0915 -- faithful 250-line C function
    """Resolve the Castilian Spanish target for one parameter at one phone slot.

    Faithful translation of:

    .. code-block:: c

        short sp_gettar(LPTTS_HANDLE_T phTTS, int nphone_temp);

    The C source's flow:

    1. Look up the three surrounding phone codes via :func:`get_phone`.
    2. Compute ``npar = np - PF1`` and ``pphotr = npar * 39`` (or
       ``(npar - 1) * 39`` for ``np >= PFZ``, since there's no PAP
       table row).
    3. Dispatch on ``partyp[npar]`` (cached into
       ``pDphsettar->par_type``).
    4. Within each branch, read the per-parameter table
       (``p_tar`` / ``p_amp``) and apply phoneme-specific corrections.

    Args:
        phTTS: Two-pointer engine handle. ``p_ph_thread_data`` must
            be a populated :class:`~dectalk.ph.dph_t.DphT` with
            ``pSTphsettar`` set and ``p_tar`` / ``p_amp`` pointing at
            the Spanish ROM tables; ``p_kernel_share_data`` must be a
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
        pphotr = npar * SP_TOT_ALLOPHONES
    else:
        # No table row for PAP; subsequent parameters shift down by 1.
        pphotr = (npar - 1) * SP_TOT_ALLOPHONES

    phlas_temp = get_phone(p_dph_t, nphone_temp - 1)
    phone_temp = get_phone(p_dph_t, nphone_temp)
    phnex_temp = get_phone(p_dph_t, nphone_temp + 1)

    # The C source has a `#ifdef GETITOUTAHERE` block for Spanish
    # nasal assimilation (m/n -> obstruent place before an
    # obstruent). It's compiled out in the shipping build; we drop
    # it from the Python port for the same reason.

    phone_feat = phone_feature(phone_temp)

    p_dphsettar.par_type = partyp[npar]
    tartemp = 0

    p_tar = cast(list[int], p_dph_t.p_tar)

    if p_dphsettar.par_type > _PARTYPE_PARALLEL_FORM_AMP:
        # FORM_FREQ_OR_BW: F1, F2, F3, B1, B2, B3.
        tartemp = p_tar[(phone_temp & PVALUE) + pphotr]
        if tartemp < -1:
            # Diphthong sentinel: target < -1 means "first entry of
            # p_diph[2]", and so on. Return the sentinel so the
            # caller (getbegtar/getendtar) can dereference it.
            return tartemp
        # The C source has a vestigial second `if (tartemp < -1)`
        # immediately after the return-on-sentinel block. It can
        # never execute because the early return caught it; the
        # Python port drops it.

        # Special rule for B3 of /n/, /nh/, /nx/ adjacent to a
        # high-front vowel: clamp to 300 (was 1600 pre-Dec-96).
        if (
            npar == B3 - F1
            and phone_temp in (SPP_N, SPP_NH, SPP_NX)
            and (
                (sp_place[phnex_temp & PVALUE] & F2BACKI) != 0
                or (sp_place[phlas_temp & PVALUE] & F2BACKI) != 0
            )
        ):
            tartemp = 300

        # Special rule for /i/ (high-front vowel) following /f/.
        if (
            npar == B3 - F1
            and (sp_place[phone_temp & PVALUE] & F2BACKI) != 0
            and phlas_temp == SPP_F
        ):
            tartemp = 90

        # Special rule for /r/ and /rr/ after a "back" vowel /o/ or /u/.
        if phone_temp in (SPP_R, SPP_RR) and phlas_temp in (SPP_O, SPP_U):
            if npar == F1 - F1:
                tartemp -= 100

    elif p_dphsettar.par_type == _PARTYPE_AV_OR_AH:
        # AV or AP (npar == 7 for AV, 8 for AP relative to F1=1).
        if npar == AV - 1:
            tartemp = p_tar[(phone_temp & PVALUE) + pphotr]

            # Glottal stop drops further at slow speech rates. The
            # C source compares against USP_Q (US font) even in the
            # Spanish path -- a probable cross-language oversight,
            # but we preserve it for byte-identical behaviour.
            if p_ksd_t.sprate < 100 and phone_temp == USP_Q:
                tartemp -= 20

            # No voicing for stop-release dummy vowels.
            if (p_dph_t.allofeats[nphone_temp] & FDUMMY_VOWEL) != 0:
                tartemp = 0

            # Reduce amplitudes if unstressed (no negative output).
            if (p_dph_t.allofeats[nphone_temp] & FSTRESS) == 0:
                tartemp -= 3
                if tartemp < 0:
                    tartemp = 0

            # "EAB HACK LETS FIX IT LATER HELPME": +10 if nonzero.
            if tartemp:
                tartemp += 10
        else:
            # AP: stronger aspiration on Spanish trills and /j/.
            tartemp = 0
            if phone_temp in (SPP_R, SPP_RR):
                tartemp = 33
            if phone_temp == SPP_LL:
                tartemp = 10
            if phone_temp == SPP_J:
                tartemp = 25  # make stronger for Castilian

    elif p_dphsettar.par_type == _PARTYPE_PARALLEL_FORM_AMP:
        # PARALLEL_FORM_AMP: A2-A6, AB, TILT.
        # The C source guards this whole branch with `#ifndef HLSYN`;
        # we keep it for non-HLSYN parity.
        p_amp = cast(list[int], p_dph_t.p_amp)
        if p_dphsettar.np == TILT:
            # Spectral tilt: high for obstruents, low for vowels.
            tartemp = 3
            if phone_temp == GEN_SIL:
                tartemp = 3  # eab
            elif (phone_feat & (FVOICD | FPLOSV)) == (FVOICD | FPLOSV) and (
                phone_temp != SPP_DH or phone_temp == SPP_YH
            ):
                # Voiced plosives (b/d/g): max tilt to signal voicebar.
                tartemp = 12
            elif begtyp(phone_temp) == 1 or endtyp(phone_temp) == 1:
                # Front vowels: small sex-dependent bias.
                if p_dph_t.malfem == FEMALE:
                    tartemp += 5
                else:
                    tartemp += 3
            elif phone_temp in (SPP_R, SPP_RR):
                # Trills: 24 (7-Jul-86 MM).
                tartemp = 24
            elif SPP_DH <= phone_temp <= SPP_GH:
                # Pseudo-voicebars (dh..gh range): 24 (12-Apr-86 MM).
                tartemp = 24
            elif (phone_feat & FNASAL) != 0:
                tartemp = 6
            elif (phone_feat & FOBST) != 0:
                tartemp = 7
        else:
            # Non-TILT parallel-amp: index into p_amp via ptram.
            tartemp = ptram(phone_temp)
            if tartemp > 0:
                begtypnex = begtyp(phnex_temp) - 1
                if phnex_temp == GEN_SIL:
                    begtypnex = endtyp(phlas_temp) - 1
                if begtypnex == _OBSTRUENT:
                    begtypnex = _BACK_UNROUNDED_VOWEL
                tartemp += npar - A2 + 1 + (6 * begtypnex)
                tartemp = p_amp[tartemp]

        # Reduce amplitudes if next phone is a dummy vowel. Note
        # this guard sits OUTSIDE the np == TILT branch in the C
        # source but INSIDE the par_type == PARALLEL_FORM_AMP
        # branch -- it fires for both TILT and ptram-driven targets.
        if (p_dph_t.allofeats[nphone_temp + 1] & FDUMMY_VOWEL) != 0:
            tartemp -= 6
            if tartemp < 0:
                tartemp = 0

    elif p_dphsettar.par_type == _PARTYPE_NASAL_ZERO_FREQ:
        # FZ: NASAL_ZERO_BOUNDARY during nasal murmur, else NON_NASAL_ZERO.
        # Note: US uses NASAL_ZERO_CONS here; Spanish uses the
        # different default NASAL_ZERO_BOUNDARY.
        tartemp = NON_NASAL_ZERO
        if (phone_feat & FNASAL) != 0:
            tartemp = NASAL_ZERO_BOUNDARY

    return tartemp


__all__ = ["sp_gettar"]
