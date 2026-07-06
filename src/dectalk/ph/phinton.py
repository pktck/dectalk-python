"""``phinton`` -- intonation-engine entry point from ph_inton0.c.

Translated from ``src/dapi/src/ph/ph_inton0.c`` line 1325 — the
**second** ``phinton`` definition, active for the production
``ENGLISH_US`` + ``OLD_INTONATION_AND_TIMING`` build (``HLSYN``
undefined). (The first definition at line 154 is the ``NWSNOAA`` /
``ENGLISH_UK`` variant.)

The function generates the F0 (pitch) contour for one clause: it walks
the allophone stream, fires F0 commands on stressed syllables, applies
hat-rise / hat-fall patterns, and finally pads clause-final stops with a
"dummy" schwa to give plosive releases something to voice into. Output
lives in ``f0tar`` / ``f0tim`` on the :class:`~dectalk.ph.dph_t.DphT`
(see :func:`~dectalk.ph.make_f0_command.make_f0_command`) — the command
*type* is encoded into each ``tar`` value, not stored separately.

This is a substantially simpler engine than the HLSYN ``ph_inton2.c``
the port originally followed. Differences from that variant, dropped
here to match the production build:

- **No word-feature (noun/verb/adj) F0 bump** — Rule 2 is just
  ``us_f0_stress_level[stresscur] + us_f0_phrase_position[nrises_sofar]``.
- **No open-quotient (``alloopenq``) block** — that was an HLSYN-only
  feature.
- **No ``hatstate`` machine, no ``malfem`` (male/female) table split,
  no ``impulse_width`` / divide-by-3** on the stress impulse.
- **Single** ``us_f0_stress_level`` / ``us_f0_phrase_position`` tables
  (from ``p_us_rom_dectalk_1996m_43f.c``), not per-voice-gender pairs.
- Q-gestures are the literals **181 / 251**; comma gestures **71 / 101**.

C bugs / quirks preserved faithfully:

- ``Rule 9`` dummy-schwa insertion uses the ``USP_P..USP_G`` plosive
  range and the ``USP_T..USP_D`` schwa-quality predicate
  (ph_inton0.c lines 1970-1994), with an ``NF25MS`` schwa.
- The main loop re-reads ``nallotot`` each iteration (the C ``for``-loop
  condition), so the trailing silence shifted right by a schwa
  insertion is still visited.

Pipeline note — ``tcumdur``: in the active production build tcumdur is
**never accumulated at all**. ``us_phtiming`` zeroes it per clause
(p_us_tim0.c line 124) and the only accumulating code lives in
ph_inton0.c's FIRST ``phinton`` definition (lines 1086 / 1125), which is
``#if defined NWSNOAA || defined ENGLISH_UK`` — dead here. This second
definition (the US one) leaves it alone, so downstream consumers see 0:
``ph_drwt01.c`` clamps ``if (tcumdur == 0) tcumdur = 1`` before its
baseline division, and ``ph_draw.c``'s ``nframb > tcumdur-92``
end-of-phrase gates are always-true (#270 audit). Only ``cumdur`` (the
F0-command clock) is a real accumulator in this function.
"""

# ruff: noqa: N803, N806, PLR0912, PLR0915, PLR1714, PLR1730, PLR2004, SIM102 -- mirror C structure

from __future__ import annotations

from typing import Final, cast

from dectalk.include.usp_codes import (
    USP_AE,
    USP_AX,
    USP_D,
    USP_G,
    USP_IX,
    USP_P,
    USP_T,
)
from dectalk.kernel.ksd_t import KsdT
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import (
    FBOUNDARY,
    FCBNEXT,
    FDUMMY_VOWEL,
    FEMPHASIS,
    FEXCLNEXT,
    FHAT_BEGINS,
    FHAT_ENDS,
    FPERNEXT,
    FQUENEXT,
    FSENTENDS,
    FSTRESS,
    FSTRESS_1,
    FVPNEXT,
)
from dectalk.ph.frame_counts import (
    NF20MS,
    NF25MS,
    NF50MS,
    NF60MS,
    NF80MS,
    NF100MS,
    NF160MS,
)
from dectalk.ph.inton_constants import (
    HAT_F0_SIZES_SPECIFIED,
    NORMAL,
    PHONE_TARGETS_SPECIFIED,
    SINGING,
)
from dectalk.ph.make_f0_command import make_f0_command as _make_f0_command
from dectalk.ph.math_helpers import muldv
from dectalk.ph.numeric_constants import NPHON_MAX
from dectalk.ph.phoneme_features import FSYLL
from dectalk.ph.task_helpers import mstofr
from dectalk.ph.timing import phone_feature
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.utterance_constants import GEN_SIL
from dectalk.vtm.frac import frac4mul

