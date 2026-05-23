"""Form-class homograph disambiguation.

Per LTS audit (PR #123 §2, issue #144): the C runtime selects between
the ``P`` and ``S`` dictionary entries of a noun/verb minimal pair
(``record``, ``present``, ``object``, ...) using the surrounding
words' part-of-speech bits and the 27 rules in ``ls_homo.h``.

This module is a focused port of ``ls_homo_homo`` from
``src/dapi/src/lts/ls_homo.c`` covering the homograph disambiguation
case the audit identified — noun/verb stress-shift pairs in the 2002
US dictionary. The implementation reuses the verbatim
:data:`dectalk.lts.homo_table.homo_table` rules and threads them
against a small POS lexicon (:data:`_CONTEXT_FC`) that tags the
common function-word neighbours (articles, pronouns, ``to``,
auxiliaries, etc.) seen in the audit corpus.

The data table :data:`HOMOGRAPH_FC_BITS` records, for every
homograph word with both ``P`` and ``S`` entries in
``Dic_us_2002.txt``, the FC bitmask (``FC_NOUN | FC_VERB | FC_ADJ``)
each entry carries. This is the part the bundled
``lexicon_us_full.txt`` *does not* preserve — the build script
collapses the FC-bits column away. Embedding the bits here lets
the disambiguator answer "is the P entry the noun reading?" without
re-parsing the source dictionary at runtime.

References:
- ``src/dapi/src/lts/ls_homo.c`` — :func:`ls_homo_homo` selection logic.
- ``src/dapi/src/lts/ls_homo.h`` — the 27-rule context/select/elim table
  (already translated as :mod:`dectalk.lts.homo_table`).
- ``src/dapi/src/include/fc_def.tab`` — the FC_* bit definitions
  (already translated as :mod:`dectalk.dic.form_class_bits`).
"""

from __future__ import annotations

from typing import Final

from dectalk.dic.form_class_bits import (
    FC_ADJ,
    FC_ADV,
    FC_ART,
    FC_AUX,
    FC_BE,
    FC_BEV,
    FC_CONJ,
    FC_HAVE,
    FC_NOUN,
    FC_POS,
    FC_PREP,
    FC_PRON,
    FC_TO,
    FC_VERB,
    FC_WHOW,
)
from dectalk.lts.homo_table import homo_table

# -- Per-homograph FC bits (collapsed N|V|A roles from Dic_us_2002.txt) ----
#
# Values are ``(p_mask, s_mask)`` where each mask is a small bitfield:
#   bit 0 = noun, bit 1 = verb, bit 2 = adjective.
# Built by inspecting column 4 of every ``word,P,...`` / ``word,S,...``
# row in ``Dic_us_2002.txt`` (the 29-bit form-class column from the
# DECtalk source). Only the N/V/A bits are retained — they're all the
# disambiguator needs for the noun/verb/adj selection.
#
# These three masks correspond to the bits the ``homo_table`` rules
# select against: ``h_select`` / ``h_elim`` are typically ``FC_NOUN``
# (0x400) or ``FC_VERB`` (0x20000) or ``FC_ADJ`` (0x01). The compact
# encoding keeps the table inline and audit-friendly.
_ROLE_NOUN: Final[int] = 1
_ROLE_VERB: Final[int] = 2
_ROLE_ADJ: Final[int] = 4

# Expand a compact role-mask into the full FC_* bitfield the
# homo_table rules consume.
_ROLE_TO_FC: Final[dict[int, int]] = {
    _ROLE_NOUN: FC_NOUN,
    _ROLE_VERB: FC_VERB,
    _ROLE_ADJ: FC_ADJ,
}


def _expand_role_mask(mask: int) -> int:
    """Convert a compact (N|V|A) role mask to the full FC bitfield."""
    out = 0
    for compact, fc_bit in _ROLE_TO_FC.items():
        if mask & compact:
            out |= fc_bit
    return out


