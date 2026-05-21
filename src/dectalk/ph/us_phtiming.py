"""``us_phtiming`` -- US-English per-allophone duration rules from p_us_tim.c.

Translated from ``src/dapi/src/ph/p_us_tim.c`` line 107 (~1300 lines
of C, ~1100 lines of which are active under ``ENGLISH_US`` /
``TYPING_MODE`` -- the build flags for ``libtts_us.so``).

The function walks every allophone in the current clause and computes
its frame duration (``pDph_t.allodurs[nphon]``) by applying 26 named
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
- ``ACNA`` (extra dictionary entries; irrelevant here).
- ``TYPING_MODE`` (enables the typing-mode fast-path; the function
  honours ``phTTS->bInTypingMode``).

Not defined: ``TOMBUCHLER``, ``NEWTYPING_MODE``, ``FASTTALK``,
``SLOWTALK``, ``EPSON_ARM7``, ``MSDOS``, ``ASKKEN``, ``NEVER_USED``,
``needsrefining``, ``OUTFORNOW``, and all ``MSDBG*`` /
``MSDEBUG`` / ``DEBUGPHT`` debug-print guards. Branches inside
those guards are omitted from the Python port; comments preserve
the rule number / intent.

``HLSYN`` is the back-end synthesizer directory name, not a
``#define``, so ``#ifdef HLSYN`` branches inside ``us_phtiming``
proper are NOT compiled. (``init_timing``'s HLSYN branch is in
``ph_timng.c``, which is a separate translation unit; that branch
*is* picked up because the ``ph`` source's compilation flag set
differs -- see init_timing.py's docstring for context.)

``NSAMP_FRAME`` is 71 in this build (10 kHz frame rate, 7.1 ms
frames), so the ``if (NSAMP_FRAME == 128)`` branch at line 1255 is
dead code and is omitted.
"""

# ruff: noqa: N803, N806, PLR0912, PLR0915, PLR2004, PLR1714, PLR1730, PLR5501, SIM102, SIM108, SIM109 -- mirror C structure

from __future__ import annotations

from typing import Final, cast

from dectalk.include.usp_codes import (
    USP_AX,
    USP_CH,
    USP_DF,
    USP_DX,
    USP_EN,
    USP_HX,
    USP_IX,
    USP_LL,
    USP_LX,
    USP_LY,
    USP_NX,
    USP_Q,
    USP_RR,
    USP_RX,
    USP_S,
    USP_SH,
    USP_TH,
    USP_W,
)
from dectalk.kernel.ksd_t import KsdT
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import (
    F_ADJ,
    F_FUNC,
    F_NOUN,
    F_VERB,
    FBOUNDARY,
    FCBNEXT,
    FEMPHASIS,
    FFIRSTSYL,
    FHAT_ENDS,
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
from dectalk.ph.frame_counts import NF15MS, NF20MS, NF25MS, NF30MS, NF40MS
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
    FSYLL,
    FVOICD,
    FVOWEL,
    WORDFEAT,
)
from dectalk.ph.q14_percent_constants import (
    N25PRCNT,
    N40PRCNT,
    N60PRCNT,
    N70PRCNT,
    N75PRCNT,
    N80PRCNT,
    N85PRCNT,
    N90PRCNT,
    N100PRCNT,
    N120PRCNT,
    N130PRCNT,
)
from dectalk.ph.task_helpers import mstofr
from dectalk.ph.timing import inh_timing as _inh_timing
from dectalk.ph.timing import min_timing as _min_timing
from dectalk.ph.timing import phone_feature
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.utterance_constants import GEN_SIL

# Constants from ph_timng.c lines 125-129.
BASE_ASP: Final[int] = 500
MAX_ASP_COMMA: Final[int] = 8
MIN_ASP_COMMA: Final[int] = -4
MAX_ASP_PERIOD: Final[int] = 20
MIN_ASP_PERIOD: Final[int] = -10


def _inh_dur_frames(phone: int) -> int:
    """Return ``((inh_timing(phone) * 10) + 50) >> 6`` -- ms-to-frame.

    Faithful translation of the C macro at p_us_tim.c lines 218.
    ``inh_timing`` returns milliseconds; the conversion rounds to
    the nearest frame at 64-sample frames.
    """
    return ((_inh_timing(phone) * 10) + 50) >> 6


def _min_dur_frames(phone: int) -> int:
    """Return ``((min_timing(phone) * 10) + 50) >> 6`` -- ms-to-frame.

    Faithful translation of the C macro at p_us_tim.c lines 219.
    """
    return ((_min_timing(phone) * 10) + 50) >> 6


