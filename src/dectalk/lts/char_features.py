"""Character-classification lookup tables used by the LTS module.

Translated from:

- ``src/dapi/src/lts/ls_char.h`` — the ``CFEAT_*`` feature-bit flags and
  the ``IS_LOWER`` / ``IS_UPPER`` / ``IS_ALPHA`` / ``IS_DIGIT`` /
  ``IS_PUNCT`` / ``IS_VOWEL`` / ``IS_CONS`` macros.
- ``src/dapi/src/lts/l_us_cha.c`` — declares the four 256-entry tables:
  ``ls_fold``, ``ls_lower``, ``ls_upper``, ``ls_char_feat``. The table
  bodies come from corresponding ``.tab`` files under
  ``src/dapi/src/include/``.

Each table is indexed by an 8-bit character value (0..255). The lookup
tables return:

- :data:`ls_lower` / :data:`ls_upper`: the case-folded character.
- :data:`ls_fold`: the case-AND-multinational-folded character — e.g.
  ``À`` (0xC0) folds to ``'a'`` (0x61). Used by the lexicon to match
  accented inputs against the dictionary's ASCII keys.
- :data:`ls_char_feat`: a bit-OR of :data:`CFEAT_*` flags describing
  the character's class.

The table bytes are committed as ``bytes.fromhex(...)`` literals
generated from the C ``.tab`` files; a parity test re-parses the
``.tab`` files at test time and asserts every byte matches.
"""

from __future__ import annotations

from typing import Final

# -- CFEAT_* feature bits ---------------------------------------------------

CFEAT_null: Final[int] = 0x00
"""Placeholder — character has no recognised features."""

CFEAT_lower: Final[int] = 0x01
"""ASCII lower-case letter ``a`` .. ``z`` (plus latin-1 lower equivalents)."""

CFEAT_upper: Final[int] = 0x02
"""ASCII upper-case letter ``A`` .. ``Z`` (plus latin-1 upper equivalents)."""

CFEAT_punct: Final[int] = 0x04
r"""Punctuation: ``! " # $ % & ' ( ) , . / : ; ? @ \ [ ] ^ _ ` { | } ~``."""

CFEAT_non_alpha: Final[int] = 0x08
"""Printable non-alphabetic / non-digit characters not classified as punct."""

CFEAT_digit: Final[int] = 0x10
"""ASCII digit ``0`` .. ``9``."""

CFEAT_cons: Final[int] = 0x20
"""Consonant (combined with :data:`CFEAT_lower` or :data:`CFEAT_upper`)."""

CFEAT_vowel: Final[int] = 0x40
"""Vowel (combined with :data:`CFEAT_lower` or :data:`CFEAT_upper`)."""


# -- Lookup tables ---------------------------------------------------------
# Generated from src/dapi/src/include/ls_{fold,lower,upper,feat}.tab.
# Each line below is 32 bytes; the table size matches the C source byte-
# for-byte. ls_char_feat has 258 bytes because the C source intentionally
# emits 2 trailing CFEAT_null entries beyond the 256-byte range.

ls_fold: Final[bytes] = bytes.fromhex(
    "000102030405060708090a0b0c0d0e0f"
    "101112131415161718191a1b1c1d1e1f"
    "202122232425262728292a2b2c2d2e2f"
    "303132333435363738393a3b3c3d3e3f"
    "406162636465666768696a6b6c6d6e6f"
    "707172737475767778797a5b5c5d5e5f"
    "606162636465666768696a6b6c6d6e6f"
    "707172737475767778797a7b7c7d7e7f"
    "808182838485868788898a8b8c8d8e8f"
    "909192939495969798999a9b9c9d9e9f"
    "a0a1a2a3a4a5a6a7a8a961abacadaeaf"
    "b0b13233b475b6b7b8316fbbbcbdbebf"
    "61616161616165636565656569696969"
    "d06e6f6f6f6f6f656f7575757579de73"
    "61616161616165636565656569696969"
    "f06e6f6f6f6f6f656f7575757579feff"
)
"""Multi-national + case folding: 256 bytes; index by ``ord(ch) & 0xff``."""