# Mapping from upper-cased word → (P_role_mask, S_role_mask). Generated
# from ``Dic_us_2002.txt`` by extracting the FC_NOUN/FC_VERB/FC_ADJ bits
# of every word that ships both a ``,P,`` and a ``,S,`` row.
#
# Used by :func:`disambiguate` to answer "does the P entry of WORD
# carry the FC mask the current homo_table rule wants to select?".
HOMOGRAPH_FC_BITS: Final[dict[str, tuple[int, int]]] = {
    "ABSTRACT": (5, 2),
    "ABUSE": (2, 1),
    "ADDICT": (2, 1),
    "ADVOCATE": (2, 1),
    "AFFIX": (1, 2),
    "ALLY": (1, 2),
    "ALTERNATE": (4, 2),
    "ANIMATE": (2, 4),
    "ANNEX": (1, 2),
    "APPROPRIATE": (4, 2),
    "ARITHMETIC": (1, 4),
    "ARTICULATE": (2, 4),
    "ASSOCIATE": (2, 1),
    "ATTRIBUTE": (2, 1),
    "AUGUST": (1, 4),
    "BASS": (4, 1),
    "BATON": (1, 1),
    "BOW": (1, 2),
    "CLOSE": (2, 5),
    "COMBAT": (2, 5),
    "COMBINE": (2, 3),
    "COMPACT": (6, 1),
    "COMPLEX": (1, 4),
    "COMPOUND": (5, 2),
    "COMPRESS": (2, 1),
    "CONCERT": (1, 2),
    "CONDUCT": (2, 1),
    "CONFEDERATE": (5, 2),
    "CONFINE": (2, 1),
    "CONFLICT": (1, 2),
    "CONGLOMERATE": (1, 2),
    "CONSOLE": (1, 2),
    "CONSTRUCT": (2, 1),
    "CONTENT": (1, 4),
    "CONTEST": (1, 2),
    "CONTRACT": (1, 2),
    "CONTRAST": (1, 2),
    "CONVERSE": (1, 7),
    "CONVERT": (2, 1),
    "CONVICT": (2, 1),
    "COORDINATE": (2, 5),
    "DECREASE": (3, 0),
    "DEFECT": (2, 1),
    "DELEGATE": (1, 2),
    "DELIBERATE": (4, 2),
    "DESERT": (5, 3),
    "DESOLATE": (4, 2),
    "DIFFUSE": (4, 2),
    "DIGEST": (1, 2),
    "DISCHARGE": (2, 1),
    "DISCOUNT": (1, 2),
    "DOVE": (0, 1),
    "DUPLICATE": (2, 5),
    "EGRESS": (1, 2),
    "ELABORATE": (4, 2),
    "ESTIMATE": (2, 1),
    "EXCERPT": (1, 2),
    "EXCUSE": (2, 1),
    "EXPATRIATE": (1, 2),
    "EXPLOIT": (2, 1),
    "EXPORT": (2, 1),
    "EXTRACT": (2, 1),
    "FERMENT": (2, 1),
    "FREQUENT": (6, 2),
    "GEMINATE": (4, 2),
    "GRADUATE": (2, 5),
    "GUESSTIMATE": (2, 1),
    "IMPACT": (1, 2),
    "IMPLANT": (2, 1),
    "IMPORT": (1, 2),
    "IMPRINT": (1, 2),
    "INCENSE": (2, 1),
    "INCLINE": (2, 1),
    "INCREASE": (2, 1),
    "INSERT": (2, 1),
    "INSULT": (2, 1),
    "INTERCHANGE": (1, 2),
    "INTIMATE": (5, 2),
    "INVALID": (4, 1),
    "JUST": (4, 0),
    "LEAD": (7, 3),
    "LIVE": (2, 5),
    "MINUTE": (1, 4),
    "MISCOUNT": (1, 2),
    "MISPRINT": (1, 2),
    "MISUSE": (2, 1),
    "MODERATE": (4, 2),
    "OBJECT": (1, 2),
    "OVERRUN": (1, 2),
    "PERFECT": (4, 2),
    "PERMIT": (2, 1),
    "PERVERT": (2, 1),
    "POLISH": (3, 5),
    "POSTULATE": (2, 1),
    "PREDICATE": (1, 2),
    "PREDOMINATE": (2, 4),
    "PRESENT": (2, 1),
    "PROCEED": (2, 0),
    "PROCEEDS": (0, 1),
    "PRODUCE": (2, 1),
    "PROGRESS": (1, 2),
    "PROJECT": (1, 2),
    "PROTEST": (1, 2),
    "READ": (2, 2),
    "REBEL": (1, 2),
    "RECALL": (3, 1),
    "RECAP": (2, 1),
    "RECESS": (1, 2),
    "RECORD": (1, 2),
    "RECOUNT": (2, 1),
    "REFILL": (1, 2),
    "REFUND": (2, 1),
    "REFUSE": (2, 1),
    "REJECT": (2, 1),
    "RELAPSE": (1, 2),
    "RELAY": (1, 2),
    "REMAKE": (1, 2),
    "RERUN": (1, 2),
    "RESEARCH": (1, 2),
    "RESUME": (2, 1),
    "RETAKE": (2, 1),
    "REWRITE": (2, 1),
    "SEGMENT": (1, 2),
    "SEPARATE": (2, 5),
    "SOW": (2, 1),
    "SUBJECT": (5, 2),
    "SUBLET": (1, 2),
    "SUBORDINATE": (5, 2),
    "SURVEY": (1, 2),
    "SUSPECT": (5, 2),
    "SYNDICATE": (1, 2),
    "TEAR": (2, 1),
    "TORMENT": (2, 1),
    "TRANSFORM": (2, 1),
    "TRANSPLANT": (2, 1),
    "TRANSPORT": (2, 1),
    "UPSET": (6, 1),
    "USE": (2, 1),
    "WIND": (3, 2),
    "WOUND": (2, 3),
}
"""Word → ``(P_role_mask, S_role_mask)`` lookup for the 140 noun/verb
homographs that ship both ``,P,`` and ``,S,`` rows in
``Dic_us_2002.txt``. Each mask is a compact 3-bit field
(noun=1, verb=2, adj=4); use :func:`_expand_role_mask` to convert it
to the full ``FC_*`` bitfield the ``homo_table`` rules consume."""


