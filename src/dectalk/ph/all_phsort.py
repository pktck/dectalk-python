"""``all_phsort`` -- multi-language PH-sort engine from ph_sort.c.

Translated from ``src/dapi/src/ph/ph_sort.c`` lines 428-1712 (the
~1284-line C function). This port covers the **US English** path
(``LANG_english``); the other branches in the C source (UK English,
German, Spanish, Latin-American Spanish) raise
:class:`NotImplementedError` because their helper chains are not yet
ported. French goes through :func:`fr_phsort` and never reaches this
entry.

The function processes the per-clause input symbol stream
(``pDph_t->symbols[]``) and produces:

- ``pDph_t->phonemes[]`` -- the output phoneme sequence.
- ``pDph_t->sentstruc[]`` -- parallel feature-bit array.
- ``pDph_t->user_durs[]`` / ``user_f0[]`` -- per-phone prosody.
- Clause-level state: ``clausetype``, ``cbsymbol``, ``f0mode``,
  ``nphonetot``, ``number_words``, ``newparagsw``, etc.

It runs as two passes:

1. **Pass 1 -- input cleanup.** Walks ``symbols[]`` and applies:

   - GR/SP/LA-specific allophonic rewrites -- skipped for US.
   - SPECIALWORD removal -- HLSYN build skips it for US.
   - Adjacent ``NEW_PARAGRAPH`` collapse, ``WBOUND + PERIOD``
     deduplication.
   - User-F0 mode detection (``HAT_RISE``..``HAT_RF`` -> set
     ``HAT_LOCATIONS_SPECIFIED``).
   - PPSTART promotion to ``WBOUND`` when followed by a clause
     boundary; inserts a dangling ``S1`` then moves it.
   - Slow-rate boundary promotion (``PPSTART``->``VPSTART``).
   - Stressless-clause repair (``find_syll_to_stress``).
   - Phrase-reset on clause boundaries; question/exclaim flags.

2. **Pass 2 -- output emit.** Walks ``symbols[]`` again, calling
   :func:`make_phone` for each real phoneme and adding feature bits
   for each control code (stress, hat, boundary, paragraph, etc.).

See Phase E in
``/root/.claude/plans/create-a-python-port-smooth-hoare.md``.
"""

from __future__ import annotations

from typing import cast

from dectalk.include.all_phon_counts import MAX_PHONES
from dectalk.include.cmd_codes import PVALUE
from dectalk.include.defs import FALSE, TRUE
from dectalk.include.phoneme_codes import (
    BLOCK_RULES,
    COMMA,
    DOUBLCONS,
    EXCLAIM,
    HAT_FALL,
    HAT_RF,
    HAT_RISE,
    HYPHEN,
    MBOUND,
    NEW_PARAGRAPH,
    PERIOD,
    PPSTART,
    QUEST,
    RELSTART,
    S1,
    S2,
    S3,
    SBOUND,
    SEMPH,
    VPSTART,
    WBOUND,
)
from dectalk.include.usp_codes import (
    USP_F,
    USP_OR,
    USP_RR,
    USP_T,
    USP_UH,
    USP_UW,
    USP_W,
)
from dectalk.kernel.adjust_index import adjust_index
from dectalk.kernel.ksd_t import KsdT
from dectalk.kernel.lang_codes import (
    LANG_british,
    LANG_english,
    LANG_french,
    LANG_german,
    LANG_latin_american,
    LANG_spanish,
)
from dectalk.ph.delete_symbol import delete_symbol
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import (
    FBLOCK,
    FDOUBLECONS,
    FEMPHASIS,
    FHAT_BEGINS,
    FHAT_ENDS,
    FHAT_ROOF,
    FSENTENDS,
    FSTRESS_1,
    FSTRESS_2,
    FWINITC,
    PRESSBOUND,
)
from dectalk.ph.find_syll_to_stress import find_syll_to_stress
from dectalk.ph.get_next_bound_type import get_next_bound_type
from dectalk.ph.get_stress_of_conson import get_stress_of_conson
from dectalk.ph.init_med_final import init_med_final
from dectalk.ph.insertphone import insertphone
from dectalk.ph.interp_user_f0 import interp_user_f0
from dectalk.ph.inton_constants import HAT_LOCATIONS_SPECIFIED, NORMAL, SINGING
from dectalk.ph.is_wboundary import is_wboundary
from dectalk.ph.make_phone import add_feature, make_phone
from dectalk.ph.move_stdangle import move_stdangle
from dectalk.ph.phoneme_features import FSYLL
from dectalk.ph.raise_last_stress import raise_last_stress
from dectalk.ph.timing import phone_feature
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.utterance_constants import (
    COMMACLAUSE,
    DECLARATIVE,
    EXCLAIMCLAUSE,
    GEN_SIL,
    QUESTION,
)