ls_lower: Final[bytes] = bytes.fromhex(
    "000102030405060708090a0b0c0d0e0f"
    "101112131415161718191a1b1c1d1e1f"
    "202122232425262728292a2b2c2d2e2f"
    "303132333435363738393a3b3c3d3e3f"
    "406162636465666768696a6b6c6d6e6f"
    "707172737475767778797a5b5c5d5e5f"
    "606162636465666768696a6b6c6d6e6f"
    "707172737475767778797a7b7c7d7e7f"
    "808182838485868788898a8b8c8d8e8f"
    "909192939495969798999a9b9c9d9e9f"
    "a0a1a2a3a4a5a6a7a8a9aaabacadaeaf"
    "b0b1b2b3b4b5b6b7b8b9babbbcbdbebf"
    "e0e1e2e3e4e5c6e7e8e9eaebecedeeef"
    "d0f1f2f3f4f5f6d7f8f9fafbfcfddedf"
    "e0e1e2e3e4e5e6e7e8e9eaebecedeeef"
    "f0f1f2f3f4f5f6f7f8f9fafbfcfdfeff"
)
"""Case-fold to lower: 256 bytes; index by ``ord(ch) & 0xff``."""

ls_upper: Final[bytes] = bytes.fromhex(
    "000102030405060708090a0b0c0d0e0f"
    "101112131415161718191a1b1c1d1e1f"
    "202122232425262728292a2b2c2d2e2f"
    "303132333435363738393a3b3c3d3e3f"
    "404142434445464748494a4b4c4d4e4f"
    "505152535455565758595a5b5c5d5e5f"
    "604142434445464748494a4b4c4d4e4f"
    "505152535455565758595a7b7c7d7e7f"
    "808182838485868788898a8b8c8d8e8f"
    "909192939495969798999a9b9c9d9e9f"
    "a0a1a2a3a4a5a6a7a8a9aaabacadaeaf"
    "b0b1b2b3b4b5b6b7b8b9babbbcbdbebf"
    "c0c1c2c3c4c5c6c7c8c9cacbcccdcecf"
    "d0d1d2d3d4d5d6d7d8d9dadbdcdddedf"
    "c0c1c2c3c4c5e6c7c8c9cacbcccdcecf"
    "f0d1d2d3d4d5d6f7d8d9dadbdcddfeff"
)
"""Case-fold to upper: 256 bytes; index by ``ord(ch) & 0xff``."""

ls_char_feat: Final[bytes] = bytes.fromhex(
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0004040808080004080808080404040410101010101010101010040408080804"
    "0842222222422222224222222222224222222222224222222262220004080800"
    "0841212121412121214121212121214121212121214121212161210808080800"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000001010000000000000000010101000"
    "4242424242420022424242424242424200424242424242004242424242420023"
    "4141414141410021414141414141414100414141414141004141414141414108"
    "0000"
)
"""Per-character feature bits: **258 bytes** (the C source emits 2 trailing
zeros after the 256-byte range; mirror that exactly for sizeof()-parity)."""


# -- IS_* helper functions reproducing the C macros -------------------------


def is_lower(c: int) -> bool:
    """C macro ``IS_LOWER(c)``: True if ``c`` is an ASCII or latin-1 lower-case letter."""
    return bool(ls_char_feat[c & 0xFF] & CFEAT_lower)


def is_upper(c: int) -> bool:
    """C macro ``IS_UPPER(c)``: True if ``c`` is an ASCII or latin-1 upper-case letter."""
    return bool(ls_char_feat[c & 0xFF] & CFEAT_upper)


def is_alpha(c: int) -> bool:
    """C macro ``IS_ALPHA(c)``: True if ``c`` is a letter."""
    return bool(ls_char_feat[c & 0xFF] & (CFEAT_lower | CFEAT_upper))


def is_digit(c: int) -> bool:
    """C macro ``IS_DIGIT(c)``: True if ``c`` is an ASCII digit ``0``..``9``."""
    return bool(ls_char_feat[c & 0xFF] & CFEAT_digit)


def is_punct(c: int) -> bool:
    """C macro ``IS_PUNCT(c)``: True if ``c`` is a punctuation mark."""
    return bool(ls_char_feat[c & 0xFF] & CFEAT_punct)


def is_vowel(c: int) -> bool:
    """C macro ``IS_VOWEL(c)``: True if ``c`` is a vowel (case-insensitive)."""
    return bool(ls_char_feat[c & 0xFF] & CFEAT_vowel)


def is_cons(c: int) -> bool:
    """C macro ``IS_CONS(c)``: True if ``c`` is a consonant (case-insensitive)."""
    return bool(ls_char_feat[c & 0xFF] & CFEAT_cons)


__all__ = [
    "CFEAT_cons",
    "CFEAT_digit",
    "CFEAT_lower",
    "CFEAT_non_alpha",
    "CFEAT_null",
    "CFEAT_punct",
    "CFEAT_upper",
    "CFEAT_vowel",
    "is_alpha",
    "is_cons",
    "is_digit",
    "is_lower",
    "is_punct",
    "is_upper",
    "is_vowel",
    "ls_char_feat",
    "ls_fold",
    "ls_lower",
    "ls_upper",
]
