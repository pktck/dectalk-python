"""Sentence-level and stress-level prosody aligned with FONIX C tables.

The shape of the contour is structured to track ``Ph_inton2.c`` rather
than the simple multiplicative ramp the earlier implementation used.
Three layers, in order:

1. **Declination** — a gentle ~10 % start-of-utterance rise that
   linearly returns to the voice's baseline by sentence end. This is
   the slow background fall.

2. **Stress accents with phrase-position decay** — each stressed
   syllable gets a discrete F0 bump, but the size of the bump shrinks
   as accents accumulate (primary stress on the 4th accent is much
   smaller than on the 1st). Mirrors C's
   ``us_f0_mphrase_position[] = {160, 80, 60, 40, 30, 20, 20, 5}``.

3. **Final-syllable gesture** — for declaratives, the last vowel
   drops sharply *below* baseline (matches C's
   ``F0_FINAL_FALL = 550``). For yes/no questions, the last syllable
   rises sharply (matches C's `F0_QGesture1/2`). The earlier
   "linear-rising contour for the entire question" approach has been
   replaced with this localised gesture so the question contour
   keeps its English-like shape rather than feeling like a monotone
   sweep.

The earlier per-segment audio-level smoothing (the sequencer's linear
frame interpolation across the first half of each segment) still
applies, so per-phoneme jumps still translate into smooth audio
transitions rather than discrete steps.

See ``docs/c_audit/prosody.md`` for the full C-vs-Python audit that
informed this layout.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

# ---------------------------------------------------------------------------
# Declination
# ---------------------------------------------------------------------------

# Baseline declination is gentler than before (10 % rise → baseline)
# so the larger pitch gestures come from stress accents and the
# final-syllable drop, not from a global ramp. The C source uses an
# impulse-driven model with no global ramp at all; this is the
# closest linear approximation that doesn't fight the per-accent
# motion.
_DECLINATION_START: Final[float] = 1.10
_DECLINATION_END: Final[float] = 0.92

# Final-syllable drop for declarative sentences. Applied multiplicatively
# on top of the declination, on the *last vowel* of the utterance
# (not just the last phoneme — coda consonants don't carry F0).
# 0.78 takes a 0.92-baseline last-vowel down to 0.72 of base F0,
# which on a 100 Hz voice is a 28 Hz drop — in line with C's
# F0_FINAL_FALL = 550 (Hz x 10) ≈ 55 Hz, halved because some of the
# fall is already absorbed by the declination.
_FINAL_FALL_FRACTION: Final[float] = 0.78

# Final-syllable rise for yes/no questions. Replaces the old
# whole-utterance rising contour; localising it keeps the rest of
# the sentence sounding declarative the way English questions
# actually do.
_FINAL_RISE_FRACTION: Final[float] = 1.32

# ---------------------------------------------------------------------------
# Stress accents
# ---------------------------------------------------------------------------

# Per-stress F0 deltas (added to 1.0 for the multiplier). These are
# the *first-accent* deltas; later accents are scaled down via
# `_PHRASE_POSITION_DECAY`. Mirrors the relative magnitudes of C's
# `us_f0_mstress_level[] = {1, 81, 61, 161}` (Hz x 10).
_STRESS_F0_DELTA: Final[dict[str, float]] = {
    "1": 0.35,  # primary  → +35 % at first accent
    "2": 0.18,  # secondary → +18 %
    "0": -0.08,  # unstressed -> -8 %
}

# Phrase-position decay for stress F0. Index 0 is the first stress
# accent, index 1 is the second, etc.; once we run out of entries
# we use the last value. Tracks C's
# `us_f0_mphrase_position[] = {160, 80, 60, 40, 30, 20, 20, 5}`
# (normalised so position 0 → 1.0; each subsequent position is the
# original ratio).
_PHRASE_POSITION_DECAY: Final[tuple[float, ...]] = (
    1.00,  # 1st accent
    0.50,  # 2nd: 80 / 160
    0.38,  # 3rd: 60 / 160
    0.25,  # 4th: 40 / 160
    0.19,  # 5th: 30 / 160
    0.13,  # 6th: 20 / 160
    0.13,  # 7th: 20 / 160
    0.03,  # 8th+: 5 / 160
)

# ---------------------------------------------------------------------------
# Durations
# ---------------------------------------------------------------------------

# Per-stress duration multipliers. These stay a coarse approximation
# of C's per-phoneme-class rules; the granular phoneme-class scheme
# (sonorant vs obstruent, monosyllable shortening) is a Phase-5
# follow-up and isn't needed to close the audible-prosody gap.
_STRESS_DURATION: Final[dict[str, float]] = {
    "1": 1.20,  # primary stress: 20 % longer
    "2": 1.05,
    "0": 0.85,  # unstressed: 15 % shorter
}

# Phrase-final lengthening for declarative sentences (Rule 2 in
# `p_us_tim.c`): the last vowel of a declarative gets ~30 % extra
# duration on top of any stress multiplier, giving the cadence-style
# "settle" at sentence end. Skipped for questions (which want the
# rising vowel to stay tight rather than drawl).
_PHRASE_FINAL_LENGTHENING: Final[float] = 1.30


# ---------------------------------------------------------------------------
# Phoneme classification helpers
# ---------------------------------------------------------------------------

# Vowel ARPABET roots. Match without trailing stress digits.
_VOWEL_ROOTS: Final[frozenset[str]] = frozenset(
    {
        "AA",
        "AE",
        "AH",
        "AO",
        "AW",
        "AY",
        "EH",
        "ER",
        "EY",
        "IH",
        "IY",
        "OW",
        "OY",
        "UH",
        "UW",
    }
)


def _root(code: str) -> str:
    """Return ``code`` without any trailing stress digit."""
    if code and code[-1].isdigit():
        return code[:-1]
    return code


def _is_vowel(code: str) -> bool:
    """Whether ``code`` is a vowel (any stress level)."""
    return _root(code) in _VOWEL_ROOTS


def _stress_digit(code: str) -> str:
    """Return the trailing stress digit of an ARPABET code, or ``""``."""
    if code and code[-1].isdigit():
        return code[-1]
    return ""


def _last_vowel_index(phonemes: Sequence[str]) -> int:
    """Return the index of the last vowel phoneme, or ``-1`` if none."""
    for i in range(len(phonemes) - 1, -1, -1):
        if _is_vowel(phonemes[i]):
            return i
    return -1


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def f0_contour(phonemes: Sequence[str], *, question: bool = False) -> list[float]:
    """Compute a per-phoneme F0 multiplier contour.

    The contour is the product of three components:

    1. A linear declination from ``_DECLINATION_START`` to
       ``_DECLINATION_END`` over the utterance.
    2. A per-stress F0 bump that decays with phrase-position
       (1st accent gets the full delta; later accents get smaller
       deltas per ``_PHRASE_POSITION_DECAY``).
    3. A final-syllable gesture: a sharp drop for declaratives or a
       sharp rise for questions, applied to the last vowel only.

    Args:
        phonemes: Flat ARPABET phoneme stream (may include ``"SIL"``).
        question: If True, the final-syllable gesture is a rise; if
            False, a fall.

    Returns:
        List of multiplicative factors, one per phoneme, suitable for
        scaling each frame's ``F0`` field.
    """
    n = len(phonemes)
    if n == 0:
        return []

    # 1. Declination across the utterance.
    contour: list[float] = []
    accent_count = 0
    for i, code in enumerate(phonemes):
        if code == "SIL":
            contour.append(1.0)
            continue
        alpha = i / max(1, n - 1)
        decl = _DECLINATION_START * (1.0 - alpha) + _DECLINATION_END * alpha
        # 2. Stress-accent bump with phrase-position decay. Only
        # primary- or secondary-stressed vowels register as accents
        # for the decay counter; unstressed vowels still get their
        # (smaller) delta but don't shrink subsequent accents.
        if _is_vowel(code):
            digit = _stress_digit(code)
            base_delta = _STRESS_F0_DELTA.get(digit, 0.0)
            if digit in {"1", "2"}:
                decay = _PHRASE_POSITION_DECAY[min(accent_count, len(_PHRASE_POSITION_DECAY) - 1)]
                decl *= 1.0 + base_delta * decay
                accent_count += 1
            else:
                # Unstressed: apply the full (negative) delta. There
                # is nothing to decay since unstressed syllables don't
                # produce a rise that the next accent would shrink.
                decl *= 1.0 + base_delta
        contour.append(decl)

    # 3. Final-syllable gesture: applied to the last vowel and the
    # phonemes that follow it (typically a coda consonant or two),
    # so the gesture extends across the whole final syllable rather
    # than just the vowel target.
    last_v = _last_vowel_index(phonemes)
    if last_v >= 0:
        gesture = _FINAL_RISE_FRACTION if question else _FINAL_FALL_FRACTION
        for i in range(last_v, n):
            if phonemes[i] != "SIL":
                contour[i] *= gesture

    return contour


def duration_factors(phonemes: Sequence[str], *, statement_final: bool = False) -> list[float]:
    """Compute per-phoneme duration multipliers.

    Stress-level multipliers (``_STRESS_DURATION``) apply to any
    phoneme carrying a stress digit. For declarative sentences,
    ``statement_final=True`` adds an extra phrase-final-lengthening
    factor to the last vowel.

    Args:
        phonemes: Flat ARPABET phoneme stream.
        statement_final: When True, the last vowel of the utterance
            gets ``_PHRASE_FINAL_LENGTHENING`` extra duration on top
            of any stress multiplier. Use this only when the
            sentence terminator is ``.`` or ``!``; questions keep
            the final vowel tight to support the rising gesture.

    Returns:
        List of duration multipliers, one per phoneme.
    """
    out: list[float] = []
    for code in phonemes:
        if code == "SIL" or not code:
            out.append(1.0)
            continue
        digit = _stress_digit(code)
        if digit:
            out.append(_STRESS_DURATION.get(digit, 1.0))
        else:
            out.append(1.0)

    if statement_final:
        last_v = _last_vowel_index(phonemes)
        if last_v >= 0:
            out[last_v] *= _PHRASE_FINAL_LENGTHENING

    return out


def looks_like_question(text: str) -> bool:
    """Return True if the text segment ends with ``?`` (trailing whitespace tolerated)."""
    return text.rstrip().endswith("?")


def split_sentences(text: str) -> list[tuple[str, bool]]:
    """Split ``text`` into individual sentences for per-sentence prosody.

    A sentence ends at the next ``.``, ``?``, or ``!`` (or end-of-text).
    The terminator is preserved on each sentence so downstream
    tokenisation still emits a trailing pause and so question
    intonation can be detected. Returned tuples are
    ``(sentence_text, is_question)``.

    Empty / whitespace-only inputs yield ``[]``. Text with no sentence
    punctuation is returned as a single statement.

    Args:
        text: Input string, possibly containing multiple sentences.

    Returns:
        List of ``(sentence, is_question)`` tuples in source order.
    """
    out: list[tuple[str, bool]] = []
    buf: list[str] = []
    for ch in text:
        buf.append(ch)
        if ch in ".?!":
            sentence = "".join(buf).strip()
            if sentence:
                out.append((sentence, ch == "?"))
            buf = []
    tail = "".join(buf).strip()
    if tail:
        out.append((tail, False))
    return out
