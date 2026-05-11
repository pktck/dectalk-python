"""LTS coarse character-class table (``lsctype``).

Translated from:

- ``src/dapi/src/lts/ls_defs.h`` — the word-character type and feature
  bits used by ``lsctype``.
- ``src/dapi/src/lts/l_us_con.c`` — the 256-entry U16 ``lsctype[]``
  table that the LTS engine consults via ``ISUPPER(c)`` / ``ISLOWER(c)``
  / ``ISALPHA(c)`` / ``ISVOWEL(c)`` macros and the low 4 bits' "what
  kind of word character is this?" decision.

This is a **separate** classification from :mod:`dectalk.lts.char_features`
(``ls_char_feat``). ``ls_char_feat`` is consulted by short-word case
folding and the math-mode tables; ``lsctype`` is consulted by the
word-extraction state machine that decides which input bytes survive
as part of a word and which trigger sentence/clause boundaries.

Bit layout for each ``lsctype[c]`` entry (U16):

- Bits 0-3 (mask :data:`TYPE`): word-character disposition —
  :data:`IGNORE`, :data:`BACKUP`, :data:`NEVER`, :data:`MIGHT`,
  :data:`ALWAYS`, :data:`PHONEME`. Drives the C ``put_letter`` flow
  in ``ls1.c``.
- Bit 4 (:data:`II`): "invisible" — character is ignored visually
  but may still affect parsing.
- Bit 5 (:data:`UU`): uppercase letter.
- Bit 6 (:data:`LS`): left-side strippable (when this character
  starts a word, peel it off).
- Bit 7 (:data:`RS`): right-side strippable.
- Bit 8 (:data:`FB`): forced clause break (triggers a phrase
  boundary).
- Bit 9 (:data:`OO`): vowel.
- Bit 10 (:data:`C_BIT`): consonant.
- Bit 11 (:data:`PR`): printing character.
- Bit 12 (:data:`L`): letter.
- Bit 13 (:data:`LC`): lowercase letter.
"""

from __future__ import annotations

from typing import Final

# -- TYPE field values (bits 0-3) ------------------------------------------

IGNORE: Final[int] = 0
"""Always discarded — character contributes nothing to word formation."""

BACKUP: Final[int] = 1
"""Backup the word cursor — character ends the current word."""

NEVER: Final[int] = 2
"""Never part of a word."""

MIGHT: Final[int] = 3
"""Goes in a word if embedded (e.g. apostrophe in 'don\\'t')."""

ALWAYS: Final[int] = 4
"""Always kept as part of the word."""

PHONEME: Final[int] = 5
"""Out-of-band signal — character represents a phoneme not a letter."""


# -- Single-bit feature flags (bits 4-13) ----------------------------------

TYPE: Final[int] = 0x000F
"""Mask for the TYPE field (IGNORE..PHONEME) in the low nibble."""

II: Final[int] = 0x0010
"""Invisible character."""

UU: Final[int] = 0x0020
"""Uppercase letter."""

LS: Final[int] = 0x0040
"""Left-side strippable."""

RS: Final[int] = 0x0080
"""Right-side strippable."""

FB: Final[int] = 0x0100
"""Forced clause break."""

OO: Final[int] = 0x0200
"""Vowel (kludge two-letter name in the C source)."""

C_BIT: Final[int] = 0x0400
"""Consonant. Named ``C_BIT`` to avoid clashing with Python's builtins;
the C source uses the single letter ``C``."""

PR: Final[int] = 0x0800
"""Printing character."""

L: Final[int] = 0x1000
"""Letter."""

LC: Final[int] = 0x2000
"""Lowercase letter."""


# -- lsctype[256] U16 table from l_us_con.c --------------------------------
# Indexed by ord(ch); ASCII subset is bytes 0x00..0x7F; bytes 0x80..0xFF
# carry the latin-1 letter coverage that DECtalk supports.

