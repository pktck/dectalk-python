"""``phsettar`` -- per-clause target/transition orchestrator from ph_setar.c.

Translated from ``src/dapi/src/ph/ph_setar.c`` line 561 (~1870 lines
total in C; the active Linux US-English path is ~600 lines after
preprocessor stripping).

The phsettar orchestrator iterates over every Klatt voice parameter
F1..TILT for the current phone position (``pDph_t.nphone``) and writes
all the per-parameter state slots that PH_DRAW.C later consumes to
generate per-frame parameter trajectories:

- ``tarlas`` / ``tarcur`` / ``tarnex`` / ``tarend`` -- target values
  at previous-end / current-start / next-start / current-end.
- ``bouval`` / ``durtran`` -- forward-smooth boundary value and
  transition duration.
- ``ftran`` / ``dftran`` / ``btran`` / ``dbtran`` / ``tbacktr`` --
  forward and backward transition states (per-frame increments).
- ``tspesh`` / ``pspesh`` -- special-rule "constant override"
  timestamps and values.

Flow (per parameter):

1. Snapshot last-phone target into ``tarlas``.
2. Look up next/current targets via :func:`getbegtar` + :func:`gettar`.
3. If diphthong sentinel: :func:`make_dip` walks the diph table.
   Else: apply general coarticulation (5% tarlas + 5% tarnex tug
   toward tarcur).
4. Forward-smooth via :func:`us_forw_smooth_rules`, compute ``ftran``
   and ``dftran``.
5. Backward-smooth via :func:`us_back_smooth_rules`, compute ``btran``
   and ``dbtran``.
6. Apply :func:`us_special_rules` once after the loop for plosive
   bursts / VOT / voicebar.

The Python port currently dispatches only to the US-English path;
GERMAN / FRENCH / SPANISH / LATIN preprocessor branches in the C
source are not translated.
"""

from __future__ import annotations

# ruff: noqa: PLR2004 -- C-literal style kept
from typing import cast

from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import FSENTENDS, FSTRESS
from dectalk.ph.frame_counts import NF25MS, NF30MS
from dectalk.ph.getbegtar import getbegtar
from dectalk.ph.gettar import gettar
from dectalk.ph.init_variables import init_variables
from dectalk.ph.make_dip import make_dip
from dectalk.ph.math_helpers import mlsh1
from dectalk.ph.numeric_constants import AREAB, AREAL, F1, F2, TILT
from dectalk.ph.parameter_tables import divtab, partyp
from dectalk.ph.q14_percent_constants import N15PRCNT, N25PRCNT
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.us_back_smooth_rules import us_back_smooth_rules
from dectalk.ph.us_forw_smooth_rules import us_forw_smooth_rules
from dectalk.ph.us_special_rules import us_special_rules
from dectalk.ph.utterance_constants import GEN_SIL

_PARTYPE_FORM_FREQ: int = 3
_DIVTAB_THRESHOLD: int = 50


