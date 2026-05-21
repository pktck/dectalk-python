"""Derive per-allophone feature bits (``DphT.allofeats``) from ARPABET data.

In the C reference, ``allofeats[]`` is populated by ``make_out_phonol``
(inside ``phalloph2`` / ``ph_aloph2.c``) which copies the
``curr_outstruc`` feature word — itself computed by ``phsort`` /
``phsyl`` / ``phalloph`` from the per-phone ``sentstruc[]`` array —
into ``pDph_t->allofeats[nallotot]`` for each emitted allophone. The
downstream PH stages then read ``allofeats`` to drive prosody:

* ``phinton`` (``ph_inton2.c`` lines 749-873) gates Rule 1 (hat rise)
  on ``FHAT_BEGINS``, Rule 2 (stress pulse) on ``FSTRESS`` masked
  against the allophone's feature word, and Rules 3-6 (comma /
  question / period falls) on ``FBOUNDARY`` and ``FPERNEXT`` /
  ``FQUENEXT`` / ``FCBNEXT`` values.
* ``us_phtiming`` reads ``FSTRESS`` to bump duration on stressed
  vowels (lines 170-460 of ``p_us_st1.c``).

The Python pipeline currently skips ``phsort``/``phalloph`` and works
directly off the ARPABET stream produced by the LTS / dictionary
front-end. That stream still carries the two pieces of information
``phinton`` needs:

* **Stress digit** — CMUdict's ARPABET embeds stress as a trailing
  ``0`` / ``1`` / ``2`` on vowel symbols (e.g. ``"AH1"`` is primary-
  stressed schwa). That maps directly to :data:`FNOSTRESS` /
  :data:`FSTRESS_1` / :data:`FSTRESS_2`.
* **Word boundary** — the front-end tokenises the input into
  ``WORD`` tokens before LTS, so per-word ARPABET lists are
  available. Marking the last phone of each word with
  :data:`FWBNEXT` lets ``phinton``'s ``nextwrdbou`` lookahead
  (``ph_inton2.c`` line 845-861) terminate correctly.

This module ports the *behaviour* of the C ``make_out_phonol`` /
``ph_aloph2`` allofeats-emission step using the data the Python
pipeline already has. It is a minimal stop-gap until the full
``phalloph`` / ``phsort`` chain is ported; once those land,
``allofeats`` will be populated as a side-effect of running them and
this module's wiring can be removed.

See ``docs/parity-divergence-audit.md`` §"Top 3 divergence root
causes" #2 for the broader context.

Tracks issue #63.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dectalk.ph.feature_bits import (
    FBOUNDARY,
    FNOSTRESS,
    FPERNEXT,
    FSENTENDS,
    FSTRESS_1,
    FSTRESS_2,
    FWBNEXT,
)
from dectalk.ph.phoneme_features import FSYLL
from dectalk.ph.timing import phone_feature

if TYPE_CHECKING:
    from dectalk.ph.dph_t import DphT


# Mapping from ARPABET stress digit to the feature-bit constant.
# CMUdict uses three values: 0 (unstressed), 1 (primary), 2 (secondary).
# A symbol with no digit (e.g. "HH", "L") is a consonant and gets
# FNOSTRESS by default. The C source's `FEMPHASIS` (= 3) is reserved
# for the ``[+]`` user-emphasis marker and is *not* derived here.
_STRESS_FROM_DIGIT: dict[str, int] = {
    "0": FNOSTRESS,
    "1": FSTRESS_1,
    "2": FSTRESS_2,
}


def _arpabet_to_us_allophone_code(name: str) -> int | None:
    """ARPABET symbol → DECtalk US allophone code (or ``None``).

    Local copy of the mapping in :func:`dectalk.api.speak._arpabet_to_us_allophone`.
    Duplicated here so :func:`ph_setallofeats` can stay agnostic of the
    high-level API module and so pyright doesn't flag the cross-module
    private import. The mapping rule is identical: strip a trailing
    stress digit, upper-case, lookup in the US allophone enum.
    """
    from dectalk.include.phoneme_codes import PFUSA, USPhoneme  # noqa: PLC0415

    bare = name.rstrip("0123456789").upper()
    try:
        return (PFUSA << 8) | int(USPhoneme[bare])
    except KeyError:
        return None


def _stress_bits_for_arpabet(name: str) -> int:
    """Return the :data:`FSTRESS` value implied by an ARPABET symbol.

    CMUdict embeds stress as a trailing decimal digit on vowel symbols
    (``"AH0"`` / ``"AH1"`` / ``"AH2"``). Symbols with no digit
    (consonants, the silence sentinel) decode as :data:`FNOSTRESS`.

    Args:
        name: ARPABET symbol as produced by the front-end / LTS.

    Returns:
        One of :data:`FNOSTRESS`, :data:`FSTRESS_1`, :data:`FSTRESS_2`.
    """
    if not name:
        return FNOSTRESS
    last = name[-1]
    return _STRESS_FROM_DIGIT.get(last, FNOSTRESS)


def ph_setallofeats(
    p_dph_t: DphT,
    arpabet_words: list[list[str]],
    *,
    is_sentence_final: bool = True,
) -> None:
    """Populate ``p_dph_t.allofeats[]`` from the ARPABET word groups.

    The function mirrors what ``ph_aloph2.c::make_out_phonol`` does in
    the C pipeline — emit a per-allophone feature word — but derives
    the feature word from data the Python front-end already has
    (stress digits + word grouping) rather than from the
    ``sentstruc[]`` array that the unported ``phsort`` / ``phsyl``
    chain would have produced.

    The caller is expected to have:

    1. Populated ``p_dph_t.allophons`` with the allophone stream
       (leading :data:`GEN_SIL`, the per-word allophones in order,
       trailing :data:`GEN_SIL`) and set ``p_dph_t.nallotot``.
    2. Run ``init_phclause`` already, so ``allofeats`` is sized and
       zero-initialised.

    On return, ``allofeats[i]`` carries:

    * :data:`FSTRESS_1` / :data:`FSTRESS_2` / :data:`FNOSTRESS` from
      the matching ARPABET symbol's stress digit (vowels only;
      consonants get :data:`FNOSTRESS`).
    * :data:`FWBNEXT` ORed onto the last syllabic allophone of each
      non-final word, mirroring the C ``FBOUNDARY`` field that
      ``phinton``'s ``nextwrdbou`` lookahead consumes.
    * :data:`FPERNEXT` ``|`` :data:`FSENTENDS` ORed onto the last
      syllabic allophone of the final word when
      ``is_sentence_final`` is true.

    The leading and trailing :data:`GEN_SIL` sentinels keep their
    zero ``allofeats[]`` values — matching the C source, which sets
    ``allofeats[0] = 0`` (GEN_SIL) and
    ``allofeats[nallotot] = 0`` (trailing GEN_SIL) explicitly in
    ``ph_aloph2.c`` lines 1539 / 1691.

    Args:
        p_dph_t: The per-thread PH state. ``allophons``,
            ``allofeats``, and ``nallotot`` must already be set by
            :func:`init_phclause` + the caller's allophone copy.
        arpabet_words: Per-word ARPABET symbol groups in clause
            order. Words that produced zero recognised allophones
            (e.g. punctuation tokens) should be omitted by the
            caller; the index into ``allofeats`` is recovered by
            walking ``arpabet_words`` and skipping symbols whose
            allophone mapping returned ``None``.
        is_sentence_final: ``True`` if the clause ends a sentence
            (period / question / exclamation). When ``True``, the
            last syllabic allophone of the final word is marked with
            :data:`FPERNEXT` ``|`` :data:`FSENTENDS` so ``phinton``'s
            Rule 4 (final fall) fires. Pass ``False`` for
            mid-sentence clauses ending in a comma; the caller
            should then mark the appropriate phone with
            :data:`FCBNEXT` separately if needed.

    Notes:
        This is a feature-derivation helper, not a faithful port of
        any single C function. The closest C equivalents are
        ``make_out_phonol`` (which writes the feature word) and the
        ``phsort`` / ``phsyl`` chain (which computes it). Issue #63
        tracks the full port; this helper unblocks ``phinton`` in
        the meantime so the pure-Python pipeline produces audible
        pitch contour.
    """
    # Walk the ARPABET stream alongside the populated allophons array
    # to discover which allofeats[] index each ARPABET symbol lives
    # at. ``allophons[0]`` is the leading SIL; per-word allophones
    # begin at index 1. Symbols whose ARPABET→USPhoneme lookup
    # returned None (HH, L, NG with the current alias gap of issue
    # #61) are skipped here too: the resulting allophone wasn't
    # appended, so there's no allofeats[] slot to set.
    allo_index = 1  # skip leading GEN_SIL at allophons[0]
    word_count = len(arpabet_words)
    for word_idx, word in enumerate(arpabet_words):
        # Track the last syllabic-allophone index emitted by this
        # word; FWBNEXT / FPERNEXT attach to that slot. Defaults to
        # -1 if the word produced no syllabic allophones (rare:
        # consonant-only words like a clipped "shh"); in that case
        # the word boundary marker falls onto the last emitted
        # allophone regardless of FSYLL.
        last_syllabic_idx = -1
        last_emitted_idx = -1
        for name in word:
            allo_code = _arpabet_to_us_allophone_code(name)
            if allo_code is None:
                # ARPABET symbol the alias gap dropped (issue #61).
                # Nothing was appended to allophons[]; skip without
                # advancing allo_index.
                continue
            if allo_index >= p_dph_t.nallotot - 1:
                # Defensive: ran past the populated allophons array.
                # Should not happen if the caller wired allophons /
                # nallotot consistently, but bail rather than
                # write out of bounds.
                break

            # Apply stress bits derived from the ARPABET stress
            # digit. OR into whatever init_phclause / the caller
            # already wrote (typically zero).
            stress = _stress_bits_for_arpabet(name)
            p_dph_t.allofeats[allo_index] |= stress

            last_emitted_idx = allo_index
            # FSYLL distinguishes vowels from consonants in the
            # us_featb LUT; the C source attaches FBOUNDARY only to
            # the last vowel of a word ("the syllable nucleus") so
            # phinton's nextsylbou lookahead resolves correctly.
            if phone_feature(p_dph_t.allophons[allo_index]) & FSYLL:
                last_syllabic_idx = allo_index
            allo_index += 1

        # Attach the word-boundary marker. Prefer the last syllabic
        # allophone; fall back to the last emitted allophone for
        # consonant-only words.
        boundary_idx = last_syllabic_idx if last_syllabic_idx >= 0 else last_emitted_idx
        if boundary_idx < 0:
            continue

        is_last_word = word_idx == word_count - 1
        if is_last_word and is_sentence_final:
            # Sentence-final word: mark with FPERNEXT | FSENTENDS so
            # phinton's Rule 4 (final fall, ph_inton2.c lines
            # 1505-1518) fires. FSENTENDS shares the FPERNEXT bit
            # value (both = 0o400); the C source ORs them together
            # at the marking site and tests either one downstream.
            # Clear any prior FBOUNDARY bits first since FBOUNDARY
            # is a 4-bit field, not a flag.
            p_dph_t.allofeats[boundary_idx] &= ~FBOUNDARY
            p_dph_t.allofeats[boundary_idx] |= FPERNEXT | FSENTENDS
        elif not is_last_word:
            # Mid-clause word: just a word boundary so phinton's
            # nextwrdbou lookahead resolves to FWBNEXT.
            p_dph_t.allofeats[boundary_idx] &= ~FBOUNDARY
            p_dph_t.allofeats[boundary_idx] |= FWBNEXT


__all__ = ["ph_setallofeats"]
