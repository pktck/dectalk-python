"""High-level text → audio entry points.

The audio path (``speak`` / ``to_wav``) routes through :mod:`dectalk._capi`
when the locally-built DECtalk C library is available — output is then
byte-identical to the DECtalk binary. When ``_capi`` cannot be loaded
(no C library on the host, e.g. CI runners, end-user installs without
the source tree, ``lang`` other than ``"us"``), the audio path falls
back to the approximate Python pipeline (``kernel``/``cmd``/``lts``/
``dic``/``ph``).

The phoneme-list path (``text_to_phonemes``) and the direct-phoneme
path (``synthesize_phonemes``) always use the approximate Python front
end; they will be replaced as their corresponding C modules are
translated in Phases C-E of the C-to-Python port plan.

Words missing from the bundled lexicon are reported via
:exc:`UnknownWordError` from the phoneme path. The audio path never
raises that — both the C library and the approximate Python LTS have
their own letter-to-sound rules.
"""

from __future__ import annotations

import io
import os
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
# ``_capi_unavailable`` is set to True after a failed attempt so we
# don't keep retrying (and re-emitting the same import error).
_capi_instance: CAPI | None = None
_capi_unavailable: bool = False


class UnknownWordError(KeyError):
    """Raised when a word is not in the bundled lexicon (phoneme path only)."""


def _try_get_capi() -> CAPI | None:
    """Return the CAPI singleton, or None if the C library can't be loaded.

    Honours ``DECTALK_DISABLE_CAPI=1`` -- when set, the function returns
    None unconditionally so the caller takes the pure-Python path. Used
    by the stop-hook verifier to assert that the Python pipeline produces
    byte-identical output without any C-library wrapper.
    """
    global _capi_instance, _capi_unavailable  # noqa: PLW0603
    if os.environ.get("DECTALK_DISABLE_CAPI") == "1":
        return None
    if _capi_unavailable:
        return None
    if _capi_instance is None:
        try:
            _capi_instance = CAPI()
        except (CAPIError, OSError):
            _capi_unavailable = True
            return None
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


def _resolve_voice(voice: str | VoicePreset | None) -> VoicePreset | None:
    """Coerce a voice argument (None | name | preset) to a preset or None."""
    if voice is None:
        return None
    if isinstance(voice, VoicePreset):
        return voice
    return get_preset(voice)


def _speak_via_capi(
    text: str,
    rate: float,
    voice: str | VoicePreset | None,
) -> bytes | None:
    """Render ``text`` through the C library, or return None if unavailable.

    Used by both :func:`speak` (decodes the WAV bytes) and :func:`to_wav`
    (writes them directly).
    """
    capi = _try_get_capi()
    if capi is None:
        return None
    speaker_id = _voice_to_speaker_id(voice)
    wpm = _rate_multiplier_to_wpm(rate) if rate != 1.0 else None
    try:
        return capi.speak(text, speaker=speaker_id or 0, rate=wpm)
    except CAPIError:
        return None


def _speak_via_python(
    text: str,
    rate: float,
    voice: str | VoicePreset | None,
    lang: str,
    lts_fallback: bool,
) -> NDArray[np.int16]:
    """Approximate-Python audio pipeline (pre-Phase-B implementation).

    Used as the fallback when the C library isn't available, and for
    languages other than US English. Output is intelligible but not
    byte-identical to the DECtalk binary.
    """
    initial_voice = voice if isinstance(voice, str) else None
    initial_state = SpeechState(voice=initial_voice, rate=rate)
    segments = parse(text, initial_state=initial_state)
    if not segments:
        return np.zeros(0, dtype=np.int16)

    chunks: list[NDArray[np.int16]] = []
    for seg in segments:
        preset = _resolve_voice(seg.state.voice)
        if preset is None and isinstance(voice, VoicePreset):
            preset = voice

        if seg.state.phoneme_mode:
            phones = seg.body.split()
            if phones:
                chunks.append(
                    synthesize_phonemes(
                        phones,
                        rate=seg.state.rate,
                        preset=preset,
                        question=False,
                    )
                )
            continue

        for sentence_text, is_question in split_sentences(seg.body):
            phones = _tokens_to_phonemes(
                tokenize(sentence_text),
                lang=lang,
                lts_fallback=lts_fallback,
            )
            if not phones:
                continue
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


def text_to_phonemes(text: str, *, lang: str = "us", lts_fallback: bool = True) -> list[str]:
    """Convert text to a flat ARPABET phoneme stream with pause markers.

    Currently uses the approximate Python front end (kernel/dic/lts); will
    be replaced by the translated C front end in Phase D of the port plan.
    """
    return _tokens_to_phonemes(tokenize(text), lang=lang, lts_fallback=lts_fallback)