# -- US-English F0 tables from p_us_rom_dectalk_1996m_43f.c -----------------
#
# us_f0_stress_level is indexed by the 2-bit stress field (stresscur); Rule 2
# only fires for odd stresscur (FSTRESS_1 set) so indices 1 (primary) and 3
# (emphatic) are the live ones. us_f0_phrase_position is indexed by
# nrises_sofar (0..MAX_NRISES). The active build uses a single pair of tables
# regardless of voice gender. (p_us_rom_dectalk_1996m_43f.c lines 795/803.)
_US_F0_STRESS_LEVEL: Final[tuple[int, ...]] = (1, 71, 31, 281)
_US_F0_PHRASE_POSITION: Final[tuple[int, ...]] = (210, 90, 60, 40, 0)

# -- ENGLISH_US constants (ph_defs.h lines 869-891, #ifndef HLSYN) ----------
# MAX_NRISES resolves to 4 for VOICE_ROM_DECTALK_1996M_43F.
_SCHWA1: Final[int] = USP_AX
_SCHWA2: Final[int] = USP_IX
_MAX_NRISES: Final[int] = 4
_F0_FINAL_FALL: Final[int] = 180
_F0_NON_FINAL_FALL: Final[int] = 150
_F0_QSYLL_FALL: Final[int] = 80
_F0_GLOTTALIZE: Final[int] = -60


def _ensure_buffer(arr: list[int], min_size: int) -> None:
    """Grow ``arr`` to at least ``min_size`` entries with zeroes."""
    if len(arr) < min_size:
        arr.extend([0] * (min_size - len(arr)))


