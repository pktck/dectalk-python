"""Sentence-level F0 contour (intonation).

A monotone synth sounds like a robot. This module applies a simple but
effective declination contour: F0 starts a few semitones above the
voice's baseline, falls slowly through the utterance, and dips further
at the final syllable. Rising punctuation (``?``) inverts the trailing
slope so questions sound like questions.

The contour is a sequence of multipliers (one per phoneme) that the
sequencer applies on top of the voice preset's baseline F0. Pauses
trigger a small reset toward baseline so each clause starts fresh.
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


def f0_contour(phonemes: Sequence[str], *, question: bool = False) -> list[float]:
    """Compute a per-phoneme F0 multiplier contour for the given segment.

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
            # Pauses reset toward baseline so the next clause starts fresh.
            contour.append(1.0)
            continue
        # Linear interpolation start -> end across the phonemes.
        alpha = i / max(1, n - 1)
        factor = _DECLINATION_START * (1 - alpha) + end_factor * alpha
        contour.append(factor)

    if not question and contour:
        # Apply the extra final-dip on the last voiced segment for a clear
        # cadence — a hallmark of statement intonation.
        for i in range(n - 1, -1, -1):
            if phonemes[i] != "SIL":
                contour[i] *= _FINAL_DIP_FRACTION
                break
    return contour


def looks_like_question(text: str) -> bool:
    """Return True if the text segment ends with ``?`` (with trailing whitespace allowed)."""
    return text.rstrip().endswith("?")
