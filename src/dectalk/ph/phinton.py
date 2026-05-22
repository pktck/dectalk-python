"""``phinton`` -- intonation-engine entry point from ph_inton2.c.

Translated from ``src/dapi/src/ph/ph_inton2.c`` line 216 (~2080-line C
function). The function generates the F0 (pitch) contour for one
clause: it walks the allophone stream, fires F0 events on stressed
syllables, applies hat-rise / hat-fall patterns, schedules
glottalisation gestures, and finally pads clause-final stops with a
"dummy" schwa to give plosive releases something to voice into.

Output lives in :class:`~dectalk.ph.dph_t.DphT`'s F0-event arrays
(``f0tar``, ``f0type``, ``f0length``, ``f0tim``) and the bookkeeping
counters ``nf0tot`` / ``nf0ev``. The per-phone open-quotient state
(``alloopenq``) is updated in lockstep.

This port covers the **US English** path only (``LANG_english`` with
``ENGLISH_US`` defined -- see ``src/Makefile.in`` lines 122 / 130).
The German / French / Spanish / Latin-American / British branches in
the C source are dropped; the Python pipeline today targets US output
exclusively, and the cross-language branches in the C are gated by a
``pKsd_t->lang_curr`` runtime check that always reads
``LANG_english`` in our build.

C bugs / quirks preserved faithfully:

- The "useless" early stress-table assignment that is then immediately
  overwritten by the unconditional ``targf0 = f0_{m,f}stress_level
  [stresscur] + wordfeat`` block (C ph_inton2.c lines 1080-1106).
- The ``stresscur != FNOSTRESS && (struccur & FBOUNDARY) == FCBNEXT ||
  (struccur & FBOUNDARY) == FQUENEXT`` short-circuit precedence
  (parens-as-written; line 1516).
- ``Rule 6`` dangling ``else if`` attached to the ``FCBNEXT`` block,
  not the ``FQUENEXT`` block (line 1859).
- Rule 31's ``WINprintf`` dead-code path is omitted (the body would
  fire but only prints).
- ``stepcount`` and ``lowrisesw`` are clause-local accumulators
  declared in the C but never actually reset between calls into PH
  on a fresh clause -- we initialise them at function entry to match.
"""

# ruff: noqa: N803, N806, PLR0912, PLR0915, PLR2004, SIM108, SIM102, PLR1714 -- mirror C structure

from __future__ import annotations

from typing import Final, cast

from dectalk.include.usp_codes import (
    USP_AX,
    USP_CH,
    USP_F,
    USP_G,
    USP_IX,
    USP_P,
    USP_S,
    USP_SH,
    USP_TH,
)
from dectalk.kernel.ksd_t import KsdT
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import (
    AT_TOP_OF_HAT,
    F_ADJ,
    F_IRESET,
    F_NOUN,
    F_VERB,
    FBOUNDARY,
    FCBNEXT,
    FDUMMY_VOWEL,
    FEMPHASIS,
    FHAT_BEGINS,
    FHAT_ENDS,
    FPERNEXT,
    FQUENEXT,
    FSTRESS,
    FVPNEXT,
    FWINITC,
)
from dectalk.ph.frame_counts import (
    NF7MS,
    NF20MS,
    NF25MS,
    NF40MS,
    NF80MS,
    NF160MS,
)
from dectalk.ph.inton_constants import (
    AFTER_FINAL_FALL,
    AFTER_NONFINAL_FALL,
    BEFORE_HAT_RISE,
    HAT_F0_SIZES_SPECIFIED,
    NORMAL,
    ON_TOP_OF_HAT,
    PHONE_TARGETS_SPECIFIED,
    SINGING,
)
from dectalk.ph.make_f0_command import make_f0_command as _make_f0_command
from dectalk.ph.math_helpers import muldv
from dectalk.ph.numeric_constants import MALE, NPHON_MAX
from dectalk.ph.phoneme_features import F_ADJ as _F_ADJ_WF
from dectalk.ph.phoneme_features import F_NOUN as _F_NOUN_WF
from dectalk.ph.phoneme_features import F_VERB as _F_VERB_WF
from dectalk.ph.phoneme_features import (
    FALVEL,
    FBURST,
    FOBST,
    FPLOSV,
    FSON1,
    FSONOR,
    FSYLL,
    FVOICD,
    WORDFEAT,
)
from dectalk.ph.task_helpers import mstofr
from dectalk.ph.timing import begtyp, phone_feature
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.utterance_constants import (
    COMMACLAUSE,
    DECLARATIVE,
    GEN_SIL,
    GLIDE,
    IMPULSE,
    STEP,
    USER,
)
from dectalk.vtm.frac import frac4mul

