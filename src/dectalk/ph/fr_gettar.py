# ruff: noqa: PLR2004 -- faithful translation of branchy C source
"""``fr_gettar`` -- French per-parameter target lookup from p_fr_st1.c.

Translated from ``src/dapi/src/ph/p_fr_st1.c`` line 53 (~110 lines).

``fr_gettar`` is the French sibling of :func:`us_gettar` -- the leaf
of the ``getbegtar`` / ``getendtar`` / ``gettar`` dispatch chain that
resolves the target value of one Klatt voice parameter for one phone
position in a clause. Unlike the US path, French stores its targets
in a single 2-D ``Cibles_Defaut[42][17]`` table (selected at language
switch from ``Cibles_MALE`` or ``Cibles_FEMALE`` -- see
:mod:`dectalk.ph.fr_target_tables`).

The function branches on ``pDphsettar->par_type`` (the partyp entry
for the current parameter, as set by :func:`phsettar`):

- ``par_type > 2`` (form-frequency or bandwidth -- F1, F2, F3, B1,
  B2, B3): reads ``Cibles_Defaut[phone, col]`` where ``col = npar + 9``.
  When the lookup yields ``-1``, the function walks forward and
  backward looking for a defined value (next phone, then n+2, then
  previous phone), resolving a diphthong sentinel via ``p_diph[]``
  when one is found, and finally falling back to ``parini[npar]``.
- ``par_type == 1`` (nasal-zero frequency -- FZ): reads
  ``Cibles_Defaut[phone, 12]`` directly (FNZ column).
- ``par_type == 0`` (voicing / aspiration amplitude -- AV, AP):
  reads ``Cibles_Defaut[phone, 7]`` for AV and
  ``Cibles_Defaut[phone, 6]`` for AH/AP. Unlike the US branch,
  fr_gettar applies no further phoneme-specific tweaks.
- ``par_type == 2`` (parallel formant amplitudes -- A2..A6, AB,
  TILT): under the non-HLSYN build (the one this port mirrors), it
  reads ``p_amp`` for fricative-like ``ptram > 0`` cases and the
  ``Cibles_Defaut[phone, npar - 9]`` column otherwise. TILT comes
  straight from ``Cibles_Defaut[phone, 8]``.

The function reads (but does not write) per-parameter state through
``pDphsettar->np`` (current parameter index, ``F1``..``TILT``).

.. note::

   The shipped Linux ``say`` binary does not link the French target
   tables, so this Python port has no oracle to compare against.
   The behavioural tests in
   ``tests/unit/test_ph_fr_gettar_parity.py`` mirror the C source's
   table-lookup structure and verify the parity test extractor
   re-finds the same C body shape, but cannot exercise round-trip
   audio parity against the C binary.
"""

from __future__ import annotations

from typing import cast

from dectalk.include.cmd_codes import PVALUE
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.fr_target_tables import N_PARAM_FR
from dectalk.ph.get_phone import get_phone
from dectalk.ph.numeric_constants import A2, AV, TILT
from dectalk.ph.parameter_tables import parini, partyp
from dectalk.ph.timing import begtyp, endtyp, ptram
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.utterance_constants import GEN_SIL

# par_type encoding from ph_defs.h IS_* macros:
#   IS_AV_OR_AH         == 0
#   IS_NASAL_ZERO_FREQ  == 1
#   IS_PARALLEL_FORM_AMP== 2
#   IS_FORM_FREQ        == 3
#   IS_FORM_FREQ_OR_BW   > 2  (covers FORM_FREQ == 3 and FORM_BW == 4)
_PARTYPE_AV_OR_AH: int = 0
_PARTYPE_NASAL_ZERO_FREQ: int = 1
_PARTYPE_PARALLEL_FORM_AMP: int = 2

# Cibles_Defaut column offsets:
#   F1/F2/F3/FNZ/B1/B2/B3 land at columns 9..15  ⇒  col = npar + 9.
#   AV is column 7, AH (treated as AP here) is column 6.
#   TILT is column 8.
#   A2..AB land at columns 0..5  ⇒  col = npar - 9 (with A2 npar==9).
_FNZ_COLUMN: int = 12
_TILT_COLUMN: int = 8
_AV_COLUMN: int = 7
_AH_COLUMN: int = 6


def _cibles(p_dph_t: DphT, phone: int, col: int) -> int:
    """Look up ``Cibles_Defaut[phone & PVALUE, col]`` via the flat view."""
    cibles = cast(list[int], p_dph_t.Cibles_Defaut)
    return cibles[N_PARAM_FR * (phone & PVALUE) + col]


