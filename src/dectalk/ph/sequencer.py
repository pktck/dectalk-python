"""Phoneme-stream → Klatt-frame-stream → audio.

Takes an ARPABET phoneme sequence (e.g. ``["HH", "AH", "L", "OW"]``) and
produces 16-bit PCM audio at the synthesizer's native sample rate. The
sequencer:

1. Looks up each phoneme's nominal duration and Klatt-frame target via
   :mod:`dectalk.ph.phoneme_frames`.
2. Linearly interpolates frame parameters between adjacent phoneme
   targets to soften transitions.
3. Drives :func:`dectalk.hlsyn.synthesize.ll_synthesize` frame by frame,
   concatenating the sample-level output.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import fields
from typing import Final

import numpy as np
from numpy.typing import NDArray

from dectalk.hlsyn.llsyn import LLFrame, LLSynth, Speaker
from dectalk.hlsyn.synthesize import ll_synthesize
from dectalk.hlsyn.vowels import default_speaker
from dectalk.include.phonemes import get_phoneme
from dectalk.ph.phoneme_frames import get_frames

# Fraction of each segment used for the transition into the segment from
# the previous phoneme. The remaining samples are at the steady-state target.
_TRANSITION_FRACTION: Final[float] = 0.5

# Headroom we want to keep below int16 saturation. The synth's frication
# amplitudes can spike during dense /S/-/CH/ sequences; we apply a soft
# normalisation only when the unscaled peak exceeds this threshold.
_TARGET_PEAK_INT16: Final[int] = 28000


def _interpolate_frame(start: LLFrame, end: LLFrame, alpha: float) -> LLFrame:
    """Linearly interpolate every numeric field of an :class:`LLFrame`.

    Args:
        start: Source frame (alpha = 0 returns this).
        end: Target frame (alpha = 1 returns this).
        alpha: Mix in ``[0, 1]``.

    Returns:
        A fresh :class:`LLFrame` with interpolated integer fields.
    """
    a = max(0.0, min(1.0, alpha))
    out_kwargs: dict[str, int] = {}
    for f in fields(start):
        sv = getattr(start, f.name)
        ev = getattr(end, f.name)
        out_kwargs[f.name] = round(sv + (ev - sv) * a)
    return LLFrame(**out_kwargs)


def _phoneme_target_frames(code: str) -> tuple[LLFrame, ...]:
    """Get the target frame(s) for a phoneme.

    Wrapper around :func:`get_frames` that adds context-free fixups (no
    voicing for silences, etc.).
    """
    return get_frames(code)


def _segment_durations(codes: Sequence[str], rate_factor: float) -> list[int]:
    """Compute per-phoneme sample durations.

    Args:
        codes: Sequence of ARPABET phoneme codes.
        rate_factor: Speaking-rate multiplier (1.0 = nominal). Smaller is
            faster.

    Returns:
        List of integer sample counts, one per phoneme.
    """
    return [max(1, round(get_phoneme(c).duration_ms * 0.001 * 11025 * rate_factor)) for c in codes]


def synthesize_phonemes(
    codes: Iterable[str],
    *,
    speaker: Speaker | None = None,
    rate: float = 1.0,
) -> NDArray[np.int16]:
    """Synthesize a sequence of ARPABET phonemes into int16 PCM samples.

    Args:
        codes: Iterable of ARPABET symbols (case-insensitive). Stress
            digits (``"AH1"``) are accepted and discarded.
        speaker: Klatt speaker; defaults to :func:`default_speaker`.
        rate: Speaking-rate multiplier, > 1 slower, < 1 faster.

    Returns:
        1-D ``int16`` array of PCM samples at ``speaker.SR``.
    """
    spkr = speaker if speaker is not None else default_speaker()
    code_list = [c for c in codes if c.strip()]
    if not code_list:
        return np.zeros(0, dtype=np.int16)

    durations = _segment_durations(code_list, rate)
    synth = LLSynth(spkr=spkr)
    chunks: list[NDArray[np.int16]] = []

    # Build a flat list of (target_frame, sample_count) covering every phoneme,
    # treating diphthongs as two equal-length sub-segments.
    plan: list[tuple[LLFrame, int]] = []
    for code, total_samples in zip(code_list, durations, strict=True):
        targets = _phoneme_target_frames(code)
        if len(targets) == 1:
            plan.append((targets[0], total_samples))
        else:
            half = total_samples // 2
            plan.append((targets[0], half))
            plan.append((targets[1], total_samples - half))

    prev_frame = plan[0][0]
    for target, sample_count in plan:
        rendered = _render_segment(
            synth,
            prev_frame,
            target,
            sample_count,
            transition_frac=_TRANSITION_FRACTION,
        )
        chunks.append(rendered)
        prev_frame = target

    if not chunks:
        return np.zeros(0, dtype=np.int16)
    waveform = np.concatenate(chunks)
    return _soft_normalize(waveform)


def _soft_normalize(samples: NDArray[np.int16]) -> NDArray[np.int16]:
    """Scale the waveform down to ``_TARGET_PEAK_INT16`` if it exceeds it.

    A no-op when the peak is already within budget. We never *amplify* —
    quiet utterances stay quiet rather than getting boosted into
    artefacts.
    """
    peak = int(np.max(np.abs(samples))) if samples.size else 0
    if peak > _TARGET_PEAK_INT16:
        scale = _TARGET_PEAK_INT16 / peak
        return (samples.astype(np.float64) * scale).astype(np.int16)
    return samples


def _render_segment(
    synth: LLSynth,
    prev_target: LLFrame,
    target: LLFrame,
    n_samples: int,
    *,
    transition_frac: float,
) -> NDArray[np.int16]:
    """Render one phoneme segment with an interpolated lead-in.

    Args:
        synth: Synthesizer instance (state carries across calls).
        prev_target: Previous segment's target frame.
        target: Current segment's target frame.
        n_samples: Total samples to produce for this segment.
        transition_frac: Fraction of the segment spent transitioning from
            ``prev_target`` to ``target`` at the start. The remainder runs
            at ``target`` steady state.

    Returns:
        1-D int16 array of synthesized samples (length ``n_samples``,
        modulo rounding to whole frames).
    """
    samples_per_frame = synth.spkr.UI
    n_frames = max(1, math.ceil(n_samples / samples_per_frame))
    transition_frames = max(1, round(n_frames * transition_frac))

    out_buf = np.zeros(n_frames * samples_per_frame, dtype=np.int16)
    for fi in range(n_frames):
        if fi < transition_frames:
            alpha = (fi + 1) / transition_frames
            frame = _interpolate_frame(prev_target, target, alpha)
        else:
            frame = target
        ll_synthesize(synth, frame, out_buf[fi * samples_per_frame : (fi + 1) * samples_per_frame])

    # Trim back to the requested sample count.
    return out_buf[:n_samples]
