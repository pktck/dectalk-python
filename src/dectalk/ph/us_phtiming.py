"""``us_phtiming`` -- US-English per-allophone duration rules from p_us_tim0.c.

Translated from ``src/dapi/src/ph/p_us_tim0.c`` line 90 (~1100 LOC of C,
~970 active after preprocessor flags).

The production ``libtts_us.so`` builds with ``OLD_INTONATION_AND_TIMING``
defined (see ``src/dectalkf_klsyn.h:248``), which causes ``ph_time1.c``
to ``#include "p_us_tim0.c"`` rather than ``p_us_tim.c``. The two
files implement materially different duration-rule sets — ``p_us_tim.c``
includes a part-of-speech multiplier (``F_NOUN`` / ``F_VERB``), Rules
24/25/26 (RR retroflex floor, unvoiced-after-vowel lengthening,
word-initial HX clamp), and a different stress-rhythm rebalance pass
(using ``FSON1`` + non-nasal); ``p_us_tim0.c`` is the older, leaner
rule set that this Python port targets.

The function walks every allophone in the current clause and computes
its frame duration (``pDph_t.allodurs[nphon]``) by applying ~22 named
duration rules. The rules layer multiplicative scaling factors
(``prcnt``, in Q14 fixed-point with ``100% == 128``) onto a per-phone
inherent / minimum-duration pair, plus additive increments
(``deldur``, in frames). The final duration is then scaled by the
speaking-rate factors that :func:`~dectalk.ph.init_timing.init_timing`
cached into ``pDphsettar.sprat1`` / ``sprat2``.

Inputs (mutated on ``p_dph_t``):

- ``allodurs[nphon]``: per-allophone frame duration (the function's
  primary output).
- ``tcumdur``: zeroed at function entry (durations are recomputed).
- ``asperation``: rescaled in the silence-pause branch.
- ``longcumdur``: incremented by ``durxx * NSAMP_FRAME`` per phone.
- ``pSTphsettar.numstresses``: incremented for each stressed allophone.

Inputs (consumed):

- ``allophons[]`` / ``allofeats[]``: per-phone allophone code and
  packed feature bits.
- ``user_durs[]``: optional user-specified duration override
  (millisecond units).
- ``pDphsettar.sprat0`` / ``sprat1`` / ``sprat2``: speaking-rate
  fields populated by :func:`init_timing`.
- ``pKsd_t.sprate``: raw speaking rate in words-per-minute.

C-source preprocessing notes
----------------------------

The build that produces ``libtts_us.so`` defines:

- ``LANGUAGE=ENGLISH`` (no specific language sub-flag in CFLAGS but
  the ``LANG_english`` runtime dispatch picks this path).
- ``ENGLISH_US`` (US-English-specific behaviour).
- ``OLD_INTONATION_AND_TIMING`` (selects p_us_tim0.c via ph_time1.c).
- ``TYPING_MODE`` (enables the typing-mode fast-path; the function
  honours ``phTTS->bInTypingMode``).

Not defined: ``NEWTYPING_MODE``, ``CHANGES_FOR_V44``, ``MSDBG*``,
``MSDEBUG``, ``DEBUGPHT``, ``SLOWTALK``, ``EABDEBUG``, ``SPANISH``,
``ENGLISH_UK``. Branches inside those guards are omitted from the
Python port; comments preserve the rule number / intent.

``NSAMP_FRAME`` is 71 in this build (10 kHz frame rate, 7.1 ms
frames), so the ``if (NSAMP_FRAME == 128)`` branch at line 1030 is
dead code and is omitted.

C ``goto break3`` semantics
---------------------------

``p_us_tim0.c`` uses three ``goto break3`` sites and one fall-through:

- ``goto break3`` from the user_durs branch (line 183): durxx is set
  via ``mstofr(user_durs[n] + 4)``; the goto skips the entire rule
  body **including** the speaking-rate scaling block and the
  stress-rhythm rebalance pass.
- ``goto break3`` from the silence branch (line 283): durxx is set
  to ``dpause`` which has *already* been scaled by ``sprat1`` inside
  the silence block; again the rate-scaling-of-durxx block is skipped
  and so is the rhythm pass.
- ``goto break3`` from the [s,th]+SH cluster shortcut (line 679):
  durxx is set to ``NF15MS``; skips rate scaling and rhythm pass.
- Fall-through past line 855: durxx is computed from ``prcnt *
  (durinh - durmin) >> 7 + durmin``, then the rate-scaling block
  runs, then the rhythm pass runs, and finally break3 writes
  ``allodurs[nphon]`` and updates ``longcumdur``.

This Python port preserves the asymmetry: the three goto sites
``continue`` straight to the break3 epilogue (TYPING_MODE override +
longcumdur+=), while the fall-through path executes the speaking-rate
scaling and rhythm-pass between rule body and epilogue.
"""

