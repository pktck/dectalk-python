"""Reference Klatt frame definitions for steady-state vowels.

Provides one :class:`LLFrame` per English monophthong with formant
frequencies and bandwidths drawn from Klatt's 1980 reference paper. Useful
for smoke-testing the synthesizer pipeline before the full text-to-speech
front-end is in place.
"""

from __future__ import annotations

from typing import Final

from dectalk.hlsyn.llsyn import LLFrame, Speaker
from dectalk.hlsyn.voice import SOURCE_NATURAL


def default_speaker(sr_hz: int = 11025) -> Speaker:
    """Build a generic Klatt speaker definition for testing.

    Approximates Perfect Paul: 11025 Hz sample rate, 5 cascade formants,
    natural KLGLOT88 source, modest gain.

    Args:
        sr_hz: Sample rate. DECtalk's native rate is 11025 Hz.

    Returns:
        A :class:`Speaker` with sensible defaults.
    """
    samples_per_frame = round(sr_hz * 0.01)  # ~10 ms frames
    return Speaker(
        DU=0,
        UI=samples_per_frame,
        SR=sr_hz,
        NF=5,
        SS=SOURCE_NATURAL,
        RS=8191,
        SB=0,
        CP=0,
        OS=0,
        GV=60,
        GH=60,
        GF=60,
    )


def _vowel(*, f1: int, b1: int, f2: int, b2: int, f3: int, b3: int) -> LLFrame:
    """Build a steady-vowel frame with neutral defaults for higher formants."""
    return LLFrame(
        F0=1220,  # 122 Hz
        AV=60,
        OQ=50,
        SQ=200,
        TL=0,
        FL=0,
        DI=0,
        Ah=0,
        Af=0,
        F1=f1,
        B1=b1,
        F2=f2,
        B2=b2,
        F3=f3,
        B3=b3,
        F4=3500,
        B4=250,
        F5=4500,
        B5=300,
    )


# Klatt 1980 formant references for adult male English vowels (Hz).
# These are the canonical values widely cited in speech-synthesis literature.
AH: Final[LLFrame] = _vowel(f1=730, b1=90, f2=1090, b2=110, f3=2440, b3=170)
"""Open-mid back unrounded — as in "father"."""

EE: Final[LLFrame] = _vowel(f1=270, b1=60, f2=2290, b2=90, f3=3010, b3=170)
"""Close front unrounded — as in "see"."""

OO: Final[LLFrame] = _vowel(f1=300, b1=70, f2=870, b2=80, f3=2240, b3=160)
"""Close back rounded — as in "boot"."""

EH: Final[LLFrame] = _vowel(f1=530, b1=80, f2=1840, b2=110, f3=2480, b3=170)
"""Open-mid front unrounded — as in "bet"."""

AW: Final[LLFrame] = _vowel(f1=570, b1=80, f2=840, b2=80, f3=2410, b3=170)
"""Open-mid back rounded — as in "bought"."""

VOWELS: Final[dict[str, LLFrame]] = {
    "ah": AH,
    "ee": EE,
    "oo": OO,
    "eh": EH,
    "aw": AW,
}
"""Lookup of vowel id -> reference :class:`LLFrame`."""
