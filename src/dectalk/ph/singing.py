"""Singing mode: per-phoneme pitch and duration markers.

DECtalk's singing mode lets the input specify a fixed pitch and duration
for each phoneme via a ``<duration_ms,tone>`` suffix. For example::

    "HH<300,5> AH<300,7> L<300,8> OW<400,9>"

The tone number is a chromatic pitch-class index above some baseline.
We map tone 1 -> A2 (110 Hz) by default; each step is one chromatic
semitone (multiply by 2**(1/12)). Duration overrides the phoneme's
nominal length.

This module exposes a small parser that consumes singing-mode tokens
and produces ``(code, duration_ms_or_None, pitch_hz_or_None)`` triples
the sequencer can act on.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final

# Base pitch for tone number 1 (A2 = 110 Hz). Successive tones are one
# chromatic semitone apart.
_TONE_BASE_HZ: Final[float] = 110.0
_SEMITONE_RATIO: Final[float] = 2.0 ** (1.0 / 12.0)

_SINGING_RE: Final[re.Pattern[str]] = re.compile(r"([A-Za-z]+\d?)\s*<\s*(\d+)\s*,\s*(\d+)\s*>")


@dataclass(frozen=True, slots=True)
class SingingNote:
    """One scheduled phoneme with optional fixed pitch and duration.

    Attributes:
        code: ARPABET phoneme code (uppercased).
        duration_ms: Override duration in milliseconds, or None to use
            the phoneme's nominal default.
        pitch_hz: Override pitch in Hertz, or None to use the prosody
            contour's pitch.
    """

    code: str
    duration_ms: int | None = None
    pitch_hz: float | None = None


def tone_to_hz(tone: int) -> float:
    """Convert a DECtalk tone number to a frequency in Hz.

    Args:
        tone: Tone number (1-based; 1 -> A2 = 110 Hz, 13 -> A3 = 220 Hz, …).

    Returns:
        Pitch in Hertz.
    """
    return _TONE_BASE_HZ * (_SEMITONE_RATIO ** (tone - 1))


def parse_singing(source: str) -> list[SingingNote]:
    """Parse a singing-mode phoneme string into :class:`SingingNote` triples.

    Tokens not matching the ``<dur,tone>`` syntax are emitted with both
    overrides set to None — those phonemes use the default duration and
    are subject to the normal prosody contour.

    Args:
        source: Whitespace-separated phoneme tokens, optionally with
            ``<duration_ms,tone>`` suffixes.

    Returns:
        Ordered list of :class:`SingingNote`.
    """
    notes: list[SingingNote] = []
    for tok in source.split():
        m = _SINGING_RE.fullmatch(tok)
        if m is None:
            notes.append(SingingNote(code=tok.upper()))
            continue
        code = m.group(1).upper()
        dur = int(m.group(2))
        tone = int(m.group(3))
        notes.append(SingingNote(code=code, duration_ms=dur, pitch_hz=tone_to_hz(tone)))
    return notes


def notes_to_codes(notes: Iterable[SingingNote]) -> list[str]:
    """Return just the phoneme codes from a singing-note stream."""
    return [n.code for n in notes]
