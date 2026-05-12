"""``lflag`` word-state flag bits from ls_defs.h.

Translated from ``src/dapi/src/lts/ls_defs.h`` lines 569-580 —
the ``lflag`` bit-field that ls_task.c (formerly ls1.c) sets as
it scans a word looking for left/right strippable characters,
digits, slashes, and other word-shape features. These bits then
control downstream LTS-engine decisions (whether to spell, treat
as a compound, etc.).
"""

from __future__ import annotations

from typing import Final

LSTRIP: Final[int] = 0x0001
"""Left stripping was done on the word."""

RSTRIP: Final[int] = 0x0002
"""Right stripping was done on the word."""

DIGSLSH: Final[int] = 0x0004
"""Word has at least one digit or slash."""

SQUOTE: Final[int] = 0x0008
"""Word contains a single quote (apostrophe / contraction)."""

HVOWEL: Final[int] = 0x0010
"""Word has at least one vowel."""

HCONS: Final[int] = 0x0020
"""Word has at least one consonant."""

HHYPHEN: Final[int] = 0x0040
"""Word has a hyphen — possible compound."""

HNONY: Final[int] = 0x0080
"""Word has at least one non-``y`` character."""


__all__ = [
    "DIGSLSH",
    "HCONS",
    "HHYPHEN",
    "HNONY",
    "HVOWEL",
    "LSTRIP",
    "RSTRIP",
    "SQUOTE",
]
