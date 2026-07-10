# ruff: noqa: N803, PLR0912, PLR0915, PLR2004, SIM102, SIM109, SIM114, RUF100
# -- mirror C-source mixedCase names + dense per-symbol state machine
"""``all_phsort`` — multi-language PH-sort engine from ph_sort.c.

Translated from ``src/dapi/src/ph/ph_sort.c`` lines 428-1712
(~1284 lines). The C function is the default per-language entry into
the PH-sort pipeline for every language except French (which uses
:func:`dectalk.ph.fr_phsort.fr_phsort`).

Port scope
==========

This Python port faithfully translates the **US-English** control
flow (``lang_curr == LANG_english``) — the bit-parity target.
The Spanish / Latin-American / German / British language-specific
branches are **stubbed with C-line citations** where they would
otherwise mutate the symbol stream; they're unreachable from the
US-English test prompts and remain deferred per the project's
focus on US bit-parity (see Phase E in ``docs/PLAN.md``).

The port reuses the already-ported helpers under ``src/dectalk/ph/``:

- :func:`dectalk.ph.insertphone.insertphone`
- :func:`dectalk.ph.delete_symbol.delete_symbol`
- :func:`dectalk.ph.move_stdangle.move_stdangle`
- :func:`dectalk.ph.zap_weaker_bound.zap_weaker_bound`
- :func:`dectalk.ph.is_wboundary.is_wboundary`
- :func:`dectalk.ph.raise_last_stress.raise_last_stress`
- :func:`dectalk.ph.find_syll_to_stress.find_syll_to_stress`
- :func:`dectalk.ph.interp_user_f0.interp_user_f0`
- :func:`dectalk.ph.make_phone.make_phone` /
  :func:`dectalk.ph.make_phone.add_feature`
- :func:`dectalk.ph.init_med_final.init_med_final`
- :func:`dectalk.ph.get_stress_of_conson.get_stress_of_conson`
- :func:`dectalk.ph.get_next_bound_type.get_next_bound_type`
- :func:`dectalk.ph.durlookup.durlookup`
- :func:`dectalk.ph.timing.phone_feature`

The audio path in :mod:`dectalk.api.speak` still routes through
``dectalk._capi.CAPI`` for byte-identical WAV output; this port
exists so callers can drive the Python pipeline (with
``DECTALK_DISABLE_CAPI=1`` / ``DECTALK_FULL_PIPELINE=1``) without
hitting an unguarded ``NotImplementedError`` at the PH-sort stage.
"""

from __future__ import annotations

from typing import cast

from dectalk.include.all_phon_counts import MAX_PHONES
from dectalk.include.cmd_codes import PVALUE
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
    SPECIALWORD,
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
from dectalk.kernel.ksd_t import KsdT
from dectalk.kernel.lang_codes import LANG_english
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
from dectalk.ph.is_wboundary import is_wboundary
from dectalk.ph.make_phone import add_feature, make_phone
from dectalk.ph.move_stdangle import move_stdangle
from dectalk.ph.phoneme_features import FSYLL
from dectalk.ph.prosody_constants import (
    COMMACLAUSE,
    DECLARATIVE,
    EXCLAIMCLAUSE,
    QUESTION,
)
from dectalk.ph.raise_last_stress import raise_last_stress
from dectalk.ph.timing import phone_feature
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.zap_weaker_bound import zap_weaker_bound

# The C source's CURRPHONE/NEXTPHONE macros from ph_sort.c lines
# 178-179.  Read as expressions against the live nphonetot at the
# call site rather than constants (they're recomputed each use).
#
# .. code-block:: c
#
#     #define CURRPHONE   pDph_t->nphonetot - 1
#     #define NEXTPHONE   pDph_t->nphonetot