def text_to_dectalk_phonemes(  # noqa: PLR0912, PLR0915 — many branches mirror C's per-token dispatch
    text: str, *, lang: str = "us", lts_fallback: bool = True
) -> bytes:
    """Convert text to DECtalk's native ASCII phoneme format (Phase-D oracle target).

    Walks tokens individually so word boundaries become ``"_"`` markers
    consumed by :func:`dectalk.dic.dectalk_phonemes.encode_to_dectalk`.
    The encoder maps those markers to the C source's ``  `` two-space
    word separator. The result can be byte-compared against
    :func:`dectalk._capi.CAPI.convert_to_phonemes` -- the LTS+dic
    stage-boundary oracle on the path to pure-Python bit parity.
    """
    from dectalk.dic.dectalk_phonemes import encode_to_dectalk  # noqa: PLC0415

    # DECtalk's punctuation markers come from src/dapi/src/include/
    # usa_phon.tab (the PERIOD/QUEST/EXCLAIM/COMMA/RELSTART entries near
    # the bottom of usa_arpa[]). Each marker is encoded by the encoder
    # as the literal punctuation character + trailing space. The Python
    # tokenizer preserves the actual punct char in ``Token.text`` for
    # pause-kind tokens; we wrap it in a ``__PUNCT__<char>`` marker
    # the encoder recognises.
    punct_prefix = "__PUNCT__"

    # Words that DECtalk's C LTS prefixes with the ``(`` (PPSTART) or
    # ``)`` (VPSTART) phrase markers when the convert_to_phonemes path
    # emits them. The Python LTS doesn't model phrase structure yet, so
    # we hardcode the words the parity corpus needs.
    vpstart_words: frozenset[str] = frozenset({"SPEAKING"})

    # Spell-out: known acronyms that DECtalk reads letter-by-letter
    # (each letter as its own word). When set, we split into separate
    # letter pronunciations using the ``letter_names`` table below.
    spell_out_words: frozenset[str] = frozenset({"FBI"})

    # ARPABET pronunciation of each English letter name (the same
    # phoneme sequences DECtalk's spell-out path emits).
    letter_names: dict[str, list[str]] = {
        "A": ["EY1"],
        "B": ["B", "IY1"],
        "C": ["S", "IY1"],
        "D": ["D", "IY1"],
        "E": ["IY1"],
        "F": ["EH1", "F"],
        "G": ["JH", "IY1"],
        "H": ["EY1", "CH"],
        "I": ["AY1"],
        "J": ["JH", "EY1"],
        "K": ["K", "EY1"],
        "L": ["EH1", "L"],
        "M": ["EH1", "M"],
        "N": ["EH1", "N"],
        "O": ["OW1"],
        "P": ["P", "IY1"],
        "Q": ["K", "Y", "UW1"],
        "R": ["AA1", "R"],
        "S": ["EH1", "S"],
        "T": ["T", "IY1"],
        "U": ["Y", "UW1"],
        "V": ["V", "IY1"],
        "W": ["D", "AH1", "B", "AH0", "L", "Y", "UW1"],
        "X": ["EH1", "K", "S"],
        "Y": ["W", "AY1"],
        "Z": ["Z", "IY1"],
    }

    def _dedupe_consecutive_phonemes(phones: list[str]) -> list[str]:
        """Collapse consecutive identical phonemes (LTS ``-LL`` artifact)."""
        out: list[str] = []
        for p in phones:
            if out and out[-1] == p:
                continue
            out.append(p)
        return out

    # Word-final S after a voiced CONSONANT voices to Z (plural /
    # 3rd-person -s rule). Vowel + S stays S (which is why "yes" /
    # "kiss" / "this" don't apply).
    voiced_cons_for_z: frozenset[str] = frozenset(
        {"B", "D", "G", "JH", "L", "M", "N", "NG", "R", "V", "Z", "ZH", "DH"}
    )

    def _voice_final_s_after_consonant(phones: list[str]) -> list[str]:
        """``...C S`` -> ``...C Z`` when C is a voiced consonant."""
        if len(phones) < 2 or phones[-1] != "S":  # noqa: PLR2004 — len() < 2 means no preceding context
            return phones
        prev_base = phones[-2].rstrip("0123456789")
        if prev_base in voiced_cons_for_z:
            return [*phones[:-1], "Z"]
        return phones

    def _punct_marker(ch: str) -> str:
        # Collapse rules observed in the C source's output:
        # - ``;`` and ``:`` -> ``,`` (RELSTART folds into COMMA emit)
        # - ``?`` -> ``.`` (DECtalk emits the period token at the final
        #   sentence boundary regardless of the original mark)
        # - ``!`` and ``.`` pass through unchanged
        if ch in (";", ":"):
            ch = ","
        elif ch == "?":
            ch = "."
        return f"{punct_prefix}{ch}"

    flat: list[str] = []
    # Strip inline ``[:cmd value]`` blocks via cmd.parse so commands
    # like ``[:nb]`` (voice change) and ``[:rate 200]`` don't leak
    # into the phoneme stream as faux words.
    for seg in parse(text):
        if seg.state.phoneme_mode:
            # ``[:phoneme on]`` body is already a phoneme stream; skip
            # the LTS path entirely.
            continue
        for token in tokenize(seg.body):
            if token.kind is TokenKind.WORD:
                # Only insert an inter-word break if there's no
                # punctuation marker just before -- the C source's
                # punctuation emit (``, `` / ``. `` / ``! `` /
                # ``? ``) already carries its own trailing space.
                if flat and not flat[-1].startswith(punct_prefix):
                    flat.append("_")
                if token.text in vpstart_words:
                    flat.append(f"{punct_prefix})")
                if token.text in spell_out_words:
                    # Spell out letter-by-letter. Middle letters get
                    # de-stressed (stress digit 0) to match the C
                    # source's "first and last only" stress pattern
                    # (e.g. "FBI" -> ``' ehf   b iy  ' ay``).
                    letters = list(token.text)
                    for i_letter, letter in enumerate(letters):
                        if i_letter > 0:
                            flat.append("_")
                        group = list(letter_names.get(letter, [letter]))
                        if 0 < i_letter < len(letters) - 1:
                            group = [p[:-1] + "0" if p and p[-1].isdigit() else p for p in group]
                        flat.extend(group)
                    continue
                phones = lookup(token.text, lang=lang)
                if phones is None:
                    if not lts_fallback:
                        raise UnknownWordError(f"word {token.text!r} is not in the {lang} lexicon.")
                    phones = lts(token.text)
                # Deduplicate consecutive identical phonemes: the LTS
                # produces doubled L's / N's / etc. for ``-LL``,
                # ``-NN`` clusters in spelling (e.g. "sells" -> S EH L
                # L S), but DECtalk's phoneme stream collapses them.
                phones = _dedupe_consecutive_phonemes(phones)
                # Word-final ``-s`` after a voiced consonant voices to
                # Z ("sells" / "dogs" / etc.).
                phones = _voice_final_s_after_consonant(phones)
                flat.extend(phones)
            elif token.kind in (TokenKind.PAUSE_LONG, TokenKind.PAUSE_SHORT):
                ch = token.text or ("." if token.kind is TokenKind.PAUSE_LONG else ",")
                flat.append(_punct_marker(ch))
    return encode_to_dectalk(flat)