# ruff: noqa: N803, N806, PLR0912, PLR0915, PLR2004, PLR1714, PLR1730, PLR5501, SIM102, SIM108, SIM109 -- mirror C structure

from __future__ import annotations

from typing import Final, cast

from dectalk.include.usp_codes import (
    USP_AX,
    USP_CH,
    USP_D,
    USP_DF,
    USP_DX,
    USP_EN,
    USP_HX,
    USP_IX,
    USP_IY,
    USP_LL,
    USP_LX,
    USP_N,
    USP_NX,
    USP_RX,
    USP_S,
    USP_SH,
    USP_T,
    USP_TH,
    USP_W,
)
from dectalk.kernel.ksd_t import KsdT
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import (
    FBOUNDARY,
    FCBNEXT,
    FEMPHASIS,
    FFIRSTSYL,
    FHAT_ENDS,
    FISBOUND,
    FMBNEXT,
    FMEDIALSYL,
    FMONOSYL,
    FNOSTRESS,
    FPPNEXT,
    FSENTENDS,
    FSTRESS,
    FSTRESS_1,
    FTYPESYL,
    FVPNEXT,
    FWBNEXT,
    FWINITC,
)
from dectalk.ph.frame_counts import NF7MS, NF15MS, NF20MS, NF25MS, NF30MS, NF40MS
from dectalk.ph.inton_constants import SINGING
from dectalk.ph.math_helpers import mlsh1
from dectalk.ph.numeric_constants import FRAC_HALF, FRAC_ONE, NSAMP_FRAME
from dectalk.ph.phoneme_features import (
    FCONSON,
    FNASAL,
    FOBST,
    FPLOSV,
    FSON1,
    FSON2,
    FSONCON,
    FSONOR,
    FSYLL,
    FVOICD,
    FVOWEL,
)
from dectalk.ph.q14_percent_constants import (
    N10PRCNT,
    N25PRCNT,
    N35PRCNT,
    N50PRCNT,
    N60PRCNT,
    N70PRCNT,
    N80PRCNT,
    N85PRCNT,
    N120PRCNT,
    N150PRCNT,
)
from dectalk.ph.task_helpers import mstofr
from dectalk.ph.timing import inh_timing as _inh_timing
from dectalk.ph.timing import min_timing as _min_timing
from dectalk.ph.timing import phone_feature
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.utterance_constants import GEN_SIL

# Constants from p_us_tim0.c (matches the ph_timng.c constants).
BASE_ASP: Final[int] = 500
MAX_ASP_COMMA: Final[int] = 8
MIN_ASP_COMMA: Final[int] = -4
MAX_ASP_PERIOD: Final[int] = 20
MIN_ASP_PERIOD: Final[int] = -10


def _inh_dur_frames(phone: int) -> int:
    """Return ``((inh_timing(phone) * 10) + 50) >> 6`` -- ms-to-frame."""
    return ((_inh_timing(phone) * 10) + 50) >> 6


def _min_dur_frames(phone: int) -> int:
    """Return ``((min_timing(phone) * 10) + 50) >> 6`` -- ms-to-frame."""
    return ((_min_timing(phone) * 10) + 50) >> 6