def phsettar(phTTS: TtsHandle) -> None:  # noqa: N803, PLR0912, PLR0915
    """Compute targets and transitions for every Klatt voice parameter.

    Faithful translation of the per-phone orchestrator. Iterates
    F1..TILT, calling the per-language smooth/special-rule helpers
    after each target lookup.

    Args:
        phTTS: Two-pointer engine handle with populated DphT.
    """
    p_dph_t = cast(DphT, phTTS.p_ph_thread_data)
    p_dphsettar = cast(DphSettarSt, p_dph_t.pSTphsettar)

    # Per-clause initialization: zero AREAL / AREAB special-override
    # timestamps. (NEW_VTM also zeroes TONGUEBODY; not modelled.)
    p_dph_t.param[AREAL].tspesh = 0
    p_dph_t.param[AREAB].tspesh = 0

    init_out = init_variables(phTTS)
    inhdr_frames = init_out.inhdr_frames
    pholas = init_out.pholas
    fealas = init_out.fealas
    feacur = init_out.feacur
    feanex = init_out.feanex
    struclm2 = init_out.struclm2
    struclas = init_out.struclas
    struccur = init_out.struccur
    strucnex = init_out.strucnex
    # ndips: mutable cell holding the current dipspec write offset
    # (the C ``short **ppsNdips`` argument to make_dip).
    ndips: list[int] = [init_out.ndips_offset]

    p_dph_t.shrink = init_out.shrink
    p_dph_t.shrif = init_out.shrif
    p_dph_t.shrib = init_out.shrib

    # Breathyness switch.
    if p_dphsettar.phcur == GEN_SIL:
        p_dph_t.breathysw = 0
    if (struccur & FSENTENDS) != 0:
        p_dph_t.breathysw = 1

    # Main loop: iterate parameter indices F1..TILT (inclusive).
    for np_idx in range(F1, TILT + 1):
        p_dphsettar.np = np_idx
        np_param = p_dph_t.param[np_idx]

        p_dphsettar.par_type = partyp[np_idx - F1]

        # 1. Snapshot end-of-last-phone target into tarlas.
        np_param.tarlas = np_param.tarend

        # 2. Compute target at onset of next phone.
        np_param.tarnex = getbegtar(phTTS, p_dph_t.nphone + 1)
        if np_param.tarnex == 4:
            np_param.tarnex += 1  # C source workaround ("???? Michel").

        # 3. Compute current target.
        np_param.tarcur = gettar(phTTS, p_dph_t.nphone)
        np_param.dipcum = 0

        if np_param.tarcur < -1:
            # Diphthong sentinel: walk diph table to populate
            # ``np_param.tarcur`` and ``tarend`` plus dipspec entries.
            make_dip(
                p_dph_t,
                -np_param.tarcur,
                inhdr_frames,
                p_dph_t.shrink,
                struccur,
                ndips,
            )
        else:
            np_param.deldip = 0
            np_param.durlin = p_dph_t.durfon

            # 4. General coarticulation for sonor-cons formants.
            if p_dphsettar.par_type == _PARTYPE_FORM_FREQ:
                p_dphsettar.gencoartic = 0
                if (struccur & FSTRESS) == 0:
                    p_dphsettar.gencoartic = N15PRCNT
                    if p_dphsettar.np == F2:
                        p_dphsettar.gencoartic = N25PRCNT

                if np_param.tarnex <= 0:
                    p_dph_t.arg1 = np_param.tarlas - np_param.tarcur
                else:
                    p_dph_t.arg1 = ((np_param.tarlas + np_param.tarnex) >> 1) - np_param.tarcur

                p_dph_t.arg2 = p_dphsettar.gencoartic
                np_param.tarcur += mlsh1(p_dph_t.arg1, p_dph_t.arg2)

            np_param.tarend = np_param.tarcur

        # 5a. Forward-smooth default bouval / durtran -- mirrors
        # ph_setar.c lines 1003-1004:
        #     bouval = (tarlas + tarcur) >> 1   # halfway by default
        #     durtran = NF30MS                  # 30 ms transition
        # The smoothing rule below may overwrite either based on the
        # phone-pair coarticulation context. Pre-fix the Python port
        # skipped this init, so bouval/durtran inherited from the
        # previous loop iteration (or even the previous nphone's
        # phsettar call) when the smoothing rule's branches all
        # fell through.
        p_dphsettar.bouval = (np_param.tarlas + np_param.tarcur) >> 1
        p_dphsettar.durtran = NF30MS

        # 5b. Forward smooth.
        us_forw_smooth_rules(
            phTTS=phTTS,
            shrif=p_dph_t.shrif,
            pholas=pholas,
            fealas=fealas,
            feacur=feacur,
            struclas=struclas,
            struccur=struccur,
            feanex=feanex,
        )

        # 6. Convert bouval/durtran into phdraw-consumable
        # ``ftran``/``dftran`` (ph_setar.c lines 1060-1078). The shape:
        #
        #     ftran = 0
        #     if durtran > 0:
        #         ftran = (bouval - tarcur) << 3
        #         if ftran != 0:
        #             dftran = mlsh1(ftran, divtab[durtran])
        #             ftran = dftran * durtran
        #
        # Pre-fix the Python port used ``ftran = bouval`` and
        # ``dftran = (tarend - bouval) << 3 / durtran`` -- the wrong
        # endpoint and the wrong sign. Each frame phdraw does ``ftran
        # -= dftran``, so the wrong sign made ftran *grow* every
        # frame, saturating the synthesizer. The corrected formula
        # mirrors the C source line-for-line.
        np_param.ftran = 0
        if p_dphsettar.durtran > 0:
            np_param.ftran = (p_dphsettar.bouval - np_param.tarcur) << 3
            if np_param.ftran != 0:
                p_dph_t.arg1 = np_param.ftran
                if p_dphsettar.durtran < _DIVTAB_THRESHOLD:
                    p_dph_t.arg2 = divtab[p_dphsettar.durtran]
                    np_param.dftran = mlsh1(p_dph_t.arg1, p_dph_t.arg2)
                else:
                    np_param.dftran = p_dph_t.arg1 // p_dphsettar.durtran
                np_param.ftran = np_param.dftran * p_dphsettar.durtran

        # 7a. Backward-smooth default bouval / durtran -- mirrors
        # ph_setar.c lines 1122-1123:
        #     bouval = (tarend + tarnex) >> 1   # halfway by default
        #     durtran = NF25MS                  # 25 ms transition
        # Same fix as 5a: pre-fix the Python port skipped this init
        # so the back-smooth rule's fall-through paths reused stale
        # values from forward smoothing.
        p_dphsettar.bouval = (np_param.tarend + np_param.tarnex) >> 1
        p_dphsettar.durtran = NF25MS

        # 7b. Backward smooth.
        us_back_smooth_rules(
            phTTS=phTTS,
            shrib=p_dph_t.shrib,
            feacur=feacur,
            feanex=feanex,
            strucnex=strucnex,
        )

        # 8. Convert bouval/durtran into phdraw-consumable
        # ``btran``/``dbtran`` (ph_setar.c lines 1186-1199). The shape
        # differs from forward smoothing: ``btran`` stays zero (the
        # backward trajectory is purely driven by ``dbtran`` per-frame
        # accumulation), and the temp uses ``tarend`` (not
        # ``tarcur``):
        #
        #     btran = 0
        #     dbtran = 0
        #     if durtran > 0:
        #         temp = (bouval - tarend) << 3
        #         if temp != 0:
        #             dbtran = mlsh1(temp, divtab[durtran])
        np_param.btran = 0
        np_param.dbtran = 0
        if p_dphsettar.durtran > 0:
            temp = (p_dphsettar.bouval - np_param.tarend) << 3
            if temp != 0:
                p_dph_t.arg1 = temp
                if p_dphsettar.durtran < _DIVTAB_THRESHOLD:
                    p_dph_t.arg2 = divtab[p_dphsettar.durtran]
                    np_param.dbtran = mlsh1(p_dph_t.arg1, p_dph_t.arg2)
                else:
                    np_param.dbtran = p_dph_t.arg1 // p_dphsettar.durtran

        # 8b. F2-only vowel-to-vowel coarticulation across a consonant
        # (ph_setar.c lines 1205-1226). The backward smoothing rule
        # for F2 calls setloc -> vv_coartic_across_c which writes
        # vvbouval/vvdurtran on the per-clause settar struct. This
        # block converts those into the per-frame ``bvvtran`` /
        # ``dbvvtran`` / ``tvvbacktr`` fields on DphT that phdraw
        # adds to F2 every frame after ``tvvbacktr``. Reset
        # vvbouval/vvdurtran to zero at the end so the next phone's
        # F2 starts clean.
        if np_idx == F2:
            p_dph_t.bvvtran = 0
            p_dph_t.dbvvtran = 0
            p_dph_t.tvvbacktr = p_dph_t.durfon
            if p_dphsettar.vvdurtran > p_dph_t.durfon:
                p_dphsettar.vvdurtran = p_dph_t.durfon
            if p_dphsettar.vvdurtran > 0 and p_dphsettar.vvbouval != 0:
                p_dph_t.tvvbacktr = p_dph_t.durfon - p_dphsettar.vvdurtran
                p_dph_t.arg1 = p_dphsettar.vvbouval << 3
                if p_dphsettar.vvdurtran < _DIVTAB_THRESHOLD:
                    p_dph_t.arg2 = divtab[p_dphsettar.vvdurtran]
                    p_dph_t.dbvvtran = mlsh1(p_dph_t.arg1, p_dph_t.arg2)
                else:
                    p_dph_t.dbvvtran = p_dph_t.arg1 // p_dphsettar.vvdurtran
            p_dphsettar.vvdurtran = 0
            p_dphsettar.vvbouval = 0

    # 9. Special rules — called once after the per-parameter loop.
    us_special_rules(
        phTTS=phTTS,
        fealas=fealas,
        feacur=feacur,
        feanex=feanex,
        struclm2=struclm2,
        struccur=struccur,
        pholas=pholas,
        struclas=struclas,
    )


__all__ = ["phsettar"]