# -- Context-word POS tagger ----------------------------------------------
#
# DECtalk's runtime threads each word's form-class bits through
# ``pLts_t->word_info[].form_class``. We don't have the full main-dic
# at hand, so we tag the function-word neighbours the audit cared about
# using a compact table. Open-class context (other nouns/verbs/adjs)
# defaults to ``FC_NOUN`` per the C source's BATS#705 fallback (see
# the ``"if (pLts_t->fc_struct[pLts_t->fc_index-1] == 0)"`` branch in
# ``ls_homo_homo``).

_CONTEXT_FC: Final[dict[str, int]] = {
    # Articles. The C ``a`` and ``an`` dic entries carry FC_ART; ``the``
    # is FC_ART | FC_PRON (per Dic_us_2002.txt row 1).
    "A": FC_ART,
    "AN": FC_ART,
    "THE": FC_ART,
    # Pronouns (subject + object). The C dic flags these as FC_PRON; we
    # cover the high-frequency cases the audit corpus exercises.
    "I": FC_PRON,
    "YOU": FC_PRON,
    "HE": FC_PRON,
    "SHE": FC_PRON,
    "IT": FC_PRON,
    "WE": FC_PRON,
    "THEY": FC_PRON,
    "ME": FC_PRON,
    "HIM": FC_PRON,
    "HER": FC_PRON,
    "US": FC_PRON,
    "THEM": FC_PRON,
    "WHO": FC_PRON | FC_WHOW,
    "WHOM": FC_PRON | FC_WHOW,
    # ``to`` -- the FC_TO bit drives rule 10 (context TO → select VERB),
    # canonical for the infinitive ("to record", "to present").
    "TO": FC_TO,
    # Auxiliaries. ``will`` / ``can`` / ``shall`` / ``would`` / ``could`` /
    # ``should`` / ``may`` / ``might`` / ``must`` all carry FC_AUX in the
    # main dic. They select VERB via rule 15.
    "WILL": FC_AUX,
    "CAN": FC_AUX,
    "SHALL": FC_AUX,
    "WOULD": FC_AUX,
    "COULD": FC_AUX,
    "SHOULD": FC_AUX,
    "MAY": FC_AUX,
    "MIGHT": FC_AUX,
    "MUST": FC_AUX,
    "DO": FC_AUX,
    "DOES": FC_AUX,
    "DID": FC_AUX,
    # ``be`` / ``am`` / ``is`` / ``are`` / ``was`` / ``were`` / ``been`` —
    # FC_BE bit drives rules 14 + 18 (context BE → select VERB / ED).
    "BE": FC_BE,
    "AM": FC_BE,
    "IS": FC_BE,
    "ARE": FC_BE,
    "WAS": FC_BE,
    "WERE": FC_BE,
    "BEEN": FC_BE,
    "BEING": FC_BEV,
    # ``have`` / ``has`` / ``had`` — FC_HAVE drives rules 12 + 16 (context
    # HAVE → select ED past-participle / VERB).
    "HAVE": FC_HAVE,
    "HAS": FC_HAVE,
    "HAD": FC_HAVE,
    "HAVING": FC_HAVE,
    # Prepositions — FC_PREP drives rule 21 (context PREP → eliminate
    # VERB) and rule 22 (context ART → eliminate VERB), which together
    # cover "of record", "by record", "in record", etc.
    "OF": FC_PREP,
    "IN": FC_PREP,
    "ON": FC_PREP,
    "AT": FC_PREP,
    "BY": FC_PREP,
    "FOR": FC_PREP,
    "WITH": FC_PREP,
    "FROM": FC_PREP,
    "ABOUT": FC_PREP,
    "AS": FC_PREP,
    "INTO": FC_PREP,
    "THROUGH": FC_PREP,
    "OVER": FC_PREP,
    "UNDER": FC_PREP,
    "AFTER": FC_PREP,
    "BEFORE": FC_PREP,
    # Possessives — FC_POS drives rule 19 (context POSS → select NOUN).
    "MY": FC_POS,
    "YOUR": FC_POS,
    "HIS": FC_POS,
    "ITS": FC_POS,
    "OUR": FC_POS,
    "THEIR": FC_POS,
    # Conjunctions — leave at 0 (no homo_table rule keys on FC_CONJ).
    "AND": FC_CONJ,
    "OR": FC_CONJ,
    "BUT": FC_CONJ,
    # Negations and a few common adverbs feed rule 4 + 24/25.
    "NOT": FC_ADV,
    "VERY": FC_ADV,
    "QUITE": FC_ADV,
    "ALSO": FC_ADV,
    "JUST": FC_ADV,
    "ONLY": FC_ADV,
    "NEVER": FC_ADV,
    "ALWAYS": FC_ADV,
    "OFTEN": FC_ADV,
    "SOMETIMES": FC_ADV,
    "USUALLY": FC_ADV,
    "RARELY": FC_ADV,
    "REALLY": FC_ADV,
    "TRULY": FC_ADV,
    "BARELY": FC_ADV,
    # ``wh-`` words drive rule 11 (context WHOW → eliminate NOUN).
    "WHAT": FC_WHOW,
    "WHERE": FC_WHOW,
    "WHEN": FC_WHOW,
    "WHY": FC_WHOW,
    "HOW": FC_WHOW,
    "WHICH": FC_WHOW,
}
"""Compact POS tagger for the common function-word neighbours seen in
the LTS audit corpus. ``form_class_of(word)`` looks this up and
falls back to ``FC_NOUN`` for any other word (matching the C
``BATS#705`` fallback in :func:`ls_homo_homo`)."""


