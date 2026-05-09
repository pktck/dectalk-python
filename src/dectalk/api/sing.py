"""Singing-mode public API.

Wraps :func:`dectalk.ph.singing.parse_singing` and the underlying
sequencer to render a singing-mode phoneme string into PCM samples.
The input syntax is ``"PHONEME<duration_ms,tone_number> ..."`` — for
example::

    "HH<200,5> AH<200,7> L<200,8> OW<400,9>"

would render a four-note "hello" with each phoneme held to a specific
duration and pitch. Tone numbers are 1-based; tone 1 corresponds to A2
(110 Hz) and each subsequent integer adds one chromatic semitone.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from dectalk.data.voices import VoicePreset, get_preset
from dectalk.hlsyn.llsyn import LLSynth
from dectalk.hlsyn.synthesize import ll_synthesize
from dectalk.hlsyn.vowels import default_speaker
from dectalk.nt.audio import write_wav
from dectalk.ph.phoneme_frames import get_frames
from dectalk.ph.singing import SingingNote, parse_singing


def sing(
    notes: str,
    *,
    voice: str | VoicePreset | None = None,
) -> NDArray[np.int16]:
    """Render a singing-mode phoneme string into ``int16`` PCM samples.

    Args:
        notes: Whitespace-separated singing tokens. Each token may
            optionally carry a ``<duration_ms,tone_number>`` suffix.
        voice: Voice preset by short name or :class:`VoicePreset`.

    Returns:
        1-D ``int16`` array of PCM samples at 11025 Hz.
    """
    parsed = parse_singing(notes)
    return _render_notes(parsed, voice=_resolve_voice(voice))


def sing_to_wav(
    notes: str,
    path: str | Path,
    *,
    voice: str | VoicePreset | None = None,
) -> None:
    """Render singing-mode notes and write the WAV to ``path``."""
    write_wav(sing(notes, voice=voice), path)


def _resolve_voice(voice: str | VoicePreset | None) -> VoicePreset | None:
    if voice is None:
        return None
    if isinstance(voice, VoicePreset):
        return voice
    return get_preset(voice)


def _render_notes(notes: list[SingingNote], *, voice: VoicePreset | None) -> NDArray[np.int16]:
    """Run each note through the synth, holding pitch + duration when set."""
    spkr = voice.speaker if voice is not None else default_speaker()
    synth = LLSynth(spkr=spkr)
    chunks: list[NDArray[np.int16]] = []

    for note in notes:
        frames = get_frames(note.code)
        # Pick the first frame; diphthongs would split across the duration.
        target = frames[0]
        if note.pitch_hz is not None and target.F0 != 0:
            target = replace(target, F0=round(note.pitch_hz * 10))
        elif voice is not None and target.F0 != 0:
            target = replace(target, F0=voice.f0_x10)

        ms = note.duration_ms if note.duration_ms is not None else 200
        n_samples = max(1, round(ms * 0.001 * spkr.SR))
        n_frames = max(1, n_samples // spkr.UI)
        out = np.zeros(spkr.UI * n_frames, dtype=np.int16)
        for fi in range(n_frames):
            ll_synthesize(synth, target, out[fi * spkr.UI : (fi + 1) * spkr.UI])
        chunks.append(out[:n_samples])

    return np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.int16)