lsctype: Final[tuple[int, ...]] = (
    0x0000,
    0x0000,
    0x0000,
    0x0000,
    0x0000,
    0x0000,
    0x0000,
    0x0000,  # 0x00
    0x0001,
    0x0002,
    0x0002,
    0x0002,
    0x0002,
    0x0002,
    0x0000,
    0x0000,  # 0x08
    0x0000,
    0x0000,
    0x0000,
    0x0000,
    0x0000,
    0x0000,
    0x0000,
    0x0000,  # 0x10
    0x0000,
    0x0000,
    0x0000,
    0x0000,
    0x0000,
    0x0000,
    0x0000,
    0x0000,  # 0x18
    0x0002,
    0x0803,
    0x08C4,
    0x0804,
    0x0804,
    0x0804,
    0x0804,
    0x08C4,  # 0x20
    0x0944,
    0x0984,
    0x0804,
    0x0804,
    0x0803,
    0x0804,
    0x0803,
    0x0804,  # 0x28
    0x0804,
    0x0804,
    0x0804,
    0x0804,
    0x0804,
    0x0804,
    0x0804,
    0x0804,  # 0x30
    0x0804,
    0x0804,
    0x0803,
    0x0803,
    0x0944,
    0x0804,
    0x0984,
    0x0803,  # 0x38
    0x0804,
    0x0A24,
    0x0C24,
    0x0C24,
    0x0C24,
    0x0A24,
    0x0C24,
    0x0C24,  # 0x40
    0x0C24,
    0x0A24,
    0x0C24,
    0x0C24,
    0x0C24,
    0x0C24,
    0x0C24,
    0x0A24,  # 0x48
    0x0C24,
    0x0C24,
    0x0C24,
    0x0C24,
    0x0C24,
    0x0A24,
    0x0C24,
    0x0C24,  # 0x50
    0x0C24,
    0x0824,
    0x0C24,
    0x0944,
    0x0804,
    0x0984,
    0x0804,
    0x0814,  # 0x58
    0x0804,
    0x0A04,
    0x0C04,
    0x0C04,
    0x0C04,
    0x0A04,
    0x0C04,
    0x0C04,  # 0x60
    0x0C04,
    0x0A04,
    0x0C04,
    0x0C04,
    0x0C04,
    0x0C04,
    0x0C04,
    0x0A04,  # 0x68
    0x0C04,
    0x0C04,
    0x0C04,
    0x0C04,
    0x0C04,
    0x0A04,
    0x0C04,
    0x0C04,  # 0x70
    0x0C04,
    0x0804,
    0x0C04,
    0x0944,
    0x0804,
    0x0984,
    0x0804,
    0x0000,  # 0x78
    0x0804,
    0x0000,
    0x0000,
    0x0000,
    0x0000,
    0x0000,
    0x0000,
    0x0000,  # 0x80
    0x0000,
    0x0000,
    0x0000,
    0x0000,
    0x0000,
    0x0000,
    0x0000,
    0x0000,  # 0x88
    0x0000,
    0x0000,
    0x0000,
    0x0000,
    0x0000,
    0x0000,
    0x0000,
    0x0000,  # 0x90
    0x0000,
    0x0000,
    0x0000,
    0x0000,
    0x0000,
    0x0000,
    0x0000,
    0x0000,  # 0x98
    0x0802,
    0x0844,
    0x0804,
    0x0804,
    0x0000,
    0x0804,
    0x0000,
    0x0804,  # 0xa0
    0x0804,
    0x0804,
    0x0804,
    0x0844,
    0x0000,
    0x0000,
    0x0000,
    0x0000,  # 0xa8
    0x0804,
    0x0804,
    0x0804,
    0x0804,
    0x0000,
    0x0804,
    0x0804,
    0x0804,  # 0xb0
    0x0000,
    0x0804,
    0x0804,
    0x0884,
    0x0804,
    0x0804,
    0x0000,
    0x0844,  # 0xb8
    0x0A24,
    0x0A24,
    0x0A24,
    0x0A24,
    0x0A24,
    0x0A24,
    0x0804,
    0x0C24,  # 0xc0
    0x0A24,
    0x0A24,
    0x0A24,
    0x0A24,
    0x0A24,
    0x0A24,
    0x0A24,
    0x0A24,  # 0xc8
    0x0000,
    0x0C24,
    0x0A24,
    0x0A24,
    0x0A24,
    0x0A24,
    0x0A24,
    0x0824,  # 0xd0
    0x0A24,
    0x0A24,
    0x0A24,
    0x0A24,
    0x0A24,
    0x0C24,
    0x0000,
    0x0804,  # 0xd8
    0x0A04,
    0x0A04,
    0x0A04,
    0x0A04,
    0x0A04,
    0x0A04,
    0x0804,
    0x0C04,  # 0xe0
    0x0A04,
    0x0A04,
    0x0A04,
    0x0A04,
    0x0A04,
    0x0A04,
    0x0A04,
    0x0A04,  # 0xe8
    0x0000,
    0x0C04,
    0x0A04,
    0x0A04,
    0x0A04,
    0x0A04,
    0x0A04,
    0x0804,  # 0xf0
    0x0A04,
    0x0A04,
    0x0A04,
    0x0A04,
    0x0A04,
    0x0C04,
    0x0000,
    0x0000,  # 0xf8
)


# -- C macro translations --------------------------------------------------
# Note: the C source defines ISUPPER/ISLOWER/ISALPHA/ISVOWEL macros over
# lsctype, but only ISUPPER + the OO bit are actually used by US/UK
# code paths — the L/LC/OO/C bits aren't set on ASCII letters in the
# US table (look at e.g. `'a' = ALWAYS+OO+PR` which has no LC bit).
# The ISLOWER/ISALPHA/ISVOWEL macros are only referenced by
# l_la_ru1.c (Latin-American Spanish). For US English use
# :mod:`dectalk.lts.char_features` (the ls_char_feat table) instead.


def is_upper(c: int) -> bool:
    """C macro ``ISUPPER(c) = (lsctype[c] & UU) != 0``.

    Correct for US English: the table sets ``UU`` on A-Z (latin-1 too).
    """
    return bool(lsctype[c & 0xFF] & UU)


def char_type(c: int) -> int:
    """Return the low-nibble TYPE field of ``lsctype[c]``.

    One of :data:`IGNORE`, :data:`BACKUP`, :data:`NEVER`, :data:`MIGHT`,
    :data:`ALWAYS`, :data:`PHONEME` — the word-character disposition
    used by the word-extraction state machine.
    """
    return lsctype[c & 0xFF] & TYPE


__all__ = [
    "ALWAYS",
    "BACKUP",
    "C_BIT",
    "FB",
    "IGNORE",
    "II",
    "LC",
    "LS",
    "MIGHT",
    "NEVER",
    "OO",
    "PHONEME",
    "PR",
    "RS",
    "TYPE",
    "UU",
    "L",
    "char_type",
    "is_upper",
    "lsctype",
]
