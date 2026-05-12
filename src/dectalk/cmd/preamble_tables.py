"""Static phoneme-stream preambles for the ``cm_cmd_preamble`` handler.

Translated from ``src/dapi/src/cmd/cm_copt.c``. These five fixed
phoneme streams are injected by the C library when the inline
command ``[:cmd preamble N]`` fires — they speak prepended labels
like "Message," / "Message is," / "Message from," that DECtalk's
accessibility modes insert before each input chunk.

Each record is a ``Phoneme(phone, dur, pitch, nextra)`` tuple
matching the C ``struct phoneme_s``. The ``phone`` field is a packed
U16:

    bits 0-7   phoneme / control code (US_M, S2, WBOUND, COMMA, ...)
    bits 8-12  font code (always PFUSA = 0x1E for US English)
    bits 13+   N-extra encoding (0 = scalar, 2 = pre-spelled)

For example, ``0x5E1F`` decodes as nextra=2, font=PFUSA, code=US_M.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class Phoneme:
    """One C ``struct phoneme_s`` record (packed phone code + prosody)."""

    phone: int
    """Packed code: bits 0-7 = phoneme/control, 8-12 = font, 13+ = nextra."""

    dur: int
    """Duration override in milliseconds, 0 = use default."""

    pitch: int
    """Pitch override (semitones), 0 = use default."""

    nextra: int
    """Extra-encoding hint matching the high bits of ``phone``."""


# Preamble 1: "Message is, "

preamble_1: Final[tuple[Phoneme, ...]] = (
    Phoneme(24095, 0, 0, 2),
    Phoneme(7782, 0, 0, 0),
    Phoneme(24068, 0, 0, 2),
    Phoneme(24105, 0, 0, 2),
    Phoneme(24082, 0, 0, 2),
    Phoneme(24119, 0, 0, 2),
    Phoneme(7791, 0, 0, 0),
    Phoneme(24066, 0, 0, 2),
    Phoneme(24106, 0, 0, 2),
    Phoneme(7795, 0, 0, 0),
    Phoneme(7791, 0, 0, 0),
)

# Preamble 2a: "Message" (first half of "Message is")

preamble_2a: Final[tuple[Phoneme, ...]] = (
    Phoneme(24095, 0, 0, 2),
    Phoneme(7782, 0, 0, 0),
    Phoneme(24068, 0, 0, 2),
    Phoneme(24105, 0, 0, 2),
    Phoneme(24082, 0, 0, 2),
    Phoneme(24119, 0, 0, 2),
    Phoneme(7791, 0, 0, 0),
)

# Preamble 2b: ", is" (second half of "Message is")

preamble_2b: Final[tuple[Phoneme, ...]] = (
    Phoneme(24066, 0, 0, 2),
    Phoneme(24106, 0, 0, 2),
    Phoneme(7795, 0, 0, 0),
    Phoneme(7791, 0, 0, 0),
)

# Preamble 3a: "Message from" (first half of "Message from ___")

preamble_3a: Final[tuple[Phoneme, ...]] = (
    Phoneme(24095, 0, 0, 2),
    Phoneme(7782, 0, 0, 0),
    Phoneme(24068, 0, 0, 2),
    Phoneme(24105, 0, 0, 2),
    Phoneme(24082, 0, 0, 2),
    Phoneme(24119, 0, 0, 2),
    Phoneme(7791, 0, 0, 0),
    Phoneme(24101, 0, 0, 2),
    Phoneme(24090, 0, 0, 2),
    Phoneme(24073, 0, 0, 2),
    Phoneme(24095, 0, 0, 2),
    Phoneme(7791, 0, 0, 0),
)

# Preamble 3b: ", is" (second half of "Message from ___, is")

preamble_3b: Final[tuple[Phoneme, ...]] = (
    Phoneme(24066, 0, 0, 2),
    Phoneme(24106, 0, 0, 2),
    Phoneme(7795, 0, 0, 0),
    Phoneme(7791, 0, 0, 0),
)


__all__ = [
    "Phoneme",
    "preamble_1",
    "preamble_2a",
    "preamble_2b",
    "preamble_3a",
    "preamble_3b",
]