def us_phtiming(phTTS: TtsHandle) -> None:
    """Compute per-allophone frame durations for the active US clause.

    Faithful line-by-line port of ``us_phtiming`` from
    ``src/dapi/src/ph/p_us_tim.c`` line 107.

    The function:

    1. Calls :func:`~dectalk.ph.init_timing.init_timing` to seed the
       per-clause speaking-rate factors (note: this Python port does
       *not* call ``init_timing`` -- the orchestrator in
       :mod:`dectalk.api.speak` calls ``init_timing`` *before*
       ``us_phtiming``, so the C source's redundant call is dropped).
    2. Walks every ``nphon`` in ``[0, nallotot)``.
    3. Applies 26 named duration rules layering ``prcnt`` (Q14
       multiplicative scaling) and ``deldur`` (additive frame count)
       onto the per-phone ``durinh`` / ``durmin`` base.
    4. Combines into ``durxx = (prcnt * (durinh - durmin)) / 128 +
       durmin`` then scales by ``sprat2`` and adds ``deldur * sprat1``.
    5. Stress-rhythm post-pass: for each stressed syllabic, redistribute
       a portion of ``timeref - syldur`` across the preceding sonorants
       to even out the stressed-timed rhythm.

    Args:
        phTTS: Two-pointer engine handle with populated ``DphT`` and
            ``KsdT``. Reads ``allophons`` / ``allofeats`` /
            ``user_durs`` from ``DphT``, plus ``sprate`` from ``KsdT``;
            writes ``allodurs`` / ``tcumdur`` / ``longcumdur`` /
            ``asperation``.
    """
    # The C source's local declarations (p_us_tim.c lines 108-138).
    psonsw: int = 0
    posvoc: int = 0
    pDph_t = cast(DphT, phTTS.p_ph_thread_data)
    pKsd_t = cast(KsdT, phTTS.p_kernel_share_data)
    pDphsettar = cast(DphSettarSt, pDph_t.pSTphsettar)

    stcnt: int = 0
    syldur: int = 0
    ncnt: int = 0
    endcnt: int = 0
    sonocnt: int = 0
    adjust: int = 0
    emphasissw: int = 0  # FALSE
    pholas: int = GEN_SIL
    struclas: int = 0
    fealas: int = GEN_SIL
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
    # arg1 / arg2 are used as scratch pairs into mlsh1 (the C
    # ``phmath`` routines take args from shared scratch slots).
    arg1: int = 0
    arg2: int = 0

    # TYPING_MODE: minsize is allocated per the `#ifdef TYPING_MODE`.
    minsize: int = 0

    wordfeat: int = 0

    # The C source calls init_timing(phTTS) here, but the Python
    # orchestrator (api/speak.py) has already invoked init_timing
    # before calling us_phtiming. Calling it again would double-zero
    # longcumdur, which is harmless but unnecessary; we skip it.

    pDph_t.tcumdur = 0

    # MAIN LOOP: walk each output phoneme.
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

        wordfeat = pDph_t.allofeats[nphon] & WORDFEAT

        # ----- Duration rules -----

        # Use user-specified duration if one exists. ``user_durs`` is
        # a SAFETY-offset window into ``allodurs`` -- see init_phclause.
        # However, in this port user_durs aliases pDph_t.allodurs at
        # this point, so we just read pDph_t.allodurs[nphon] when no
        # user override is present. Match the C: it checks
        # pDph_t->user_durs[nphon] != 0, treating the SAFETY-window as
        # the per-allophone array.
        user_dur_val = 0
        if pDph_t.user_durs is not None:
            # user_durs is the SAFETY-offset window; allodurs is the
            # base buffer. In init_phclause they alias so user_durs[i]
            # reads allodurs[i + SAFETY] in C. The Python port aliases
            # them to the same list and treats user_durs[nphon] as the
            # caller-supplied override. Default 0 means "no override".
            if nphon < len(pDph_t.user_durs):
                user_dur_val = pDph_t.user_durs[nphon]

        if user_dur_val != 0:
            pDphsettar.durxx = mstofr(user_dur_val + 4)
            deldur = 0
            # GOTO break3 in C -- jump to the end-of-loop block.
            _finalize_phone(
                pDph_t=pDph_t,
                pDphsettar=pDphsettar,
                pKsd_t=pKsd_t,
                nphon=nphon,
                phocur=phocur,
                feacur=feacur,
                feasyllabiccur=feasyllabiccur,
                deldur=deldur,
                strucstresscur=strucstresscur,
            )
            # Update the stress-rhythm tail state.
            stcnt, endcnt, ncnt, syldur, sonocnt, adjust = _stress_rhythm_pass(
                pDph_t=pDph_t,
                pDphsettar=pDphsettar,
                nphon=nphon,
                phocur=phocur,
                feacur=feacur,
                feasyllabiccur=feasyllabiccur,
                struccur=struccur,
                strucstresscur=strucstresscur,
                stcnt=stcnt,
                endcnt=endcnt,
                ncnt=ncnt,
                syldur=syldur,
                sonocnt=sonocnt,
                adjust=adjust,
            )
            # TYPING_MODE override: see _typing_mode_override block.
            _typing_mode_override(
                phTTS=phTTS,
                pDph_t=pDph_t,
                nphon=nphon,
                phocur=phocur,
                feacur=feacur,
                minsize_in=minsize,
            )
            pDph_t.longcumdur += pDphsettar.durxx * NSAMP_FRAME
            continue

        # Convert inherent and minimum duration in msec to frames.
        durinh = _inh_dur_frames(phocur)
        durmin = _min_dur_frames(phocur)

        if wordfeat and nphon < pDph_t.nallotot - 3:
            if wordfeat & F_NOUN:
                wordfeat = N120PRCNT
            elif wordfeat & F_ADJ:
                wordfeat = N100PRCNT
            elif wordfeat & F_VERB:
                wordfeat = N70PRCNT
            elif wordfeat & F_FUNC:
                # already gets crushed so don't do much now
                if pDph_t.nallotot > 7 and not (phone_feature(pDph_t.allophons[nphon]) & FOBST):
                    wordfeat = N80PRCNT
                else:
                    wordfeat = N100PRCNT
            else:
                wordfeat = N100PRCNT
        else:
            wordfeat = N100PRCNT

        # Additive increment.
        deldur = 0
        # Multiplicative constant (let 128 be 100%).
        prcnt = 128

        # Adjust word length by part of speech.
        if wordfeat:
            arg1 = wordfeat
            arg2 = prcnt
            prcnt = mlsh1(arg1, arg2)

        # Rule 1: Pause durations depend on syntax.
        if phocur == GEN_SIL:
            if (pDphsettar.feanex & (FVOICD | FOBST)) or (pDphsettar.feanex & FPLOSV):
                dpause = 14  # NF7MS-ish
            else:
                dpause = 15

            pDph_t.asperation = (pDph_t.asperation - BASE_ASP) // 10

            # Treatment of other than clause-initial pauses.
            if nphon > 1:
                # If this clause ends in a comma, use short pause.
                if (struclas & FBOUNDARY) == FCBNEXT:
                    # C bug at p_us_tim.c line 299: trailing semicolon
                    # turns the `<` branch into an empty statement, so the
                    # `pDph_t.asperation = MIN_ASP_COMMA` assignment fires
                    # unconditionally. Preserve the buggy behaviour.
                    if pDph_t.asperation > MAX_ASP_COMMA:
                        pDph_t.asperation = MAX_ASP_COMMA
                    pDph_t.asperation = MIN_ASP_COMMA
                    dpause = pDph_t.nfcomma + pDph_t.compause + pDph_t.asperation
                # End of clause has long pause if ends with "." "!" "?".
                if (struclas & FBOUNDARY) & FSENTENDS:
                    # Same trailing-semicolon C bug at p_us_tim.c line
                    # 316 -- `<` branch is empty; the assignment below
                    # always fires.
                    if pDph_t.asperation > MAX_ASP_PERIOD:
                        pDph_t.asperation = MAX_ASP_PERIOD
                    pDph_t.asperation = MIN_ASP_PERIOD
                    dpause = pDph_t.nfperiod + pDph_t.perpause + pDph_t.asperation
            # Make sentence-initial pause long if new paragraph.
            elif pDph_t.newparagsw != 0:
                dpause = pDph_t.nfperiod

            pDph_t.asperation = 0

            # Effect of speaking rate greatest on pauses.
            arg1 = dpause
            arg2 = pDphsettar.sprat1
            dpause = mlsh1(arg1, arg2)
            # Minimum pause is 13 ms.
            dpause = max(dpause, 2)

            # Skip over remaining duration rules if input is SIL.
            pDphsettar.durxx = dpause
            durinh = pDphsettar.durxx  # for debugging print only
            durmin = pDphsettar.durxx
            # Fall through to "break3" finalize.
            _finalize_phone(
                pDph_t=pDph_t,
                pDphsettar=pDphsettar,
                pKsd_t=pKsd_t,
                nphon=nphon,
                phocur=phocur,
                feacur=feacur,
                feasyllabiccur=feasyllabiccur,
                deldur=deldur,
                strucstresscur=strucstresscur,
            )
            stcnt, endcnt, ncnt, syldur, sonocnt, adjust = _stress_rhythm_pass(
                pDph_t=pDph_t,
                pDphsettar=pDphsettar,
                nphon=nphon,
                phocur=phocur,
                feacur=feacur,
                feasyllabiccur=feasyllabiccur,
                struccur=struccur,
                strucstresscur=strucstresscur,
                stcnt=stcnt,
                endcnt=endcnt,
                ncnt=ncnt,
                syldur=syldur,
                sonocnt=sonocnt,
                adjust=adjust,
            )
            _typing_mode_override(
                phTTS=phTTS,
                pDph_t=pDph_t,
                nphon=nphon,
                phocur=phocur,
                feacur=feacur,
                minsize_in=minsize,
            )
            pDph_t.longcumdur += pDphsettar.durxx * NSAMP_FRAME
            continue

        # Rule 2: Lengthening of segments in clause-final rime.
        if strucboucur >= FCBNEXT and pDph_t.number_words >= 4:
            deldur = NF40MS
            # Except for plosives.
            if feacur & FPLOSV:
                deldur = 0
            # Except for sonor conson [rx, lx] followed by voiceless obst.
            if (
                (phocur == USP_RX or phocur == USP_LX)
                and (pDphsettar.feanex & FOBST)
                and not (pDphsettar.feanex & FVOICD)
            ):
                deldur = NF15MS
            # More lengthening of a vowel if in a short phrase.
            if pDph_t.nallotot < 10 and feasyllabiccur and strucstresscur:
                deldur += NF30MS - (pDph_t.nallotot >> 1)
            # Less lengthening if next seg is sonorant in same rime.
            if pDphsettar.feanex & FSON1:
                deldur -= NF20MS

        # Rule 3: Shortening of non-phrase-final syllabics.
        if feasyllabiccur:
            if (strucboucur < FVPNEXT and pKsd_t.sprate > 160) or (strucboucur < FPPNEXT):
                # Reduce percent by factor of 0.7.
                arg1 = N70PRCNT
                arg2 = prcnt
                prcnt = mlsh1(arg1, arg2)

        # Nasal-after-nasal lengthening (post-Rule-3 hand-rolled rule).
        if (feacur & FNASAL) and (fealas & FNASAL) and phocur != pholas:
            # need to lengthen second nasal for time to differentiate
            deldur += NF30MS

        # Lengthening of phrase-final postvocalic nasal.
        if (feacur & FNASAL) and not strucstresscur and strucboucur >= FVPNEXT:
            deldur = deldur + NF40MS

        # Rule 4: Shorten syll segs in syll-init / medial positions, etc.
        if feasyllabiccur:
            if (struccur & FTYPESYL) == FMONOSYL:
                arg1 = N85PRCNT
                if not (strucstresscur & FSTRESS_1):
                    # Secondary-stressed monosyllables shortened by 85%.
                    arg1 = N75PRCNT
                    if not strucstresscur:
                        # Unstressed monosyllable shortened by 70%.
                        arg1 = N70PRCNT
                    arg2 = prcnt
                    prcnt = mlsh1(arg1, arg2)
            elif (struccur & FTYPESYL) != FMONOSYL and strucboucur < FWBNEXT:
                # Initial vowel of each word is shorter by 0.7.
                arg1 = N70PRCNT
                if (struccur & FTYPESYL) > FFIRSTSYL:
                    # Other nonfinal syllables shortened by 0.85.
                    arg1 = N85PRCNT
                arg2 = prcnt
                prcnt = mlsh1(arg1, arg2)

            # Rule 5: Shorten vowels in polysyllabic words.
            if (struccur & FTYPESYL) != FMONOSYL:
                # Multiply by 0.8.
                arg1 = prcnt
                arg2 = N80PRCNT
                prcnt = mlsh1(arg1, arg2)

        # Rule 6: Shortening of non-word-initial consonants.
        if not feasyllabiccur and not (struccur & FWINITC):
            if (feacur & FOBST) and not (feacur & FPLOSV) and (struccur & FBOUNDARY) >= FWBNEXT:
                # Except that word-final fricatives are lengthened.
                deldur += NF20MS
            else:
                # Multiply by 0.85.
                arg1 = prcnt
                arg2 = N85PRCNT
                prcnt = mlsh1(arg1, arg2)

        # Rule 7: Shortening of unstressed segs.
        if not (strucstresscur & FSTRESS_1):
            if durmin < durinh and not (feacur & FOBST):
                # Non-stressed segs more compressible (except obstruents).
                if not strucstresscur:
                    durmin = durmin >> 1
                else:
                    durmin -= durmin >> 2  # 2-stress
                # but not too short
                if durmin < 3:
                    durmin = 3
            # Non-primary-stressed syllabic segments shorter.
            if feasyllabiccur:
                # Shorten word-medial syllable more.
                if (struccur & FTYPESYL) == FMEDIALSYL:
                    prcnt -= prcnt >> 2
                else:
                    # Multiply by 0.7.
                    arg1 = prcnt
                    arg2 = N70PRCNT
                    prcnt = mlsh1(arg1, arg2)
                # Special case: Schwa next to a flap or followed by HX.
                if phocur == USP_AX or phocur == USP_IX:
                    if (
                        pholas == USP_DX
                        or pDphsettar.phonex_timing == USP_DX
                        or pDphsettar.phonex_timing == USP_HX
                    ):
                        deldur += NF15MS
            else:
                # Extra shortening of w,y,r,l.
                if USP_W <= phocur <= USP_LL:
                    prcnt = prcnt >> 1
                else:
                    # All other consonants -- multiply by 0.7.
                    arg1 = prcnt
                    arg2 = N70PRCNT
                    prcnt = mlsh1(arg1, arg2)
        else:
            # Penultimate lengthening of stressed syllabic with hat-fall.
            if feasyllabiccur:
                if (struccur & FHAT_ENDS) and strucboucur < FVPNEXT and strucboucur > FMBNEXT:
                    deldur = deldur + NF25MS

        # Rule 8: Lengthen each seg of an emphasized syllable.
        if (struccur & FWINITC) or (feasyllabiccur and strucstresscur != FEMPHASIS):
            emphasissw = 0  # FALSE
        if strucstresscur == FEMPHASIS:
            emphasissw = 1  # TRUE
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
            # Determine whether next segment is postvocalic consonant.
            if (not (pDphsettar.feanex & FSYLL)) and not (
                pDphsettar.strucnex & (FSTRESS | FWINITC)
            ):
                posvoc = pDphsettar.phonex_timing
                # See if postvocalic consonant is a sonorant
                # or if postvoc sonor is followed by an obst cons.
                if (
                    nphon + 2 < pDph_t.nallotot
                    and USP_RX <= posvoc <= USP_NX
                    and (phone_feature(pDph_t.allophons[nphon + 2]) & FOBST)
                    and not (pDph_t.allofeats[nphon + 2] & (FSTRESS | FWINITC))
                ):
                    psonsw = 1
                    posvoc = pDph_t.allophons[nphon + 2]
                # If posvoc is now voiceless or obst or nasal, do something.
                if posvoc != GEN_SIL:
                    if not (phone_feature(posvoc) & FVOICD):
                        deldur = deldur - (deldur >> 1)
                        # Multiply by 0.8 if a voiceless fric.
                        arg1 = N80PRCNT
                        if (phone_feature(posvoc) & FPLOSV) or posvoc == USP_CH:
                            # Multiply by 0.7 if voiceless plosive.
                            arg1 = N70PRCNT
                    else:
                        # Postvocalic segment is voiced.
                        if (phone_feature(posvoc) & FOBST) and phocur != USP_EN:
                            arg1 = N120PRCNT
                            # Voiced fricative -- add 25 ms to +syl.
                            if (
                                not (phone_feature(posvoc) & FPLOSV)
                                and posvoc != USP_DX
                                and (feacur & FSYLL)
                            ):
                                deldur = deldur + NF25MS
                        elif phone_feature(posvoc) & FNASAL:
                            # Nasal -- multiply by 0.85 (the rule comment says
                            # 0.9, the code uses N90PRCNT which == N85PRCNT
                            # by the documented 4.2CD typo).
                            arg1 = N90PRCNT
            # Attenuate effect if not phrase-final or +syl followed
            # by sonor or if postvoc sonor next.
            if strucboucur < FVPNEXT or psonsw == 1:
                arg1 = FRAC_HALF + (arg1 >> 1)
            arg2 = prcnt
            prcnt = mlsh1(arg1, arg2)

        # Rule 10: Lengthen first vowel of a two-vowel sequence.
        if feasyllabiccur:
            if pDphsettar.feanex & FSYLL:
                deldur = deldur + NF30MS
            # Rule 11: Lengthen word-initial stressed vowel of polysyl word.
            if (
                (struccur & FTYPESYL) == FFIRSTSYL
                and (struccur & FSTRESS_1)
                and not (struclas & FWINITC)
            ):
                deldur += NF25MS
            # Rule 12: Shorten vowels before postvocalic L.
            if pDphsettar.phonex_timing == USP_LX or pDphsettar.phonex_timing == USP_LY:
                # Reduce percent by factor of 0.7.
                arg1 = N70PRCNT
                arg2 = prcnt
                prcnt = mlsh1(arg1, arg2)
        # Rule 13: Shorten consonant clusters.
        else:
            if feacur & FCONSON:
                if (pDphsettar.feanex & FCONSON) and strucboucur < FWBNEXT:
                    # First consonant of a two-consonant sequence.
                    # Default shortening is 70 percent, unless plosive-
                    # plosive sequence.
                    if not (pDphsettar.feanex & FPLOSV) or not (feacur & FPLOSV):
                        arg1 = N70PRCNT
                    # Lengthen nasal by 1.5 if next cons is word-init.
                    if (feacur & FNASAL) and (pDphsettar.strucnex & FWINITC):
                        # from 1.5 to 1.2
                        arg1 = N120PRCNT
                    else:
                        # Also make min duration shorter for C's in cluster.
                        durmin -= durmin >> 2
                    # Shorten [S,TH] followed by a plosive or [SH].
                    if phocur == USP_S or phocur == USP_TH:
                        if pDphsettar.feanex & FPLOSV:
                            # Multiply by 0.5.
                            arg1 = FRAC_HALF
                        if pDphsettar.phonex_timing == USP_SH:
                            pDphsettar.durxx = NF15MS
                            # goto break3
                            _finalize_phone(
                                pDph_t=pDph_t,
                                pDphsettar=pDphsettar,
                                pKsd_t=pKsd_t,
                                nphon=nphon,
                                phocur=phocur,
                                feacur=feacur,
                                feasyllabiccur=feasyllabiccur,
                                deldur=deldur,
                                strucstresscur=strucstresscur,
                            )
                            (
                                stcnt,
                                endcnt,
                                ncnt,
                                syldur,
                                sonocnt,
                                adjust,
                            ) = _stress_rhythm_pass(
                                pDph_t=pDph_t,
                                pDphsettar=pDphsettar,
                                nphon=nphon,
                                phocur=phocur,
                                feacur=feacur,
                                feasyllabiccur=feasyllabiccur,
                                struccur=struccur,
                                strucstresscur=strucstresscur,
                                stcnt=stcnt,
                                endcnt=endcnt,
                                ncnt=ncnt,
                                syldur=syldur,
                                sonocnt=sonocnt,
                                adjust=adjust,
                            )
                            _typing_mode_override(
                                phTTS=phTTS,
                                pDph_t=pDph_t,
                                nphon=nphon,
                                phocur=phocur,
                                feacur=feacur,
                                minsize_in=minsize,
                            )
                            pDph_t.longcumdur += pDphsettar.durxx * NSAMP_FRAME
                            continue
                    arg2 = prcnt
                    prcnt = mlsh1(arg1, arg2)
                if (fealas & FCONSON) and (struclas & FBOUNDARY) < FVPNEXT:
                    # Second consonant of a two-consonant sequence.
                    # Multiply by 0.7.
                    arg1 = N70PRCNT
                    # Also make min duration shorter for C's in cluster.
                    durmin -= durmin >> 2
                    if feacur & FPLOSV:
                        # Shorten plosive if preceded by [s].
                        # Multiply by 0.6.
                        if pholas == USP_S:
                            arg1 = N60PRCNT
                        # Shorten unstr plos if preceded by nasal.
                        if fealas & FNASAL:
                            # Multiply by 0.1.
                            if not strucstresscur:
                                arg1 = 1638
                    arg2 = prcnt
                    prcnt = mlsh1(arg1, arg2)

        # Rule 14: Increase sonor dur if preceding plosive is aspirated.
        if feacur & FSON1:
            if not (fealas & FVOICD) and (fealas & FPLOSV):
                deldur = deldur + NF20MS

        # Rule 15: Increase duration of phrase-initial vowels (after silence).
        if feacur & FVOWEL:
            if pholas == GEN_SIL:
                deldur = deldur + NF20MS

        # Rule 16: Increase vowel dur if preceded by non-nasal sonor conson.
        if feacur & FVOWEL:
            if (fealas & FSON2) and not (fealas & FNASAL):
                if deldur == 0:
                    deldur = NF20MS

        # Rule 17: More lengthening of segments if in a short phrase.
        if pDph_t.nallotot < 10 and durinh != durmin:
            prcnt += 10

        # Rule (unnumbered): plosive obst + voiced next.
        if (feacur & FPLOSV) and (feacur & FOBST):
            arg1 = N80PRCNT
            if nphon + 1 < pDph_t.nallotot and (
                phone_feature(pDph_t.allophons[nphon + 1]) & FVOICD
            ):
                arg1 = N70PRCNT
            arg2 = prcnt
            prcnt = mlsh1(arg1, arg2)

        # Rule 18: Shortening of prevocalic clustered semivowels.
        if (feacur & FSONCON) and (fealas & FOBST):
            arg1 = prcnt
            arg2 = N70PRCNT
            prcnt = mlsh1(arg1, arg2)

        # Rule 19: Shorten function word final TH as in "with".
        if (
            phocur == USP_TH
            and (struccur & FTYPESYL) == FMONOSYL
            and strucboucur >= FWBNEXT
            and strucstresscur == FNOSTRESS
        ):
            arg1 = prcnt
            arg2 = N60PRCNT
            prcnt = mlsh1(arg1, arg2)

        # Rule 21: Shorten stop following a stop and preceding a fricative
        # within the same syllable.
        if (
            (feacur & FPLOSV)
            and (fealas & FPLOSV)
            and (pDphsettar.feanex & FOBST)
            and strucboucur > FMBNEXT
        ):
            durmin = durmin >> 1
            arg1 = prcnt
            arg2 = N25PRCNT
            prcnt = mlsh1(arg1, arg2)

        # Rule 23: Shorten vowel if phonex == df (writing vs riding).
        if pDphsettar.phonex_timing == USP_DF:
            if prcnt > 50:
                arg1 = prcnt
                arg2 = N40PRCNT
                prcnt = mlsh1(arg1, arg2)

        # Rule 24: RR retroflex minimum-dur floor.
        if phocur == USP_RR:
            if durmin <= 13:
                durmin = 13

        # Rule 25: Lengthen unvoiced cons after vowel (prev rule shortened vowel).
        if (fealas & FVOICD) and not (feacur & FVOICD):
            deldur = deldur + (deldur >> 1)
            arg1 = N130PRCNT
            arg2 = prcnt
            prcnt = mlsh1(arg1, arg2)

        # Rule 26: Shorten word-initial HX.
        if phocur == USP_HX and (struccur & FWINITC):
            arg1 = N60PRCNT
            arg2 = prcnt
            prcnt = mlsh1(arg1, arg2)

        pDphsettar.strucstressprev = strucstresscur

        # Finish up: set durxx from durinh, durmin, prcnt.
        pDphsettar.durxx = (prcnt * (durinh - durmin)) >> 7  # DIV_BY128
        pDphsettar.durxx += durmin

        # Rule for slow speaking: lengthen inserted glottal stop.
        if phocur == USP_Q and pKsd_t.sprate < 75:
            pDphsettar.durxx = 1 + (80 - pKsd_t.sprate)

        # break3 label target: speaking-rate scaling + clamps + writeback.
        _finalize_phone(
            pDph_t=pDph_t,
            pDphsettar=pDphsettar,
            pKsd_t=pKsd_t,
            nphon=nphon,
            phocur=phocur,
            feacur=feacur,
            feasyllabiccur=feasyllabiccur,
            deldur=deldur,
            strucstresscur=strucstresscur,
        )
        stcnt, endcnt, ncnt, syldur, sonocnt, adjust = _stress_rhythm_pass(
            pDph_t=pDph_t,
            pDphsettar=pDphsettar,
            nphon=nphon,
            phocur=phocur,
            feacur=feacur,
            feasyllabiccur=feasyllabiccur,
            struccur=struccur,
            strucstresscur=strucstresscur,
            stcnt=stcnt,
            endcnt=endcnt,
            ncnt=ncnt,
            syldur=syldur,
            sonocnt=sonocnt,
            adjust=adjust,
        )

        _typing_mode_override(
            phTTS=phTTS,
            pDph_t=pDph_t,
            nphon=nphon,
            phocur=phocur,
            feacur=feacur,
            minsize_in=minsize,
        )

        pDph_t.longcumdur += pDphsettar.durxx * NSAMP_FRAME


