"""Form-class bit-flag constants from fc_def.tab.

Translated from ``src/dapi/src/include/fc_def.tab``. The 32-bit
form-class mask the LTS and CMD modules use to tag a dictionary
entry's part-of-speech / grammatical role. Each ``FC_*`` constant
is a single-bit flag corresponding to one position in the mask;
:mod:`dectalk.dic.form_class` provides the human-readable
abbreviations for each position.
"""

from __future__ import annotations

from typing import Final

FC_ADJ: Final[int] = 0x00000001
"""Adjective."""

FC_ADV: Final[int] = 0x00000002
"""Adverb."""

FC_ART: Final[int] = 0x00000004
"""Article."""

FC_AUX: Final[int] = 0x00000008
"""Auxiliary verb."""

FC_BE: Final[int] = 0x00000010
"""Form of ``be`` (am, is, are, was, were, been)."""

FC_BEV: Final[int] = 0x00000020
"""``be`` + verb construction."""

FC_CONJ: Final[int] = 0x00000040
"""Conjunction."""

FC_ED: Final[int] = 0x00000080
"""Past-tense / past-participle ``-ed`` form."""

FC_HAVE: Final[int] = 0x00000100
"""Form of ``have`` (has, had, having)."""

FC_ING: Final[int] = 0x00000200
"""Present-participle / gerund ``-ing`` form."""

FC_NOUN: Final[int] = 0x00000400
"""Noun."""

FC_POS: Final[int] = 0x00000800
"""Possessive."""

FC_PREP: Final[int] = 0x00001000
"""Preposition."""

FC_PRON: Final[int] = 0x00002000
"""Pronoun."""

FC_SMS: Final[int] = 0x00004000
"""SMS / abbreviation marker."""

FC_THAT: Final[int] = 0x00008000
"""The word ``that``."""

FC_TO: Final[int] = 0x00010000
"""The word ``to``."""

FC_VERB: Final[int] = 0x00020000
"""Verb."""

FC_WHOW: Final[int] = 0x00040000
"""``wh-`` word (who, what, where, when, why, how)."""

FC_NEG: Final[int] = 0x00080000
"""Negation marker."""

FC_INTER: Final[int] = 0x00100000
"""Interjection."""

FC_PART: Final[int] = 0x00400000
"""Particle."""

FC_FUNC: Final[int] = 0x00800000
"""Function word (closed-class)."""

FC_CONTR: Final[int] = 0x01000000
"""Contraction."""

FC_CHARACTER: Final[int] = 0x02000000
"""Single-character word."""

FC_NAME: Final[int] = 0x10000000
"""Proper name."""

FC_FC_MARKER: Final[int] = 0x20000000
"""Form-class marker."""

FC_HOMOGRAPH: Final[int] = 0x80000000
"""Homograph (multiple pronunciations)."""


# -- FC_M_* aliases / extras (from fc_def.tab) ------------------------------
#
# Most ``FC_M_*`` constants are renames of the ``FC_*`` flags above. A
# handful introduce new bits (FC_M_REF / FC_M_REFR / FC_M_CONTRACTION) that
# don't appear in the FC_* set.

FC_M_ADJ: Final[int] = 0x00000001
"""Adjective (alias of :data:`FC_ADJ`)."""

FC_M_ADV: Final[int] = 0x00000002
"""Adverb (alias of :data:`FC_ADV`)."""

FC_M_ART: Final[int] = 0x00000004
"""Article (alias of :data:`FC_ART`)."""

FC_M_AUX: Final[int] = 0x00000008
"""Auxiliary verb (alias of :data:`FC_AUX`)."""

FC_M_BE: Final[int] = 0x00000010
"""``be`` form (alias of :data:`FC_BE`)."""

FC_M_BEV: Final[int] = 0x00000020
"""``be`` + verb (alias of :data:`FC_BEV`)."""

FC_M_CONJ: Final[int] = 0x00000040
"""Conjunction (alias of :data:`FC_CONJ`)."""

FC_M_ED: Final[int] = 0x00000080
"""``-ed`` past form (alias of :data:`FC_ED`)."""

FC_M_HAVE: Final[int] = 0x00000100
"""``have`` form (alias of :data:`FC_HAVE`)."""

FC_M_ING: Final[int] = 0x00000200
"""``-ing`` present-participle form (alias of :data:`FC_ING`)."""

FC_M_NOUN: Final[int] = 0x00000400
"""Noun (alias of :data:`FC_NOUN`)."""

FC_M_POS: Final[int] = 0x00000800
"""Possessive (alias of :data:`FC_POS`)."""

FC_M_PREP: Final[int] = 0x00001000
"""Preposition (alias of :data:`FC_PREP`)."""

FC_M_PRON: Final[int] = 0x00002000
"""Pronoun (alias of :data:`FC_PRON`)."""

FC_M_SUBCONJ: Final[int] = 0x00004000
"""Subordinating conjunction (alias of :data:`FC_SMS`)."""

FC_M_THAT: Final[int] = 0x00008000
"""``that`` word (alias of :data:`FC_THAT`)."""

FC_M_TO: Final[int] = 0x00010000
"""``to`` word (alias of :data:`FC_TO`)."""

FC_M_VERB: Final[int] = 0x00020000
"""Verb (alias of :data:`FC_VERB`)."""

FC_M_WHO: Final[int] = 0x00040000
"""``who``-type word (alias of :data:`FC_WHOW`)."""

FC_M_NEG: Final[int] = 0x00080000
"""Negation marker (alias of :data:`FC_NEG`)."""

