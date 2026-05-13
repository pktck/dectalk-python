"""Binary-rule opcode constants from par_bin.h.

Translated from ``src/dapi/src/cmd/par_bin.h``. These define how
rules are encoded as bytes in the compiled binary rule format
the LTS rule engine consumes.

The encoding has three layers:

- :data:`BIN_OPERATION_MASK` (0x1F) — low 5 bits select the
  primary rule operation (alphabetic / numeric / punctuation /
  rule-form delimiter etc.).
- :data:`BIN_OPERATION_FLAG_MASK` (0xE0) — high 3 bits flag the
  operation-specific modifiers (look-to/from disable, digit
  range, case-insensitive, etc.).
- :data:`BIN_SIZE_DESC_MASK` (0x3F) and friends — runs of the
  same operation packed via small/large-descriptor variants.
- :data:`BIN_SPECIAL_RULE_MASK` (0xE000) — top 3 bits of a
  16-bit special-rule code (STOP / RETURN / GOTO / GORET).

Two values are deliberately overloaded:

- :data:`BIN_COMP_BREAK` (0x1B) and :data:`BIN_AFTER` (0x1B) are
  the same byte — the C source uses each name in different
  contexts depending on the rule's operation.
- :data:`BIN_DIGIT_RANGE` (0x20) and :data:`BIN_CASE_INSEN`
  (0x20) — a shared bit with different meanings per operation.
"""

from __future__ import annotations

from typing import Final

# -- Opcode masks ----------------------------------------------------------

BIN_OPERATION_MASK: Final[int] = 0x1F
"""Low 5 bits — selects the primary rule operation."""

BIN_OPERATION_FLAG_MASK: Final[int] = 0xE0
"""High 3 bits — operation-specific flags."""

# -- Primary operations (low 5 bits) ---------------------------------------

BIN_END_OF_RULE: Final[int] = 0x00
BIN_ALPHANUMERIC: Final[int] = 0x01
BIN_ANY_ALPHABET: Final[int] = 0x02
BIN_ANY_CHARACTER: Final[int] = 0x03
BIN_CLAUSE_BOUNDRY: Final[int] = 0x04
BIN_CONSONANT: Final[int] = 0x05
BIN_LOWER: Final[int] = 0x06
BIN_NON_ALPHABET: Final[int] = 0x07
BIN_NUMBER: Final[int] = 0x08
BIN_PUNCT_SOME: Final[int] = 0x09
BIN_PUNCTUATION: Final[int] = 0x0A
BIN_UPPER: Final[int] = 0x0B
BIN_VOWEL: Final[int] = 0x0C
BIN_VOWEL_NON_Y: Final[int] = 0x0D
BIN_WHITESPACE: Final[int] = 0x0E
BIN_DIGIT: Final[int] = 0x0F
BIN_EXACT: Final[int] = 0x10
BIN_HEXADECIMAL: Final[int] = 0x11
BIN_RESTORE: Final[int] = 0x12
BIN_SETS: Final[int] = 0x13
BIN_COPY: Final[int] = 0x14
BIN_DELETE: Final[int] = 0x15
BIN_OPTIONAL: Final[int] = 0x16
BIN_SAVE: Final[int] = 0x17
BIN_MACRO: Final[int] = 0x18
BIN_REPLACE: Final[int] = 0x19
BIN_INSERT: Final[int] = 0x1A
BIN_COMP_BREAK: Final[int] = 0x1B
"""Composition break (alias of :data:`BIN_AFTER`)."""
BIN_AFTER: Final[int] = 0x1B
"""Insert-after marker (alias of :data:`BIN_COMP_BREAK`)."""
BIN_BEFORE: Final[int] = 0x1C
BIN_DICTIONARY: Final[int] = 0x1D
BIN_STATUS: Final[int] = 0x1E
BIN_WORD: Final[int] = 0x1F

# -- Operation flags (high 3 bits) -----------------------------------------

BIN_LOOK_TO_DISABLE: Final[int] = 0x80
BIN_LOOK_FROM_DISABLE: Final[int] = 0x40
BIN_DIGIT_RANGE: Final[int] = 0x20
"""Digit range flag — shared bit with :data:`BIN_CASE_INSEN`."""
BIN_CASE_INSEN: Final[int] = 0x20
"""Case-insensitive flag — shared bit with :data:`BIN_DIGIT_RANGE`."""
BIN_DICT_HIT_FAIL: Final[int] = 0x80
BIN_DICT_MISS_FAIL: Final[int] = 0x40
BIN_CONDITIONAL_REPLACE: Final[int] = 0x80
BIN_AFTER_FLAG: Final[int] = 0x40
BIN_BEFORE_FLAG: Final[int] = 0x20

