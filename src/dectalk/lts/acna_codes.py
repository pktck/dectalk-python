"""ACNA (auto-language detection) constants and struct from ls_acna.h.

Translated from ``src/dapi/src/lts/ls_acna.h``. ACNA stands for
"Auto-Categorise Name by Algorithm" — the multilingual extras that
classify foreign-looking words by language family using trigram
statistics, applied when MODE_NAME is on.

The Python port exposes the constants and struct shape; the actual
trigram table loading is gated by ``#ifdef ACNA`` in C and isn't
needed for the US-only path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# -- Trigram byte field layout ----------------------------------------------

TG_start: Final[int] = 0x80
"""Trigram byte high bit: word-start marker."""

TG_end: Final[int] = 0x40
"""Trigram byte 2nd bit: word-end marker."""

TG_freq: Final[int] = 0x3F
"""Trigram byte low 6 bits: frequency count (0..63)."""

# -- Pattern-rule encoding bits ---------------------------------------------

PLENGTH: Final[int] = 0x0F
"""Pattern length in phonemes (low nibble)."""

PCONT: Final[int] = 0x10
"""Pattern flag: continue with the next pattern."""

PRCON: Final[int] = 0x20
"""Pattern flag: require a consonant at the boundary."""

PRVOC: Final[int] = 0x40
"""Pattern flag: require a vowel at the boundary."""

P2SYL: Final[int] = 0x80
"""Pattern flag: destress two syllables."""

# -- Language group identifiers ---------------------------------------------

NAME_ENGLISH: Final[int] = 0
"""ACNA language group: English."""

NAME_FRENCH: Final[int] = 1
"""ACNA language group: French."""

NAME_GERMANIC: Final[int] = 2
"""ACNA language group: Germanic (German, Dutch, Scandinavian)."""

NAME_IRISH: Final[int] = 3
"""ACNA language group: Irish Gaelic."""

NAME_ITALIAN: Final[int] = 4
"""ACNA language group: Italian."""

NAME_JAPANESE: Final[int] = 5
"""ACNA language group: Japanese."""

NAME_SLAVIC: Final[int] = 6
"""ACNA language group: Slavic (Russian, Polish, Czech…)."""

NAME_SPANISH: Final[int] = 7
"""ACNA language group: Spanish."""

NO_LANGS: Final[int] = 8
"""Total number of ACNA language groups."""

# -- Rule-language tag bit masks --------------------------------------------

M_R_LANG: Final[int] = 0x7FFF
"""Mask for the rule's language-tag field (low 15 bits)."""

M_R_SPECIFIC: Final[int] = 0x8000
"""Mask for the rule's specificity flag (high bit)."""


@dataclass(slots=True)
class Langs:
    """Per-language ACNA classification state.

    Faithful translation of:

    .. code-block:: c

        struct langs {
            unsigned char *tri_grams;
            int  entries;
            int  hits;
            int  last_prob;
            char eliminate;
            S32  prob;
            int  name_type;
        };

    Attributes:
        tri_grams: Pointer to the trigram table for this language
            (modelled as ``bytes | None``).
        entries: Total trigram entries in the table.
        hits: Number of trigrams matched against the input word.
        last_prob: Previously computed log-probability.
        eliminate: Non-zero if this language has been ruled out.
        prob: Running log-probability (signed 32-bit).
        name_type: The :data:`NAME_*` group ID this struct represents.
    """

    tri_grams: bytes | None = None
    entries: int = 0
    hits: int = 0
    last_prob: int = 0
    eliminate: int = 0
    prob: int = 0
    name_type: int = 0


__all__ = [
    "M_R_LANG",
    "M_R_SPECIFIC",
    "NAME_ENGLISH",
    "NAME_FRENCH",
    "NAME_GERMANIC",
    "NAME_IRISH",
    "NAME_ITALIAN",
    "NAME_JAPANESE",
    "NAME_SLAVIC",
    "NAME_SPANISH",
    "NO_LANGS",
    "P2SYL",
    "PCONT",
    "PLENGTH",
    "PRCON",
    "PRVOC",
    "Langs",
    "TG_end",
    "TG_freq",
    "TG_start",
]