def form_class_of(word: str | None) -> int:
    """Return the FC bitmask for a context word.

    Words not in :data:`_CONTEXT_FC` default to ``FC_NOUN`` — this
    mirrors the C ``ls_homo_homo`` fallback path that treats an
    unknown previous word as a noun (BATS#705 in
    ``src/dapi/src/lts/ls_homo.c``).

    Args:
        word: Upper-cased context word, or ``None`` for "no neighbour"
            (sentence boundary).

    Returns:
        The FC bitmask the homograph rules should test ``h_context``
        against. Returns ``0`` for sentence-boundary (``word=None``).
    """
    if word is None:
        return 0
    return _CONTEXT_FC.get(word.upper(), FC_NOUN)


def homograph_fc_masks(word: str) -> tuple[int, int] | None:
    """Return ``(p_fc, s_fc)`` FC bitmasks for a known homograph word.

    ``p_fc`` and ``s_fc`` are full FC_* masks (e.g. ``FC_NOUN``,
    ``FC_VERB``) expanded from the compact 3-bit role mask in
    :data:`HOMOGRAPH_FC_BITS`.

    Args:
        word: Word to look up; case is folded to upper.

    Returns:
        Tuple of ``(P_entry_fc, S_entry_fc)`` masks, or ``None`` if
        ``word`` is not a known noun/verb-pair homograph.
    """
    entry = HOMOGRAPH_FC_BITS.get(word.upper())
    if entry is None:
        return None
    p_role, s_role = entry
    return _expand_role_mask(p_role), _expand_role_mask(s_role)