# Part-of-speech bit aliases. feature_bits.F_NOUN/F_VERB/F_ADJ and
# phoneme_features.F_NOUN/F_VERB/F_ADJ carry the same numeric value
# but the C source touches both via two different headers; OR them
# together so the wordfeat test reads as it does in the C.
_F_NOUN_BIT: Final[int] = F_NOUN | _F_NOUN_WF
_F_VERB_BIT: Final[int] = F_VERB | _F_VERB_WF
_F_ADJ_BIT: Final[int] = F_ADJ | _F_ADJ_WF


# -- US-English language-dispatch constants from ph_inton2.c lines 654-703 --
#
# All constants are pulled from the ``LANG_english`` branch of the
# language-dispatch block. The block writes function-scope ``short``s;
# we make them module-level Finals since they never vary at runtime
# in the US-only Python port.

# Phrase-position and stress-level tables (us_f0_*[] from lines 314-334).
_US_F0_MPHRASE_POSITION: Final[tuple[int, ...]] = (160, 80, 60, 40, 30, 20, 20, 5)
_US_F0_MSTRESS_LEVEL: Final[tuple[int, ...]] = (1, 81, 61, 161)
_US_F0_FPHRASE_POSITION: Final[tuple[int, ...]] = (180, 80, 70, 60, 50, 40, 34, 30)
_US_F0_FSTRESS_LEVEL: Final[tuple[int, ...]] = (1, 100, 80, 161)

# Per-language scalars from the LANG_english (non-SUEB) block.
# C source ph_inton2.c lines 677-696 (the ``#else`` of the SUEB #ifdef).
_SCHWA1: Final[int] = USP_AX
_SCHWA2: Final[int] = USP_IX
_F0_QGESTURE1: Final[int] = 351
_F0_QGESTURE2: Final[int] = 451
_F0_CGESTURE1: Final[int] = 171
_F0_CGESTURE2: Final[int] = 250
_GEST_SHIFT: Final[int] = 1
_MAX_NRISES: Final[int] = 7
_F0_FINAL_FALL: Final[int] = 550
_F0_NON_FINAL_FALL: Final[int] = 150
_F0_COMMA_FALL: Final[int] = 120
_F0_QSYLL_FALL: Final[int] = 80
_F0_GLOTTALIZE: Final[int] = -60
_REDUCE_LAST: Final[int] = 10


def _ensure_buffer(arr: list[int], min_size: int) -> None:
    """Grow ``arr`` to at least ``min_size`` entries with zeroes."""
    if len(arr) < min_size:
        arr.extend([0] * (min_size - len(arr)))