# US-English-only ports are gated behind these language codes; the
# C source has parallel rule sets for the others that we leave for
# later Phase E work.
_SUPPORTED_LANGS = frozenset({LANG_english})

# Non-US languages that still raise NotImplementedError. Exposed so
# downstream agents can introspect deferral status.
_DEFERRED_LANGS = frozenset({LANG_british, LANG_german, LANG_spanish, LANG_latin_american})

# C source's hard-coded WBOUND test in the "missing leading word
# boundary" repair: ``pDph_t->symbols[1] != 111``. 111 is the raw
# numeric value of WBOUND (100 + 11) in the C source.
_WBOUND_RAW = 111

# Minimum symbol count needed for the leading-WBOUND repair to fire.
# Mirrors the C source's ``pDph_t->nsymbtot > 2`` guard.
_MIN_NSYMBTOT_FOR_REPAIR = 2

# Slow-rate threshold for the PPSTART -> VPSTART promotion.
_SPRATE_PROMOTE_PPSTART = 140

# Comma-clause -> declarative-clause promotion thresholds.
_MIN_COMMACNT_FOR_DECL = 1  # > 1 in the C source.
_MIN_WORDS_FOR_DECL = 4  # > 4 in the C source.

# Singing-mode F0 hint threshold (notes C2..C5 are <= 37 semitones).
_SINGING_NOTE_LIMIT = 38


def _unsupported_lang(lang_curr: int) -> bool:
    """Return True if the current language isn't in the US-only port."""
    return lang_curr not in _SUPPORTED_LANGS and lang_curr != LANG_french


def all_phsort(phTTS: TtsHandle) -> int:  # noqa: N803
    """Default per-language PH-sort entry; processes the symbols stream.

    Mirrors the C signature ``int all_phsort(LPTTS_HANDLE_T phTTS)``.

    Args:
        phTTS: Two-pointer engine handle (kernel-shared + PH-thread
            data).

    Returns:
        ``TRUE`` (``1``) on success, ``FALSE`` (``0``) on halt.

    Raises:
        NotImplementedError: For non-US-English languages (UK / GR /
            SP / LA).
    """
    p_ksd_t = cast("KsdT", phTTS.p_kernel_share_data)
    p_dph_t = cast("DphT", phTTS.p_ph_thread_data)
    pst_phsettar = cast("DphSettarSt", p_dph_t.pSTphsettar)

    if _unsupported_lang(p_ksd_t.lang_curr):
        raise NotImplementedError(
            f"all_phsort: non-US-English language {p_ksd_t.lang_curr} not yet ported (Phase E)"
        )

    # ---- Initialise per-clause state (C source lines 462-490) --------
    p_dph_t.special_phrase = 0
    p_dph_t.number_words = 0
    pst_phsettar.did_del = 0
    p_dph_t.f0mode = NORMAL
    p_dph_t.cbsymbol = 0
    p_dph_t.nphonetot = 0

    # ---- Repair: insert leading word boundary if missing. ------------
    if (
        p_dph_t.nsymbtot > _MIN_NSYMBTOT_FOR_REPAIR
        and len(p_dph_t.symbols) > 1
        and p_dph_t.symbols[1] != _WBOUND_RAW
    ):
        insertphone(p_ksd_t, p_dph_t, 1, _WBOUND_RAW)

    # ---- Pass 1: clean up input string -------------------------------
    if not _pass1_cleanup(p_ksd_t, p_dph_t, pst_phsettar):
        return FALSE

    # ---- Pass 2: emit output phoneme + sentstruc stream --------------
    return _pass2_emit(p_ksd_t, p_dph_t)