def disambiguate(  # noqa: PLR0911 - mirrors the C rule-loop's per-branch returns
    word: str,
    *,
    prev_word: str | None = None,
    prev_prev_word: str | None = None,
    is_sentence_initial: bool = False,
) -> str:
    """Pick ``"P"`` or ``"S"`` for a noun/verb homograph from context.

    Port of the rule-evaluation tail of :func:`ls_homo_homo` from
    ``src/dapi/src/lts/ls_homo.c``: walks the 27-entry homograph
    rule table, testing each rule's ``h_context`` against the
    previous word's FC bits and (when ``h_select`` /``h_elim`` is
    nonzero) checking whether the current word's primary/secondary
    candidate entry matches.

    Args:
        word: The homograph word (must appear in
            :data:`HOMOGRAPH_FC_BITS`).
        prev_word: The immediately preceding word, or ``None``.
        prev_prev_word: The word two positions back, used only when
            ``prev_word`` is an adverb (rule 21 fall-through in
            :func:`ls_homo_homo`).
        is_sentence_initial: ``True`` when ``word`` is the first
            content word of the sentence. The C code's
            ``cur_word_index == 1`` branch returns the primary entry
            in that case.

    Returns:
        ``"P"`` to select the primary entry, ``"S"`` to select the
        secondary entry. Defaults to ``"P"`` when no rule fires
        (matching the C fallback).
    """
    masks = homograph_fc_masks(word)
    if masks is None:
        return "P"
    p_fc, s_fc = masks

    # Sentence-initial words default to the primary entry per the C
    # ``cur_word_index == 1`` branch (line 349 of ls_homo.c).
    if is_sentence_initial:
        return "P"

    prev_fc = form_class_of(prev_word)
    # GL 3/3/1997 fall-through: if prev is an adverb, also test the
    # word two back. Matches the ``FC_ADV & prev`` branch on
    # line 397-400 of ls_homo.c.
    prev_prev_fc = form_class_of(prev_prev_word) if (prev_fc & FC_ADV) else 0

    # We don't have a stripped-suffix FC mask for the target word, so
    # ``h_suffix == 0`` rules are the only ones that can fire — the
    # ``h_suffix != 0`` rules need the suffix engine's FC mask
    # (e.g. an -ED suffix carries FC_ED). For the noun/verb pairs in
    # the audit corpus those don't apply: those words ship as bare
    # forms, not suffix-derived.
    for rule in homo_table:
        if rule.h_suffix != 0:
            continue
        # Match context (prev or prev-prev when prev is ADV).
        if rule.h_context == 0:
            continue  # h_suffix=0 AND h_context=0 -- impossible / no-op
        context_match = bool(rule.h_context & prev_fc) or bool(rule.h_context & prev_prev_fc)
        if not context_match:
            continue

        # h_select: "if the primary entry has this FC, keep it; else
        # if the secondary entry has this FC, swap to secondary".
        if rule.h_select:
            if rule.h_select & p_fc:
                return "P"
            if rule.h_select & s_fc:
                return "S"
        # h_elim: "if the secondary entry has this FC, keep primary;
        # else if the primary entry has this FC, swap to secondary".
        if rule.h_elim:
            if rule.h_elim & s_fc:
                return "P"
            if rule.h_elim & p_fc:
                return "S"

    # No rule fired — fall back to primary (mirrors the C default).
    return "P"


__all__ = [
    "HOMOGRAPH_FC_BITS",
    "disambiguate",
    "form_class_of",
    "homograph_fc_masks",
]