def phinton(phTTS: TtsHandle) -> None:
    """Run the per-clause intonation engine.

    Mirrors the C signature ``void phinton(LPTTS_HANDLE_T phTTS)``.
    Walks the clause's allophone stream and writes F0 commands into
    ``f0tar`` / ``f0type`` / ``f0length`` / ``f0tim`` on ``phTTS``'s
    PH-thread state. Mutates ``nf0tot`` / ``alloopenq`` /
    ``allofeats`` / ``allodurs`` / ``nallotot`` (for the trailing
    dummy-vowel insertion) along the way.

    Args:
        phTTS: Two-pointer engine handle with populated ``KsdT`` and
            ``DphT``. The function casts both pointers as
            non-``None``; callers are responsible for initialisation.
    """
    # KsdT cast retained for parity with the C source even though the
    # US-only Python port never reads ``lang_curr``.
    _pKsd_t = cast(KsdT, phTTS.p_kernel_share_data)
    del _pKsd_t
    pDph_t = cast(DphT, phTTS.p_ph_thread_data)
    pDphsettar = cast(DphSettarSt, pDph_t.pSTphsettar)

    # Per-language F0 rise / phrase-position tables. Module-level
    # tuples for US English; aliased to locals so the body reads
    # identically to the C source's pointer arithmetic.
    f0_mstress_level = _US_F0_MSTRESS_LEVEL
    f0_fstress_level = _US_F0_FSTRESS_LEVEL
    f0_mphrase_position = _US_F0_MPHRASE_POSITION
    f0_fphrase_position = _US_F0_FPHRASE_POSITION
    SCHWA1 = _SCHWA1
    SCHWA2 = _SCHWA2
    F0_QGesture1 = _F0_QGESTURE1
    F0_QGesture2 = _F0_QGESTURE2
    F0_CGesture1 = _F0_CGESTURE1
    F0_CGesture2 = _F0_CGESTURE2
    MAX_NRISES = _MAX_NRISES
    F0_FINAL_FALL = _F0_FINAL_FALL
    # F0_NON_FINAL_FALL: declared in C but never read on the US path.
    F0_COMMA_FALL = _F0_COMMA_FALL
    F0_QSYLL_FALL = _F0_QSYLL_FALL
    F0_GLOTTALIZE = _F0_GLOTTALIZE
    Reduce_last = _REDUCE_LAST

    # Automatic variables (matching the C declarations at lines 517-535).
    # ``cumdur`` is mutable across make_f0_command calls; pass a list-cell.
    cumdur: list[int] = [0]
    mf0 = 0
    length = 0
    pholas = GEN_SIL
    fealas = phone_feature(GEN_SIL)
    targf0 = 0
    delayf0 = 0
    f0fall = 0
    nphonx = 0
    inputscrewup = False
    # lowrisesw, nextwrdbou, nextsylbou, NotQuest are declared in the
    # C body but only read inside ``#ifdef MAYBE`` / dead-code
    # branches; the US English path never inspects them.
    issubclause = 0
    wordfeat: int = 0
    feacur: int = 0
    feanex: int = 0
    phonex: int = 0
    stresscur: int = 0
    struccur: int = 0

    # Per-clause initialization (lines 537-558).
    pDph_t.delta_special = 0
    pDphsettar.nrises_sofar = 0
    pDphsettar.hatsize = 0
    pDphsettar.hat_loc_re_baseline = 0
    pDph_t.had_hatbegin = 0
    pDph_t.had_hatend = 0
    pDph_t.had_in_phrase_final = 0
    pDph_t.nf0tot = 0
    pDph_t.prevtargf0 = -1
    pDph_t.done = 0

    # Ensure clause-scoped arrays are large enough for in-place mutation.
    _ensure_buffer(pDph_t.alloopenq, NPHON_MAX)
    _ensure_buffer(pDph_t.allophons, NPHON_MAX)
    _ensure_buffer(pDph_t.allofeats, NPHON_MAX)
    _ensure_buffer(pDph_t.allodurs, NPHON_MAX)
    if pDph_t.user_f0 is None:
        pDph_t.user_f0 = [0] * NPHON_MAX
    else:
        _ensure_buffer(pDph_t.user_f0, NPHON_MAX)
    if pDph_t.user_offset is None:
        pDph_t.user_offset = [0] * NPHON_MAX

    # Main loop -- one iteration per allophone.
    nallotot_at_start = pDph_t.nallotot
    nphon = 0
    while nphon < nallotot_at_start:
        if nphon > 0:
            pholas = pDph_t.allophons[nphon - 1]
            fealas = phone_feature(pholas)

        phocur = pDph_t.allophons[nphon]
        struccur = pDph_t.allofeats[nphon]

        # Extract word-feature high bits into the ``wordfeat`` accumulator.
        # ph_inton2.c lines 757-778.
        if struccur & WORDFEAT:
            wordfeat = struccur & WORDFEAT
            if wordfeat & _F_NOUN_BIT:
                wordfeat = 25
            elif wordfeat & _F_VERB_BIT:
                wordfeat = 20
            elif wordfeat & _F_ADJ_BIT:
                wordfeat = 35
        else:
            wordfeat = 0

        stresscur = struccur & FSTRESS
        feacur = phone_feature(phocur)
        if nphon < (pDph_t.nallotot - 1):
            phonex = pDph_t.allophons[nphon + 1]
            feanex = phone_feature(phonex)

        # * * * OPEN QUOTIENT (lines 788-829, ENGLISH && !HLSYN path) * * *
        pDph_t.alloopenq[nphon] = 50

        if not (fealas & FVOICD) and pholas != GEN_SIL:
            if feacur & FSON1:
                pDph_t.alloopenq[nphon] = 70
                if pholas in (USP_F, USP_TH, USP_S, USP_SH, USP_CH):
                    pDph_t.alloopenq[nphon] = 30
        elif (fealas & FOBST) and not (fealas & FBURST):
            pDph_t.alloopenq[nphon] = 70
        elif pholas == GEN_SIL and (stresscur & FSTRESS):
            pDph_t.alloopenq[nphon] = 30
            if nphon - 1 >= 0:
                pDph_t.alloopenq[nphon - 1] = 30

        if pDph_t.hatstate == AFTER_NONFINAL_FALL:
            if not (feacur & FVOICD):
                pDph_t.alloopenq[nphon] = 30
        if fealas & FVOICD:
            if not (feacur & FVOICD):
                pDph_t.alloopenq[nphon] = 70
                if phocur == GEN_SIL or phonex == GEN_SIL:
                    pDph_t.alloopenq[nphon] = 30

        # Remember previous hat state; reset to BEFORE_HAT_RISE at silence.
        pDph_t.hatstatel = pDph_t.hatstate
        if phocur == GEN_SIL:
            pDph_t.hatstate = BEFORE_HAT_RISE

        # Boundary look-ahead (lines 836-878). The C body builds
        # ``nextsylbou`` / ``nextwrdbou`` / ``nextphrbou`` but the
        # US path never reads them outside ``#ifdef MAYBE`` and
        # ``#ifdef GERMANout``. We still execute Step 1 because it
        # mutates ``nphonx``, which a later rule (Rule 9's dummy-
        # vowel insertion) treats as a scratch pointer.
        nphonx = nphon
        while nphonx < pDph_t.nallotot and (pDph_t.allofeats[nphonx] & FWINITC):
            nphonx += 1

        # Local make_f0_command shim binding cumdur + nphon.
        def _f0(
            type_: int,
            rule: int,
            tar: int,
            delay: int,
            length_arg: int,
            *,
            n: int = nphon,
        ) -> None:
            _make_f0_command(pDph_t, type_, rule, tar, delay, length_arg, cumdur, n)

        # ---- Rule 0: user-specified F0 targets / singing ----
        # The C source does ``goto skiprules`` here (ph_inton2.c line
        # 895), which jumps PAST Rules 1-7 but still executes the
        # cumdur / tcumdur update and Rule 9's dummy-schwa insertion
        # (which live AFTER the ``skiprules:`` label at line 1944). A
        # prior revision of this port used ``continue`` here, which
        # also skipped Rule 9. We now mirror the goto via a flag:
        # skip the rules block but fall through to the tail.
        skiprules = False
        if pDph_t.f0mode == PHONE_TARGETS_SPECIFIED or pDph_t.f0mode == SINGING:
            assert pDph_t.user_f0 is not None
            if pDph_t.user_f0[nphon] != 0:
                _f0(USER, 0, 1000 + pDph_t.user_f0[nphon], 0, 0)
            skiprules = True

        # ---- Hat-rise / hat-end accumulator updates (lines 911-932) ----
        if not skiprules and pDph_t.number_words > 2:
            if struccur & FHAT_BEGINS:
                pDph_t.had_hatbegin = 1
            if struccur & FHAT_ENDS:
                pDph_t.had_hatend = 1

        if not skiprules and (struccur & F_IRESET) and pDph_t.hatstate == ON_TOP_OF_HAT:
            if pDph_t.nallotot > (nphon + 10):
                pDph_t.had_hatend = 1

        if not skiprules and (pDph_t.f0mode == NORMAL or pDph_t.f0mode == HAT_F0_SIZES_SPECIFIED):
            if feacur & FSYLL:
                # ---- Rule 1: hat rise on first stressed syll ----
                if pDph_t.had_hatbegin:
                    if pDph_t.f0mode == NORMAL and not pDph_t.special_phrase:
                        pDph_t.had_hatbegin = 0
                        pDphsettar.hatsize = pDph_t.size_hat_rise
                        if nphon > 10:
                            pDphsettar.hatsize = pDphsettar.hatsize + 15
                        if nphon == 2:
                            pDphsettar.hatsize += 70
                        _f0(STEP, 1, pDphsettar.hatsize, 0, 5)
                    elif pDph_t.f0mode == HAT_F0_SIZES_SPECIFIED:
                        assert pDph_t.user_f0 is not None
                        assert pDph_t.user_offset is not None
                        pDphsettar.hatsize = ((pDph_t.user_f0[mf0] - 200) * 10) + 2
                        if pDphsettar.hatsize >= 2000 or pDphsettar.hatsize <= 0 or inputscrewup:
                            pDphsettar.hatsize = 2
                        delayf0 = mstofr(pDph_t.user_offset[mf0])
                        mf0 += 1
                        _f0(STEP, 1, pDphsettar.hatsize, 0, 15)

                    pDphsettar.hat_loc_re_baseline += pDphsettar.hatsize
                    pDph_t.hatpos = AT_TOP_OF_HAT
                    pDph_t.hatstate = ON_TOP_OF_HAT

                if pDph_t.special_phrase:
                    pDphsettar.nrises_sofar = 5

                if issubclause:
                    pDphsettar.nrises_sofar = 3
                    issubclause = 0

                # ---- Rule 2: stress pulse on every stressed vowel ----
                targf0 = 0

                if not pDph_t.special_phrase and (stresscur & FSTRESS):
                    # Initial conditional assignment (lines 1081-1094)
                    # -- buggy: immediately overwritten by the
                    # unconditional block below. Preserved faithfully.
                    if wordfeat:
                        if pDph_t.malfem == MALE:
                            targf0 = f0_mstress_level[stresscur] + wordfeat
                        else:
                            targf0 = f0_fstress_level[stresscur] + wordfeat
                    elif pDph_t.malfem == MALE:
                        targf0 = f0_mstress_level[stresscur]
                    else:
                        targf0 = f0_fstress_level[stresscur]

                    # Unconditional override -- "expanded feature bits".
                    if pDph_t.malfem == MALE:
                        targf0 = f0_mstress_level[stresscur] + wordfeat
                    else:
                        targf0 = f0_fstress_level[stresscur] + wordfeat

                    wordfeat = 0

                    if pDph_t.malfem == MALE:
                        targf0 += f0_mphrase_position[pDphsettar.nrises_sofar]
                    else:
                        targf0 += f0_fphrase_position[pDphsettar.nrises_sofar]

                    pDph_t.impulse_width = pDph_t.allodurs[nphon] >> 1

                    if pDph_t.cbsymbol:
                        targf0 >>= 2

                    delayf0 = pDph_t.allodurs[nphon] - (pDph_t.impulse_width >> 1)

                    if (struccur & FHAT_ENDS) or (struccur & FPERNEXT):
                        delayf0 = -NF20MS
                        targf0 = targf0 - Reduce_last
                        if targf0 < 0:
                            targf0 = 30

                    if stresscur == FEMPHASIS:
                        delayf0 = NF7MS

                    if pDph_t.f0mode == HAT_F0_SIZES_SPECIFIED:
                        assert pDph_t.user_f0 is not None
                        assert pDph_t.user_offset is not None
                        targf0 = ((pDph_t.user_f0[mf0] - 1000) * 10) + 1
                        if targf0 >= 2000 or targf0 <= 0 or inputscrewup:
                            targf0 = 1
                        delayf0 = mstofr(pDph_t.user_offset[mf0])
                        mf0 += 1

                    # Scale by speaker-def parameter SR, bumped to 16 for emphatic.
                    temp = pDph_t.scale_str_rise
                    if stresscur == FEMPHASIS and temp < 16:
                        temp = 16
                    pDph_t.arg2 = targf0
                    pDph_t.arg3 = 32
                    targf0 = muldv(temp, targf0, 32)

                    # US English (non-British): divided-by-3 impulse.
                    _f0(
                        IMPULSE,
                        2,
                        targf0 // 3,
                        delayf0,
                        pDph_t.impulse_width + 15,
                    )

                    # Increment stress counter, wrapping at MAX_NRISES.
                    if pDphsettar.nrises_sofar < MAX_NRISES:
                        pDphsettar.nrises_sofar += 1
                    if pDphsettar.nrises_sofar == MAX_NRISES:
                        pDphsettar.nrises_sofar = 1

                # ---- Rule 3: hat fall when end-of-hat is pending ----
                # The C source nests Rule 4 inside this ``if (had_hatend)``
                # block (ph_inton2.c lines 1354-1591). Both rules clear
                # ``had_hatend`` once and share a single boundary-driven
                # f0fall/comma-impulse dispatch — see the brace tracing
                # in the parity test.
                if pDph_t.had_hatend:
                    pDph_t.had_hatend = 0
                    pDph_t.had_in_phrase_final = 1
                    if pDph_t.f0mode == NORMAL:
                        if pDph_t.malfem == MALE:
                            f0fall = F0_FINAL_FALL >> 1
                        else:
                            f0fall = F0_FINAL_FALL
                        pDph_t.hatstate = AFTER_FINAL_FALL

                        delayf0 = 10
                        delayf0 = max(delayf0, NF25MS)

                        # ENGLISH_US #ifdef branch (lines 1382-1395).
                        if (struccur & FBOUNDARY) == FCBNEXT or pDph_t.clausetype == COMMACLAUSE:
                            f0fall = F0_COMMA_FALL
                            pDph_t.hatstate = AFTER_NONFINAL_FALL

                        if (struccur & FBOUNDARY) == FVPNEXT:
                            f0fall = 0
                        if (struccur & FBOUNDARY) == FQUENEXT:
                            f0fall = F0_QSYLL_FALL

                        # if (pDph_t->hatstate == AFTER_FINAL_FALL)
                        #     lowrisesw = 0;  -- ``lowrisesw`` is only
                        # read inside ``#ifdef MAYBE`` (dead code).

                        f0fall = frac4mul(f0fall, pDph_t.assertiveness)
                        if pDph_t.cbsymbol:
                            f0fall = f0fall >> 1
                        f0fall += pDphsettar.hatsize

                    elif pDph_t.f0mode == HAT_F0_SIZES_SPECIFIED:
                        assert pDph_t.user_f0 is not None
                        assert pDph_t.user_offset is not None
                        f0fall = ((pDph_t.user_f0[mf0] - 400) * 10) + 2
                        if f0fall >= 2000 or f0fall <= 0 or inputscrewup:
                            f0fall = 2
                        delayf0 = mstofr(pDph_t.user_offset[mf0])
                        mf0 += 1

                    if feanex & FSONOR:
                        delayf0 += 5

                    length = pDph_t.allodurs[nphon] + 10

                    if struccur & F_IRESET:
                        delayf0 += 30
                        length += 10
                        pDph_t.had_hatbegin = 1

                    _f0(GLIDE, 3, -f0fall, delayf0, length)
                    pDphsettar.hat_loc_re_baseline -= f0fall

                    # ---- Rule 4: positive pulse for non-terminal fall-rise ----
                    # C ph_inton2.c lines 1499-1590 -- this whole block
                    # sits at depth 5 (inside ``if (had_hatend)``), NOT
                    # at the syllable-loop scope. A prior revision of
                    # the port had it un-nested, which made the comma-
                    # impulse pair fire on every FCBNEXT phone whether
                    # or not a hat-fall was pending. The C only walks
                    # this path when ``had_hatend`` was just cleared.
                    #
                    # ``NotQuest`` is set at line 1505/1510 but only
                    # consumed inside dead-code branches; we elide the
                    # assignments.

                    # C precedence (faithful): &&-chain || boundary==FQUENEXT.
                    rule4_a = (
                        pDph_t.clausetype != DECLARATIVE
                        and stresscur != 0
                        and (struccur & FBOUNDARY) == FCBNEXT
                    )
                    rule4_b = (struccur & FBOUNDARY) == FQUENEXT
                    if rule4_a or rule4_b:
                        delayf0 = pDph_t.allodurs[nphon] - NF80MS
                        pDph_t.delta_special = 0

                        if (struccur & FBOUNDARY) == FQUENEXT:
                            # Spanish / LA / German Q-impulse calls don't
                            # fire on US English path.
                            pDph_t.delta_special = 0
                        else:
                            pDph_t.delta_special = -50
                            delayf0 -= NF20MS

                            # BATS#709: first comma in a clause uses one
                            # timing; subsequent ones use another.
                            if pDph_t.commacnt == 0:
                                _f0(IMPULSE, 42, F0_CGesture1, 3, 22)
                                _f0(
                                    IMPULSE,
                                    42,
                                    F0_CGesture2,
                                    pDph_t.allodurs[nphon] >> 1,
                                    18,
                                )
                            else:
                                _f0(IMPULSE, 420, F0_CGesture1, delayf0, 24)
                                _f0(
                                    IMPULSE,
                                    420,
                                    F0_CGesture2,
                                    pDph_t.allodurs[nphon] >> 1,
                                    24,
                                )
                            pDph_t.commacnt += 1

            # Rule 31 (lines 1604-1731): "code still being hit" debug
            # branch. Only fires when had_hatend was just re-armed and
            # current phone is +FSYLL.
            if pDph_t.had_hatend and (feacur & FSYLL):
                if pDph_t.f0mode == NORMAL:
                    f0fall = F0_FINAL_FALL
                    delayf0 = pDph_t.allodurs[nphon] - NF160MS
                    delayf0 = max(delayf0, NF25MS)

                    if ((struccur & FBOUNDARY) == FCBNEXT) or (pDph_t.clausetype == COMMACLAUSE):
                        f0fall = 60
                    if (struccur & FBOUNDARY) == FVPNEXT:
                        f0fall = 0
                    if (struccur & FBOUNDARY) == FQUENEXT:
                        f0fall = F0_QSYLL_FALL

                    f0fall = frac4mul(f0fall, pDph_t.assertiveness)
                    if pDph_t.cbsymbol:
                        f0fall = f0fall >> 1
                    f0fall += pDphsettar.hatsize

                elif pDph_t.f0mode == HAT_F0_SIZES_SPECIFIED:
                    assert pDph_t.user_f0 is not None
                    assert pDph_t.user_offset is not None
                    f0fall = ((pDph_t.user_f0[mf0] - 400) * 10) + 2
                    if f0fall >= 2000 or f0fall <= 0 or inputscrewup:
                        f0fall = 2
                    delayf0 = mstofr(pDph_t.user_offset[mf0])
                    mf0 += 1

                # US English: STEP down.
                _f0(STEP, 31, -f0fall, delayf0, 0)
                pDphsettar.hat_loc_re_baseline -= f0fall

        # ---- Rule 5 (lines 1740-1817) ----
        # Spanish / LA only inside the FSYLL && stress-less block;
        # US English skips Rule 5 entirely.

        # ---- Rule 6: continuation rise on unstressed clause-final syll ----
        # Skipped when ``goto skiprules`` was taken at Rule 0 above
        # (PHONE_TARGETS_SPECIFIED / SINGING modes); Rule 9 still runs.
        delayf0 = -5
        if not skiprules and (struccur & FBOUNDARY) == FQUENEXT:
            # US English (non-GERMAN).
            _f0(IMPULSE, 6, F0_QGesture1, delayf0, 24)
            _f0(IMPULSE, 6, F0_QGesture2, pDph_t.allodurs[nphon], 20)
        if not skiprules and (struccur & FBOUNDARY) == FCBNEXT:
            delayf0 += NF20MS
            _f0(IMPULSE, 6, F0_CGesture1, 0, 24)
            _f0(IMPULSE, 6, F0_CGesture2, delayf0, 20)
            pDph_t.commacnt += 1

        # Dangling ``else if`` -- C source attaches it to FCBNEXT block.
        elif not skiprules and (struccur & FBOUNDARY) == FPERNEXT:
            targf0 = F0_GLOTTALIZE
            targf0 = frac4mul(targf0, pDph_t.assertiveness)
            pDph_t.test_targf0 = targf0
            pDph_t.impulse_width = 20

            # Voiced-next adjustment for BATS#796.
            if phone_feature(phonex) & FVOICD:
                pDph_t.test_targf0 = targf0 >> 3
                if nphon + 2 <= pDph_t.nallotot and (
                    phone_feature(pDph_t.allophons[nphon + 2]) & FVOICD
                ):
                    _f0(
                        IMPULSE,
                        6,
                        pDph_t.test_targf0,
                        pDph_t.allodurs[nphon],
                        pDph_t.impulse_width,
                    )
                else:
                    delayf0 = (pDph_t.allodurs[nphon] >> 1) + (pDph_t.allodurs[nphon] >> 2)
                    _f0(
                        IMPULSE,
                        6,
                        pDph_t.test_targf0,
                        delayf0,
                        pDph_t.impulse_width,
                    )
            else:
                _f0(
                    IMPULSE,
                    6,
                    pDph_t.test_targf0,
                    (pDph_t.allodurs[nphon] >> 1) + 3,
                    pDph_t.impulse_width,
                )

        # ---- Rule 7: reset baseline at end of sentence ----
        if not skiprules and phocur == GEN_SIL:
            if pDphsettar.hat_loc_re_baseline != 0 and pDph_t.nf0tot > 0:
                # US English (non-British): no STEP emit.
                pDphsettar.hat_loc_re_baseline = 0

            if nphon > 0:
                pDphsettar.nrises_sofar = 1
                # The C else/else-if branches need nphon == 0, which
                # paired with ``phocur == GEN_SIL`` is the leading
                # silence -- but the soft-reset always wins for
                # everything past the first phone.

        # END OF F0 RULES (skiprules: label).

        # Update cumdur to time at end of current phone.
        cumdur[0] += pDph_t.allodurs[nphon]

        # tcumdur accumulator -- skip the trailing silence.
        if (
            nphon <= (pDph_t.nallotot - 1) and nphon > 0 and (pDph_t.allophons[nphon] & 0xFF) != 0
        ) or nphon == 0:
            pDph_t.tcumdur += pDph_t.allodurs[nphon]

        # ---- Rule 9: insert dummy schwa after clause-final plosive ----
        if (
            phonex == GEN_SIL
            and (phone_feature(phocur) & FPLOSV)
            and (phone_feature(phocur) & FBURST)
        ):
            # Shift trailing phones one slot to the right.
            for k in range(pDph_t.nallotot + 1, nphon, -1):
                if k < len(pDph_t.allophons):
                    pDph_t.allophons[k] = pDph_t.allophons[k - 1]
                if k < len(pDph_t.allofeats):
                    pDph_t.allofeats[k] = pDph_t.allofeats[k - 1]
                if k < len(pDph_t.allodurs):
                    pDph_t.allodurs[k] = pDph_t.allodurs[k - 1]
                if k < len(pDph_t.user_f0):
                    pDph_t.user_f0[k] = pDph_t.user_f0[k - 1]

            pDph_t.allophons[nphon + 1] = SCHWA1
            if begtyp(pholas) == 1 or (phone_feature(phocur) & FALVEL):
                pDph_t.allophons[nphon + 1] = SCHWA2

            # NF40MS for both branches (the C if/else is dead code).
            if USP_P <= phocur <= USP_G and (feacur & FVOICD):
                pDph_t.allodurs[nphon + 1] = NF40MS
            else:
                pDph_t.allodurs[nphon + 1] = NF40MS

            cumdur[0] += pDph_t.allodurs[nphon + 1]
            pDph_t.tcumdur += pDph_t.allodurs[nphon + 1]
            pDph_t.allofeats[nphon + 1] = pDph_t.allofeats[nphon] | FDUMMY_VOWEL
            pDph_t.nallotot += 1
            nphon += 1  # C does ``nphon++`` to skip the new schwa.

        nphon += 1


__all__ = ["phinton"]