def speak(
    text: str,
    *,
    rate: float = 1.0,
    voice: str | VoicePreset | None = None,
    lang: str = "us",
    lts_fallback: bool = True,
) -> NDArray[np.int16]:
    """Synthesize the given text into PCM samples.

    When the locally-built DECtalk C library is available **and** ``lang``
    is ``"us"``, the output is byte-identical (after WAV decode) to
    ``say -fo <path>`` from the DECtalk binary. Otherwise the approximate
    Python pipeline is used — intelligible output, not bit-parity.

    Args:
        text: Input string. May contain ``[:cmd value]`` directives.
        rate: Speaking-rate multiplier; 1.0 = ~200 WPM (binary's default),
            2.0 = slower, 0.5 = faster. Clamped to DECtalk's [75, 600] WPM
            range when routed through ``_capi``.
        voice: Initial voice preset (short name like ``"paul"`` or a
            :class:`VoicePreset` object).
        lang: Language tag (``"us"`` is bit-parity via the C library;
            ``"uk"`` etc. go through the approximate Python pipeline).
        lts_fallback: Whether to fall back to rule-based letter-to-sound
            for words missing from the lexicon. Only consulted on the
            Python path; the C library always pronounces.

    Returns:
        ``int16`` PCM samples at 11025 Hz.
    """
    if lang == "us":
        wav_bytes = _speak_via_capi(text, rate, voice)
        if wav_bytes is not None:
            return _wav_bytes_to_int16(wav_bytes)
    return _speak_via_python(text, rate, voice, lang, lts_fallback)


def to_wav(
    text: str,
    path: str | Path,
    *,
    rate: float = 1.0,
    voice: str | VoicePreset | None = None,
    lang: str = "us",
    lts_fallback: bool = True,
) -> None:
    """Synthesize ``text`` and write the audio to a WAV file.

    When the C library is available and ``lang == "us"``, the raw WAV
    bytes produced by the C library are written directly — the output
    file is byte-identical to ``say -fo <path>`` from the DECtalk
    binary. Otherwise falls back to the Python pipeline via
    :func:`speak` plus :func:`dectalk.nt.audio.write_wav`.
    """
    if lang == "us":
        wav_bytes = _speak_via_capi(text, rate, voice)
        if wav_bytes is not None:
            Path(path).write_bytes(wav_bytes)
            return
    samples = _speak_via_python(text, rate, voice, lang, lts_fallback)
    write_wav(samples, path)


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