def fr_gettar(phTTS: TtsHandle, nphone_temp: int) -> int:  # noqa: N803, PLR0912 -- faithful translation
    """Resolve the French target for one parameter at one phone slot.

    Faithful translation of:

    .. code-block:: c

        short fr_gettar(LPTTS_HANDLE_T phTTS, int nphone_temp);

    The C source's flow:

    1. (Skipped here -- gettar's table-load prologue assigns
       ``Cibles_Defaut`` before the per-phone path is taken. The C
       source also tests ``last_lang`` and reloads the male/female
       tables on a French language transition; the Python dispatcher
       in :mod:`dectalk.ph.gettar` handles that step.)
    2. Look up the three surrounding phone codes via :func:`get_phone`.
    3. Compute ``npar = np - PF1`` (the Klatt parameter index, with
       F1 as zero).
    4. Dispatch on ``partyp[npar]`` (cached into
       ``pDphsettar->par_type``).
    5. Within the form-frequency branch, walk forward / backward to
       resolve ``-1`` placeholders and diphthong sentinels.

    Args:
        phTTS: Two-pointer engine handle. ``p_ph_thread_data`` must
            be a populated :class:`~dectalk.ph.dph_t.DphT` with
            ``pSTphsettar`` set, ``Cibles_Defaut`` loaded with a
            French target table (see
            :func:`dectalk.ph.gettar._load_fr_tables`), and
            ``param[np]`` indexed by the caller.
        nphone_temp: Index into ``allophons[]`` for the target phone.

    Returns:
        The raw target value (``short`` in C; an arbitrary-precision
        ``int`` here).
    """
    p_dph_t = cast(DphT, phTTS.p_ph_thread_data)
    p_dphsettar = cast(DphSettarSt, p_dph_t.pSTphsettar)

    # Skip the C source's language-switch prologue (lines 59-79). The
    # Python dispatcher in gettar() handles `last_lang` updates and
    # loads Cibles_Defaut + the shared p_diph/p_tar/p_amp pointers.

    # npar = pDphsettar->np - &PF1 -- pointer arithmetic over param[].
    # Mirroring us_gettar: F1's numeric value is 1, so npar = np - 1.
    npar = p_dphsettar.np - 1

    phlas_temp = get_phone(p_dph_t, nphone_temp - 1)
    phone_temp = get_phone(p_dph_t, nphone_temp)
    phnex_temp = get_phone(p_dph_t, nphone_temp + 1)

    p_dphsettar.par_type = partyp[npar]
    tartemp = 0

    if p_dphsettar.par_type > _PARTYPE_PARALLEL_FORM_AMP:
        # GETTAR: F1, F2, F3, B1, B2, B3.
        # pphotr = npar + 9 yields: F1 -> 9, F2 -> 10, ..., B3 -> 15.
        pphotr = npar + 9

        tartemp = _cibles(p_dph_t, phone_temp, pphotr)
        if tartemp == -1:
            # ``-1`` is the "undefined" placeholder. Try the next phone.
            tartemp = _cibles(p_dph_t, phnex_temp, pphotr)
            if tartemp == -1:
                # Try the second-next phone.
                phone_p2 = get_phone(p_dph_t, nphone_temp + 2)
                tartemp = _cibles(p_dph_t, phone_p2, pphotr)
                if tartemp == -1:
                    # Try the previous phone.
                    tartemp = _cibles(p_dph_t, phlas_temp, pphotr)
                    if tartemp < -1:
                        # Diphthongised seg: walk p_diph to the last entry.
                        p_diph = cast(list[int], p_dph_t.p_diph)
                        while p_diph[-tartemp] != -1:
                            tartemp -= 1
                        tartemp = p_diph[-tartemp - 1]
                    # If still undefined, fall back to parini[npar].
                    if tartemp == -1:
                        tartemp = parini[npar]

    elif p_dphsettar.par_type == _PARTYPE_NASAL_ZERO_FREQ:
        # FNZ -- column 12.
        tartemp = _cibles(p_dph_t, phone_temp, _FNZ_COLUMN)

    elif p_dphsettar.par_type == _PARTYPE_AV_OR_AH:
        # Voicing amplitude (AV) or aspiration (AH/AP).
        if npar == AV - 1:
            tartemp = _cibles(p_dph_t, phone_temp, _AV_COLUMN)
        else:
            # AH/AP -- column 6 in Cibles_Defaut.
            tartemp = _cibles(p_dph_t, phone_temp, _AH_COLUMN)

    elif p_dphsettar.par_type == _PARTYPE_PARALLEL_FORM_AMP:
        # GETTAR: A2, A3, A4, A5, A6, AB, TILT (partyp == 2).
        # Mirrors the C ``#ifndef HLSYN`` branch (the non-HLSYN build).
        p_amp = cast(list[int], p_dph_t.p_amp)
        if p_dphsettar.np != TILT:
            tartemp = ptram(phone_temp)
            if tartemp > 0:
                # ptram > 0 -- index into the obstruent ``taram`` array.
                begtypnex = begtyp(phnex_temp) - 1
                if phnex_temp == GEN_SIL:
                    begtypnex = endtyp(phlas_temp) - 1
                if begtypnex == 4:
                    begtypnex = 2
                tartemp += npar - A2 + 1 + (6 * begtypnex)
                tartemp = p_amp[tartemp]
            else:
                # A2..AB direct lookup. pphotr = npar - 9.
                # For A2 (npar==9) ⇒ col 0; AB (npar==14) ⇒ col 5.
                pphotr = npar - 9
                tartemp = _cibles(p_dph_t, phone_temp, pphotr)

        if p_dphsettar.np == TILT:
            # Spectral tilt -- column 8 of Cibles_Defaut.
            tartemp = _cibles(p_dph_t, phone_temp, _TILT_COLUMN)

    return tartemp


__all__ = ["fr_gettar"]
