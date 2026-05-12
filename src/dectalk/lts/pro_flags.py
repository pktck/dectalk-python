"""PRO_* prosody-marker bit flags from ls_data.h.

Translated from ``src/dapi/src/lts/ls_data.h``. The LTS task pipeline
maintains a per-word ``pro_markers`` array of these bit flags marking
each position's prosody-relevant features:

- Punctuation parens / quotes (``PRO_OPEN_PAREN`` etc.)
- Hyphens (``PRO_DASH``)
- Form-class hints (``PRO_CONJ`` / ``PRO_FUNC`` / ``PRO_PREP``)
- Trigger words (``PRO_THAT`` / ``PRO_MULTI_CONJ``)
- Phrase-break hints (``PRO_OPT_BREAK`` / ``PRO_REQ_BREAK``)
"""

from __future__ import annotations

from typing import Final

PRO_OPEN_PAREN: Final[int] = 0x00000001
"""Opening parenthesis at this position."""

PRO_CLOSE_PAREN: Final[int] = 0x00000002
"""Closing parenthesis at this position."""

PRO_OPEN_QUOTE: Final[int] = 0x00000004
"""Opening quotation mark."""

PRO_CLOSE_QUOTE: Final[int] = 0x00000008
"""Closing quotation mark."""

PRO_DASH: Final[int] = 0x00000010
"""Dash / hyphen."""

PRO_CONJ: Final[int] = 0x00000020
"""Word at this position is a conjunction."""

PRO_FUNC: Final[int] = 0x00000040
"""Word at this position is a function word."""

PRO_PREP: Final[int] = 0x00000080
"""Word at this position is a preposition."""

PRO_THAT: Final[int] = 0x00000100
"""Word at this position is ``that``."""

PRO_MULTI_CONJ: Final[int] = 0x00000200
"""Multi-word conjunction begins here (e.g. ``as well as``)."""

PRO_OPT_BREAK: Final[int] = 0x00400000
"""Optional phrase break — prosodically helpful but not required."""

PRO_REQ_BREAK: Final[int] = 0x00800000
"""Required phrase break — must be honoured for prosody correctness."""


__all__ = [
    "PRO_CLOSE_PAREN",
    "PRO_CLOSE_QUOTE",
    "PRO_CONJ",
    "PRO_DASH",
    "PRO_FUNC",
    "PRO_MULTI_CONJ",
    "PRO_OPEN_PAREN",
    "PRO_OPEN_QUOTE",
    "PRO_OPT_BREAK",
    "PRO_PREP",
    "PRO_REQ_BREAK",
    "PRO_THAT",
]
