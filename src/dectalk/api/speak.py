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

from dectalk.cmd import SpeechState, parse
from dectalk.data.voices import PRESETS, VoicePreset, get_preset
from dectalk.dic import lookup
from dectalk.kernel.text import Token, TokenKind, tokenize
from dectalk.lts import lts
from dectalk.nt.audio import write_wav
from dectalk.ph.prosody import looks_like_question
from dectalk.ph.sequencer import synthesize_phonemes


class UnknownWordError(KeyError):
    """Raised when a word is not in the bundled lexicon."""


def text_to_phonemes(text: str, *, lang: str = "us", lts_fallback: bool = True) -> list[str]:
    """Convert text to a flat ARPABET phoneme stream with pause markers.

    Pause tokens are encoded as ``"SIL"`` phonemes so the same
    :func:`synthesize_phonemes` call handles them.

    Args:
        text: Input string to pronounce.
        lang: ``"us"`` (default) or ``"uk"`` — selects the bundled lexicon.
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
    return _tokens_to_phonemes(tokenize(text), lang=lang, lts_fallback=lts_fallback)


def _resolve_voice(voice: str | VoicePreset | None) -> VoicePreset | None:
    """Coerce a voice argument (None | name | preset) to a preset or None."""
    if voice is None:
        return None
    if isinstance(voice, VoicePreset):
        return voice
    return get_preset(voice)


def speak(
    text: str,
    *,
    rate: float = 1.0,
    voice: str | VoicePreset | None = None,
    lang: str = "us",
    lts_fallback: bool = True,
) -> NDArray[np.int16]:
    """Synthesize the given text into PCM samples (no playback / file output).

    Inline ``[:cmd value]`` directives in ``text`` are interpreted: ``[:dv
    NAME]`` switches voice, ``[:rate N]`` adjusts the rate (as a percent
    of nominal where 100 = normal), ``[:phoneme on/off]`` toggles direct
    phoneme input. The ``rate`` and ``voice`` keyword arguments seed the
    initial state; commands in the text override them.

    Args:
        text: Input string. May contain ``[:cmd value]`` directives.
        rate: Initial speaking-rate multiplier; > 1 slower, < 1 faster.
        voice: Initial voice preset (short name or :class:`VoicePreset`).
        lang: Language tag selecting the bundled lexicon (``"us"`` or
            ``"uk"``).
        lts_fallback: Whether to pronounce out-of-lexicon words via the
            letter-to-sound rules.

    Returns:
        ``int16`` PCM samples at 11025 Hz.

    Raises:
        UnknownWordError: If a word in ``text`` is not in the lexicon and
            ``lts_fallback`` is disabled.
        KeyError: If ``voice`` is a name that doesn't match a known preset.
    """
    initial_voice = voice if isinstance(voice, str) else None
    initial_state = SpeechState(voice=initial_voice, rate=rate)
    segments = parse(text, initial_state=initial_state)
    if not segments:
        return np.zeros(0, dtype=np.int16)

    chunks: list[NDArray[np.int16]] = []
    for seg in segments:
        if seg.state.phoneme_mode:
            phones = seg.body.split()
        else:
            phones = _tokens_to_phonemes(tokenize(seg.body), lang=lang, lts_fallback=lts_fallback)
        if not phones:
            continue
        preset = _resolve_voice(seg.state.voice)
        if preset is None and isinstance(voice, VoicePreset):
            preset = voice
        is_question = looks_like_question(seg.body)
        chunks.append(
            synthesize_phonemes(
                phones,
                rate=seg.state.rate,
                preset=preset,
                question=is_question,
            )
        )

    if not chunks:
        return np.zeros(0, dtype=np.int16)
    return np.concatenate(chunks)


def to_wav(
    text: str,
    path: str | Path,
    *,
    rate: float = 1.0,
    voice: str | VoicePreset | None = None,
    lang: str = "us",
    lts_fallback: bool = True,
) -> None:
    """Synthesize ``text`` and write the resulting audio to a WAV file.

    Args:
        text: Input string.
        path: Output WAV path. Parent directory must exist.
        rate: Speaking-rate multiplier.
        voice: See :func:`speak`.
        lang: See :func:`speak`.
        lts_fallback: See :func:`speak`.

    Raises:
        UnknownWordError: See :func:`speak`.
    """
    samples = speak(text, rate=rate, voice=voice, lang=lang, lts_fallback=lts_fallback)
    write_wav(samples, path)


def available_voices() -> list[str]:
    """Return the list of available voice preset names."""
    return sorted(PRESETS.keys())


def _tokens_to_phonemes(tokens: Iterable[Token], *, lang: str, lts_fallback: bool) -> list[str]:
    """Internal helper: flatten a token stream to ARPABET phonemes."""
    phonemes: list[str] = []
    for token in tokens:
        if token.kind is TokenKind.WORD:
            phones = lookup(token.text, lang=lang)
            if phones is None:
                if not lts_fallback:
                    raise UnknownWordError(f"word {token.text!r} is not in the {lang} lexicon.")
                phones = lts(token.text)
            phonemes.extend(phones)
        elif token.kind in (TokenKind.PAUSE_SHORT, TokenKind.PAUSE_LONG):
            # Both pauses currently map to a single SIL; later phases can
            # differentiate the pause length via a longer silence segment.
            phonemes.append("SIL")
    return phonemes
