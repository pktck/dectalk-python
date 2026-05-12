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
    "FC_WHOW",
]
