"""Character-classification + illegal-cluster tables for the parser.

Translated from ``src/dapi/src/cmd/par_char.c``:

- :data:`parser_char_types` — 257-entry U16 table indexed by an
  unsigned char (plus a trailing 0 sentinel). Each entry is an OR of
  TYPE_* flags from cmd/par_def.h indicating digit/upper/lower/alpha/
  vowel/consonant/punctuation/whitespace/clause-terminator/etc. The
  bigger sibling of cm_char.c's char_types, with finer-grained flags
  (e.g. separates lower from upper case, vowel from non-y-vowel).
- :data:`par_illegal_cluster` — 14 short two-byte (mostly) digraphs
  that the parser treats as illegal consonant clusters. When the LTS
  rule pass would generate one of these, the parser inserts a vowel
  (typically schwa) to fix it.

The ``par_lower`` and ``par_upper`` case-folding tables in the same
C file are ``#include "ls_lower.tab"`` / ``ls_upper.tab`` — already
translated as :data:`dectalk.lts.char_features.ls_lower` and
:data:`ls_upper`, so they're not duplicated here.
"""

from __future__ import annotations

from typing import Final

# TYPE_* flag bits (from par_def.h).

TYPE_null: Final[int] = 0x0000
TYPE_digit: Final[int] = 0x0001
TYPE_upper: Final[int] = 0x0002
TYPE_lower: Final[int] = 0x0004
TYPE_alpha: Final[int] = 0x0008
TYPE_any_char: Final[int] = 0x0010
TYPE_white: Final[int] = 0x0020
TYPE_punct: Final[int] = 0x0040
TYPE_non_alpha: Final[int] = 0x0080
TYPE_vowel: Final[int] = 0x0100
TYPE_consonant: Final[int] = 0x0200
TYPE_number: Final[int] = 0x0400
TYPE_clause: Final[int] = 0x0800
TYPE_alpha_num: Final[int] = 0x1000
TYPE_vowel_non_y: Final[int] = 0x2000
TYPE_punct_some: Final[int] = 0x4000
TYPE_quot: Final[int] = 0x8000


# parser_char_types: U16 entries 0..255 plus a trailing 0 sentinel
# at index 256 (the C source includes the explicit final "0,").