def _pass1_cleanup(  # noqa: PLR0912
    p_ksd_t: KsdT,
    p_dph_t: DphT,
    pst_phsettar: DphSettarSt,
) -> bool:
    """Pass 1 of all_phsort: clean up ``symbols[]`` re mis-orderings."""
    nstresses = 0
    nstartphrase = 0

    n = 0
    while n < p_dph_t.nsymbtot:
        if p_ksd_t.halting:
            return False

        if pst_phsettar.did_del:
            # A delete shifted things down; back up one to re-process.
            n -= 1
            pst_phsettar.did_del = 0
            if n < 0:
                n = 0
                continue

        if n >= len(p_dph_t.symbols):
            break
        sym_n = p_dph_t.symbols[n]
        sym_val = sym_n & PVALUE

        # -- Adjacent NEW_PARAGRAPH dedup ------------------------------
        if (
            sym_n == NEW_PARAGRAPH
            and n + 1 < len(p_dph_t.symbols)
            and p_dph_t.symbols[n + 1] == NEW_PARAGRAPH
        ):
            delete_symbol(p_ksd_t, p_dph_t, pst_phsettar, n)
            n += 1
            continue

        # -- WBOUND + PERIOD dedup -------------------------------------
        if sym_n == WBOUND and n + 1 < len(p_dph_t.symbols) and p_dph_t.symbols[n + 1] == PERIOD:
            delete_symbol(p_ksd_t, p_dph_t, pst_phsettar, n)
            n += 1
            continue

        # -- HAT_RISE..HAT_RF -> set HAT_LOCATIONS_SPECIFIED mode ------
        if HAT_RISE <= sym_val <= HAT_RF and p_dph_t.f0mode == NORMAL:
            p_dph_t.f0mode = HAT_LOCATIONS_SPECIFIED

        # -- Clause-final function word: PPSTART promotion -------------
        if sym_n == PPSTART:
            _handle_ppstart(p_ksd_t, p_dph_t, pst_phsettar, n)

        # -- Stress counter for the "every breath group needs S1" rule -
        if sym_val in (S1, SEMPH):
            nstresses += 1

        # -- Slow-rate PPSTART -> VPSTART promotion --------------------
        if p_ksd_t.sprate <= _SPRATE_PROMOTE_PPSTART and sym_n == PPSTART:
            p_dph_t.symbols[n] = VPSTART
            sym_val = VPSTART & PVALUE

        # -- Every breath group must have one primary stress -----------
        if COMMA <= sym_val <= EXCLAIM and n > 0 and nstresses == 0:
            locend = [n]
            find_syll_to_stress(p_ksd_t, p_dph_t, locend, nstartphrase)
            n = locend[0]
            nstresses = 1

        # -- Reset to new phrase on RELSTART..EXCLAIM ------------------
        if RELSTART <= sym_val <= EXCLAIM:
            nstresses = 0
            nstartphrase = n

        # -- EXCLAIM raises last stress to emphasis --------------------
        if sym_val == EXCLAIM:
            raise_last_stress(p_dph_t, n)

        # -- QUEST marks the clause as a question ----------------------
        if sym_val == QUEST:
            p_dph_t.cbsymbol = TRUE

        n += 1

    return True


def _handle_ppstart(
    p_ksd_t: KsdT,
    p_dph_t: DphT,
    pst_phsettar: DphSettarSt,
    n: int,
) -> None:
    """Handle the ``PPSTART`` -> ``WBOUND`` clause-final promotion."""
    m = n + 1
    while m < p_dph_t.nsymbtot:
        if m >= len(p_dph_t.symbols):
            return
        if is_wboundary(p_dph_t.symbols[m] & PVALUE):
            if (p_dph_t.symbols[m] & PVALUE) == WBOUND:
                m += 1
            if m >= len(p_dph_t.symbols):
                return
            m_val = p_dph_t.symbols[m] & PVALUE
            next_val = p_dph_t.symbols[m + 1] if m + 1 < len(p_dph_t.symbols) else 0
            if m_val >= COMMA or (m_val == PPSTART and next_val != USP_W):
                p_dph_t.symbols[n] = WBOUND
                if m_val == PPSTART:
                    p_dph_t.symbols[m] = VPSTART
                _unreduce_for_to_into(p_dph_t, n, m)

                if n + 1 < len(p_dph_t.symbols) and p_dph_t.symbols[n + 1] == S2:
                    p_dph_t.symbols[n + 1] = S1
                else:
                    insertphone(p_ksd_t, p_dph_t, n + 1, S1)
                    move_stdangle(p_ksd_t, p_dph_t, pst_phsettar, n + 1)
            return

        m += 1


