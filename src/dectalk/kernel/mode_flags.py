"""Kernel state ``modeflag`` and ``pronflag`` bits from esc.h.

Translated from ``src/dapi/src/include/esc.h``. These are 16-bit
flag values ORed together into:

- ``pKsd_t->modeflag`` — the kernel mode-bits read by LTS/CMD to
  decide between US/European number format, citation mode, spelling
  mode, etc. (Constants prefixed ``MODE_``.)
- ``pKsd_t->pronflag`` — the per-word pronunciation flags carrying
  dictionary-class hints (primary / alternate / noun / verb /
  adjective / function / interjection). (Constants prefixed ``PRON_``.)
"""

from __future__ import annotations

from typing import Final

# -- modeflag bits ----------------------------------------------------------

MODE_MATH: Final[int] = 0x0004
"""Mathematical pronunciation — read ``+`` as ``plus`` etc."""

MODE_EUROPE: Final[int] = 0x0008
"""European number format — flip ``.`` and ``,`` in numbers."""

MODE_SPELL: Final[int] = 0x0010
"""Spell all words letter-by-letter (override LTS)."""

MODE_NAME: Final[int] = 0x0040
"""Automatically detect proper names (ACNA mode)."""

MODE_HOMOGRAPH: Final[int] = 0x0080
"""Disambiguate homographs automatically using POS tagging."""

MODE_CITATION: Final[int] = 0x0100
"""Word-citation mode (deliberate, pause-after-each-word reading)."""

MODE_LATIN: Final[int] = 0x0200
"""Spanish Latin-American pronunciation mode."""

MODE_SESEO: Final[int] = 0x0200
"""Spanish seseo mode (alias of :data:`MODE_LATIN` — same bit)."""

MODE_TABLE: Final[int] = 0x0400
"""Table-reading mode (column-by-column / row-by-row pauses)."""

MODE_EMAIL: Final[int] = 0x1000
"""Email-reading mode — recognise @ / . in addresses."""

# -- pronflag bits ----------------------------------------------------------

PRON_DIC_PRIMARY: Final[int] = 0x0001
"""Pronunciation: use the primary dictionary entry."""

PRON_DIC_ALTERNATE: Final[int] = 0x0002
"""Pronunciation: use the alternate dictionary entry (rare homographs)."""

PRON_ACNA_NAME: Final[int] = 0x0004
"""Pronunciation: word is an ACNA (proper noun) name — apply name rules."""

PRON_DIC_NOUN: Final[int] = 0x0008
"""Pronunciation: word is a noun (homograph disambiguation)."""

PRON_DIC_VERB: Final[int] = 0x0010
"""Pronunciation: word is a verb (homograph disambiguation)."""

PRON_DIC_ADJECTIVE: Final[int] = 0x0020
"""Pronunciation: word is an adjective."""

PRON_DIC_FUNCTION: Final[int] = 0x0040
"""Pronunciation: word is a function word (article / preposition)."""

PRON_DIC_INTERJECTION: Final[int] = 0x0080
"""Pronunciation: word is an interjection."""

__all__ = [
    "MODE_CITATION",
    "MODE_EMAIL",
    "MODE_EUROPE",
    "MODE_HOMOGRAPH",
    "MODE_LATIN",
    "MODE_MATH",
    "MODE_NAME",
    "MODE_SESEO",
    "MODE_SPELL",
    "MODE_TABLE",
    "PRON_ACNA_NAME",
    "PRON_DIC_ADJECTIVE",
    "PRON_DIC_ALTERNATE",
    "PRON_DIC_FUNCTION",
    "PRON_DIC_INTERJECTION",
    "PRON_DIC_NOUN",
    "PRON_DIC_PRIMARY",
    "PRON_DIC_VERB",
]