def phinton(phTTS: TtsHandle) -> None:
    """Run the per-clause intonation engine (ph_inton0.c:1325).

    Mirrors the C signature ``void phinton(LPTTS_HANDLE_T phTTS)``.
    Walks the clause's allophone stream and writes F0 commands into
    ``f0tar`` / ``f0tim`` on ``phTTS``'s PH-thread state, advancing
    ``nf0tot`` and inserting a trailing dummy schwa after a clause-final
    plosive.

    Args:
        phTTS: Two-pointer engine handle with populated ``KsdT`` and
            ``DphT``. ``p_ph_thread_data.pSTphsettar`` must be set.
    """
    # KsdT cast retained for parity with the C source; the US-only path
    # never reads pKsd_t.
    _pKsd_t = cast(KsdT, phTTS.p_kernel_share_data)
    del _pKsd_t
    pDph_t = cast(DphT, phTTS.p_ph_thread_data)
    pDphsettar = cast(DphSettarSt, pDph_t.pSTphsettar)

    # Local aliases so the body reads like the C source.
    us_f0_stress_level = _US_F0_STRESS_LEVEL
    us_f0_phrase_position = _US_F0_PHRASE_POSITION
    SCHWA1 = _SCHWA1
    SCHWA2 = _SCHWA2
    MAX_NRISES = _MAX_NRISES
    F0_FINAL_FALL = _F0_FINAL_FALL
    F0_NON_FINAL_FALL = _F0_NON_FINAL_FALL
    F0_QSYLL_FALL = _F0_QSYLL_FALL
    F0_GLOTTALIZE = _F0_GLOTTALIZE

    # Automatic variables (ph_inton0.c lines 1331-1344). ``cumdur`` is the
    # F0-command clock, mutated across make_f0_command calls; pass a list-cell.
    cumdur: list[int] = [0]
    mf0 = 0
    pholas = GEN_SIL
    struclas = 0
    targf0 = 0
    delayf0 = 0
    f0fall = 0
    inputscrewup = False

    # Per-clause initialization (ph_inton0.c lines 1352-1366).
    pDphsettar.nrises_sofar = 0
    pDphsettar.hatsize = 0
    pDphsettar.hat_loc_re_baseline = 0
    pDph_t.had_hatbegin = 0
    pDph_t.had_hatend = 0
    pDph_t.nf0tot = 0

    # Ensure clause-scoped arrays are large enough for in-place mutation
    # (the C assumes fixed-size NPHON_MAX arrays; Rule 9 shifts them).
    _ensure_buffer(pDph_t.allophons, NPHON_MAX)
    _ensure_buffer(pDph_t.allofeats, NPHON_MAX)
    _ensure_buffer(pDph_t.allodurs, NPHON_MAX)
    if pDph_t.user_f0 is None:
        pDph_t.user_f0 = [0] * NPHON_MAX
    else:
        _ensure_buffer(pDph_t.user_f0, NPHON_MAX)
    if pDph_t.user_offset is None:
        pDph_t.user_offset = [0] * NPHON_MAX

    # Local make_f0_command shim binding cumdur (pDph_t, rule, tar, delay, len).
    def _f0(rule: int, tar: int, delay: int, length: int = 0) -> None:
        _make_f0_command(pDph_t, rule, tar, delay, length, cumdur)

    # MAIN LOOP — one iteration per output phoneme. The C ``for`` condition
    # re-reads nallotot, which Rule 9 grows.
    nphon = 0
    while nphon < pDph_t.nallotot:
        if nphon > 0:
            pholas = pDph_t.allophons[nphon - 1]
            struclas = pDph_t.allofeats[nphon - 1]
            # fealas (phone_feature of pholas) is unused on the US path.

        phocur = pDph_t.allophons[nphon]
        struccur = pDph_t.allofeats[nphon]
        stresscur = struccur & FSTRESS
        feacur = phone_feature(phocur)
        phonex = 0
        if nphon < (pDph_t.nallotot - 1):
            phonex = pDph_t.allophons[nphon + 1]

        # ---- Rule 0: user-specified F0 targets / singing ----
        # The C does ``goto skiprules`` here, jumping past Rules 1-8 but
        # still running the cumdur/tcumdur tail and Rule 9.
        skiprules = False
        if pDph_t.f0mode == PHONE_TARGETS_SPECIFIED or pDph_t.f0mode == SINGING:
            assert pDph_t.user_f0 is not None
            if pDph_t.user_f0[nphon] != 0:
                _f0(0, 2000 + pDph_t.user_f0[nphon], 0)
            skiprules = True

        if not skiprules:
            # Rule 1 hat-begin / hat-end arming (unconditional).
            if struccur & FHAT_BEGINS:
                pDph_t.had_hatbegin = 1
            if struccur & FHAT_ENDS:
                pDph_t.had_hatend = 1

            if pDph_t.f0mode == NORMAL or pDph_t.f0mode == HAT_F0_SIZES_SPECIFIED:
                if feacur & FSYLL:
                    # ---- Rule 1: hat rise on first stressed syllable ----
                    if pDph_t.had_hatbegin:
                        pDph_t.had_hatbegin = 0
                        delayf0 += 1
                        if pDph_t.f0mode == NORMAL:
                            pDphsettar.hatsize = pDph_t.size_hat_rise
                            if pDph_t.cbsymbol:
                                pDphsettar.hatsize >>= 1
                            pDphsettar.hatsize &= 0o37776  # Must be even.
                            pDphsettar.hatsize |= 0o2  # Must be non-zero.
                            delayf0 = 0
                            if struccur & FHAT_ENDS:
                                delayf0 = -NF80MS
                            _f0(1, pDphsettar.hatsize, delayf0)
                        elif pDph_t.f0mode == HAT_F0_SIZES_SPECIFIED:
                            assert pDph_t.user_f0 is not None
                            assert pDph_t.user_offset is not None
                            pDphsettar.hatsize = ((pDph_t.user_f0[mf0] - 200) * 10) + 2
                            if (
                                pDphsettar.hatsize >= 2000
                                or pDphsettar.hatsize <= 0
                                or inputscrewup
                            ):
                                pDphsettar.hatsize = 2
                                inputscrewup = True
                            delayf0 = mstofr(pDph_t.user_offset[mf0])
                            mf0 += 1
                            _f0(1, pDphsettar.hatsize, delayf0)
                        pDphsettar.hat_loc_re_baseline += pDphsettar.hatsize

                    # ---- Rule 2: stress pulse on every primary/emph vowel ----
                    targf0 = 0
                    if stresscur & FSTRESS_1:
                        targf0 = (
                            us_f0_stress_level[stresscur]
                            + us_f0_phrase_position[pDphsettar.nrises_sofar]
                        )
                        if pDph_t.cbsymbol:
                            targf0 >>= 1  # All gestures reduced in "?".
                        delayf0 = pDph_t.allodurs[nphon] >> 2
                        if (struccur & FHAT_ENDS) or (struccur & FPERNEXT):
                            delayf0 = -NF60MS
                        if stresscur == FEMPHASIS:
                            delayf0 = 0
                        if pDph_t.f0mode == HAT_F0_SIZES_SPECIFIED:
                            assert pDph_t.user_f0 is not None
                            assert pDph_t.user_offset is not None
                            targf0 = ((pDph_t.user_f0[mf0] - 1000) * 10) + 1
                            if targf0 >= 2000 or targf0 <= 0 or inputscrewup:
                                targf0 = 1
                                inputscrewup = True
                            delayf0 = mstofr(pDph_t.user_offset[mf0])
                            mf0 += 1
                        # Scale by speaker-def SR, bumped to 16 for emphatic.
                        pDph_t.arg1 = pDph_t.scale_str_rise
                        if stresscur == FEMPHASIS and pDph_t.arg1 < 16:
                            pDph_t.arg1 = 16
                        pDph_t.arg2 = targf0
                        pDph_t.arg3 = 32
                        targf0 = muldv(pDph_t.arg1, pDph_t.arg2, pDph_t.arg3)
                        targf0 |= 0o1  # Must be odd -> decoded as IMPULSE.
                        _f0(2, targf0, delayf0)
                        if pDphsettar.nrises_sofar < MAX_NRISES:
                            pDphsettar.nrises_sofar += 1

                    # ---- Rule 3: execute hat fall ----
                    if pDph_t.had_hatend:
                        pDph_t.had_hatend = 0
                        if pDph_t.f0mode == NORMAL:
                            f0fall = F0_FINAL_FALL
                            delayf0 = pDph_t.allodurs[nphon] - NF160MS
                            if delayf0 < NF25MS:
                                delayf0 = NF25MS
                            if (struccur & FBOUNDARY) == FCBNEXT:
                                f0fall = 120
                            if (struccur & FBOUNDARY) == FVPNEXT:
                                f0fall = 0
                            if (struccur & FBOUNDARY) < FVPNEXT:
                                for nphonx in range(nphon + 1, pDph_t.nallotot):
                                    if pDph_t.allofeats[nphonx] & FHAT_BEGINS:
                                        f0fall = 0
                                        break
                                    if phone_feature(pDph_t.allophons[nphonx]) & FSYLL:
                                        if not (pDph_t.allofeats[nphonx] & FSTRESS):
                                            delayf0 = pDph_t.allodurs[nphon] - NF50MS
                                        if (pDph_t.allofeats[nphonx] & FBOUNDARY) == FVPNEXT:
                                            f0fall = 0
                                            break
                                        if (pDph_t.allofeats[nphonx] & FBOUNDARY) > FVPNEXT:
                                            f0fall = F0_NON_FINAL_FALL
                                            break
                            # bfound:
                            if (struccur & FBOUNDARY) == FQUENEXT:
                                f0fall = F0_QSYLL_FALL
                            f0fall = frac4mul(f0fall, pDph_t.assertiveness)
                            if pDph_t.cbsymbol:
                                f0fall = f0fall >> 1
                            f0fall &= 0o37776  # Must be even.
                            f0fall += pDphsettar.hatsize
                        elif pDph_t.f0mode == HAT_F0_SIZES_SPECIFIED:
                            assert pDph_t.user_f0 is not None
                            assert pDph_t.user_offset is not None
                            f0fall = ((pDph_t.user_f0[mf0] - 400) * 10) + 2
                            if f0fall >= 2000 or f0fall <= 0 or inputscrewup:
                                f0fall = 2
                                inputscrewup = True
                            delayf0 = mstofr(pDph_t.user_offset[mf0])
                            mf0 += 1
                        _f0(3, -f0fall, delayf0)
                        pDphsettar.hat_loc_re_baseline -= f0fall

                    # ---- Rule 4: nonterminal fall-rise on clause-final stress ----
                    if ((struccur & FBOUNDARY) == FCBNEXT) or ((struccur & FBOUNDARY) == FQUENEXT):
                        delayf0 = pDph_t.allodurs[nphon] - NF80MS
                        if (struccur & FBOUNDARY) == FQUENEXT:
                            _f0(4, 181, delayf0)
                            _f0(4, 251, pDph_t.allodurs[nphon])
                        else:
                            delayf0 += NF20MS
                            _f0(4, 71, delayf0)
                            _f0(4, 101, pDph_t.allodurs[nphon])

                # ---- Rule 5: final fall (glottalise) + Rule 6 continuation ----
                if feacur & FSYLL:
                    if (not (stresscur & FSTRESS_1)) or (not (struccur & FHAT_ENDS)):
                        # Rule 5: pitch falls at end of declarative sentence.
                        if (struccur & FBOUNDARY) == FPERNEXT or (
                            struccur & FBOUNDARY
                        ) == FEXCLNEXT:
                            targf0 = F0_GLOTTALIZE
                            targf0 = frac4mul(targf0, pDph_t.assertiveness)
                            targf0 |= 0o1  # Must be odd.
                            _f0(5, targf0, pDph_t.allodurs[nphon] - NF100MS)

                        # Rule 6: continuation rise before comma / question.
                        delayf0 = pDph_t.allodurs[nphon] - NF80MS
                        if (struccur & FBOUNDARY) == FQUENEXT:
                            _f0(6, 181, delayf0)
                            _f0(6, 251, pDph_t.allodurs[nphon])
                        if (struccur & FBOUNDARY) == FCBNEXT:
                            delayf0 += NF20MS
                            _f0(6, 71, delayf0)
                            _f0(6, 101, pDph_t.allodurs[nphon])

                # ---- Rule 7: reset baseline at end of sentence ----
                if phocur == GEN_SIL:
                    if pDphsettar.hat_loc_re_baseline != 0 and pDph_t.nf0tot > 0:
                        _f0(7, -(pDphsettar.hat_loc_re_baseline), 0)
                        pDphsettar.hat_loc_re_baseline = 0
                    if nphon > 0:
                        pDphsettar.nrises_sofar = 1  # Soft reset.

                    # ---- Rule 8: hard reset baseline at sentence end ----
                    if struclas & FSENTENDS:
                        _f0(8, 0, 0)
                        pDphsettar.hat_loc_re_baseline = 0
                        pDphsettar.nrises_sofar = 0

        # skiprules: END OF F0 RULES.

        # Update cumdur to time at end of current phone (ph_inton0.c:1963).
        cumdur[0] += pDph_t.allodurs[nphon]

        # NO tcumdur accumulation here -- in the active production build
        # (ENGLISH_US + OLD_INTONATION_AND_TIMING, HLSYN undefined) tcumdur
        # is zeroed by us_phtiming (p_us_tim0.c line 124) and never
        # accumulated anywhere: the accumulating code lives in
        # ph_inton0.c's FIRST phinton definition (lines 1086 / 1125),
        # which sits inside ``#if defined NWSNOAA || defined ENGLISH_UK``
        # -- dead on this build. The consumers are written for the zero:
        # ph_drwt01.c guards ``if (tcumdur == 0) tcumdur = 1`` (lines
        # 761 / 1550) before dividing by it, and ph_draw.c's
        # ``nframb > tcumdur-92`` end-of-phrase comparisons are
        # always-true at 0 (issue #270 audit).

        # ---- Rule 9: insert dummy schwa after clause-final plosive ----
        # ph_inton0.c lines 1970-1994 (ENGLISH_US).
        if phonex == GEN_SIL and USP_P <= phocur <= USP_G and pDph_t.nallotot < NPHON_MAX:
            for n in range(pDph_t.nallotot, nphon, -1):
                pDph_t.allophons[n] = pDph_t.allophons[n - 1]
                pDph_t.allofeats[n] = pDph_t.allofeats[n - 1]
                pDph_t.allodurs[n] = pDph_t.allodurs[n - 1]
                pDph_t.user_f0[n] = pDph_t.user_f0[n - 1]
            pDph_t.allophons[nphon + 1] = SCHWA1
            if pholas < USP_AE or (USP_T <= phocur <= USP_D):
                pDph_t.allophons[nphon + 1] = SCHWA2
            pDph_t.allodurs[nphon + 1] = NF25MS
            cumdur[0] += NF25MS
            pDph_t.allofeats[nphon + 1] = pDph_t.allofeats[nphon] | FDUMMY_VOWEL
            pDph_t.nallotot += 1
            nphon += 1  # C does ``nphon++`` to skip the new schwa.

        nphon += 1


__all__ = ["phinton"]
