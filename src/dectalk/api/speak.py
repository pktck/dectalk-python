"""High-level text → audio entry points.

Audio path (``speak`` / ``to_wav``) routes through :mod:`dectalk._capi`
so output is byte-identical to the DECtalk binary. The phoneme-list
path (``text_to_phonemes``) and the direct-phoneme path
(``synthesize_phonemes``) still use the approximate Python front end;
they will be replaced as their corresponding C modules are translated
in Phases C-E of the C-to-Python port plan.

Words missing from the bundled lexicon are reported via
:exc:`UnknownWordError` from the phoneme path. The audio path never
raises that — the C library has its own letter-to-sound rules.
"""

from __future__ import annotations

import io
import wave
from collections.abc import Iterable
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from dectalk._capi import CAPI, CAPIError
from dectalk.cmd import SpeechState, parse
from dectalk.data.voices import PRESETS, VoicePreset, get_preset
from dectalk.dic import lookup
from dectalk.kernel.text import Token, TokenKind, tokenize
from dectalk.lts import lts
from dectalk.nt.audio import write_wav
from dectalk.ph.prosody import split_sentences
from dectalk.ph.sequencer import synthesize_phonemes

# Nominal speaking rate that maps to ``rate=1.0`` in the public API.
# DECtalk's TextToSpeechSetRate accepts words-per-minute in [75, 600];
# 200 wpm is the binary's default.
_DEFAULT_WPM: int = 200

# Expected WAV format from _capi: 16-bit signed mono.
_INT16_SAMPLE_WIDTH: int = 2
_MONO_CHANNELS: int = 1

# Lazily-constructed CAPI singleton; created on first audio call so
# imports of this module don't require the C library to be present.
_capi_instance: CAPI | None = None


class UnknownWordError(KeyError):
    """Raised when a word is not in the bundled lexicon (phoneme path only)."""


def _get_capi() -> CAPI:
    """Return a process-wide ``CAPI`` instance, creating it on first use."""
    global _capi_instance  # noqa: PLW0603
    if _capi_instance is None:
        _capi_instance = CAPI()
    return _capi_instance


def _voice_to_speaker_id(voice: str | VoicePreset | None) -> int | None:
    """Map a public-API ``voice`` argument to a DECtalk speaker ID.

    Returns None when no speaker change is needed (default = Perfect Paul).
    """
    if voice is None:
        return None
    preset = voice if isinstance(voice, VoicePreset) else get_preset(voice)
    return int(preset.voice)


def _rate_multiplier_to_wpm(rate: float) -> int:
    """Convert a multiplier (1.0 = normal, 2.0 = slower) to WPM."""
    return max(75, min(600, round(_DEFAULT_WPM / rate)))


def _wav_bytes_to_int16(wav_bytes: bytes) -> NDArray[np.int16]:
    """Decode a 16-bit mono WAV byte string into an ``int16`` NumPy array."""
    with wave.open(io.BytesIO(wav_bytes), "rb") as fh:
        if fh.getsampwidth() != _INT16_SAMPLE_WIDTH or fh.getnchannels() != _MONO_CHANNELS:
            raise CAPIError(
                f"_capi returned non-int16-mono WAV "
                f"(sampwidth={fh.getsampwidth()}, channels={fh.getnchannels()})"
            )
        raw = fh.readframes(fh.getnframes())
    return np.frombuffer(raw, dtype=np.int16)


def text_to_phonemes(text: str, *, lang: str = "us", lts_fallback: bool = True) -> list[str]:
    """Convert text to a flat ARPABET phoneme stream with pause markers.

    Currently uses the approximate Python front end (kernel/dic/lts); will
    be replaced by the translated C front end in Phase D of the port plan.
    """
    return _tokens_to_phonemes(tokenize(text), lang=lang, lts_fallback=lts_fallback)


def speak(
    text: str,
    *,
    rate: float = 1.0,
    voice: str | VoicePreset | None = None,
    lang: str = "us",
    lts_fallback: bool = True,
) -> NDArray[np.int16]:
    """Synthesize the given text into PCM samples.

    Output is byte-identical to the DECtalk binary's ``-fo`` WAV output
    (decoded to ``int16``). Inline ``[:cmd value]`` directives in ``text``
    are honoured by the C library's command parser.

    Args:
        text: Input string. May contain ``[:cmd value]`` directives.
        rate: Speaking-rate multiplier; 1.0 = ~200 WPM, 2.0 = slower,
            0.5 = faster. Clamped to DECtalk's [75, 600] WPM range.
        voice: Initial voice preset (short name like ``"paul"`` or a
            :class:`VoicePreset` object). ``None`` keeps the C library
            default (Perfect Paul).
        lang: Language tag; only ``"us"`` is currently supported by the
            ctypes wrapper.
        lts_fallback: Ignored. Retained for backwards-compat; the C
            library always pronounces unknown words via its built-in
            letter-to-sound rules.

    Returns:
        ``int16`` PCM samples at 11025 Hz.

    Raises:
        NotImplementedError: For ``lang != "us"``.
        CAPIError: If the local C library cannot be loaded.
    """
    del lts_fallback  # documented as ignored; kept for API stability.
    if lang != "us":
        raise NotImplementedError(
            f"_capi-routed speak() currently supports lang='us' only (got {lang!r})."
        )
    speaker_id = _voice_to_speaker_id(voice)
    wpm = _rate_multiplier_to_wpm(rate) if rate != 1.0 else None
    capi = _get_capi()
    wav_bytes = capi.speak(text, speaker=speaker_id or 0, rate=wpm)
    return _wav_bytes_to_int16(wav_bytes)


def to_wav(
    text: str,
    path: str | Path,
    *,
    rate: float = 1.0,
    voice: str | VoicePreset | None = None,
    lang: str = "us",
    lts_fallback: bool = True,
) -> None:
    """Synthesize ``text`` and write the WAV file produced by the C library.

    Unlike :func:`speak`, this writes the raw WAV bytes produced by the C
    library directly to ``path`` without re-encoding. The output file is
    byte-identical to ``say -fo <path>`` from the DECtalk binary.

    Raises the same exceptions as :func:`speak`.
    """
    del lts_fallback
    if lang != "us":
        raise NotImplementedError(
            f"_capi-routed to_wav() currently supports lang='us' only (got {lang!r})."
        )
    speaker_id = _voice_to_speaker_id(voice)
    wpm = _rate_multiplier_to_wpm(rate) if rate != 1.0 else None
    capi = _get_capi()
    wav_bytes = capi.speak(text, speaker=speaker_id or 0, rate=wpm)
    Path(path).write_bytes(wav_bytes)


def available_voices() -> list[str]:
    """Return the list of available voice preset names."""
    return sorted(PRESETS.keys())


def _tokens_to_phonemes(tokens: Iterable[Token], *, lang: str, lts_fallback: bool) -> list[str]:
    """Internal helper: flatten a token stream to ARPABET phonemes (approx. path)."""
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
            phonemes.append("SIL")
    return phonemes


# Re-export the approximate-path symbols so existing imports still resolve.
__all__ = [
    "UnknownWordError",
    "available_voices",
    "speak",
    "synthesize_phonemes",
    "text_to_phonemes",
    "to_wav",
]

# Suppress unused-import warnings for re-exports.
_ = (SpeechState, parse, split_sentences, synthesize_phonemes, write_wav)
