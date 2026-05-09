"""ARPABET phoneme inventory and phonological feature lookups.

ARPABET is the standard ASCII phoneme set used by CMUDict and many TTS
systems; DECtalk's internal notation can be mapped onto it. We use ARPABET
2-letter codes for the phoneme identifiers throughout the Python pipeline
because they are unambiguous, well-documented, and widely understood.

Each phoneme carries:

- :attr:`Phoneme.code`: the 2-letter ARPABET symbol.
- :attr:`Phoneme.kind`: vowel / stop / fricative / nasal / etc.
- :attr:`Phoneme.voiced`: True for voiced segments.
- :attr:`Phoneme.duration_ms`: nominal segment duration; the prosody pass
  scales this by stress, position, and rate.

The numerical durations come from common Klatt-synth defaults documented
in the speech-synthesis literature (Klatt 1980, Allen-Hunnicutt-Klatt 1987).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final


class PhonemeKind(Enum):
    """Coarse phonetic class of an English phoneme.

    The synthesizer uses this to pick the right voicing-source and
    parallel-formant amplitudes (e.g. fricatives drive the parallel branch
    via frication noise; stops produce a burst at release).
    """

    VOWEL = "vowel"
    DIPHTHONG = "diphthong"
    STOP = "stop"
    FRICATIVE = "fricative"
    AFFRICATE = "affricate"
    NASAL = "nasal"
    LIQUID = "liquid"
    GLIDE = "glide"
    SILENCE = "silence"


@dataclass(frozen=True, slots=True)
class Phoneme:
    """One phoneme entry: identifier, classification, and timing default.

    Attributes:
        code: 2-letter ARPABET code, uppercased.
        kind: Phonetic class (vowel, stop, fricative, …).
        voiced: True if the segment is voiced.
        duration_ms: Nominal segment duration in milliseconds; prosody
            scales this by stress and rate.
    """

    code: str
    kind: PhonemeKind
    voiced: bool
    duration_ms: int


# ------------------------------------------------------------------- vowels
_VOWEL_DURATION_MS: Final[int] = 100
_LONG_VOWEL_DURATION_MS: Final[int] = 140
_DIPHTHONG_DURATION_MS: Final[int] = 180

# Monophthongs and r-coloured vowels.
_VOWELS: Final[tuple[Phoneme, ...]] = (
    Phoneme("AA", PhonemeKind.VOWEL, voiced=True, duration_ms=_LONG_VOWEL_DURATION_MS),  # father
    Phoneme("AE", PhonemeKind.VOWEL, voiced=True, duration_ms=_VOWEL_DURATION_MS),  # cat
    Phoneme("AH", PhonemeKind.VOWEL, voiced=True, duration_ms=_VOWEL_DURATION_MS),  # but, sofa
    Phoneme("AO", PhonemeKind.VOWEL, voiced=True, duration_ms=_LONG_VOWEL_DURATION_MS),  # bought
    Phoneme("AX", PhonemeKind.VOWEL, voiced=True, duration_ms=70),  # schwa
    Phoneme("EH", PhonemeKind.VOWEL, voiced=True, duration_ms=_VOWEL_DURATION_MS),  # bet
    Phoneme("ER", PhonemeKind.VOWEL, voiced=True, duration_ms=_LONG_VOWEL_DURATION_MS),  # bird
    Phoneme("IH", PhonemeKind.VOWEL, voiced=True, duration_ms=_VOWEL_DURATION_MS),  # bit
    Phoneme("IY", PhonemeKind.VOWEL, voiced=True, duration_ms=_LONG_VOWEL_DURATION_MS),  # see
    Phoneme("UH", PhonemeKind.VOWEL, voiced=True, duration_ms=_VOWEL_DURATION_MS),  # book
    Phoneme("UW", PhonemeKind.VOWEL, voiced=True, duration_ms=_LONG_VOWEL_DURATION_MS),  # boot
)

_DIPHTHONGS: Final[tuple[Phoneme, ...]] = (
    Phoneme("AY", PhonemeKind.DIPHTHONG, voiced=True, duration_ms=_DIPHTHONG_DURATION_MS),  # buy
    Phoneme("AW", PhonemeKind.DIPHTHONG, voiced=True, duration_ms=_DIPHTHONG_DURATION_MS),  # cow
    Phoneme("EY", PhonemeKind.DIPHTHONG, voiced=True, duration_ms=_DIPHTHONG_DURATION_MS),  # bay
    Phoneme("OW", PhonemeKind.DIPHTHONG, voiced=True, duration_ms=_DIPHTHONG_DURATION_MS),  # boat
    Phoneme("OY", PhonemeKind.DIPHTHONG, voiced=True, duration_ms=_DIPHTHONG_DURATION_MS),  # boy
)

# --------------------------------------------------------------- consonants
_STOP_DURATION_MS: Final[int] = 80
_FRICATIVE_DURATION_MS: Final[int] = 100
_NASAL_DURATION_MS: Final[int] = 70
_LIQUID_DURATION_MS: Final[int] = 70
_GLIDE_DURATION_MS: Final[int] = 60

_CONSONANTS: Final[tuple[Phoneme, ...]] = (
    # Stops
    Phoneme("P", PhonemeKind.STOP, voiced=False, duration_ms=_STOP_DURATION_MS),
    Phoneme("B", PhonemeKind.STOP, voiced=True, duration_ms=_STOP_DURATION_MS),
    Phoneme("T", PhonemeKind.STOP, voiced=False, duration_ms=_STOP_DURATION_MS),
    Phoneme("D", PhonemeKind.STOP, voiced=True, duration_ms=_STOP_DURATION_MS),
    Phoneme("K", PhonemeKind.STOP, voiced=False, duration_ms=_STOP_DURATION_MS),
    Phoneme("G", PhonemeKind.STOP, voiced=True, duration_ms=_STOP_DURATION_MS),
    # Fricatives
    Phoneme("F", PhonemeKind.FRICATIVE, voiced=False, duration_ms=_FRICATIVE_DURATION_MS),
    Phoneme("V", PhonemeKind.FRICATIVE, voiced=True, duration_ms=_FRICATIVE_DURATION_MS),
    Phoneme("TH", PhonemeKind.FRICATIVE, voiced=False, duration_ms=_FRICATIVE_DURATION_MS),
    Phoneme("DH", PhonemeKind.FRICATIVE, voiced=True, duration_ms=_FRICATIVE_DURATION_MS),
    Phoneme("S", PhonemeKind.FRICATIVE, voiced=False, duration_ms=_FRICATIVE_DURATION_MS),
    Phoneme("Z", PhonemeKind.FRICATIVE, voiced=True, duration_ms=_FRICATIVE_DURATION_MS),
    Phoneme("SH", PhonemeKind.FRICATIVE, voiced=False, duration_ms=_FRICATIVE_DURATION_MS),
    Phoneme("ZH", PhonemeKind.FRICATIVE, voiced=True, duration_ms=_FRICATIVE_DURATION_MS),
    Phoneme("HH", PhonemeKind.FRICATIVE, voiced=False, duration_ms=_FRICATIVE_DURATION_MS),
    # Affricates
    Phoneme("CH", PhonemeKind.AFFRICATE, voiced=False, duration_ms=_FRICATIVE_DURATION_MS),
    Phoneme("JH", PhonemeKind.AFFRICATE, voiced=True, duration_ms=_FRICATIVE_DURATION_MS),
    # Nasals
    Phoneme("M", PhonemeKind.NASAL, voiced=True, duration_ms=_NASAL_DURATION_MS),
    Phoneme("N", PhonemeKind.NASAL, voiced=True, duration_ms=_NASAL_DURATION_MS),
    Phoneme("NG", PhonemeKind.NASAL, voiced=True, duration_ms=_NASAL_DURATION_MS),
    # Liquids
    Phoneme("L", PhonemeKind.LIQUID, voiced=True, duration_ms=_LIQUID_DURATION_MS),
    Phoneme("R", PhonemeKind.LIQUID, voiced=True, duration_ms=_LIQUID_DURATION_MS),
    # Glides
    Phoneme("W", PhonemeKind.GLIDE, voiced=True, duration_ms=_GLIDE_DURATION_MS),
    Phoneme("Y", PhonemeKind.GLIDE, voiced=True, duration_ms=_GLIDE_DURATION_MS),
)

_SILENCE: Final[Phoneme] = Phoneme("SIL", PhonemeKind.SILENCE, voiced=False, duration_ms=80)
"""Inter-word/utterance pause."""


# --------------------------------------------------- public lookup table --
PHONEMES: Final[dict[str, Phoneme]] = {
    p.code: p for p in (*_VOWELS, *_DIPHTHONGS, *_CONSONANTS, _SILENCE)
}
"""ARPABET code -> :class:`Phoneme`. Codes are case-insensitive on lookup
(see :func:`get_phoneme`)."""


def get_phoneme(code: str) -> Phoneme:
    """Look up a phoneme by ARPABET code.

    Strips any trailing stress digit (``0``, ``1``, ``2``) — CMUDict places
    stress markers on vowels (``AH1``); we treat them as the same phoneme
    here because stress is handled separately in the prosody pass.

    Args:
        code: ARPABET symbol, case-insensitive, optionally with a trailing
            stress digit.

    Returns:
        The :class:`Phoneme` entry.

    Raises:
        KeyError: If ``code`` is not a recognised ARPABET symbol.
    """
    upper = code.upper().rstrip("012")
    return PHONEMES[upper]