def _finalize_phone(
    *,
    pDph_t: DphT,
    pDphsettar: DphSettarSt,
    pKsd_t: KsdT,
    nphon: int,
    phocur: int,
    feacur: int,
    feasyllabiccur: int,
    deldur: int,
    strucstresscur: int,
) -> None:
    """Apply speaking-rate scaling + clamps + writeback (``break3:`` target).

    Faithful translation of p_us_tim.c lines 1019-1070 (the
    ``break3:`` block reached by all three goto sites and by the
    fall-through end of the per-phone rule body).
    """
    del strucstresscur  # used by C for the (omitted) FASTTALK path

    # Effect of speaking rate.
    if pDphsettar.sprat0 != 180 and pDphsettar.durxx != 0:
        arg1 = pDphsettar.durxx
        arg2 = pDphsettar.sprat2
        pDphsettar.durxx = mlsh1(arg1, arg2) + 1  # Round upwards
        # Effect of speaking rate on additive increment to dur.
        arg1 = deldur
        arg2 = pDphsettar.sprat1
        deldur = mlsh1(arg1, arg2)
    # Add in rule-governed additive increment to dur.
    pDphsettar.durxx = pDphsettar.durxx + deldur

    if pDphsettar.durxx < 0:
        # eab oct 93 found dur could get set =0 compromise.
        pDphsettar.durxx = 1

    # Clamp aspiration-final HX cap.
    if phocur == USP_HX:
        if pDphsettar.durxx > 11:
            pDphsettar.durxx = 11

    pDph_t.allodurs[nphon] = pDphsettar.durxx
    # Use kPKsd reference to silence unused-arg lint (parity for
    # future sprate-dependent extensions).
    _ = pKsd_t
    _ = feasyllabiccur
    _ = feacur