def _unreduce_for_to_into(p_dph_t: DphT, n: int, m: int) -> None:
    """Apply the "for / to / into" vowel-unreduction in the PPSTART rule."""
    symbols = p_dph_t.symbols
    if n + 2 < len(symbols) and symbols[n + 1] == USP_F and symbols[n + 2] == USP_RR:
        symbols[n + 2] = USP_OR
    if (
        m - 2 >= 0
        and m - 1 < len(symbols)
        and symbols[m - 2] == USP_T
        and symbols[m - 1] == USP_UH
        and n + 2 < len(symbols)
    ):
        symbols[n + 2] = USP_UW


def _pass2_emit(p_ksd_t: KsdT, p_dph_t: DphT) -> int:  # noqa: PLR0912
    """Pass 2 of all_phsort: emit phonemes + feature bits."""
    mf0 = [0]
    p_dph_t.nphonetot = 0
    word_init_sw_box = [FALSE]
    compound_destress_box = [FALSE]
    in_rhyme = FALSE
    p_dph_t.newparagsw = FALSE

    p_dph_t.hat_seen = 0
    p_dph_t.wordcount = 1

    for n in range(p_dph_t.nsymbtot):
        snphonetot = p_dph_t.nphonetot

        if p_ksd_t.halting:
            return FALSE

        if n >= len(p_dph_t.symbols):
            break
        curr_in_phone = p_dph_t.symbols[n]
        curr_in_sym = p_dph_t.symbols[n] & PVALUE

        curr_dur_box = [0]
        curr_f0_box = [0]
        if p_dph_t.user_durs is not None and n < len(p_dph_t.user_durs):
            curr_dur_box[0] = p_dph_t.user_durs[n]
            p_dph_t.user_durs[n] = 0
        if p_dph_t.user_f0 is not None and n < len(p_dph_t.user_f0):
            curr_f0_box[0] = p_dph_t.user_f0[n]
            p_dph_t.user_f0[n] = 0

        # Interpret a (dur, f0) attached to a stress / hat impulse.
        interp_user_f0(p_dph_t, curr_dur_box, curr_f0_box, curr_in_sym, mf0)
        curr_dur = curr_dur_box[0]
        curr_f0 = curr_f0_box[0]

        # Singing-mode detection from f0 hint.
        if curr_f0 > 0 and (curr_f0 % 1000) < _SINGING_NOTE_LIMIT:
            p_dph_t.f0mode = SINGING

        if curr_in_sym < MAX_PHONES:
            # A real phoneme.
            make_phone(p_dph_t, curr_in_phone, n, curr_dur, curr_f0)

            if (phone_feature(curr_in_phone) & FSYLL) != 0:
                in_rhyme = TRUE
                word_init_sw_box[0] = FALSE
                init_med_final(p_dph_t, n)
            else:
                get_stress_of_conson(p_dph_t, n, compound_destress_box[0])

            if word_init_sw_box[0] == TRUE:
                currphone = p_dph_t.nphonetot - 1
                add_feature(p_dph_t, FWINITC, currphone)

            if in_rhyme == TRUE:
                get_next_bound_type(p_dph_t, n)
        else:
            _handle_control_symbol(
                p_dph_t,
                n,
                curr_in_sym,
                curr_dur,
                curr_f0,
                word_init_sw_box,
                compound_destress_box,
            )

        if p_dph_t.nphonetot == snphonetot:
            adjust_index(p_ksd_t.spc_pkt_save, n + 1, -1, 0)

    return TRUE