def us_phtiming(phTTS: TtsHandle) -> None:
    """Compute per-allophone frame durations for the active US clause.

    Faithful line-by-line port of ``us_phtiming`` from
    ``src/dapi/src/ph/p_us_tim0.c`` line 90.
    """
    psonsw: int = 0
    posvoc: int = 0
    pDph_t = cast(DphT, phTTS.p_ph_thread_data)
    pKsd_t = cast(KsdT, phTTS.p_kernel_share_data)
    pDphsettar = cast(DphSettarSt, pDph_t.pSTphsettar)

    stcnt: int = 0
    syldur: int = 0
    ncnt: int = 0
    endcnt: int = 0
    vowcnt: int = 0
    adjust: int = 0
    emphasissw: int = 0  # FALSE
    pholas: int = GEN_SIL
    struclas: int = 0
    fealas: int = phone_feature(GEN_SIL)
    prcnt: int = 0
    durinh: int = 0
    durmin: int = 0
    deldur: int = 0
    phocur: int = 0
    feacur: int = 0
    feasyllabiccur: int = 0
    struccur: int = 0
    strucboucur: int = 0
    strucstresscur: int = 0
    dpause: int = 0
    arg1: int = 0
    arg2: int = 0

    minsize: int = 0  # TYPING_MODE

    # init_timing() is called by the orchestrator (api/speak.py) before
    # us_phtiming, not here. Re-zero tcumdur per the C source (line 124).
    pDph_t.tcumdur = 0

    # MAIN LOOP.
    for nphon in range(pDph_t.nallotot):
        if nphon > 0:
            pholas = pDph_t.allophons[nphon - 1]
            struclas = pDph_t.allofeats[nphon - 1]
            fealas = phone_feature(pholas)

        phocur = pDph_t.allophons[nphon]
        struccur = pDph_t.allofeats[nphon]
        strucboucur = struccur & FBOUNDARY
        feacur = phone_feature(phocur)
        feasyllabiccur = feacur & FSYLL
        strucstresscur = struccur & FSTRESS

        if nphon < (pDph_t.nallotot - 1):
            pDphsettar.phonex_timing = pDph_t.allophons[nphon + 1]
            pDphsettar.strucnex = pDph_t.allofeats[nphon + 1]
            pDphsettar.feanex = phone_feature(pDphsettar.phonex_timing)

        # p_us_tim0.c lines 161-164: numstresses increment.
        if struccur & FSTRESS:
            pDphsettar.numstresses += 1

        # `goto_break3` flag emulates the C goto: when set, skip the
        # speaking-rate scaling and rhythm-pass and jump to the
        # break3 epilogue.
        goto_break3 = False

        # User-specified duration short-circuit. (line 171-184)
        user_dur_val = 0
        if pDph_t.user_durs is not None and nphon < len(pDph_t.user_durs):
            user_dur_val = pDph_t.user_durs[nphon]
        if user_dur_val != 0:
            pDphsettar.durxx = mstofr(user_dur_val + 4)
            goto_break3 = True

        if not goto_break3:
            # Convert inherent / minimum duration in msec to frames.
            durinh = _inh_dur_frames(phocur)
            durmin = _min_dur_frames(phocur)

            deldur = 0
            prcnt = 128

            # Rule 1: Pause durations depend on syntax.
            if phocur == GEN_SIL:
                if (
                    ((pDphsettar.feanex & FVOICD) and (pDphsettar.feanex & FOBST))
                    or (pDphsettar.feanex & FPLOSV)
                ):
                    dpause = 1
                else:
                    dpause = 0

                pDph_t.asperation = (pDph_t.asperation - BASE_ASP) // 10

                if nphon > 1:
                    if (struclas & FBOUNDARY) == FCBNEXT:
                        # C bug: trailing `;` makes the `<` branch empty;
                        # the asperation = MIN_ASP_COMMA fires unconditionally.
                        if pDph_t.asperation > MAX_ASP_COMMA:
                            pDph_t.asperation = MAX_ASP_COMMA
                        pDph_t.asperation = MIN_ASP_COMMA
                        dpause = pDph_t.nfcomma + pDph_t.compause + pDph_t.asperation
                    if (struclas & FBOUNDARY) & FSENTENDS:
                        if pDph_t.asperation > MAX_ASP_PERIOD:
                            pDph_t.asperation = MAX_ASP_PERIOD
                        pDph_t.asperation = MIN_ASP_PERIOD
                        dpause = pDph_t.nfperiod + pDph_t.perpause + pDph_t.asperation
                elif pDph_t.newparagsw != 0:
                    dpause = pDph_t.nfperiod

                pDph_t.asperation = 0

                dpause = mlsh1(dpause, pDphsettar.sprat1)
                if dpause < NF7MS:
                    dpause = NF7MS

                pDphsettar.durxx = dpause
                durinh = pDphsettar.durxx
                durmin = pDphsettar.durxx
                goto_break3 = True

        if not goto_break3:
            # Rule 2: Lengthening of segments in clause-final rime.
            if strucboucur >= FCBNEXT:
                deldur = NF40MS
                if (feacur & FVOICD) and (feacur & FOBST):
                    deldur = NF20MS
                if feacur & FPLOSV:
                    deldur = 0
                if (
                    (phocur == USP_RX or phocur == USP_LX)
                    and (pDphsettar.feanex & FOBST)
                    and not (pDphsettar.feanex & FVOICD)
                ):
                    deldur = NF15MS
                if pDph_t.nallotot < 10 and feasyllabiccur and strucstresscur:
                    deldur += NF30MS - (pDph_t.nallotot >> 1)
                if pDphsettar.feanex & FSON1:
                    deldur -= NF20MS

            # Rule 3: Shortening of non-phrase-final syllabics.
            if feasyllabiccur:
                if (strucboucur < FVPNEXT and pKsd_t.sprate > 160) or (
                    strucboucur < FPPNEXT
                ):
                    prcnt = mlsh1(N70PRCNT, prcnt)

            # Rule 4: Shorten syllabic segs in syll-init / medial /
            # unstressed monosyl positions.
            if feasyllabiccur:
                if (
                    not (strucstresscur & FSTRESS_1)
                    and (struccur & FTYPESYL) == FMONOSYL
                ):
                    arg1 = N85PRCNT
                    if not strucstresscur:
                        arg1 = N70PRCNT
                    prcnt = mlsh1(arg1, prcnt)
                elif (struccur & FTYPESYL) != FMONOSYL and strucboucur < FWBNEXT:
                    # Initial vowel of each word shorter by .85.
                    arg1 = N85PRCNT
                    if (struccur & FTYPESYL) > FFIRSTSYL:
                        arg1 = N85PRCNT
                    prcnt = mlsh1(arg1, prcnt)

                # Rule 5: Shorten vowels in polysyllabic words.
                if (struccur & FTYPESYL) != FMONOSYL:
                    prcnt = mlsh1(prcnt, N80PRCNT)

            # Rule 6: Shortening of non-word-initial consonants.
            if not feasyllabiccur and not (struccur & FWINITC):
                if (
                    (feacur & FOBST)
                    and not (feacur & FPLOSV)
                    and (struccur & FBOUNDARY) == FWBNEXT
                ):
                    deldur += NF20MS
                else:
                    prcnt = mlsh1(prcnt, N85PRCNT)

            # Rule 7: Shortening of unstressed segs.
            if not (strucstresscur & FSTRESS_1):
                if durmin < durinh and not (feacur & FOBST):
                    if not strucstresscur:
                        durmin = durmin >> 1
                    else:
                        durmin -= durmin >> 2
                if feasyllabiccur:
                    if (struccur & FTYPESYL) == FMEDIALSYL:
                        prcnt = prcnt >> 1
                    else:
                        prcnt = mlsh1(prcnt, N70PRCNT)
                    if phocur == USP_AX or phocur == USP_IX:
                        if (
                            pholas == USP_DX
                            or pDphsettar.phonex_timing == USP_DX
                            or pDphsettar.phonex_timing == USP_HX
                        ):
                            deldur += NF25MS
                else:
                    if USP_W <= phocur <= USP_LL:
                        prcnt = prcnt >> 1
                    else:
                        prcnt = mlsh1(prcnt, N70PRCNT)
            else:
                # Penultimate lengthening of stressed syllabic with hat-fall.
                if feasyllabiccur:
                    if (
                        (struccur & FHAT_ENDS)
                        and strucboucur < FVPNEXT
                        and strucboucur > FMBNEXT
                    ):
                        deldur = deldur + NF25MS

            # Rule 8: Lengthen each seg of an emphasized syllable.
            if (struccur & FWINITC) or (
                feasyllabiccur and strucstresscur != FEMPHASIS
            ):
                emphasissw = 0
            if strucstresscur == FEMPHASIS:
                emphasissw = 1
            if emphasissw == 1:
                deldur = deldur + NF20MS
                if feasyllabiccur:
                    deldur = deldur + NF40MS

            # Rule 9: Influence of final conson on vowels and postvoc sonor.
            psonsw = 0
            arg1 = FRAC_ONE
            posvoc = GEN_SIL
            if feasyllabiccur or (
                USP_RX <= phocur <= USP_NX
                and not (struccur & (FSTRESS | FWINITC))
                and (pDphsettar.feanex & FOBST)
            ):
                if (not (pDphsettar.feanex & FSYLL)) and not (
                    pDphsettar.strucnex & (FSTRESS | FWINITC)
                ):
                    posvoc = pDphsettar.phonex_timing
                    if (
                        nphon + 2 < pDph_t.nallotot
                        and USP_RX <= posvoc <= USP_NX
                        and (phone_feature(pDph_t.allophons[nphon + 2]) & FOBST)
                        and not (pDph_t.allofeats[nphon + 2] & (FSTRESS | FWINITC))
                    ):
                        psonsw = 1
                        posvoc = pDph_t.allophons[nphon + 2]
                    if posvoc != GEN_SIL:
                        if not (phone_feature(posvoc) & FVOICD):
                            deldur = deldur - (deldur >> 1)
                            arg1 = N80PRCNT
                            if (phone_feature(posvoc) & FPLOSV) or posvoc == USP_CH:
                                arg1 = N70PRCNT
                        else:
                            if (phone_feature(posvoc) & FOBST) and phocur != USP_EN:
                                arg1 = N120PRCNT
                                if (
                                    not (phone_feature(posvoc) & FPLOSV)
                                    and posvoc != USP_DX
                                    and (feacur & FSYLL)
                                ):
                                    deldur = deldur + NF25MS
                            elif phone_feature(posvoc) & FNASAL:
                                arg1 = N85PRCNT
                if strucboucur < FVPNEXT or psonsw == 1:
                    arg1 = FRAC_HALF + (arg1 >> 1)
                # [nt] postvocalic cluster shortcut.
                if (
                    phocur == USP_N
                    and pDphsettar.phonex_timing == USP_T
                    and not (pDphsettar.strucnex & (FWINITC | FSTRESS))
                ):
                    arg1 = N10PRCNT
                    if (
                        nphon + 2 < pDph_t.nallotot
                        and (phone_feature(pDph_t.allophons[nphon + 2]) & FSYLL)
                        and not (pDph_t.allofeats[nphon + 2] & FMEDIALSYL)
                    ):
                        pDph_t.allophons[nphon + 1] = USP_D
                        arg1 = N70PRCNT
                prcnt = mlsh1(arg1, prcnt)

            # Rule 10/11/12: Two-vowel lengthen / word-init stressed /
            # pre-postvoc-L shortening.
            if feasyllabiccur:
                if pDphsettar.feanex & FSYLL:
                    deldur = deldur + NF30MS
                if (
                    (struccur & FTYPESYL) == FFIRSTSYL
                    and (struccur & FSTRESS_1)
                    and not (struclas & FWINITC)
                ):
                    deldur += NF25MS
                if pDphsettar.phonex_timing == USP_LX:
                    deldur -= NF20MS
            else:
                # Rule 13: Shorten consonant clusters.
                if feacur & FCONSON:
                    if (pDphsettar.feanex & FCONSON) and strucboucur < FVPNEXT:
                        arg1 = N70PRCNT
                        if (feacur & FNASAL) and (pDphsettar.strucnex & FWINITC):
                            arg1 = N150PRCNT
                        else:
                            durmin -= durmin >> 2
                        if phocur == USP_S or phocur == USP_TH:
                            if pDphsettar.feanex & FPLOSV:
                                arg1 = FRAC_HALF
                            if pDphsettar.phonex_timing == USP_SH:
                                pDphsettar.durxx = NF15MS
                                goto_break3 = True
                        if not goto_break3:
                            prcnt = mlsh1(arg1, prcnt)
                    if (not goto_break3) and (fealas & FCONSON) and (
                        struclas & FBOUNDARY
                    ) < FVPNEXT:
                        arg1 = N70PRCNT
                        durmin -= durmin >> 2
                        if feacur & FPLOSV:
                            if pholas == USP_S:
                                arg1 = N60PRCNT
                            if fealas & FNASAL:
                                if not strucstresscur:
                                    arg1 = 1638
                        prcnt = mlsh1(arg1, prcnt)

        if not goto_break3:
            # Rule 14: Increase sonor dur if preceding plosive is aspirated.
            if feacur & FSON1:
                if not (fealas & FVOICD) and (fealas & FPLOSV):
                    deldur = deldur + NF20MS

            # Rule 15: Increase duration of phrase-initial vowels.
            if (feacur & FVOWEL) and pholas == GEN_SIL:
                deldur = deldur + NF20MS

            # Rule 16: Increase vowel dur if preceded by non-nasal sonor.
            if feacur & FVOWEL:
                if (fealas & FSON2) and not (fealas & FNASAL):
                    if deldur == 0:
                        deldur = NF20MS

            # Rule 17: More lengthening of segments if in a short phrase.
            if pDph_t.nallotot < 10 and durinh != durmin:
                prcnt += 30

            # Rule 18 (#ifdef NEVER) omitted.

            # Rule 19: Shorten function word final TH ("with").
            if (
                phocur == USP_TH
                and (struccur & FTYPESYL) == FMONOSYL
                and strucboucur >= FWBNEXT
                and strucstresscur == FNOSTRESS
            ):
                prcnt = mlsh1(prcnt, N60PRCNT)

            # Rule 20: Lengthen i in "the" / "he" / "me".
            if (
                phocur == USP_IY
                and (struccur & FBOUNDARY) > FMBNEXT
                and strucstresscur == FNOSTRESS
                and (struccur & FTYPESYL) == FMONOSYL
            ):
                prcnt = mlsh1(prcnt, N150PRCNT)

            # Rule 21: Shorten stop following stop preceding fricative same syl.
            if (
                (feacur & FPLOSV)
                and (fealas & FPLOSV)
                and (pDphsettar.feanex & FOBST)
                and strucboucur > FMBNEXT
            ):
                durmin = durmin >> 1
                prcnt = mlsh1(prcnt, N25PRCNT)

            # Rule 23: Shorten vowel if phonex == DF (writing vs riding).
            if pDphsettar.phonex_timing == USP_DF:
                prcnt = mlsh1(prcnt, N35PRCNT)

            # eab 3-94: feanex plosive + feacur consonant.
            if (pDphsettar.feanex & FPLOSV) and (feacur & FCONSON):
                durmin = durmin >> 1
                prcnt = mlsh1(prcnt, N50PRCNT)

            pDphsettar.strucstressprev = strucstresscur

            # Set durxx = prcnt * (durinh - durmin) / 128 + durmin.
            pDphsettar.durxx = (prcnt * (durinh - durmin)) >> 7
            pDphsettar.durxx += durmin

            # Speaking-rate scaling (lines 874-893).
            if pDphsettar.sprat0 != 180 and pDphsettar.durxx != 0:
                pDphsettar.durxx = mlsh1(pDphsettar.durxx, pDphsettar.sprat2) + 1
                deldur = mlsh1(deldur, pDphsettar.sprat1)
            pDphsettar.durxx = pDphsettar.durxx + deldur

            # Clamp negative durxx.
            if pDphsettar.durxx < 0:
                pDphsettar.durxx = 1

            pDph_t.allodurs[nphon] = pDphsettar.durxx
            if pDph_t.allophons[nphon] != 0:
                syldur += pDphsettar.durxx
            if (feacur & FSONOR) and pDph_t.allophons[nphon] != 0:
                vowcnt += 1

            # Stress-rhythm rebalance: FISBOUND or penultimate.
            # NOTE the C operator-precedence bug at line 912:
            # `(((cond) == FISBOUND) && nphon != 0 || nphon == nallotot - 2)`
            # parses as `((cond && nphon != 0) || nphon == nallotot - 2)`.
            is_isbound = (struccur & FISBOUND) == FISBOUND
            if (is_isbound and nphon != 0) or nphon == pDph_t.nallotot - 2:
                timeref_minus = pDph_t.timeref - (syldur >> 1)
                if vowcnt == 1:
                    adjust = timeref_minus
                elif vowcnt == 2:
                    adjust = timeref_minus >> 1
                elif vowcnt == 3:
                    adjust = (timeref_minus >> 3) * 3
                elif vowcnt == 4:
                    adjust = timeref_minus >> 2
                elif vowcnt == 5:
                    adjust = timeref_minus >> 3
                else:
                    adjust = timeref_minus >> 4

                # sprat0-based attenuation.
                if pDphsettar.sprat0 <= 250:
                    adjust = 0
                elif pDphsettar.sprat0 >= 325:
                    adjust = adjust >> 1
                elif pDphsettar.sprat0 >= 250:
                    adjust = adjust >> 2

                user_dur_active = (
                    pDph_t.user_durs is not None
                    and nphon < len(pDph_t.user_durs)
                    and pDph_t.user_durs[nphon] != 0
                )
                if user_dur_active or pDph_t.f0mode == SINGING:
                    adjust = 0

                # Redistribute adjust across phones with allophone code 1..7
                # (the FSON1 sonorants in the original table).
                endcnt = nphon
                while stcnt - endcnt != 0:
                    phon_e = pDph_t.allophons[endcnt]
                    if 0 < phon_e <= 7:
                        pDph_t.allodurs[endcnt] += adjust
                        if pDph_t.allodurs[endcnt] <= 6:
                            pDph_t.allodurs[endcnt] = 6
                        ncnt += 1
                    endcnt -= 1
                    if endcnt < 0:
                        break

                ncnt = 0
                stcnt = nphon
                syldur = 0
                vowcnt = 0

        # break3 epilogue.
        # NSAMP_FRAME == 128 branch is dead code (NSAMP_FRAME == 71).
        if pDphsettar.durxx <= 0:
            pDphsettar.durxx = 1
        pDph_t.allodurs[nphon] = pDphsettar.durxx

        _typing_mode_override(
            phTTS=phTTS,
            pDph_t=pDph_t,
            nphon=nphon,
            phocur=phocur,
            feacur=feacur,
            minsize_in=minsize,
        )

        pDph_t.longcumdur += pDphsettar.durxx * NSAMP_FRAME


def _typing_mode_override(
    *,
    phTTS: TtsHandle,
    pDph_t: DphT,
    nphon: int,
    phocur: int,
    feacur: int,
    minsize_in: int,
) -> None:
    """``#ifdef TYPING_MODE`` override (p_us_tim0.c lines 1072-1095)."""
    del minsize_in
    if not getattr(phTTS, "bInTypingMode", False):
        return
    denom = pDph_t.nallotot - 1
    if denom <= 0:
        return
    minsize = 30 // denom
    if minsize < 6:
        minsize = 6
    if (feacur & FSONOR) and phocur != GEN_SIL:
        pDph_t.allodurs[nphon] = minsize
    else:
        if pDph_t.allophons[nphon] == USP_S:
            pDph_t.allodurs[nphon] = 5
        else:
            pDph_t.allodurs[nphon] = 1


__all__ = ["us_phtiming"]
