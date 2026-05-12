"""Word-level feature-mark bits from ls_dict.h.

Translated from ``src/dapi/src/lts/ls_dict.h``. These are 16-bit
``MARK_*`` flags the LTS pipeline ORs together to classify a word
(start of sentence, has vowel, has digit, contains hyphen, …).

**Not to be confused with the 8-bit ``MARK_*`` flags in cm_defs.h**
(``MARK_clause``, ``MARK_space``, ``MARK_punct``, …) which classify
*individual characters* rather than whole words. The cm_defs.h
namespace is exposed via :mod:`dectalk.cmd.char_types_table`; the
ls_dict.h namespace is here.

The C source also defines two ``FC_*`` modifier flags
(:data:`FC_NEGATE` and :data:`FC_STRUCTURE`) plus three composite
masks (:data:`FC_ALWAYS`, :data:`FC_TARGET`, :data:`FC_CONSIDER`,
:data:`FC_KEEP`) used to gate dictionary feature-class probes.
"""

from __future__ import annotations

from typing import Final

# -- Word-level marker bits (16-bit) ----------------------------------------

MARK_null: Final[int] = 0x0000
"""Null marker — empty placeholder."""

MARK_start: Final[int] = 0x0001
"""Word at the start of a sentence."""

MARK_end: Final[int] = 0x0002
"""Word at the end of a sentence."""

MARK_comma: Final[int] = 0x0004
"""Word contains a comma."""

MARK_first_upper: Final[int] = 0x0008
"""First character of the word is upper-case."""

MARK_vowel: Final[int] = 0x0010
"""Word contains at least one vowel."""

MARK_upper: Final[int] = 0x0020
"""Word contains at least one upper-case letter."""

MARK_cons: Final[int] = 0x0040
"""Word contains at least one consonant."""

MARK_digit: Final[int] = 0x0080
"""Word contains at least one digit."""

MARK_hyphen: Final[int] = 0x0100
"""Word contains a hyphen."""

MARK_ques_excl: Final[int] = 0x0200
"""Word contains a ``?`` or ``!``."""

MARK_non_alpha: Final[int] = 0x0400
"""Word contains a non-alphanumeric character."""

MARK_slash: Final[int] = 0x0800
"""Word contains a ``/``."""

MARK_numeric: Final[int] = 0x1000
"""Word looks numeric (sign / digits / decimal / exponent)."""

MARK_period: Final[int] = 0x2000
"""Word contains a ``.``."""

MARK_dquote: Final[int] = 0x4000
"""Word contains a ``"``."""

MARK_squote: Final[int] = 0x8000
"""Word contains a ``'``."""

# -- Feature-class probe modifiers (32-bit) ---------------------------------

FC_NEGATE: Final[int] = 0x04000000
"""Negate the test (probe matches when the feature is *absent*)."""

FC_STRUCTURE: Final[int] = 0x08000000
"""Word-structure definition (vs. ordinary feature match)."""

FC_TARGET: Final[int] = 0xFFFFFFFF
"""Full-mask probe target — matches any word."""

FC_CONSIDER: Final[int] = 0x00FFFFFF
"""Low-24 bits — the feature-bits portion of an FC_* value."""

FC_KEEP: Final[int] = 0xFF000000
"""High-8 bits — the flag-modifier portion of an FC_* value."""

__all__ = [
    "FC_CONSIDER",
    "FC_KEEP",
    "FC_NEGATE",
    "FC_STRUCTURE",
    "FC_TARGET",
    "MARK_comma",
    "MARK_cons",
    "MARK_digit",
    "MARK_dquote",
    "MARK_end",
    "MARK_first_upper",
    "MARK_hyphen",
    "MARK_non_alpha",
    "MARK_null",
    "MARK_numeric",
    "MARK_period",
    "MARK_ques_excl",
    "MARK_slash",
    "MARK_squote",
    "MARK_start",
    "MARK_upper",
    "MARK_vowel",
]