def _handle_control_symbol(  # noqa: PLR0912, PLR0915
    p_dph_t: DphT,
    n: int,
    curr_in_sym: int,
    curr_dur: int,
    curr_f0: int,
    word_init_sw_box: list[int],
    compound_destress_box: list[int],
) -> None:
    """Dispatch the per-control-symbol switch in pass 2 (ph_sort.c 1467-1696)."""
    nextphone = p_dph_t.nphonetot

    if curr_in_sym == DOUBLCONS:
        add_feature(p_dph_t, FDOUBLECONS, nextphone)
    elif curr_in_sym == S1:
        add_feature(p_dph_t, FSTRESS_1, nextphone)
    elif curr_in_sym == S2:
        add_feature(p_dph_t, FSTRESS_2, nextphone)
    elif curr_in_sym == S3:
        # Spanish quote-phrase marker; no-op for US.
        return
    elif curr_in_sym == SEMPH:
        add_feature(p_dph_t, FEMPHASIS, nextphone)
    elif curr_in_sym in (HYPHEN, MBOUND, SBOUND):
        # English HLSYN build skips the MBOUND/SBOUND feature add.
        return
    elif curr_in_sym == WBOUND:
        p_dph_t.number_words += 1
        word_init_sw_box[0] = TRUE
    elif curr_in_sym in (PPSTART, VPSTART):
        word_init_sw_box[0] = TRUE
    elif curr_in_sym == RELSTART:
        word_init_sw_box[0] = TRUE
        if n + 1 < len(p_dph_t.symbols) and p_dph_t.symbols[n + 1] == HYPHEN:
            return
        word_init_sw_box[0] = TRUE
        compound_destress_box[0] = FALSE
    elif curr_in_sym == COMMA:
        p_dph_t.clausetype = COMMACLAUSE
        p_dph_t.clausenumber += 1
        p_dph_t.dcommacnt += 1
        if p_dph_t.dcommacnt > _MIN_COMMACNT_FOR_DECL or p_dph_t.number_words > _MIN_WORDS_FOR_DECL:
            p_dph_t.clausetype = DECLARATIVE
        make_phone(p_dph_t, GEN_SIL, n, curr_dur, curr_f0)
        word_init_sw_box[0] = TRUE
        compound_destress_box[0] = FALSE
    elif curr_in_sym == PERIOD:
        p_dph_t.clausetype = DECLARATIVE
        add_feature(p_dph_t, FSENTENDS, nextphone)
        p_dph_t.clausenumber = 0
        make_phone(p_dph_t, GEN_SIL, n, curr_dur, curr_f0)
        word_init_sw_box[0] = TRUE
        compound_destress_box[0] = FALSE
    elif curr_in_sym == EXCLAIM:
        p_dph_t.clausetype = EXCLAIMCLAUSE
        p_dph_t.clausenumber = 0
        make_phone(p_dph_t, GEN_SIL, n, curr_dur, curr_f0)
        word_init_sw_box[0] = TRUE
        compound_destress_box[0] = FALSE
    elif curr_in_sym == QUEST:
        p_dph_t.clausetype = QUESTION
        p_dph_t.clausenumber = 0
        make_phone(p_dph_t, GEN_SIL, n, curr_dur, curr_f0)
        word_init_sw_box[0] = TRUE
        compound_destress_box[0] = FALSE
    elif curr_in_sym == HAT_RISE:
        p_dph_t.hat_seen += 1
        add_feature(p_dph_t, FHAT_BEGINS, nextphone)
    elif curr_in_sym == HAT_FALL:
        p_dph_t.hat_seen += 1
        add_feature(p_dph_t, FHAT_ENDS, nextphone)
    elif curr_in_sym == HAT_RF:
        p_dph_t.hat_seen += 1
        add_feature(p_dph_t, FHAT_ROOF, nextphone)
    elif curr_in_sym == BLOCK_RULES:
        add_feature(p_dph_t, FBLOCK, nextphone)
    elif curr_in_sym == NEW_PARAGRAPH:
        add_feature(p_dph_t, PRESSBOUND, nextphone)
        add_feature(p_dph_t, PRESSBOUND, p_dph_t.nphonetot + 1)
        p_dph_t.newparagsw = TRUE


__all__ = ["all_phsort"]
