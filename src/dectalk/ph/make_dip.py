"""``make_dip`` -- static parameter-dip generator from ph_setar.c.

Translated from ``src/dapi/src/ph/ph_setar.c`` line 1429 (~180 lines).

The C function generates the diphthongisation "dip" (sequence of
straight-line segments) for a parameter on a diphthongised vowel.
It walks each ``<value, time>`` pair in the diphthong table,
applies general and per-language ``*_special_coartic`` coarticulation
rules, calls :func:`shrdur` to scale transition durations relative
to the phone's inherent duration, and writes the resulting
per-frame increments and segment durations into ``dipspec[]``.

The C ``short **ppsNdips`` argument is the running write pointer
into ``dipspec[]``. The Python port models this as a single-element
list ``pps_ndips`` whose element-zero is the integer offset, and the
``dipspec`` array lives on :class:`~dectalk.ph.dph_t.DphT`.
"""

from __future__ import annotations

# ruff: noqa: PLR2004, SIM108 -- C-literal magic numbers and if/else parallel to C kept
from typing import cast

from dectalk.include.cmd_codes import PFONT, PSFONT
from dectalk.include.phoneme_codes import PFFR, PFGR, PFLA, PFSP, PFUSA
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import FSTRESS
from dectalk.ph.get_phone import get_phone
from dectalk.ph.gr_special_coartic import gr_special_coartic
from dectalk.ph.la_special_coartic import la_special_coartic
from dectalk.ph.math_helpers import mlsh1
from dectalk.ph.numeric_constants import F2, NSAMP_FRAME
from dectalk.ph.parameter_tables import divtab
from dectalk.ph.q14_percent_constants import N10PRCNT, N15PRCNT, N25PRCNT
from dectalk.ph.shrdur import shrdur
from dectalk.ph.sp_special_coartic import sp_special_coartic
from dectalk.ph.us_special_coartic import us_special_coartic

_FONT_USA: int = PFUSA << PSFONT
_FONT_GR: int = PFGR << PSFONT
_FONT_LA: int = PFLA << PSFONT
_FONT_SP: int = PFSP << PSFONT
_FONT_FR: int = PFFR << PSFONT

_PARTYPE_FORM_FREQ: int = 3
_DIVTAB_THRESHOLD: int = 50  # C: if (temp < 50) use divtab lookup