def _stress_rhythm_pass(
    *,
    pDph_t: DphT,
    pDphsettar: DphSettarSt,
    nphon: int,
    phocur: int,
    feacur: int,
    feasyllabiccur: int,
    struccur: int,
    strucstresscur: int,
    stcnt: int,
    endcnt: int,
    ncnt: int,
    syldur: int,
    sonocnt: int,
    adjust: int,
) -> tuple[int, int, int, int, int, int]:
    """Stressed-timed rhythm post-pass.

    Faithful translation of p_us_tim.c lines 1063-1207 (the
    non-TOMBUCHLER path: accumulate ``syldur`` / ``sonocnt`` per
    stressed syllabic, then redistribute ``timeref - syldur`` across
    the preceding sonorant frames).
    """
    if pDph_t.allophons[nphon] != GEN_SIL:
        # Don't count silence.
        # In English this is really not syldur but duration between
        # stresses, as English is a stress-timed language.
        syldur += pDphsettar.durxx

    # Instead of counting vowels, now count sonorants.
    if (feacur & FSON1) and pDph_t.allophons[nphon] != 0:
        sonocnt += 1

    # EAB 11/20/98: consonants before vowel are also marked with
    # stress; we want to ignore them here. Only fire when the current
    # phone is also syllabic.
    if (struccur & FSTRESS) and feasyllabiccur:
        if sonocnt == 1:
            adjust = pDph_t.timeref - syldur
        elif sonocnt == 2:
            adjust = (pDph_t.timeref - syldur) >> 1
        elif sonocnt == 3:
            # do 3/8 instead of divide by 3
            adjust = ((pDph_t.timeref - syldur) >> 3) * 3
        elif sonocnt == 4:
            adjust = (pDph_t.timeref - syldur) >> 2
        elif sonocnt == 5:
            adjust = (pDph_t.timeref - syldur) >> 3
        elif sonocnt == 6:
            adjust = (pDph_t.timeref - syldur) >> 4
        elif sonocnt == 7:
            adjust = (pDph_t.timeref - syldur) >> 5
        elif sonocnt == 8:
            adjust = (pDph_t.timeref - syldur) >> 6
        elif sonocnt == 9:
            adjust = (pDph_t.timeref - syldur) >> 7
        elif sonocnt == 10:
            adjust = (pDph_t.timeref - syldur) >> 8
        else:
            adjust = (pDph_t.timeref - syldur) >> 7

        adjust = adjust >> 1
        if pDphsettar.sprat0 <= 150:
            adjust = 0
        if nphon < 3:
            # First stress at beginning vowel of a stressed word --
            # reduce effect.
            adjust = adjust >> 3

        # Skip the redistribution if a user-supplied dur is in play
        # or we're in singing mode.
        user_dur_active = (
            pDph_t.user_durs is not None
            and nphon < len(pDph_t.user_durs)
            and pDph_t.user_durs[nphon] != 0
        )
        if user_dur_active or pDph_t.f0mode == SINGING:
            adjust = 0

        # Walk back from nphon-1 to stcnt; redistribute adjust across
        # sonorant phones that aren't nasal.
        endcnt = nphon - 1
        while stcnt - endcnt != 0:
            phon_e = pDph_t.allophons[endcnt]
            feat_e = phone_feature(phon_e)
            if (feat_e & FSON1) and not (feat_e & FNASAL):
                # Not first one much.
                if endcnt >= 3:
                    if pDph_t.allodurs[endcnt] <= 8:
                        # Phone already very short -- minimise effect.
                        adjust_local = adjust >> 1
                    else:
                        adjust_local = adjust
                    pDph_t.allodurs[endcnt] += adjust_local
                    if pDph_t.allodurs[endcnt] <= 6:
                        pDph_t.allodurs[endcnt] = 6
                    ncnt += 1
            endcnt -= 1
            if endcnt < 0:
                break

        ncnt = 0
        stcnt = nphon
        # reset syldur
        syldur = 0
        sonocnt = 0

    _ = phocur
    return stcnt, endcnt, ncnt, syldur, sonocnt, adjust


def _typing_mode_override(
    *,
    phTTS: TtsHandle,
    pDph_t: DphT,
    nphon: int,
    phocur: int,
    feacur: int,
    minsize_in: int,
) -> None:
    """``#ifdef TYPING_MODE`` override (p_us_tim.c lines 1298-1310).

    When the engine is in typing mode, override the just-computed
    ``allodurs[nphon]`` with a uniform short duration so each phone
    fires quickly. Sonorants get ``minsize`` (``30 / (nallotot - 1)``,
    floored at 6); everything else gets 3.
    """
    del minsize_in  # always recomputed below; kept for signature parity.
    # The TtsHandle exposes ``bInTypingMode`` only when the C build
    # defines TYPING_MODE; the Python port stores it as a bool that
    # defaults to False, so the override is a no-op until callers set
    # the flag.
    if not getattr(phTTS, "bInTypingMode", False):
        return
    denom = pDph_t.nallotot - 1
    if denom <= 0:
        return
    minsize = 30 // denom
    if minsize < 6:
        minsize = 6
    if (feacur & FSON1) and phocur != GEN_SIL:
        pDph_t.allodurs[nphon] = minsize


__all__ = ["us_phtiming"]