FC_M_INTER: Final[int] = 0x00100000
"""Interjection (alias of :data:`FC_INTER`)."""

FC_M_REF: Final[int] = 0x00200000
"""Reflexive pronoun (no FC_* equivalent)."""

FC_M_PART: Final[int] = 0x00400000
"""Particle (alias of :data:`FC_PART`)."""

FC_M_FUNC: Final[int] = 0x00800000
"""Function word (alias of :data:`FC_FUNC`)."""

FC_M_CONT: Final[int] = 0x01000000
"""Contraction (alias of :data:`FC_CONTR`)."""

FC_M_CHARACTER: Final[int] = 0x02000000
"""Single-character word (alias of :data:`FC_CHARACTER`)."""

FC_M_REFR: Final[int] = 0x04000000
"""Referential marker (no FC_* equivalent)."""

FC_M_FC_MARKER: Final[int] = 0x20000000
"""Form-class marker (alias of :data:`FC_FC_MARKER`)."""

FC_M_CONTRACTION: Final[int] = 0x40000000
"""Contraction-2 marker (no FC_* equivalent)."""

FC_M_HOMOGRAPH: Final[int] = 0x80000000
"""Homograph marker (alias of :data:`FC_HOMOGRAPH`)."""


# -- Bit-position constants (FC_V_*) ---------------------------------------
#
# These are the log2 indices of the FC_* flags (0..31). Used when the C
# source needs to set or test a specific bit by position rather than by
# mask, e.g. ``bit_array |= (1L << FC_V_NOUN)``.

FC_V_ADJ: Final[int] = 0
FC_V_ADV: Final[int] = 1
FC_V_ART: Final[int] = 2
FC_V_AUX: Final[int] = 3
FC_V_BE: Final[int] = 4
FC_V_BEV: Final[int] = 5
FC_V_CONJ: Final[int] = 6
FC_V_ED: Final[int] = 7
FC_V_HAVE: Final[int] = 8
FC_V_ING: Final[int] = 9
FC_V_NOUN: Final[int] = 10
FC_V_POS: Final[int] = 11
FC_V_PREP: Final[int] = 12
FC_V_PRON: Final[int] = 13
FC_V_SUBCONJ: Final[int] = 14
FC_V_THAT: Final[int] = 15
FC_V_TO: Final[int] = 16
FC_V_VERB: Final[int] = 17
FC_V_WHO: Final[int] = 18
FC_V_NEG: Final[int] = 19
FC_V_INTER: Final[int] = 20
FC_V_REF: Final[int] = 21
FC_V_PART: Final[int] = 22
FC_V_FUNC: Final[int] = 23
FC_V_CONT: Final[int] = 24
FC_V_CHARACTER: Final[int] = 25
FC_V_REFR: Final[int] = 26
FC_V_FC_MARKER: Final[int] = 29
FC_V_CONTRACTION: Final[int] = 30
FC_V_HOMOGRAPH: Final[int] = 31


__all__ = [
    "FC_ADJ",
    "FC_ADV",
    "FC_ART",
    "FC_AUX",
    "FC_BE",
    "FC_BEV",
    "FC_CHARACTER",
    "FC_CONJ",
    "FC_CONTR",
    "FC_ED",
    "FC_FC_MARKER",
    "FC_FUNC",
    "FC_HAVE",
    "FC_HOMOGRAPH",
    "FC_ING",
    "FC_INTER",
    "FC_M_ADJ",
    "FC_M_ADV",
    "FC_M_ART",
    "FC_M_AUX",
    "FC_M_BE",
    "FC_M_BEV",
    "FC_M_CHARACTER",
    "FC_M_CONJ",
    "FC_M_CONT",
    "FC_M_CONTRACTION",
    "FC_M_ED",
    "FC_M_FC_MARKER",
    "FC_M_FUNC",
    "FC_M_HAVE",
    "FC_M_HOMOGRAPH",
    "FC_M_ING",
    "FC_M_INTER",
    "FC_M_NEG",
    "FC_M_NOUN",
    "FC_M_PART",
    "FC_M_POS",
    "FC_M_PREP",
    "FC_M_PRON",
    "FC_M_REF",
    "FC_M_REFR",
    "FC_M_SUBCONJ",
    "FC_M_THAT",
    "FC_M_TO",
    "FC_M_VERB",
    "FC_M_WHO",
    "FC_NAME",
    "FC_NEG",
    "FC_NOUN",
    "FC_PART",
    "FC_POS",
    "FC_PREP",
    "FC_PRON",
    "FC_SMS",
    "FC_THAT",
    "FC_TO",
    "FC_VERB",
    "FC_V_ADJ",
    "FC_V_ADV",
    "FC_V_ART",
    "FC_V_AUX",
    "FC_V_BE",
    "FC_V_BEV",
    "FC_V_CHARACTER",
    "FC_V_CONJ",
    "FC_V_CONT",
    "FC_V_CONTRACTION",
    "FC_V_ED",
    "FC_V_FC_MARKER",
    "FC_V_FUNC",
    "FC_V_HAVE",
    "FC_V_HOMOGRAPH",
    "FC_V_ING",
    "FC_V_INTER",
    "FC_V_NEG",
    "FC_V_NOUN",
    "FC_V_PART",
    "FC_V_POS",
    "FC_V_PREP",
    "FC_V_PRON",
    "FC_V_REF",
    "FC_V_REFR",
    "FC_V_SUBCONJ",
    "FC_V_THAT",
    "FC_V_TO",
    "FC_V_VERB",
    "FC_V_WHO",
    "FC_WHOW",
]
