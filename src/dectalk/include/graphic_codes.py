"""Latin-1 right-side graphics codes used by LTS / KERNEL number rules.

Translated from ``src/dapi/src/include/l_all_ph.h`` — the
``CENT``…``SUPER_O`` block of ``#define``s naming high-bit Latin-1
characters that the C source treats specially when scanning text
(currency, fractions, superscripts, ordinal indicators). These
codes appear inline in the C source as bare ``0xA2``, ``0xBD``,
etc. literals; the named constants here make Python translations
of ``ls_util_*``, ``cm_*`` and ``ker_*`` self-documenting.
"""

from __future__ import annotations

from typing import Final

CENT: Final[int] = 0xA2
"""Cent sign ``¢`` (Latin-1)."""

STERLING: Final[int] = 0xA3
"""Pound-sterling sign ``£`` (Latin-1)."""

YEN: Final[int] = 0xA5
"""Yen sign ``¥`` (Latin-1)."""

SECTION: Final[int] = 0xA7
"""Section sign ``§`` (Latin-1)."""

DEGREE: Final[int] = 0xB0
"""Degree sign ``°`` (Latin-1)."""

PLUS_MINUS: Final[int] = 0xB1
"""Plus-minus sign ``±`` (Latin-1)."""

PARAGRAPH: Final[int] = 0xB6
"""Paragraph / pilcrow sign ``¶`` (Latin-1)."""

FOURTH: Final[int] = 0xBC
"""Vulgar fraction one-quarter ``¼`` (Latin-1)."""

HALF: Final[int] = 0xBD
"""Vulgar fraction one-half ``½`` (Latin-1)."""

SUPER_1: Final[int] = 0xB9
"""Superscript-1 ``¹`` (Latin-1)."""

SUPER_2: Final[int] = 0xB2
"""Superscript-2 ``²`` (Latin-1)."""

SUPER_3: Final[int] = 0xB3
"""Superscript-3 ``³`` (Latin-1)."""

SUPER_O: Final[int] = 0xBA
"""Masculine ordinal indicator ``º`` (Latin-1)."""

SUPER_A: Final[int] = 0xAA
"""Feminine ordinal indicator ``ª`` (Latin-1)."""


__all__ = [
    "CENT",
    "DEGREE",
    "FOURTH",
    "HALF",
    "PARAGRAPH",
    "PLUS_MINUS",
    "SECTION",
    "STERLING",
    "SUPER_1",
    "SUPER_2",
    "SUPER_3",
    "SUPER_A",
    "SUPER_O",
    "YEN",
]
