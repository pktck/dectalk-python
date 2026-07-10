# ruff: noqa: N803 -- ``phTTS`` matches the C source's handle parameter name
"""Wire ARPABET front-end through the full ``phsort + phalloph`` chain.

This module is the orchestrator that replaces the
:mod:`dectalk.ph.ph_setallofeats` stop-gap merged in PR #66. Where
the stop-gap derived :data:`~dectalk.ph.dph_t.DphT.allofeats` directly
from the ARPABET stress digits and word grouping, this module drives
the **real** C-source pipeline:

1. Encode the ARPABET word groups into a DECtalk ``symbols[]`` stream
   (US allophone codes plus :data:`~dectalk.include.phoneme_codes.WBOUND` /
   :data:`~dectalk.include.phoneme_codes.S1` / :data:`~dectalk.include.phoneme_codes.S2` /
   :data:`~dectalk.include.phoneme_codes.PERIOD` / :data:`~dectalk.include.phoneme_codes.QUEST`
   markers — the format the C kernel hands to ``phsort``).
2. Call :func:`dectalk.ph.all_phsort.all_phsort` (the language-default
   PH-sort engine, US path of ``ph_sort.c`` lines 428-1712). This walks
   the symbol stream emitting :data:`~dectalk.ph.dph_t.DphT.phonemes`
   and :data:`~dectalk.ph.dph_t.DphT.sentstruc` — one entry per phoneme,
   with the stress / syllable-position / word-boundary feature word
   composed via :func:`dectalk.ph.make_phone.add_feature`.
3. Call :func:`dectalk.ph.us_phalloph.us_phalloph` (translated from
   ``ph_aloph1.c`` lines 444-1546). Walks ``phonemes[]`` /
   ``sentstruc[]`` applying the ~30 US-English allophonic substitution
   rules (post-vocalic /R/, flap rule, /dh/-after-/t,d,n/, vowel
   unreduction in citation mode, hat-rise / hat-fall markers, ...) and
   appends per-phone allophone + feature words to
   :data:`~dectalk.ph.dph_t.DphT.allophons` / :data:`~dectalk.ph.dph_t.DphT.allofeats`
   via :func:`dectalk.ph.make_out_phonol.make_out_phonol`.

The end result: ``allophons[]`` and ``allofeats[]`` are populated by
the same chain the DECtalk binary uses (with the
``OLD_INTONATION_AND_TIMING`` build flag active — see
``ph_aloph.c`` line 14), enabling :func:`dectalk.ph.phinton.phinton`
downstream to see the FBOUNDARY / FSTRESS / FHAT_BEGINS bits it needs
to emit a real F0 contour.

Why the wrapper module
======================

The C kernel feeds ``phsort`` from ``symbols[]``, which is the
DECtalk-native phonetic stream (allophone + control codes interleaved
with WBOUND / S1 / PERIOD markers). The Python pipeline currently
runs on **ARPABET** (CMU-style symbols with stress digits embedded in
vowel names). Bridging the two formats is the only new work this
module does on top of the already-ported ``all_phsort`` +
``us_phalloph``.

Per the partial-port allowance in issue #69, only the US-English
control flow is implemented; UK / German / Spanish / French
extensions are deferred (the existing ``all_phsort`` body has runtime
guards that short-circuit those paths via ``lang_curr`` checks).

Tracks issue #69.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from dectalk.include.all_phon_counts import MAX_PHONES
from dectalk.include.phoneme_codes import (
    COMMA,
    EXCLAIM,
    PERIOD,
    PFUSA,
    QUEST,
    S1,
    S2,
    WBOUND,
    USPhoneme,
)
from dectalk.include.phoneme_stream import parse_phoneme_stream
from dectalk.ph.all_phsort import all_phsort
from dectalk.ph.inton_constants import SAFETY
from dectalk.ph.us_phalloph import us_phalloph

if TYPE_CHECKING:
    from dectalk.ph.dph_t import DphT
    from dectalk.ph.tts_handle import TtsHandle

# Maximum slots we'll allocate for the symbol stream. NPHON_MAX is the
# C kernel's upper bound on phonemes per clause; reserve enough slack
# (WBOUND between every word + S1/S2 stress markers + leading/trailing
# silence + PERIOD/QUEST) to fit any sane corpus prompt.
_SYMBOLS_RESERVE: int = 8

# Map ARPABET stress digits (CMUdict convention) to DECtalk's per-phone
# stress marker. Digit ``0`` (unstressed) emits no marker; digits ``1``
# / ``2`` emit S1 / S2 before the phone, matching how the C source's
# ``ls_*`` LTS stage writes the symbol stream (e.g. for stressed AH the
# stream is ``S1, AH``).
_STRESS_DIGIT_TO_MARKER: dict[str, int] = {
    "1": S1,  # primary
    "2": S2,  # secondary
    # digit "0" -> no marker (unstressed)
    # digit "3" reserved for tertiary stress (Spanish quote marker S3
    # in C; not emitted by the US-English ARPABET front-end).
}


def _mirror_phsort_scratch_into_allophons(p_dph_t: DphT) -> None:
    """Replay ``all_phsort``'s writes-through-the-alias into ``allophons[]``.

    In the C kernel ``phonemes`` is not a separate buffer: ``phclause``
    aliases it into the allophone scratch with an 8-slot offset
    (``pDph_t->phonemes = &(pDph_t->allophons[SAFETY])``, ph_claus.c:597),
    so every ``phonemes[i]`` cell ``all_phsort`` writes lands at
    ``allophons[SAFETY + i]``. ``us_phalloph`` then overwrites
    ``allophons[0..nallotot-1]`` as it walks, but any scratch cell at or
    past ``max(nallotot, SAFETY)`` keeps the phoneme-stream leftovers.

    That stale content is observable: ``ph_claus.c:472`` publishes
    ``parstochip[OUT_PH2] = allophons[nphone + 1]`` and its ``nphone+1 >
    nallotot`` guard does **not** exclude the ``== nallotot`` case, so
    every frame of a clause's final phone emits the one-past-end scratch
    cell in the ``OUT_PH2`` packet metadata (issues #277 / #290). On
    ``hello world`` the binary emits 7707 there — ``phonemes[3]``
    (``LL``) showing through at ``allophons[11]`` after ``phinton``'s
    dummy-schwa insert grows ``nallotot`` past ``us_phalloph``'s last
    write.

    The Python port runs ``all_phsort`` against an independent
    ``phonemes`` list (see the reallocation note in the callers), so the
    alias writes must be replayed explicitly: copy the **entire** final
    ``phonemes`` buffer — including cells past ``nphonetot``, which hold
    the same delete-shift leftovers as the C memory — into
    ``allophons[SAFETY:]`` before ``us_phalloph`` runs. The sibling C
    aliases (``sentstruc``/``allofeats``, ``user_durs``/``allodurs``,
    ``user_f0``/``f0tar``, ``user_offset``/``f0tim``) are intentionally
    NOT mirrored: no packet cell or downstream reader consumes those
    arrays past ``nallotot`` / ``nf0tot``, so mirroring them would add
    blast radius on verified files with no observable effect.
    """
    allophons = p_dph_t.allophons
    phonemes = p_dph_t.phonemes
    if phonemes is None:
        # Both callers reallocate the buffer before all_phsort runs, so
        # this only guards direct/partial-pipeline callers that never
        # produced a phoneme stream — nothing to replay.
        return
    span = min(len(phonemes), len(allophons) - SAFETY)
    allophons[SAFETY : SAFETY + span] = phonemes[:span]


def _promote_sole_secondary_stress(arpabet_words: list[list[str]]) -> list[list[str]]:
    """Promote a word's secondary stress to primary when it has no primary.

    Issue #224. The bundled lexicon is CMUdict-derived; CMUdict marks the
    main-stressed syllable of a sizeable set of words with the **secondary**
    stress digit ``2`` and no primary ``1`` at all — e.g. ``quick`` =
    ``K W IH2 K``, ``brown`` = ``B R AW2 N``, ``red`` = ``R EH2 D``,
    ``about`` = ``AH0 B AW2 T``, ``between`` = ``B AH0 T W IY2 N``. The
    C front-end instead runs the DECtalk source dictionary ``dtalk_us.dic``,
    which marks the strongest syllable of every such word as **primary**,
    backed by ``ph_sort.c``'s invariant that "any phrase must have one
    primary stress" (revision 0011, line 48; the ``find_syll_to_stress``
    fallback at lines 1286-1293 promotes the most-recent ``S2`` to ``S1``
    when a breath group reaches its terminator with zero primaries).

    Direct C-oracle dumps of ``allofeats[]`` confirm the effect: ``quick``,
    ``brown``, ``red``, ``about``, ``between``, ``black`` all carry exactly
    one ``FSTRESS_1`` and **no** ``FSTRESS_2`` in the stream the C engine
    hands to ``phinton``. Emitting ``S2`` instead leaves ``phinton`` Rule 2
    firing the weaker secondary-stress impulse (male target 61 dHz vs the
    primary's 81 dHz; ``_US_F0_*STRESS_LEVEL`` in :mod:`dectalk.ph.phinton`)
    and never tripping Rule 1's hat rise on these syllables — flattening the
    F0 contour (issue #224, couples with #220).

    The transform is intentionally narrow and mirrors ``dtalk_us.dic`` /
    ``ph_sort.c`` rather than reclassifying stress wholesale:

    * It fires **only** for words that carry at least one ``2``-stressed
      phone and **no** ``1``-stressed phone. Words with an existing primary
      (``computer`` = ``... UW1 ...``, ``present`` = ``... EH1 ...``,
      ``baseball`` = ``EY1 ... AO2 ...``) are left untouched, so genuine
      secondary stresses that coexist with a primary keep their ``S2``.
    * Every ``2`` in such a word becomes ``1``. Across the full bundled
      US lexicon (13.8 K entries) only 104 words match the gate, and **none**
      of them carry more than one ``2``, so each promoted word ends up with
      exactly one primary stress — no over-promotion.

    Returns a new word list; input groups are not mutated in place.
    """
    promoted: list[list[str]] = []
    for word in arpabet_words:
        digits = {name[-1] for name in word if name and name[-1].isdigit()}
        if "2" in digits and "1" not in digits:
            promoted.append(
                [f"{name[:-1]}1" if name and name[-1] == "2" else name for name in word]
            )
        else:
            promoted.append(list(word))
    return promoted


def _arpabet_to_us_offset(name: str) -> int | None:
    """Map an ARPABET symbol to the US allophone enum offset (0-70).

    Strips any trailing CMU stress digit (``"AH1"`` -> ``"AH"``),
    upper-cases, then looks up in :class:`~dectalk.include.phoneme_codes.USPhoneme`.
    Returns ``None`` when the symbol has no DECtalk allophone
    counterpart (e.g. CMU symbols only present under their alias name
    — those are handled upstream by ``_speak_via_python_full``'s
    ``_ARPABET_ALIAS`` table).
    """
    if not name:
        return None
    bare = name.rstrip("0123456789").upper()
    # Pause marker emitted by the kernel tokenizer for punct tokens.
    if bare == "SIL":
        return int(USPhoneme.SIL)
    try:
        return int(USPhoneme[bare])
    except KeyError:
        return None


# Aliases for ARPABET symbols that don't share their bare name with
# the DECtalk allophone enum. Kept in sync with
# ``dectalk.api.speak._ARPABET_ALIAS`` — the two tables resolve the
# same set of CMU-39 ARPABET symbols.
_ARPABET_ALIAS_OFFSET: dict[str, int] = {
    "HH": int(USPhoneme.HX),  # /h/ → DECtalk HX
    "L": int(USPhoneme.LL),  # /l/ → DECtalk LL (light L)
    "NG": int(USPhoneme.NX),  # /ŋ/ → DECtalk NX
    # ARPABET ``ER`` (rhotacized vowel "bird") is **always** DECtalk
    # ``RR`` (syllabic R) in the source US dictionary — every "bird"
    # / "world" / "her" / "fir" entry in
    # ``${DECTALK_SRC}/src/dapi/src/dic/Dic_us.txt`` uses ``R``
    # (= US_RR), never ``K`` (= US_ER). Mapping to USPhoneme.ER instead
    # leaves us with the wrong allophone whose duration / formant
    # tables don't match the C reference, and downstream phsort treats
    # the two as distinct phones for cluster / boundary purposes.
    # Stress digits 0 / 1 / 2 are all collapsed to RR; the per-phone
    # stress marker (S1 / S2) is still emitted from the digit (issue
    # #156 / parity re-audit §2).
    "ER": int(USPhoneme.RR),  # /ɝ/ "bird" → syllabic R
}


# Stress-sensitive aliases for CMU ARPABET vowels whose mapping changes
# under stress digit ``0`` (unstressed). The C dictionary represents
# these reduced-vowel slots with explicit schwa allophones (``x`` =
# US_AX, ``|`` = US_IX) rather than the unreduced AH / IH forms; e.g.
# ``hello`` is ``hxl'o`` (HX-AX-LL-OW) in
# ``${DECTALK_SRC}/src/dapi/src/dic/Dic_us.txt``, not ``hHl'o``. Issue
# #156 (parity re-audit §2).
_ARPABET_UNSTRESSED_ALIAS_OFFSET: dict[str, int] = {
    "AH0": int(USPhoneme.AX),  # CMU unstressed AH → DECtalk schwa AX
    "IH0": int(USPhoneme.IX),  # CMU unstressed IH → DECtalk schwa-front IX
}


def _resolve_arpabet_offset(name: str) -> int | None:
    """Resolve an ARPABET symbol to its US allophone offset, with alias fallback.

    Resolution order:

    1. Exact (stress-digit-included) match in the unstressed-vowel
       alias table — maps CMU ``AH0`` / ``IH0`` to their DECtalk
       reduced-vowel counterparts (AX / IX) per the source US
       dictionary's ``x`` / ``|`` characters.
    2. Bare-name alias (``HH`` → ``HX``, ``L`` → ``LL``, ``NG`` →
       ``NX``, ``ER`` → ``RR``).
    3. Bare-name lookup in the :class:`~dectalk.include.phoneme_codes.USPhoneme`
       enum.
    """
    if not name:
        return None
    upper_name = name.upper()
    if upper_name in _ARPABET_UNSTRESSED_ALIAS_OFFSET:
        return _ARPABET_UNSTRESSED_ALIAS_OFFSET[upper_name]
    bare = name.rstrip("0123456789").upper()
    if bare in _ARPABET_ALIAS_OFFSET:
        return _ARPABET_ALIAS_OFFSET[bare]
    return _arpabet_to_us_offset(name)


def _arpabet_words_to_symbols(
    arpabet_words: list[list[str]],
    *,
    is_sentence_final: bool = True,
    is_question: bool = False,
    is_exclamation: bool = False,
) -> tuple[list[int], int]:
    """Convert ARPABET word groups to a DECtalk ``symbols[]`` stream.

    The C kernel's ``phsort`` expects its input in
    ``pDph_t->symbols[]`` — a packed array of either:

    - **Phoneme codes**: ``(font << 8) | offset`` where ``font = PFUSA``
      (= 0x1E) for US English and ``offset`` is the 0-70
      :class:`~dectalk.include.phoneme_codes.USPhoneme` index.
    - **Control markers**: ``S1`` / ``S2`` / ``WBOUND`` / ``PERIOD`` /
      ``QUEST`` / ``EXCLAIM`` — single-byte values >= 100 (above
      :data:`~dectalk.include.all_phon_counts.MAX_PHONES`), used by
      ``all_phsort``'s ``curr_in_sym < MAX_PHONES`` dispatch.

    The Python front-end (``_tokens_to_phoneme_words``) already emits
    per-word ARPABET groups. This helper:

    1. Inserts a leading ``WBOUND`` (matching ``all_phsort``'s
       defensive insert at C lines 493-495).
    2. For each word, emits the per-phoneme ``S1`` / ``S2`` stress
       marker (from the ARPABET stress digit) followed by the
       allophone code with the US font shifted into the high byte.
    3. Emits a ``WBOUND`` between adjacent words (but not after the
       last word, where the sentence-end marker goes instead).
    4. Closes with ``PERIOD`` (declarative), ``QUEST`` (yes/no
       question), or ``EXCLAIM`` (exclamation) per the caller's flags.
       ``EXCLAIM`` triggers ``all_phsort``'s ``raise_last_stress`` —
       promoting the last ``S1`` marker to ``SEMPH`` (= ``FEMPHASIS``)
       so ``us_phtiming`` Rule 8 adds +60 ms per emphasised syllable
       (issue #212).

    Args:
        arpabet_words: ARPABET word groups in clause order. Pause
            tokens emitted as ``["SIL"]`` are passed through as
            standalone silence words — ``all_phsort`` handles them as
            ordinary phonemes.
        is_sentence_final: ``True`` if the clause ends a complete
            sentence — emits a trailing ``PERIOD``. ``False`` is for
            mid-sentence clauses (the caller wires the appropriate
            marker separately if needed).
        is_question: ``True`` if the sentence ends in ``?`` — emits
            ``QUEST`` instead of ``PERIOD``. Mutually exclusive with
            ``is_sentence_final == False``.
        is_exclamation: ``True`` if the sentence ends in ``!`` —
            emits ``EXCLAIM`` instead of ``PERIOD``. ``EXCLAIM`` and
            ``QUEST`` are mutually exclusive; ``QUEST`` takes
            precedence if both are set.

    Returns:
        ``(symbols, nsymbtot)`` — the populated stream and its
        length. ``nsymbtot`` is what the caller writes onto
        :data:`~dectalk.ph.dph_t.DphT.nsymbtot` before calling
        :func:`all_phsort`.
    """
    # Promote a word's sole secondary stress to primary when it carries no
    # primary at all — mirrors ``dtalk_us.dic`` / ``ph_sort.c``'s "every
    # phrase must have one primary stress" so content words the CMUdict-
    # derived lexicon marks ``S2`` (quick, brown, red, about, between, ...)
    # emit ``S1`` like the C engine, restoring phinton's stronger stress
    # impulse + hat rise (issue #224).
    arpabet_words = _promote_sole_secondary_stress(arpabet_words)

    symbols: list[int] = []
    # Leading GEN_SIL phoneme: ``ph_task.c`` lines 437-439 seed
    # ``symbols[0] = GEN_SIL`` before the LTS layer appends words.
    # ``phsort``'s output_pass walks this in the FSYLL/FNON-FSYLL
    # branch and emits a leading silence phone via :func:`make_phone`,
    # which downstream ``us_phalloph`` re-emits as ``allophons[0] =
    # GEN_SIL``. The C reference WAV for ``hello world`` has 213
    # samples (~3 Klatt frames) of zeros before the first voiced
    # sample; that prefix comes from this leading-SIL phone's
    # duration. PR #137 / issue #139 attempted to drop this prepend
    # on the theory that the C kernel only seeds ``symbols[0] =
    # GEN_SIL`` at task init (once per process) and the per-clause
    # flow should NOT re-emit it. In practice that drop collapsed
    # the 213-sample prefix to 2 samples (first-nonzero index
    # regression measured against the C oracle); the C binary
    # clearly emits a leading-SIL phone per clause when invoked via
    # ``say -a``. Restoring the prepend brings the prefix back into
    # alignment with C (issue #200). The wrong-defaults observed in
    # #137's audit (T0=500 etc.) are a separate per-allophone
    # initialisation gap and don't justify dropping the SIL phone
    # itself.
    symbols.append((PFUSA << 8) | int(USPhoneme.SIL))
    # Leading WBOUND: ``all_phsort`` defensively inserts this when
    # absent (C lines 493-495), but emitting it ourselves keeps the
    # cleanup pass quiet.
    symbols.append(WBOUND)

    last_word_idx = len(arpabet_words) - 1
    for word_idx, word in enumerate(arpabet_words):
        emitted_any = False
        for name in word:
            offset = _resolve_arpabet_offset(name)
            if offset is None:
                # ARPABET symbol that doesn't map to a DECtalk
                # allophone — skip rather than emit garbage. Mirrors
                # the ARPABET-alias-gap behaviour from the existing
                # _speak_via_python_full path.
                continue
            # Emit a stress marker (S1 / S2) before the phone if the
            # ARPABET symbol carries a trailing digit. DECtalk's
            # symbols[] holds stress as a separate marker token; the
            # ``add_feature(p_dph_t, FSTRESS_*, nphonetot)`` call in
            # ``all_phsort`` (lines 1413-1418) attaches it to the
            # NEXT-emitted phone.
            digit = name[-1] if name and name[-1].isdigit() else ""
            marker = _STRESS_DIGIT_TO_MARKER.get(digit)
            if marker is not None:
                symbols.append(marker)
            symbols.append((PFUSA << 8) | offset)
            emitted_any = True
        # Insert a WBOUND between adjacent words (but not after the
        # last word — the sentence-end marker goes there).
        if emitted_any and word_idx < last_word_idx:
            symbols.append(WBOUND)

    # Sentence-end marker. WBOUND-before-PERIOD is redundant per
    # ``all_phsort``'s cleanup pass (C lines 599-603 collapse it), so
    # emit just the boundary marker. ``EXCLAIM`` is the C-source
    # ``EXCLAIM`` token (phoneme_codes.EXCLAIM); when emitted,
    # ``all_phsort`` (lines 1311-1314 of ``ph_sort.c``) calls
    # ``raise_last_stress`` to promote the last ``S1`` to ``SEMPH``
    # (which the output_pass then translates into a ``FEMPHASIS``
    # feature bit), driving ``us_phtiming`` Rule 8's +60 ms per
    # emphasised syllable (issue #212).
    if is_sentence_final:
        if is_question:
            symbols.append(QUEST)
        elif is_exclamation:
            symbols.append(EXCLAIM)
        else:
            symbols.append(PERIOD)

    return symbols, len(symbols)


def phalloph2(
    phTTS: TtsHandle,
    arpabet_words: list[list[str]],
    *,
    is_sentence_final: bool = True,
    is_question: bool = False,
    is_exclamation: bool = False,
) -> None:
    """Drive the full ``phsort + phalloph`` chain from ARPABET word groups.

    Replacement for the stop-gap :func:`dectalk.ph.ph_setallofeats.ph_setallofeats`
    helper merged in PR #66. Where the stop-gap only populated
    :data:`~dectalk.ph.dph_t.DphT.allofeats` with a minimum FSTRESS /
    FWBNEXT / FPERNEXT bit pattern, this function runs the **real**
    PH-stage chain (translated from ``ph_sort.c`` + ``ph_aloph1.c``),
    which:

    - Emits every phoneme's full feature word (FSTRESS_1 / FSTRESS_2 /
      FWINITC / FTYPESYL / FBOUNDARY / FSENTENDS / FHAT_BEGINS /
      FHAT_ENDS / FBLOCK / FEMPHASIS).
    - Applies the US-English allophonic substitution rules to
      :data:`~dectalk.ph.dph_t.DphT.allophons` (postvocalic R collapse,
      flap rule, citation-mode unreduce, etc.).
    - Writes through to :data:`~dectalk.ph.dph_t.DphT.nallotot` so
      downstream :func:`dectalk.ph.phinton.phinton` and
      :func:`dectalk.ph.us_phtiming.us_phtiming` see the proper phone
      count.

    The caller is expected to have:

    1. Run :func:`dectalk.ph.init_phclause.init_phclause` so the per-
       clause arrays exist and are zero-initialised.
    2. Allocated separate :data:`~dectalk.ph.dph_t.DphT.symbols` /
       :data:`~dectalk.ph.dph_t.DphT.phonemes` /
       :data:`~dectalk.ph.dph_t.DphT.sentstruc` /
       :data:`~dectalk.ph.dph_t.DphT.user_durs` /
       :data:`~dectalk.ph.dph_t.DphT.user_f0` buffers — the Python
       port's ``init_phclause`` aliases ``phonemes`` to ``allophons``,
       which would cause ``us_phalloph`` to read and overwrite the
       same slot. This function reallocates them as independent
       arrays before calling the chain.
    3. Set :data:`~dectalk.ph.dph_t.DphT.pSTphsettar` (the
       ``DphSettarSt`` state needed by ``all_phsort``'s delete /
       insert helpers).
    4. Set :data:`~dectalk.kernel.ksd_t.KsdT.lang_curr` to
       :data:`~dectalk.kernel.lang_codes.LANG_english`.

    Args:
        phTTS: TTS handle with ``p_ph_thread_data`` (DphT) and
            ``p_kernel_share_data`` (KsdT) populated.
        arpabet_words: Per-word ARPABET symbol groups in clause order
            (from ``_tokens_to_phoneme_words``). Each group is a list
            of CMU-style ARPABET symbols with embedded stress digits.
        is_sentence_final: ``True`` (default) emits a trailing
            ``PERIOD`` / ``QUEST`` marker so ``phsort`` attaches
            FSENTENDS to the final stressed vowel and ``phinton``'s
            Rule 4 (final fall) fires.
        is_question: ``True`` if the sentence ends in ``?``; emits
            ``QUEST`` so ``phsort`` sets ``cbsymbol = 1`` (which
            ``phinton`` reads to switch to question-final rising
            intonation).
        is_exclamation: ``True`` if the sentence ends in ``!``;
            emits ``EXCLAIM`` instead of ``PERIOD`` so
            ``all_phsort``'s C-line-1311 hook calls
            :func:`raise_last_stress` (promotes the last ``S1``
            marker to ``SEMPH`` / ``FEMPHASIS`` and drives
            ``us_phtiming`` Rule 8's +60 ms emphasis bump per
            issue #212). ``is_question`` takes precedence if both
            flags are set.
    """
    p_dph_t = cast("DphT", phTTS.p_ph_thread_data)

    # 1. Encode ARPABET word groups into a DECtalk symbols[] stream.
    symbols, nsymbtot = _arpabet_words_to_symbols(
        arpabet_words,
        is_sentence_final=is_sentence_final,
        is_question=is_question,
        is_exclamation=is_exclamation,
    )

    # 2. Pad to the size the C kernel uses (NPHON_MAX + SAFETY + 2 ~
    # 256 slots). all_phsort indexes up to nsymbtot, so just need the
    # populated entries; the rest get zero padding.
    p_dph_t.symbols = list(symbols)
    p_dph_t.nsymbtot = nsymbtot

    # 3. Reallocate ``phonemes`` / ``sentstruc`` / ``user_durs`` /
    # ``user_f0`` as INDEPENDENT buffers — Python's init_phclause
    # aliases them to ``allophons`` / ``allofeats`` / ``allodurs`` /
    # ``f0tar`` which would cause us_phalloph to clobber its own
    # input as it walks the phoneme stream. The C source uses
    # ``&allophons[SAFETY]`` for ``phonemes`` (8-slot offset) so the
    # two never alias; the Python port doesn't model that offset.
    buf_size = max(nsymbtot + _SYMBOLS_RESERVE, 256)
    p_dph_t.phonemes = [0] * buf_size
    p_dph_t.sentstruc = [0] * buf_size
    p_dph_t.user_durs = [0] * buf_size
    p_dph_t.user_f0 = [0] * buf_size

    # 4. Run the PH-sort engine. Walks symbols[] cleanup-pass then
    # output-pass, writing phonemes[] / sentstruc[] / user_durs[] /
    # user_f0[]. Sets nphonetot to the count emitted.
    all_phsort(phTTS)

    # 4b. Replay the C's phonemes->allophons aliasing (ph_claus.c:597)
    # so scratch cells past us_phalloph's writes carry the same
    # phoneme-stream leftovers the binary's shared memory does — the
    # OUT_PH2 one-past-end packet cell reads them (#277 / #290).
    _mirror_phsort_scratch_into_allophons(p_dph_t)

    # 5. Run the allophonic-substitution pass. Walks phonemes[] /
    # sentstruc[] applying the US-English rules; writes allophons[]
    # and allofeats[] with the per-phone allophone + feature word,
    # setting nallotot.
    us_phalloph(phTTS)


# Clause/sentence terminators that already close a DECtalk symbol stream;
# when the byte-exact stream ends in one of these, no implicit PERIOD is
# appended (mirrors the C kernel, where a trailing ``.`` / ``?`` / ``!`` /
# ``,`` already terminates the clause).
_CLAUSE_TERMINATORS: frozenset[int] = frozenset({COMMA, PERIOD, QUEST, EXCLAIM})


def _dectalk_stream_to_symbols(
    raw: bytes,
    *,
    default_terminator: int = PERIOD,
) -> tuple[list[int], int]:
    """Convert a byte-exact DECtalk ASCII phoneme stream to a ``symbols[]`` array.

    ``raw`` is the output of
    :func:`dectalk.api.speak.text_to_dectalk_phonemes` — byte-identical to
    the C library's ``convert_to_phonemes``. :func:`parse_phoneme_stream`
    decodes its fixed-width 2-byte slots into the numeric phoneme / control
    codes the C kernel's LTS stage hands to ``phsort``; this helper then
    assembles them into the packed ``symbols[]`` stream
    :func:`all_phsort` consumes:

    1. A leading ``GEN_SIL`` phone + ``WBOUND`` — the per-clause
       ``ph_task.c`` lines 437-439 bootstrap (``symbols[0] = GEN_SIL``)
       that supplies the ~213-sample leading silence; mirrors
       :func:`_arpabet_words_to_symbols`.
    2. Each allophone code (``< MAX_PHONES``) shifted into the US font
       (``(PFUSA << 8) | code``) so ``make_phone`` recovers the font from
       the high byte; control codes (``>= MAX_PHONES``: ``S1`` / ``S2`` /
       ``WBOUND`` / ``MBOUND`` / ``SBOUND`` / ``PPSTART`` / ``VPSTART`` /
       ``RELSTART`` / ``COMMA`` / ``PERIOD`` / ``QUEST`` / ``EXCLAIM`` /
       ``SPECIALWORD`` / …) pass through unchanged — ``all_phsort``
       dispatches on them directly.
    3. A trailing ``default_terminator`` (``PERIOD`` by default) when the
       stream does not already end in a clause/sentence marker — the
       implicit end-of-text period the C kernel applies to unpunctuated
       input.

    Unlike :func:`_arpabet_words_to_symbols`, the punctuation / phrase
    markers (``COMMA`` / ``PERIOD`` / ``VPSTART`` / ``MBOUND`` / …) are
    already present in ``raw`` and flow straight through, so
    ``all_phsort`` generates the internal ``GEN_SIL`` phones and sets the
    ``FSENTENDS`` / clause-boundary features natively — no caller-side
    boundary-feature fix-up is needed.

    Returns:
        ``(symbols, nsymbtot)`` — the populated stream and its length.
    """
    tokens = parse_phoneme_stream(raw)
    symbols: list[int] = [(PFUSA << 8) | int(USPhoneme.SIL), WBOUND]
    for tok in tokens:
        if tok.code < MAX_PHONES:
            symbols.append((PFUSA << 8) | tok.code)
        else:
            symbols.append(tok.code)
    if symbols[-1] not in _CLAUSE_TERMINATORS:
        symbols.append(default_terminator)
    return symbols, len(symbols)


def split_dectalk_stream_clauses(
    raw: bytes,
    *,
    default_terminator: int = PERIOD,
) -> list[tuple[list[int], int]]:
    """Split a DECtalk ASCII stream into per-clause ``symbols[]`` arrays.

    Mirrors the C ``ph_task.c`` ``kltask`` loop, which buffers incoming
    symbols and calls ``speak_now`` -> ``phclause`` **per clause
    delimiter** (``isdelim(ph)`` = ``COMMA``..``EXCLAIM``, ph_defs.h
    line 781) rather than once per utterance. After each clause the
    buffer resets to a leading ``GEN_SIL`` (``symbols[0] = GEN_SIL;
    nsymbtot = 1`` — ph_task.c lines 1126-1129), so every clause gets
    its own clause-initial silence phone — and, critically, its own
    **clause-local** ``nallotot``: ``us_phtiming``'s short-phrase rules
    (Rule 2's ``nallotot < 10`` vowel bonus, Rule 17's ``prcnt += 30``)
    and the rhythm-pass state see per-clause counts exactly as the C
    engine does. Driving the whole multi-clause utterance through one
    merged clause walk left every content phone systematically short —
    the ``multi_clause`` |Δ|med = 1633-sample shortfall in the 500-prompt
    FULL+VTM1 measurement (issue #270).

    The final fragment (no trailing delimiter in the stream) is closed
    with ``default_terminator``, matching the C flush path
    (``ph_task.c`` line 738: ``symbols[nsymbtot] = PERIOD; speak_now``)
    which also only fires when the buffer holds real content
    (``nsymbtot > 1``).

    Returns:
        List of ``(symbols, nsymbtot)`` pairs, one per clause, each in
        the same shape :func:`_dectalk_stream_to_symbols` produces.
    """
    tokens = parse_phoneme_stream(raw)
    sil = (PFUSA << 8) | int(USPhoneme.SIL)
    clauses: list[tuple[list[int], int]] = []
    cur: list[int] = [sil]
    for tok in tokens:
        if tok.code < MAX_PHONES:
            # C's post-clause reset is a bare ``symbols[0] = GEN_SIL``;
            # the word-boundary marker Python's single-shot decoder
            # injects models the kernel's invisible per-word marker in
            # front of the first WORD. When a clause opens with
            # explicit syntax markers instead (``^`` SBOUND / ``(``
            # PPSTART / ``)`` VPSTART, e.g. the ``^ ( aen d`` "and"
            # cluster after a comma), the C stream carries NO WBOUND
            # before them — injecting one shifts ``all_phsort``'s
            # boundary classification of the following word.
            if len(cur) == 1:
                cur.append(WBOUND)
            cur.append((PFUSA << 8) | tok.code)
        else:
            cur.append(tok.code)
        if tok.code in _CLAUSE_TERMINATORS:
            clauses.append((cur, len(cur)))
            cur = [sil]
    if len(cur) > 1:
        # Unterminated trailing fragment: close it like the C flush
        # path (implicit end-of-text PERIOD).
        cur.append(default_terminator)
        clauses.append((cur, len(cur)))
    return clauses


def phalloph2_from_dectalk(phTTS: TtsHandle, raw: bytes) -> None:
    """Drive ``phsort + phalloph`` from a byte-exact DECtalk phoneme stream.

    Byte-exact counterpart to :func:`phalloph2`. Where :func:`phalloph2`
    re-encodes per-word ARPABET groups (which routes the synth path through
    an approximate per-word lexicon/LTS lookup), this consumes the
    byte-identical stream produced by
    :func:`dectalk.api.speak.text_to_dectalk_phonemes` — the same stream
    the C library emits from ``convert_to_phonemes``. The allophone stream
    therefore inherits the faithful phonemes, letter-by-letter spell-out,
    digit-expansion prosody, vowel reductions, and punctuation / phrase
    markers instead of the divergent approximate transcription
    (issues #217 / #225 / #237 / #238).

    The caller must, exactly as for :func:`phalloph2`, have run
    :func:`dectalk.ph.init_phclause.init_phclause`, set
    :data:`~dectalk.ph.dph_t.DphT.pSTphsettar`, and set
    :data:`~dectalk.kernel.ksd_t.KsdT.lang_curr` to
    :data:`~dectalk.kernel.lang_codes.LANG_english`.

    Args:
        phTTS: TTS handle with ``p_ph_thread_data`` (DphT) and
            ``p_kernel_share_data`` (KsdT) populated.
        raw: DECtalk-native ASCII phoneme bytes (the
            ``text_to_dectalk_phonemes`` output for one clause). The
            sentence/clause terminator is read from the stream itself, so
            question / exclamation intonation needs no separate flag.
    """
    # 1. Decode the byte-exact stream into a packed symbols[] array.
    symbols, nsymbtot = _dectalk_stream_to_symbols(raw)
    phalloph2_from_symbols(phTTS, symbols, nsymbtot)


def phalloph2_from_symbols(phTTS: TtsHandle, symbols: list[int], nsymbtot: int) -> None:
    """Run the ``phsort + phalloph`` chain on one clause's ``symbols[]``.

    Body shared by :func:`phalloph2_from_dectalk` (single-shot stream)
    and the per-clause driver loop in ``dectalk.api.speak`` (which
    feeds one :func:`split_dectalk_stream_clauses` entry at a time,
    mirroring the C ``speak_now`` -> ``phclause`` per-delimiter cycle).

    The caller must have run
    :func:`dectalk.ph.init_phclause.init_phclause` beforehand — once
    per utterance suffices, matching C's ``kltask`` which zeroes the
    scratch arrays at task entry (ph_task.c line 422), not per clause.
    """
    p_dph_t = cast("DphT", phTTS.p_ph_thread_data)

    p_dph_t.symbols = list(symbols)
    p_dph_t.nsymbtot = nsymbtot

    # Reallocate phonemes[] / sentstruc[] / user_durs[] / user_f0[] as
    # INDEPENDENT buffers — Python's init_phclause aliases them to
    # allophons[] / allofeats[] / allodurs[] / f0tar[], which us_phalloph
    # would otherwise clobber as it walks the phoneme stream (see the
    # matching note in phalloph2).
    buf_size = max(nsymbtot + _SYMBOLS_RESERVE, 256)
    p_dph_t.phonemes = [0] * buf_size
    p_dph_t.sentstruc = [0] * buf_size
    p_dph_t.user_durs = [0] * buf_size
    p_dph_t.user_f0 = [0] * buf_size

    # Run the PH-sort + allophonic-substitution chain, replaying the
    # C's phonemes->allophons aliasing between the two passes so the
    # one-past-end scratch cells match the binary (see
    # :func:`_mirror_phsort_scratch_into_allophons`; #277 / #290).
    all_phsort(phTTS)
    _mirror_phsort_scratch_into_allophons(p_dph_t)
    us_phalloph(phTTS)


__all__ = [
    "phalloph2",
    "phalloph2_from_dectalk",
    "phalloph2_from_symbols",
    "split_dectalk_stream_clauses",
]