parser_char_types: Final[tuple[int, ...]] = (
    0x0000, 0x0010, 0x0010, 0x0010, 0x0010, 0x0010, 0x0010, 0x0030,
    0x0030, 0x0810, 0x0030, 0x0830, 0x0030, 0x0030, 0x0010, 0x0030,
    0x0010, 0x0410, 0x0010, 0x0010, 0x0010, 0x0010, 0x0010, 0x0010,
    0x0010, 0x0010, 0x0010, 0x0010, 0x0010, 0x0010, 0x0010, 0x0010,
    0x0030, 0x08D0, 0x80D0, 0x40D0, 0x44D0, 0x44D0, 0x40D0, 0x00D0,
    0x84D0, 0x84D0, 0x44D0, 0x44D0, 0x08D0, 0x04D0, 0x08D0, 0x04D0,
    0x1091, 0x1091, 0x1091, 0x1091, 0x1091, 0x1091, 0x1091, 0x1091,
    0x1091, 0x1091, 0x08D0, 0x08D0, 0x84D0, 0x44D0, 0x84D0, 0x08D0,
    0x40D0, 0x311A, 0x121A, 0x121A, 0x121A, 0x311A, 0x121A, 0x121A,
    0x121A, 0x311A, 0x121A, 0x121A, 0x121A, 0x121A, 0x121A, 0x311A,
    0x121A, 0x121A, 0x121A, 0x121A, 0x121A, 0x311A, 0x121A, 0x121A,
    0x121A, 0x131A, 0x121A, 0x80D0, 0x80D0, 0x80D0, 0x44D0, 0x40D0,
    0x40D0, 0x311C, 0x121C, 0x121C, 0x121C, 0x311C, 0x121C, 0x121C,
    0x121C, 0x311C, 0x121C, 0x121C, 0x121C, 0x121C, 0x121C, 0x311C,
    0x121C, 0x121C, 0x121C, 0x121C, 0x121C, 0x311C, 0x121C, 0x121C,
    0x121C, 0x131C, 0x121C, 0x80D0, 0x80D0, 0x80D0, 0x40D0, 0x0010,
    0x0010, 0x0010, 0x0010, 0x0030, 0x0010, 0x0010, 0x0010, 0x0010,
    0x0010, 0x0010, 0x0010, 0x0010, 0x0010, 0x0010, 0x0010, 0x0010,
    0x0010, 0x0010, 0x0010, 0x0010, 0x0010, 0x0010, 0x0010, 0x0010,
    0x0010, 0x0010, 0x0010, 0x0010, 0x0010, 0x0010, 0x0010, 0x0010,
    0x0090, 0x00D0, 0x0090, 0x0090, 0x0090, 0x0090, 0x0090, 0x0090,
    0x0090, 0x0090, 0x0090, 0x0090, 0x0090, 0x0090, 0x0090, 0x0090,
    0x0090, 0x0090, 0x0490, 0x0490, 0x0090, 0x0090, 0x0090, 0x0090,
    0x0090, 0x0490, 0x0090, 0x0090, 0x0490, 0x0490, 0x0490, 0x00D0,
    0x311A, 0x311A, 0x311A, 0x311A, 0x311A, 0x311A, 0x311A, 0x121A,
    0x311A, 0x311A, 0x311A, 0x311A, 0x311A, 0x311A, 0x311A, 0x311A,
    0x121A, 0x121A, 0x311A, 0x311A, 0x311A, 0x311A, 0x311A, 0x0010,
    0x311A, 0x311A, 0x311A, 0x311A, 0x311A, 0x131A, 0x0012, 0x121C,
    0x311C, 0x311C, 0x311C, 0x311C, 0x311C, 0x311C, 0x311C, 0x121C,
    0x311C, 0x311C, 0x311C, 0x311C, 0x311C, 0x311C, 0x311C, 0x311C,
    0x121C, 0x121C, 0x311C, 0x311C, 0x311C, 0x311C, 0x311C, 0x0010,
    0x311C, 0x311C, 0x311C, 0x311C, 0x311C, 0x131C, 0x0014, 0x131C,
    0x0000,
)  # fmt: skip


# par_illegal_cluster: illegal-onset/coda digraphs the parser refuses
# to leave intact (the LTS engine inserts a schwa to break them).

par_illegal_cluster: Final[tuple[str, ...]] = (
    "bn", "bt", "db", "hb", "hp", "kd", "mb", "mc", "mf", "mt",
    "rf", "yf", "wb", "-",
)  # fmt: skip


# par_pars1.c::char_type_table — index-to-flag lookup used by the
# parser's table-driven dispatch. Each entry is one of the TYPE_*
# constants above. The 16 entries cover the 4-bit type tags the
# parser packs into its state machine table.

char_type_table: Final[tuple[int, ...]] = (
    TYPE_null,        # 0
    TYPE_alpha_num,   # 1
    TYPE_alpha,       # 2
    TYPE_any_char,    # 3
    TYPE_clause,      # 4
    TYPE_consonant,   # 5
    TYPE_lower,       # 6
    TYPE_non_alpha,   # 7
    TYPE_number,      # 8
    TYPE_punct_some,  # 9
    TYPE_punct,       # 10
    TYPE_upper,       # 11
    TYPE_vowel,       # 12
    TYPE_vowel_non_y, # 13
    TYPE_white,       # 14
    TYPE_digit,       # 15
)  # fmt: skip


__all__ = [
    "TYPE_alpha",
    "TYPE_alpha_num",
    "TYPE_any_char",
    "TYPE_clause",
    "TYPE_consonant",
    "TYPE_digit",
    "TYPE_lower",
    "TYPE_non_alpha",
    "TYPE_null",
    "TYPE_number",
    "TYPE_punct",
    "TYPE_punct_some",
    "TYPE_quot",
    "TYPE_upper",
    "TYPE_vowel",
    "TYPE_vowel_non_y",
    "TYPE_white",
    "char_type_table",
    "par_illegal_cluster",
    "parser_char_types",
]