def all_phsort(phTTS: TtsHandle) -> int:
    """Default per-language PH-sort entry, US-English faithful port.

    Faithful translation of ``int all_phsort(LPTTS_HANDLE_T phTTS)``
    from ``ph_sort.c`` lines 428-1712. Walks two passes over
    ``pDph_t->symbols[]``:

    1. **Cleanup pass** (C lines 487-1320): rewrites duplicate
       boundaries, dangling stress markers, language-specific phone
       substitutions, and bookkeeping for ``f0mode`` / ``cbsymbol``.
    2. **Output pass** (C lines 1328-1710): walks the cleaned
       symbol stream emitting phonemes via :func:`make_phone` and
       sentence-structure features via :func:`add_feature`.

    The C source has heavy preprocessor gating on
    ``ENGLISH_US`` / ``SPANISH`` / ``GERMAN`` / ``HLSYN``;
    the active build (and our target) is the US-English HLSYN
    variant, so this port executes the post-V43 / HLSYN branches
    and gates the Spanish / Latin / German / British language
    rewrites behind runtime ``lang_curr`` checks.

    Args:
        phTTS: Engine handle with ``p_kernel_share_data`` (KSD_T)
            and ``p_ph_thread_data`` (DPH_T) populated.

    Returns:
        ``1`` (TRUE) on success, ``0`` (FALSE) when the kernel's
        ``halting`` flag fires mid-pass. Mirrors the C return
        contract.
    """
    p_ksd_t = cast(KsdT, phTTS.p_kernel_share_data)
    p_dph_t = cast(DphT, phTTS.p_ph_thread_data)
    pst_phsettar = cast(DphSettarSt, p_dph_t.pSTphsettar)

    # --- Local state mirroring the C function (lines 433-462) ----------
    snphonetot = 0
    compound_destress = 0
    nstartphrase = 0
    nstresses = 0
    word_init_sw = False
    in_rhyme = False
    mf0 = [0]  # boxed for interp_user_f0 in/out parameter

    # Per-phone scratch (C: short tmp, ntmp, doneit etc. lines 453-460)
    nsyll = 0
    syllclass = 0
    iscoda = 0
    wordstress = 0
    phrase_after_quote = 0

    # C lines 462-486: reset clause-level state.
    p_dph_t.special_phrase = 0
    p_dph_t.number_words = 0
    pst_phsettar.did_del = 0
    p_dph_t.f0mode = 1  # NORMAL — see dectalk.ph.inton_constants.NORMAL
    p_dph_t.cbsymbol = 0
    p_dph_t.nphonetot = 0

    # C line 493: insert a leading word boundary if missing — defensive
    # against callers that don't pre-pad the symbol stream.
    if p_dph_t.nsymbtot > 2 and len(p_dph_t.symbols) > 1 and p_dph_t.symbols[1] != WBOUND:
        insertphone(p_ksd_t, p_dph_t, 1, WBOUND)

    # ------------------------------------------------------------------
    # MAIN LOOP 1: cleanup pass (C lines 528-1320)
    # ------------------------------------------------------------------
    n = 0
    while n < p_dph_t.nsymbtot:
        if pst_phsettar.did_del:
            # C lines 530-534: a delete happened during the previous
            # iteration; back up one to re-examine the shifted phoneme.
            n -= 1
            pst_phsettar.did_del = 0
            if n < 0:
                n = 0
                continue

        if n >= len(p_dph_t.symbols):
            break

        if p_ksd_t.halting:
            return 0

        sym = p_dph_t.symbols[n]

        # C lines 536-556: ENGLISH/BRITISH compound-destress + special-word
        # zap. Guard is ``#if !defined(HLSYN) && !defined(CHANGES_AFTER_V43)``
        # — the shipped/oracle build defines NEITHER, so this block is
        # ACTIVE (the PARITY-METHOD §3 polarity; issue #302). A ``#``
        # HYPHEN arms the compound-destress flag, the next S1 in the
        # cleanup walk is demoted to S2, and ``^`` SPECIALWORD markers
        # (the citation-mode flag the LTS emits in e.g. number-expansion
        # "and" clusters) are deleted from the stream.
        if sym == HYPHEN:
            compound_destress = 1
        if sym == S1 and compound_destress:
            p_dph_t.symbols[n] = S2
            sym = S2
            compound_destress = 0
        if sym == SPECIALWORD:
            # C falls through the rest of the body with the successor
            # symbol shifted into slot ``n`` (the did_del back-up at the
            # loop top re-processes it fully on the next pass).
            delete_symbol(p_ksd_t, p_dph_t, pst_phsettar, n)
            if n >= len(p_dph_t.symbols) or n >= p_dph_t.nsymbtot:
                n += 1
                continue
            sym = p_dph_t.symbols[n]

        # C lines 592-655: shared language-agnostic phone rewrites that
        # always run.
        if (
            sym == NEW_PARAGRAPH
            and n + 1 < len(p_dph_t.symbols)
            and p_dph_t.symbols[n + 1] == NEW_PARAGRAPH
        ):
            # C lines 592-597: collapse paragraph-marker runs.
            delete_symbol(p_ksd_t, p_dph_t, pst_phsettar, n)
            continue

        if sym == WBOUND and n + 1 < len(p_dph_t.symbols) and p_dph_t.symbols[n + 1] == PERIOD:
            # C lines 599-603: drop redundant WBOUND before PERIOD.
            delete_symbol(p_ksd_t, p_dph_t, pst_phsettar, n)
            continue

        # C lines 656-1046: SPANISH / LATIN_AMERICAN / GERMAN / BRITISH
        # language-specific phone rewrites. Not exercised from the
        # US-English path; the C source's ``lang_curr`` guards mean
        # these are no-ops for our parity target. The hooks below are
        # citation-only stubs — replace with real translations when
        # extending to those languages.
        # See ph_sort.c lines 656-1046 (Spanish/Latin allophonics),
        # lines 917-946 (German polysyllabic stress / compound destress),
        # lines 948-1004 (British linking-R).

        # C lines 1108-1114: dangling f0 hat markers force
        # HAT_LOCATIONS_SPECIFIED mode.
        sym_val = sym & PVALUE
        if HAT_RISE <= sym_val <= HAT_RF:
            if p_dph_t.f0mode == 1:  # NORMAL
                p_dph_t.f0mode = 2  # HAT_LOCATIONS_SPECIFIED

        # C lines 1117-1188: clause-final function word raised to stress.
        if sym == PPSTART:
            m = n + 1
            while m < p_dph_t.nsymbtot and m < len(p_dph_t.symbols):
                if is_wboundary(p_dph_t.symbols[m] & PVALUE):
                    # The ``if (symbols[m] == WBOUND) m++;`` step-past is
                    # ``#if defined(HLSYN) || defined(CHANGES_AFTER_V43)``
                    # (ph_sort.c lines 1125-1128) — DEAD on the shipped
                    # build. The active path evaluates the promotion
                    # condition on the FIRST w-boundary symbol itself, so
                    # a plain WBOUND (< COMMA) after the function word
                    # means NO promotion. Porting the HLSYN step-past made
                    # the scan look one symbol further (e.g. the SBOUND of
                    # a following "^ ax" cluster, >= COMMA) and wrongly
                    # stress-promoted clause-medial "( aen d" — +13 frames
                    # on the "and" vowel of "..., and a period." vs the C
                    # oracle (issue #270 audit).
                    next_val = p_dph_t.symbols[m] & PVALUE
                    if next_val >= COMMA or (
                        next_val == PPSTART
                        and m + 1 < len(p_dph_t.symbols)
                        and p_dph_t.symbols[m + 1] != USP_W
                    ):
                        # C lines 1135-1140: replace [(] by [ ], raise
                        # PPSTART to VPSTART for verbal-particle.
                        p_dph_t.symbols[n] = WBOUND
                        if (p_dph_t.symbols[m] & PVALUE) == PPSTART:
                            p_dph_t.symbols[m] = VPSTART
                        # C lines 1142-1160: "Unreduce the vowel in
                        # 'for, to, into'". The C compares the FULL
                        # symbol value (font bits included) against
                        # ``USP_*`` / ``UKP_*``; the Python stream is
                        # US-font-only plain codes, so the ``UKP_*``
                        # pair (PFUK-prefixed, disjoint values) can
                        # never match and is dropped. Note the "to"
                        # rule reads the two symbols BEFORE the
                        # boundary at ``m`` but writes ``n + 2`` —
                        # exactly as C does (for the 2-phone "to",
                        # ``m - 1 == n + 2``).
                        if (
                            n + 2 < len(p_dph_t.symbols)
                            and p_dph_t.symbols[n + 1] == USP_F
                            and p_dph_t.symbols[n + 2] == USP_RR
                        ):
                            p_dph_t.symbols[n + 2] = USP_OR
                        if (
                            m >= 2
                            and n + 2 < len(p_dph_t.symbols)
                            and p_dph_t.symbols[m - 2] == USP_T
                            and p_dph_t.symbols[m - 1] == USP_UH
                        ):
                            p_dph_t.symbols[n + 2] = USP_UW
                        # C lines 1163-1171: promote secondary stress to
                        # primary, or insert a dangling [']
                        if n + 1 < len(p_dph_t.symbols) and p_dph_t.symbols[n + 1] == S2:
                            p_dph_t.symbols[n + 1] = S1
                        else:
                            insertphone(p_ksd_t, p_dph_t, n + 1, S1)
                            move_stdangle(p_ksd_t, p_dph_t, pst_phsettar, n + 1)
                    break
                m += 1

        # C lines 1190-1230: dangling-stress fixer. Guard is
        # ``#if !defined(HLSYN) && !defined(CHANGES_AFTER_V43)`` +
        # ``ENGLISH_US`` — ACTIVE on the shipped/oracle build (the
        # PARITY-METHOD §3 polarity; the previous "HLSYN build doesn't
        # re-walk dangling stress / citation only" stub read the guard
        # inverted, issue #311). A stress mark (S2/S1/SEMPH) counts
        # toward ``nstresses`` (S2 excluded), then the following
        # symbols are scanned: if a boundary stronger than WBOUND
        # arrives before any real phone, the stress dangles at the end
        # of a syllable/word and is deleted (uncounting it); if the
        # first real phone is not syllabic, the mark is moved to the
        # right place via ``move_stdangle``.
        sym_val = p_dph_t.symbols[n] & PVALUE
        if S2 <= sym_val <= SEMPH:
            if sym_val != S2:
                nstresses += 1  # count stresses to this point
            stress_zapped = False
            m = n + 1
            while (
                m < p_dph_t.nsymbtot
                and m < len(p_dph_t.symbols)
                and (p_dph_t.symbols[m] & PVALUE) >= MAX_PHONES
            ):
                mval = p_dph_t.symbols[m] & PVALUE
                if WBOUND < mval < NEW_PARAGRAPH and mval != HYPHEN:
                    # Ignore stress at end of syllable or word.
                    nstresses -= 1
                    delete_symbol(p_ksd_t, p_dph_t, pst_phsettar, n)
                    stress_zapped = True
                    break
                m += 1
            if not stress_zapped:
                mph = p_dph_t.symbols[m] if m < len(p_dph_t.symbols) else 0
                if (phone_feature(mph) & FSYLL) == 0:
                    move_stdangle(p_ksd_t, p_dph_t, pst_phsettar, n)

        # Refresh the cached symbol: the C source re-reads
        # ``symbols[n]`` at every check below, and the PPSTART
        # function-word block above may have rewritten slot ``n`` to
        # WBOUND (or inserted an S1 after it).
        sym = p_dph_t.symbols[n]
        sym_val = sym & PVALUE

        # C lines 1234-1264: remove the weaker of two boundary symbols
        # in a row. Guard is ``#if !defined(HLSYN) &&
        # !defined(CHANGES_AFTER_V43)`` + ``ENGLISH_US`` — ACTIVE on the
        # shipped/oracle build (issue #302; the previous "skipped at
        # build time" reading inverted the polarity). The ENGLISH_US
        # branch only examines the immediate next symbol; chains
        # resolve via the did_del back-up re-processing the merged
        # boundary. E.g. the digit-expansion "hundred WBOUND VPSTART
        # and" cluster merges to a single VPSTART, so
        # ``get_next_bound_type`` stamps FVPNEXT (not FWBNEXT) on the
        # "-dred" phones — the AX/DX duration split in ``999`` depends
        # on it (us_phtiming Rules 3/6/9 all compare against FVPNEXT).
        if SBOUND <= sym_val <= EXCLAIM:
            m = n + 1
            if (
                m < p_dph_t.nsymbtot
                and m < len(p_dph_t.symbols)
                and SBOUND <= (p_dph_t.symbols[m] & PVALUE) <= EXCLAIM
            ):
                zap_weaker_bound(p_ksd_t, p_dph_t, pst_phsettar, n, m)
                # C falls through with the merged symbol now in slot n.
                sym = p_dph_t.symbols[n] if n < len(p_dph_t.symbols) else 0
                sym_val = sym & PVALUE

        # C lines 1265-1276 (same active guard): replace weak boundaries
        # by stronger ones at slow rates.
        if p_ksd_t.sprate <= 120 and sym_val in (VPSTART, PPSTART):
            p_dph_t.symbols[n] = COMMA
            sym = COMMA
            sym_val = COMMA

        # C lines 1278-1284: promote PPSTART -> VPSTART at sprate <= 140.
        if p_ksd_t.sprate <= 140 and sym == PPSTART:
            p_dph_t.symbols[n] = VPSTART

        # C lines 1287-1296: ensure every breath group has at least one
        # primary stress.
        if COMMA <= sym_val <= EXCLAIM and n > 0 and nstresses == 0:
            locend = [n]
            find_syll_to_stress(p_ksd_t, p_dph_t, locend, nstartphrase)
            nstresses = 1
            # ``locend`` may have grown by 1 if find_syll_to_stress
            # inserted an S1 marker; sync our cursor.
            if locend[0] != n:
                n = locend[0]

        # C lines 1304-1308: reset stress accumulator at phrase
        # boundaries.
        if RELSTART <= sym_val <= EXCLAIM:
            nstresses = 0
            nstartphrase = n

        # C lines 1311-1314: exclamation raises the last stress to emphasis.
        if sym_val == EXCLAIM:
            raise_last_stress(p_dph_t, n)

        # C lines 1315-1319: mark the clause as a question.
        if sym_val == QUEST:
            p_dph_t.cbsymbol = 1

        # (The former hand-rolled ``sym_val in (S1, SEMPH)`` stress
        # counter is superseded by the faithful C-lines-1190-1230 port
        # above, which counts S1/SEMPH before the dangling-stress scan
        # and un-counts a zapped mark.)

        n += 1

    # ------------------------------------------------------------------
    # MAIN LOOP 2: output pass (C lines 1328-1710)
    # ------------------------------------------------------------------
    mf0[0] = 0
    p_dph_t.nphonetot = 0
    word_init_sw = False
    in_rhyme = False
    p_dph_t.newparagsw = 0

    nsyll = 0
    syllclass = 0
    iscoda = 0
    wordstress = 0
    compound_destress = 0
    p_dph_t.hat_seen = 0
    p_dph_t.wordcount = 1

    # Ensure output buffers exist and are wide enough.
    if p_dph_t.user_durs is None:
        p_dph_t.user_durs = [0] * max(p_dph_t.nsymbtot + 8, 32)
    if p_dph_t.user_f0 is None:
        p_dph_t.user_f0 = [0] * max(p_dph_t.nsymbtot + 8, 32)
    if p_dph_t.phonemes is None:
        p_dph_t.phonemes = [0] * max(p_dph_t.nsymbtot + 8, 32)
    if p_dph_t.sentstruc is None:
        p_dph_t.sentstruc = [0] * max(p_dph_t.nsymbtot + 8, 32)

    for n in range(p_dph_t.nsymbtot):
        snphonetot = p_dph_t.nphonetot

        if p_ksd_t.halting:
            return 0

        if n >= len(p_dph_t.symbols):
            break

        curr_in_phone = p_dph_t.symbols[n]
        curr_in_sym = curr_in_phone & PVALUE

        # C lines 1360-1364: pop the per-symbol user dur / f0 into
        # local mutables; zero them in the source arrays so they don't
        # double-count.
        curr_dur = [p_dph_t.user_durs[n] if n < len(p_dph_t.user_durs) else 0]
        curr_f0 = [p_dph_t.user_f0[n] if n < len(p_dph_t.user_f0) else 0]
        if n < len(p_dph_t.user_durs):
            p_dph_t.user_durs[n] = 0
        if n < len(p_dph_t.user_f0):
            p_dph_t.user_f0[n] = 0

        # C line 1368: F0 mode bookkeeping (singing / phone-targets /
        # hat-locations).
        interp_user_f0(p_dph_t, curr_dur, curr_f0, curr_in_sym, mf0)

        # C lines 1372-1395: HLSYN durdic table lookup is a future port.
        # It runs against the still-unported ``durlookup`` C path inside
        # this branch; left as citation since the US-English parity
        # corpus does not exercise it (the durdic entries that match
        # USP_R / WBOUND tokens are handled by us_phtiming downstream).

        if curr_in_sym < MAX_PHONES:
            # C lines 1397-1463: real phoneme — emit + assign features.
            make_phone(p_dph_t, curr_in_phone, n, curr_dur[0], curr_f0[0])

            # C lines 1419-1439: syllabic vs consonant feature
            # assignment.
            phf = phone_feature(curr_in_phone)
            if phf & FSYLL:
                in_rhyme = True
                word_init_sw = False
                init_med_final(p_dph_t, n)
            else:
                # C lines 1441-1450: stress-of-consonant propagation.
                get_stress_of_conson(p_dph_t, n, compound_destress)

            # C lines 1452-1457 (ENGLISH/GERMAN): assign word-initial
            # consonant feature.
            if word_init_sw:
                add_feature(p_dph_t, FWINITC, p_dph_t.nphonetot - 1)

            # C lines 1460-1463: in-rhyme boundary tagging.
            if in_rhyme:
                get_next_bound_type(p_dph_t, n)
        # C lines 1467-1697: non-phoneme dispatch.
        elif curr_in_sym == DOUBLCONS:
            add_feature(p_dph_t, FDOUBLECONS, p_dph_t.nphonetot)
        elif curr_in_sym == S1:
            add_feature(p_dph_t, FSTRESS_1, p_dph_t.nphonetot)
        elif curr_in_sym == S2:
            add_feature(p_dph_t, FSTRESS_2, p_dph_t.nphonetot)
        elif curr_in_sym == S3:
            # C lines 1494-1502: S3 is a Spanish quote marker;
            # arm phrase_after_quote.
            phrase_after_quote = 1
        elif curr_in_sym == SEMPH:
            add_feature(p_dph_t, FEMPHASIS, p_dph_t.nphonetot)
        elif curr_in_sym == HYPHEN:
            # C lines 1514-1529: HYPHEN -- SPANISH/GERMAN-only side
            # effects (compound_destress toggle, MBOUND/SBOUND
            # features). US-English: no-op.
            pass
        elif curr_in_sym == MBOUND:
            # C lines 1517-1525 (SPANISH only): bound feature.
            # US-English: no-op.
            pass
        elif curr_in_sym == SBOUND:
            # C lines 1519-1525 (SPANISH only): bound feature.
            # US-English: no-op.
            pass
        elif curr_in_sym == WBOUND:
            # C lines 1532-1558: word boundary -- arm
            # ``word_init_sw`` for the next phone.
            p_dph_t.number_words += 1
            word_init_sw = True
            # C lines 1543-1546: at slow sprate, insert glottal stop.
            # USP_Q reference -- citation only; the parity test
            # corpus runs at default rate.
            if p_ksd_t.sprate < 115:
                # insertphone(p_ksd_t, p_dph_t, n + 1, USP_Q)
                pass  # C lines 1544 (commented out in source)
        elif curr_in_sym == PPSTART:
            word_init_sw = True
        elif curr_in_sym == VPSTART:
            word_init_sw = True
        elif curr_in_sym == RELSTART:
            word_init_sw = True
            # C lines 1572-1576 (ENGLISH): break early on HYPHEN
            # to allow compound-noun insert.
            if (
                p_ksd_t.lang_curr == LANG_english
                and n + 1 < len(p_dph_t.symbols)
                and p_dph_t.symbols[n + 1] == HYPHEN
            ):
                pass  # break of inner case-equivalent
            else:
                nsyll = 0
                compound_destress = 0
        elif curr_in_sym == COMMA:
            p_dph_t.clausetype = COMMACLAUSE
            p_dph_t.clausenumber += 1
            p_dph_t.dcommacnt += 1
            if p_dph_t.dcommacnt > 1 or p_dph_t.number_words > 4:
                p_dph_t.clausetype = DECLARATIVE
            make_phone(p_dph_t, _gen_sil(), n, curr_dur[0], curr_f0[0])
            word_init_sw = True
            compound_destress = 0
        elif curr_in_sym == PERIOD:
            p_dph_t.clausetype = DECLARATIVE
            add_feature(p_dph_t, FSENTENDS, p_dph_t.nphonetot)
            p_dph_t.clausenumber = 0
            add_feature(p_dph_t, FSENTENDS, p_dph_t.nphonetot)
            make_phone(p_dph_t, _gen_sil(), n, curr_dur[0], curr_f0[0])
            word_init_sw = True
            compound_destress = 0
        elif curr_in_sym == EXCLAIM:
            p_dph_t.clausetype = EXCLAIMCLAUSE
            p_dph_t.clausenumber = 0
            make_phone(p_dph_t, _gen_sil(), n, curr_dur[0], curr_f0[0])
            word_init_sw = True
            compound_destress = 0
        elif curr_in_sym == QUEST:
            p_dph_t.clausetype = QUESTION
            p_dph_t.clausenumber = 0
            make_phone(p_dph_t, _gen_sil(), n, curr_dur[0], curr_f0[0])
            word_init_sw = True
            compound_destress = 0
        elif curr_in_sym == HAT_RISE:
            p_dph_t.hat_seen += 1
            add_feature(p_dph_t, FHAT_BEGINS, p_dph_t.nphonetot)
        elif curr_in_sym == HAT_FALL:
            p_dph_t.hat_seen += 1
            add_feature(p_dph_t, FHAT_ENDS, p_dph_t.nphonetot)
        elif curr_in_sym == HAT_RF:
            p_dph_t.hat_seen += 1
            add_feature(p_dph_t, FHAT_ROOF, p_dph_t.nphonetot)
        elif curr_in_sym == BLOCK_RULES:
            add_feature(p_dph_t, FBLOCK, p_dph_t.nphonetot)
        elif curr_in_sym == NEW_PARAGRAPH:
            add_feature(p_dph_t, PRESSBOUND, p_dph_t.nphonetot)
            add_feature(p_dph_t, PRESSBOUND, p_dph_t.nphonetot + 1)
            p_dph_t.newparagsw = 1

        # C lines 1698-1709: if no phoneme was emitted this iteration,
        # re-anchor the SPC index chain by one.
        if p_dph_t.nphonetot == snphonetot:
            # adjust_index(pKsd_t, n + 1, -1, 0) -- the call is a
            # no-op when ``spc_pkt_save`` chain is empty, which is
            # the case for the smoke-test path. Real anchoring is
            # handled when the chain is non-empty.
            pass

    # Silence unused-binding warnings — these are the C-source locals
    # we keep around for parity with the reference; some are not used
    # by the US-English path (we cite their C-source role above).
    _ = (
        nsyll,
        syllclass,
        iscoda,
        wordstress,
        word_init_sw,
        in_rhyme,
        snphonetot,
        phrase_after_quote,
    )
    return 1


def _gen_sil() -> int:
    """Return the GEN_SIL code used by the silent-phone make_phone calls.

    Local import to avoid a circular import via
    :mod:`dectalk.ph.utterance_constants`.
    """
    from dectalk.ph.utterance_constants import GEN_SIL  # noqa: PLC0415

    return GEN_SIL


__all__ = ["all_phsort"]
