"""Sentence-level and stress-level prosody.

Two prosody passes layered on top of each other:

1. **Declination contour** — F0 starts ~15% above the voice's baseline,
   falls through the utterance, and dips further on the final syllable.
   Rising punctuation (``?``) inverts the trailing slope.

2. **Stress accent** — primary-stressed vowels (``AH1``, ``IY1`` etc. —
   stress digit ``1``) get a brief F0 boost and a slight duration
   stretch. Secondary-stressed vowels (``2``) get a smaller boost.
   Unstressed vowels (``0``) are slightly attenuated. The result is
   that a word like ``"BANANA"`` with phonemes ``B AH0 N AE1 N AH0``
   has audible accent on the middle syllable.

Both passes return per-phoneme multipliers; the sequencer applies them
on top of each frame's F0 / duration.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

# Maximum start-of-utterance pitch boost as a multiplicative factor. ~1.15
# adds ~2 semitones on top of the baseline.
_DECLINATION_START: Final[float] = 1.15

# End-of-utterance dip (statement) as a multiplicative factor.
_DECLINATION_END_STATEMENT: Final[float] = 0.88

# End-of-utterance rise (question).
_DECLINATION_END_QUESTION: Final[float] = 1.20

# Per-phoneme dip applied to the very last segment to give a clear cadence.
_FINAL_DIP_FRACTION: Final[float] = 0.85

# Stress-accent multipliers applied on top of the declination contour.
_STRESS_F0: Final[dict[str, float]] = {
    "1": 1.10,  # primary stress: F0 +10%
    "2": 1.04,  # secondary stress
    "0": 0.94,  # unstressed: F0 -6%
}

_STRESS_DURATION: Final[dict[str, float]] = {
    "1": 1.20,  # primary stress: 20% longer
    "2": 1.05,
    "0": 0.85,  # unstressed: 15% shorter
}


def f0_contour(phonemes: Sequence[str], *, question: bool = False) -> list[float]:
    """Compute a per-phoneme F0 multiplier contour for the given segment.

    Combines the sentence-level declination contour with a per-phoneme
    stress accent derived from the trailing ``0/1/2`` digit on each
    ARPABET symbol.

    Args:
        phonemes: Flat ARPABET phoneme stream (may include ``"SIL"``).
        question: If True, the trailing slope rises (yes/no question
            intonation); otherwise it falls (statement declination).

    Returns:
        List of multiplicative factors, one per phoneme, suitable for
        scaling each frame's ``F0`` field.
    """
    n = len(phonemes)
    if n == 0:
        return []

    end_factor = _DECLINATION_END_QUESTION if question else _DECLINATION_END_STATEMENT
    contour: list[float] = []
    for i, code in enumerate(phonemes):
        if code == "SIL":
            contour.append(1.0)
            continue
        # Declination component.
        alpha = i / max(1, n - 1)
        decl = _DECLINATION_START * (1 - alpha) + end_factor * alpha
        # Stress accent component (multiplies the declination value).
        stress_digit = code[-1] if code and code[-1].isdigit() else ""
        stress = _STRESS_F0.get(stress_digit, 1.0)
        contour.append(decl * stress)

    if not question:
        for i in range(n - 1, -1, -1):
            if phonemes[i] != "SIL":
                contour[i] *= _FINAL_DIP_FRACTION
                break
    return contour


def duration_factors(phonemes: Sequence[str]) -> list[float]:
    """Compute per-phoneme duration multipliers from stress digits.

    Stressed vowels stretch by 20% (primary) or 5% (secondary);
    unstressed vowels compress by 15%. Consonants and pauses pass
    through unchanged.

    Args:
        phonemes: Flat ARPABET phoneme stream.

    Returns:
        List of duration multipliers, one per phoneme.
    """
    out: list[float] = []
    for code in phonemes:
        if code == "SIL" or not code:
            out.append(1.0)
            continue
        last = code[-1]
        if last.isdigit():
            out.append(_STRESS_DURATION.get(last, 1.0))
        else:
            out.append(1.0)
    return out


def looks_like_question(text: str) -> bool:
    """Return True if the text segment ends with ``?`` (trailing whitespace tolerated)."""
    return text.rstrip().endswith("?")
