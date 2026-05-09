"""High-level text → audio entry points.

Wires together the front end (:mod:`dectalk.kernel.text` for tokenization,
:mod:`dectalk.dic` for word → phoneme lookup) and the synthesizer
(:mod:`dectalk.ph.sequencer` for phoneme-string synthesis).

Words missing from the bundled lexicon are reported via
:exc:`UnknownWordError`; later phases will plug in either CMUDict or an
LTS rule pass to handle them automatically.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from dectalk.dic import lookup
from dectalk.kernel.text import Token, TokenKind, tokenize
from dectalk.lts import lts
from dectalk.nt.audio import write_wav
from dectalk.ph.sequencer import synthesize_phonemes


class UnknownWordError(KeyError):
    """Raised when a word is not in the bundled lexicon."""


def text_to_phonemes(text: str, *, lts_fallback: bool = True) -> list[str]:
    """Convert text to a flat ARPABET phoneme stream with pause markers.

    Pause tokens are encoded as ``"SIL"`` phonemes so the same
    :func:`synthesize_phonemes` call handles them.

    Args:
        text: Input string to pronounce.
        lts_fallback: When True (default), words missing from the bundled
            lexicon are pronounced via the rule-based letter-to-sound
            engine in :mod:`dectalk.lts`. When False, an
            :exc:`UnknownWordError` is raised instead.

    Returns:
        Flat list of ARPABET phonemes (vowels with stress digits, plus
        ``"SIL"`` pauses).

    Raises:
        UnknownWordError: If a token's word form is missing from the
            lexicon and ``lts_fallback`` is False.
    """
    return _tokens_to_phonemes(tokenize(text), lts_fallback=lts_fallback)


def speak(text: str, *, rate: float = 1.0, lts_fallback: bool = True) -> NDArray[np.int16]:
    """Synthesize the given text into PCM samples (no playback / file output).

    Args:
        text: Input string.
        rate: Speaking-rate multiplier; > 1 slower, < 1 faster.
        lts_fallback: Whether to pronounce out-of-lexicon words via the
            letter-to-sound rules.

    Returns:
        ``int16`` PCM samples at 11025 Hz.

    Raises:
        UnknownWordError: If a word in ``text`` is not in the lexicon and
            ``lts_fallback`` is disabled.
    """
    phonemes = text_to_phonemes(text, lts_fallback=lts_fallback)
    return synthesize_phonemes(phonemes, rate=rate)


def to_wav(text: str, path: str | Path, *, rate: float = 1.0, lts_fallback: bool = True) -> None:
    """Synthesize ``text`` and write the resulting audio to a WAV file.

    Args:
        text: Input string.
        path: Output WAV path. Parent directory must exist.
        rate: Speaking-rate multiplier.
        lts_fallback: See :func:`speak`.

    Raises:
        UnknownWordError: See :func:`speak`.
    """
    samples = speak(text, rate=rate, lts_fallback=lts_fallback)
    write_wav(samples, path)


def _tokens_to_phonemes(tokens: Iterable[Token], *, lts_fallback: bool) -> list[str]:
    """Internal helper: flatten a token stream to ARPABET phonemes."""
    phonemes: list[str] = []
    for token in tokens:
        if token.kind is TokenKind.WORD:
            phones = lookup(token.text)
            if phones is None:
                if not lts_fallback:
                    raise UnknownWordError(f"word {token.text!r} is not in the bundled lexicon.")
                phones = lts(token.text)
            phonemes.extend(phones)
        elif token.kind in (TokenKind.PAUSE_SHORT, TokenKind.PAUSE_LONG):
            # Both pauses currently map to a single SIL; later phases can
            # differentiate the pause length via a longer silence segment.
            phonemes.append("SIL")
    return phonemes
