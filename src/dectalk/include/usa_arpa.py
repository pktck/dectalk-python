"""Phoneme-code → 2-byte ARPABET ASCII map from ``usa_phon.tab``.

Translated from ``src/dapi/src/include/usa_phon.tab`` lines 117-249
(``const unsigned char usa_arpa[]``).

The kernel exposes this table via ``pKsd_t->arpabet`` (set by
``default_lang`` when US English is selected). The LTS engine reads
two bytes per slot to print the human-readable ARPABET name of a
phoneme code (e.g. code ``USPhoneme.IY`` → ``"iy"``).

Slots are 2 bytes wide:

- Slots 0-56 (US allophones used at runtime).
- Slots 57-70 are placeholders for an unused phoneme range.
- Slots 71-99 are zero-filled padding.
- Slots 100-122 are the stress + boundary control codes (BLOCK_RULES,
  S3, S2, S1, SEMPH, HAT_RISE, HAT_FALL, HAT_RF, SBOUND, MBOUND,
  HYPHEN, WBOUND, PPSTART, VPSTART, RELSTART, COMMA, PERIOD, QUEST,
  EXCLAIM, NEW_PARAGRAPH, SPECIALWORD, LINKRWORD, DOUBLCONS).

The table has 246 bytes total (123 slots, 2 bytes each); see
``tests/unit/test_usa_arpa.py`` for the parity check that re-parses
the C source.
"""

from __future__ import annotations

from typing import Final

_USA_ARPA_LEN: Final[int] = 246
"""Expected length of :data:`usa_arpa` (123 slots * 2 bytes)."""

usa_arpa: Final[bytes] = (
    b"_ iyiheyehaeaaay"
    b"awahaoowoyuhuwrr"
    b"yuaxixirerarorur"
    b"w yxr llhxrxlxm "
    b"n nxeldzenf v th"
    b"dhs z shzhp b t "
    b"d k g dxtxq chjh"
    b"dftzczlyrex1x2x3"
    b"x4x5x6x7x8x9z1\x00\x00"
    + b"\x00" * 16
    + b"\x00" * 16
    + b"\x00" * 16
    + b"\x00\x00\x00\x00\x00\x00\x00\x00"
    + b"~ = ` ' "
    + b'" / \\ /\\- * #   '
    + b"( ) ; , . ? ! + "
    + b"^ & > "
)

assert len(usa_arpa) == _USA_ARPA_LEN, f"expected {_USA_ARPA_LEN} bytes, got {len(usa_arpa)}"


__all__ = ["usa_arpa"]