# -- Size descriptors ------------------------------------------------------

BIN_SIZE_DESC_MASK: Final[int] = 0x3F
BIN_SIZE_DESC_FLAG_MASK: Final[int] = 0xC0
BIN_COMPLIMENT: Final[int] = 0x80
BIN_LARGE_DESC: Final[int] = 0x40
BIN_MAX_SMALL_DESC: Final[int] = 0x3F
BIN_SMALL_DESC_FLG_MASK: Final[int] = 0xC0
BIN_SMALL_ANY_NUMBER: Final[int] = 0x80
BIN_SMALL_CONTINUE: Final[int] = 0x40
BIN_MAX_LARGE_DESC: Final[int] = 0x3FFF
BIN_LARGE_DESC_FLG_MASK: Final[int] = 0xC000
BIN_LARGE_ANY_NUMBER: Final[int] = 0x8000
BIN_LARGE_CONTINUE: Final[int] = 0x4000

# -- Special rule codes (top 3 bits of 16-bit special-rule encoding) -------

BIN_SPECIAL_RULE_MASK: Final[int] = 0xE000
BIN_IS_SPECIAL: Final[int] = 0x8000
BIN_STOP: Final[int] = 0x2000
BIN_RETURN: Final[int] = 0x4000
BIN_GOTO: Final[int] = 0xA000
BIN_GORET: Final[int] = 0xC000
BIN_NEXT_HIT: Final[int] = 0x1000
BIN_NEXT_MISS: Final[int] = 0x0800
BIN_GORET_HIT: Final[int] = 0x0400
BIN_GORET_MISS: Final[int] = 0x0200
BIN_COPY_HIT: Final[int] = 0x0100
BIN_DICT_HIT: Final[int] = 0x0080
BIN_DICT_MISS: Final[int] = 0x0040


__all__ = [
    "BIN_AFTER",
    "BIN_AFTER_FLAG",
    "BIN_ALPHANUMERIC",
    "BIN_ANY_ALPHABET",
    "BIN_ANY_CHARACTER",
    "BIN_BEFORE",
    "BIN_BEFORE_FLAG",
    "BIN_CASE_INSEN",
    "BIN_CLAUSE_BOUNDRY",
    "BIN_COMPLIMENT",
    "BIN_COMP_BREAK",
    "BIN_CONDITIONAL_REPLACE",
    "BIN_CONSONANT",
    "BIN_COPY",
    "BIN_COPY_HIT",
    "BIN_DELETE",
    "BIN_DICTIONARY",
    "BIN_DICT_HIT",
    "BIN_DICT_HIT_FAIL",
    "BIN_DICT_MISS",
    "BIN_DICT_MISS_FAIL",
    "BIN_DIGIT",
    "BIN_DIGIT_RANGE",
    "BIN_END_OF_RULE",
    "BIN_EXACT",
    "BIN_GORET",
    "BIN_GORET_HIT",
    "BIN_GORET_MISS",
    "BIN_GOTO",
    "BIN_HEXADECIMAL",
    "BIN_INSERT",
    "BIN_IS_SPECIAL",
    "BIN_LARGE_ANY_NUMBER",
    "BIN_LARGE_CONTINUE",
    "BIN_LARGE_DESC",
    "BIN_LARGE_DESC_FLG_MASK",
    "BIN_LOOK_FROM_DISABLE",
    "BIN_LOOK_TO_DISABLE",
    "BIN_LOWER",
    "BIN_MACRO",
    "BIN_MAX_LARGE_DESC",
    "BIN_MAX_SMALL_DESC",
    "BIN_NEXT_HIT",
    "BIN_NEXT_MISS",
    "BIN_NON_ALPHABET",
    "BIN_NUMBER",
    "BIN_OPERATION_FLAG_MASK",
    "BIN_OPERATION_MASK",
    "BIN_OPTIONAL",
    "BIN_PUNCTUATION",
    "BIN_PUNCT_SOME",
    "BIN_REPLACE",
    "BIN_RESTORE",
    "BIN_RETURN",
    "BIN_SAVE",
    "BIN_SETS",
    "BIN_SIZE_DESC_FLAG_MASK",
    "BIN_SIZE_DESC_MASK",
    "BIN_SMALL_ANY_NUMBER",
    "BIN_SMALL_CONTINUE",
    "BIN_SMALL_DESC_FLG_MASK",
    "BIN_SPECIAL_RULE_MASK",
    "BIN_STATUS",
    "BIN_STOP",
    "BIN_UPPER",
    "BIN_VOWEL",
    "BIN_VOWEL_NON_Y",
    "BIN_WHITESPACE",
    "BIN_WORD",
]