def make_dip(  # noqa: PLR0912, PLR0915 -- faithful 180-line C function
    p_dph_t: DphT,
    pdip: int,
    inhdr_frames: int,
    shrink: int,
    struccur: int,
    pps_ndips: list[int],
) -> None:
    """Generate the diphthong "dip" sequence for the current parameter.

    Args:
        p_dph_t: PH thread state with populated ``dipspec``,
            ``p_diph``, and ``pSTphsettar.np``.
        pdip: Index of the first diphthong entry in ``p_diph[]``.
        inhdr_frames: Inherent duration of the current phone in frames.
        shrink: Sonorant-duration shrinkage factor (FRAC_ONE-scaled).
        struccur: Allofeats bitmask of the current phone.
        pps_ndips: Single-element list cell holding the current
            ``dipspec[]`` write offset. Mutated in place.
    """
    p_dphsettar = cast(DphSettarSt, p_dph_t.pSTphsettar)
    p_diph = cast(list[int], p_dph_t.p_diph)
    dipspec = p_dph_t.dipspec
    np_param = p_dph_t.param[p_dphsettar.np]

    # Mark the start of this parameter's diph info in dipspec.
    np_param.ndip = pps_ndips[0]

    # Initial value of first straight line.
    oldvalue = p_diph[pdip]

    # Formant-frequency coarticulation rules.
    if p_dphsettar.par_type == _PARTYPE_FORM_FREQ:
        # General rule: previous phone tugs the initial vowel target.
        p_dphsettar.gencoartic = N10PRCNT
        if (struccur & FSTRESS) == 0:
            # Increased coarticulation, especially F2, if unstressed.
            p_dphsettar.gencoartic = N15PRCNT
            if p_dphsettar.np == F2:
                p_dphsettar.gencoartic = N25PRCNT
        p_dph_t.arg1 = np_param.tarlas - oldvalue
        p_dph_t.arg2 = p_dphsettar.gencoartic
        oldvalue += mlsh1(p_dph_t.arg1, p_dph_t.arg2)

        # Per-language special_coartic at dip_pos=0.
        tmp = get_phone(p_dph_t, p_dph_t.nphone) & PFONT
        if tmp == _FONT_USA:
            oldvalue += us_special_coartic(p_dph_t, p_dph_t.nphone, 0)
        elif tmp == _FONT_GR:
            oldvalue += gr_special_coartic(p_dph_t, p_dph_t.nphone, 0)
        elif tmp == _FONT_LA:
            oldvalue += la_special_coartic(p_dph_t, p_dph_t.nphone, 0)
        elif tmp == _FONT_SP:
            oldvalue += sp_special_coartic(p_dph_t, p_dph_t.nphone, 0)
        # FR branch is commented out in C; no-op here too.

    np_param.tarcur = oldvalue

    oldtime = 0
    dipsw = 0
    while True:
        if dipsw == 0:
            newvalue = oldvalue
            dipsw += 1
            pdip += 1
        else:
            newvalue = p_diph[pdip]
            pdip += 1

            # Coarticulation toward the next phone (formant only).
            if p_dphsettar.par_type == _PARTYPE_FORM_FREQ:
                if np_param.tarnex > 0:
                    p_dph_t.arg1 = np_param.tarnex - newvalue
                    p_dph_t.arg2 = p_dphsettar.gencoartic
                    newvalue += mlsh1(p_dph_t.arg1, p_dph_t.arg2)

                # The C source has a bug here: it reads tmp from the
                # bare integer nphone rather than get_phone(...)'s
                # result. Mirror verbatim for parity.
                tmp = p_dph_t.nphone & PFONT
                if tmp == _FONT_USA:
                    newvalue += us_special_coartic(p_dph_t, p_dph_t.nphone, 0)
                elif tmp == _FONT_GR:
                    newvalue += gr_special_coartic(p_dph_t, p_dph_t.nphone, 0)
                elif tmp == _FONT_LA:
                    newvalue += la_special_coartic(p_dph_t, p_dph_t.nphone, 0)
                elif tmp == _FONT_SP:
                    newvalue += sp_special_coartic(p_dph_t, p_dph_t.nphone, 0)

        # Halve newtime if NSAMP_FRAME == 128 (DOS 1/2-sample-rate mode).
        # The Linux build uses NSAMP_FRAME == 71, so the halving branch
        # is dead, but we preserve it for the eventual cross-build port.
        if NSAMP_FRAME == 128:
            newtime = p_diph[pdip] >> 1
        else:
            newtime = p_diph[pdip]

        if newtime != -1:
            # Scale transition dur relative to phone's inherent dur.
            newtime = shrdur(newtime, inhdr_frames, shrink)
        else:
            newtime = p_dph_t.durfon

        # *(*ppsNdips)++ = newtime;
        dipspec[pps_ndips[0]] = newtime
        pps_ndips[0] += 1

        # Compute increment/frame during transition.
        temp = newtime - oldtime
        if temp == 0:
            dipspec[pps_ndips[0]] = 0
        else:
            p_dph_t.arg2 = (newvalue - oldvalue) << 3
            if temp < _DIVTAB_THRESHOLD:
                p_dph_t.arg1 = divtab[temp]
                dipspec[pps_ndips[0]] = mlsh1(p_dph_t.arg1, p_dph_t.arg2)
            else:
                dipspec[pps_ndips[0]] = p_dph_t.arg2 // temp
            oldvalue = newvalue
            oldtime = newtime

        pps_ndips[0] += 1

        # while (p_diph[pdip++] != -1) -- terminate AFTER the increment.
        sentinel = p_diph[pdip]
        pdip += 1
        if sentinel == -1:
            break

    # Set final value of diph tran, first increment, and duration in frames.
    np_param.tarend = newvalue
    # `*np->ndip++` in C reads then advances. In Python, np_param.ndip is
    # the current offset; we read dipspec at the offset, then bump.
    assert np_param.ndip is not None
    np_param.durlin = dipspec[np_param.ndip]
    np_param.ndip += 1
    np_param.deldip = dipspec[np_param.ndip]
    np_param.ndip += 1


__all__ = ["make_dip"]
