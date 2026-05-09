"""Unit tests for the audio I/O module (`dectalk.nt.audio`)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from dectalk.nt.audio import (
    CHANNELS,
    SAMPLE_RATE_HZ,
    SAMPLE_WIDTH_BYTES,
    read_wav,
    sine_tone,
    write_wav,
)


def test_sine_tone_shape_and_dtype() -> None:
    tone = sine_tone(440.0, 0.5)
    assert tone.dtype == np.int16
    assert tone.ndim == 1
    assert tone.shape[0] == round(0.5 * SAMPLE_RATE_HZ)


def test_sine_tone_amplitude_within_range() -> None:
    tone = sine_tone(440.0, 0.1, amplitude=0.5)
    peak = int(np.max(np.abs(tone)))
    half_int16 = np.iinfo(np.int16).max // 2
    assert peak <= np.iinfo(np.int16).max
    assert peak >= half_int16 - 5  # tolerate 1-LSB rounding


def test_write_wav_roundtrip(tmp_path: Path) -> None:
    out = tmp_path / "tone.wav"
    tone = sine_tone(440.0, 0.25)
    write_wav(tone, out)

    assert out.exists()
    expected_bytes = tone.size * SAMPLE_WIDTH_BYTES * CHANNELS
    # WAV header is 44 bytes for canonical PCM mono.
    assert out.stat().st_size >= expected_bytes


def test_read_wav_recovers_samples(tmp_path: Path) -> None:
    out = tmp_path / "tone.wav"
    tone = sine_tone(440.0, 0.1)
    write_wav(tone, out)
    recovered = read_wav(out)
    assert recovered.dtype == np.int16
    assert recovered.shape == tone.shape
    np.testing.assert_array_equal(recovered, tone)


def test_write_wav_rejects_non_int16_dtype(tmp_path: Path) -> None:
    bad = np.zeros(100, dtype=np.float32)
    with pytest.raises(TypeError, match="int16"):
        write_wav(bad, tmp_path / "x.wav")  # pyright: ignore[reportArgumentType]


def test_write_wav_rejects_2d_arrays(tmp_path: Path) -> None:
    bad = np.zeros((10, 2), dtype=np.int16)
    with pytest.raises(TypeError, match="1-D"):
        write_wav(bad, tmp_path / "x.wav")
