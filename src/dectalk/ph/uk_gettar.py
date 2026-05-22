# ruff: noqa: PLR2004, SIM102, SIM108, PLR5501, PLR1730 -- faithful translation of branchy C source
"""``uk_gettar`` -- UK-English per-parameter target lookup from p_uk_st1.c.

Translated from ``src/dapi/src/ph/p_uk_st1.c`` line 76 (~210 lines).

The UK-English sibling of :func:`dectalk.ph.us_gettar.us_gettar`: same
shape (par_type-dispatched, four branches), same flow through
``p_tar`` / ``p_amp`` / ``p_diph``, but with UK-tuned constants:

- ``UK_TOT_ALLOPHONES == 57`` (vs 71 for US): the inner-table stride.
- Reads :data:`dectalk.ph.uk_rom_tables.uk_place` (vs ``us_place``).
- Dummy-vowel AV reduction is ``-7`` (US: ``-12``).
- /hx/ aspiration target is 50 / 52 (US: 53 / 56) below/above
  back-vowel context.
- The unstressed ``tartemp -= 4`` is moved outside the AV branch so
  it applies to *both* AV and AP (the US version applies it only to
  AV).
- TILT branch:
  - Dummy vowel → 20 (US: 10).
  - Female front-vowel +6 / male +3 (US: always +3).
  - ``UKP_OW`` gets an extra +10.
  - No ``begtyp == 1`` post-bias for males beyond the front-vowel
    branch (US adds +6 indiscriminately for front vowels).

Since ``PFUK<<PSFONT`` differs from ``PFUSA<<PSFONT`` in the Python
port (``0x1D`` vs ``0x1E``; both equal ``0x1E`` in the C build with
the integrated phoneme set), the per-language dispatch is real here
and not a font-equality accident.

The UKP_* phone constants are numerically identical to the USP_*
constants (both share the ``PFUSA == 0x1D``/``0x1E`` low byte from
``l_uk_ph.h`` / ``l_all_ph.h``) — the high-byte font tag is added at
parse time, so this function compares against the imported
``USP_*`` symbols where the C source compares ``UKP_*``. The two
match phone-for-phone.
"""

from __future__ import annotations

from typing import cast

from dectalk.include.cmd_codes import PVALUE
from dectalk.include.usp_codes import (
    USP_EN,
    USP_HX,
    USP_JH,
    USP_N,
    USP_NX,
    USP_OW,
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
from dectalk.ph.parameter_tables import partyp
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
from dectalk.ph.timing import begtyp, endtyp, phone_feature, ptram
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.uk_rom_tables import uk_place
from dectalk.ph.utterance_constants import (
    GEN_SIL,
    NASAL_ZERO_CONS,
    NON_NASAL_ZERO,
)

# UK_TOT_ALLOPHONES is the inner-table stride; one row per parameter.
_UK_TOT_ALLOPHONES: int = 57

# par_type encoding from ph_defs.h IS_* macros (identical to us_gettar).
_PARTYPE_AV_OR_AH: int = 0
_PARTYPE_NASAL_ZERO_FREQ: int = 1
_PARTYPE_PARALLEL_FORM_AMP: int = 2


def uk_gettar(phTTS: TtsHandle, nphone_temp: int) -> int:  # noqa: N803, PLR0912, PLR0915 -- faithful 210-line C function
    """Resolve the UK-English target for one parameter at one phone slot.

    Faithful translation of:

    .. code-block:: c

        short uk_gettar(LPTTS_HANDLE_T phTTS, int nphone_temp);

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
        pphotr = npar * _UK_TOT_ALLOPHONES
    else:
        # No table row for PAP; subsequent parameters shift down by 1.
        pphotr = (npar - 1) * _UK_TOT_ALLOPHONES

    phlas_temp = get_phone(p_dph_t, nphone_temp - 1)
    phone_temp = get_phone(p_dph_t, nphone_temp)
    phnex_temp = get_phone(p_dph_t, nphone_temp + 1)

    p_dphsettar.par_type = partyp[npar]
    tartemp = 0

    p_tar = cast(list[int], p_dph_t.p_tar)

    if p_dphsettar.par_type > _PARTYPE_PARALLEL_FORM_AMP:
        # FORM_FREQ_OR_BW: F1, F2, F3, B1, B2, B3.
        tartemp = p_tar[(phone_temp & PVALUE) + pphotr]
        if tartemp < -1:
            # Diphthong sentinel: return so caller (getbegtar/getendtar)
            # can dereference it.
            return tartemp
        # The C source has a vestigial second ``if (tartemp < -1)``
        # immediately after the return-on-sentinel block. It can never
        # execute because the early return caught it; the Python port
        # drops it (same as us_gettar).

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
            if (uk_place[phnex_temp & PVALUE] & F2BACKI) != 0 or (
                uk_place[phlas_temp & PVALUE] & F2BACKF
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

            # Dummy vowel has less intensity (UK: -7; US: -12).
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
        else:
            # AP: only /hx/ has aspiration; stronger before back vowels.
            # UK uses 50 / 52 (US: 53 / 56).
            if phone_temp == USP_HX:
                tartemp = 50
                if begtyp(phnex_temp) != 1:
                    tartemp = 52
            else:
                tartemp = 0

        # Reduce amplitudes if unstressed (UK applies this to BOTH
        # AV and AP; the US version applies it only to AV).
        if (p_dph_t.allofeats[nphone_temp] & FSTRESS) == 0:
            tartemp -= 4
            if tartemp < 0:
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
            tartemp = 0
            if phone_temp == GEN_SIL:
                tartemp = 0
            elif phone_temp == USP_HX:
                tartemp = 20
            elif (p_dph_t.allofeats[nphone_temp] & FDUMMY_VOWEL) != 0:
                # UK: dummy vowel → 20 (US: 10).
                tartemp = 20
            elif (phone_feature(phone_temp) & FOBST) != 0:
                tartemp = 7
                if (phone_feature(phone_temp) & FVOICD) != 0 and (
                    (phone_feature(phone_temp) & FPLOSV) != 0 or p_dphsettar.phcur == USP_JH
                ):
                    tartemp = 40
            elif (phone_feature(phone_temp) & FNASAL) != 0:
                # UK uses ``tartemp = 6`` (assignment, not +=) here.
                tartemp = 6
            elif begtyp(phone_temp) == 1 or endtyp(phone_temp) == 1:
                # Front vowels: female +6, male +3 (US is +3 either way).
                if p_dph_t.malfem == FEMALE:
                    tartemp += 6
                else:
                    tartemp += 3
            elif phone_temp == USP_OW:
                # UK gives /ow/ an extra +10 tilt.
                tartemp += 10

    return tartemp


__all__ = ["uk_gettar"]
