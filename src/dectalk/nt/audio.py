"""WAV file I/O and live audio playback for DECtalk synthesis output.

DECtalk synthesizes 16-bit signed PCM at 11025 Hz (its native rate). This
module provides a thin, fully-typed wrapper for writing those samples to a
WAV file or pushing them through the speakers.

The C original (`src/dapi/src/nt/`) was Windows-NT-specific WaveOut glue. We
replace it with `wave` (standard library) and `sounddevice` (cross-platform
PortAudio bindings with prebuilt wheels), so no compiled binaries ship from
this project.
"""

from __future__ import annotations

import wave
from pathlib import Path
from typing import Final

import numpy as np
from numpy.typing import NDArray

# DECtalk's native output format. Kept as constants so callers don't repeat
# magic numbers and the synthesizer module can import them too.
SAMPLE_RATE_HZ: Final[int] = 11025
SAMPLE_WIDTH_BYTES: Final[int] = 2
CHANNELS: Final[int] = 1


def write_wav(samples: NDArray[np.int16], path: str | Path) -> None:
    """Write 16-bit mono PCM samples to a WAV file at the DECtalk sample rate.

    Args:
        samples: 1-D `int16` array of PCM samples. Must be `int16`; other
            dtypes raise `TypeError` rather than silently lossy-casting.
        path: Destination path. Parent directories must already exist.

    Raises:
        TypeError: If `samples.dtype` is not `int16` or `samples` is not 1-D.
    """
    if samples.dtype != np.int16:
        raise TypeError(
            f"samples must be int16 PCM; got dtype={samples.dtype}. "
            f"Cast explicitly with `samples.astype(np.int16)` if that is what you want."
        )
    if samples.ndim != 1:
        raise TypeError(f"samples must be 1-D; got shape={samples.shape}")

    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(CHANNELS)
        fh.setsampwidth(SAMPLE_WIDTH_BYTES)
        fh.setframerate(SAMPLE_RATE_HZ)
        fh.writeframes(samples.tobytes())


def read_wav(path: str | Path) -> NDArray[np.int16]:
    """Read a 16-bit mono WAV file at the DECtalk sample rate into an int16 array.

    Used primarily by the audio-regression test harness.

    Args:
        path: Source WAV path.

    Returns:
        1-D `int16` array of PCM samples.

    Raises:
        ValueError: If the file is not 16-bit mono at `SAMPLE_RATE_HZ`.
    """
    with wave.open(str(path), "rb") as fh:
        nchannels = fh.getnchannels()
        sampwidth = fh.getsampwidth()
        framerate = fh.getframerate()
        nframes = fh.getnframes()
        if nchannels != CHANNELS:
            raise ValueError(f"expected {CHANNELS}-channel WAV, got {nchannels}")
        if sampwidth != SAMPLE_WIDTH_BYTES:
            raise ValueError(f"expected {SAMPLE_WIDTH_BYTES}-byte samples, got {sampwidth}")
        if framerate != SAMPLE_RATE_HZ:
            raise ValueError(f"expected {SAMPLE_RATE_HZ} Hz sample rate, got {framerate}")
        raw = fh.readframes(nframes)

    return np.frombuffer(raw, dtype=np.int16).copy()


def play(samples: NDArray[np.int16], *, blocking: bool = True) -> None:
    """Play 16-bit mono PCM samples through the default audio device.

    Args:
        samples: 1-D `int16` array of PCM samples at `SAMPLE_RATE_HZ`.
        blocking: If True (default), wait for playback to finish before
            returning. If False, return immediately and play in the
            background; the caller is responsible for keeping the process
            alive long enough for playback to complete.

    Raises:
        TypeError: If `samples.dtype` is not `int16` or it is not 1-D.
        RuntimeError: If `sounddevice` cannot open an output stream (e.g.
            no audio device available, as in many CI environments).
    """
    if samples.dtype != np.int16:
        raise TypeError(f"samples must be int16; got dtype={samples.dtype}")
    if samples.ndim != 1:
        raise TypeError(f"samples must be 1-D; got shape={samples.shape}")

    # Lazy import so a missing audio backend doesn't break write-only users.
    import sounddevice  # noqa: PLC0415  # pyright: ignore[reportMissingTypeStubs]

    sounddevice.play(samples, samplerate=SAMPLE_RATE_HZ)  # pyright: ignore[reportUnknownMemberType]
    if blocking:
        sounddevice.wait()  # pyright: ignore[reportUnknownMemberType]


def sine_tone(freq_hz: float, duration_sec: float, *, amplitude: float = 0.5) -> NDArray[np.int16]:
    """Generate a pure sine tone for self-test and smoke purposes.

    Args:
        freq_hz: Tone frequency in Hertz.
        duration_sec: Duration in seconds.
        amplitude: Peak amplitude in `[0.0, 1.0]`. Values >1 will clip.

    Returns:
        1-D `int16` array of PCM samples ready to feed `play` or `write_wav`.
    """
    n_samples = round(duration_sec * SAMPLE_RATE_HZ)
    t = np.arange(n_samples, dtype=np.float64) / SAMPLE_RATE_HZ
    wave_f = np.sin(2.0 * np.pi * freq_hz * t) * amplitude
    return (wave_f * np.iinfo(np.int16).max).astype(np.int16)
