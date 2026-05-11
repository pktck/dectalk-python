"""LTS spell-vs-speak decision for short all-caps "words".

When DECtalk encounters a short all-uppercase token like ``FBI`` or
``USA``, it has to decide whether to pronounce it as a word (``BUS``
→ "bus") or spell it out letter-by-letter (``FBI`` → "F B I"). The
decision uses three signals:

1. Length: 1-letter tokens are spoken; > 4-letter tokens are also
   spoken (presumed pronounceable). 2-to-4 letter tokens are
   candidates for spelling.
2. All-vowel tokens (``EOE``, ``AIA``) are spelled.
3. Pair-of-letters table lookup: if the *first two* letters form an
   illegal English word-start (e.g. ``FB``, ``CN``) or the *last two*
   letters (in reverse order) form an illegal word-end, the token is
   spelled.

Translated from:

- ``src/dapi/src/lts/l_us_sp1.c`` — the ``ls_spel_say_it`` function.
- ``src/dapi/src/lts/l_us_spe.c`` — the 26-by-26 ``spell_it`` byte table.
- ``src/dapi/src/lts/ls_defs.h`` — the ``SPELL_BEGIN`` / ``SPELL_END``
  feature-bit constants.

The C table indexing is asymmetric — ``spell_it[BC1][BC2]`` uses
forward letter order for the start (BC1 = first, BC2 = second),
``spell_it[EC1][EC2]`` uses reverse order for the end (EC1 = last,
EC2 = second-to-last). The same matrix encodes both directions; the
SPELL_BEGIN / SPELL_END bits differentiate which usage applies.
"""

from __future__ import annotations

from typing import Final

from dectalk.lts.char_features import is_vowel

# Feature-bit constants from ls_defs.h.

SPELL_END: Final[int] = 0x01
"""If a 2-letter pair appears at the *end* of a short word in reverse
order, ``spell_it[last][second_to_last] & SPELL_END`` triggers spelling."""

SPELL_BEGIN: Final[int] = 0x02
"""If a 2-letter pair appears at the *start* of a short word,
``spell_it[first][second] & SPELL_BEGIN`` triggers spelling."""


# 26-by-26 byte matrix from l_us_spe.c. Each cell holds 0..3:
#   bit 0 (SPELL_END):   if this pair (in reverse order) ends a short
#                        word, spell rather than speak.
#   bit 1 (SPELL_BEGIN): if this pair starts a short word, spell rather
#                        than speak.
# Indexing: row = first letter index, col = second letter index, both
# in [0, 25] computed as ``ord(ch) - ord('A')``.
spell_it: Final[bytes] = bytes.fromhex(
    "0000000000000000000000000000000000000000000000000100"
    "0002030300030303000303000203000303000303000303030003"
    "0003030300030301000303000302000303000303000303030001"
    "0003030200030303000303020302000303000303000300030003"
    "0000000000000000000000000000000000000000000000000000"
    "0003030300020303000103000302000303000303000303030003"
    "0003030300030201000303010300000303000303000301030003"
    "0002020300030203000302020303000203030202000303030003"
    "0200000002000000030000000000000000000000020000000300"
    "0003030300030303000203020303000303030303000303030003"
    "0003020300020301000303000300000303000203000300030003"
    "0003030300030302000303000303000303020303000302030003"
    "0003010300030202000303020201000303020203000303030003"
    "0003030300030202000303030202000303020303000302030003"
    "0000000002000000000000000000020000000000000000000300"
    "0003030300030301000303000200000203000201000303030003"
    "0003030300030303000303030303000303030303000303030003"
    "0003030200030301000303030303000303000303000303030003"
    "0002000200020200000200000000000003020200000000030003"
    "0002020300020301000303020002000203000002000300020003"
    "0200000003000000030000000000020000000000030000000300"
    "0003030300030303000303030303000303030303000303030003"
    "0003030200030301000303030303000303000303000303030003"
    "0003030300030303000303020302000303030303000303030003"
    "0000000000000000010000000000000000000000000000000100"
    "0003030200030303000303030302000303030303000303030002"
)
"""676 = 26-by-26 bytes. ``spell_it[row*26 + col]`` is the per-pair bitfield."""

assert len(spell_it) == 26 * 26, "spell_it must be exactly 676 bytes"


# -- Function translation --------------------------------------------------

_MAX_SPELL_LEN: Final[int] = 4
"""Words longer than this are always spoken; only 2..4 letter words can be
spelled out (after the all-vowel and pair-table checks)."""


def say_it(word: str) -> bool:
    """Return ``True`` if ``word`` should be spoken, ``False`` if spelled.

    Translation of ``ls_spel_say_it`` (``l_us_sp1.c:61``). The C version
    receives left/right ``LETTER *`` pointers; this Python version takes
    the same content as a string. Pre-conditions match the C version:

    - If any character is outside the A-Z range, return True (speak).
      The C version returns early on the first non-A-Z byte, leaving
      ``size`` partially counted. We do the same scan up front.
    - 1-letter words (or empty) are spoken.
    - All-vowel tokens are spelled.
    - 5+ letter tokens are spoken.
    - 2..4 letter tokens with consonants: spelled iff the start-pair has
      ``SPELL_BEGIN`` or the end-pair (in reverse order) has ``SPELL_END``.
    """
    # Pre-scan: any non-A-Z character → speak.
    for ch in word:
        if ch < "A" or ch > "Z":
            return True

    size = len(word)
    if size <= 1:
        return True

    if all(is_vowel(ord(ch)) for ch in word):
        return False

    if size > _MAX_SPELL_LEN:
        return True

    # spell_it[BC1][BC2] — forward order for word start.
    bc1 = ord(word[0]) - ord("A")
    bc2 = ord(word[1]) - ord("A")
    if spell_it[bc1 * 26 + bc2] & SPELL_BEGIN:
        return False

    # spell_it[EC1][EC2] — reverse order for word end (EC1 = last,
    # EC2 = second-to-last). Symmetric reuse of the same matrix.
    ec1 = ord(word[-1]) - ord("A")
    ec2 = ord(word[-2]) - ord("A")
    return not spell_it[ec1 * 26 + ec2] & SPELL_END


__all__ = [
    "SPELL_BEGIN",
    "SPELL_END",
    "say_it",
    "spell_it",
]
